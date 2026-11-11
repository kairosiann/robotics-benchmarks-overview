import random
from functools import partial

import numpy as np

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("store_non_alcoholic_drink")
class StoreNonAlcoholicDrinkConfigManager(BenchTaskConfigManager):
    """
    ConfigManager for store_item_fridge task (BV02, put items into fridge).

    Config source: t_config.json
    - seen_object:    ["water_bottle_2"]
    - distractor:     ["beer_5", "wine_2"]
    - seen_container: ["small_fridge"]
    - robocasa_scene: ONE_WALL_LARGE_9
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    - Inheritance: BenchTaskConfigManager (target_entity is str, target_container is str)
    """

    def __init__(self, task_name, num_objects=[2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(
        self,
        workregion_offset=-0.3,
        workregion_y_set=0.1,
        target_dim=(0.3, 0.25),
        grid_size=[10, 10],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def load_containers(self, target_container,offset=0.3,y_set = 0.05,direction="left",z_set=-0.03,orient_offset=[0,0,0]):
        super().load_containers(target_container,offset,y_set,direction,z_set,orient_offset)

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success conditions: first open the fridge door, then place the target object into the fridge.
        In BenchTaskConfigManager both target_entity / target_container are str.
        Corresponding expert sequence: pick(fridge) → open_door(fridge) → pick(target) → place(fridge).
        The small_fridge entity class has a built-in is_open(physics) check (door joint angle > 0.785 rad).
        """
        conditions_config = dict(
            asyn_sequence=dict(
                condition_sets=[
                    dict(is_open=dict(container=target_container)),
                    dict(contain=dict(
                        container=target_container,
                        entities=[target_entity],
                    )),
                ],
                ordered_indices=[0, 1],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like the non-alcoholic drink chilled."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("store_non_alcoholic_drink")
class StoreNonAlcoholicDrinkTask(PrimitiveSeqTask):
    """
    Task class for store_item_fridge task.

    Task flow: pick → place(fridge) → end
    Objects that need to be fixed: fridge
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "fridge",  # container
            # "water_bottle", "boxed_drink",  # target objects
            # "beer", "wine", "alcohol", "cola", "pepsi", "lemonade",  # distractors
        ]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def reset_entities_positions(self):
        if self.config_manager.all_entities is not None:
            entities = self.config_manager.all_entities
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
                elif any(d in k for d in ["cola_1",  "lemonade_3"]):
                    height += 0.03
                elif height == 0:
                    height += 0.01
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        container_name = self.target_container
        print(f"{container_name}/handle")

        skill_sequence = [
            partial(SkillLib.pick, body_name=f"{container_name}/handle"),
            partial(SkillLib.open_door, target_container_name=container_name),
            partial(SkillLib.observe),
            partial(SkillLib.pick, target_entity_name=target_entity),
            partial(SkillLib.place, target_container_name=container_name),
            partial(SkillLib.end),
        ]
        return skill_sequence


# ===== BV02 sub-task 2: child drink =====
@register.add_config_manager("store_child_drink")
class StoreChildDrinkConfigManager(StoreNonAlcoholicDrinkConfigManager):
    """
    BV02 sub-task 2: Chill a suitable drink for a child.
    - seen_object:    ["boxed_drink_2"]
    - distractor:     ["beer_11", "wine_9", "alcohol_7"]
    - seen_container: ["small_fridge"]
    - num_objects:    [3]
    """

    def __init__(self, task_name, num_objects=[3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["boxed_drink_2"]
        self.distractor = ["beer_11", "wine_9", "alcohol_7"]
        self.seen_container = ["small_fridge"]
        self.robocasa_scene = "ONE_WALL_LARGE_3"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like a suitable drink for a child chilled."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("store_child_drink")
class StoreChildDrinkTask(StoreNonAlcoholicDrinkTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== BV02 sub-task 3: no sugar drink =====
@register.add_config_manager("store_no_sugar_drink")
class StoreNoSugarDrinkConfigManager(StoreNonAlcoholicDrinkConfigManager):
    """
    BV02 sub-task 3: Chill a no-sugar drink.
    - seen_object:    ["water_bottle_3"]
    - distractor:     ["cola_1", "pepsi_3", "lemonade_3", "boxed_drink_0"]
    - seen_container: ["small_fridge"]
    - num_objects:    [4]
    """

    def __init__(self, task_name, num_objects=[3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["water_bottle_3"]
        self.distractor = ["cola_1", "lemonade_3",  "boxed_drink_0"]#
        self.seen_container = ["small_fridge"]
        self.robocasa_scene = "ONE_WALL_LARGE_4"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like a no-sugar drink option chilled."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("store_no_sugar_drink")
class StoreNoSugarDrinkTask(StoreNonAlcoholicDrinkTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
