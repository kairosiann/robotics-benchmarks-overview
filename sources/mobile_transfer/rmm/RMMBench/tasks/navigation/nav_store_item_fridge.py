from functools import partial

from RMMBench.tasks.navigation.base import CompositeNavigationTask
from RMMBench.tasks.config_manager import CompositeNavigationConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


# ==================== Base ConfigManager ====================

class NavStoreItemFridgeConfigManager(CompositeNavigationConfigManager):
    """
    Base ConfigManager for nav_store_item_fridge tasks.
    Each sub-task has 2 variants (0: dual-region facing one area;
                                   1: dual-region robot in front of obstacle).
    """

    def __init__(self, task_name, num_objects=None, **kwargs):
        if num_objects is None:
            num_objects = [[2, 1], [0, 1]]
        super().__init__(task_name, num_objects, **kwargs)

        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.4, 0.4),
                "grid_size": [8, 8],
            },
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.02,
                "target_dim": (0.4, 0.4),
                "grid_size": [6, 6],
            },
        ]

        self.CONTAINER_CONFIG_TABLE = [
            {},
            {
                "configs": [
                    {"offset": 0.1, "y_set": 0.09, "direction": "left", "z_set": 0},
                    {"offset": 0.1, "y_set": 0.09, "direction": "right", "z_set": 0}

                ]
            },
        ]

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron",
                ),

            ),
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[1],
                    robot="pandaomron",
                ),

            ),
            dict(
                # 参考 manipulation 版 store_item_fridge：is_open 必须先于 contain
                # （once met, always met：开门状态在时序中会被记住，之后关门不影响判定）
                is_open=dict(
                    container=f"{self.merged_seen_container[1][0]}",
                ),
            ),
            dict(
                contain=dict(
                    entities=[self.merged_seen_object[0][0]],
                    container=f"{self.merged_seen_container[1][0]}",
                )
            ),
        ]
        conditions_config["ordered_indices"] = [0, 1, 2, 3]

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[1]["target_bbox"] = self.target_bbox[1]

        self.config["task"]["conditions"] = conditions_config

    def reorder_target_object_info(self):
        pass


class NavStoreItemFridgeTask(CompositeNavigationTask):
    """Base Task for nav_store_item_fridge."""

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "plate", "sink", "small_fridge", "tray",
        ]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)

    def reset_entities_positions(self):
        if self.config_manager.composite_entities is not None:
            entities = self.config_manager.composite_entities
            for k in entities:
                entity = self.entities.get(k)
                if entity is None:
                    continue
                height = entity.get_placement_height()
                if "water_bottle_2" in k:
                    height += 0.035
                elif "bottle" in k:
                    height += 0.04
                elif "wine" in k:
                    height -= 0.03
                elif "beer" in k:
                    height -= 0.03
                elif "alcohol" in k:
                    height += -0.02
                elif "milk" in k:
                    height += -0.01
                elif "boxed" in k:
                    height += -0.02
                elif "pepsi" in k:
                    height += -0.02
                elif any(d in k for d in ["cola_1", "lemonade_3"]):
                    height += 0.03
                elif height == 0:
                    height += 0.01
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        target_entities = self.config_manager.target_entity[0]
        containers_region2 = self.config_manager.target_container[1]
        fridge = containers_region2[0]
        # 区域2托盘：单臂机器人先放托盘腾出夹爪开门，再取回放入冰箱
        tray = containers_region2[1] if len(containers_region2) > 1 else fridge

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                # 区域1：拿起目标饮料
                partial(SkillLib.pick, target_entity_name=entity),
                # 区域2：先把饮料放到托盘上（腾出夹爪）
                partial(SkillLib.place, target_container_name=tray),
                partial(SkillLib.observe),
                # 开冰箱门（参考 manipulation 版：pick(handle) -> open_door）
                partial(SkillLib.pick, body_name=f"{fridge}/handle"),
                partial(SkillLib.open_door, target_container_name=fridge),
                partial(SkillLib.observe),
                # 从托盘取回饮料，放入冰箱
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=fridge),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


# ==================== Sub-task 1: store_non_alcoholic_drink (G_SHAPED_SMALL) ====================

