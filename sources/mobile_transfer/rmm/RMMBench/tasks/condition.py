from typing import Optional

import numpy as np
from RMMBench.utils.register import register
from RMMBench.utils.utils import distance
from RMMBench.tasks.components.entity import Entity


class Condition:
    def __init__(self):
        pass

    def is_met(self, physics=None):
        raise NotImplementedError()

    def met_progress(self, physics=None):
        return self.is_met(physics)


@register.add_condition("order")
class OrderCondition(Condition):
    """
    check the position order of the given entities.
    params:
        entities: the given entities should in the expected order.
        axis: the  axis to check the order.
        offset: the acceptable offset between the entities in other axis.
    """

    def __init__(self, entities, axis=[0], offset=0.1):
        self.entities = entities
        self.axis = axis
        self.offset = offset

    def is_met(self, physics):
        if isinstance(self.entities[-1], Entity):
            self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]
        entity_points = [physics.bind(entity_mjcf).xpos for entity_mjcf in self.entities_mjcf]
        for axis in [0, 1, 2]:  # x y z
            if axis in self.axis:
                if not all(
                        [entity_points[i][axis] < entity_points[i + 1][axis] for i in range(len(entity_points) - 1)]):
                    return False
            else:
                if not all([(entity_points[i][axis] - entity_points[i + 1][axis]) < self.offset for i in
                            range(len(entity_points) - 1)]):
                    return False
        return True


@register.add_condition("scene_contain")  # TODO: consider renaming to distinguish
class ContainSceneCondition(Condition):
    """
    Condition for checking containment against containers extracted from the Scene.
    """

    def __init__(self, entities, container_name, scene, vel_th=0.1, **kwargs):
        # Core logic: if a scene instance is passed, dynamically obtain the container instance in that scene
        self.scene = scene
        self.container_name = container_name
        self.entities = entities

        self.vel_th = vel_th
        self.kwargs = kwargs

    def is_met(self, physics=None):
        self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]

        # Get physics data
        entity_points = [physics.bind(e).xpos for e in self.entities_mjcf]
        entity_velocity = [physics.bind(e).cvel for e in self.entities_mjcf]
        # 1. Spatial containment check
        # print("self.scene:", self.scene)
        # print("self.container_name:", self.container_name)
        # print("self.entities:", self.entities)
        for point in entity_points:
            if not self.scene.contain(point, self.container_name, physics, **self.kwargs):
                return False

        return True


@register.add_condition("scene_not_contain")  # TODO: consider renaming to distinguish
class NoContainSceneCondition(Condition):
    """
    Condition for checking containment against containers extracted from the Scene.
    """

    def __init__(self, entities, container_name, scene, vel_th=0.1, **kwargs):
        # Core logic: if a scene instance is passed, dynamically obtain the container instance in that scene
        self.scene = scene
        self.container_name = container_name
        self.entities = entities
        self.vel_th = vel_th
        self.kwargs = kwargs

    def is_met(self, physics=None):
        self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]

        # Get physics data
        entity_points = [physics.bind(e).xpos for e in self.entities_mjcf]
        entity_velocity = [physics.bind(e).cvel for e in self.entities_mjcf]
        # 1. Spatial containment check

        for point in entity_points:
            if not self.scene.contain(point, self.container_name, physics, **self.kwargs):
                return True
        return False


