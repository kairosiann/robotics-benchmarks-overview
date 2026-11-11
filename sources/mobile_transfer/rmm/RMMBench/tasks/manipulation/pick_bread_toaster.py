import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("select_bread_toaster_0")
class SelectBreadToaster0ConfigManager(BenchTaskConfigManager):
    """
    ConfigManager for pick_bread_toaster task (sub-task 0).

    Config source: t_config.json / sub_config.json
    - seen_object:    ["bread_3"]
    - distractor:     ["bagel_2", "cake_1"]
    - seen_container: ["plate_0"]
    - num_objects:    [2]  (2 distractors)
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    """

    def __init__(self, task_name, num_objects=[2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(
        self,
        workregion_offset=0,
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
            f"I would like the {self.extract_base_name(target_entity)} on the plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("select_bread_toaster_0")
class SelectBreadToaster0Task(PrimitiveTask):
    """
    Task class for pick_bread_toaster sub-task 0.

    Task flow: select bread → place on plate → end
    attach_objects: plate (the container is placed on the countertop), stove
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate", "stove"]
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
                if height == 0:
                    height += 0.02
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        skill_sequence = [
            partial(SkillLib.pick, target_entity_name=target_entity),
            partial(SkillLib.place, target_container_name=self.target_container),
            partial(SkillLib.end),
        ]
        return skill_sequence


# ===== sub-task 1: harder distractors, more objects =====
@register.add_config_manager("select_bread_toaster_1")
class SelectBreadToaster1ConfigManager(SelectBreadToaster0ConfigManager):
    def __init__(self, task_name, num_objects=[3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["bread_9"]
        self.distractor = ["bread_8", "donut_4", "cake_4"]
        self.seen_container = ["plate_1"]
        self.robocasa_scene = "ONE_WALL_LARGE_5"
        return super().get_seen_task_config()


@register.add_task("select_bread_toaster_1")
class SelectBreadToaster1Task(SelectBreadToaster0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== sub-task 2: hardest, most distractors, sliced bread instruction =====
@register.add_config_manager("select_bread_toaster_2")
class SelectBreadToaster2ConfigManager(SelectBreadToaster0ConfigManager):
    def __init__(self, task_name, num_objects=[4], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["bread_3"]
        self.distractor = ["bagel_9", "bread_0", "cake_5", "tofu_4"]
        self.seen_container = ["plate_2"]
        self.robocasa_scene = "ONE_WALL_LARGE_6"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            f"I would like the {self.extract_base_name(target_entity)} for my sandwich on the plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("select_bread_toaster_2")
class SelectBreadToaster2Task(SelectBreadToaster0Task):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
