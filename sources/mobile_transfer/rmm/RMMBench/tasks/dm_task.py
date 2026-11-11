from RMMBench.utils.paths import PROJECT_ROOT
import os
import numpy as np
import yaml
import json
import random
import itertools
import logging
import re
import copy
from functools import partial
from dm_control import composer, mjcf
from RMMBench.utils.register import register
from RMMBench.tasks.condition import ConditionSet, OrCondition
from RMMBench.utils.utils import compute_camera_positions_and_bounds, CAMERA_NAME_MAP,grid_sample, distance,quaternion_to_matrix,quaternion_multiply,quaternion_conjugate

from RMMBench.tasks.components.scene import Scene
from RMMBench.configs.constant import name2class_xml
from RMMBench.tasks.components.entity import Entity
from RMMBench.utils.skill_lib import SkillLib
from RMMBench.utils.gpt_utils import query_gpt4_v
# from test_dm_control import physics

with open(os.path.join(PROJECT_ROOT, "configs/camera_config.json"), "r") as f:
    CAMERA_VIEWS = json.load(f)

ROBOCASA_SCENE_NAMES = [
    "ONE_WALL_SMALL",
    "ONE_WALL_LARGE",
    "L_SHAPED_SMALL",
    "L_SHAPED_LARGE",
    "GALLEY",
    "U_SHAPED_SMALL",
    "U_SHAPED_LARGE",
    "G_SHAPED_SMALL",
    "G_SHAPED_LARGE",
    "WRAPAROUND"
]

NUM_SUBSTEPS = 100