@register.add_condition("contain")
class ContainCondition(Condition):
    """
    Check if the container contains the target entities
    params:
        container: the container to contain the target eneities
        entities: the target entities to be contained
    """

    def __init__(self, container, entities, **kwargs):
        assert container is not None, "container must be provided"
        self.container = container
        self.entities = entities
        self.kwargs = kwargs
        # print("self.entities:", self.entities)

    def is_met(self, physics=None):
        # print("self.entities:", self.entities)
        # print("self.container:", self.container)
        if isinstance(self.entities[-1], Entity):
            self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]
        entity_points = [physics.bind(entity_mjcf).xpos for entity_mjcf in self.entities_mjcf]

        for point in entity_points:
            if not self.container.contain(point, physics, **self.kwargs):
                return False
        return True

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("contain_robot_pose")
class ContainRobotPoseCondition(Condition):
    """
        Condition to check if the robot's base has entered the target area.
        This is used to determine if the navigation phase is complete and
        the robot is close enough to the object to begin manipulation.

        Args:
            target_bbox: The boundary coordinates of the arrival zone [xmin, xmax, ymin, ymax].
            robot: The robot instance used to retrieve real-time pose data.
        """

    def __init__(self, target_bbox, robot, **kwargs):
        assert target_bbox is not None, "target_bbox must be provided"
        self.target_bbox = target_bbox
        self.robot = robot
        self.kwargs = kwargs

    def is_met(self, physics=None):
        robot_info = self.robot.get_link_base_info(physics)
        robot_position = robot_info["position"]

        xmin, xmax, ymin, ymax = self.target_bbox

        if xmin <= robot_position[0] <= xmax and ymin <= robot_position[1] <= ymax:
            return True
        return False

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("robot_orientation")
class RobotOrientationCondition(Condition):
    """
        Condition to check if the robot's base orientation matches the target facing direction.
        This is used to evaluate the 'success_at_facing' metric in navigation tasks,
        ensuring the robot is correctly aligned for subsequent interaction or observation.

        Args:
            target_orientation: The semantic target direction ("top", "bottom", "left", "right").
            robot: The robot instance used to retrieve real-time pose data (euler angles).
    """

    def __init__(self, target_orientation, robot, target_bbox=None, **kwargs):
        assert target_orientation is not None, "target_orientation must be provided"
        self.target_orientation = target_orientation
        self.robot = robot
        self.target_bbox = target_bbox
        self.kwargs = kwargs

    def is_met(self, physics=None):
        robot_info = self.robot.get_link_base_info(physics)
        robot_position = robot_info["position"]
        robot_euler = robot_info["euler"]

        # First check whether the robot is inside the target area
        if self.target_bbox is not None:
            xmin, xmax, ymin, ymax = self.target_bbox
            if not (xmin <= robot_position[0] <= xmax and ymin <= robot_position[1] <= ymax):
                return False

        # When inside the target area, check the orientation
        if self.target_orientation == "top":
            if abs(robot_euler[2] - 1.57) < 0.01:
                return True
        if self.target_orientation == "left":
            if abs(robot_euler[2] - 3.14) < 0.01 or abs(robot_euler[2] + 3.14) < 0.01:
                return True
        if self.target_orientation == "right":
            if abs(robot_euler[2]) < 0.01:
                return True
        if self.target_orientation == "bottom":
            if abs(robot_euler[2] + 1.57) < 0.01:
                return True
        return False

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("contain_v_pos")
class ContainCondition(Condition):
    """
    Check if the container contains the target entities
    params:
        container: the container to contain the target eneities
        entities: the target entities to be contained

    """

    def __init__(self, container, entities, check_xquat=False, vel_th=None, z_th=None, **kwargs):
        assert container is not None, "container must be provided"
        self.container = container
        # print("entities:", entities)
        self.entities = entities
        self.kwargs = kwargs
        self.vel_th = vel_th
        self.z_th = z_th
        self.check_xquat = check_xquat

    def is_met(self, physics=None):
        # print("self.entities:", self.entities)
        if isinstance(self.entities[-1], Entity):
            self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]

        entity_points = [physics.bind(entity_mjcf).xpos for entity_mjcf in self.entities_mjcf]
        entity_velocity = [physics.bind(entity_mjcf).cvel for entity_mjcf in self.entities_mjcf]
        entity_xquat = [physics.bind(entity_mjcf).xquat for entity_mjcf in self.entities_mjcf]

        # container:
        self.c_mjcf = self.container.mjcf_model.worldbody
        c_points = physics.bind(self.c_mjcf).xpos
        c_xquat = physics.bind(self.c_mjcf).xquat

        geom_id = [physics.bind(entity_mjcf).element_id for entity_mjcf in self.entities_mjcf]
        entity_geom_xpos = physics.data.geom_xpos[geom_id]

        for point in entity_points:
            if not self.container.contain(point, physics, z_th=self.z_th, **self.kwargs):
                return False
        for vel in entity_velocity:
            if not self.container.stationary(vel, physics, th=self.vel_th, **self.kwargs):
                return False
        if self.check_xquat:
            for quat in entity_xquat:
                if not self.container.standing(physics, quat, **self.kwargs):
                    return False

        return True

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("contain_v")
class ContainCondition(Condition):
    """
    Check if the container contains the target entities
    params:
        container: the container to contain the target eneities
        entities: the target entities to be contained
    """

    def __init__(self, container, entities, check_xquat=False, vel_th=1.5, **kwargs):
        assert container is not None, "container must be provided"
        self.container = container
        self.entities = entities
        print("container:", container)
        print("entities:", entities)
        self.kwargs = kwargs
        self.vel_th = vel_th
        self.check_xquat = check_xquat

    def is_met(self, physics=None):
        # print("self.entities", self.entities)

        if isinstance(self.entities[-1], Entity):
            self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]
        entity_points = [physics.bind(entity_mjcf).xpos for entity_mjcf in self.entities_mjcf]
        entity_velocity = [physics.bind(entity_mjcf).cvel for entity_mjcf in self.entities_mjcf]
        entity_xquat = [physics.bind(entity_mjcf).xquat for entity_mjcf in self.entities_mjcf]

        # print("self.container_type:",self.container.__class__.__name__)

        for point in entity_points:
            if not self.container.contain(point, physics, **self.kwargs):
                return False
        for vel in entity_velocity:
            if not self.container.stationary(vel, physics, th=self.vel_th, **self.kwargs):
                return False
        if self.check_xquat:
            for quat in entity_xquat:
                if not self.container.standing(physics, quat, **self.kwargs):
                    return False

        return True

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("tube_contain_v")
class TubeContainCondition(Condition):
    """
    Check if the container contains the target entities
    params:
        container: the container to contain the target eneities
        entities: the target entities to be contained

    """

    def __init__(self, container, entities, check_xquat=False, vel_th=None, **kwargs):
        assert container is not None, "container must be provided"
        self.container = container
        self.entities = entities
        self.kwargs = kwargs
        self.vel_th = vel_th
        self.check_xquat = check_xquat

    def is_met(self, physics=None):
        # print("self.entities", self.entities)
        if isinstance(self.entities[-1], Entity):
            self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]

        entity_points = [physics.bind(entity_mjcf).xpos for entity_mjcf in self.entities_mjcf]
        entity_velocity = [physics.bind(entity_mjcf).cvel for entity_mjcf in self.entities_mjcf]
        entity_xquat = [physics.bind(entity_mjcf).xquat for entity_mjcf in self.entities_mjcf]

        # print("physics dir", dir(physics.data))
        geom_id = [physics.bind(entity_mjcf).element_id for entity_mjcf in self.entities_mjcf]
        entity_geom_xpos = physics.data.geom_xpos[geom_id]

        # print("entity_geom_xpos:", entity_geom_xpos)

        # print("entity_points", entity_points)
        # print("entity_velocity:", entity_velocity)
        # print("entity_xquat:", entity_xquat)
        # print("entity_points:",entity_points)
        for point in entity_points:
            if not self.container.tube_contain(point, physics, **self.kwargs):
                return False
        for vel in entity_velocity:
            if not self.container.stationary(vel, physics, th=self.vel_th, **self.kwargs):
                return False
        if self.check_xquat:
            for quat in entity_xquat:
                if not self.container.standing(physics, quat, **self.kwargs):
                    return False

        return True

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("not_contain")
class NotContainCondition(Condition):
    """
    Check if the container does not contain the target entities.
    params:
        container: the container to not contain the target entities
        entities: the target entities to be not contained
    """

    def __init__(self, container, entities):
        super().__init__()
        assert container is not None, "container must be provided"
        self.container = container
        self.entities = entities

    def is_met(self, physics=None):
        if isinstance(self.entities[-1], Entity):
            self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]
        entity_points = [physics.bind(entity_mjcf).xpos for entity_mjcf in self.entities_mjcf]
        for point in entity_points:
            if self.container.contain(point, physics):
                return False
        return True

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("not_contain_v")
class NotContainVCondition(Condition):
    """
    Check if the container does not contain the target entities.
    params:
        container: the container to not contain the target entities
        entities: the target entities to be not contained
    """

    def __init__(self, container, entities, **kwargs):
        super().__init__()
        self.entities_mjcf = None
        assert container is not None, "container must be provided"
        self.container = container
        self.entities = entities
        self.kwargs = kwargs

    def is_met(self, physics=None):
        if isinstance(self.entities[-1], Entity):
            self.entities_mjcf = [entity.mjcf_model.worldbody for entity in self.entities]
        entity_points = [physics.bind(entity_mjcf).xpos for entity_mjcf in self.entities_mjcf]
        entity_velocity = [physics.bind(entity_mjcf).cvel for entity_mjcf in self.entities_mjcf]

        for point in entity_points:
            contain_condition = self.container.contain(point, physics, **self.kwargs)
        for vel in entity_velocity:
            stationary_condition = self.container.stationary(vel, physics, th=0.01, **self.kwargs)
        if not contain_condition and stationary_condition:
            return True
        return False

    def met_progress(self, physics=None):
        # TODO: return the progress of the condition
        return super().met_progress(physics)