@register.add_config_manager("nav_store_non_alcoholic_drink_0")
class NavStoreNonAlcoholicDrink0ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 0: dual-region, robot faces one of the areas.
    Scene: G_SHAPED_SMALL_9
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "G_SHAPED_SMALL_9"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_2"],
                "distractor": ["beer_5", "wine_2"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom",
            },
            {
                "seen_container": ["small_fridge","tray_7"],
                "fixture_surface": "counter_1_front_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["I would like a chilled non-alcoholic drink. Navigate to the counter where several drinks are placed, and keep the drink I want chilled in the white mini fridge. If necessary, the tray beside the mini fridge can serve as a temporary intermediate container."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_non_alcoholic_drink_0")
class NavStoreNonAlcoholicDrink0Task(NavStoreItemFridgeTask):
    pass


@register.add_config_manager("nav_store_non_alcoholic_drink_1")
class NavStoreNonAlcoholicDrink1ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 1: dual-region, robot in front of obstacle.
    Scene: G_SHAPED_SMALL_8
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "G_SHAPED_SMALL_8"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_2"],
                "distractor": ["beer_5", "wine_2"],
                "fixture_surface": "counter_1_left_group",
                "destination_position": "right",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "counter_1_front_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["I would like a chilled non-alcoholic drink. Navigate to the counter where several drinks are placed, and keep the drink I want chilled in the white mini fridge. If necessary, the tray beside the mini fridge can serve as a temporary intermediate container."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_non_alcoholic_drink_1")
class NavStoreNonAlcoholicDrink1Task(NavStoreItemFridgeTask):
    def __init__(self, task_name, robot, **kwargs):

        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3.0, -4.0, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# ==================== Sub-task 2: store_child_drink (L_SHAPED_LARGE) ====================

