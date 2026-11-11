import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("cook_steak_0")
class CookSteakConfigManager(Multi_traget_container):
    """
    ConfigManager for cook_meat_pan_stove task.

    Config source: t_config.json
    - seen_object:    ["steak_0"]
    - distractor:     ["pork_chop_13", "lamb_chop_5"]
    - seen_container: ["plate_0"]
    - fixed_fixture:  ["stove_0"]
    - robocasa_scene: U_SHAPED_LARGE_2
    - fixture_surface: stovetop_main_group
    - destination_position: bottom
    - robot: position [3.050067173852504, -1.6998841861248737, 0.0], euler [0, 0, -1.57]
    - inherited: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[1, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.3, "y_set": -0.03, "direction": "right", "z_set": 0.01},
            {"offset": 0.25, "y_set": 0.1, "direction": "left", "z_set": 0.04,"orient_offset":[0,0,3.14]},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=-0.62,
        workregion_y_set=0.05,
        target_dim=(0.25, 0.25),
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
        Success condition: the steak is first placed into the pan to cook, then finally placed on the plate and at rest.
        target_container has the structure [plate, pan] (index 0 is the final container plate, index 1 is the cooking container pan).
        asyn_sequence is used to enforce the process order: pan first, then plate.
        """
        pan = target_container[1] if isinstance(target_container, list) and len(target_container) > 1 else target_container
        plate = target_container[0] if isinstance(target_container, list) else target_container

        conditions_config = dict(
            and_conditions=[
                dict(
                    asyn_sequence=dict(
                        condition_sets=[
                            dict(
                                contain=dict(
                                    container=pan,
                                    entities=target_entity,
                                )
                            ),
                            dict(
                                contain=dict(
                                    container=plate,
                                    entities=target_entity,
                                )
                            ),
                        ],
                        ordered_indices=[0, 1]
                    )
                ),
                # The stovetop knob must be turned on (is_open locks in once satisfied, ANDed with the ordered condition)
                dict(
                    is_open=dict(
                        container="stove_0",
                        joint_name="knob_front_right",
                    )
                ),
            ]
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text using declarative sentences, without exposing specific operation steps.
        """
        instruction = [
            "I want to eat the steak, please cook it in the pan and put it on the plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("cook_steak_0")
class CookSteakTask(PrimitiveSeqTask):
    """
    Task class for cook_meat_pan_stove task.

    Task flow: pick → cook → place → end
    Objects that need to be fixed: plate (the container is placed on the countertop and must be attached to the arena)
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate","pan"]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)

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
                    height = 0.02
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: multi-target pick → cook → place → observe loop, followed by end.
        target_entity is a list and target_container is also a list.
        All target objects are placed into the same container.
        """
        target_entities = self.config_manager.target_entity
        container_name = self.target_container[0] if isinstance(self.target_container, list) else self.target_container
        skill_sequence = []
        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name=target_entities[0]),

            partial(SkillLib.place, target_container_name=self.target_container[1]),

            partial(SkillLib.observe),
            partial(SkillLib.pick, body_name="stove_0/knob_front_right"),
            partial(SkillLib.rotate_knob),
            partial(SkillLib.observe),
            partial(SkillLib.pick, target_entity_name=target_entities[0]),
            partial(SkillLib.place, target_container_name=self.target_container[0]),
        ])
        skill_sequence.extend([partial(SkillLib.end)])
        # skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("cook_chicken_breast_0")
class CookChickenBreastConfigManager(CookSteakConfigManager):
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["chicken_breast_0"]
        self.distractor = ["pork_chop_13", "lamb_chop_5"]
        self.seen_container = ["plate_5", "pan_1"]
        self.fixed_fixture = ["stove_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_0"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the chicken breast, please cook it in the pan and put it on the plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("cook_chicken_breast_0")
class CookChickenBreastTask(CookSteakTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("cook_sausage_0")
class CookSausageConfigManager(CookSteakConfigManager):
    def __init__(self, task_name, num_objects=[2, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["sausage_0"]
        self.distractor = ["pork_chop_13", "lamb_chop_5"]
        self.seen_container = ["plate_7", "pan_1"]
        self.fixed_fixture = ["stove_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_2"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat the sausage, please cook it in the pan and put it on the plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("cook_sausage_0")
class CookSausageTask(CookSteakTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
