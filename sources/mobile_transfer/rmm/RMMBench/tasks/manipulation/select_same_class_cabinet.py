import random
from functools import partial

import numpy as np

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("select_same_cake")
class SelectSameCakeConfigManager(BenchTaskConfigManager):
    """
    Same-category selection task: a reference object (cake_9, placed inside the cabinet via the
    mid_container mapping) is already stored in the cabinet counter_0; on the countertop there is
    a same-category target (cake_0) and different-category distractors (scone_0, jello_cup_0).
    The robot needs to pick the same-category object and put it into the cabinet.

    Config source: task_config.json["select_same_class_cabinet"] (class 1)
    - seen_object:    ["cake_0"], sample 1 as target_entity
    - distractor:     ["cake_9", "scone_0", "jello_cup_0"], num_objects=[2] samples 2 onto the countertop
    - mid_container:  [{"counter_0": ["cake_9"]}], counter_0 is in seen_container,
                      so it goes through container_mapping and cake_9 is placed inside the cabinet as a subentity
    - seen_container: ["counter_0"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - Inheritance: BenchTaskConfigManager (both target_entity / target_container are str)
    """

    def __init__(self, task_name, num_objects=[2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(self, workregion_offset=0, workregion_y_set=0.1,
                        target_dim=(0.2, 0.3), grid_size=[4, 1]):
        super().get_object_info(workregion_offset, workregion_y_set,
                                target_dim=target_dim, grid_size=grid_size)

    def load_containers(self, target_container, offset=0.4, y_set=0.5,
                        direction="left", z_set=0.1, orient_offset=[0, 0, 0]):
        """
        Overrides the container placement parameters.
        The counter_0 cabinet placement parameters (offset/z_set/orient_offset) follow test_1.py;
        and the subentities handling of container_mapping in the parent class load_containers is kept,
        so that the reference object (cake_9) is placed inside the cabinet as a subentity.
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
                # The children of container_mapping (the in-cabinet reference object) are placed into the cabinet body as subentities
                for parent, children in self.container_mapping.items():
                    if parent == target_container:
                        container_config["subentities"] = []
                        for j, child in enumerate(children):
                            child_config = self.get_entity_config(
                                child,
                                position=[j * 0.1 - 0.05 * (len(children) - 1), 0, -0.075],
                                orientation=[0, 0, 0],
                            )
                            container_config["subentities"].append(child_config)
                self.config["task"]["components"].append(container_config)
            else:
                container_config = self.get_entity_config(target_container)
                self.config["task"]["components"].append(container_config)

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success conditions (ordered constraint):
        Stage 0: the cabinet counter_0 is pulled open (is_open, locked in permanently once satisfied; closing the door afterwards does not revert it)
        Stage 1: the selected same-category object is placed inside the cabinet and at rest (contain_v); the check is only unlocked after is_open is satisfied
        Both target_entity / target_container are str.
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
        instruction = ["An object is already stored in the cabinet. "
                       "Pick the object of the same kind on the table and put it into the cabinet."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("select_same_cake")
class SelectSameCakeTask(PrimitiveSeqTask):
    """
    Task flow: open the cabinet door (pull) → pick(cake_0) → place(counter_0) → close the cabinet door (push) → end
    The success condition is asyn_sequence (is_open → contain_v), hence it inherits PrimitiveSeqTask.
    Objects that need to be fixed: counter (the cabinet body is a component and must be attached to the arena)
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "counter",
            # "cake",  # container
            #  "banana",  # target object
            # "scone", "cherry", "bagel", "bar_soap",  # distractors and in-cabinet reference object
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
                if height==0.0:
                    height+=0.018
                if any(j in k for j in ["cake","scone"]):
                    height-=0.008
                entity.init_pos[2] += height

    def attach_entities_to_arena(self):
        for key, entity in self.entities.items():
            if any(obj in key for obj in self.attach_objects):
                entity.detach()
                self._arena.attach(entity)

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


# ---------------------------- Class 2 task (inherits class 1, only swaps the object pool) ----------------------------

@register.add_config_manager("select_same_banana")
class SelectSameBananaConfigManager(SelectSameCakeConfigManager):
    """
    Class 2: the in-cabinet reference object is replaced with cherry_1, the same-category target
    on the countertop is replaced with banana_21, and the distractors are replaced with bagel_3
    and bar_soap_2. All other logic is fully reused from class 1.
    """

    def get_seen_task_config(self):
        self.seen_object = ["banana_21"]
        self.distractor = ["cherry_1", "bagel_3", "bar_soap_2"]
        self.mid_container = [{"counter_0": ["cherry_1"]}]
        self.robocasa_scene = "ONE_WALL_LARGE_1"
        return super().get_seen_task_config()

    def load_containers(self, target_container, offset=0.4, y_set=0.5,
                        direction="left", z_set=0.1, orient_offset=[0, 0, 0]):
        """
        Overrides the container placement parameters.
        The counter_0 cabinet placement parameters (offset/z_set/orient_offset) follow test_1.py;
        and the subentities handling of container_mapping in the parent class load_containers is kept,
        so that the reference object (cake_9) is placed inside the cabinet as a subentity.
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
                # The children of container_mapping (the in-cabinet reference object) are placed into the cabinet body as subentities
                for parent, children in self.container_mapping.items():
                    if parent == target_container:
                        container_config["subentities"] = []
                        for j, child in enumerate(children):
                            child_config = self.get_entity_config(
                                child,
                                position=[j * 0.1 - 0.05 * (len(children) - 1), -0.02, -0.02],
                                orientation=[0, 0, 0],
                            )
                            container_config["subentities"].append(child_config)
                self.config["task"]["components"].append(container_config)
            else:
                container_config = self.get_entity_config(target_container)
                self.config["task"]["components"].append(container_config)

@register.add_task("select_same_banana")
class SelectSameBananaTask(SelectSameCakeTask):
    """Fully reuses the Task logic of class 1."""

    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
