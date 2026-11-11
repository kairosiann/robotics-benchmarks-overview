"""Per-robot-index arm interface for bimanual environments."""

from mesa.mimicgen.env_interfaces.robosuite import (
    _action_to_target_pose_with_controller,
    _controller_to_eef_pose,
    _target_pose_to_action_with_controller,
)


def _get_arm_controller(env, robot_index):
    """Return the OSC_POSE part controller for the given robot index."""
    # Each YAM arm runs a single OSC part that robosuite keys as "right" in its
    # composite controller, regardless of which physical arm (robot_index) it is.
    return env.robots[robot_index].composite_controller.part_controllers["right"]


class ArmInterface:
    """
    Thin interface to a single robot arm identified by ``robot_index``.
    """

    def __init__(self, env, robot_index):
        """
        Args:
            env: robosuite environment instance with ``env.robots``
            robot_index (int): 0 for the first robot (left), 1 for the second (right)
        """
        self.env = env
        self.robot_index = robot_index

    @property
    def controller(self):
        return _get_arm_controller(self.env, self.robot_index)

    def get_robot_eef_pose(self):
        """
        Get current robot end effector pose for this arm.

        Returns:
            pose (np.array): 4x4 EEF pose matrix
        """
        return _controller_to_eef_pose(self.env, self.controller)

    def target_pose_to_action(self, target_pose, relative=True):
        """
        Convert a 4x4 target EEF pose to a 6D action (position + axis-angle).

        Args:
            target_pose (np.array): 4x4 target EEF pose
            relative (bool): if True, return normalized delta action

        Returns:
            action (np.array): 6D action [dx, dy, dz, dax, day, daz]
        """
        return _target_pose_to_action_with_controller(
            target_pose=target_pose,
            get_eef_pose_fn=self.get_robot_eef_pose,
            controller=self.controller,
            relative=relative,
        )

    def action_to_target_pose(self, action, relative=True):
        """
        Convert a 6D (or 7D) action to a 4x4 target EEF pose.

        Args:
            action (np.array): environment action (at least 6D; gripper dim ignored)
            relative (bool): if True, interpret as delta action

        Returns:
            target_pose (np.array): 4x4 target EEF pose
        """
        return _action_to_target_pose_with_controller(
            action=action,
            get_eef_pose_fn=self.get_robot_eef_pose,
            controller=self.controller,
            relative=relative,
        )

    def action_to_gripper_action(self, action):
        """
        Extract the gripper actuation part from a 7D single-arm action.

        Args:
            action (np.array): 7D arm action [pose6, gripper1]

        Returns:
            gripper_action (np.array): shape (1,)
        """
        return action[-1:]
