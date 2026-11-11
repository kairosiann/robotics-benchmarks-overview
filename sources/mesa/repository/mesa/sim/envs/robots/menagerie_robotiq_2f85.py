"""
6-DoF gripper with its open/close variant
"""
import os

import numpy as np
from robosuite.models.grippers.gripper_model import GripperModel


class MenagerieRobotiq85GripperBase(GripperModel):
    """
    6-DoF Robotiq gripper.

    Args:
        idn (int or str): Number or some other unique identification string for this gripper instance
    """

    # Actuator target range from the XML (<position ... ctrlrange="0 0.8"/>)
    _CTRL_MIN = -1
    _CTRL_MAX = 1

    def __init__(self, idn=0):
        super().__init__(os.path.join(os.path.dirname(__file__), "assets/robotiq-2f85/robotiq-2f85.xml"), idn=idn)

    def _scalar_to_ctrl(self, a: float) -> float:
        """
        Map scalar in [-1, 1] to actuator position target in [CTRL_MIN, CTRL_MAX].
        -1 -> open (CTRL_MIN), +1 -> closed (CTRL_MAX)
        """
        a_clamped = np.clip(a, -1.0, 1.0)
        t = 0.5 * (a_clamped + 1.0)  # Transform [-1, 1] -> [0, 1]
        return self._CTRL_MIN + t * (self._CTRL_MAX - self._CTRL_MIN)

    def format_action(self, action):
        """
        Return ONE actuator target derived from a single scalar command.
        
        Args:
            action (np.array): shape (1,), with -1=open, +1=close

        Returns:
            np.array: shape (1,), position target for the single tendon actuator
        """
        assert len(action) == 1, "MenagerieRobotiq85Gripper expects a 1-DoF action"
        
        # Update internal state (incremental control)
        # Reverted clip range to [-1.0, 1.0]
        self.current_action = np.clip(
            self.current_action + self.speed * np.sign(action), -1.0, 1.0
        )
        # Convert the scalar state to the actuator unit
        val = self.current_action[0]
        target = self._scalar_to_ctrl(val)
        # Returns shape (1,) to match the single <actuator> in your XML
        return np.array([target], dtype=np.float32)

    @property
    def init_qpos(self):
        return np.array([
            0.00227, 
            0.000136, 
            0.00247, 
            -0.00267, 
            0.00227, 
            0.000136, 
            0.00247, 
            -0.00267
        ], dtype=np.float32)

    @property
    def _important_geoms(self):
        return {
            "left_finger": [
                "left_driver_col",
                "left_coupler_col",
                "left_spring_link_col",
                "left_follower_col",
                "left_pad1",
                "left_pad2",
            ],
            "right_finger": [
                "right_driver_col",
                "right_coupler_col",
                "right_spring_link_col",
                "right_follower_col",
                "right_pad1",
                "right_pad2",
            ],
            "left_fingerpad": ["left_pad1", "left_pad2"],
            "right_fingerpad": ["right_pad1", "right_pad2"],
        }


class MenagerieRobotiq85Gripper(MenagerieRobotiq85GripperBase):
    """
    1-DoF open/close wrapper for the Robotiq 2F-85.
    """

    @property
    def contact_geom_rgba(self):
        """
        Set collision geoms (Group 0) to be transparent (alpha=0).
        This allows the visual geoms (Group 1) to be seen.
        """
        return np.array([0, 0, 0, 0])

    @property
    def speed(self):
        # Step size for the internal accumulator in format_action; increase for snappier motion.
        return 0.20

    @property
    def dof(self):
        # Expose a single DoF to higher-level controllers / policies
        return 1
