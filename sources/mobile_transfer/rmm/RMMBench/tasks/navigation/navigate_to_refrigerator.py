import random
from functools import partial

from RMMBench.tasks.navigation.base import CompositeNavigationTask
from RMMBench.tasks.config_manager import CompositeNavigationConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


# =============================================================================
# Base classes for navigate_to_refrigerator tasks
# =============================================================================

class NavigateToRefrigeratorBaseConfigManager(CompositeNavigationConfigManager):
    """
    Base ConfigManager for navigate_to_refrigerator tasks.

    All three variants are single-area tasks whose target poses are hardcoded
    (fixture_surface / destination_position only keep the composite pipeline
    from erroring; object positions never come from work_info).

    Single area: big_fridge placed at a hardcoded pose with the target objects
    inside at hardcoded offsets. The navigation stop point is hardcoded in
    load_objects_for_layout (the auto stop point from work_info is skipped
    because target_bbox is already appended there).
    """

    def _load_fridge_with_objects(self, idx, fridge_pos, fridge_orient, objects=None):
        """Place big_fridge at a hardcoded pose with objects inside at hardcoded offsets."""
        self.init_container_config = self.get_entity_config(
            "big_fridge", position=fridge_pos, orientation=fridge_orient, randomness=None)
        self.init_container_config["subentities"] = []

        if objects is None:
            objects = list(self.merged_seen_object[idx])

        drink = 1
        eat = 1
        for object in objects:
            entity_class = self.get_entity_class(object)
            if entity_class in ["Drink"] and "cola" not in object:
                object_config = self.get_entity_config(
                    object,
                    self.transform_position(
                        position=[-0.25 + drink * 0.16,
                                  random.uniform(-0.29, -0.28), 0.8],
                        parent_orient=fridge_orient),
                    orientation=[-1.57, 0, 0]
                )
                drink += 1

            else:
                object_config = self.get_entity_config(
                    object,
                    self.transform_position(
                        position=[
                            -0.12 + eat * 0.12,
                            -0.3, 1.03],
                        parent_orient=fridge_orient),
                )
            eat += 1
            self.init_container_config["subentities"].append(object_config)

        self.config["task"]["components"].append(self.init_container_config)


class NavigateToRefrigeratorBaseTask(CompositeNavigationTask):
    """
    Base Task for navigate_to_refrigerator tasks.
    attach_objects includes the fridge so it gets attached to the arena.
    """

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)

    def attach_entities_to_arena(self):
        """通用的挂载逻辑"""
        for key, entity in self.entities.items():
            if any(obj in key for obj in self.attach_objects):
                entity.detach()
                self._arena.attach(entity)

    def reset_entities_positions(self):
        if self.config_manager.composite_entities is not None:
            entities = self.config_manager.composite_entities
            for k in entities:
                if "fridge" in k:
                    # fridge pose is hardcoded, do not lift it
                    continue
                entity = self.entities.get(f"{k}", None)
                if entity is None:
                    continue
                height = entity.get_placement_height()
                if height == 0:
                    height = 0.02
                entity.init_pos[2] += height


# =============================================================================
# navigate_to_refrigerator_0 (base task, formerly registered as _1)
# Scene: ONE_WALL_LARGE_0 (from task_config.json)
# fixture_surface: island_counter_island_group ('around', so "right" is valid)
# big_fridge at [-0.4, -2, 0.13], stop point (hardcoded): [0.45, -1.85, 0]
# =============================================================================

