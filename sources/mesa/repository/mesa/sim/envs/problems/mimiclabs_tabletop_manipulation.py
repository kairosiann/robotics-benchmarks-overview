"""
This file contains the MimicLabs Tabletop Manipulation classes for 8 different scenes (adapted from LIBERO).
"""

import numpy as np
from robosuite.utils.mjcf_utils import new_site

import mesa
from mesa.sim.envs.objects.utils import humanize_id

from ..bddl_base_domain import BDDLBaseDomain, register_problem
from ..objects import *
from ..predicates import *
from ..regions import *
from ..robots import *


class MimicLabs_Tabletop_Manipulation_Base(BDDLBaseDomain):
    workspace_name = "table"
    default_table_full_size = (1.0, 1.2, 0.05)
    default_table_offset = (0.0, 0, 0.90)
    # If None, defaults to (0.01 - table_full_size[2]).
    default_z_offset = None
    default_arena_type = "table"
    default_scene_xml = (
        f"{mesa.__path__[0]}/sim/assets/scenes/libero_scenes/"
        "libero_kitchen_tabletop_base_style.xml"
    )
    # If not None and caller didn't pass scene_properties, these are applied.
    default_scene_properties = None
    reverse_mount_robots = False
    
    def __init__(self, **kwargs):
        self.visualization_sites_list = []
        # Subclasses can pre-set attributes before calling super().__init__.
        if "table_full_size" in kwargs and kwargs["table_full_size"] is not None:
            # (Bugfix) This used to reference an undefined variable `table_full_size`.
            self.table_full_size = kwargs["table_full_size"]
        elif not hasattr(self, "table_full_size"):
            self.table_full_size = self.default_table_full_size

        if not hasattr(self, "table_offset"):
            self.table_offset = self.default_table_offset

        # For z offset of environment fixtures
        if not hasattr(self, "z_offset"):
            if self.default_z_offset is None:
                self.z_offset = 0.01 - self.table_full_size[2]
            else:
                self.z_offset = self.default_z_offset

        if self.reverse_mount_robots and "robots" in kwargs and kwargs["robots"] is not None:
            robots = list(kwargs["robots"])
            robots = [
                robot_name
                if robot_name.startswith("ReverseMounted")
                else f"ReverseMounted{robot_name.removeprefix('Mounted')}"
                for robot_name in robots
            ]
            kwargs.update({"robots": robots})
        if "workspace_offset" not in kwargs or kwargs["workspace_offset"] is None:
            kwargs.update({"workspace_offset": self.table_offset})
        if "arena_type" not in kwargs or kwargs["arena_type"] is None:
            kwargs.update({"arena_type": self.default_arena_type})
        if "scene_xml" not in kwargs or kwargs["scene_xml"] is None:
            kwargs.update(
                {
                    "scene_xml": self.default_scene_xml
                }
            )
        if (
            ("scene_properties" not in kwargs or kwargs["scene_properties"] is None)
            and self.default_scene_properties is not None
        ):
            # Avoid sharing a mutable dict between instances.
            kwargs.update({"scene_properties": dict(self.default_scene_properties)})

        self.natural_name_dict = {}

        self._serialize_kwargs = kwargs

        super().__init__(**kwargs)

    def serialize(self):
        return {
            "env_name": self.__class__.__name__,
            "env_kwargs": self._serialize_kwargs,
        }

    def get_object_natural_name(self, object_name):
        return self.natural_name_dict[object_name]

    def _load_fixtures_in_arena(self, mujoco_arena):
        """Nothing extra to load in this simple problem."""
        for fixture_category in list(self.parsed_problem["fixtures"].keys()):
            if "table" in fixture_category:
                continue
            for fixture_instance in self.parsed_problem["fixtures"][fixture_category]:
                self.fixtures_dict[fixture_instance] = get_object_fn(
                    fixture_category, self.object_format
                )(
                    name=fixture_instance,
                    joints=None,
                )

    def _load_objects_in_arena(self, mujoco_arena):
        objects_dict = self.parsed_problem["objects"]
        for category_name in objects_dict.keys():
            for object_name in objects_dict[category_name]:
                self.objects_dict[object_name] = get_object_fn(
                    category_name, self.object_format
                )(
                    name=object_name
                )
                self.natural_name_dict[object_name] = humanize_id(category_name)

    def _load_sites_in_arena(self, mujoco_arena):
        # Create site objects
        object_sites_dict = {}
        region_dict = self.parsed_problem["regions"]
        for object_region_name in list(region_dict.keys()):

            if "table" in object_region_name:
                ranges = region_dict[object_region_name]["ranges"][0]
                assert ranges[2] >= ranges[0] and ranges[3] >= ranges[1]
                zone_size = ((ranges[2] - ranges[0]) / 2, (ranges[3] - ranges[1]) / 2)
                zone_centroid_xy = (
                    (ranges[2] + ranges[0]) / 2 + self.workspace_offset[0],
                    (ranges[3] + ranges[1]) / 2 + self.workspace_offset[1],
                )
                target_zone = TargetZone(
                    name=object_region_name,
                    rgba=region_dict[object_region_name]["rgba"],
                    zone_size=zone_size,
                    z_offset=self.workspace_offset[2],
                    zone_centroid_xy=zone_centroid_xy,
                )
                object_sites_dict[object_region_name] = target_zone
                mujoco_arena.table_body.append(
                    new_site(
                        name=target_zone.name,
                        pos=target_zone.pos + np.array([0.0, 0.0, -0.90]),
                        quat=target_zone.quat,
                        rgba=target_zone.rgba,
                        size=target_zone.size,
                        type="box",
                    )
                )
                continue
            # Otherwise the processing is consistent
            for query_dict in [self.objects_dict, self.fixtures_dict]:
                for name, body in query_dict.items():
                    try:
                        if "worldbody" not in list(body.__dict__.keys()):
                            # Handling composite objects
                            parts = [body.get_obj(), *body.get_obj().findall(".//body")]
                        else:
                            parts = body.worldbody.find("body").findall(".//body")
                    except Exception:
                        continue

                    for part in parts:
                        sites = part.findall(".//site")
                        joints = part.findall("./joint")  # joints within the part
                        if sites == []:
                            break
                        for site in sites:
                            site_name = site.get("name")
                            if site_name == object_region_name:
                                object_sites_dict[object_region_name] = SiteObject(
                                    name=site_name,
                                    parent_name=body.name,  # name in bddl
                                    joints=[joint.get("name") for joint in joints],
                                    size=site.get("size"),
                                    rgba=site.get("rgba"),
                                    site_type=site.get("type"),
                                    site_pos=site.get("pos"),
                                    site_quat=site.get("quat"),
                                    object_properties=body.object_properties,
                                )
                                # NOTE(VS) this creates SiteObject's with empty list of joints for the "object" part
                                # and finally overrides them with the SiteObject with the correct list of joints upon
                                # reaching the correct part that has the required site as well as the joint.
        self.object_sites_dict = object_sites_dict

        # Keep track of visualization objects
        for query_dict in [self.fixtures_dict, self.objects_dict]:
            for name, body in query_dict.items():
                if body.object_properties["vis_site_names"] != {}:
                    self.visualization_sites_list.append(name)

    def _add_placement_initializer(self):
        """Very simple implementation at the moment. Will need to upgrade for other relations later."""
        super()._add_placement_initializer()

    def _check_success(self):
        """
        Check if the goal is achieved. Consider conjunction goals at the moment
        """
        goal_conj = self.parsed_problem["goal_state"][0]
        goal_state = self.parsed_problem["goal_state"][1:]
        if goal_conj == "and":
            result = True
            for state in goal_state:
                result = self._eval_predicate(state) and result
        elif goal_conj == "or":
            result = False
            for state in goal_state:
                result = self._eval_predicate(state) or result
        else:
            raise ValueError(f"Unsupported goal conjunction {goal_conj}.")
        return result
        
    def _get_subtask_progress(self):
        """
        Returns list of currently satisfied subtasks for a given timestep
        """
        satisfied = set()
        demo_states = self.parsed_problem.get("demonstration_states", [])

        for state in demo_states:
            if self._eval_predicate(state):
                satisfied.add(tuple(state))

        return satisfied

    def _get_distractor_task_completion(self):
        """
        Returns any completed distractor tasks for a given timestep
        """
        completed_dist_tasks = set()
        potential_dist_tasks = self.parsed_problem.get("distractor_goal_specs", [])

        for task in potential_dist_tasks:
            if self._eval_predicate(task):
                completed_dist_tasks.add(tuple(task))

        return completed_dist_tasks

    def _eval_predicate(self, state):
        if len(state) == 3:
            # Checking binary logical predicates
            predicate_fn_name = state[0]
            object_1_name = state[1]
            object_2_name = state[2]
            if (
                object_1_name not in self.object_states_dict
                or object_2_name not in self.object_states_dict
            ):
                return False
            return eval_predicate_fn(
                predicate_fn_name,
                self.object_states_dict[object_1_name],
                self.object_states_dict[object_2_name],
            )
        elif len(state) == 2:
            # Checking unary logical predicates
            predicate_fn_name = state[0]
            object_name = state[1]
            if object_name not in self.object_states_dict:
                return False
            return eval_predicate_fn(
                predicate_fn_name, self.object_states_dict[object_name]
            )

    def _setup_references(self):
        super()._setup_references()

    def _post_process(self):
        super()._post_process()

        self.set_visualization()

    def set_visualization(self):

        for object_name in self.visualization_sites_list:
            for _, (site_name, site_visible) in (
                self.get_object(object_name).object_properties["vis_site_names"].items()
            ):
                vis_g_id = self.sim.model.site_name2id(site_name)
                if ((self.sim.model.site_rgba[vis_g_id][3] <= 0) and site_visible) or (
                    (self.sim.model.site_rgba[vis_g_id][3] > 0) and not site_visible
                ):
                    # We toggle the alpha value
                    self.sim.model.site_rgba[vis_g_id][3] = (
                        1 - self.sim.model.site_rgba[vis_g_id][3]
                    )


