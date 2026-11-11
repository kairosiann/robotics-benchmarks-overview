from functools import partial

from RMMBench.tasks.navigation.base import CompositeNavigationTask
from RMMBench.tasks.config_manager import CompositeNavigationConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


# =============================================================================
# Base classes for nav_cook_steak tasks
# =============================================================================

class NavCookSteakBaseConfigManager(CompositeNavigationConfigManager):
    """
    Base ConfigManager for nav_cook_steak tasks.
    Based on cook_meat_pan_stove / cook_steak_0.
    Scene: U_SHAPED_LARGE (1 obstacle island).

    Region 2 is based on the base configuration of cook_steak_0:
    - fixture_surface: stovetop_main_group
    - destination_position: bottom
    - seen_container: ["plate_0", "pan_1"]
    - fixed_fixture: ["sink_0", "stove_0"]

    Subclasses override: composite_configs, robocasa_scene, LAYOUT_CONFIG_TABLE,
    load_objects_for_layout, get_instruction, get_condition_config.
    """
    pass


class NavCookSteakBaseTask(CompositeNavigationTask):
    """
    Base Task for nav_cook_steak tasks.
    Subclasses override: attach_objects, robot initial position.
    """
    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)

    def attach_entities_to_arena(self):
        for key, entity in self.entities.items():
            if any(obj in key for obj in self.attach_objects):
                entity.detach()
                self._arena.attach(entity)

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

    def get_manipulation_skill_sequence(self):
        """
        Manipulation skills mirroring cook_steak_0: put the steak into the
        pan, turn on the stove knob, then transfer it to the plate.
        """
        return [
            partial(SkillLib.place, target_container_name="pan_1"),
            partial(SkillLib.observe),
            partial(SkillLib.pick, body_name="stove_0/knob_front_right"),
            partial(SkillLib.rotate_knob),
            partial(SkillLib.observe),
            partial(SkillLib.pick, target_entity_name="steak_0"),
            partial(SkillLib.place, target_container_name="plate_0"),
        ]


# =============================================================================
# cook_steak navigation variants (cook_steak_0 based, U_SHAPED_LARGE)
# =============================================================================

