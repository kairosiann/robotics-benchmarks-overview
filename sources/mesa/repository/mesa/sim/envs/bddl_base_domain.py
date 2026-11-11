"""
Base environment class for BDDL-based tasks in MESA (adapted from LIBERO).
"""

import datetime
import json
import os
import pathlib
import time
import uuid
import xml.etree.ElementTree as ET

import cv2
import mujoco
import numpy as np
import robosuite
import robosuite.utils.transform_utils as T
import transforms3d as t3d
from robosuite.environments.manipulation.manipulation_env import ManipulationEnv
from robosuite.models.tasks import ManipulationTask
from robosuite.utils.errors import RandomizationError
from robosuite.utils.observables import Observable, sensor
from robosuite.utils.placement_samplers import SequentialCompositeSampler

import mesa
import mesa.sim.envs.sensor_utils as sensor_utils
import mesa.sim.envs.utils as env_utils
import mesa.sim.macros as macros
from mesa.sim import ASSETS_ROOT as ASSETS_ROOT
from mesa.sim.envs.arenas import MimicLabsTableArena
from mesa.sim.envs.object_states import *
from mesa.sim.envs.objects import *
from mesa.sim.envs.regions import *

MIMICLABS_TMP_FOLDER = macros.MESA_TMP_FOLDER

TASK_MAPPING = {}


def register_problem(target_class):
    TASK_MAPPING[target_class.__name__.lower()] = target_class


class BDDLBaseDomain(ManipulationEnv):
    """
    A base domain for parsing bddl files.
    """

    workspace_name = None

    def __init__(
        self,
        *,
        parsed_problem,
        robots,
        init_noops=50,
        controller_configs=None,
        use_object_obs=True,
        reward_scale=1.0,
        reward_shaping=False,
        placement_initializer=None,
        object_property_initializers=None,
        workspace_offset=(0.0, 0.0, 0.0),
        arena_type="table",
        scene_xml="scenes/mimiclabs_scenes/lab2/lab2.xml",
        scene_properties={},
        return_2d_bboxes=False,
        return_3d_bboxes=False,
        return_segmentation_masks=False,
        deterministic_reset=False,
        **kwargs,
    ):
        # Skip random object placement on reset. Set when the scene will be restored from a saved
        # init state (e.g. evaluation), so crowded scenes can't fail placement before being overwritten.
        self.deterministic_reset_override = deterministic_reset

        # settings for table top (hardcoded since it's not an essential part of the environment)
        self.workspace_offset = workspace_offset
        self.init_noops = init_noops

        # YAM arms -> bimesa assets; everything else (Panda) -> mesa.
        robot_names = robots if isinstance(robots, (list, tuple)) else [robots]
        self.object_format = (
            "bimesa" if any("yam" in str(r).lower() for r in robot_names) else "mesa"
        )

        if controller_configs is None:
            controller_configs = json.load(open(os.path.join(mesa.__path__[0], "config", "controllers", "osc_pose.json"), "r"))

        try:
            if type(controller_configs) is list:
                self.control_delta = controller_configs[0]["body_parts"]["right"]["input_type"] == "delta"
                self.controller_type = controller_configs[0]["body_parts"]["right"]["type"].lower()
            else:
                self.control_delta = controller_configs["body_parts"]["right"]["input_type"] == "delta"
                self.controller_type = controller_configs["body_parts"]["right"]["type"].lower()
        except Exception:
            self.control_delta = False
            self.controller_type = "osc_pose"
        # reward configuration
        self.reward_scale = reward_scale or 1.0
        self.reward_shaping = reward_shaping

        # whether to use ground-truth object states
        self.use_object_obs = use_object_obs

        # object placement initializer
        self.placement_initializer = placement_initializer
        self.conditional_placement_initializer = None
        self.conditional_placement_on_objects_initializer = None

        # object property initializer

        if object_property_initializers is not None:
            self.object_property_initializers = object_property_initializers
        else:
            self.object_property_initializers = list()

        # Keep track of movable objects in the tasks
        self.objects_dict = {}
        # Kepp track of fixed objects in the tasks
        self.fixtures_dict = {}
        # Keep track of site objects in the tasks. site objects
        # (instances of SiteObject)
        self.object_sites_dict = {}
        # This is a dictionary that stores all the object states
        # interface for all the objects
        self.object_states_dict = {}

        # For those that require visual feature changes, update the state every time step to avoid missing state changes. We keep track of this type of objects to make predicate checking more efficient.
        self.tracking_object_states_change = []

        self.objects = []
        self.fixtures = []

        self.parsed_problem = parsed_problem

        self._assert_problem_name()

        self._arena_type = arena_type
        self._arena_xml = (
            scene_xml
            if os.path.isabs(scene_xml)
            else os.path.join(ASSETS_ROOT, scene_xml)
        )
        self._arena_properties = scene_properties

        # 2D projection settings (set BEFORE super init so that initial observables include these)
        self.return_2d_bboxes = return_2d_bboxes
        self.return_3d_bboxes = return_3d_bboxes
        self.return_segmentation_masks = return_segmentation_masks

        super().__init__(
            robots=robots,
            controller_configs=controller_configs,
            **kwargs,
        )

    def seed(self, seed):
        np.random.seed(seed)

    @staticmethod
    def _average_quaternions(quat_a, quat_b):
        """
        Average two quaternions, aligning signs first to avoid cancellation.
        """
        quat_a = np.asarray(quat_a, dtype=np.float64)
        quat_b = np.asarray(quat_b, dtype=np.float64)
        if np.dot(quat_a, quat_b) < 0.0:
            quat_b = -quat_b
        mean_quat = quat_a + quat_b
        quat_norm = np.linalg.norm(mean_quat)
        if quat_norm < 1e-8:
            return quat_a
        return mean_quat / quat_norm

    def _resolve_recorded_asset_path(self, file_attr):
        """
        Remap stale asset references stored in recorded XML onto the current asset tree.
        """
        if not file_attr:
            return file_attr

        candidates = []
        if os.path.isabs(file_attr):
            candidates.append(file_attr)
        else:
            candidates.extend(
                [
                    file_attr,
                    os.path.join(os.path.dirname(self._arena_xml), file_attr),
                    os.path.join(ASSETS_ROOT, file_attr),
                ]
            )

        path_parts = pathlib.PurePosixPath(file_attr).parts
        asset_indices = [idx for idx, part in enumerate(path_parts) if part == "assets"]
        if asset_indices:
            suffix = path_parts[asset_indices[-1] + 1 :]
            if suffix:
                candidates.append(os.path.join(ASSETS_ROOT, *suffix))

        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if os.path.exists(candidate):
                return candidate

        return file_attr

    def edit_model_xml(self, xml_str):
        """
        Update from superclass to postprocess MimicLabs paths too.

        This function edits the model xml with custom changes, including resolving relative paths,
        applying changes retroactively to existing demonstration files, and other custom scripts.
        Environment subclasses should modify this function to add environment-specific xml editing features.
        Args:
            xml_str (str): Mujoco sim demonstration XML file as string
        Returns:
            str: Edited xml file as string
        """

        # Start with robosuite's XML post-processing (e.g., include handling, path resolution).
        # We then apply MimicLabs-specific adjustments on top.
        xml_str = super().edit_model_xml(xml_str)

        # replace mesh and texture file paths
        root = ET.fromstring(xml_str)
        asset = root.find("asset")
        if asset is None:
            # Unexpected, but keep behavior safe rather than crashing.
            return xml_str
        meshes = asset.findall("mesh")
        textures = asset.findall("texture")
        all_elements = meshes + textures

        for elem in all_elements:
            old_path = elem.get("file")
            if old_path is None:
                continue
            old_path_split = old_path.split("/")

            # maybe replace all paths to mimiclabs assets
            check_lst = [
                loc for loc, val in enumerate(old_path_split) if val == "mimiclabs"
            ]
            if len(check_lst) > 0:
                ind = max(check_lst)  # last occurrence index
                new_path_split = (
                    os.path.split(mesa.__path__[0])[0].split("/")
                    + ["mesa", "sim"]
                    + old_path_split[ind + 1 :]
                )
                new_path = "/".join(new_path_split)
                elem.set("file", new_path)
                continue  # path may contain "robosuite", hence continue

            # BiMESA init states reference robocasa365 objects under an extracted `robocasa_assets/`
            # tree ({objaverse,aigen_objs}/...), which lives at mesa/sim/assets/objects/ in this repo.
            if "robocasa_assets" in old_path_split:
                ind = len(old_path_split) - 1 - old_path_split[::-1].index("robocasa_assets")
                elem.set("file", os.path.join(ASSETS_ROOT, "objects", *old_path_split[ind + 1 :]))
                continue

            # Absolute paths into another checkout's mesa/sim/ (robot meshes, scene assets).
            sim_inds = [
                loc for loc in range(len(old_path_split) - 1)
                if old_path_split[loc] == "mesa" and old_path_split[loc + 1] == "sim"
            ]
            if sim_inds and os.path.isabs(old_path):
                ind = max(sim_inds)
                elem.set("file", os.path.join(mesa.__path__[0], "sim", *old_path_split[ind + 2 :]))
                continue

            # maybe replace all paths to robosuite assets
            check_lst = [
                loc for loc, val in enumerate(old_path_split) if val == "robosuite"
            ]
            if len(check_lst) > 0:
                ind = max(check_lst)  # last occurrence index
                new_path_split = (
                    os.path.split(robosuite.__file__)[0].split("/")
                    + old_path_split[ind + 1 :]
                )
                new_path = "/".join(new_path_split)
                elem.set("file", new_path)
            
        for mesh in meshes:
            mesh_file = mesh.get("file") or ""
            # Match both relative and absolute forms.
            if "/meshes/lab" in mesh_file or mesh_file.startswith("meshes/lab"):
                mesh.set("inertia", "shell")

        return ET.tostring(root, encoding="utf8").decode("utf8")

    def reward(self, action=None):
        """
        Reward function for the task.

        Sparse un-normalized reward:

            - a discrete reward of 1.0 is provided if the task succeeds.

        Args:
            action (np.array): [NOT USED]

        Returns:
            float: reward value
        """
        return float(self._check_success()) * self.reward_scale

    def _assert_problem_name(self):
        """Implement this to make sure the loaded bddl file has the correct problem name specification."""
        assert (
            self.parsed_problem["problem_name"] == self.__class__.__name__.lower()
        ), "Problem name mismatched"

    def _load_fixtures_in_arena(self, mujoco_arena):
        """
        Load fixtures based on the bddl file description. Please override the method in the custom problem file.
        """
        raise NotImplementedError

    def _load_objects_in_arena(self, mujoco_arena):
        """
        Load movable objects based on the bddl file description
        """
        raise NotImplementedError

    def _load_sites_in_arena(self, mujoco_arena):
        """
        Load sites information from each object to keep track of them for predicate checking
        """
        raise NotImplementedError

    def _generate_object_state_wrapper(
        self, skip_object_names=["main_table", "floor", "countertop", "coffee_table"]
    ):
        object_states_dict = {}
        tracking_object_states_changes = []
        for object_name, object_class in self.objects_dict.items():
            if object_name in skip_object_names:
                continue
            joints = None
            if hasattr(self.get_object(object_name), "object_state_joints"):
                joints = self.get_object(object_name).object_state_joints
            joints = None
            if hasattr(self.get_object(object_name), "object_state_joints"):
                joints = self.get_object(object_name).object_state_joints
            if object_class.category_name in STACKABLE_OBJECTS_DICT:
                stack_info = {
                    "xy_threshold": STACKABLE_OBJECTS_DICT[object_class.category_name]["xy_threshold"],
                    "z_threshold": STACKABLE_OBJECTS_DICT[object_class.category_name]["z_threshold"],
                }
            else:
                stack_info = None
            object_states_dict[object_name] = ObjectState(
                self, object_name, joints=joints, stack_info=stack_info
            )
            if (
                object_class.category_name
                in VISUAL_CHANGE_OBJECTS_DICT
            ):
                tracking_object_states_changes.append(object_states_dict[object_name])

        for object_name, object_class in self.fixtures_dict.items():
            if object_name in skip_object_names:
                continue
            object_states_dict[object_name] = ObjectState(
                self, object_name, is_fixture=True
            )
            if (
                object_class.category_name
                in VISUAL_CHANGE_OBJECTS_DICT
            ):
                tracking_object_states_changes.append(object_states_dict[object_name])

        for object_name, object_class in self.object_sites_dict.items():
            if object_name in skip_object_names:
                continue
            object_states_dict[object_name] = SiteObjectState(
                self,
                object_name,
                parent_name=object_class.parent_name,
            )
        self.object_states_dict = object_states_dict
        self.tracking_object_states_change = tracking_object_states_changes

    def _setup_camera(self, mujoco_arena):

        # Built in, fixed camera poses
        mujoco_arena.set_camera(
            camera_name="agentview", pos=[-1.0, 0.0, 1.48], quat=[0.56, 0.43, -0.43, -0.56]
        )
        mujoco_arena.set_camera(
            camera_name="behindview", 
            pos=[1.31432386, 0.0, 1.62287812], 
            quat=[0.62330046, 0.33391096, 0.33391096, 0.62330046]
        )
        mujoco_arena.set_camera(
            camera_name="galleryview",
            pos=[2.844547668904445, 2.1279684793440667, 3.128616846013882],
            quat=[
                0.42261379957199097,
                0.23374411463737488,
                0.41646939516067505,
                0.7702690958976746,
            ],
        )
        mujoco_arena.set_camera(
            camera_name="paperview",
            pos=[2.1, 0.535, 2.075],
            quat=[0.513, 0.353, 0.443, 0.645],
        )

        for camera_name, camera_parameters in self.parsed_problem["camera"].items():
            camera_pos, camera_quat = env_utils.sample_camera_pose(
                table_offset=self.workspace_offset,
                **camera_parameters,
            )
            mujoco_arena.set_camera(
                camera_name=camera_name,
                pos=camera_pos,
                quat=camera_quat,
            )

    def _load_model(self):
        """
        Loads an xml model, puts it in self.model
        """
        super()._load_model()
        # Adjust base pose accordingly

        if "styles" in self.parsed_problem:
            styles = {f"{key}_style": value for key, value in self.parsed_problem["styles"].items()}
        else:
            styles = {}
        self._arena_properties.update(styles)

        if self._arena_type == "table":
            num_robots = len(self.robots)
            side_by_side_spacing_m = 0.6

            for robot_idx, robot in enumerate(self.robots):
                xpos = np.array(
                    robot.robot_model.base_xpos_offset["table"](self.table_full_size[0]),
                    dtype=np.float64,
                )
                if num_robots > 1:
                    # Spread robot bases along Y so multiple normal-mounted arms are side-by-side.
                    y_shift = (robot_idx - (num_robots - 1) / 2.0) * side_by_side_spacing_m
                    xpos[1] += y_shift

                robot.robot_model.set_base_xpos(tuple(xpos))
                ori = robot.robot_model.base_ori_offset["table"](
                    self.table_full_size[0]
                )
                robot.robot_model.set_base_ori(ori)
            mujoco_arena = MimicLabsTableArena(
                table_full_size=self.table_full_size,
                table_offset=self.workspace_offset,
                table_friction=(0.6, 0.005, 0.0001),
                xml=self._arena_xml,
                **self._arena_properties,
            )
        else:
            raise NotImplementedError

        # Arena always gets set to zero origin
        mujoco_arena.set_origin([0, 0, 0])

        self._setup_camera(mujoco_arena)

        # self._load_custom_material() # NOTE(VS) removed, unused

        self._load_fixtures_in_arena(mujoco_arena)

        self._load_objects_in_arena(mujoco_arena)

        self._load_sites_in_arena(mujoco_arena)

        self._generate_object_state_wrapper()

        self._setup_placement_initializer(mujoco_arena)

        self.objects = list(self.objects_dict.values())
        self.fixtures = list(self.fixtures_dict.values())

        self._randomize_lighting_dir(mujoco_arena)

        # task includes arena, robot, and objects of interest
        self.model = ManipulationTask(
            mujoco_arena=mujoco_arena,
            mujoco_robots=[robot.robot_model for robot in self.robots],
            mujoco_objects=self.objects + self.fixtures,
        )

        for fixture in self.fixtures:
            self.model.merge_assets(fixture)

    def _randomize_lighting_dir(self, mujoco_arena):
        lighting_params = self.parsed_problem["lighting"]
        light = mujoco_arena.worldbody.find("./light")
        if light is not None:
            # Setting shadow
            light.attrib["castshadow"] = str(
                lighting_params.get("shadow", False)
            ).lower()  # default: no shadow

            # Setting lighting direction
            ranges_r_theta_phi = lighting_params.get(
                "source", [[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]]
            )  # default: top-down light source
            range_choice = np.random.choice(range(len(ranges_r_theta_phi)))
            range_r_theta_phi = ranges_r_theta_phi[range_choice]
            range_r = [range_r_theta_phi[0], range_r_theta_phi[3]]
            range_theta = [range_r_theta_phi[1], range_r_theta_phi[4]]
            range_phi = [range_r_theta_phi[2], range_r_theta_phi[5]]
            sample_r = (range_r[1] - range_r[0]) * np.random.random_sample() + range_r[
                0
            ]
            sample_theta = (
                range_theta[1] - range_theta[0]
            ) * np.random.random_sample() + range_theta[0]
            sample_phi = (
                range_phi[1] - range_phi[0]
            ) * np.random.random_sample() + range_phi[0]
            pos, _ = env_utils.convert_spherical_to_pos_quat(sample_r, sample_theta, sample_phi)
            light.attrib["dir"] = f"{-pos[0]} {-pos[1]} {-pos[2]}"

    def _setup_placement_initializer(self, mujoco_arena):
        self.placement_initializer = SequentialCompositeSampler(name="ObjectSampler")
        self.conditional_placement_initializer = SiteSequentialCompositeSampler(
            name="ConditionalSiteSampler"
        )
        self.conditional_placement_on_objects_initializer = SequentialCompositeSampler(
            name="ConditionalObjectSampler"
        )
        self._add_placement_initializer()

    def _setup_references(self):
        """
        Sets up references to important components. A reference is typically an
        index or a list of indices that point to the corresponding elements
        in a flatten array, which is how MuJoCo stores physical simulation data.
        """
        super()._setup_references()

        # Additional object references from this env
        self.obj_body_id = dict()

        for object_name, object_body in self.objects_dict.items():
            self.obj_body_id[object_name] = self.sim.model.body_name2id(
                object_body.root_body
            )

        for fixture_name, fixture_body in self.fixtures_dict.items():
            self.obj_body_id[fixture_name] = self.sim.model.body_name2id(
                fixture_body.root_body
            )

    def _setup_observables(self):
        """
        Sets up observables to be used for this environment. Creates object-based observables if enabled

        Returns:
            OrderedDict: Dictionary mapping observable names to its corresponding Observable object
        """
        observables = super()._setup_observables()

        observables["robot0_joint_pos"]._active = True

        # low-level object information
        if self.use_object_obs:
            # Get robot prefix and define observables modality
            pf = self.robots[0].robot_model.naming_prefix
            sensors = []
            names = [s.__name__ for s in sensors]

            # Also append handle qpos if we're using a locked drawer version with rotatable handle

            # Create observables
            for name, s in zip(names, sensors):
                observables[name] = Observable(
                    name=name,
                    sensor=s,
                    sampling_rate=self.control_freq,
                )

        pf = self.robots[0].robot_model.naming_prefix

        # ------------------------------------------------------------------
        # Robot / gripper geometry observables
        # ------------------------------------------------------------------

        for robot in self.robots:
            rpf = robot.robot_model.naming_prefix
            jaw_sensor = sensor_utils.create_gripper_jaw_width_sensor(self.sim, pf=rpf)
            sensors.append(jaw_sensor)
            names.append(f"{rpf}gripper_jaw_width")

        @sensor(modality="object")
        def world_pose_in_gripper(obs_cache):
            return (
                T.pose_inv(
                    T.pose2mat((obs_cache[f"{pf}eef_pos"], obs_cache[f"{pf}eef_quat"]))
                )
                if f"{pf}eef_pos" in obs_cache and f"{pf}eef_quat" in obs_cache
                else np.eye(4)
            )

        sensors.append(world_pose_in_gripper)
        names.append("world_pose_in_gripper")

        for i, obj in enumerate(self.objects):
            obj_sensors, obj_sensor_names = sensor_utils.create_obj_sensors(
                sim=self.sim,
                obj_name=obj.name,
                obj_body_id=self.obj_body_id[obj.name],
                modality="object",
                return_2d_bboxes=self.return_2d_bboxes,
                return_3d_bboxes=self.return_3d_bboxes,
                return_segmentation_masks=self.return_segmentation_masks,
                camera_names=self.camera_names,
                camera_heights=self.camera_heights,
                camera_widths=self.camera_widths,
                robot_naming_prefix=pf,
            )

            sensors += obj_sensors
            names += obj_sensor_names

        # breakpoint()
        for name, s in zip(names, sensors):
            if name == "world_pose_in_gripper":
                observables[name] = Observable(
                    name=name,
                    sensor=s,
                    sampling_rate=self.control_freq,
                    enabled=True,
                    active=False,
                )
            else:
                observables[name] = Observable(
                    name=name, sensor=s, sampling_rate=self.control_freq
                )

        return observables

    def _add_placement_initializer(self):

        mapping_inv = {}
        for k, values in self.parsed_problem["fixtures"].items():
            for v in values:
                mapping_inv[v] = k
        for k, values in self.parsed_problem["objects"].items():
            for v in values:
                mapping_inv[v] = k

        regions = self.parsed_problem["regions"]
        initial_state = self.parsed_problem["initial_state"]
        problem_name = self.parsed_problem["problem_name"]

        conditioned_initial_place_state_on_sites = []
        conditioned_initial_place_state_on_objects = []
        conditioned_initial_place_state_in_objects = []

        placement_initializers = []

        for state in initial_state:
            if state[0] == "on" and state[2] in self.objects_dict:
                conditioned_initial_place_state_on_objects.append(state)
                continue

            # (Yifeng) Given that an object needs to have a certain "containing" region in order to hold the relation "In", we assume that users need to specify the containing region of the object already.
            if state[0] == "in" and state[2] in regions:
                conditioned_initial_place_state_in_objects.append(state)
                continue
            # Check if the predicate is in the form of On(object, region)
            if state[0] == "on" and state[2] in regions:
                object_name = state[1]
                region_name = state[2]
                target_name = regions[region_name]["target"]
                x_ranges, y_ranges = env_utils.rectangle2xyrange(regions[region_name]["ranges"])
                yaw_rotation = regions[region_name]["yaw_rotation"]
                if (
                    target_name in self.objects_dict
                    or target_name in self.fixtures_dict
                ):
                    conditioned_initial_place_state_on_sites.append(state)
                    continue
                if self.is_fixture(object_name):
                    # This is to place environment fixtures.
                    fixture_object = self.fixtures_dict[object_name]
                    if fixture_object.rotation is not None:
                        rotation_kwargs = dict(
                            rotation=fixture_object.rotation,
                            rotation_axis=fixture_object.rotation_axis,
                        )
                    else:
                        assert yaw_rotation is not None
                        rotation_kwargs = dict(
                            rotation=yaw_rotation,
                            rotation_axis=fixture_object.rotation_axis,
                        )
                    fixture_sampler = get_region_samplers(
                        problem_name, mapping_inv[target_name]
                    )(
                        f"{object_name}_sampler",
                        mujoco_objects=fixture_object,
                        x_ranges=x_ranges,
                        y_ranges=y_ranges,
                        z_offset=self.z_offset,
                        ensure_object_boundary_in_range=False,
                        ensure_valid_placement=True,
                        reference_pos=self.workspace_offset,
                        **rotation_kwargs,
                    )
                    placement_initializers.append((fixture_object, fixture_sampler))
                else:
                    object_instance = self.objects_dict[object_name]

                    # This is to place movable objects.
                    if object_instance.rotation is not None:
                        # yaw_rotation for objects in object class overrides spec in bddl
                        rotation_kwargs = dict(
                            rotation=object_instance.rotation,
                            rotation_axis=object_instance.rotation_axis,
                        )
                    else:
                        assert yaw_rotation is not None
                        rotation_kwargs = dict(
                            rotation=yaw_rotation,
                            rotation_axis=object_instance.rotation_axis,
                        )
                    region_sampler = get_region_samplers(
                        problem_name, mapping_inv[target_name]
                    )(
                        object_name,
                        object_instance,
                        x_ranges=x_ranges,
                        y_ranges=y_ranges,
                        reference_pos=self.workspace_offset,
                        **rotation_kwargs,
                    )
                    placement_initializers.append((object_instance,region_sampler))
            if state[0] in ["open", "close"]:
                # If "open" is implemented, we assume "close" is also implemented
                if state[1] in self.object_states_dict and hasattr(
                    self.object_states_dict[state[1]], "set_joint"
                ):
                    obj = self.get_object(state[1])
                    if state[0] == "open":
                        joint_ranges = obj.object_properties["articulation"][
                            "default_open_ranges"
                        ]
                    else:
                        joint_ranges = obj.object_properties["articulation"][
                            "default_close_ranges"
                        ]

                    property_initializer = OpenCloseSampler(
                        name=obj.name,
                        state_type=state[0],
                        joint_ranges=joint_ranges,
                    )
                    self.object_property_initializers.append(property_initializer)
            elif state[0] in ["turnon", "turnoff"]:
                # If "turnon" is implemented, we assume "turnoff" is also implemented.
                if state[1] in self.object_states_dict and hasattr(
                    self.object_states_dict[state[1]], "set_joint"
                ):
                    obj = self.get_object(state[1])
                    if state[0] == "turnon":
                        joint_ranges = obj.object_properties["articulation"][
                            "default_turnon_ranges"
                        ]
                    else:
                        joint_ranges = obj.object_properties["articulation"][
                            "default_turnoff_ranges"
                        ]

                    property_initializer = TurnOnOffSampler(
                        name=obj.name,
                        state_type=state[0],
                        joint_ranges=joint_ranges,
                    )
                    self.object_property_initializers.append(property_initializer)

        # Place objects with larger horizontal offsets first. This makes it less likely to be unable to place the last object
        placement_initializers = sorted(placement_initializers, key=lambda x: np.linalg.norm(x[0].horizontal_offset), reverse=True)
        for placement_initializer in placement_initializers:
            self.placement_initializer.append_sampler(placement_initializer[1])

        # Place objects that are on sites
        for state in conditioned_initial_place_state_on_sites:
            object_name = state[1]
            region_name = state[2]
            target_name = regions[region_name]["target"]
            site_xy_size = self.object_sites_dict[region_name].size[:2]
            sampler = SiteRegionRandomSampler(
                f"{object_name}_sampler",
                mujoco_objects=self.objects_dict[object_name],
                x_ranges=[[-site_xy_size[0] / 2, site_xy_size[0] / 2]],
                y_ranges=[[-site_xy_size[1] / 2, site_xy_size[1] / 2]],
                ensure_object_boundary_in_range=True,
                ensure_valid_placement=True,
                rotation=self.objects_dict[object_name].rotation,
                rotation_axis=self.objects_dict[object_name].rotation_axis,
            )
            self.conditional_placement_initializer.append_sampler(
                sampler, {"reference": target_name, "site_name": region_name}
            )
        # Place objects that are on other objects
        for state in conditioned_initial_place_state_on_objects:
            object_name = state[1]
            other_object_name = state[2]
            sampler = ObjectBasedSampler(
                f"{object_name}_sampler",
                mujoco_objects=self.objects_dict[object_name],
                x_ranges=[[0.0, 0.0]],
                y_ranges=[[0.0, 0.0]],
                ensure_object_boundary_in_range=False,
                ensure_valid_placement=False,
                rotation=self.objects_dict[object_name].rotation,
                rotation_axis=self.objects_dict[object_name].rotation_axis,
            )
            self.conditional_placement_on_objects_initializer.append_sampler(
                sampler, {"reference": other_object_name}
            )
        # Place objects inside some containing regions
        for state in conditioned_initial_place_state_in_objects:
            object_name = state[1]
            region_name = state[2]
            target_name = regions[region_name]["target"]

            site_xy_size = self.object_sites_dict[region_name].size[:2]
            sampler = InSiteRegionRandomSampler(
                f"{object_name}_sampler",
                mujoco_objects=self.objects_dict[object_name],
                ensure_object_boundary_in_range=True,
                ensure_valid_placement=True,
                rotation=self.objects_dict[object_name].rotation,
                rotation_axis=self.objects_dict[object_name].rotation_axis,
            )
            self.conditional_placement_initializer.append_sampler(
                sampler, {"reference": target_name, "site_name": region_name}
            )

    def _reset_internal(self):
        """
        Resets simulation internal configurations.
        """
        super()._reset_internal()

        # Reset all object positions using initializer sampler if we're not directly loading from an xml
        if not self.deterministic_reset and not self.deterministic_reset_override:

            # Sample from the placement initializer for all objects
            for object_property_initializer in self.object_property_initializers:
                if isinstance(object_property_initializer, OpenCloseSampler):
                    joint_pos = object_property_initializer.sample()
                    self.object_states_dict[object_property_initializer.name].set_joint(
                        joint_pos
                    )
                elif isinstance(object_property_initializer, TurnOnOffSampler):
                    joint_pos = object_property_initializer.sample()
                    self.object_states_dict[object_property_initializer.name].set_joint(
                        joint_pos
                    )
                else:
                    print("Warning!!! This sampler doesn't seem to be used")
            # robosuite didn't provide api for this stepping. we manually do this stepping to increase the speed of resetting simulation.
            mujoco.mj_step1(self.sim.model._model, self.sim.data._data)

            object_placements = None
            for _ in range(1000):
                try:
                    object_placements = self.placement_initializer.sample()
                    object_placements = self.conditional_placement_initializer.sample(
                        self.sim, object_placements
                    )
                    object_placements = (
                        self.conditional_placement_on_objects_initializer.sample(
                            object_placements
                        )
                    )
                    break
                except RandomizationError:
                    continue
            if not object_placements:
                raise RandomizationError("Cannot place all objects ):")

            for obj_pos, obj_quat, obj in object_placements.values():
                if obj.name not in list(self.fixtures_dict.keys()):
                    # This is for movable object resetting (setting free joint)
                    self.sim.data.set_joint_qpos(
                        obj.joints[-1],
                        np.concatenate([np.array(obj_pos), np.array(obj_quat)]),
                    )
                else:
                    # This is for fixture resetting
                    body_id = self.sim.model.body_name2id(obj.root_body)
                    self.sim.model.body_pos[body_id] = obj_pos
                    self.sim.model.body_quat[body_id] = obj_quat

    def get_noop_action(self):
        if self.controller_type == "osc_pose":
            if self.control_delta:
                return np.concatenate([np.zeros(7) for _ in self.robots])
            else:
                noop_parts = []
                for robot in self.robots:
                    action_abs_pos = robot.composite_controller.part_controllers['right'].ref_pos
                    action_abs_ori = robot.composite_controller.part_controllers['right'].ref_ori_mat
                    action_rot_quat = t3d.quaternions.mat2quat(action_abs_ori)
                    axis, theta = t3d.quaternions.quat2axangle(action_rot_quat)
                    action_abs_ori = theta * axis
                    noop_parts.append(np.concatenate([action_abs_pos, action_abs_ori, [-1]]))
                return np.concatenate(noop_parts)
        elif self.controller_type == "joint_position":
            if self.control_delta:
                return np.concatenate([np.concatenate([np.zeros(7), [-1]]) for _ in self.robots])
            else:
                noop_parts = []
                for robot in self.robots:
                    current_joint_pos = self.sim.data.qpos[robot.joint_indexes]
                    noop_parts.append(np.concatenate([current_joint_pos, [-1]]))
                return np.concatenate(noop_parts)
        else:
            raise ValueError(f"Invalid controller type: {self.controller_type}")

    def stable_reset(self):
        valid = False
        while not valid:
            valid = True
            super().reset()

            noop_action = self.get_noop_action()

            # Perform several noop actions. This ensures two things:
            # 1. The objects have settled to a stable state
            # 2. We check the object velocities to ensure nothing spawned in a collsion state -> unstable

            for _ in range(5):

                for _ in range(self.init_noops):
                    for obj in self.objects_dict.values():
                        root_body = obj.root_body
                        linear_vel = self.sim.data.get_body_xvelp(root_body)
                        if np.linalg.norm(linear_vel) > 2:
                            valid = False
                            break

                    if not valid:
                        break
                    self.step(noop_action)

                max_qvel = np.max(np.abs(self.sim.data.qvel))
                max_cvel = np.max(np.abs(self.sim.data.cvel))
                if max(max_qvel, max_cvel) < 1.0:
                    break
            
            if max(max_qvel, max_cvel) > 1.0:
                valid = False

        return self._get_observations(force_update=True)

    def reset_to(self, state):
        """
        Reset to a specific simulator state.

        Args:
            state (dict): A dictionary containing the state to reset to.
                Contains keys "states" and "model".
        """
        if "model" in state:
            # Edit model xml and reset
            xml = self.edit_model_xml(state["model"])
            self.reset_from_xml_string(xml)

        if "states" in state:
            # Reset to state
            self.sim.reset()
            self.sim.set_state_from_flattened(state["states"])
            self.sim.forward()

        self._setup_camera(self.model.mujoco_arena)

        return self._get_observations(force_update=True)

    def reset_from_xml_string(self, xml_string):
        """
        Resets object textures to ones currently in the model before
        calling reset_from_xml_string()
        """
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_string)
        asset = root.find("asset")

        # Resetting table texture to default
        tex = asset.find("./texture[@name='tex-table']")
        if tex is not None:
            orig_scene = ET.parse(self._arena_xml)
            orig_tex_file = orig_scene.find(
                "./asset/texture[@name='tex-table']"
            ).attrib["file"]
            orig_tex_file = os.path.join(
                os.path.dirname(self._arena_xml), orig_tex_file
            )
            tex.attrib["file"] = orig_tex_file

        # Resetting all object textures to default
        for obj_name, obj in self.objects_dict.items():
            try:
                objtex = obj.asset.find("./texture")
                texname = objtex.attrib["name"]
                asset.find(f"./texture[@name='{texname}']").attrib["file"] = objtex.attrib["file"]
            except Exception:
                pass

        # Recorded XML may contain stale absolute asset paths from another machine.
        # Repair them before Mujoco loads the model so scene textures stay intact.
        for tex in asset.findall("texture"):
            file_attr = tex.get("file")
            repaired_file = self._resolve_recorded_asset_path(file_attr)
            if repaired_file != file_attr and os.path.exists(repaired_file):
                tex.set("file", repaired_file)

        modified_xml_string = ET.tostring(root, encoding="utf8").decode("utf8")

        try:
            super().reset_from_xml_string(modified_xml_string)
        except ValueError:
            # Some older XML strings reference texture files that no longer exist.
            # Repair by remapping into the current assets tree and only fall back
            # to the placeholder texture if no valid asset exists locally.
            placeholder_texture = os.path.join(ASSETS_ROOT, "textures/missing.png")

            repaired_root = ET.fromstring(modified_xml_string)
            repaired_asset = repaired_root.find("asset")
            if repaired_asset is not None:
                for tex in repaired_asset.findall("texture"):
                    file_attr = tex.get("file")
                    if not file_attr:
                        continue
                    repaired_file = self._resolve_recorded_asset_path(file_attr)
                    if os.path.exists(repaired_file):
                        tex.set("file", repaired_file)
                        continue
                    tex.set("file", placeholder_texture)

            repaired_xml_string = ET.tostring(repaired_root, encoding="utf8").decode("utf8")
            super().reset_from_xml_string(repaired_xml_string)

    def get_state(self):
        """
        Get current environment simulator state as a dictionary. Should be compatible with @reset_to.
        """
        xml = self.sim.model.get_xml() # model xml file
        state = np.array(self.sim.get_state().flatten()) # simulator state
        return dict(model=xml, states=state)

    def is_success(self):
        """
        Check if the task condition(s) is reached. Should return a dictionary
        { str: bool } with at least a "task" key for the overall task success,
        and additional optional keys corresponding to other task criteria.
        """
        succ = self._check_success()
        if isinstance(succ, dict):
            assert "task" in succ
            return succ
        return { "task" : succ }

    def _check_success(self):
        """
        This needs to match with the goal description from the bddl file

        Returns:
            bool: True if drawer has been opened
        """
        return False

    def _get_subtask_progress(self):
        return set()

    def _get_distractor_task_completion(self):
        return set()

    def get_observation(self):
        return self._get_observations(force_update=True)

    def step(self, action):
        if self.action_dim == 4 and len(action) > 4:
            # Convert OSC_POSITION action
            action = np.array(action)
            action = np.concatenate((action[:3], action[-1:]), axis=-1)

        obs, reward, done, info = super().step(action)
        done = self._check_success()
        info['subtask_complete'] = self._get_subtask_progress()
        info['distractor_complete'] = self._get_distractor_task_completion()
        info["success"] = done

        return obs, reward, done, info

    def _post_action(self, action):
        reward, done, info = super()._post_action(action)

        self._post_process()

        return reward, done, info

    def _post_process(self):
        # Update some object states, such as light switching etc.
        for object_state in self.tracking_object_states_change:
            object_state.update_state()

    def is_fixture(self, object_name):
        """
        Check if an object is defined as a fixture in the task

        Args:
            object_name (str): The name string of the object in query
        """
        return object_name in list(self.fixtures_dict.keys())

    def get_object(self, object_name):
        for query_dict in [
            self.fixtures_dict,
            self.objects_dict,
            self.object_sites_dict,
        ]:
            if object_name in query_dict:
                return query_dict[object_name]

    def get_object_natural_name(self, object_name):
        return self.objects_dict[object_name].name
