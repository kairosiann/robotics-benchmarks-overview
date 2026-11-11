import os

import numpy as np
from robosuite.models.robots.manipulators.manipulator_model import ManipulatorModel


class Yam(ManipulatorModel):
    """
    I2RT YAM (Yet Another Manipulator) - a lightweight 6-DOF arm.
    https://github.com/google-deepmind/mujoco_menagerie/tree/main/i2rt_yam

    Args:
        idn (int or str): Number or some other unique identification string for this robot instance
    """

    arms = ["right"]  # for robosuite v1.5

    def __init__(self, idn=0):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "assets", "yam", "yam_robot.xml"),
            idn=idn,
        )

    @property
    def default_mount(self):
        return "RethinkMount"

    @property
    def default_base(self):
        return "RethinkMount"

    @property
    def default_gripper(self):
        return {"right": "YamGripper"}

    @property
    def default_controller_config(self):
        return {"right": "default_panda"}

    @property
    def init_qpos(self):
        # YAM home position from the menagerie keyframe
        return np.array([0, 1.047, 1.047, 0, 0, 0])

    @property
    def base_xpos_offset(self):
        return {
            "bins": (-0.6, -0.1, -0.15),
            "empty": (-0.7, 0, -0.15),
            "table": lambda table_length: (-0.26 - table_length / 2, 0, -0.15),
            "study_table": lambda table_length: (-0.35 - table_length / 2, 0, -0.15),
            "kitchen_table": lambda table_length: (-0.26 - table_length / 2, 0, -0.15),
        }

    @property
    def base_ori_offset(self):
        return {
            "bins": (0, 0, 0),
            "empty": (0, 0, 0),
            "table": lambda table_length: (0, 0, 0),
            "study_table": lambda table_length: (0, 0, 0),
            "kitchen_table": lambda table_length: (0, 0, 0),
        }

    @property
    def top_offset(self):
        return np.array((0, 0, 1.0))

    @property
    def _horizontal_radius(self):
        return 0.5

    @property
    def arm_type(self):
        return "single"