@register.add_condition("is_grasped")
class IsGraspedCondition(Condition):
    """
    Check if the target entities are grasped
    """

    def __init__(self, entities, robot):
        self.entities = entities
        self.robot = robot

    def is_met(self, physics=None):
        for entity in self.entities:
            # print("is_grasped", entity.is_grasped(physics, self.robot))
            if not entity.is_grasped(physics, self.robot):
                return False
        return True


@register.add_condition("press_button")
class ButtonPressedCondition(Condition):
    """
    Check if the button is pressed
    """

    def __init__(self, target_button):
        self.button = target_button

    def is_met(self, physics=None):
        return self.button.is_pressed()


@register.add_condition("on")
class OnCondition(Condition):
    """
    Check if the target entities are on the target surface.
    In most of cases, only on entity in entities.
    """

    def __init__(self, entities, container):
        self.entities = entities
        self.container = container

    def is_met(self, physics=None):
        contacts = physics.data.contact

        container_geoms_id = [physics.bind(geom).element_id for geom in self.container.geoms]
        container_geoms_xpos = [physics.bind(geom).xpos for geom in self.container.geoms]
        max_xpos_z = max([xpos[-1] for xpos in container_geoms_xpos])
        for entity in self.entities:
            is_contacted = False
            entity_geom_ids = [physics.bind(geom).element_id for geom in entity.geoms]
            entity_xpos = physics.bind(entity.mjcf_model.worldbody).xpos
            # z position detection
            if entity_xpos[-1] <= max_xpos_z:
                return False
            # on contact detection
            for contact in contacts:
                if (contact.geom1 in container_geoms_id and contact.geom2 in entity_geom_ids) or \
                        (contact.geom2 in entity_geom_ids and contact.geom1 in container_geoms_id):
                    is_contacted = True
                    break
            if is_contacted is False:
                return False
        return True


@register.add_condition("above")
class AboveCondition(Condition):
    """
    Entity above the platform/container condition. Usually used for the entity is above the flat container.
    params:
        target_entity: the target entity to be above the platform
        platform: the platform/flat container
    """

    def __init__(self, target_entity, platform):
        self.target_entity = target_entity
        self.platform = platform

    def is_met(self, physics):
        target_entity_xpos = physics.bind(self.target_entity.mjcf_model.worldbody).xpos
        z_platform = physics.bind(self.platform.mjcf_model.worldbody).xpos[-1]
        if target_entity_xpos[-1] < z_platform:
            return False
        else:
            point_to_check = target_entity_xpos
            point_to_check[-1] = z_platform + 0.01
            if self.platform.contain(point_to_check, physics): return True
        return False