@register.add_config_manager("navigate_to_refrigerator_0")
class NavigateToRefrigerator0ConfigManager(NavigateToRefrigeratorBaseConfigManager):
    """
    Variant 0 (base): single area, navigate to the open main refrigerator.
    composite_configs come from task_config.json ("navigate_to_refrigerator").
    """

    def __init__(self, task_name, num_objects=[[0, 3]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.LAYOUT_CONFIG_TABLE = [
            {
                "workregion_offset": 0,
                "workregion_y_set": 0.1,
                "target_dim": (0.3, 0.25),
                "grid_size": [6, 6]
            }
        ]

    def load_containers_for_layout(self, idx):
        if idx != 0:
            return super().load_containers_for_layout(idx)
        # big_fridge at hardcoded pose, objects inside at hardcoded offsets
        self._load_fridge_with_objects(idx, fridge_pos=[-0.4, -2, 0.13],
                                       fridge_orient=[0, 0, 1.57])

    def load_objects_for_layout(self, idx):
        super().load_objects_for_layout(idx)
        if idx == 0:
            # 冰箱前 (hardcoded stop point, from the original file)
            pos = [0.45, -1.94, 0]
            self.target_object_info.append({"position": pos})
            self.target_bbox.append(self.center2bbox(pos))

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to the open main refrigerator and grasp the bell pepper."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="left",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                is_grasped=dict(
                    entities=["bell_pepper_0"],
                    robot="pandaomron"
                ),
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "left"

        self.config["task"]["conditions"] = conditions_config


@register.add_task("navigate_to_refrigerator_0")
class NavigateToRefrigerator0Task(NavigateToRefrigeratorBaseTask):
    """Base task: navigate to the main refrigerator and pick the target."""

    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["big_fridge"]  # 这里填入需要挂载的物体名称
        super().__init__(task_name, robot=robot, **kwargs)

    def get_expert_skill_sequence(self, physics):
        skill_sequence = [
            partial(SkillLib.rotate_left),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_right),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_left),
            partial(SkillLib.pick, target_entity_name=self.config_manager.target_entity[0][0],
                    grasp_direction="horizontal"),
            partial(SkillLib.end, wait_time=10),
        ]
        return skill_sequence


# =============================================================================
# navigate_to_refrigerator_1 (formerly registered as _0)
# Scene: ONE_WALL_SMALL_0; big_fridge at [0.5, -1, 0.13]
# Robot starts in front of the fridge, so the stop point equals the
# robot init pos [1.35, -0.85, 0] and the expert only picks.
# =============================================================================

