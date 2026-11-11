# Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the NVIDIA Source Code License [see LICENSE for details].

"""
MimicGen environment interface classes for basic robosuite environments.
"""
import numpy as np
import robosuite
import robosuite.utils.transform_utils as T

import mesa.mimicgen.utils.pose_utils as PoseUtils
from mesa.mimicgen.env_interfaces.base import MG_EnvInterface
from mesa.mimicgen.utils.misc_utils import get_controller


def _assert_supported_robosuite_version():
    assert (robosuite.__version__.split(".")[0] == "1")
    assert (robosuite.__version__.split(".")[1] >= "2")


def _controller_to_eef_pose(env, controller):
    """Return 4x4 EEF pose for a controller by reading its reference site."""
    ref_name = controller.ref_name
    site_id = env.sim.model.site_name2id(ref_name)
    pos = np.array(env.sim.data.site_xpos[site_id])
    rot = np.array(env.sim.data.site_xmat[site_id].reshape(3, 3))
    return PoseUtils.make_pose(pos, rot)


def _target_pose_to_action_with_controller(target_pose, get_eef_pose_fn, controller, relative=True):
    """Convert target EEF pose to action using a provided controller."""
    _assert_supported_robosuite_version()

    target_pos, target_rot = PoseUtils.unmake_pose(target_pose)

    curr_pose = get_eef_pose_fn()
    curr_pos, curr_rot = PoseUtils.unmake_pose(curr_pose)

    max_dpos = controller.output_max[0]
    max_drot = controller.output_max[3]

    if relative:
        delta_position = np.clip((target_pos - curr_pos) / max_dpos, -1., 1.)

        delta_rot_mat = target_rot.dot(curr_rot.T)
        delta_quat = T.mat2quat(delta_rot_mat)
        delta_rotation = T.quat2axisangle(delta_quat)
        delta_rotation = np.clip(delta_rotation / max_drot, -1., 1.)
        return np.concatenate([delta_position, delta_rotation])

    target_quat = T.mat2quat(target_rot)
    abs_rotation = T.quat2axisangle(target_quat)
    return np.concatenate([target_pos, abs_rotation])


def _action_to_target_pose_with_controller(action, get_eef_pose_fn, controller, relative=True):
    """Convert action to target EEF pose using a provided controller."""
    _assert_supported_robosuite_version()

    if not relative:
        target_pos = action[:3]
        target_quat = T.axisangle2quat(action[3:6])
        target_rot = T.quat2mat(target_quat)
    else:
        max_dpos = controller.output_max[0]
        max_drot = controller.output_max[3]

        delta_position = action[:3] * max_dpos
        delta_rotation = action[3:6] * max_drot

        curr_pose = get_eef_pose_fn()
        curr_pos, curr_rot = PoseUtils.unmake_pose(curr_pose)

        target_pos = curr_pos + delta_position
        delta_quat = T.axisangle2quat(delta_rotation)
        delta_rot_mat = T.quat2mat(delta_quat)
        target_rot = delta_rot_mat.dot(curr_rot)

    return PoseUtils.make_pose(target_pos, target_rot)


class RobosuiteInterface(MG_EnvInterface):
    """
    MimicGen environment interface base class for basic robosuite environments.
    """

    # Note: base simulator interface class must fill out interface type as a class property
    INTERFACE_TYPE = "robosuite"

    def get_robot_eef_pose(self):
        """
        Get current robot end effector pose. Should be the same frame as used by the robot end-effector controller.

        Returns:
            pose (np.array): 4x4 eef pose matrix
        """

        # OSC control frame is a MuJoCo site - just retrieve its current pose.
        # TODO: this should work fine for single-arm robots, but not for multi-arm robots.
        return _controller_to_eef_pose(self.env, get_controller(self.env))

    def target_pose_to_action(self, target_pose, relative=True):
        """
        Takes a target pose for the end effector controller and returns an action 
        (usually a normalized delta pose action) to try and achieve that target pose. 

        Args:
            target_pose (np.array): 4x4 target eef pose
            relative (bool): if True, use relative pose actions, else absolute pose actions

        Returns:
            action (np.array): action compatible with env.step (minus gripper actuation)
        """

        return _target_pose_to_action_with_controller(
            target_pose=target_pose,
            get_eef_pose_fn=self.get_robot_eef_pose,
            controller=get_controller(self.env),
            relative=relative,
        )

    def action_to_target_pose(self, action, relative=True):
        """
        Converts action (compatible with env.step) to a target pose for the end effector controller.
        Inverse of @target_pose_to_action. Usually used to infer a sequence of target controller poses
        from a demonstration trajectory using the recorded actions.

        Args:
            action (np.array): environment action
            relative (bool): if True, use relative pose actions, else absolute pose actions

        Returns:
            target_pose (np.array): 4x4 target eef pose that @action corresponds to
        """

        return _action_to_target_pose_with_controller(
            action=action,
            get_eef_pose_fn=self.get_robot_eef_pose,
            controller=get_controller(self.env),
            relative=relative,
        )

    def action_to_gripper_action(self, action):
        """
        Extracts the gripper actuation part of an action (compatible with env.step).

        Args:
            action (np.array): environment action

        Returns:
            gripper_action (np.array): subset of environment action for gripper actuation
        """

        # last dimension is gripper action
        return action[-1:]

    # robosuite-specific helper method for getting object poses
    def get_object_pose(self, obj_name, obj_type):
        """
        Returns 4x4 object pose given the name of the object and the type.

        Args:
            obj_name (str): name of object
            obj_type (str): type of object - either "body", "geom", or "site"

        Returns:
            obj_pose (np.array): 4x4 object pose
        """
        assert obj_type in ["body", "geom", "site"]

        if obj_type == "body":
            obj_id = self.env.sim.model.body_name2id(obj_name)
            obj_pos = np.array(self.env.sim.data.body_xpos[obj_id])
            obj_rot = np.array(self.env.sim.data.body_xmat[obj_id].reshape(3, 3))
        elif obj_type == "geom":
            obj_id = self.env.sim.model.geom_name2id(obj_name)
            obj_pos = np.array(self.env.sim.data.geom_xpos[obj_id])
            obj_rot = np.array(self.env.sim.data.geom_xmat[obj_id].reshape(3, 3))
        elif obj_type == "site":
            obj_id = self.env.sim.model.site_name2id(obj_name)
            obj_pos = np.array(self.env.sim.data.site_xpos[obj_id])
            obj_rot = np.array(self.env.sim.data.site_xmat[obj_id].reshape(3, 3))

        return PoseUtils.make_pose(obj_pos, obj_rot)
