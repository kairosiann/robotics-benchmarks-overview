"""Shared constants for bimanual (dex) data generation."""

ARM_ACTION_DIM = 7                          # per arm: 6-DoF OSC pose + 1 gripper
BIMANUAL_ACTION_DIM = 2 * ARM_ACTION_DIM    # [left7, right7] = 14
GRIPPER_IDX = ARM_ACTION_DIM - 1            # gripper dim within one arm action (6)
# right-arm gripper in the 14-D action = ARM_ACTION_DIM + GRIPPER_IDX (13)
