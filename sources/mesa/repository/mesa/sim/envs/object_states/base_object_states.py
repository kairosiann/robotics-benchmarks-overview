import numpy as np
import robosuite.utils.transform_utils as transform_utils

from mesa.sim.envs.utils import angle_from_quaternion


class BaseObjectState:
    def __init__(self):
        pass

    def get_geom_state(self):
        raise NotImplementedError

    def check_contact(self, other):
        raise NotImplementedError

    def check_contain(self, other):
        raise NotImplementedError

    def get_joint_state(self):
        raise NotImplementedError

    def is_open(self):
        raise NotImplementedError

    def is_close(self):
        raise NotImplementedError

    def get_size(self):
        raise NotImplementedError

    def check_ontop(self, other):
        raise NotImplementedError

    def check_grasp(self, robot_index=None):
        raise NotImplementedError


class ObjectState(BaseObjectState):
    def __init__(self, env, object_name, joints=None, is_fixture=False, stack_info=None):
        self.env = env
        self.object_name = object_name
        self.joints = joints
        self.is_fixture = is_fixture
        self.stack_info = stack_info
        self.query_dict = (
            self.env.fixtures_dict if self.is_fixture else self.env.objects_dict
        )
        self.object_state_type = "object"
        self.has_turnon_affordance = hasattr(
            self.env.get_object(self.object_name), "turn_on"
        )

    def get_geom_state(self):
        object_pos = self.env.sim.data.body_xpos[self.env.obj_body_id[self.object_name]]
        object_quat = self.env.sim.data.body_xquat[
            self.env.obj_body_id[self.object_name]
        ]
        return {"pos": object_pos, "quat": object_quat}

    def check_contact(self, other):
        object_1 = self.env.get_object(self.object_name)
        object_2 = self.env.get_object(other.object_name)
        return self.env.check_contact(object_1, object_2)

    def check_contain(self, other):
        object_1 = self.env.get_object(self.object_name)
        object_1_position = self.env.sim.data.body_xpos[
            self.env.obj_body_id[self.object_name]
        ]
        # x.env.sim.data.body_xpos[x.env.obj_body_id[x.object_name]]
        object_2_position = self.env.sim.data.body_xpos[
            self.env.obj_body_id[other.object_name]
        ]
        return object_1.in_box(object_1_position, object_2_position)

    def get_joint_state(self):
        # Return None if joint state does not exist
        joint_states = []
        joints = (
            self.env.get_object(self.object_name).joints
            if self.joints is None
            else self.joints
        )
        for joint in joints:
            qpos_addr = self.env.sim.model.get_joint_qpos_addr(joint)
            joint_states.append(self.env.sim.data.qpos[qpos_addr])
        return joint_states

    def check_ontop(self, other):
        this_object = self.env.get_object(self.object_name)
        this_object_id = self.env.obj_body_id[self.object_name]
        this_object_position = self.env.sim.data.body_xpos[this_object_id]
        other_object_id = self.env.obj_body_id[other.object_name]
        other_object_position = self.env.sim.data.body_xpos[other_object_id]

        # 2D oriented bounding box (OBB) containment test in the ground plane,
        # factored out into a helper for reuse and clarity.
        this_object_quat = self.env.sim.data.body_xquat[this_object_id]
        in_2d_bbox = self.is_in_2d_bbox(
            center_pos=this_object_position,
            other_pos=other_object_position,
            quat=this_object_quat,
            rotation_axis=this_object.rotation_axis,
            horizontal_offset=this_object.horizontal_offset,
        )

        # Original vertical + contact condition, now gated by 2D bbox membership
        # or a supporting contact normal, plus low velocity (object stationary).
        is_above_in_z = this_object_position[2] <= other_object_position[2]
        is_touching = self.check_contact(other)
        other_is_stationary = self.is_stationary(other_object_id, threshold=0.1, ignore_angular=True)
        this_is_stationary = self.is_stationary(this_object_id, threshold=0.1, ignore_angular=False)

        has_contact_normal = self.has_supporting_contact_normal(other) if is_touching else False
        lateral_or_normal = in_2d_bbox or has_contact_normal

        return (
            is_above_in_z
            and is_touching
            and lateral_or_normal
            and other_is_stationary
            and this_is_stationary
        )

    def set_joint(self, qpos=1.5):
        joints = (
            self.env.get_object(self.object_name).joints
            if self.joints is None
            else self.joints
        )
        for joint in joints:
            self.env.sim.data.set_joint_qpos(joint, qpos)

    def is_open(self):
        joints = (
            self.env.get_object(self.object_name).joints
            if self.joints is None
            else self.joints
        )
        for joint in joints:
            qpos_addr = self.env.sim.model.get_joint_qpos_addr(joint)
            qpos = self.env.sim.data.qpos[qpos_addr]
            if self.env.get_object(self.object_name).is_open(qpos):
                return True
        return False

    def is_close(self):
        joints = (
            self.env.get_object(self.object_name).joints
            if self.joints is None
            else self.joints
        )
        for joint in joints:
            qpos_addr = self.env.sim.model.get_joint_qpos_addr(joint)
            qpos = self.env.sim.data.qpos[qpos_addr]
            if not (self.env.get_object(self.object_name).is_close(qpos)):
                return False
        return True

    def turn_on(self):
        joints = (
            self.env.get_object(self.object_name).joints
            if self.joints is None
            else self.joints
        )
        for joint in joints:
            qpos_addr = self.env.sim.model.get_joint_qpos_addr(joint)
            qpos = self.env.sim.data.qpos[qpos_addr]
            if self.env.get_object(self.object_name).turn_on(qpos):
                return True
        return False

    def turn_off(self):
        joints = (
            self.env.get_object(self.object_name).joints
            if self.joints is None
            else self.joints
        )
        for joint in joints:
            qpos_addr = self.env.sim.model.get_joint_qpos_addr(joint)
            qpos = self.env.sim.data.qpos[qpos_addr]
            if not (self.env.get_object(self.object_name).turn_off(qpos)):
                return False
        return True

    def update_state(self):
        if self.has_turnon_affordance:
            self.turn_on()

    def check_grasp(self, robot_index=None):
        obj = self.env.get_object(self.object_name)
        if robot_index is not None:
            robot = self.env.robots[robot_index]
            return self.env._check_grasp(gripper=robot.gripper, object_geoms=obj)
        for robot in self.env.robots:
            if self.env._check_grasp(gripper=robot.gripper, object_geoms=obj):
                return True
        return False

    def is_stationary(self, object_id, threshold=0.1, ignore_angular=True):
        object_velocity = self.env.sim.data.cvel[object_id]
        if ignore_angular:
            linear_velocity = object_velocity[3:]
            return np.linalg.norm(linear_velocity) < threshold
        else:
            return np.linalg.norm(object_velocity) < threshold

    def _get_object_geom_ids(self, obj_body_id):
        sim = self.env.sim
        nbody = sim.model.nbody
        children = [[] for _ in range(nbody)]
        for bid in range(1, nbody):
            parent = sim.model.body_parentid[bid]
            if parent >= 0:
                children[parent].append(bid)

        subtree = {obj_body_id}
        stack = [obj_body_id]
        while stack:
            body_id = stack.pop()
            for child in children[body_id]:
                if child not in subtree:
                    subtree.add(child)
                    stack.append(child)

        return [
            gid
            for gid in range(sim.model.ngeom)
            if sim.model.geom_bodyid[gid] in subtree
        ]

    def has_supporting_contact_normal(self, other, threshold=0.5):
        sim = self.env.sim
        if sim.data.ncon == 0:
            return False

        this_object_id = self.env.obj_body_id[self.object_name]
        other_object_id = self.env.obj_body_id[other.object_name]
        this_geom_ids = set(self._get_object_geom_ids(this_object_id))
        other_geom_ids = set(self._get_object_geom_ids(other_object_id))

        if not this_geom_ids or not other_geom_ids:
            return False

        for i in range(sim.data.ncon):
            contact = sim.data.contact[i]
            geom1 = int(contact.geom1)
            geom2 = int(contact.geom2)
            if geom1 in this_geom_ids and geom2 in other_geom_ids:
                normal = np.asarray(contact.frame).reshape(-1)
                if normal.size >= 3 and normal[2] <= -threshold:
                    return True
            elif geom1 in other_geom_ids and geom2 in this_geom_ids:
                normal = np.asarray(contact.frame).reshape(-1)
                if normal.size >= 3 and normal[2] >= threshold:
                    return True

        return False

    def is_in_2d_bbox(
        self,
        center_pos: np.ndarray,
        other_pos: np.ndarray,
        quat: np.ndarray,
        rotation_axis: str,
        horizontal_offset: np.ndarray,
    ) -> bool:
        """
        Check whether the 2D projection of `other_pos` lies inside the oriented
        bounding box defined around `center_pos`.

        The box is defined by:
          - `center_pos`: 3D position of the box center in world frame
          - `quat`: orientation quaternion of the object (w, x, y, z)
          - `rotation_axis`: axis ("x", "y" or "z") used to compute in-plane rotation
          - `horizontal_offset`: 3D offset to a corner of the horizontal radius site
            in the object's local frame (we use its x-y components as half-extents)
        """
        # Compute in-plane rotation angle from quaternion and axis.
        theta = angle_from_quaternion(quat, rotation_axis)
        half_extents = np.abs(horizontal_offset[:2])

        # Project to 2D in world frame.
        center_2d = center_pos[:2]
        other_2d = other_pos[:2]

        # Relative position in world frame (2D).
        rel_pos_2d = other_2d - center_2d

        # Rotate into the object's local 2D frame by undoing its yaw so that
        # the bounding box becomes axis-aligned.
        cos_t, sin_t = np.cos(-theta), np.sin(-theta)
        rot_mat = np.array([[cos_t, -sin_t], [sin_t, cos_t]])
        rel_local_2d = rot_mat @ rel_pos_2d

        return (
            -half_extents[0] <= rel_local_2d[0] <= half_extents[0]
            and -half_extents[1] <= rel_local_2d[1] <= half_extents[1]
        )