class LM4ManipBaseTask(composer.Task):
    """
    Base class for task to carry out, derived from dm_control composer.Task.
    The key attribute to manage the task is 'config_manager' in build_from_config method. 
    For evaluation, 'episode_config' will be passed to generate deterministic configurations.
    """
    def __init__(self, 
                 task_name, 
                 robot,
                 eval=False,
                 random_init=True,
                 use_llm=False,
                 episode_config=None,
                 random_params=None,
                 xml_file="base/default.xml",
                 run_mode="efficient",
                 **kwargs):
        """
        Params:
            robot: robot name to use in the task
            eval: whether load unseen objects to evaluate the generalization ability
            random_init: whether to compute grid sampling positions when initializing the entities
            use_llm: whether to use LLMs to generate instructions
            episode_config: deterministic configuration for task building
            xml_file: the file path of root xml for the task
            run_mode: the running mode of the environment, choose 'efficient' for data collection and 'eval' for evaluation
        """
        # Added in __init__ (after around line 79)
        self.test_robot_info=0
        self.robocasa_scene=None
        self.robot_end_pos = None
        self._attached_entities = {}  # Initialize the dict of attached entities
        self.component_name_list=[]
        self.robot_params = None
        self.navigation_condition = None
        self.skill_end = False
        self.task_name = task_name
        self.config_manager = register.load_config_manager(task_name)(task_name)  # BenchTaskConfigManager instance
        self.asset_path = os.path.join(PROJECT_ROOT, "assets") 
        self.use_llm = use_llm       
        self._arena = composer.Arena(xml_path=os.path.join(self.asset_path, xml_file))
        self._robot = robot
        self.attach_entity(robot)
        self._task_observables = {}
        config = self.config_manager.config
        if random_params is not None:
            if "shadow" in random_params:
                config["task"]["scene"]["shadow"] = random_params["shadow"]


        # print("LM4,config:", config)
        self.control_timestep = self.physics_timestep * NUM_SUBSTEPS
        self.entities = dict()
        self.distractors = dict()
        self.random_init = random_init
        self.run_mode = run_mode
        if config is not None:
            self.random_ignored_entities = config["task"].get("random_ignored_entities", ["table"])
            self.ngrid = config["task"].get("ngrid", None)
            self.workspace = config["task"].get("workspace", [-0.3, 0.3, -0.2, 0.3, 0.75, 1.5]) # minx, maxx, miny, maxy, minz, maxz
        else:
            self.random_ignored_entities = ["table"]
            self.ngrid = None
            self.workspace = [-0.3, 0.3, -0.2, 0.3, 0.75, 1.5]
        self.build_from_config(eval, deterministic_config=episode_config)
        self.reset_camera_views()







    # Modified after_substep (originally line 224)
    def after_substep(self, physics, random_state):
        pass
    #default_index=2
    def reset_camera_views(self, index=2):
        # check_keys = set(["left" ,"right" ,"forward", "wrist","head","opposite"])#index:0,1,2,3
        check_keys = set(["left" ,"right" ,"forward", "wrist","opposite","head"])#index:0,1,2,3

        # check_index={
        #     "right": 0,
        #     "left" :1,
        #     "forward" :2,
        #     "wrist" :3,
        #     "head":4,
        #     "opposite":5
        # }

        check_index={
            "right": 0,
            "left" :1,
            "forward" :2,
            "wrist" :3,
            "opposite":4,
            "head": 5,
        }
        #-------
        cam_head = self.robot.cam_head
        # print("joint:",cam_head)
        # cam_head.pos = np.array([0-0.35,0,1.75])# head view for navigation
        # print("1",cam_head.pos)
        cam_head.pos = np.array([0.27,0,1.7])# head view for manipulation

        #______

        if self.camera_task_name in CAMERA_VIEWS:
            task_camera_keys = set(CAMERA_VIEWS[self.camera_task_name].keys())
            cameras = self._arena.mjcf_model.find_all("camera")
            if task_camera_keys & check_keys:
                # print("task_camera_keys:",task_camera_keys)

                common_keys = task_camera_keys & check_keys
                for key in common_keys:
                    # print("key:",key)
                    target_camera = cameras[check_index[key]]
                    for attr, value in CAMERA_VIEWS[self.camera_task_name][key].items():
                        # print("attr:",attr)
                        # print("value:",value)

                        #attr: pos
                        #value: 2.4 -6 3

                        setattr(target_camera, attr, value)

            else:
                # cameras = self._arena.mjcf_model.find_all("camera")
                target_camera = cameras[index]
                for attr, value in CAMERA_VIEWS[self.camera_task_name].items():
                    setattr(target_camera, attr, value)

        # Default mechanism: if left/right are not configured, compute from robot pose
        self._reset_left_right_cameras_from_robot_pose()

    def _reset_left_right_cameras_from_robot_pose(self):
        """
        Default camera position reset mechanism.
        If left/right cameras are not explicitly configured in CAMERA_VIEWS,
        compute their positions and orientations based on robot base pose.
        """
        from RMMBench.utils.camera_utils import rotation_6d_to_matrix
        from RMMBench.utils.utils import euler_to_rotation_matrix

        # Get robot base pose
        robot_info = self.robot.robot_init_info
        robot_pos = robot_info["position"]
        robot_euler = robot_info["euler"]

        left_pos, right_pos, _, _ = compute_camera_positions_and_bounds(
            robot_pos, robot_euler
        )

        cameras = self._arena.mjcf_model.find_all("camera")

        # Base xyaxes for robot facing +Y (yaw=1.57)
        right_xyaxes_base = np.array([0.733, 0.681, 0.000, -0.134, 0.144, 0.981])
        left_xyaxes_base = np.array([0.733, -0.681, 0.000, 0.134, 0.144, 0.981])

        # Compute delta rotation from base yaw=1.57 to current yaw
        delta_yaw = robot_euler[2] - 1.57
        R_delta = euler_to_rotation_matrix([0, 0, delta_yaw], order='xyz')

        # Helper to rotate xyaxes
        def rotate_xyaxes(xyaxes_base, R_delta):
            R_base = rotation_6d_to_matrix(xyaxes_base)
            R_new = R_delta @ R_base
            return " ".join([str(v) for v in np.concatenate([R_new[:, 0], R_new[:, 1]])])

        # Update left camera if not configured in CAMERA_VIEWS
        if "left" not in CAMERA_VIEWS.get(self.camera_task_name, {}):
            left_cam = cameras[CAMERA_NAME_MAP["left"]]
            left_cam.pos = " ".join([str(v) for v in left_pos])
            left_cam.xyaxes = rotate_xyaxes(left_xyaxes_base, R_delta)

        # Update right camera if not configured in CAMERA_VIEWS
        if "right" not in CAMERA_VIEWS.get(self.camera_task_name, {}):
            right_cam = cameras[CAMERA_NAME_MAP["right"]]
            right_cam.pos = " ".join([str(v) for v in right_pos])
            right_cam.xyaxes = rotate_xyaxes(right_xyaxes_base, R_delta)

    def step(self, action):
        pass
    
    @property
    def root_entity(self):
        return self._arena
    
    @property
    def task_observables(self):
        return self._task_observables
    
    @property
    def robot(self):
        return self._robot

    @property
    def get_robocasa_scene_class(self):
        return self.robocasa_scene

    @property
    def name(self):
        return self.task_name
    
    @property
    def target_entity(self): # especially for primitive tasks
        return self.config_manager.target_entity

    @property
    def all_entities(self):
        return self.config_manager.all_entities

    @property
    def target_entities(self): 
        """
        expoecially for composite tasks
        """
        return self.config_manager.target_entities
    
    @property
    def target_container(self):
        return self.config_manager.target_container
    
    @property
    def init_container(self):
        return self.config_manager.init_container


    
    def initialize_episode(self, physics, random_state):
        if self.run_mode == "eval":
            self.reset_intention_distance()
            self.reset_task_progress()
        # grid sampling
        if self.ngrid is not None and self.random_init:
            entities_to_random = [key for key in self.entities.keys() if key not in self.random_ignored_entities]
            sampled_points = grid_sample(self.workspace, self.ngrid, len(entities_to_random), farthest_sample=True)
            for key, point in zip(entities_to_random, sampled_points):
                entity = self.entities[key]
                entity.init_pos[:2] = point
        # self.robot.init_ee_pos, self.robot.init_ee_quat = list(self.robot.get_end_effector_pos(physics)), self.robot.get_end_effector_quat(physics)
        self.robot.init_ee_pos = np.array(self.robot.get_end_effector_pos(physics)).copy()
        self.robot.init_ee_quat = np.array(self.robot.get_end_effector_quat(physics)).copy()
        # print("self.robot.init_ee_pos:",self.robot.init_ee_pos)
        # print("self.robot.init_ee_quat",self.robot.init_ee_quat)
        self.init_robot_info = self.robot.get_link_base_info(physics)
        self.test_robot_info = self.init_robot_info
        return super().initialize_episode(physics, random_state)


    # def settle_object(self, key,entity, physics):
    #     # 1. First lift the object slightly higher (to ensure it is not embedded)
    #     if key.rsplit("_", 1)[0] == "ONE_WALL_LARGE":
    #         return
    #     pos = entity.get_xpos(physics).copy()
    #     # pos[2] += 0.05
    #     # entity.set_pose(physics, pos)
    #
    #     # 2. Step it downward in small increments until contact is detected
    #     for _ in range(100):  # descend at most 5cm
    #         pos[2] -= 0.001  # move down 1mm each step
    #         entity.set_pose(physics, pos)
    #         physics.forward()  # update geometry only, no dynamics
    #
    #         # Check whether the object collides with anything
    #         if any(c.dist <= 0 for c in physics.data.contact):
    #             # Move back up 0.8mm to guarantee no embedding
    #             pos[2] += 0.0008
    #             entity.set_pose(physics, pos)
    #             physics.forward()
    #             break

    def get_reward(self, physics):
        return 0
    
    def before_step(self, physics, action, random_state):
        data = physics.data
        # print("before_step_action:",action)
        data.ctrl[:] = action

        pass
    
    def before_substep(self, physics, action, random_state):
        pass
    
    def after_step(self, physics, random_state):
        physics.data.ctrl[:] = 0
        if self.run_mode == "eval":
            self.update_intention_distance(physics)
            self.update_task_progress(physics)
    
    # def after_substep(self, physics, random_state):
    #     pass
    
    def add_free_entity(self, entity):
        frame = self._arena.add_free_entity(entity)
        self.entities[entity.mjcf_model.model] = entity
    
    def delete_entity(self, entity):
        entity.detach()
        self.entities.pop(entity.mjcf_model.model)

    def get_clean_entity_names(self,name_list):
        clean_names = set()  # use a set to deduplicate automatically

        for full_name in name_list:
            match = re.match(r'^[a-zA-Z_]+(?=[0-9]|$)', full_name)

            if match:
                # Strip any trailing underscore residue
                clean_name = match.group().strip('_')
                clean_names.add(clean_name)
            else:
                # If the regex does not match (e.g. digits only), split by underscore and take the first segment
                clean_name = full_name.split('_')[0]
                # Filter out the pure-digit case
                if not clean_name.isdigit():
                    clean_names.add(clean_name)

        return list(clean_names)

    def build_from_config(self, eval=False, **kwargs):
        """
        Load configurations from the config file and build the task.
        Configuration includes:
            - options and parameters of mujoco physics engine
            - load scene by configuration
            - entity configuration
        """
        if eval: config = self.config_manager.get_unseen_task_config()

        else: config = self.config_manager.get_seen_task_config()
        # print("config_select_carrot:",config)
        self.camera_task_name = config["task"].get("camera_task_name", None)

        if isinstance(config, dict):
            self.config = config
        elif isinstance(config, str):
            with open(config, "r") as f:
                self.config = yaml.safe_load(f)
        # override the config with deterministic config
        deterministic_config = kwargs.get("deterministic_config", None)
        # print("self.config1:",self.config)
        # print("deterministic_config:",deterministic_config)

        # print("deterministic_config:",deterministic_config)
        if deterministic_config is not None: 
            for key in ["scene", "components", "instructions", "conditions"]:
                if key in deterministic_config["task"].keys():
                    # print("key:",key)
                    self.config["task"][key] = deterministic_config["task"][key]
            for key in ["target_entity", "target_container", "target_entities", "robocasa_scene"]:
                if key in deterministic_config["task"].keys() and hasattr(self.config_manager, key):
                    setattr(self.config_manager, key, deterministic_config["task"][key])

            # New: make the deterministic robocasa_scene actually take part in loading.
            # Background: in the two loops above, if the deterministic components wholly
            # replace the list, the scene entries appended during the
            # config_manager.get_xxx_task_config() stage would be wiped out; while the
            # robocasa_scene string itself is only set via setattr and never triggers loading.
            # So after the override completes, call load_robocasa_scene() once more (with a dedup check).
            if deterministic_config["task"].get("robocasa_scene") is not None:
                scene_in_components = any(
                    isinstance(c, dict)
                    and str(c.get("name", "")).rsplit("_", 1)[0] in ROBOCASA_SCENE_NAMES
                    for c in self.config["task"]["components"]
                )
                if not scene_in_components:
                    self.config_manager.load_robocasa_scene()

        # print("self.config[---:", self.config["task"]["components"])

        # 1. Define the predicate and the recursive helper outside the loop
        def is_scene_name(full_name):
            return any(scene in full_name for scene in ROBOCASA_SCENE_NAMES)

        def process_entity(entity_config):
            # Filter out scene names
            if is_scene_name(entity_config["name"]):
                return

            # Add the current entity
            self.component_name_list.append(entity_config["name"])
            # print("entity_config[\"name\"]:", entity_config["name"])

            # If there are subentities, recurse to process them
            if "subentities" in entity_config and entity_config["subentities"]:
                for sub_entity in entity_config["subentities"]:
                    process_entity(sub_entity)

        # 2. Keep the original traversal behavior, redirecting it to the recursive entry point
        for entity_config in self.config["task"]["components"]:
            process_entity(entity_config)

        # Known issue: mid_contain cannot be recognized
        self.cleaned_component_name_list = self.get_clean_entity_names(self.component_name_list)
        # print("self.component_name_list:",self.component_name_list)
        # load engine config
        self.set_engine_config(self.config["engine"])
        # load scene and entities
        if self.config["task"].get("scene", None) is not None:
            robot_config = self.config.get("robot", None)
            config["task"]["scene"]["robot"] = robot_config
            self.load_scene_from_config(config["task"]["scene"])
        for entity_config in self.config["task"]["components"]:
            self.load_entity_from_config(entity_config)
        # build instrutions
        self.build_instruction()
        # build conditions
        self.init_conditions()

        #add robocasa fixtures name
        for condition in self.config["task"]["conditions"].keys():
            if condition == "scene_contain":
                robocasa_container = self.config["task"]["conditions"][condition]["container_name"]
                robocasa_container_name = robocasa_container.split("_")[0]
                self.cleaned_component_name_list.append(robocasa_container_name)

        # print("self.cleaned_component_name_list:", self.cleaned_component_name_list)
        # exit()

        self.random_ignored_entities.extend(self.config["task"].get("random_ignored_entities", []))
        if self.config_manager.work_info and deterministic_config is None:
            self.reset_entities_positions()


    def attach_entities_to_arena(self):
        for key, entity in self.entities.items():
            if any(obj in key for obj in self.attach_objects):
                # Old approach: detach + attach (weld to world), which freezes knob joints
                entity.detach()
                self._arena.attach(entity)


    def _has_child_joints(self, entity):
        """Check whether the entity has internal joints other than a freejoint (e.g. hinge, slide)."""
        for joint in entity.mjcf_model.find_all('joint'):
            if joint.tag != 'freejoint':
                return True
        return False

    def _fix_entity_with_equality(self, entity):
        """Lock the freejoint with an equality constraint while keeping child joints movable."""

        freejoint = None
        for joint in entity.mjcf_model.find_all('joint'):
            if joint.tag == 'freejoint':
                freejoint = joint
                break

        if freejoint is not None:
            self._arena.mjcf_model.equality.add(
                'joint', joint=freejoint
            )
        else:
            # Already attached and no freejoint left; fall back to weld
            root_body = entity.mjcf_model.find(
                'body', entity.mjcf_model.model
            )
            if root_body is not None:
                self._arena.mjcf_model.equality.add(
                    'weld', body1=root_body
                )

    # Initialize positions in the environment only after all entity_configs are loaded and set up
    def init_conditions(self):
        # print("dm_self.entities:", self.entities)
        if self.config["task"].get("conditions", None) is not None:
            condition_config = copy.deepcopy(self.config["task"]["conditions"])
        else: # no condition configs, return False. Task build default conditions
            self.conditions = None
            return False
        conditions = list()
        # or-style, list=[{contain:{}}]
        for condition_key, specific_condition in condition_config.items():
            # print("condition_key:", condition_key)
            # print("specific_condition:", specific_condition)
            # Look up the condition class by key (e.g. contain_v) from the registry
            condition_cls = register.load_condition(condition_key)
            for k, entities in specific_condition.items():


                if k in ["robot"]:
                    specific_condition[k] = self.robot
                    continue
                if k in ["positions", "target_pos_range"]: continue

                if k in ["target_bbox"]:
                    specific_condition[k] = entities
                    continue

                if k in ["container_name"]: continue

                if isinstance(entities, str):
                    specific_condition[k] = self.entities.get(entities, None)
                    if specific_condition[k] is None:
                        specific_condition[k] = entities
                if isinstance(entities, list):
                    # k corresponds to each individual contain_v: {} entry
                    specific_condition[k] = [self.entities.get(entity, None) for entity in entities]
            # Build the condition
            condition = condition_cls(**specific_condition)
            print("condition:", condition)
            conditions.append(condition)
            if condition_key in ["contain_robot_pose"]:
                self.navigation_condition = condition

        self.conditions = ConditionSet(conditions)

        # navigation

        return True
    
    def set_engine_config(self, config):
        """
        Recursively sets attributes from a nested dictionary to mujoco engine attributes.
        """

        def set_recursive_attr(obj, config):
            for key, value in config.items():
                if isinstance(value, dict):
                    if hasattr(obj, key):
                        nested_obj = getattr(obj, key)
                        set_recursive_attr(nested_obj, value)
                    else:
                        setattr(obj, key, type(obj)())
                        set_recursive_attr(getattr(obj, key), value)
                else:
                    setattr(obj, key, value)
                    
        set_recursive_attr(self._arena.mjcf_model, config)
         
    def load_scene_from_config(self, config):
        """
        Build the scene from the configuration dictionary
        """
        scene = Scene(**config)
        self.attach_entity(scene)
        self.scene = scene

    def reset_entities_positions(self):
        if self.config_manager.objects is not None:
            entities = self.config_manager.objects
            # print("entities:", entities)
            for k in entities:
                entity = self.entities[k]
                height = entity.get_placement_height()
                # print(f"{k}_height:{height}")
                entity.init_pos[2] =entity.init_pos[2] + height


    def load_entity_from_config(self, config: dict, parent_node=None):
        entity_cls = config.get("class", None)
        assert entity_cls is not None, "entity class must be provided"
        if isinstance(entity_cls, str):
            # print("entity_cls: ", entity_cls)
            entity_cls = register.load_entity(entity_cls)
        elif isinstance(entity_cls, Entity):
            entity_cls = entity_cls
        if config.get("xml_path", None) is not None:
            config["xml_path"] = os.path.join(self.asset_path, config["xml_path"])
        if parent_node is not None:
            config["parent_entity"] = parent_node
            self.random_ignored_entities.append(config["name"])
        entity = entity_cls(**config)
        entity_name = config.get("name", None)

        if entity_name.rsplit('_', 1)[0] in ROBOCASA_SCENE_NAMES:
            # print("self.entities:", self.entities)
            self.attach_entity(entity)
            # self.add_free_entity(entity)
            # self._fix_entity_with_equality(entity)
            # Keep the robocasa scene class out of self.entities; a different route is needed if used later
            self.robocasa_scene = entity
            # self.entities[entity.mjcf_model.model] = entity
        elif entity_name in (self.config_manager.fixed_fixture or []):
            self.add_free_entity(entity)

        else:
            self.add_free_entity(entity)
        # self.attach_entity(entity)

        if entity.subentities is not None:
            for subentity_config in entity.subentities:
                self.load_entity_from_config(subentity_config, parent_node=entity)
        return entity

    
    def attach_entity(self, entity):
        self._arena.attach(entity)

    
    def _build_observables(self):
        self.robot.observables.joint_positions.enabled = True
        self.robot.observables.joint_velocities.enabled = True
        self._task_observables["robot"] = self.robot.observables
        for obs in self._task_observables.values():
            obs.enabled = True
    
    def get_element_by_name(self, name, type):
        return self._arena.mjcf_model.find(f"{type}", name)
    
    def add_disturbance(self, magnitude, random_state):
        """randomly add disturbance to the scene for robustness testing"""
        pass
    
    def get_instruction(self):
        if isinstance(self.instructions, str):
            return self.instructions
        elif isinstance(self.instructions, list):
            if self.instructions:
                return random.sample(self.instructions, 1)[-1]
            return None

    def remove_second_last(self,skill_sequence):
        """Remove the second-to-last element of the list."""
        if len(skill_sequence) >= 2:
            return skill_sequence[:-2] + skill_sequence[-1:]
        return skill_sequence

    def should_terminate_episode(self, physics):
        if self.navigation_condition is not None:
            self.robot_end_pos = self.robot.get_link_base_info(physics)["position"]
            self.navig_condition = self.navigation_condition.is_met(physics)
        else:
            self.navig_condition = True
        if hasattr(self, "conditions"):
            terminal = self.conditions.is_met(physics) and self.skill_end
            self.task_success = terminal
        else:
            terminal = False
        return terminal

    def check_collision(self, physics):
        # body1_id = physics.model.body(body1_name+"/").id
        # body2_id = physics.model.body(body2_name+"/").id
        contact_body_pairs = set()
        for contact in physics.data.contact:
            if contact.dist == 0:
                continue
            geom1_id = contact.geom1
            geom2_id = contact.geom2

            contact_body1 = physics.model.geom_bodyid[geom1_id]
            contact_body2 = physics.model.geom_bodyid[geom2_id]
            pair = sorted([contact_body1, contact_body2])
            contact_body_pairs.add(tuple(pair))   

        combinations = itertools.combinations(list(self.entities.keys()), 2)
        for combine in combinations:
            pair = tuple(sorted([physics.model.body(combine[0]+"/").id, 
                                physics.model.body(combine[1]+"/").id]))
            if pair in contact_body_pairs:
                print(f"{pair} in contact")
                # return True
            
    def intialization_valid(self, physics):
        collision = self.check_collision(physics)
        if collision:
            return False
        return True
    
    def reset_distractors(self, n_distractor=1):
        """
        generate n distractor entities randomly for task robustness and diversity
        """
        for name, distractor in self.distractors.items():
            self.delete_entity(distractor)
        self.distractors.clear()    
        for i in range(n_distractor):
            entity_name,  entity_cls_and_xml= random.choice(list(name2class_xml.items()))
            entity_cls, xml_path = entity_cls_and_xml[0], entity_cls_and_xml[1]
            # print("entity_cls",entity_cls)
            # choose a new entity if the entity name already exists
            while entity_name in self.entities.keys():
                entity_name, entity_cls_and_xml = random.choice(list(name2class_xml.items()))
                entity_cls, xml_path = entity_cls_and_xml[0], entity_cls_and_xml[1]
            xml_path = os.path.join(self.asset_path, "obj/meshes", xml_path)
            distractor = entity_cls(name=f"distractor_{i}_{entity_name}", xml_path=xml_path, position=[0, 0, 0.82], orientation=[0, 0, 0])
            self.add_free_entity(distractor)
            self.distractors[distractor.mjcf_model.model] = distractor
    
    def reset_intention_distance(self):
        self.intention_distance = dict()
        entity_names = list(self.entities.keys())
        for ignore_entity in self.random_ignored_entities:
            if ignore_entity in entity_names:
                entity_names.remove(ignore_entity)
        for entity_name in entity_names: 
            self.intention_distance[entity_name] = np.inf
            
    def reset_task_progress(self):
        self.target_is_grasped = dict()
        if isinstance(self.target_entity, str):
            self.target_is_grasped[self.target_entity] = False
        elif isinstance(self.target_entity, list):
            for entity in self.target_entity:
                self.target_is_grasped[entity] = False
        
    def update_intention_distance(self, physics):
        ee_pos = self.robot.get_end_effector_pos(physics)
        for key, entity in self.entities.items():
            if key in self.random_ignored_entities: continue
            self.intention_distance[key] = min(self.intention_distance[key], distance(ee_pos, entity.get_xpos(physics)))
    
    def update_task_progress(self, physics):
        if isinstance(self.target_entity, list):
            for entity in self.target_entity:
                if self.entities[entity].is_grasped(physics, self.robot):
                    self.target_is_grasped[entity] = True
        elif isinstance(self.target_entity, str):
            if self.entities[self.target_entity].is_grasped(physics, self.robot):
                self.target_is_grasped[self.target_entity] = True
        
    def get_intention_score(self, physics, threshold=0.2, discrete=True):
        if isinstance(self.target_entity, list):
            return self.get_intention_score_to_entity(physics, self.target_entity[-1], threshold, discrete)
        return self.get_intention_score_to_entity(physics, self.target_entity, threshold, discrete)
    
    def get_task_progress(self, physics):
        # FIXME: temporary solution: in primitive tasks, a successful pick often occupies half of the task progress
        _, conditions_met = self.conditions.met_progress(physics)
        n_condition = len(self.conditions)
        n_condition += len(self.target_is_grasped)
        target_entity_met = []
        for value in self.target_is_grasped.values():
            if value: target_entity_met.append(value)
        return (len(conditions_met) + len(target_entity_met)) / n_condition
    
    def get_intention_score_to_entity(self, physics, entity_name, threshold=0.2, discrete=False):
        """
        Get the intention score of the entity during carry out, computed by the min distance to the entity.
        """
        if discrete:
            return int(self.intention_distance[entity_name] < threshold)
        else:
            if threshold - self.intention_distance[entity_name] < 0:
                return 0
            return 1 / (1 + (threshold - self.intention_distance[entity_name]) + 1e-6)
        
    def get_expert_skill_sequence(self, physics):
        """
        Expert trajectory generation for the task. Notice that the success rate is not 100%.
        """
        logging.info(f"Task:{self.task_name} did not implement get_expert_skill_sequence method")
        return None
    
    def build_instruction(self):
        self.instructions = ['']
        if self.config["task"].get("instructions", None) is not None:
            self.instructions = self.config["task"]["instructions"]
        if not self.use_llm:
            return 
        # generate instruction with GPT4
        with open(os.path.join(PROJECT_ROOT, "configs/prompt/prompt.json"), "r") as f:
            prompts = json.load(f)
        if not self.task_name in prompts.keys():
            assert self.instructions is not None, "instruction must be provided"
            return 
        prompt = prompts[self.task_name]
        sys_prompt_0, sys_prompt_1, sys_prompt_2 = prompt["instruction_0"], prompt["instruction_1"], prompt["instruction_2"]
        target_entity = self.target_entity
        entity_names = list(self.entities.keys())
        query = f"{sys_prompt_0} {entity_names}. {sys_prompt_1} {target_entity}. {sys_prompt_2}"
        try:
            instructions = query_gpt4_v(query)
            instructions = re.findall(r'instruction:\s*"([^"]*)"', instructions)
            self.instructions = instructions
        except:
            self.instructions = []
    
    def save(self, physics):
        """
        Save the task information for deterministic evaluation
        """
        data_to_dump = dict(
            task=dict(
                components=[],
            )   
        )
        for entity in self.entities.values():
            data_to_dump["task"]["components"].append(entity.save(physics))
        data_to_dump["task"]["scene"] = self.scene.save(physics)
        data_to_dump["task"]["instructions"] = self.instructions
        data_to_dump["task"]["conditions"] = self.config["task"].get("conditions", None)
        data_to_dump["robot"] = self.robot.save(physics)


        # "robocasa_scene": "ONE_WALL_LARGE_1",
        # "destination_position": "top",
        # "fixture_surface": "island_counter_island_group"


        for key in ["robocasa_scene","destination_position","fixture_surface","target_entity", "target_container", "other_entity","target_entities"]:
            if hasattr(self.config_manager, key):
                data_to_dump["task"][key] = getattr(self.config_manager, key)
        return data_to_dump


    # test Status synchronization


