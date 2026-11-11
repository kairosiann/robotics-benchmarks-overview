import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("classify_chocolate_snacks")
class ClassifyChocolateSnacksConfigManager(Multi_traget_container):
    """
    Multi-target manipulation task: place multiple snacks onto the shelf shelf_1.

    Config source: task_config.json["classify_snacks_on_shelf"]
    - seen_object: ["bagged_food_0", "bar_0", "boxed_food_0"] (flat list; the parent class samples num_objects[1] items from it as target_entity)
    - seen_container: ["shelf_1"] (list; the parent class uses the whole list as target_container)
    - robocasa_scene: U_SHAPED_LARGE_1
    - fixture_surface: island_island_group
    - destination_position: bottom
    - Inheritance: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0, "y_set": 0.4, "direction": "top", "z_set": 0.03},
            {"offset": 0.18, "y_set": -0.03, "direction": "right", "z_set": 0.01},
            {"offset": 0.25, "y_set": 0.1, "direction": "left", "z_set": 0.04, "orient_offset": [0, 0, 3.14]},
        ]

    def get_object_info(self, workregion_offset=0, workregion_y_set=0.1,
                        target_dim=(0.6, 0.05), grid_size=[1, 6]):
        super().get_object_info(workregion_offset, workregion_y_set,
                                target_dim=target_dim, grid_size=grid_size)

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success conditions: all target objects placed inside the container and at rest.
        In Multi_traget_container, target_container is a list; take the first element as the checking container;
        target_entity itself is a list and is passed in directly.
        """
        container = target_container[0] if isinstance(target_container, list) else target_container
        conditions_config = dict(
            contain=dict(
                container=container,
                entities=target_entity,
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Put chocolate-related snacks on the first layer and other snacks on the second layer."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("classify_chocolate_snacks")
class ClassifyChocolateSnacksTask(PrimitiveTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["sink","stove","shelf"]

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
                if "chips" in k:
                    height = 0.015
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: multi-target pick → place → observe loop, then end.
        target_entity is a list and target_container is also a list; take target_container[0] as the placement container.
        """
        target_entities = self.config_manager.target_entity
        container_name = self.target_container[0] if isinstance(self.target_container, list) else self.target_container
        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=container_name),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence
