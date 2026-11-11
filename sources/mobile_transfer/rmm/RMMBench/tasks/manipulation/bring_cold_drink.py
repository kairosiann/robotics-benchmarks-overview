import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("bring_cold_water")
class BringColdWaterConfigManager(Multi_traget_container):
    """
    ConfigManager for bring_cold_drink task (BV01).

    Config source: t_config.json
    - seen_object:    ["water_bottle_0"]
    - distractor:     ["water_bottle_1", "bottled_cola_0"]
    - mid_container:  [{"small_fridge": ["water_bottle_0", "bottled_cola_0"]}]
    - seen_container: ["tray_0"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    - inherited: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.06, "y_set": -0.05, "direction": "right", "z_set": -0.03},
            {"offset": 0.2, "y_set": 0.05, "direction": "left", "z_set": 0},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=-0.05,
        workregion_y_set=0.3,
        target_dim=(0.8, 0.2),#[x,y]
        grid_size=[1, 2],#[y,x]
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: first open the fridge door, then place all target objects on the tray and keep them at rest.
        asyn_sequence + ordered_indices=[0, 1] enforces the stage order:
            Stage 0: is_open(small_fridge) —— the fridge door is opened
            Stage 1: contain([water_bottle_0], tray) —— the target objects are placed on the tray
        Stage 1 stays locked before Stage 0 completes; it is neither scored nor marked as done.
        """
        container = target_container[0] if isinstance(target_container, list) else target_container
        mid_container = list(self.mid_container[0].keys())[0]
        conditions_config = dict(
            asyn_sequence=dict(
                condition_sets=[
                    dict(
                        is_open=dict(container=mid_container),
                    ),
                    dict(
                        contain=dict(
                            container=container,
                            entities=target_entity,
                        ),
                    ),
                ],
                ordered_indices=[0, 1],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text.
        From the instruction field in t_config.json:
          "Bring me a cold bottle of water."
        """
        instruction = [
            "I would like a cold bottle of water."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("bring_cold_water")
class BringColdWaterTask(PrimitiveSeqTask):
    """
    Task class for bring_cold_drink task.

    Task flow: pick from fridge → place to tray → observe × N → end (multi-target loop)
    Objects that need to be fixed: small_fridge, tray
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "fridge", "tray",
            # "water_bottle_0","water_bottle_1",
            #         "bottled_cola_0",      "water_bottle_0",
            #                 "bottled_cola_0"

        ]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)

    def reset_entities_positions(self):
        """
        Height adaptation: adjust the z coordinate according to each object's own height
        to avoid initial penetration/clipping.
        """
        if self.config_manager.all_entities is not None:
            entities = self.config_manager.all_entities
            for k in entities:
                entity = self.entities.get(k)
                if entity is None:
                    continue
                height = entity.get_placement_height()
                if any(obj in k for obj in ["water_bottle_0","water_bottle_2" ,"water_bottle_3"]):
                    height+=0.06

                if "water_bottle_1" in k:
                    height+=0.04
                if "cola_1" in k:
                    height+=0.05
                if "pepsi" in k:
                    height-=0.023
                if height == 0:
                    height += 0.02
                if any(obj in k for obj in ["wine"]):
                    height-=0.03
                if any(obj in k for obj in ["beer"]):
                    height-=0.01
                if "fridge" in k:
                    height-=0.03
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: multi-target pick → place → observe loop, followed by end.
        target_entity is a list and target_container is also a list.
        All target objects are placed into the same container.
        """
        target_entities = self.config_manager.target_entity
        container_name = self.target_container[0] if isinstance(self.target_container, list) else self.target_container
        mid_container = list(self.config_manager.mid_container[0].keys())[0]
        skill_sequence = []

        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name=mid_container),
            partial(SkillLib.open_door, target_container_name=mid_container),
            partial(SkillLib.observe),
        ])
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=container_name),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("bring_cold_milk")
class BringColdMilkConfigManager(BringColdWaterConfigManager):
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["milk_9"]
        self.distractor = ["milk_10", "boxed_drink_1"]
        self.mid_container = [
            {
                "small_fridge": [
                    "milk_9",
                    "boxed_drink_1",
                ]
            }
        ]
        self.seen_container = ["tray_1"]
        self.robocasa_scene = "ONE_WALL_LARGE_4"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like some cold milk for breakfast."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("bring_cold_milk")
class BringColdMilkTask(BringColdWaterTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("bring_cold_boxed_drink")
class BringColdBoxedDrinkConfigManager(BringColdWaterConfigManager):
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["boxed_drink_3"]
        self.distractor = ["juice_0", "milk_1"]
        self.mid_container = [
            {
                "small_fridge": [
                    "boxed_drink_3",
                    "milk_1",
                ]
            }
        ]
        self.seen_container = ["tray_2"]
        self.robocasa_scene = "ONE_WALL_LARGE_7"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like a cold boxed fruit drink."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("bring_cold_boxed_drink")
class BringColdBoxedDrinkTask(BringColdWaterTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ==================== BV02: drink choice tasks ====================

@register.add_config_manager("bring_non_alcoholic_drink")
class BringNonAlcoholicDrinkConfigManager(BringColdWaterConfigManager):
    """
    BV02-1: Fetch a non-alcoholic drink from the fridge.
    Inherits BringColdWaterConfigManager, num_objects stays [2, 1].
    - seen_object:    ["water_bottle_2"]
    - distractor:     ["beer_5", "wine_2"]
    - mid_container:  [{"small_fridge": ["water_bottle_2", "beer_5"]}]
    - seen_container: ["tray_3"]
    """
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["water_bottle_2"]
        self.distractor = ["beer_5", "wine_2"]
        self.mid_container = [
            {
                "small_fridge": [
                    "water_bottle_2",
                    "beer_5"
                ]
            }
        ]
        self.seen_container = ["tray_3"]
        self.robocasa_scene = "ONE_WALL_LARGE_8"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I am driving tonight, so I would like a non-alcoholic drink."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("bring_non_alcoholic_drink")
class BringNonAlcoholicDrinkTask(BringColdWaterTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("bring_child_drink")
class BringChildDrinkConfigManager(BringColdWaterConfigManager):
    """
    BV02-2: Fetch a drink suitable for a child from the fridge.
    Inherits BringColdWaterConfigManager, num_objects stays [2, 1].
    - seen_object:    ["boxed_drink_2"]
    - distractor:     ["beer_11", "wine_9"]
    - mid_container:  [{"small_fridge": ["boxed_drink_2", "beer_11"]}]
    - seen_container: ["tray_4"]
    """
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["boxed_drink_2"]
        self.distractor = ["beer_11", "wine_9"]
        self.mid_container = [
            {
                "small_fridge": [
                    "boxed_drink_2",
                    "beer_11"
                ]
            }
        ]
        self.seen_container = ["tray_1"]
        self.robocasa_scene = "ONE_WALL_LARGE_0"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like a suitable drink for a child."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("bring_child_drink")
class BringChildDrinkTask(BringColdWaterTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("bring_no_sugar_drink")
class BringNoSugarDrinkConfigManager(BringColdWaterConfigManager):
    """
    BV02-3: Fetch a sugar-free drink from the fridge.
    Inherits BringColdWaterConfigManager, num_objects stays [2, 1].
    - seen_object:    ["water_bottle_3"]
    - distractor:     ["cola_1", "pepsi_3"]
    - mid_container:  [{"small_fridge": ["water_bottle_3", "cola_1"]}]
    - seen_container: ["tray_5"]
    """
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["water_bottle_3"]
        self.distractor = ["cola_1", "pepsi_3"]
        self.mid_container = [
            {
                "small_fridge": [
                    "water_bottle_3",
                    "cola_1"
                ]
            }
        ]
        self.seen_container = ["tray_7"]
        self.robocasa_scene = "ONE_WALL_LARGE_9"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I am trying to avoid sugary drinks, so I would like a suitable option."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("bring_no_sugar_drink")
class BringNoSugarDrinkTask(BringColdWaterTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
