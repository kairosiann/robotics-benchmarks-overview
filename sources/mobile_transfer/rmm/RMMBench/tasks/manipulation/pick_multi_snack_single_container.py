import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("select_bagged_snacks")
class SelectBaggedSnacksConfigManager(Multi_traget_container):
    """
    ConfigManager for pick_multi_snack_single_container task.

    Config source: t_config.json
    - seen_object: [["bar_11","bar_10","bagged_food_9"],["bagged_food_11","chips_1","bagged_food_7"]]
    - distractor: ["boxed_food_11","canned_food_0"]
    - seen_container: ["tray_7"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    - Inherits: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
                    {"offset": 0.25, "y_set": 0.05, "direction": "left", "z_set": 0.01},  # config of the 1st container
                    {"offset": 0.2, "y_set": 0.05, "direction": "right", "z_set": 0.01},  # config of the 2nd container (offset position)
                    {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},  # config of the 3rd container (offset position)
                ]

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
        """
        Success condition: all target objects are placed inside the container.
        In Multi_traget_container, target_container is a list; take the first element as the checking container.
        target_entity is a list containing all target objects that need to be placed.
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
        """
        Generate the instruction text in natural language style, without exposing concrete operation steps.
        """
        instruction = [
            "I'd like to have all the bagged snacks, can you put them on the tray for me?"
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("select_bagged_snacks")
class SelectBaggedSnacksTask(PrimitiveSeqTask):
    """
    Task class for pick_multi_snack_single_container task.

    Task flow: pick → place → observe × N → end (multi-target loop)
    Objects that need to be fixed: tray, stove
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["tray", "stove"]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)

    def reset_entities_positions(self):
        """
        Height adaptation: adjust the z coordinate based on each object's own height
        to avoid initial penetration/clipping.
        """
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
        Expert skill sequence: multi-target pick → place → observe loop, ending with end.
        target_entity is a list, and target_container is also a list.
        All target objects are placed into the same container.
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


@register.add_config_manager("cluster_bagged&bar_snack")
class ClusterBaggedBarSnackConfigManager(SelectBaggedSnacksConfigManager):
    """
    Multi-target, multi-container clustering task, inherited from SelectBaggedSnacksConfigManager.
    Differences from the parent class: seen_object becomes nested [[],[]], seen_container becomes two,
    and the condition becomes an or condition; the two groups of objects are placed into two trays respectively (one of the two assignment schemes is used).
    """

    def __init__(self, task_name, num_objects=[1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = [["bar_11", "bar_10"], ["bagged_food_11"]]
        self.seen_container = ["tray_1", "tray_7"]
        self.robocasa_scene = "ONE_WALL_LARGE_3"
        return super().get_seen_task_config()

    def get_condition_config(self, target_entity, target_container, **kwargs):
        conditions_config = {
            "or": [
                # Scheme A: entity[0] → container[0], entity[1] → container[1]
                {"contain_1": {"container": target_container[0], "entities": target_entity[0]},
                 "contain_2": {"container": target_container[1], "entities": target_entity[1]}},
                # Scheme B: entity[0] → container[1], entity[1] → container[0]
                {"contain_1": {"container": target_container[1], "entities": target_entity[0]},
                 "contain_2": {"container": target_container[0], "entities": target_entity[1]}},
            ],
        }
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want the bars and bagged foods sorted into two separate trays, can you help me with that?"
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("cluster_bagged&bar_snack")
class ClusterBaggedBarSnackTask(SelectBaggedSnacksTask):
    """
    Multi-target multi-container clustering task, inherited from SelectBaggedSnacksTask.
    Only overrides get_expert_skill_sequence: iterate by class, placing each class of objects into its corresponding container.
    """

    def get_expert_skill_sequence(self, physics):
        target_entities = self.config_manager.target_entity
        target_containers = self.target_container
        skill_sequence = []
        for class_idx, entities in enumerate(target_entities):
            container_name = target_containers[class_idx]
            for entity in entities:
                skill_sequence.extend([
                    partial(SkillLib.pick, target_entity_name=entity),
                    partial(SkillLib.place, target_container_name=container_name),
                    partial(SkillLib.observe),
                ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence
