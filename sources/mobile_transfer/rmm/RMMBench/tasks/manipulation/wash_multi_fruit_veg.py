import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask, PrimitiveTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("wash_veg_salad")
class WashVegSaladConfigManager(Multi_traget_container):
    """
    ConfigManager for wash_multi_fruit_veg task.

    Config source: t_config.json
    - seen_object:    ["carrot_0", "tomato_2", "cucumber_3"]
    - distractor:     ["bell_pepper_1", "eggplant_4"]
    - seen_container: ["bowl_5"]
    - fixed_fixture:  ["sink_0"]
    - robocasa_scene: U_SHAPED_LARGE_6
    - fixture_surface: island_island_group
    - destination_position: top
    - robot: position [3.050067173852504, -1.6998841861248737, 0.0], euler [0, 0, -1.57]
    - Inherits: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[1, 3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.85, "y_set": 0, "direction": "left", "z_set": -0.01,"orient_offset":[0,0,0]},
            {"offset": 0.2, "y_set": 0.05, "direction": "left", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=-0.55,
        workregion_y_set=0.05,
        target_dim=(0.3, 0.4),
        grid_size=[2, 2],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: each target object is first placed into the sink for washing, and finally placed into the target container.
        In Multi_traget_container, target_container is a list; take the first element as the final container.
        target_entity is a list containing all target objects that need to be washed.
        Each object gets an independent asyn_sequence: sink first → then container.
        """
        container = target_container[0] if isinstance(target_container, list) else target_container
        sink = "sink_0"

        and_conditions = []
        for entity in target_entity:
            and_conditions.append(
                dict(
                    asyn_sequence=dict(
                        condition_sets=[
                        dict(contain=dict(container=sink, entities=[entity])),
                        dict(contain=dict(container=container, entities=[entity])),
                        ],
                        ordered_indices=[0, 1]
                    )
                )
            )

        # The faucet must be open (is_open locks in once satisfied, ANDed with each object's ordered condition)
        and_conditions.append(dict(is_open=dict(container=sink)))

        conditions_config = dict(and_conditions=and_conditions)
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text in declarative style, without exposing concrete operation steps.
        """
        instruction = [
            "I want to make a vegetable salad, please wash the carrot, tomato, and cucumber and put them in the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("wash_veg_salad")
class WashVegSaladTask(PrimitiveSeqTask):
    """
    Task class for wash_multi_fruit_veg task.

    Task flow: pick → wash → place → end
    Objects that need to be fixed: bowl (container placed on the countertop, must be attached to the arena)
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["tray", "sink",
                               #         "carrot_0",
                               # "tomato_2",
                               # "cucumber_3",
                               # "bell_pepper_1",
                               # "eggplant_4",

                               ]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()


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
                if height == 0:
                    height = 0.02
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: open the sink once first, then for each object perform pick → place(sink) → pick → place(container) → observe, ending with end.
        Only one object is in the sink at a time, to ensure grasp success rate.
        """
        target_entities = self.config_manager.target_entity
        container_name = self.target_container[0] if isinstance(self.target_container, list) else self.target_container
        skill_sequence = [
            partial(SkillLib.pick, body_name="sink_0/handle"),
            partial(SkillLib.open_sink, target_entity_name="sink_0"),
            # partial(SkillLib.lift),
            partial(SkillLib.observe),
        ]
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name="sink_0"),
                partial(SkillLib.observe),
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=container_name),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("wash_fruit_plate")
class WashFruitPlateConfigManager(WashVegSaladConfigManager):
    def __init__(self, task_name, num_objects=[2, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["apple_0", "orange_4", "pear_13"]
        self.distractor = ["pomegranate_4", "peach_7", "tomato_8"]
        self.seen_container = ["tray_1"]
        self.fixed_fixture = ["sink_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_1"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the apple, orange, and pear, please wash them and put them on the plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("wash_fruit_plate")
class WashFruitPlateTask(WashVegSaladTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("wash_broccoli_pepper")
class WashBroccoliPepperConfigManager(WashVegSaladConfigManager):
    def __init__(self, task_name, num_objects=[2, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["broccoli_0", "bell_pepper_2"]
        self.distractor = ["cauliflower_0", "cabbage_14", "lettuce_2", "tomato_5"]
        self.seen_container = ["tray_7"]
        self.fixed_fixture = ["sink_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_5"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the broccoli and bell pepper, please wash them and put them in the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("wash_broccoli_pepper")
class WashBroccoliPepperTask(WashVegSaladTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
