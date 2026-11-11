import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask, PrimitiveTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("wash_place_carrot")
class WashPlaceCarrotConfigManager(Multi_traget_container):
    """
    ConfigManager for wash_fruit_veg task.

    Config source: t_config.json
    - seen_object:    ["carrot_1"]
    - distractor:     ["radish_6", "cucumber_2"]
    - seen_container: ["plate_0"]
    - fixed_fixture:  ["sink_0"]
    - robocasa_scene: U_SHAPED_LARGE_6
    - fixture_surface: island_island_group
    - destination_position: top
    - robot: position [3.200067173852504, -3.800115813660509, 0.0], euler [0, 0, -1.57]
    - Inherits: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0 ,"y_set": 0.21, "direction": "top", "z_set": -0.01},
            {"offset": 0.2, "y_set": 0.05, "direction": "right", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "left", "z_set": 0.01},
        ]

    def get_object_info(
        self,
            workregion_offset=-0.52,
            workregion_y_set=0.1,
            target_dim=(0.3, 0.1),  # xy
            grid_size=[2, 3],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: the target object is first placed into the sink for washing, and finally placed into the target container.
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
            "I want to eat the carrot, please wash it and put it on the plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("wash_place_carrot")
class WashPlaceCarrotTask(PrimitiveSeqTask):
    """
    Task class for wash_fruit_veg task.

    Task flow: pick → wash → place → end
    Objects that need to be fixed: plate (container placed on the countertop, must be attached to the arena)
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate","sink","bowl","tray"]
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
                if height==0:
                    height=0.02
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


@register.add_config_manager("wash_place_apple")
class WashPlaceAppleConfigManager(WashPlaceCarrotConfigManager):
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(
            self,
            workregion_offset=-0.52,
            workregion_y_set=0.1,
            target_dim=(0.3, 0.15),  # xy
            grid_size=[2, 3],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_seen_task_config(self):
        self.seen_object = ["apple_22"]
        self.distractor = ["pear_10", "peach_3", "pomegranate_1"]
        self.seen_container = ["bowl_2"]
        self.fixed_fixture = ["sink_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_5"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the apple, please wash it and put it on the bowl."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("wash_place_apple")
class WashPlaceAppleTask(WashPlaceCarrotTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("wash_place_cucumber")
class WashPlaceCucumberConfigManager(WashPlaceCarrotConfigManager):
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0, "y_set": 0.25, "direction": "top", "z_set": -0.01,"orient_offset":[0,0,1.57]}
        ]

    def get_seen_task_config(self):
        self.seen_object = ["cucumber_2"]
        self.distractor = ["zucchini_7", "eggplant_1", "carrot_4", "bell_pepper_3"]
        self.seen_container = ["tray_7"]
        self.fixed_fixture = ["sink_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_6"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the cucumber, please wash it and put it in the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("wash_place_cucumber")
class WashPlaceCucumberTask(WashPlaceCarrotTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
