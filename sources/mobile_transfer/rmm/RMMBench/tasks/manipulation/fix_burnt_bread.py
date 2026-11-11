import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveSeqTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("fix_burnt_bread_0")
class FixBurntBreadConfigManager(Multi_traget_container):
    """
    ConfigManager for fix_burnt_bread task (B04).

    Config source: t_config.json
    - seen_object:    ["bread_21", "bread_9"]
    - distractor:     ["bread_7", "cake_7"]
    - mid_container:  [{"plate_0": ["bread_21"]}]
    - seen_container: ["plate_0", "pan_1", "tray_0"]
    - fixed_fixture:  ["stove_0"]
    - robocasa_scene: U_SHAPED_LARGE_2
    - fixture_surface: stovetop_main_group
    - destination_position: bottom
    - robot: position [3.050067173852504, -1.6998841861248737, 0.0], euler [0, 0, -1.57]
    - Inheritance: Multi_traget_container (both target_entity and target_container are lists)

    Task flow:
    1. Take the burnt bread bread_21 off the plate → put it into the discard bowl
    2. Pick up the fresh bread bread_9 → put it into the pan on the stove to pan-fry
    3. Take the fried bread out of the pan → put it back on the original plate
    """

    def __init__(self, task_name, num_objects=[1, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.18, "y_set": -0.03, "direction": "right", "z_set": -0.01},
            {"offset": 0.25, "y_set": 0.2, "direction": "left", "z_set": 0.04, "orient_offset": [0, 0, 3.14]},
            {"offset": 0, "y_set": 0.18, "direction": "top", "z_set": 0.0,"orient_offset": [0, 0, 1.57]},
        ]

    def get_object_info(
        self,
        workregion_offset=-0.62,
        workregion_y_set=-0.05,
        target_dim=(0.4, 0.25),
        grid_size=[1, 2],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success conditions: asyn_sequence in expert-sequence order, ordered_indices=[0, 1, 2, 3]:
        - Stage 0: burnt bread target_entity[0] placed into the discard tray
        - Stage 1: fresh bread target_entity[1] placed into the pan to fry (supplementary step)
        - Stage 2: turn on the stove knob stove_0/knob_front_right
        - Stage 3: fried bread target_entity[1] placed back on the original plate

        The bread being in the pan is a transient state (it will be taken out afterwards), so a plain
        contain condition cannot hold simultaneously with contain(plate) at the final moment;
        the stage-memory semantics of asyn_sequence must be used.
        """
        plate = target_container[0] if isinstance(target_container, list) else target_container
        pan = target_container[1] if isinstance(target_container, list) and len(target_container) > 1 else target_container
        tray = target_container[2] if isinstance(target_container, list) and len(target_container) > 2 else target_container

        conditions_config = dict(
            asyn_sequence=dict(
                condition_sets=[
                    dict(contain=dict(container=tray, entities=[target_entity[0]])),
                    dict(contain=dict(container=pan, entities=[target_entity[1]])),
                    dict(is_open=dict(container="stove_0", joint_name="knob_front_right")),
                    dict(contain=dict(container=plate, entities=[target_entity[1]])),
                ],
                ordered_indices=[1, 3],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text.
        From the instruction field in t_config.json:
          "The bread on the plate is burnt. Put it in the discard bowl, pan-fry the fresh sliced bread on the stove, and place it on the same plate."
        """
        instruction = [
            "The bread on the plate is burnt, I would like it placed in the tray, and a fresh one pan-fried and placed on the same plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("fix_burnt_bread_0")
class FixBurntBreadTask(PrimitiveSeqTask):
    """
    Task class for fix_burnt_bread task (B04).

    Task flow:
    1. pick bread_21 (burnt bread) → place bowl (discard bowl) → observe
    2. pick bread_9 (fresh bread) → place pan (stove pan) → observe
    3. pick bread_9 (fried bread) → place plate (original plate) → observe
    4. end

    Objects that need to be fixed: plate, stove, pan, bowl
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "stove", "plate", "pan", "tray",  # containers and fixtures
            # "bread",  # target objects
            # "cake", "donut",  # distractors
        ]
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
        to avoid initial interpenetration.
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
        Expert skill sequence:
        1. pick bread_21 (burnt bread) → place bowl (discard bowl) → observe
        2. pick bread_9 (fresh bread) → place pan (stove pan) → observe
        3. pick bread_9 (fried bread) → place plate (original plate) → observe
        4. end

        target_entity = ["bread_21", "bread_9"]
        target_container = ["plate_0", "pan_1", "tray_0"]
        - target_container[0] = plate (final placement)
        - target_container[1] = pan (pan used for frying)
        - target_container[2] = tray (discard tray)
        """
        target_entities = self.config_manager.target_entity
        containers = self.target_container if isinstance(self.target_container, list) else [self.target_container]
        plate = containers[0]
        pan = containers[1]
        tray = containers[2]

        burnt_bread = target_entities[0]
        fresh_bread = target_entities[1]

        skill_sequence = []
        # # Step 1: remove the burnt bread → discard tray
        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name=burnt_bread),
            partial(SkillLib.place, target_container_name=tray),
            partial(SkillLib.observe),
        ])
        # Step 2: pick the fresh bread → put it in the pan to fry → rotate the knob to heat
        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name=fresh_bread),
            partial(SkillLib.place, target_container_name=pan),
            partial(SkillLib.observe),
            partial(SkillLib.pick, body_name="stove_0/knob_front_right"),
            partial(SkillLib.rotate_knob),
            partial(SkillLib.observe),
        ])
        # Step 3: take the fried bread out of the pan → put it back on the plate
        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name=fresh_bread),
            partial(SkillLib.place, target_container_name=plate),
            partial(SkillLib.observe),
        ])



        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


@register.add_config_manager("fix_burnt_bread_1")
class FixBurntBread1ConfigManager(FixBurntBreadConfigManager):
    def __init__(self, task_name, num_objects=[1, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["bread_21","bread_3"]
        self.distractor = ["donut_15"]
        self.mid_container = [
            {
                "plate_11": [
                    "bread_21"
                ]
            }
        ]
        self.seen_container = ["plate_11", "pan_1", "tray_1"]
        self.fixed_fixture = ["stove_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_4"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "The bread on the plate is burnt, I would like it placed in the tray, and a fresh one pan-fried and placed on the same plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("fix_burnt_bread_1")
class FixBurntBread1Task(FixBurntBreadTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


@register.add_config_manager("fix_burnt_bread_2")
class FixBurntBread2ConfigManager(FixBurntBreadConfigManager):
    def __init__(self, task_name, num_objects=[1, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["bread_21","bread_9"]
        self.distractor = [ "cake_9", "donut_13"]
        self.mid_container = [
            {
                "plate_12": [
                    "bread_21"
                ]
            }
        ]
        self.seen_container = ["plate_12", "pan_2", "tray_2"]
        self.fixed_fixture = ["stove_0"]
        self.robocasa_scene = "U_SHAPED_LARGE_7"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "The bread on the plate is burnt, I would like it placed in the tray, and a fresh one pan-fried and placed on the same plate."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("fix_burnt_bread_2")
class FixBurntBread2Task(FixBurntBreadTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