@register.add_condition("pour")
class PourCondition(Condition):
    """
    The cup/shaker/other_entity is poured.
    As mujoco does not support the liquid simulation, use this condition to simplify.
    The condition is the top site z pos is lower than the bottom site z pos.
    params:
        target_entity: the target entity to be poured
        threshold: the threshold of z_top - z_bottom, to confirm whether the entity is poured.
    """

    def __init__(self, target_entity, threshold=0):
        self.target_entity = target_entity
        self.threshold = threshold

    def is_met(self, physics):
        top_site = self.target_entity.mjcf_model.worldbody.find("site", "top_site")
        bottom_site = self.target_entity.mjcf_model.worldbody.find("site", "bottom_site")
        top_site_xpos, bottom_site_xpos = physics.bind(top_site).xpos, physics.bind(bottom_site).xpos
        if (bottom_site_xpos[-1] - top_site_xpos[-1]) > self.threshold:
            return True
        else:
            return False


@register.add_condition("on_position")
class OnPositionCondition(Condition):
    """
    Entities should close to the target position within a certain distance
    params:
        entities: list, the target entities to be close to the target positions
        positions: list, the target positions
        tolerance_distance: the acceptable distance between the entities and the target positions
        dimension: the dimension of the target positions, 2 or 3
    """

    def __init__(self, entities, positions, tolerance_distance=0.03, dimension=2):
        self.entities = entities
        self.target_positions = positions
        self.tolerance_distance = tolerance_distance
        self.dimension = dimension

    def is_met(self, physics=None):
        for entity, target_pos in zip(self.entities, self.target_positions):
            entity_xpos = physics.bind(entity.mjcf_model.worldbody).xpos
            if distance(entity_xpos[:self.dimension], target_pos[:self.dimension]) > self.tolerance_distance:
                return False
        return True


@register.add_condition("contact")
class ContactCondition(Condition):
    """
    Check if the target entities are in contact with each other
    params:
        entity1: the first entity, Entity class of list of Entity
        entity2: the second entity, Entity class of list of Entity
    """

    def __init__(self, entity1, entity2):
        self.entity1 = entity1
        self.entity2 = entity2
        self.entity_geoms_id = None

    def is_met(self, physics=None):
        contacts = physics.data.contact
        if self.entity_geoms_id is None:
            self.entity_geoms_id = dict(
                entity1=[],
                entity2=[]
            )
            if isinstance(self.entity1, Entity):
                self.entity_geoms_id["entity1"].extend([physics.bind(geom).element_id for geom in self.entity1.geoms])
            elif isinstance(self.entity1, list):
                self.entity_geoms_id["entity1"].extend([physics.bind(geom).element_id for geom in self.entity1])

            if isinstance(self.entity2, Entity):
                self.entity_geoms_id["entity2"].extend([physics.bind(geom).element_id for geom in self.entity2.geoms])
            elif isinstance(self.entity2, list):
                self.entity_geoms_id["entity2"].extend([physics.bind(geom).element_id for geom in self.entity2])

        for contact in contacts:
            if (contact.geom1 in self.entity_geoms_id["entity1"] and contact.geom2 in self.entity_geoms_id[
                "entity2"]) or \
                    (contact.geom2 in self.entity_geoms_id["entity2"] and contact.geom1 in self.entity_geoms_id[
                        "entity1"]):
                return True
        return False


@register.add_condition("joint_in_range")
class JointInRangeCondition(Condition):
    """
    The target joint should be in specific range.
    Params:
        entities: the target entities, list of Entity with a single joint (hinge or slide)
        target_pos_range: the target position range
    """

    def __init__(self, entities, target_pos_range):
        self.entities = entities
        self.target_pos_range = target_pos_range

    def is_met(self, physics=None):
        for entity in self.entities:
            joints = entity.joints
            assert len(joints) == 1, "The number of joints should be equal to the target position range"
            if physics.bind(joints[-1]).qpos < self.target_pos_range[0] or physics.bind(joints[-1]).qpos > \
                    self.target_pos_range[1]:
                return False
        return True


@register.add_condition("is_open")
class IsOpenCondition(Condition):
    """
    Check if the container's main openable part (knob/handle etc.) is open, once met, always met.
    params:
        container: the target container (e.g. "sink_0"/"stove_0", resolved from str automatically)
        joint_name: optional knob body name (e.g. "knob_front_right"), only for Stove-like
                    containers with multiple knobs; if None, calls container.is_open(physics)
        angle_th: open threshold in degrees, only used when joint_name is given
    """

    def __init__(self, container, joint_name=None, angle_th=45.0, **kwargs):
        assert container is not None, "container must be provided"
        self.container = container
        self.joint_name = joint_name
        self.angle_th = angle_th
        self.condition_has_been_met = False
        self.kwargs = kwargs

    def is_met(self, physics=None):
        if self.condition_has_been_met:  # once met, always met
            return True
        if self.joint_name is None:
            met = self.container.is_open(physics)
        else:
            met = self.container.is_open(physics, self.joint_name) if self.angle_th is None \
                else self.container.is_open(physics, self.joint_name, angle_th=self.angle_th)
        self.condition_has_been_met = bool(met)
        return self.condition_has_been_met

    def check_open_readonly(self, physics=None):
        """
        Read-only probe of the current open/closed state; does not write condition_has_been_met.
        Used by the get_entity_condition_status query path so queries have no side effects
        (is_met advances the once-met lock state, which the query path must not call).
        """
        if self.condition_has_been_met:  # once met, always met
            return True
        if self.joint_name is None:
            return bool(self.container.is_open(physics))
        if self.angle_th is None:
            return bool(self.container.is_open(physics, self.joint_name))
        return bool(self.container.is_open(physics, self.joint_name, angle_th=self.angle_th))

    def met_progress(self, physics=None):
        return 1.0 if self.is_met(physics) else 0.0


