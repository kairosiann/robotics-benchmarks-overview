import random
from functools import partial

from RMMBench.tasks.base_task import PrimitiveTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("pick_chocolate")
class PickChocolateConfigManager(BenchTaskConfigManager):
    """
    ConfigManager for pick_snack_single task.

    Config source: t_config.json
    - seen_object:    ["chocolate_2", "chocolate_5", "chocolate_6"]
    - distractor:     ["bagged_food_8", "bar_10", "boxed_food_0", "chips_7"]
    - seen_container: ["plate_2"]
    - robocasa_scene: ONE_WALL_LARGE_1
    - fixture_surface: island_counter_island_group
    - destination_position: bottom
    - robot: position [3.2, -0.89, 0.0], euler [0, 0, 1.57]
    """

    def __init__(self, task_name, num_objects=[3], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_object_info(
        self,
        workregion_offset=0,
        workregion_y_set=0.1,
        target_dim=(0.3, 0.25),
        grid_size=[10, 10],
    ):
        """
        Override workspace parameters.
        island_counter_island_group + bottom direction,
        referencing the parameters of stovetop-type tasks in the workflow.
        """
        super().get_object_info(
            workregion_offset,
            workregion_y_set,
            target_dim=target_dim,
            grid_size=grid_size,
        )

    def load_containers(
        self, target_container, offset=0.2, y_set=0.05, direction="left"
    ):
        """
        Override container placement parameters.
        The plate is placed on the left side of the workspace, 0.3m from the edge.
        """
        if target_container is not None:
            if self.work_info and self.target_container:
                container_info = self.get_container_info_from_workregion(
                    self.work_info,
                    anchor=self.destination_position,
                    offset=offset,
                    y_set=y_set,
                    direction=direction,
                )
                container_config = self.get_entity_config(
                    target_container,
                    position=container_info["position"],
                    orientation=container_info["orientation"],
                )
                self.config["task"]["components"].append(container_config)

    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Success condition: the object is placed inside the plate container.
        Uses the contain condition to check whether target_entity is in target_container.
        """
        conditions_config = dict(
            contain=dict(
                container=target_container,
                entities=[target_entity],
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, target_entity, target_container, **kwargs):
        """
        Generate the instruction text in natural language style, without exposing concrete operation steps.
        """
        instruction = [
            f"I want to eat the {self.extract_base_name(target_entity)}, can you put it on the plate for me?"
        ]
        self.config["task"]["instructions"] = instruction
        return self.config


@register.add_task("pick_chocolate")
class PickChocolateTask(PrimitiveTask):
    """
    Task class for pick_snack_single task.

    Task flow: pick chocolate → place on plate → end
    Objects that need to be fixed: plate (container placed on the countertop, must be attached to the arena)
    """

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate",
        #                       " chocolate_2",
        #  "bar_10",
        # "boxed_food_0",
        # "chips_7",
                               "stove"]
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
                print("k:",k)
                if "chips" in k:
                    height =0.015
                entity.init_pos[2] += height

    def get_expert_skill_sequence(self, physics):
        """
        Expert skill sequence: pick → place → end
        - pick:  grasp target_entity (chocolate)
        - place: put it onto target_container (plate)
        - end:   finish the task
        """
        target_entity = self.config_manager.target_entity
        skill_sequence = [
            partial(SkillLib.pick, target_entity_name=target_entity),
            partial(SkillLib.place, target_container_name=self.target_container),
            partial(SkillLib.end),
        ]
        return skill_sequence


@register.add_config_manager("pick_chip")
class PickChipConfigManager(PickChocolateConfigManager):
    def __init__(self, task_name, num_objects=[2], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    def get_seen_task_config(self):
        self.seen_object = ["chips_13","chips_14","chips_6"]
        self.distractor = ["bagged_food_8","bar_10","boxed_food_0","chocolate_5"]
        self.robocasa_scene = "ONE_WALL_LARGE_1"
        return super().get_seen_task_config()


@register.add_task("pick_chip")
class PickChipTask(PickChocolateTask):
    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)