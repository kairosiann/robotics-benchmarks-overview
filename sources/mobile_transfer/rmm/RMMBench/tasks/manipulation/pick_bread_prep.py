import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveTask
from RMMBench.tasks.config_manager import Multi_traget_container
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("place_bread_jam_knife_0")
class PlaceBreadJamKnifeConfigManager(Multi_traget_container):
    """
    ConfigManager for pick_bread_prep task (B03).

    Config source: t_config.json
    - seen_object:    ["bread_5", "jam_0", "knife_22"]
    - distractor:     ["peanut_butter_jar_2", "spoon_8"]
    - seen_container: ["tray_0"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [2.749967571243619, -3.650127391388798, 0.0], euler [0, 0, 1.57]
    - inherited: Multi_traget_container (both target_entity and target_container are lists)
    """

    def __init__(self, task_name, num_objects=[2, 3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
            {"offset": 0.28, "y_set": 0.05, "direction": "left", "z_set": 0.01},
            {"offset": 0.28, "y_set": 0.05, "direction": "right", "z_set": 0.01},
            {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},
        ]

    def get_object_info(
        self,
        workregion_offset=0,
        workregion_y_set=0.1,
        target_dim=(0.35, 0.3),
        grid_size=[10, 10],
    ):
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: all target objects are placed inside the container and at rest.
        In Multi_traget_container, target_container is a list; take the first element as the detection container.
        target_entity is a list containing all target objects that need to be placed.
        """
        container = target_container[0] if isinstance(target_container, list) else target_container
        conditions_config = dict(
            contain=dict(
                container=container,
                entities=target_entity,
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text.
        From the instruction field in t_config.json:
          "Place the bread, the jam, and the knife on the preparation tray."
        """
        instruction = [
            "I would like the bread, the jam, and the knife on the preparation tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("place_bread_jam_knife_0")
class PlaceBreadJamKnifeTask(PrimitiveTask):
    """
    Task class for pick_bread_prep task (B03).

    Task flow: pick → place → observe × N → end (multi-target loop)
    Objects that need to be fixed: tray, stove
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [
            "tray", "stove",  # container and distractor fixtures
            # "bread", "jam", "knife", "waffle", "syrup_bottle", "fork", "bagel", "butter_stick",  # target objects
            # "peanut_butter_jar", "spoon", "honey_bottle", "donut", "cheese", "spatula",  # distractors
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
        to avoid initial penetration/clipping.
        """
        if self.config_manager.all_entities is not None:
            entities = self.config_manager.all_entities
            for k in entities:
                entity = self.entities.get(k)
                if entity is None:
                    continue
                height = entity.get_placement_height()

                if "bottle" in k:
                    height += 0.04
                elif height == 0:
                    height += 0.02

                if "chips" in k:
                    height = 0.015
                if height == 0:
                    height += 0.02
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
        for entity in target_entities:
            skill_sequence.extend([
                partial(SkillLib.pick, target_entity_name=entity),
                partial(SkillLib.place, target_container_name=container_name),
                partial(SkillLib.observe),
            ])
        skill_sequence.extend([partial(SkillLib.end)])
        skill_sequence = self.remove_second_last(skill_sequence)
        return skill_sequence


# ===== B03 sub-task 2: waffle, syrup, fork =====
@register.add_config_manager("place_waffle_syrup_fork_0")
class PlaceWaffleSyrupForkConfigManager(PlaceBreadJamKnifeConfigManager):
    """
    B03 sub-task 2: Place the waffle, the syrup, and the fork on the preparation tray.
    - seen_object:    ["waffle_4", "syrup_bottle_2", "fork_10"]
    - distractor:     ["honey_bottle_14", "spoon_17", "donut_5"]
    - seen_container: ["tray_1"]
    - num_objects:    [3, 3]
    """

    def __init__(self, task_name, num_objects=[2, 3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["waffle_4", "syrup_bottle_2", "fork_10"]
        self.distractor = ["honey_bottle_14", "spoon_17", "donut_5"]
        self.seen_container = ["tray_1"]
        self.robocasa_scene = "ONE_WALL_LARGE_2"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like the waffle, the syrup, and the fork on the preparation tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("place_waffle_syrup_fork_0")
class PlaceWaffleSyrupForkTask(PlaceBreadJamKnifeTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== B03 sub-task 3: bagel, butter, knife =====
@register.add_config_manager("place_bagel_butter_knife_0")
class PlaceBagelButterKnifeConfigManager(PlaceBreadJamKnifeConfigManager):
    """
    B03 sub-task 3: Place the bagel, the butter, and the knife on the preparation tray.
    - seen_object:    ["bagel_0", "butter_stick_5", "knife_18"]
    - distractor:     ["donut_14", "cheese_0", "peanut_butter_jar_7", "spatula_1"]
    - seen_container: ["tray_4"]
    - num_objects:    [4, 3]
    """

    def __init__(self, task_name, num_objects=[2, 3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["bagel_0", "butter_stick_5", "knife_18"]
        self.distractor = ["donut_14", "cheese_0", "peanut_butter_jar_7", "spatula_1"]
        self.seen_container = ["tray_4"]
        self.robocasa_scene = "ONE_WALL_LARGE_3"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I would like the bagel, the butter, and the knife on the preparation tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("place_bagel_butter_knife_0")
class PlaceBagelButterKnifeTask(PlaceBreadJamKnifeTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== B03 sub-task 1 variant: semantic & commonsense =====
@register.add_config_manager("place_bread_jam_knife_1")
class PlaceBreadJamKnife1ConfigManager(PlaceBreadJamKnifeConfigManager):
    def __init__(self, task_name, num_objects=[2, 3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.robocasa_scene = "ONE_WALL_LARGE_4"
        return super().get_seen_task_config()


    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat bread with jam, please put what I need on the preparation tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("place_bread_jam_knife_1")
class PlaceBreadJamKnife1Task(PlaceBreadJamKnifeTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)


# ===== B03 sub-task 2 variant: semantic & commonsense =====
@register.add_config_manager("place_waffle_syrup_fork_1")
class PlaceWaffleSyrupFork1ConfigManager(PlaceWaffleSyrupForkConfigManager):
    def __init__(self, task_name, num_objects=[2, 2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.robocasa_scene = "ONE_WALL_LARGE_7"
        return super().get_seen_task_config()


    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "My friend wants to eat waffle with syrup, please put the three things needed on the preparation tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("place_waffle_syrup_fork_1")
class PlaceWaffleSyrupFork1Task(PlaceWaffleSyrupForkTask):
    def __init__(self, task_name, num_objects=[2, 3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)


# ===== B03 sub-task 3 variant: semantic & commonsense =====
@register.add_config_manager("place_bagel_butter_knife_1")
class PlaceBagelButterKnife1ConfigManager(PlaceBagelButterKnifeConfigManager):

    def get_seen_task_config(self):
        self.robocasa_scene = "ONE_WALL_LARGE_8"
        return super().get_seen_task_config()

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = [
            "I want to eat a buttered bagel for breakfast, please put what I need on the preparation tray."
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("place_bagel_butter_knife_1")
class PlaceBagelButterKnife1Task(PlaceBagelButterKnifeTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