@register.add_condition("lift")
class LiftCondition(Condition):
    """
    The entity should be lifted above the target height.
    params:
        entities: the target entities to be lifted
        target_height: the target height to achieve
    """

    def __init__(self, entities, target_height):
        self.entities = entities
        self.target_height = target_height

    def is_met(self, physics=None):
        for entity in self.entities:
            entity_xpos = physics.bind(entity.mjcf_model.worldbody).xpos
            if entity_xpos[-1] < self.target_height:
                return False
        return True


class ConditionSet:
    """
    A set of conditions, the condition set is met only when all the conditions are satisfied simutanously.
    """

    def __init__(self, conditions):
        self.conditions = conditions

    def __len__(self):
        return len(self.conditions)

    def is_met(self, physics=None):
        conditions_are_met = [condition.is_met(physics) for condition in self.conditions]
        return all(conditions_are_met)

    def add(self, condition):
        self.conditions.append(condition)

    def met_progress(self, physics=None):
        """
        compute the progress of the condition set.
        Return the ratio of the conditions that are met and those conditions are met.
        """
        conditions_are_met = [condition.is_met(physics) for condition in self.conditions]
        met_conditions = []
        for condition, met in zip(self.conditions, conditions_are_met):
            if met: met_conditions.append(condition)

        # RED = "\033[91m"
        # RESET = "\033[0m"
        score = sum(conditions_are_met) / len(conditions_are_met)
        # if score > 0:  # only print when there is progress, to avoid spam
        #     for condition, met in zip(self.conditions, conditions_are_met):
        #         print(f"{RED}[DEBUG ConditionSet.met_progress] {condition.__class__.__name__} | is_met={met}{RESET}")
        #     print(f"{RED}[DEBUG ConditionSet.met_progress] score={score:.3f}{RESET}")

        return score, conditions_are_met

    def get_entity_condition_status(self, physics, entity_name: str) -> Optional[bool]:
        """
        Get the status of conditions related to an entity by its name (read-only query, no side effects).

        The top-level condition set has AND semantics: all conditions involving the entity
        must be satisfied to return True; first-match-wins is forbidden (old bug: when the
        same entity appeared in multiple top-level conditions, only the first was checked).
        Composite members (AsynSequenceCondition / OrCondition) delegate via
        _check_entity_in_condition to their own get_entity_condition_status, so the
        top-level traversal logic stays in sync with substructure implementations;
        entity-irrelevant conditions like is_open are naturally skipped since they
        contain no entity names.

        Args:
            physics: the physics environment
            entity_name: the entity name (e.g. "lemon_0")

        Returns:
            bool: the aggregated status over all conditions/structures involving the entity
            None: if no condition related to the entity was found
        """
        # Top-level AND: aggregate all top-level results hit by the entity, rather than returning on the first hit
        results = []
        for condition in self.conditions:
            result = self._check_entity_in_condition(condition, physics, entity_name)
            if result is not None:
                results.append(result)
        if not results:
            return None
        return all(results)

    def _check_entity_in_condition(self, condition, physics, entity_name: str) -> Optional[bool]:
        """
        Query the entity's status within a single condition, delegating to the shared query
        function _query_entity_in_condition at the end of the file so that the top level
        and substructures use the same judgment logic:
        - Composite conditions (AsynSequenceCondition / OrCondition) and nested ConditionSets
          define their query semantics via their own get_entity_condition_status;
        - Leaf conditions call is_met only after matching by entity name; return None otherwise.
        """
        return _query_entity_in_condition(condition, physics, entity_name)


