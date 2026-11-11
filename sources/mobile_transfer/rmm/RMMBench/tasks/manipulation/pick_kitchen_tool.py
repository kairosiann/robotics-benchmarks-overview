import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("pick_can_opener_0")
class PickCanOpenerConfigManager(Multi_traget_container):
    """
    ConfigManager for pick_kitchen_tool task (KT01).

    Config source: t_config.json
    - seen_object:    [["can_opener_1"]]
    - distractor:     ["canned_food_6", "tongs_0", "bottle_opener_15"]
    - seen_container: ["tray_2"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    - inherited: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[3, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.25, "y_set": 0.05, "direction": "left", "z_set": 0.01},
            {"offset": 0.2, "y_set": 0.05, "direction": "right", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=0,
        workregion_y_set=0.1,
        target_dim=(0.3, 0.25),
        grid_size=[6, 6],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: the target object is placed into its corresponding container and at rest.
        target_entity is a nested list and target_container is a list; they correspond by index.
        """
        conditions_config = dict(
            contain=dict(
                container=target_container[0],
                entities=target_entity[0],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text.
        From the instruction field in t_config.json:
          "Place the can opener on the preparation tray beside the canned food."
        """
        instruction = [
            "I would like to eat the food on the table, please choose a suitable tool and put it on the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_can_opener_0")
class PickCanOpenerTask(PrimitiveTask):
    """
    Task class for pick_kitchen_tool task (KT01).

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
        Expert skill sequence: iterate by class; the outer enumerate(target_entities) determines the current class
        and its corresponding container, while the inner loop visits each object in the class with
        pick → place (corresponding container) → observe; finally the redundant trailing observe is removed and end is appended.
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


@register.add_config_manager("pick_whisk_0")
class PickWhiskConfigManager(PickCanOpenerConfigManager):
    def __init__(self, task_name, num_objects=[4, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = [["whisk_8"]]
        self.distractor = ["egg_10", "spoon_14", "ladle_3", "spatula_6"]
        self.seen_container = ["tray_3"]
        self.robocasa_scene = "ONE_WALL_LARGE_1"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like to cook the food on the table, please choose a suitable tool and put it on the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_whisk_0")
class PickWhiskTask(PickCanOpenerTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("pick_bottle_opener_0")
class PickBottleOpenerConfigManager(PickCanOpenerConfigManager):
    def __init__(self, task_name, num_objects=[5, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = [["bottle_opener_0"]]
        self.distractor = ["beer_9", "can_opener_3", "scissors_10", "tongs_1", "pizza_cutter_5"]
        self.seen_container = ["tray_5"]
        self.robocasa_scene = "ONE_WALL_LARGE_9"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like to drink the beverage on the table, please choose a suitable tool and put it on the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_bottle_opener_0")
class PickBottleOpenerTask(PickCanOpenerTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
