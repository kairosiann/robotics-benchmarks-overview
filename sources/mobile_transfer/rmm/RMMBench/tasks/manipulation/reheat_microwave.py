import random
from functools import partial

from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("reheat_steak_0")
class ReheatSteakConfigManager(Multi_traget_container):
    """
    ConfigManager for reheat_microwave task.

    Config source: t_config.json
    - seen_object:    ["steak_15"]
    - distractor:     ["steak_3", "pork_chop_1", "steak_5", "lamb_chop_2", "beet_1", "steak_6", "ham_7", "salami_11", "pork_loin_5"]
    - seen_container: ["microwave_1"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [3.050067173852504, -1.6998841861248737, 0.0], euler [0, 0, -1.57]
    - inherited: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.35, "y_set": 0.25, "direction": "left", "z_set": 0},
            {"offset": 0.23, "y_set": 0.05, "direction": "right", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=-0.2,#positive means leftward
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
        Success condition: all target objects are placed inside the microwave.
        target_entity is a list containing all target objects that need to be placed.
        """

        conditions_config = dict(
            asyn_sequence=dict(
                condition_sets=[
                    dict(is_open=dict(container="microwave_1")),
                    dict(contain=dict(
                container="microwave_1",
                entities=target_entity,
                    )),
                ],
                ordered_indices=[0, 1],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text using declarative sentences, without exposing specific operation steps.
        """
        instruction = [
            "I want to eat the steak, please warm it in the microwave."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("reheat_steak_0")
class ReheatSteakTask(PrimitiveSeqTask):
    """
    Task class for reheat_microwave task.

    Task flow: pick → reheat → place → end
    Objects that need to be fixed: plate, microwave
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate", "microwave"]
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
                    height+=0.02
                if "chips" in k:
                    height = 0.015
                entity.init_pos[2] += height


    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: open the microwave → put in the target object → end.
        No door closing or heating is involved; simply placing the object inside the microwave is enough.
        """
        target_entities = self.config_manager.target_entity
        skill_sequence = []
        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name="microwave_1"),
            partial(SkillLib.open_door, target_container_name="microwave_1"),
            partial(SkillLib.observe),
            partial(SkillLib.pick, target_entity_name=target_entities[0]),
            partial(SkillLib.place, target_container_name="microwave_1", place_direction="horizontal", placement_th=0.1),
        ])
        skill_sequence.extend([partial(SkillLib.end)])
        return skill_sequence


# ===== B02 sub-task 1: heat scone in microwave =====
@register.add_config_manager("heat_scone_0")
class HeatSconeConfigManager(ReheatSteakConfigManager):
    """
    B02 sub-task 1: Heat the scone in the microwave and place it on the plate.
    - seen_object:    ["scone_6"]
    - distractor:     ["bread_2", "potato_6"]
    - seen_container: ["microwave_1"]
    - num_objects:    [2, 1]
    """

    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["scone_6"]
        self.distractor = ["bread_2", "potato_6"]
        self.seen_container = ["microwave_1", "plate_3"]
        self.robocasa_scene = "ONE_WALL_LARGE_5"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the scone, please warm it in the microwave."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("heat_scone_0")
class HeatSconeTask(ReheatSteakTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== B02 sub-task 2: heat waffle in microwave =====
@register.add_config_manager("heat_waffle_0")
class HeatWaffleConfigManager(ReheatSteakConfigManager):
    """
    B02 sub-task 2: Heat the waffle in the microwave and place it on the plate.
    - seen_object:    ["waffle_0"]
    - distractor:     ["cake_0", "bread_1", "tofu_10"]
    - seen_container: ["microwave_1"]
    - num_objects:    [3, 1]
    """

    def __init__(self, task_name, num_objects=[3, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["waffle_0"]
        self.distractor = ["cake_0", "bread_1", "tofu_10"]
        self.seen_container = ["microwave_1", "plate_4"]
        self.robocasa_scene = "ONE_WALL_LARGE_6"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the waffle, please warm it in the microwave."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("heat_waffle_0")
class HeatWaffleTask(ReheatSteakTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== B02 sub-task 3: warm baguette in microwave =====
@register.add_config_manager("warm_baguette_0")
class WarmBaguetteConfigManager(ReheatSteakConfigManager):
    """
    B02 sub-task 3: Warm the baguette in the microwave and place it on the plate.
    - seen_object:    ["baguette_1"]
    - distractor:     ["rolling_pin_0", "sausage_0", "carrot_6"]
    - seen_container: ["microwave_1"]
    - num_objects:    [3, 1]
    """

    def __init__(self, task_name, num_objects=[3, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["baguette_1"]
        self.distractor = ["rolling_pin_0", "sausage_0", "carrot_6"]
        self.seen_container = ["microwave_1", "plate_7"]
        self.robocasa_scene = "ONE_WALL_LARGE_7"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the baguette, please warm it in the microwave."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("warm_baguette_0")
class WarmBaguetteTask(ReheatSteakTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== B02 sub-task 4: warm croissant in microwave =====
@register.add_config_manager("warm_croissant_0")
class WarmCroissantConfigManager(ReheatSteakConfigManager):
    """
    B02 sub-task 4: Warm the croissant in the microwave and place it on the plate.
    - seen_object:    ["croissant_5"]
    - distractor:     ["banana_14", "bread_14", "pork_loin_2", "sweet_potato_1"]
    - seen_container: ["microwave_1"]
    - num_objects:    [4, 1]
    """

    def __init__(self, task_name, num_objects=[4, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["croissant_5"]
        self.distractor = ["banana_14", "bread_14", "pork_loin_2", "sweet_potato_1"]
        self.seen_container = ["microwave_1"]
        self.robocasa_scene = "ONE_WALL_LARGE_8"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the croissant, please warm it in the microwave."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("warm_croissant_0")
class WarmCroissantTask(ReheatSteakTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)