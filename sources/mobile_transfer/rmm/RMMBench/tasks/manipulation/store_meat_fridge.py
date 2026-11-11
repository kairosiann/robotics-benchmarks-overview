import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("store_lamb_chicken_0")
class StoreLambChickenConfigManager(Multi_traget_container):
    """
    ConfigManager for store_meat_fridge task.

    Config source: t_config.json
    - seen_object:    ["lamb_chop_1", "chicken_breast_7"]
    - distractor:     ["beet_7", "tofu_0"]
    - seen_container: ["small_fridge"]
    - robocasa_scene: U_SHAPED_LARGE_2
    - fixture_surface: island_island_group
    - destination_position: bottom
    - robot: position [3.050067173852504, -1.6998841861248737, 0.0], euler [0, 0, -1.57]
    - inherited: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.27, "y_set": 0.2, "direction": "left", "z_set": 0},
            {"offset": 0.2, "y_set": 0.05, "direction": "right", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
            workregion_offset=-0.23,  # positive means leftward
            workregion_y_set=0.13,
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
        Success condition: first open the fridge door, then place all target objects inside the fridge.
        In Multi_traget_container, target_container is a list; take the first element as the detection container.
        Corresponding expert sequence: pick(fridge) → open_door(fridge) → pick/place loop.
        The small_fridge entity class has its own is_open(physics) check (door joint angle > 0.785 rad).
        """
        container = target_container[0] if isinstance(target_container, list) else target_container
        conditions_config = dict(
            asyn_sequence=dict(
                condition_sets=[
                    dict(is_open=dict(container=container)),
                    dict(contain=dict(
                        container=container,
                        entities=target_entity,
                    )),
                ],
                ordered_indices=[0, 1],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text.
        From the instruction field in t_config.json:
          "Put the lamb chop and the chicken breast in the refrigerator."
        """
        instruction = [
            "I would like the lamb chop and the chicken breast stored in the refrigerator."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("store_lamb_chicken_0")
class StoreLambChickenTask(PrimitiveSeqTask):
    """
    Task class for store_meat_fridge task.

    Task flow: pick → place → observe × N → end (multi-target loop)
    Objects that need to be fixed: fridge
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "fridge",
            # "lamb_chop", "chicken_breast", "pork_loin", "bacon", "sausage", "fish",
            # "beet", "tofu", "potato", "dumpling", "carrot", "chili_pepper", "eggplant",
        ]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()


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
        Expert skill sequence: multi-target pick → place → observe loop, followed by end.
        target_entity is a list and target_container is also a list.
        All target objects are placed into the same container.
        """
        target_entities = self.config_manager.target_entity
        container_name = self.target_container[0] if isinstance(self.target_container, list) else self.target_container
        skill_sequence = []
        skill_sequence.extend([
            partial(SkillLib.pick, body_name="small_fridge/handle"),
            partial(SkillLib.open_door, target_container_name=container_name),
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


@register.add_config_manager("store_pork_bacon_0")
class StorePorkBaconConfigManager(StoreLambChickenConfigManager):
    def __init__(self, task_name, num_objects=[3, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["pork_loin_12", "bacon_2"]
        self.distractor = ["potato_17", "dumpling_11", "carrot_3"]
        self.seen_container = ["small_fridge"]
        self.robocasa_scene = "ONE_WALL_LARGE_2"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like the pork loin and the bacon stored in the refrigerator."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("store_pork_bacon_0")
class StorePorkBaconTask(StoreLambChickenTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("store_sausage_fish_0")
class StoreSausageFishConfigManager(StoreLambChickenConfigManager):
    def __init__(self, task_name, num_objects=[4, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["sausage_13", "fish_10"]
        self.distractor = ["chili_pepper_2", "eggplant_1", "tofu_8", "dumpling_4"]
        self.seen_container = ["small_fridge"]
        self.robocasa_scene = "ONE_WALL_LARGE_3"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like the sausage and the fish stored in the refrigerator."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("store_sausage_fish_0")
class StoreSausageFishTask(StoreLambChickenTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