@register.add_config_manager("nav_store_child_drink_0")
class NavStoreChildDrink0ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 0: dual-region, robot faces one of the areas.
    Scene: L_SHAPED_LARGE_8
    """

    def __init__(self, task_name, num_objects=[[3, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_LARGE_8"
        self.composite_configs = [
            {
                "seen_object": ["boxed_drink_2"],
                "distractor": ["beer_11", "wine_9", "alcohol_7"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "island_left_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a suitable drink for a child."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_child_drink_0")
class NavStoreChildDrink0Task(NavStoreItemFridgeTask):
    pass


@register.add_config_manager("nav_store_child_drink_1")
class NavStoreChildDrink1ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 1: dual-region, robot in front of obstacle.
    Scene: L_SHAPED_LARGE_7
    """

    def __init__(self, task_name, num_objects=[[3, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "L_SHAPED_LARGE_7"
        self.composite_configs = [
            {
                "seen_object": ["boxed_drink_2"],
                "distractor": ["beer_11", "wine_9", "alcohol_7"],
                "fixture_surface": "counter_1_left_left_group",
                "destination_position": "right",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "island_left_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a suitable drink for a child."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_child_drink_1")
class NavStoreChildDrink1Task(NavStoreItemFridgeTask):
    def __init__(self, task_name, robot, **kwargs):

        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3.0, -4.0, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# ==================== Sub-task 3: store_no_sugar_drink (WRAPAROUND) ====================

@register.add_config_manager("nav_store_no_sugar_drink_0")
class NavStoreNoSugarDrink0ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 0: dual-region, robot faces one of the areas.
    Scene: WRAPAROUND_7
    """

    def __init__(self, task_name, num_objects=[[4, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "WRAPAROUND_7"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_3"],
                "distractor": ["cola_1", "pepsi_3", "lemonade_3", "boxed_drink_0"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "island_island_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a no-sugar drink option."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_no_sugar_drink_0")
class NavStoreNoSugarDrink0Task(NavStoreItemFridgeTask):
    pass


@register.add_config_manager("nav_store_no_sugar_drink_1")
class NavStoreNoSugarDrink1ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 1: dual-region, robot in front of obstacle.
    Scene: WRAPAROUND_6
    """

    def __init__(self, task_name, num_objects=[[4, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "WRAPAROUND_6"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_3"],
                "distractor": ["cola_1", "pepsi_3", "lemonade_3", "boxed_drink_0"],
                "fixture_surface": "counter_1_right_group",
                "destination_position": "left",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "island_island_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a no-sugar drink option."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_no_sugar_drink_1")
class NavStoreNoSugarDrink1Task(NavStoreItemFridgeTask):
    def __init__(self, task_name, robot, **kwargs):

        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3.0, -4.0, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# ==================== Sub-task 4: store_non_alcoholic_drink (U_SHAPED_SMALL) ====================

@register.add_config_manager("nav_store_non_alcoholic_drink_2")
class NavStoreNonAlcoholicDrink2ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 0: dual-region, robot faces one of the areas.
    Scene: U_SHAPED_SMALL_6
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "U_SHAPED_SMALL_6"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_2"],
                "distractor": ["beer_5", "wine_2"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "counter_1_left_group",
                "destination_position": "right",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill the non-alcoholic option."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_non_alcoholic_drink_2")
class NavStoreNonAlcoholicDrink2Task(NavStoreItemFridgeTask):
    pass


@register.add_config_manager("nav_store_non_alcoholic_drink_3")
class NavStoreNonAlcoholicDrink3ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 1: dual-region, robot in front of obstacle.
    Scene: U_SHAPED_SMALL_5
    """

    def __init__(self, task_name, num_objects=[[2, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "U_SHAPED_SMALL_5"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_2"],
                "distractor": ["beer_5", "wine_2"],
                "fixture_surface": "counter_1_left_group",
                "destination_position": "right",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill the non-alcoholic option."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_non_alcoholic_drink_3")
class NavStoreNonAlcoholicDrink3Task(NavStoreItemFridgeTask):
    def __init__(self, task_name, robot, **kwargs):

        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3.0, -4.0, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# ==================== Sub-task 5: store_child_drink (G_SHAPED_LARGE) ====================

@register.add_config_manager("nav_store_child_drink_2")
class NavStoreChildDrink2ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 0: dual-region, robot faces one of the areas.
    Scene: G_SHAPED_LARGE_5
    """

    def __init__(self, task_name, num_objects=[[3, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "G_SHAPED_LARGE_5"
        self.composite_configs = [
            {
                "seen_object": ["boxed_drink_2"],
                "distractor": ["beer_11", "wine_9", "alcohol_7"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "counter_1_front_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a suitable drink for a child."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_child_drink_2")
class NavStoreChildDrink2Task(NavStoreItemFridgeTask):
    pass


@register.add_config_manager("nav_store_child_drink_3")
class NavStoreChildDrink3ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 1: dual-region, robot in front of obstacle.
    Scene: G_SHAPED_LARGE_4
    """

    def __init__(self, task_name, num_objects=[[3, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "G_SHAPED_LARGE_4"
        self.composite_configs = [
            {
                "seen_object": ["boxed_drink_2"],
                "distractor": ["beer_11", "wine_9", "alcohol_7"],
                "fixture_surface": "counter_1_left_group",
                "destination_position": "right",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "counter_1_front_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a suitable drink for a child."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_child_drink_3")
class NavStoreChildDrink3Task(NavStoreItemFridgeTask):
    def __init__(self, task_name, robot, **kwargs):

        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3.0, -4.0, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)


# ==================== Sub-task 6: store_no_sugar_drink (ONE_WALL_LARGE) ====================

@register.add_config_manager("nav_store_no_sugar_drink_2")
class NavStoreNoSugarDrink2ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 0: dual-region, robot faces one of the areas.
    Scene: ONE_WALL_LARGE_4
    """

    def __init__(self, task_name, num_objects=[[4, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "ONE_WALL_LARGE_4"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_3"],
                "distractor": ["cola_1", "pepsi_3", "lemonade_3", "boxed_drink_0"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "island_counter_island_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a no-sugar drink option."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_no_sugar_drink_2")
class NavStoreNoSugarDrink2Task(NavStoreItemFridgeTask):
    pass


@register.add_config_manager("nav_store_no_sugar_drink_3")
class NavStoreNoSugarDrink3ConfigManager(NavStoreItemFridgeConfigManager):
    """
    Variant 1: dual-region, robot in front of obstacle.
    Scene: ONE_WALL_LARGE_3
    """

    def __init__(self, task_name, num_objects=[[4, 1], [0, 1]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.robocasa_scene = "ONE_WALL_LARGE_3"
        self.composite_configs = [
            {
                "seen_object": ["water_bottle_3"],
                "distractor": ["cola_1", "pepsi_3", "lemonade_3", "boxed_drink_0"],
                "fixture_surface": "counter_2_main_group",
                "destination_position": "bottom",
            },
            {
                "seen_container": ["small_fridge", "tray_7"],
                "fixture_surface": "island_counter_island_group",
                "destination_position": "bottom",
            },
        ]
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Help me chill a no-sugar drink option."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("nav_store_no_sugar_drink_3")
class NavStoreNoSugarDrink3Task(NavStoreItemFridgeTask):
    def __init__(self, task_name, robot, **kwargs):

        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [3.0, -4.0, 0.0],
            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)
