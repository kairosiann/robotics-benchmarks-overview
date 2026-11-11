from functools import partial

from RMMBench.tasks.navigation.base import CompositeNavigationTask
from RMMBench.tasks.config_manager import CompositeNavigationConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


# Fixed fixture name of the sink shared by every wash_place scene
# (same as the fixed_fixture entry in the task asset config).
SINK_NAME = "sink_0"


# =============================================================================
# Base classes for nav_wash_place tasks
# =============================================================================

class NavWashPlaceBaseConfigManager(CompositeNavigationConfigManager):
    """
    Base ConfigManager for nav_wash_place tasks.

    Default (dual-area) success condition, mirroring nav_cook_steak's chained
    condition and wash_veg_salad's sink -> container semantics:
        step 0: navigate to the pick area (layout 0)
        step 1: navigate to the sink island (layout 1)
        step 2: wash - target object inside sink_0 AND faucet open (is_open,
                locks in once satisfied, ANDed within this step)
        step 3: place - target object inside the final container
        ordered: 0 -> 1 -> 2 -> 3

    Orientation tokens are derived from each layout's destination_position
    (bottom/left/right/top) so subclasses with a different approach direction
    (e.g. carrot_1 "right", apple_1 "left") reuse this condition as-is.

    Single-area variants (carrot_2 / carrot_3) override with a 3-step chain:
    navigate -> wash(sink + is_open) -> place(container).
    """

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        target = self.merged_seen_object[0][0]
        container = f"{self.merged_seen_container[1][0]}"
        orientation_1 = self.composite_configs[0]["destination_position"]
        orientation_2 = self.composite_configs[1]["destination_position"]

        conditions_config["asyn_sequence"] = [
            # Step 0: navigate to area 1 and pick the target object
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
            # Step 1: navigate to area 2 (sink island)
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
            # Step 2: wash - put the object into the sink and turn on the
            # faucet (is_open locks in once satisfied, ANDed within this step,
            # mirroring wash_veg_salad's manipulation condition)
            dict(
                contain=dict(
                    container=SINK_NAME,
                    entities=[target],
                ),
                is_open=dict(
                    container=SINK_NAME,
                ),
            ),
            # Step 3: place the washed object into the final container
            dict(
                contain=dict(
                    container=container,
                    entities=[target],
                ),
            ),
        ]
        # Ordered: pick area -> sink island -> wash in sink -> place in container
        conditions_config["ordered_indices"] = [0, 1, 2, 3]

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = orientation_1
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
        self.target_object_info[1]["target_orientation"] = orientation_2

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


class NavWashPlaceBaseTask(CompositeNavigationTask):
    """
    Base Task for nav_wash_place tasks.

    Default (dual-area) expert sequence:
        nav to area 1 (placeholder moves) -> pick the target object ->
        nav to area 2 / sink island (placeholder moves) ->
        wash skill sequence (sink -> faucet -> container) -> end.

    Single-area variants (carrot_2 / carrot_3) override
    get_expert_skill_sequence with the single-area version.
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

    def get_wash_skill_sequence(self, target_entity_name, target_container_name):
        """
        Manipulation skills mirroring wash_veg_salad's wash flow:
        put the held object into the sink -> turn on the faucet ->
        pick the object back -> place it into the final container.
        Prerequisite: the gripper is already holding the target object.
        Skill-level prerequisites (e.g. pick body_name="sink_0/handle" before
        open_sink) are the same as in wash_multi_fruit_veg.py / wash_veg_salad.
        """
        return [
            # wash: put the held object into the sink
            partial(SkillLib.place, target_container_name=SINK_NAME),
            partial(SkillLib.observe),
            # turn on the faucet: pinch the handle, then open_sink lifts it
            partial(SkillLib.pick, body_name=f"{SINK_NAME}/handle"),
            partial(SkillLib.open_sink, target_entity_name=SINK_NAME),
            partial(SkillLib.observe),
            # transfer the washed object to the final container
            partial(SkillLib.pick, target_entity_name=target_entity_name),
            partial(SkillLib.place, target_container_name=target_container_name),
            partial(SkillLib.observe),
        ]

    def get_expert_skill_sequence(self, physics):
        """
        Dual-area expert: pick the target in area 1, carry it to the sink
        island, wash it (sink + faucet), then place it into the container.
        Navigation moves are placeholders (moveforward/rotate) to be tuned
        per scene.
        """
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target = target_entity[0][0]
        container = target_container[1][0]

        skill_sequence = [
            # --- Navigation to area 1 (placeholder moves, to be tuned per scene) ---
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_left),
            partial(SkillLib.moveforward),
            # --- Area 1 reached: pick up the target object ---
            partial(SkillLib.pick, target_entity_name=target),
            # --- Navigation to area 2 / sink island (placeholder moves) ---
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_right),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
        ]
        # --- Area 2 reached: wash at the sink, then place into the container ---
        skill_sequence.extend(
            self.get_wash_skill_sequence(target, container)
        )
        skill_sequence.append(partial(SkillLib.end))
        return skill_sequence


# =============================================================================
# wash_place_carrot navigation variants
# =============================================================================

@register.add_config_manager("nav_wash_place_carrot_0")
class NavWashPlaceCarrot0ConfigManager(NavWashPlaceBaseConfigManager):
    """
    Variant 0: Dual-area, robot faces one of the areas.
    Difficulty: tier_2 (obstacle, dual-area)
    Scene: U_SHAPED_LARGE_6
    Layout 0: counter_1_main_group (bottom) - pick carrot
    Layout 1: sink_island_group (top) - wash and place
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            },
            {
                "workregion_offset": -0.35,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},  # Layout 0: no container
            {
                "configs": [
                    {"offset": 0.1, "y_set": 0.1, "direction": "right", "z_set": 0.01},
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to pick the carrot, then go to the sink to wash and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_wash_place_carrot_0")
class NavWashPlaceCarrot0Task(NavWashPlaceBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate", "sink", "carrot", "radish", "cucumber"]
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("nav_wash_place_carrot_1")
class NavWashPlaceCarrot1ConfigManager(NavWashPlaceCarrot0ConfigManager):
    """
    Variant 1: Dual-area, robot in front of obstacle, forced detour.
    Difficulty: tier_3 (obstacle, dual-area, forced detour)
    Scene: U_SHAPED_LARGE_3
    Layout 0: counter_1_left_group (right) - pick carrot
    Layout 1: sink_island_group (top) - wash and place
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["carrot_1"],
                "distractor": ["radish_6", "cucumber_2"],
                "fixture_surface": "counter_1_left_group",
                "destination_position": "right"
            },
            {
                "seen_container": ["plate_0"],
                "fixture_surface": "sink_island_group",
                "destination_position": "top"
            }
        ]

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            },
            {
                "workregion_offset": -0.35,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            }
        ]

        self.CONTAINER_CONFIG_TABLE = [
            {},  # Layout 0: no container
            {
                "configs": [
                    {"offset": 0.1, "y_set": 0.1, "direction": "right", "z_set": 0.01},
                ]
            }
        ]
        self.robocasa_scene = "U_SHAPED_LARGE_3"
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")


    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to pick the carrot from the left counter, then go to the sink to wash and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_wash_place_carrot_1")
class NavWashPlaceCarrot1Task(NavWashPlaceCarrot0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3, -4, 0.0],  # in front of the fridge
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# =============================================================================
# wash_place_apple navigation variants
# =============================================================================

@register.add_config_manager("nav_wash_place_apple_0")
class NavWashPlaceApple0ConfigManager(NavWashPlaceBaseConfigManager):
    """
    Variant 0: Dual-area, robot faces one of the areas.
    Difficulty: tier_2 (obstacle, dual-area)
    Scene: U_SHAPED_LARGE_4
    Layout 0: counter_main_main_group (bottom) - pick apple
    Layout 1: sink_island_group (top) - wash and place
    """

    def __init__(self, task_name, num_objects=[[3, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            },
            {
                "workregion_offset": -0.35,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},  # Layout 0: no container
            {
                "configs": [
                    {"offset": -0.1, "y_set": 0.1, "direction": "right", "z_set": 0.01},
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to pick the apple, then go to the sink to wash and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_wash_place_apple_0")
class NavWashPlaceApple0Task(NavWashPlaceBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate", "sink", "apple", "pear", "peach", "pomegranate"]
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("nav_wash_place_apple_1")
class NavWashPlaceApple1ConfigManager(NavWashPlaceApple0ConfigManager):
    """
    Variant 1: Dual-area, robot in front of obstacle, forced detour.
    Difficulty: tier_3 (obstacle, dual-area, forced detour)
    Scene: U_SHAPED_LARGE_5
    Layout 0: counter_1_right_group (left) - pick apple
    Layout 1: sink_island_group (top) - wash and place
    """

    def __init__(self, task_name, num_objects=[[3, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["apple_22"],
                "distractor": ["pear_10", "peach_3", "pomegranate_1"],
                "fixture_surface": "counter_1_right_group",
                "destination_position": "left"
            },
            {
                "seen_container": ["plate_7"],
                "fixture_surface": "sink_island_group",
                "destination_position": "top"
            }
        ]
        self.robocasa_scene = "U_SHAPED_LARGE_5"
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
        instruction = ["Navigate to pick the apple from the right counter, then go to the sink to wash and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_wash_place_apple_1")
class NavWashPlaceApple1Task(NavWashPlaceApple0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3, -4, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# =============================================================================
# wash_place_cucumber navigation variants
# =============================================================================

@register.add_config_manager("nav_wash_place_cucumber_0")
class NavWashPlaceCucumber0ConfigManager(NavWashPlaceBaseConfigManager):
    """
    Variant 0: Dual-area, robot faces one of the areas.
    Difficulty: tier_2 (obstacle, dual-area)
    Scene: U_SHAPED_LARGE_7
    Layout 0: island_island_group (bottom) - pick cucumber
    Layout 1: sink_island_group (top) - wash and place
    """

    def __init__(self, task_name, num_objects=[[4, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0.7,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            },
            {
                "workregion_offset": -0.35,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            }
        ]
        self.CONTAINER_CONFIG_TABLE = [
            {},  # Layout 0: no container
            {
                "configs": [
                    {"offset": -0.1, "y_set": 0.1, "direction": "right", "z_set": 0.01},
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to pick the cucumber, then go to the sink to wash and place it in the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_wash_place_cucumber_0")
class NavWashPlaceCucumber0Task(NavWashPlaceBaseTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["tray", "sink", "cucumber", "zucchini", "eggplant", "carrot", "bell_pepper"]
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("nav_wash_place_cucumber_1")
class NavWashPlaceCucumber1ConfigManager(NavWashPlaceCucumber0ConfigManager):
    """
    Variant 1: Dual-area, robot in front of obstacle, forced detour.
    Difficulty: tier_3 (obstacle, dual-area, forced detour)
    Scene: U_SHAPED_LARGE_9
    Layout 0: counter_main_main_group (bottom) - pick cucumber
    Layout 1: sink_island_group (top) - wash and place
    """

    def __init__(self, task_name, num_objects=[[4, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["cucumber_2"],
                "distractor": ["zucchini_7", "eggplant_1", "carrot_4", "bell_pepper_3"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom"
            },
            {
                "seen_container": ["tray_7"],
                "fixture_surface": "sink_island_group",
                "destination_position": "top"
            }
        ]
        self.robocasa_scene = "U_SHAPED_LARGE_9"
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
        instruction = ["Navigate to pick the cucumber from the main counter, then go to the sink to wash and place it in the tray."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_wash_place_cucumber_1")
class NavWashPlaceCucumber1Task(NavWashPlaceCucumber0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3, -4, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# =============================================================================
# wash_place_carrot single-area variants
# =============================================================================

@register.add_config_manager("nav_wash_place_carrot_2")
class NavWashPlaceCarrot2ConfigManager(NavWashPlaceCarrot0ConfigManager):
    """
    Variant 2: Single-area, robot in front of obstacle.
    Difficulty: tier_2 (obstacle, single-area, near obstacle)
    Scene: U_SHAPED_LARGE_2
    Layout 0: sink_island_group (top) - wash and place carrot

    Single-area condition (3-step chain):
        step 0: navigate to the sink island
        step 1: wash - carrot inside sink_0 AND faucet open (is_open)
        step 2: place - carrot inside the plate
        ordered: 0 -> 1 -> 2
    """

    def __init__(self, task_name, num_objects=[[2, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["carrot_1"],
                "distractor": ["radish_6", "cucumber_2"],
                "seen_container": ["plate_0"],
                "fixture_surface": "sink_island_group",
                "destination_position": "top"
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
                    {"offset": 0.16, "y_set": -0.05, "direction": "right", "z_set": 0}
                ]
            }
        ]

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to the sink to wash the carrot and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        target = self.merged_seen_object[0][0]
        # Single-area: object and container share layout 0
        container = f"{self.merged_seen_container[0][0]}"
        orientation = self.composite_configs[0]["destination_position"]

        conditions_config["asyn_sequence"] = [
            # Step 0: navigate to the sink island
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation=orientation,
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                )
            ),
            # Step 1: wash - put the carrot into the sink and turn on the
            # faucet (is_open locks in once satisfied, ANDed within this step,
            # mirroring wash_veg_salad's manipulation condition)
            dict(
                contain=dict(
                    container=SINK_NAME,
                    entities=[target],
                ),
                is_open=dict(
                    container=SINK_NAME,
                ),
            ),
            # Step 2: place the washed carrot into the plate
            dict(
                contain=dict(
                    container=container,
                    entities=[target],
                ),
            ),
        ]
        # Ordered: navigate -> wash in sink -> place in container
        conditions_config["ordered_indices"] = [0, 1, 2]

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = orientation
        self.config["task"]["conditions"] = conditions_config


@register.add_task("nav_wash_place_carrot_2")
class NavWashPlaceCarrot2Task(NavWashPlaceCarrot0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3, -4, 0.0],
            "euler": [0, 0, 1.57],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        """
        Single-area expert: pick the carrot on the sink island, wash it at the
        sink, then place it into the plate. No second navigation leg.
        Navigation moves are placeholders to be tuned per scene.
        """
        target_entity = self.config_manager.target_entity
        target_container = self.config_manager.target_container
        target = target_entity[0][0]
        # Single-area: object and container share layout 0
        container = target_container[0][0]

        skill_sequence = [
            # --- Navigation to the sink island (placeholder moves, to be tuned per scene) ---
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_left),
            partial(SkillLib.moveforward),
            # --- Area reached: pick the target object ---
            partial(SkillLib.pick, target_entity_name=target),
        ]
        # --- Wash at the sink, then place into the container ---
        skill_sequence.extend(
            self.get_wash_skill_sequence(target, container)
        )
        skill_sequence.append(partial(SkillLib.end))
        return skill_sequence


@register.add_config_manager("nav_wash_place_carrot_3")
class NavWashPlaceCarrot3ConfigManager(NavWashPlaceCarrot2ConfigManager):
    """
    Variant 3: Single-area, obstacle present but robot starts in open space.
    Difficulty: tier_2 (obstacle, single-area, open start)
    Scene: U_SHAPED_LARGE_8
    Layout 0: sink_island_group (top) - wash and place carrot
    """

    def __init__(self, task_name, num_objects=[[2, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["carrot_1"],
                "distractor": ["radish_6", "cucumber_2"],
                "seen_container": ["plate_0"],
                "fixture_surface": "sink_island_group",
                "destination_position": "top"
            }
        ]
        self.robocasa_scene = "U_SHAPED_LARGE_1"

        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to the sink to wash the carrot and place it on the plate."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_wash_place_carrot_3")
class NavWashPlaceCarrot3Task(NavWashPlaceCarrot2Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [5, -4, 0.0],  # in front of the fridge
            "euler": [0, 0, 1.57],
        }
        self.robot.set_init_pos(**self.robot_params)
