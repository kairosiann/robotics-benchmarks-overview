import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("pick_non_alcoholic_drink")
class PickNonAlcoholicDrinkConfigManager(BenchTaskConfigManager):
    """
    ConfigManager for pick_drink_choice_no_fridge task (BV02, no fridge).

    Config source: t_config.json
    - seen_object:    ["water_bottle_2"]
    - distractor:     ["beer_5", "wine_2"]
    - seen_container: ["tray_3"]
    - robocasa_scene: ONE_WALL_LARGE_9
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    - inherited: BenchTaskConfigManager (target_entity is a str, target_container is a str)
    """

    def __init__(self, task_name, num_objects=[2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(
        self,
        workregion_offset=0,
        workregion_y_set=0.1,
        target_dim=(0.3, 0.25),
        grid_size=[8, 8],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def load_containers(self, target_container, offset=0.25, y_set=0.05, direction="left"):
        if target_container is not None:
            if self.work_info and self.target_container:
                container_info = self.get_container_info_from_workregion(
                    self.work_info,
                    anchor=self.destination_position,
                    offset=offset,
                    y_set=y_set,
                    direction=direction,
                )
                container_config = self.get_entity_config(
                    target_container,
                    position=container_info["position"],
                    orientation=container_info["orientation"],
                )
                self.config["task"]["components"].append(container_config)

    def get_condition_config(self, target_entity, target_container, **kwargs):
        conditions_config = dict(
            contain=dict(
                container=target_container,
                entities=[target_entity],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I am driving tonight, please recommend a drink for me on the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_non_alcoholic_drink")
class PickNonAlcoholicDrinkTask(PrimitiveTask):
    """
    Task class for pick_drink_choice_no_fridge task.

    Task flow: pick → place → end
    Objects that need to be fixed: tray
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "tray",  # container
            "water_bottle", "beer", "wine", "boxed_drink", "alcohol", "cola", "pepsi", "lemonade",  # beverage items
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
                if any(obj in k for obj in ["water_bottle_0", "water_bottle_2", "water_bottle_3"]):
                    height += 0.03


                if "cola_1" in k:
                    height += 0.03
                if "pepsi" in k:
                    height -= 0.02
                if "boxed" in k:
                    height -= 0.01

                if any(obj in k for obj in ["wine"]):
                    height -= 0.03
                if any(obj in k for obj in ["beer"]):
                    height -= 0.01
                if "fridge" in k:
                    height -= 0.03
                if height == 0:
                    height += 0.03
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        skill_sequence = [
            partial(SkillLib.pick, target_entity_name=target_entity),
            partial(SkillLib.place, target_container_name=self.target_container),
            partial(SkillLib.end),
        ]
        return skill_sequence


# ===== BV02 sub-task 2: child drink =====
@register.add_config_manager("pick_child_drink")
class PickChildDrinkConfigManager(PickNonAlcoholicDrinkConfigManager):
    """
    BV02 sub-task 2: Choose a suitable drink for a child.
    - seen_object:    ["boxed_drink_2"]
    - distractor:     ["beer_11", "wine_9", "alcohol_7"]
    - seen_container: ["tray_4"]
    - num_objects:    [3]
    """

    def __init__(self, task_name, num_objects=[3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["boxed_drink_2"]
        self.distractor = ["beer_11", "wine_9", "alcohol_7"]
        self.seen_container = ["tray_4"]
        self.robocasa_scene = "ONE_WALL_LARGE_2"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "Choose a suitable drink for a child."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_child_drink")
class PickChildDrinkTask(PickNonAlcoholicDrinkTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== BV02 sub-task 3: no sugar drink =====
@register.add_config_manager("pick_no_sugar_drink")
class PickNoSugarDrinkConfigManager(PickNonAlcoholicDrinkConfigManager):
    """
    BV02 sub-task 3: Avoid sugary drinks.
    - seen_object:    ["water_bottle_3"]
    - distractor:     ["cola_1", "pepsi_3", "lemonade_3", "boxed_drink_0"]
    - seen_container: ["tray_5"]
    - num_objects:    [4]
    """

    def __init__(self, task_name, num_objects=[4], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["water_bottle_3"]
        self.distractor = ["cola_1", "pepsi_3", "lemonade_3", "boxed_drink_0"]
        self.seen_container = ["tray_5"]
        self.robocasa_scene = "ONE_WALL_LARGE_5"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I'm trying to avoid sugary drinks. Bring me a suitable option."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_no_sugar_drink")
class PickNoSugarDrinkTask(PickNonAlcoholicDrinkTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
