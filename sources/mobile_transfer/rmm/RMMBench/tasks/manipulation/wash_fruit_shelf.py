import random
from functools import partial

import numpy as np

from RMMBench.tasks.base_task import PrimitiveSeqTask,PrimitiveTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("wash_fruit_from_shelf")
class WashFruitFromShelfConfigManager(Multi_traget_container):
    """
    ConfigManager for wash_fruit_shelf task (FV07).

    Config source: t_config.json
    - seen_object:    ["apple_22", "orange_12"]
    - distractor:     ["tomato_5", "pomegranate_4"]
    - mid_container:  [{"table_shelf_4": ["orange_12", "apple_22"]}]
    - seen_container: ["tray_7"]
    - fixed_fixture:  ["sink_0"]
    - robocasa_scene: U_SHAPED_LARGE_6
    - fixture_surface: island_island_group
    - destination_position: top
    - robot: position [3.050067173852504, -1.6998841861248737, 0.0], euler [0, 0, -1.57]
    - Inherits: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.86, "y_set": 0.08, "direction": "left", "z_set": -0.01},
            {"offset": 0.04, "y_set": 0.2, "direction": "top", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "right", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=-0.52,
        workregion_y_set=0.05,
        target_dim=(0.3, 0.1),#xy
        grid_size=[1, 2],#yx
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def load_containers(self, target_container, offset=0.3, y_set=0.1, direction="left", z_set=0,
                        orient_offset=[0, 0, 0]):
        if target_container is not None:
            if self.work_info and self.target_container:
                container_info = self.get_container_info_from_workregion(self.work_info,
                                                                         anchor=self.destination_position,
                                                                         offset=offset,
                                                                         y_set=y_set,
                                                                         z_set=z_set,
                                                                         direction=direction
                                                                         )
                container_config = self.get_entity_config(target_container,
                                                          position=container_info["position"],
                                                          orientation=np.array(
                                                              container_info["orientation"]) + orient_offset, )

                for parent, children in self.container_mapping.items():
                    if parent == target_container:

                        container_config["subentities"] = []
                        for j, child in enumerate(children):
                            child_config = self.get_entity_config(child,
                                                                  position=[0.09+j * 0.1 - 0.05 * (len(children) - 1), 0, 0],
                                                                  orientation=[0, 0, 0])
                            container_config["subentities"].append(child_config)

                self.config["task"]["components"].append(container_config)

            else:
                container_config = self.get_entity_config(target_container)
                self.config["task"]["components"].append(container_config)

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: each fruit is first placed into the sink for washing, and finally placed onto the tray and at rest.
        In Multi_traget_container, target_container is a list; take the first element as the final container (tray).
        target_entity is a list containing all target fruits that need to be washed.
        Each fruit gets an independent asyn_sequence: sink first → then tray, with fruits not interfering with each other.
        """
        tray = target_container[0] if isinstance(target_container, list) else target_container
        sink = "sink_0"  # fixed sink name

        # Build an independent asyn_sequence condition for each fruit
        and_conditions = []
        for entity in target_entity:
            and_conditions.append(
                dict(
                    asyn_sequence=dict(
                        condition_sets=[
                            dict(contain=dict(container=sink, entities=[entity])),
                            dict(contain=dict(container=tray, entities=[entity])),
                        ],
                        ordered_indices=[0, 1]
                    )
                )
            )

        and_conditions.append(dict(is_open=dict(container=sink)))

        conditions_config = dict(and_conditions=and_conditions)
        self.config["task"]["conditions"] = conditions_config


    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text.
        From the instruction field in t_config.json:
          "The fruit on the table shelf has not been washed. Wash every piece of fruit and return all of them to the tray."
        """
        instruction = [
            "The fruit on the table shelf has not been washed. Wash every piece of fruit and return all of them to the tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("wash_fruit_from_shelf")
class WashFruitFromShelfTask(PrimitiveSeqTask):
    """
    Task class for wash_fruit_shelf task.

    Task flow: pick from shelf → wash → place → end
    Objects that need to be fixed: tray (container placed on the countertop, must be attached to the arena)
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["tray", "sink","table_shelf_4"]
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
                if height == 0:
                    height = 0.02
                for obj in ["orange","apple"]:
                    if obj in k:
                        height+=0.012
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: multi-target pick → wash → place → observe loop, ending with end.
        target_entity is a list, and target_container is also a list.
        All target objects are placed into the same container.
        """
        target_entities = self.config_manager.target_entity
        container_name = self.target_container[0] if isinstance(self.target_container, list) else self.target_container

        skill_sequence = []
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name="sink_0"),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([
            partial(SkillLib.pick, body_name="sink_0/handle"),
            partial(SkillLib.open_sink, target_entity_name="sink_0"),
            # partial(SkillLib.lift),

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