@register.add_condition("asyn_sequence")
class AsynSequenceCondition(Condition):
    """
    A time sequence of conditions, the condition is met only when all the sub-conditions are satisfied asynchronously.
    Different with single condition set, the sub-conditions' met are maintained in a member value.
    params:
        condition_sets: a list of ConditionSet, each ConditionSet contains a list of conditions.

    """

    def __init__(self, condition_sets, ordered_indices=None):
        assert isinstance(condition_sets, list) and isinstance(condition_sets[0],
                                                               ConditionSet), "condition_set should be a list of condition_set"
        self.condition_has_been_met = [False for _ in range(len(condition_sets))]
        self.condition_progress_scores = [0.0 for _ in range(len(condition_sets))]  # Persist the historical max instantaneous score of each ConditionSet
        self.condition_sets = condition_sets
        # ordered_indices: a list/tuple nesting structure; ordered inside lists, unordered inside tuples
        # e.g. [2, 3] means index 2 must precede index 3; [2, (3, 4)] means complete 2 first, then 3 and 4 in any order
        self.ordered_indices = ordered_indices

    def _get_prerequisites(self, i, structure):
        """
        Find index i in the ordered_indices structure and return the set of its prerequisite indices.
        Ordered inside lists (the previous element is a prerequisite); unordered inside tuples (no prerequisite).
        Returns None if not found (i is not under ordering constraints, no prerequisite check needed).
        """
        if not isinstance(structure, (list, tuple)):
            return None
        for pos, item in enumerate(structure):
            if item == i:
                # Found: ordered inside a list, the prerequisite is all leaves at position pos-1; unordered inside a tuple, no prerequisite
                if isinstance(structure, list) and pos > 0:
                    return self._get_all_leaves(structure[pos - 1])
                else:
                    return set()
            elif isinstance(item, (list, tuple)):
                # Recurse into the substructure to find it
                result = self._get_prerequisites(i, item)
                if result is not None:
                    # Found; also add the prerequisites of item itself within the current structure
                    if isinstance(structure, list) and pos > 0:
                        return result | self._get_all_leaves(structure[pos - 1])
                    else:
                        return result
        return None  # not found

    def _get_all_leaves(self, structure):
        """Recursively collect the set of all leaf indices (ints) in the structure."""
        if isinstance(structure, int):
            return {structure}
        result = set()
        for item in structure:
            result |= self._get_all_leaves(item)
        return result

    def _is_unlocked(self, i):
        """Check whether stage i is unlocked (its prerequisite stages are done, or it needs no prerequisites)."""
        if self.ordered_indices is None:
            return True
        prereqs = self._get_prerequisites(i, self.ordered_indices)
        if prereqs is None:
            return True
        return all(self.condition_has_been_met[p] for p in prereqs)

    def is_met(self, physics=None):
        for i, condition in enumerate(self.condition_sets):
            if not self.condition_has_been_met[i]:
                # Check the ordering constraint: if i is in ordered_indices and its prerequisites are incomplete, skip it
                if not self._is_unlocked(i):
                    continue
                if condition.is_met(physics):
                    self.condition_has_been_met[i] = True
            # Update the historical max instantaneous score each step, only for unlocked stages
            if self._is_unlocked(i):
                instant_score, _ = self.condition_sets[i].met_progress(physics)
                self.condition_progress_scores[i] = max(self.condition_progress_scores[i], instant_score)
        if all(self.condition_has_been_met):
            return True
        else:
            return False

    def met_progress(self, physics=None):
        """
        Compute the progress score, taking ordered_indices into account:
        - Unlocked stages: use the max of the current instantaneous progress and the historical max progress
        - Locked stages: progress counts as 0 (excluded)
        - No ordered_indices (unordered): all stages are treated as unlocked
        """
        unlocked_scores = []
        unlocked_indices = []

        for i, condition_set in enumerate(self.condition_sets):
            if self._is_unlocked(i):
                progress_score, _ = condition_set.met_progress(physics)
                # Use the larger of the historical max score and the current instantaneous score
                effective_score = max(self.condition_progress_scores[i], progress_score)
                unlocked_scores.append(effective_score)
                unlocked_indices.append(i)

        if not unlocked_scores:
            return 0.0, self.condition_has_been_met

        return np.mean(unlocked_scores), self.condition_has_been_met

    def get_entity_condition_status(self, physics, entity_name: str) -> Optional[bool]:
        """
        Query the entity's status within this asynchronous sequence (read-only, no side effects),
        judged with "active stage" semantics:

        1. The entity does not participate in any stage of the sequence -> None;
        2. All stages are complete -> True;
        3. Take the first "unlocked and incomplete" active stage
           (condition_has_been_met[i]==False and _is_unlocked(i)),
           and return the instantaneous is_met of the sub-conditions containing the entity in
           that active stage (AND when there are several); if the entity is not in the current
           active stage (its own stage is not yet unlocked) -> False.

        Must NOT degrade to "query any stage": if the entity already satisfies the placement of
        a later stage (e.g. steak is already in plate) but the active stage is still pan, it must
        return False -- this is the core of the stage semantics.
        Note: stage advancement (writing condition_has_been_met) is done solely by the is_met
        path called every step by the eval main loop; this query only reads that state.

        Side-effect note: this method must not call AsynSequenceCondition.is_met (it advances
        condition_has_been_met / condition_progress_scores); it only reads
        condition_has_been_met / ordered_indices to compute _is_unlocked, and only calls
        is_met on leaf conditions (verified that leaves only do read-only physics checks and
        do not semantically write state).

        Args:
            physics: the physics environment
            entity_name: the entity name (e.g. "lemon_0")

        Returns:
            bool: whether the entity is in / satisfies the state it should satisfy
            None: the entity does not participate in this sequence
        """
        # Whether the entity participates in this sequence (any sub-condition of any stage contains the entity)
        involved = any(
            _entity_name_in_condition(sub_condition, entity_name)
            for condition_set in self.condition_sets
            for sub_condition in condition_set.conditions
        )
        if not involved:
            return None

        # All stages are complete -> True
        if all(self.condition_has_been_met):
            return True

        # Locate the first active stage: incomplete and unlocked
        for i, condition_set in enumerate(self.condition_sets):
            if self.condition_has_been_met[i]:
                continue
            if not self._is_unlocked(i):
                continue
            # Within the active stage, only look at the entity's own sub-conditions (a stage has AND semantics, so take AND);
            # entity-irrelevant conditions like is_open are naturally skipped since they contain no entity names
            results = []
            for sub_condition in condition_set.conditions:
                result = self._check_entity_in_condition(sub_condition, physics, entity_name)
                if result is not None:
                    results.append(result)
            if results:
                return all(results)
            # The entity is not in the current active stage: its later stage is not yet unlocked; reading ahead is forbidden
            return False

        # Defensive branch: as long as incomplete stages exist, the earliest one is necessarily unlocked,
        # so execution should never reach here
        return False

    def _check_entity_in_condition(self, condition, physics, entity_name: str) -> Optional[bool]:
        """
        Query the entity's status within a single sub-condition (a stage member), delegating to the
        shared query function _query_entity_in_condition, consistent with the top-level logic.
        """
        return _query_entity_in_condition(condition, physics, entity_name)


