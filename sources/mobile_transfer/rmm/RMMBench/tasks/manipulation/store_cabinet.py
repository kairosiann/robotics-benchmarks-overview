import random
from functools import partial

import numpy as np

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("store_yogurt")
class StoreYogurtConfigManager(BenchTaskConfigManager):
    """
    Single-target storing task: put yogurt_1 away into the cabinet counter_0.

    Config source: task_config.json["store_cabinet"]
    - seen_object:    ["yogurt_1"] (the original requirement says "yogurt", but "yogurt" is not registered
                       in name2class_xml; only "yogurt_1"/"yogurt_2" exist, so "yogurt_1" is used)
    - distractor:     ["hamburger", "scone"], with num_objects=[2] all used as distractors placed on the countertop
    - seen_container: ["counter_0"] (cabinet body, following the proven usage in test_1.py)
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - Inheritance: BenchTaskConfigManager (both target_entity / target_container are str)
    """

    def __init__(self, task_name, num_objects=[1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(self, workregion_offset=0, workregion_y_set=0.1,
                        target_dim=(0.2, 0.3), grid_size=[4, 1]):
        """Overrides the workregion parameters, following pick_snack_single.py."""
        super().get_object_info(workregion_offset, workregion_y_set,
                                target_dim=target_dim, grid_size=grid_size)

    def load_containers(self, target_container, offset=0.4, y_set=0.5,
                        direction="left", z_set=0.1, orient_offset=[0, 0, 0]):
        """
        Overrides the container placement parameters.
        The counter_0 cabinet placement parameters (offset/z_set/orient_offset) follow the proven
        configuration where counter_0 is used as a container in test_1.py.
        """
        if target_container is not None:
            if self.work_info and self.target_container:
                container_info = self.get_container_info_from_workregion(
                    self.work_info,
                    anchor=self.destination_position,
                    offset=offset,
                    y_set=y_set,
                    z_set=z_set,
                    direction=direction,
                )
                container_config = self.get_entity_config(
                    target_container,
                    position=[container_info["position"][0],
                              container_info["position"][1],
                              container_info["position"][2]],
                    orientation=np.array(container_info["orientation"]) + orient_offset,
                )
                self.config["task"]["components"].append(container_config)
            else:
                container_config = self.get_entity_config(target_container)
                self.config["task"]["components"].append(container_config)

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success conditions (ordered constraint):
        Stage 0: the cabinet counter_0 is pulled open (is_open, locked in permanently once satisfied; closing the door afterwards does not revert it)
        Stage 1: the yogurt is placed inside the cabinet and at rest (contain_v); the check is only unlocked after is_open is satisfied
        Both target_entity / target_container are str; entities must be wrapped in a list.
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
        instruction = ["Put the yogurt away into the cabinet."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("store_yogurt")
class StoreYogurtTask(PrimitiveSeqTask):
    """
    Task flow: open the cabinet door (pull) → pick(yogurt_1) → place(counter_0) → close the cabinet door (push) → end
    The success condition is asyn_sequence (is_open → contain_v), hence it inherits PrimitiveSeqTask.
    Objects that need to be fixed: counter (the cabinet body is a component and must be attached to the arena)
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "counter",  # container
            # "yogurt",  # target object
            # "hamburger", "scone",  # distractors
        ]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def reset_entities_positions(self):
        """Height adaptation: adjust the z coordinate according to each object's own height to avoid initial interpenetration."""
        if self.config_manager.all_entities is not None:
            entities = self.config_manager.all_entities
            for k in entities:
                entity = self.entities.get(k)
                if entity is None:
                    continue
                height = entity.get_placement_height()
                if height == 0.0:
                    height+=0.02
                if "yogurt" in k:
                    height-=0.01

                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: pick → place → end
        target_entity is a single str, passed directly to SkillLib.pick.
        """
        target_entity = self.config_manager.target_entity
        skill_sequence = [
            partial(SkillLib.pick, body_name="counter_0/door_handle_main"),
            partial(SkillLib.pull),
            partial(SkillLib.observe),
            partial(SkillLib.pick, target_entity_name=target_entity),
            partial(SkillLib.place, target_container_name=self.target_container),
            partial(SkillLib.observe),
            partial(SkillLib.pick, body_name="counter_0/door_handle_main"),
            partial(SkillLib.push),
            partial(SkillLib.end),
        ]
        return skill_sequence