@register_problem
class MimicLabs_Lab1_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_z_offset = 0.01
    default_scene_properties = {
        "floor_style": "gray_ceramic_tile",
        "wall_style": "yellow_linen_wall_texture",
    }


@register_problem
class MimicLabs_Lab2_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_scene_xml = "scenes/mimiclabs_scenes/lab2.xml"
    default_scene_properties = {
        "floor_style": "seamless_wood_planks_floor",
        "wall_style": "light-gray-plaster",
    }


@register_problem
class MimicLabs_Lab3_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_scene_xml = "scenes/mimiclabs_scenes/lab3.xml"
    default_scene_properties = {
        "wall_style": "wall0",
        "floor_style": "cotton",
    }


@register_problem
class MimicLabs_Lab4_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_scene_xml = "scenes/mimiclabs_scenes/lab4.xml"
    default_scene_properties = {"wall_style": "yellow_linen_wall_texture"}


@register_problem
class MimicLabs_Lab5_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_scene_xml = "scenes/mimiclabs_scenes/lab5.xml"
    default_scene_properties = {
        "wall_style": "wall8",
        "floor_style": "cotton",
    }


@register_problem
class MimicLabs_Lab6_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_scene_xml = "scenes/mimiclabs_scenes/lab6.xml"
    default_scene_properties = {"wall_style": "wall1"}


@register_problem
class MimicLabs_Lab7_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_scene_xml = "scenes/mimiclabs_scenes/lab7.xml"
    default_scene_properties = {"wall_style": "wall2"}


@register_problem
class MimicLabs_Lab8_Tabletop_Manipulation(MimicLabs_Tabletop_Manipulation_Base):
    reverse_mount_robots = True
    default_scene_xml = "scenes/mimiclabs_scenes/lab8.xml"