@register.add_condition("or")
class OrCondition(Condition):
    """
    Any one of the conditions in the condition set is met.
    params:
        condition_sets: a list of ConditionSet, each ConditionSet contains a list of conditions.
    """

    def __init__(self, condition_sets):
        assert isinstance(condition_sets, list) and isinstance(condition_sets[0],
                                                               ConditionSet), "condition_sets should be a list of condition sets"
        self.condition_sets = condition_sets
        # print("condition_sets:", self.condition_sets)
        # for con in self.condition_sets:
        #     for c in con.conditions:
        #         for entity in c.entities:
        #             print("entityname_or:", entity.name)

    def is_met(self, physics=None):
        return any([condition_set.is_met(physics) for condition_set in self.condition_sets])

    def met_progress(self, physics=None):
        """
        Compute the completion progress of the OrCondition.
        For an OR condition, return the highest progress among all condition sets
        (since satisfying any one condition set counts as success).

        Returns:
            tuple: (max_progress, best_met_conditions)
                - max_progress: the max progress across all condition sets (0.0~1.0)
                - best_met_conditions: the met-conditions list of the condition set with the max progress
        """
        if not self.condition_sets:
            return 0.0, []

        max_progress = 0.0
        best_met_conditions = []

        for condition_set in self.condition_sets:
            progress, met_conditions = condition_set.met_progress(physics)
            if progress > max_progress:
                max_progress = progress
                best_met_conditions = met_conditions
            # If a fully satisfied condition set has already been found, return directly
            if progress >= 1.0:
                return 1.0, met_conditions

        return max_progress, best_met_conditions

    def get_entity_condition_status(self, physics, entity_name: str) -> Optional[bool]:
        """
        Query the entity's status within this OR condition (read-only, no side effects), with OR semantics:

        - In any branch containing the entity, if the sub-conditions of "the entity itself" are
          satisfied -> True;
        - None of the branches containing the entity are satisfied -> False;
        - The entity does not appear in any branch -> None.

        Note that each branch is itself a ConditionSet (AND), but a single-entity query only
        aggregates the entity's own sub-conditions; other entities' conditions within a branch
        are irrelevant to this query -- the same entity may map to different containers in
        different branches, and a valid placement in any branch should be judged True
        (old bug: first-branch-wins, valid placements in the second branch were misjudged False).

        Args:
            physics: the physics environment
            entity_name: the entity name (e.g. "lemon_0")

        Returns:
            bool: whether the entity is in / satisfies the state it should satisfy
            None: the entity does not participate in this OR condition
        """
        involved = False
        for condition_set in self.condition_sets:
            # AND over all sub-conditions of the entity itself within the branch
            results = []
            for sub_condition in condition_set.conditions:
                result = self._check_entity_in_condition(sub_condition, physics, entity_name)
                if result is not None:
                    results.append(result)
            if not results:
                continue  # this branch does not contain the entity
            involved = True
            if all(results):
                return True  # any branch satisfied means the OR holds
        return False if involved else None

    def _check_entity_in_condition(self, condition, physics, entity_name: str) -> Optional[bool]:
        """
        Query the entity's status within a single sub-condition (a branch member), delegating to
        the shared query function _query_entity_in_condition, consistent with the top-level logic.
        """
        return _query_entity_in_condition(condition, physics, entity_name)


def _entity_name_is_open_container(condition, entity_name: str) -> bool:
    """
    Check whether the entity name is the body or a part of the container judged by an is_open condition.
    When pick's match is body-level it carries the entity prefix (e.g. stove_0/knob_front_right),
    so match against the container name (stove_0) by equality or the "container_name/" prefix.
    """
    cname = getattr(condition.container, 'name', condition.container)
    if not isinstance(cname, str) or not cname:
        return False
    return entity_name == cname or entity_name.startswith(cname + '/')


def _entity_name_in_condition(condition, entity_name: str) -> bool:
    """
    Pure entity-name matching: check whether an entity participates in a condition/structure;
    read-only, does not call is_met.
    Used by AsynSequenceCondition / OrCondition to determine entity involvement.
    """
    # Composite conditions: recursively check the stages/branches
    if isinstance(condition, (AsynSequenceCondition, OrCondition)):
        return any(
            _entity_name_in_condition(sub_condition, entity_name)
            for condition_set in condition.condition_sets
            for sub_condition in condition_set.conditions
        )
    if isinstance(condition, ConditionSet):
        return any(_entity_name_in_condition(sub_condition, entity_name) for sub_condition in condition.conditions)
    # is_open: picking the container body or its parts counts as participating in the condition
    if isinstance(condition, IsOpenCondition):
        return _entity_name_is_open_container(condition, entity_name)
    # Leaf conditions: match against the entities attribute
    if hasattr(condition, 'entities') and condition.entities:
        for entity in condition.entities:
            if entity is None:
                continue
            name = entity.name if hasattr(entity, 'name') else entity
            if name == entity_name:
                return True
    return False


