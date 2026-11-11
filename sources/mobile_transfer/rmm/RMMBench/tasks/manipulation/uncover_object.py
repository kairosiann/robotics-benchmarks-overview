from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("uncover_fruit")
class UncoverObjectConfigManager(BenchTaskConfigManager):
    """
    Single-target occlusion task: target object is covered by a mid_container (e.g. pan).
    Robot needs to uncover the target and place it into the seen_container (e.g. tray).
    """
    def __init__(self, task_name, num_objects=[1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(self, workregion_offset=-0.5, workregion_y_set=0.1, target_dim=(0.3, 0.25), grid_size=[6, 6]):
        super().get_object_info(workregion_offset, workregion_y_set, target_dim=target_dim, grid_size=grid_size)

    def load_containers(self, target_container, offset=0.3, y_set=-0.05, direction="right"):
        if target_container is not None:
            if self.work_info and self.target_container:
                container_info = self.get_container_info_from_workregion(self.work_info,
                                                                         anchor=self.destination_position,
                                                                         offset=offset,
                                                                         y_set=y_set,
                                                                         direction=direction)
                container_config = self.get_entity_config(target_container,
                                                          position=[container_info["position"][0],
                                                                    container_info["position"][1],
                                                                    container_info["position"][2] + 0.02],
                                                          orientation=container_info["orientation"])
                self.config["task"]["components"].append(container_config)
            else:
                container_config = self.get_entity_config(target_container)
                self.config["task"]["components"].append(container_config)

    def load_objects(self, target_entity):
        super().load_objects(target_entity)
        # Flip pan upside down to cover objects underneath (add y-axis rotation on top of existing orientation)
        for component in self.config["task"]["components"]:
            if "pan" in component.get("name", ""):
                o = component["orientation"]
                component["orientation"] = [o[0], o[1] + 3.14, o[2]]

    def get_condition_config(self, target_entity, target_container, **kwargs):
        and_conditions = [
            dict(contain=dict(container=target_container, entities=["pan_0"])),
            dict(contain=dict(container="sink_0", entities=[target_entity])),
        ]
        self.config["task"]["conditions"] = dict(and_conditions=and_conditions)

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [f"Help me wash the {self.extract_base_name(target_entity)}."]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("uncover_fruit")
class UncoverObjectTask(PrimitiveSeqTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["tray", "peach","sink"]
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
                if self.config_manager.target_entity in k:
                    continue
                height = entity.get_placement_height()
                entity.init_pos[2] += height


    def get_expert_skill_sequence(self, physics):
        target_entity = self.config_manager.target_entity
        mid_container_name = list(self.config_manager.mid_container_mapping.keys())[0]
        init_ee_pos, init_ee_quat = list(self.robot.get_end_effector_pos(physics)), self.robot.get_end_effector_quat(
            physics)
        skill_sequence = [
            partial(SkillLib.pick, target_entity_name=mid_container_name),

            partial(SkillLib.place, target_container_name=self.target_container),
            partial(SkillLib.observe),
            partial(SkillLib.pick, target_entity_name=target_entity),
            partial(SkillLib.place, target_container_name="sink_0"),
            partial(SkillLib.end),
        ]
        return skill_sequence