class SiteObjectState(BaseObjectState):
    """
    This is to make site based objects to have the same API as normal Object State.
    """

    def __init__(self, env, object_name, parent_name, is_fixture=False):
        self.env = env
        self.object_name = object_name
        self.parent_name = parent_name
        self.is_fixture = self.parent_name in self.env.fixtures_dict
        self.query_dict = (
            self.env.fixtures_dict if self.is_fixture else self.env.objects_dict
        )
        self.object_state_type = "site"

    def get_geom_state(self):
        object_pos = self.env.sim.data.get_site_xpos(self.object_name)
        object_quat = transform_utils.mat2quat(
            self.env.sim.data.get_site_xmat(self.object_name)
        )
        return {"pos": object_pos, "quat": object_quat}

    def check_contain(self, other):
        this_object = self.env.object_sites_dict[self.object_name]
        this_object_position = self.env.sim.data.get_site_xpos(self.object_name)
        this_object_mat = self.env.sim.data.get_site_xmat(self.object_name)

        other_object_position = self.env.sim.data.body_xpos[
            self.env.obj_body_id[other.object_name]
        ]
        
        # NOTE (AW) This is a hack to avoid marking a success in a bug case I encountered
        other_object_velocity = self.env.sim.data.cvel[self.env.obj_body_id[other.object_name]]
        if np.linalg.norm(other_object_velocity) > 100:
            return False

        return this_object.in_box(
            this_object_position, this_object_mat, other_object_position
        )

    def check_contact(self, other):
        """
        There is no dynamics for site objects, so we return true all the time.
        """
        return True

    def check_ontop(self, other):
        this_object = self.env.object_sites_dict[self.object_name]
        if hasattr(this_object, "under"):
            this_object_position = self.env.sim.data.get_site_xpos(self.object_name)
            this_object_mat = self.env.sim.data.get_site_xmat(self.object_name)
            other_object = self.env.get_object(other.object_name)
            other_object_position = self.env.sim.data.body_xpos[
                self.env.obj_body_id[other.object_name]
            ]

            parent_object = self.env.get_object(self.parent_name)
            if parent_object is None:
                return this_object.under(
                    this_object_position, this_object_mat, other_object_position
                )
            else:
                return this_object.under(
                    this_object_position, this_object_mat, other_object_position
                ) and self.env.check_contact(parent_object, other_object)
        else:
            return True

    def set_joint(self, qpos=1.5):
        for joint in self.env.object_sites_dict[self.object_name].joints:
            self.env.sim.data.set_joint_qpos(joint, qpos)

    def is_open(self):
        for joint in self.env.object_sites_dict[self.object_name].joints:
            qpos_addr = self.env.sim.model.get_joint_qpos_addr(joint)
            qpos = self.env.sim.data.qpos[qpos_addr]
            if self.env.get_object(self.parent_name).is_open(qpos):
                return True
        return False

    def is_close(self):
        for joint in self.env.object_sites_dict[self.object_name].joints:
            qpos_addr = self.env.sim.model.get_joint_qpos_addr(joint)
            qpos = self.env.sim.data.qpos[qpos_addr]
            if not (self.env.get_object(self.parent_name).is_close(qpos)):
                return False
        return True
    
    def check_grasp(self, robot_index=None):
        obj = self.env.get_object(self.object_name)
        if robot_index is not None:
            robot = self.env.robots[robot_index]
            return self.env._check_grasp(gripper=robot.gripper, object_geoms=obj)
        for robot in self.env.robots:
            if self.env._check_grasp(gripper=robot.gripper, object_geoms=obj):
                return True
        return False