@register.add_config_manager("navigate_to_refrigerator_1")
class NavigateToRefrigerator1ConfigManager(NavigateToRefrigerator0ConfigManager):
    """
    Variant 1: single area, ONE_WALL_SMALL_0.
    fixture_surface: counter_main_main_group (ONE_WALL_SMALL only supports 'bottom').
    """

    def __init__(self, task_name, num_objects=[[0, 3]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.composite_configs = [
            {
                "seen_object": ["bell_pepper_0", "juice", "milk_4"],
                "mid_container": [{"big_fridge": ["bell_pepper_0", "juice", "milk_4"]}],
                "seen_container": ["big_fridge"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom"
            }
        ]
        self.robocasa_scene = "L_SHAPED_SMALL_2"
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")

    def load_containers_for_layout(self, idx):
        if idx != 0:
            return super().load_containers_for_layout(idx)
        self._load_fridge_with_objects(idx, fridge_pos=[0.5, -1, 0.13],
                                       fridge_orient=[0, 0, 1.57])

    def load_objects_for_layout(self, idx):
        # Skip the base CM override (it appends the base stop point); call the
        # raw CompositeNavigationConfigManager implementation instead.
        CompositeNavigationConfigManager.load_objects_for_layout(self, idx)
        if idx == 0:
            # robot init pos == stop point (pick-only variant)
            pos = [1.35, -0.95, 0]
            self.target_object_info.append({"position": pos})
            self.target_bbox.append(self.center2bbox(pos))


@register.add_task("navigate_to_refrigerator_1")
class NavigateToRefrigerator1Task(NavigateToRefrigerator0Task):
    """Variant 1: robot already in front of the fridge, expert only picks."""

    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            "pos": [2.65, -2.85, 0],
            "euler": [0, 0, 3.14],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        skill_sequence = [
            partial(SkillLib.pick, target_entity_name=self.config_manager.target_entity[0][0],
                    grasp_direction="horizontal"),
            partial(SkillLib.end, wait_time=1),
        ]
        return skill_sequence


# =============================================================================
# navigate_to_refrigerator_2
# Scene: G_SHAPED_SMALL_9; big_fridge at [3.5, -3.85, 0.13] (boxed_drink_0 inside),
# steak/bread standalone, plate_0 and small_fridge hardcoded.
# Stop point (hardcoded): [2.2, -1.13, 0] (小冰箱前)
# =============================================================================

@register.add_config_manager("navigate_to_refrigerator_2")
class NavigateToRefrigerator2ConfigManager(NavigateToRefrigerator0ConfigManager):
    """
    Variant 2: single area, G_SHAPED_SMALL_9, navigate to the small fridge.
    """

    def __init__(self, task_name, num_objects=[[0, 3]], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.direct_limit = "limit_y"
        self.composite_configs = [
            {
                "seen_object": ["bell_pepper_0", "boxed_drink_0", "bread"],
                "mid_container": [{"big_fridge": ["bell_pepper_0", "boxed_drink_0"]}],
                "seen_container": ["plate_0", "small_fridge"],
                "fixture_surface": "counter_main_main_group",
                "destination_position": "bottom"
            }
        ]
        self.robocasa_scene = "G_SHAPED_SMALL_9"
        self.work_info = [None] * len(self.composite_configs)
        self.sampled_points = [None] * len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")

    def load_containers_for_layout(self, idx):
        if idx != 0:
            return super().load_containers_for_layout(idx)
        # big_fridge at hardcoded pose; boxed_drink_0 and bell_pepper_0 inside
        # at hardcoded offsets (transformed by the fridge orientation, like _0).
        # NOTE: never write raw local offsets here — subentity positions must go
        # through transform_position with the fridge orientation.
        self._load_fridge_with_objects(
            idx, fridge_pos=[3.5, -3.85, 0.13], fridge_orient=[0, 0, -1.57],
            objects=["boxed_drink_0", "bell_pepper_0"])
        # plate_0 and small_fridge at hardcoded poses
        plate_config = self.get_entity_config("plate_0", position=[3.0, -3.35, 0.93])
        self.config["task"]["components"].append(plate_config)
        small_fridge_config = self.get_entity_config("small_fridge", position=[2.2, -0.4, 0.98])
        self.config["task"]["components"].append(small_fridge_config)

    def load_objects_for_layout(self, idx):
        # bread is a hardcoded standalone object; skip base grid placement
        if idx == 0:
            bread_config = self.get_entity_config("bread", position=[2.7, -0.25, 0.96])
            self.config["task"]["components"].append(bread_config)

            # 小冰箱前 (hardcoded stop point)
            pos = [2.2, -1.13, 0]
            self.target_object_info.append({"position": pos})
            self.target_bbox.append(self.center2bbox(pos))

    def get_instruction(self, target_entity, target_container, **kwargs):
        instruction = ["Navigate to the open main refrigerator and put the bell pepper into the plate next to it."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_condition_config(self, **kwargs):
        conditions_config = dict()
        conditions_config["asyn_sequence"] = [
            dict(
                contain_robot_pose=dict(
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                robot_orientation=dict(
                    target_orientation="right",
                    target_bbox=self.target_bbox[0],
                    robot="pandaomron"
                ),
                contain=dict(
                    container="plate_0",
                    entities=["bell_pepper_0"],
                ),
            ),
        ]
        conditions_config["ordered_indices"] = None

        self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
        self.target_object_info[0]["target_orientation"] = "right"

        self.config["task"]["conditions"] = conditions_config


@register.add_task("navigate_to_refrigerator_2")
class NavigateToRefrigerator2Task(NavigateToRefrigerator0Task):
    """Variant 2: navigate to the small fridge, pick and open it."""

    def __init__(self, task_name, robot, **kwargs):
        super().__init__(task_name, robot=robot, **kwargs)
        self.robot_params = {
            # "pos": [2.65, -3.9, 0],  # 冰箱前
            "pos": [2.65, -0.9, 0],  # 冰箱前

            "euler": [0, 0, 0],
        }
        self.robot.set_init_pos(**self.robot_params)

    def get_expert_skill_sequence(self, physics):
        skill_sequence = [
            partial(SkillLib.rotate_left),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_right),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_right),
            partial(SkillLib.moveforward),
            partial(SkillLib.rotate_left),
            partial(SkillLib.pick, target_entity_name=self.config_manager.target_entity[0][0],
                    grasp_direction="horizontal"),
            partial(SkillLib.place, target_container_name="plate_0"),
            partial(SkillLib.end, wait_time=10),
        ]
        return skill_sequence
