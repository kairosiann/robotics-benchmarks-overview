"""
Bimanual environment interface composing two ArmInterface instances
with shared MESA object/subtask signal logic.
"""

from mesa.mimicgen.dex.arm_interface import ArmInterface
from mesa.mimicgen.dex.bimanual_datagen_info import BimanualDatagenInfo
from mesa.mimicgen.datagen.datagen_info import DatagenInfo
from mesa.mimicgen.env_interfaces.mesa import MESAInterface


class BimanualEnvInterface(MESAInterface):
    """
    Composes:
    - ``left``:  ArmInterface(robot_index=0)
    - ``right``: ArmInterface(robot_index=1)
    - shared object poses and subtask termination signals from MESA env

    Provides ``get_datagen_info(left_action, right_action)`` returning
    a BimanualDatagenInfo container.
    """

    def __init__(self, env):
        """
        Args:
            env: MESA environment instance with at least two robots
        """
        assert len(env.robots) >= 2, (
            f"BimanualEnvInterface requires at least 2 robots, got {len(env.robots)}"
        )
        super().__init__(env)
        self.left = ArmInterface(env, robot_index=0)
        self.right = ArmInterface(env, robot_index=1)

    def get_datagen_info(self, left_action=None, right_action=None):
        """
        Gather bimanual datagen info for the current timestep.

        Args:
            left_action (np.array or None): 7D left arm action
            right_action (np.array or None): 7D right arm action

        Returns:
            BimanualDatagenInfo
        """
        object_poses = self.get_object_poses()
        subtask_term_signals = self.get_subtask_term_signals()

        left_info = self._make_arm_datagen_info(self.left, left_action)
        right_info = self._make_arm_datagen_info(self.right, right_action)

        return BimanualDatagenInfo(
            left=left_info,
            right=right_info,
            object_poses=object_poses,
            subtask_term_signals=subtask_term_signals,
        )

    @staticmethod
    def _make_arm_datagen_info(arm_interface, action):
        target_pose = None
        gripper_action = None
        if action is not None:
            target_pose = arm_interface.action_to_target_pose(action=action, relative=True)
            gripper_action = arm_interface.action_to_gripper_action(action=action)
        return DatagenInfo(
            eef_pose=arm_interface.get_robot_eef_pose(),
            object_poses=None,
            subtask_term_signals=None,
            target_pose=target_pose,
            gripper_action=gripper_action,
        )
