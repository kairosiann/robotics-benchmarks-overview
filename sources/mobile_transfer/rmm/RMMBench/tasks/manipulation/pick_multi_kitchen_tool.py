import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("pick_can_opener_bottle_opener_0")
class PickCanOpenerBottleOpenerConfigManager(Multi_traget_container):
    """
    ConfigManager for pick_multi_kitchen_tool task (KT02).

    Config source: t_config.json
    - seen_object:    [["can_opener_2"], ["bottle_opener_1"]]
    - distractor:     ["canned_food_3", "beer_2", "scissors_0", "tongs_3"]
    - seen_container: ["tray_0", "tray_1"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    - inherited: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[4, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.28, "y_set": 0.05, "direction": "left", "z_set": 0.01},
            {"offset": 0.28, "y_set": 0.05, "direction": "right", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=0,
        workregion_y_set=0.18,
        target_dim=(0.3, 0.3),
        grid_size=[10, 10],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: each class of target objects is placed into its corresponding container and at rest.
        target_entity is a nested list and target_container is a list; they correspond by index.
        """
        conditions_config = {
            "or": [
                {
                    "contain_1": {"container": target_container[0], "entities": target_entity[0]},
                    "contain_2": {"container": target_container[1], "entities": target_entity[1]},
                },
                {
                    "contain_1": {"container": target_container[0], "entities": target_entity[1]},
                    "contain_2": {"container": target_container[1], "entities": target_entity[0]},
                },
            ]
        }
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text.
        From the instruction field in t_config.json:
          "Place the can opener on the tray beside the canned food and the bottle opener on the tray beside the beer bottle."
        """
        instruction = [
            "I would like to eat the canned food and drink the beer, please put the suitable tools on the trays beside them respectively."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_can_opener_bottle_opener_0")
class PickCanOpenerBottleOpenerTask(PrimitiveSeqTask):
    """
    Task class for pick_multi_kitchen_tool task (KT02).

    Task flow: pick → place → observe loop (iterate by class), followed by end
    Objects that need to be fixed: tray
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["tray"]
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
                if height == 0:
                    height += 0.02
                if "chips" in k:
                    height = 0.015
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: iterate over each class; the outer enumerate(target_entities) determines
        the current class and its corresponding container, and the inner loop iterates over each object
        in that class with pick → place(corresponding container) → observe; finally strip the trailing
        redundant observe and append end.
        """
        target_entities = self.config_manager.target_entity
        skill_sequence = []
        for idx, entity_group in enumerate(target_entities):
            container_name = self.target_container[idx] if isinstance(self.target_container, list) else self.target_container
            for entity in entity_group:
                skill_sequence.extend([
                    partial(SkillLib.pick, target_entity_name=entity),
                    partial(SkillLib.place, target_container_name=container_name),
                    partial(SkillLib.observe),
                ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("pick_whisk_knife_0")
class PickWhiskKnifeConfigManager(PickCanOpenerBottleOpenerConfigManager):
    def __init__(self, task_name, num_objects=[3, 2], **kwargs):
        self.robocasa_scene = "ONE_WALL_LARGE_9",
        super().__init__(task_name, num_objects, **kwargs)


    def get_seen_task_config(self):
        self.seen_object = [["whisk_0"], ["knife_24"]]
        self.distractor = ["egg_6", "cheese_3", "spoon_5", "spatula_0", "rolling_pin_1"]
        self.seen_container = ["tray_4", "tray_7"]

        self.robocasa_scene = "ONE_WALL_LARGE_5"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like to cook the egg and cut the cheese, please put the suitable tools on the trays beside them respectively."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_whisk_knife_0")
class PickWhiskKnifeTask(PickCanOpenerBottleOpenerTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("pick_spatula_ladle_0")
class PickSpatulaLadleConfigManager(PickCanOpenerBottleOpenerConfigManager):
    def __init__(self, task_name, num_objects=[4, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = [["spatula_3"], ["ladle_8"]]
        self.distractor = ["fork_11", "tongs_4", "whisk_5", "scissors_8"]
        self.seen_container = ["tray_9", "tray_10"]
        self.robocasa_scene = "ONE_WALL_LARGE_6"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like to fry the food and serve the soup, please put the suitable tools on the trays beside them respectively."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_spatula_ladle_0")
class PickSpatulaLadleTask(PickCanOpenerBottleOpenerTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