def _check_leaf_entity_met(condition, physics, entity) -> bool:
    """
    Single-entity-granularity check for a leaf condition.

    Background: when a multi-entity contain-type condition (e.g. contain(pan, [steak, potato]))
    has an overall is_met of False (potato not yet in place), querying steak under the original
    logic would also yield False, wrongly penalizing entities already placed correctly; whereas
    the semantics of this query is "has the entity of this single pick reached its container",
    so it should be judged at single-entity granularity.

    Implementation: only when the condition has a container attribute and contains multiple
    entities, temporarily shrink entities to the single matched entity and reuse the original
    is_met (keeping the judgment parameters of the contain-family variants -- z_th/vel_th/
    check_xquat and the inverted semantics of not_contain -- exactly the same as the original
    logic), and restore immediately after the check; single-entity conditions and non-contain
    conditions keep their original behavior.
    Note: the eval main loop is single-threaded and serial, so there is no concurrency risk
    during the swap; try/finally guarantees restoration even on exception.
    """
    if hasattr(condition, 'container') and getattr(condition, 'entities', None) and len(condition.entities) > 1:
        original_entities = condition.entities
        try:
            condition.entities = [entity]
            return condition.is_met(physics)
        finally:
            condition.entities = original_entities
    return condition.is_met(physics)


def _query_entity_in_condition(condition, physics, entity_name: str) -> Optional[bool]:
    """
    Query the entity's status within a single condition (possibly composite), returning Optional[bool]:
    - ConditionSet / AsynSequenceCondition / OrCondition: delegate to their own
      get_entity_condition_status (composite conditions know how to query themselves,
      avoiding the top-level traversal logic drifting out of sync with substructure
      implementations);
    - Leaf conditions: call their is_met only when the entity name matches, else return None.

    Side-effect note (read-only check): leaf conditions' is_met has been verified to only do
    read-only physics checks (the contain family only lazily caches mjcf references and does
    not change any judgment state).
    """
    # Composite conditions and condition sets: delegate to their own query implementations
    if isinstance(condition, (ConditionSet, AsynSequenceCondition, OrCondition)):
        return condition.get_entity_condition_status(physics, entity_name)
    # Leaf conditions: match by entity name
    if hasattr(condition, 'entities') and condition.entities:
        for entity in condition.entities:
            if entity is None:
                continue
            name = entity.name if hasattr(entity, 'name') else entity
            if name == entity_name:
                return _check_leaf_entity_met(condition, physics, entity)
    # is_open: a pick of the container body/a part (e.g. "stove_0/knob_front_right")
    # returns the read-only probe of the container's open state, without advancing the once-met lock
    if isinstance(condition, IsOpenCondition):
        if _entity_name_is_open_container(condition, entity_name):
            return condition.check_open_readonly(physics)
    return None


# ==================== Fine-grained leaf scoring (new, does not affect the existing met_progress) ====================

def _collect_leaf_conditions(node, leaves):
    """
    Recursively collect the bottom-level leaf conditions of a condition tree
    (traversal pattern follows _entity_name_in_condition).
    ConditionSet / AsynSequenceCondition / OrCondition are just containers, drill down;
    everything else (ContainCondition, IsOpenCondition, is_grasped, etc.) is treated as a leaf.
    Identical instances are deduplicated automatically (no double counting).
    """
    if isinstance(node, (AsynSequenceCondition, OrCondition)):
        for condition_set in node.condition_sets:
            _collect_leaf_conditions(condition_set, leaves)
    elif isinstance(node, ConditionSet):
        for sub in node.conditions:
            _collect_leaf_conditions(sub, leaves)
    else:
        if not any(node is leaf for leaf in leaves):
            leaves.append(node)


def _describe_leaf(leaf):
    """Generate a short description of a leaf, for debugging/logging."""
    class_name = leaf.__class__.__name__
    container = getattr(leaf, "container", None)
    cname = getattr(container, "name", container) if container is not None else None
    if cname is not None:
        entities = getattr(leaf, "entities", None) or []
        enames = [getattr(e, "name", e) for e in entities if e is not None]
        return f"{class_name}({cname}, {enames})"
    return class_name


def get_leaf_met_progress(root, physics=None):
    """
    Fine-grained scoring: each bottom-level leaf condition gets one vote, based on the
    instantaneous read-only True/False.

    - Ordering (asyn_sequence's ordered/unlocking) and OR branch semantics do not participate
      in the judgment: if an entity is placed into plate, contain(plate) reads as True,
      regardless of the order the task requires;
    - Read-only guarantee: the contain-family leaves' is_met only does physics checks (lazily
      caching mjcf references); IsOpenCondition does not call its is_met (which would trigger
      the once-met state write) and instead uses check_open_readonly for a side-effect-free
      probe; no composite condition's is_met is called, so the asyn condition_has_been_met /
      stage-lock state is never advanced.

    Args:
        root: the root of the condition tree (usually env.task.conditions, the top-level ConditionSet)
        physics: the physics environment

    Returns:
        tuple: (score, details)
            score: float, met leaves / total leaves (0.0 when there are no leaves)
            details: list[(description, met or not)], in tree traversal order
    """
    leaves = []
    _collect_leaf_conditions(root, leaves)
    if not leaves:
        return 0.0, []

    details = []
    met_count = 0
    for leaf in leaves:
        if isinstance(leaf, IsOpenCondition):
            met = leaf.check_open_readonly(physics)  # read-only, does not advance the once-met lock
        else:
            met = bool(leaf.is_met(physics))
        if met:
            met_count += 1
        details.append((_describe_leaf(leaf), met))

    score = met_count / len(leaves)
    return score, details
