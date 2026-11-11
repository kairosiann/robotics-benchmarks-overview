from functools import partial

from RMMBench.tasks.navigation.base import CompositeNavigationTask
from RMMBench.tasks.config_manager import CompositeNavigationConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


# =============================================================================
# Base classes for nav_select_tool tasks
# =============================================================================

class NavSelectToolBaseConfigManager(CompositeNavigationConfigManager):
    """
    Base ConfigManager for nav_select_tool tasks.
    Based on pick_kitchen_tool: choose the right tool based on food beside tray.

    Region 1: tools (whisk / bottle_opener / can_opener) + distractors
    Region 2: food/drink + container (tray)

    Subclasses override: composite_configs, robocasa_scene, num_objects,
    LAYOUT_CONFIG_TABLE, CONTAINER_CONFIG_TABLE, get_instruction, get_condition_config.
    """
    pass


class NavSelectToolBaseTask(CompositeNavigationTask):
    """
    Base Task for nav_select_tool tasks.
    attach_objects includes all possible objects for debugging convenience.
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "plate", "sink", "tray",
            # "apple", "pear", "peach", "pomegranate",
            # "whisk", "spoon", "ladle", "spatula",
            # "bottle_opener", "can_opener", "scissors",
            # "egg", "beer", "canned_food",

        ]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def reset_entities_positions(self):
        if self.config_manager.composite_entities is not None:
            entities = self.config_manager.composite_entities
            for k in entities:
                entity = self.entities.get(f"{k}", None)
                if entity is None:
                    continue
                height = entity.get_placement_height()
                if height == 0:
                    height = 0.005
                entity.init_pos[2] += height


# =============================================================================
# GALLEY variants (3 variants)
# =============================================================================

@register.add_config_manager("nav_select_tool_galley_0")
class NavSelectToolGalley0ConfigManager(NavSelectToolBaseConfigManager):
    """
    GALLEY Variant 0: Dual-area, robot faces one of the areas.
    Difficulty: tier_2 (dual-area)
    Scene: GALLEY_0
    Layout 0: counter_main_main_group (left) - pick tool
    Layout 1: counter_right_main_group (left) - place tool on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "GALLEY_0"
        self.composite_configs = [
            {
                "seen_object": ["whisk_8"],
                "distractor": ["spoon_14", "ladle_3", "spatula_6"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "left"
            },
            {
                "seen_object": ["egg_10"],
                "seen_container": ["tray_3"],
                "fixture_surface": "counter_right_main_group",
                "destination_position": "left"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            },
            {
                "workregion_offset": 0.2,
                "workregion_y_set": 0.02,
                "target_dim": (0.4, 0.4),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},  # Layout 0: no container
            {
                "configs": [
                    {"offset": 0.3, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Choose the appropriate tool based on the egg beside the tray and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="left",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="left",
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[1][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "left"
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
        self.target_object_info[1]["target_orientation"] = "left"

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


@register.add_task("nav_select_tool_galley_0")
class NavSelectToolGalley0Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_1 = target_container[1][0]

        skill_sequence = []
        # for entity in target_entities:
        skill_sequence.extend([
            partial(SkillLib.moveforward,L_th=5),
            partial(SkillLib.rotate_right),
            partial(SkillLib.moveforward, L_th=5),

            partial(SkillLib.pick, target_entity_name=target_entities[0]),
            partial(SkillLib.rotate_right),
            partial(SkillLib.moveforward, L_th=5),
            partial(SkillLib.rotate_left),
            partial(SkillLib.place, target_container_name=target_container_1),
            partial(SkillLib.observe),
        ])
        skill_sequence.extend([partial(SkillLib.end)])
        # skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("nav_select_tool_galley_1")
class NavSelectToolGalley1ConfigManager(NavSelectToolBaseConfigManager):
    """
    GALLEY Variant 1: Dual-area, robot faces one of the areas (different layout).
    Difficulty: tier_2 (dual-area)
    Scene: GALLEY_1
    Layout 0: counter_left_group (right) - pick tool
    Layout 1: counter_main_main_group (left) - place tool on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "GALLEY_1"
        self.composite_configs = [
            {
                "seen_object": ["bottle_opener_5"],
                "distractor": ["can_opener_2", "scissors_1"],
                "fixture_surface": "counter_left_group",
                "destination_position": "right"
            },
            {
                "seen_object": ["beer_9"],
                "seen_container": ["tray_3"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "left"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            },
            {
                "workregion_offset": 0.2,
                "workregion_y_set": 0.02,
                "target_dim": (0.4, 0.4),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},
            {
                "configs": [
                    {"offset": 0.25, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Choose the appropriate tool based on the beer beside the tray and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="right",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="left",
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[1][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "right"
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
        self.target_object_info[1]["target_orientation"] = "left"

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


@register.add_task("nav_select_tool_galley_1")
class NavSelectToolGalley1Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_1 = target_container[1][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_1),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("nav_select_tool_galley_2")
class NavSelectToolGalley2ConfigManager(NavSelectToolBaseConfigManager):
    """
    GALLEY Variant 2: Single-area, robot in open space.
    Difficulty: tier_1 (single-area, open space)
    Scene: GALLEY_2
    Layout 0: counter_main_main_group (left) - pick tool and place on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "GALLEY_2"
        self.composite_configs = [
            {
                "seen_object": ["can_opener_1"],
                "distractor": ["whisk_2", "spatula_3", "tongs_0"],
                "seen_container": ["tray_3"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "left"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {
                "configs": [
                    {"offset": 0.25, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["There are three tools on the table. Help me choose the appropriate tool for the canned food and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="left",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[0][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "left"
        self.config["task"]["conditions"] = conditions_config


@register.add_task("nav_select_tool_galley_2")
class NavSelectToolGalley2Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_0 = target_container[0][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_0),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


# =============================================================================
# L_SHAPED_LARGE variants (3 variants)
# =============================================================================

@register.add_config_manager("nav_select_tool_l_large_0")
class NavSelectToolLLarge0ConfigManager(NavSelectToolBaseConfigManager):
    """
    L_SHAPED_LARGE Variant 0: Dual-area, robot faces one of the areas.
    Difficulty: tier_2 (obstacle, dual-area)
    Scene: L_SHAPED_LARGE_0
    Layout 0: counter_main_main_group (bottom) - pick tool
    Layout 1: counter_1_right_main_group (bottom) - place tool on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_LARGE_0"
        self.composite_configs = [
            {
                "seen_object": ["whisk_8"],
                "distractor": ["spoon_14", "ladle_3", "spatula_6"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom"
            },
            {
                "seen_object": ["egg_10"],
                "seen_container": ["tray_3"],
                "fixture_surface": "counter_1_right_main_group",
                "destination_position": "bottom"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            },
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.02,
                "target_dim": (0.4, 0.4),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},
            {
                "configs": [
                    {"offset": 0.25, "y_set": 0.09, "direction": "right", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Choose the appropriate tool based on the egg beside the tray and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="bottom",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="bottom",
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[1][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "bottom"
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
        self.target_object_info[1]["target_orientation"] = "bottom"

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


@register.add_task("nav_select_tool_l_large_0")
class NavSelectToolLLarge0Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [5, -3.5, 3.14],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_1 = target_container[1][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_1),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("nav_select_tool_l_large_1")
class NavSelectToolLLarge1ConfigManager(NavSelectToolBaseConfigManager):
    """
    L_SHAPED_LARGE Variant 1: Dual-area, robot in front of island, forced detour.
    Difficulty: tier_3 (obstacle, dual-area, forced detour)
    Scene: L_SHAPED_LARGE_1
    Layout 0: counter_1_left_left_group (right) - pick tool
    Layout 1: counter_main_main_group (bottom) - place tool on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_LARGE_1"
        self.composite_configs = [
            {
                "seen_object": ["bottle_opener_5"],
                "distractor": ["can_opener_2", "scissors_1"],
                "fixture_surface": "counter_1_left_left_group",
                "destination_position": "right"
            },
            {
                "seen_object": ["beer_9"],
                "seen_container": ["tray_3"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0.8,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            },
            {
                "workregion_offset": -0.3,
                "workregion_y_set": 0.02,
                "target_dim": (0.4, 0.4),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},
            {
                "configs": [
                    {"offset": 0.15, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Choose the appropriate tool based on the beer beside the tray and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="right",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="bottom",
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[1][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "right"
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
        self.target_object_info[1]["target_orientation"] = "bottom"

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


@register.add_task("nav_select_tool_l_large_1")
class NavSelectToolLLarge1Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [5, -3.5, 3.14],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_1 = target_container[1][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_1),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("nav_select_tool_l_large_2")
class NavSelectToolLLarge2ConfigManager(NavSelectToolBaseConfigManager):
    """
    L_SHAPED_LARGE Variant 2: Single-area, robot near island.
    Difficulty: tier_2 (obstacle, single-area, near obstacle)
    Scene: L_SHAPED_LARGE_2
    Layout 0: island_left_group (top/bottom/left/right) - pick tool and place on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_LARGE_2"
        self.composite_configs = [
            {
                "seen_object": ["can_opener_1"],
                "distractor": ["whisk_2", "spatula_3", "tongs_0"],
                "seen_container": ["tray_3"],
                "fixture_surface": "island_left_group",
                "destination_position": "top"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {
                "configs": [
                    {"offset": 0.25, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["There are three tools on the table. Help me choose the appropriate tool for the canned food and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="top",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[0][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "top"
        self.config["task"]["conditions"] = conditions_config


@register.add_task("nav_select_tool_l_large_2")
class NavSelectToolLLarge2Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [5, -3.5, 4],
            "euler": [0, 0, 3.14],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_0 = target_container[0][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_0),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


# =============================================================================
# L_SHAPED_SMALL variants (3 variants)
# =============================================================================

@register.add_config_manager("nav_select_tool_l_small_0")
class NavSelectToolLSmall0ConfigManager(NavSelectToolBaseConfigManager):
    """
    L_SHAPED_SMALL Variant 0: Dual-area, robot faces one of the areas.
    Difficulty: tier_2 (dual-area)
    Scene: L_SHAPED_SMALL_0
    Layout 0: counter_main_main_group (bottom) - pick tool
    Layout 1: counter_1_right_group (left) - place tool on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_SMALL_0"
        self.composite_configs = [
            {
                "seen_object": ["whisk_8"],
                "distractor": ["spoon_14", "ladle_3", "spatula_6"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom"
            },
            {
                "seen_object": ["egg_10"],
                "seen_container": ["tray_7"],
                "fixture_surface": "counter_2_right_group",
                "destination_position": "left"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0.8,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            },
            {
                "workregion_offset": 0.2,
                "workregion_y_set": 0.02,
                "target_dim": (0.4, 0.4),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},
            {
                "configs": [
                    {"offset": 0.25, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Choose the appropriate tool based on the egg beside the tray and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="bottom",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="left",
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[1][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "bottom"
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
        self.target_object_info[1]["target_orientation"] = "left"

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


@register.add_task("nav_select_tool_l_small_0")
class NavSelectToolLSmall0Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)

    def reset_entities_positions(self):
        if self.config_manager.composite_entities is not None:
            entities = self.config_manager.composite_entities
            for k in entities:
                entity = self.entities.get(f"{k}", None)
                if entity is None:
                    continue
                height = entity.get_placement_height()
                if height == 0:
                    height = 0.02
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_1 = target_container[1][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_1),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("nav_select_tool_l_small_1")
class NavSelectToolLSmall1ConfigManager(NavSelectToolBaseConfigManager):
    """
    L_SHAPED_SMALL Variant 1: Single-area, robot in open space.
    Difficulty: tier_1 (single-area, open space)
    Scene: L_SHAPED_SMALL_1
    Layout 0: counter_main_main_group (bottom) - pick tool and place on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_SMALL_1"
        self.composite_configs = [
            {
                "seen_object": ["bottle_opener_5"],
                "distractor": ["can_opener_2", "scissors_1"],
                "seen_container": ["tray_7"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.02,
                "target_dim": (0.35, 0.3),
                "grid_size": [2, 2]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {
                "configs": [
                    {"offset": 0.3, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["There are three tools on the table. Help me choose the appropriate tool for the beer and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="bottom",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[0][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "bottom"
        self.config["task"]["conditions"] = conditions_config


@register.add_task("nav_select_tool_l_small_1")
class NavSelectToolLSmall1Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)

    def reset_entities_positions(self):
        if self.config_manager.composite_entities is not None:
            entities = self.config_manager.composite_entities
            for k in entities:
                entity = self.entities.get(f"{k}", None)
                if entity is None:
                    continue
                height = entity.get_placement_height()
                if height == 0:
                    height = 0.005
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_0 = target_container[0][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_0),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("nav_select_tool_l_small_2")
class NavSelectToolLSmall2ConfigManager(NavSelectToolBaseConfigManager):
    """
    L_SHAPED_SMALL Variant 2: Single-area, robot at far end of L.
    Difficulty: tier_2 (single-area, far start)
    Scene: L_SHAPED_SMALL_2
    Layout 0: counter_2_right_group (left) - pick tool and place on tray beside food
    """

    def __init__(self, task_name, num_objects=[[2, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_SMALL_2"
        self.composite_configs = [
            {
                "seen_object": ["can_opener_1"],
                "distractor": ["whisk_2", "spatula_3", "tongs_0"],
                "seen_container": ["tray_3"],
                "fixture_surface": "counter_2_right_group",
                "destination_position": "left"
            }
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [8, 8]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {
                "configs": [
                    {"offset": 0.25, "y_set": 0.09, "direction": "left", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["There are three tools on the table. Help me choose the appropriate tool for the canned food and place it into the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="left",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[0][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "left"
        self.config["task"]["conditions"] = conditions_config


@register.add_task("nav_select_tool_l_small_2")
class NavSelectToolLSmall2Task(NavSelectToolBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [1.5, -1.5, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target_entities = target_entity[0]
        target_container_0 = target_container[0][0]

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=target_container_0),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence
