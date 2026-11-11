"""
YAM native parallel-jaw gripper.

Simple 2-finger slide gripper built into the I2RT YAM robot.
Two slide joints coupled via an equality constraint; single position actuator.
"""
import os

import numpy as np
from robosuite.models.grippers.gripper_model import GripperModel


class YamGripperBase(GripperModel):
    """
    YAM native parallel-jaw gripper with 2 slide joints and 1 position actuator.

    Args:
        idn (int or str): Number or some other unique identification string for this gripper instance
    """

    def __init__(self, idn=0):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "assets", "yam", "yam_gripper.xml"),
            idn=idn,
        )

    def format_action(self, action):
        """
        Map a single scalar command to normalized gripper control.

        Incremental control: accumulates an internal state in [-1, 1].
        -1 = fully open
        +1 = fully closed

        robosuite's GRIP controller will map this normalized command to actuator
        ctrlrange, so we return normalized values (not raw actuator targets).

        Args:
            action (np.array): shape (1,), values in [-1, 1]

        Returns:
            np.array: shape (1,), normalized control in [-1, 1]
        """
        assert len(action) == 1, "YamGripper expects a 1-DoF action"

        self.current_action = np.clip(
            self.current_action + self.speed * np.sign(action), -1.0, 1.0
        )

        # Actuator range is [0, 0.041] where higher values open the gripper.
        # Invert so teleop convention remains: +1 = close, -1 = open.
        return np.array([-self.current_action[0]], dtype=np.float32)

    @property
    def init_qpos(self):
        # Two slide joints (left_finger, right_finger), both start at 0 (closed)
        return np.array([0.0, 0.0], dtype=np.float32)

    @property
    def _important_geoms(self):
        return {
            "left_finger": [
                "lf_rot_col1",
                "lf_rot_col2",
                "lf_down_col1",
                "lf_down_col2",
                "lf_down_col3",
                "lf_pad1",
                "lf_pad2",
                "lf_tip1",
                "lf_tip2",
                "lf_tip3",
                "lf_tip4",
                "lf_tip5",
                "lf_tip6",
            ],
            "right_finger": [
                "rf_rot_col1",
                "rf_rot_col2",
                "rf_down_col1",
                "rf_down_col2",
                "rf_down_col3",
                "rf_pad1",
                "rf_pad2",
                "rf_tip1",
                "rf_tip2",
                "rf_tip3",
                "rf_tip4",
                "rf_tip5",
                "rf_tip6",
            ],
            "left_fingerpad": [
                "lf_pad1", "lf_pad2",
                "lf_tip1", "lf_tip2", "lf_tip3", "lf_tip4", "lf_tip5", "lf_tip6",
                "lf_down_col2", "lf_down_col3",
            ],
            "right_fingerpad": [
                "rf_pad1", "rf_pad2",
                "rf_tip1", "rf_tip2", "rf_tip3", "rf_tip4", "rf_tip5", "rf_tip6",
                "rf_down_col2", "rf_down_col3",
            ],
        }


class YamGripper(YamGripperBase):
    """
    1-DoF open/close wrapper for the YAM native gripper.
    """

    @property
    def contact_geom_rgba(self):
        return np.array([0, 0, 0, 0])

    @property
    def speed(self):
        return 0.20

    @property
    def dof(self):
        return 1
