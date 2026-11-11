"""
Container for per-timestep bimanual datagen information.

Stores left and right arm data (eef_pose, target_pose, gripper_action)
alongside shared data (object_poses, subtask_term_signals).
"""

from copy import deepcopy

import numpy as np

from mesa.mimicgen.datagen.datagen_info import DatagenInfo


class BimanualDatagenInfo:
    """
    Bimanual datagen info container holding per-arm DatagenInfo and shared fields.

    Attributes:
        left (DatagenInfo): left arm datagen info (eef_pose, target_pose, gripper_action)
        right (DatagenInfo): right arm datagen info (eef_pose, target_pose, gripper_action)
        object_poses (dict or None): shared object poses
        subtask_term_signals (dict or None): shared subtask termination signals
    """

    def __init__(self, left, right, object_poses=None, subtask_term_signals=None):
        """
        Args:
            left (DatagenInfo): left arm info
            right (DatagenInfo): right arm info
            object_poses (dict or None): shared object pose dict
            subtask_term_signals (dict or None): shared subtask termination signals
        """
        self.left = left
        self.right = right
        self.object_poses = None
        if object_poses is not None:
            self.object_poses = {k: np.array(v) for k, v in object_poses.items()}
        self.subtask_term_signals = None
        if subtask_term_signals is not None:
            self.subtask_term_signals = {}
            for k, v in subtask_term_signals.items():
                if isinstance(v, (int, float)):
                    self.subtask_term_signals[k] = v
                else:
                    self.subtask_term_signals[k] = np.array(v)

    def to_dict(self):
        """
        Serialize to ``{"left": {...}, "right": {...}}`` with shared fields
        included in both arms for HDF5 compatibility.
        """
        ret = {
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }
        if self.object_poses is not None:
            ret["object_poses"] = deepcopy(self.object_poses)
        if self.subtask_term_signals is not None:
            ret["subtask_term_signals"] = deepcopy(self.subtask_term_signals)
        return ret

    def __repr__(self):
        return (
            f"BimanualDatagenInfo(left={self.left}, right={self.right}, "
            f"object_poses={self.object_poses}, "
            f"subtask_term_signals={self.subtask_term_signals})"
        )
