from robosuite.models.grippers import GRIPPER_MAPPING
from robosuite.robots import ROBOT_CLASS_MAPPING
from robosuite.robots import FixedBaseRobot as RobosuiteRobot

from .menagerie_robotiq_2f85 import MenagerieRobotiq85Gripper
from .mounted_panda import MountedPanda
from .mounted_yam import Yam
from .reverse_mounted_panda import ReverseMountedPanda
from .reverse_mounted_ur5e import ReverseMountedUR5e
from .reverse_mounted_yam import ReverseMountedYam
from .yam_gripper import YamGripper

ROBOT_CLASS_MAPPING.update({"MountedPanda": RobosuiteRobot})
ROBOT_CLASS_MAPPING.update({"ReverseMountedPanda": RobosuiteRobot})
ROBOT_CLASS_MAPPING.update({"ReverseMountedUR5e": RobosuiteRobot})
ROBOT_CLASS_MAPPING.update({"Yam": RobosuiteRobot})
ROBOT_CLASS_MAPPING.update({"ReverseMountedYam": RobosuiteRobot})
GRIPPER_MAPPING.update({"MenagerieRobotiq85Gripper": MenagerieRobotiq85Gripper})
GRIPPER_MAPPING.update({"YamGripper": YamGripper})

__all__ = [
    "MenagerieRobotiq85Gripper",
    "MountedPanda",
    "ReverseMountedPanda",
    "ReverseMountedUR5e",
    "ReverseMountedYam",
    "Yam",
    "YamGripper",
]