@register.add_config_manager("nav_cook_steak_0")
class NavCookSteak0ConfigManager(NavCookSteakBaseConfigManager):
    """
    Variant 0: Dual-area, robot faces one of the areas.
    Difficulty: tier_2 (obstacle, dual-area)
    Scene: U_SHAPED_LARGE_0
    Layout 0: island_island_group (bottom) - pick steak
    Layout 1: stovetop_main_group (bottom) - cook and place
    """

    def __init__(self, task_name, num_objects=[[1, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            },
            {
            "workregion_offset":-0.62,
            "workregion_y_set":0.05,
            "target_dim":(0.25, 0.25),
            "grid_size":[2, 2],
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},  # Layout 0: no container
            {
                "configs": [
                    {"offset": 0.18, "y_set": -0.03, "direction": "right", "z_set": 0.01},
                    {"offset": 0.25, "y_set": 0.1, "direction": "left", "z_set": 0.04, "orient_offset": [0, 0, 3.14]},
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to pick the steak, then go to the stove to cook it in the pan and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        # Orientation tokens are derived from each area's destination_position
        # (bottom/left/right/top) so that subclasses with a different approach
        # direction can reuse this condition as-is.
        orientation_1 = self.composite_configs[0]["destination_position"]
        orientation_2 = self.composite_configs[1]["destination_position"]
        conditions_config["asyn_sequence"] = [
            # Step 0: navigate to area 1 (pick the steak)
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation=orientation_1,
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            # Step 1: navigate to area 2 (stove)
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation=orientation_2,
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron"
                )
            ),
            # Step 2: cook - put the steak into the pan and turn on the stove
            # (is_open locks in once satisfied, ANDed within this step,
            # mirroring cook_steak_0's manipulation condition)
            dict(
                contain=dict(
                    container="pan_1",
                    entities=["steak_0"]
                ),
                is_open=dict(
                    container="stove_0",
                    joint_name="knob_front_right"
                ),
            ),
            # Step 3: place the cooked steak on the plate
            dict(
                contain=dict(
                    container="plate_0",
                    entities=["steak_0"]
                ),
            ),
        ]
        # Ordered: pick (nav 0) -> stove (nav 1) -> cook in pan -> place on
        # plate, enforcing the pan-before-plate order of cook_steak_0.
        conditions_config["ordered_indices"] = [0, 1, 2, 3]

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = orientation_1
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
        self.target_object_info[1]["target_orientation"] = orientation_2

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


@register.add_task("nav_cook_steak_0")
class NavCookSteak0Task(NavCookSteakBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate", "pan", "stove", "sink",
                               # "steak", "pork_chop", "lamb_chop"
                               ]
        super().__init__(task_name, robot=robot, **kwargs)

    def get_expert_skill_sequence(self, physics):
        skill_sequence = [
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_left),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            # Area 1 reached: pick up the steak
            partial(SkillLib.pick, target_entity_name="steak_0"),
            partial(SkillLib.rotate_right),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
        ]
        # Area 2 (stove) reached: cook in pan, turn on the stove, place on plate
        skill_sequence.extend(self.get_manipulation_skill_sequence())
        skill_sequence.append(partial(SkillLib.end))
        return skill_sequence


@register.add_config_manager("nav_cook_steak_1")
class NavCookSteak1ConfigManager(NavCookSteak0ConfigManager):
    """
    Variant 1: Dual-area, robot in front of obstacle, forced detour.
    Difficulty: tier_3 (obstacle, dual-area, forced detour)
    Scene: U_SHAPED_LARGE_4
    Layout 0: counter_1_left_group (right) - pick steak
    Layout 1: stovetop_main_group (bottom) - cook and place
    """

    def __init__(self, task_name, num_objects=[[1, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["steak_0"],
                "distractor": ["pork_chop_13", "lamb_chop_5"],
                "fixture_surface": "counter_1_left_group",
                "destination_position": "right"
            },
            {
                "seen_container": ["plate_0", "pan_1"],
                "fixture_surface": "stovetop_main_group",
                "destination_position": "bottom"
            }
        ]
        self.robocasa_scene = "U_SHAPED_LARGE_4"
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0.2,
                "workregion_y_set": 0.02,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            },
            {
                "workregion_offset": -0.65,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to pick the steak from the left counter, then go to the stove to cook it in the pan and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_cook_steak_1")
class NavCookSteak1Task(NavCookSteak0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3, -4, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# =============================================================================
# cook_steak Variant 2: Single-area, robot in front of obstacle
# =============================================================================

@register.add_config_manager("nav_cook_steak_2")
class NavCookSteak2ConfigManager(NavCookSteak0ConfigManager):
    """
    Variant 2: Single-area, robot in front of obstacle.
    Difficulty: tier_2 (obstacle, single-area, near obstacle)
    Scene: U_SHAPED_LARGE_2
    Layout 0: stovetop_main_group (bottom) - cook steak and place
    """

    def __init__(self, task_name, num_objects=[[1, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["steak_0"],
                "distractor": ["pork_chop_13", "lamb_chop_5"],
                "seen_container": ["plate_0", "pan_1"],
                "fixture_surface": "stovetop_main_group",
                "destination_position": "bottom"
            }
        ]
        self.robocasa_scene = "U_SHAPED_LARGE_2"
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": -0.65,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {
                "configs": [
                    {"offset": 0.18, "y_set": -0.03, "direction": "right", "z_set": 0.01},
                    {"offset": 0.25, "y_set": 0.1, "direction": "left", "z_set": 0.04, "orient_offset": [0, 0, 3.14]},
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to the stove to cook the steak in the pan and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        # Orientation token derived from the single area's destination_position.
        orientation_1 = self.composite_configs[0]["destination_position"]
        conditions_config["asyn_sequence"] = [
            # Step 0: dock at the operating area
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation=orientation_1,
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            # Step 1: cook - put the steak into the pan and turn on the stove
            # (is_open locks in once satisfied, ANDed within this step,
            # mirroring cook_steak_0's manipulation condition)
            dict(
                contain=dict(
                    container="pan_1",
                    entities=["steak_0"]
                ),
                is_open=dict(
                    container="stove_0",
                    joint_name="knob_front_right"
                ),
            ),
            # Step 2: place the cooked steak on the plate
            dict(
                contain=dict(
                    container="plate_0",
                    entities=["steak_0"]
                ),
            ),
        ]
        # Ordered: dock -> cook in pan -> place on plate, enforcing the
        # pan-before-plate order of cook_steak_0.
        conditions_config["ordered_indices"] = [0, 1, 2]

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = orientation_1
        self.config["task"]["conditions"] = conditions_config


@register.add_task("nav_cook_steak_2")
class NavCookSteak2Task(NavCookSteak0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3, -4, 0.0],
            "euler": [0, 0, 1.57],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        # Single area: dock once, then cook in pan and place on plate
        # (steak_0 is in the same area as pan_1/plate_0).
        skill_sequence = [
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_left),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
        ]
        skill_sequence.extend(self.get_manipulation_skill_sequence())
        skill_sequence.append(partial(SkillLib.end))
        return skill_sequence


# =============================================================================
# cook_steak Variant 3: Single-area, obstacle present but robot starts in open space
# =============================================================================

@register.add_config_manager("nav_cook_steak_3")
class NavCookSteak3ConfigManager(NavCookSteak2ConfigManager):
    """
    Variant 3: Single-area, obstacle present but robot starts in open space.
    Difficulty: tier_2 (obstacle, single-area, open start)
    Scene: U_SHAPED_LARGE_8
    Layout 0: stovetop_main_group (bottom) - cook steak and place
    """

    def __init__(self, task_name, num_objects=[[1, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["steak_0"],
                "distractor": ["pork_chop_13", "lamb_chop_5"],
                "seen_container": ["plate_0", "pan_1"],
                "fixture_surface": "stovetop_main_group",
                "destination_position": "bottom"
            }
        ]
        self.robocasa_scene = "U_SHAPED_LARGE_8"

        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to the stove to cook the steak in the pan and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_cook_steak_3")
class NavCookSteak3Task(NavCookSteak2Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [5, -4, 0.0],
            "euler": [0, 0, 1.57],
        }
        self.robot.set_init_pos(**self.robot_params)
