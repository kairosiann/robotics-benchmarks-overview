# Robots

We used the Panda robot with Robotiq-2F85 gripper for all of our official experiments. However, we are open sourcing code for a handful of other embodiments that we implemented. Specifically, we support the UR5e and YAM. For more details, see the `mesa/sim/envs/robots` folder.

The dual-arm [BiMESA](../mesa_bench/task_suites_bimanual.md) benchmark uses two reverse-mounted YAM arms (`ReverseMountedYam ReverseMountedYam`) with the YAM gripper. Each arm has 6 joints and is controlled in `joint_pos`, addressed as `robot0` (left) and `robot1` (right); each arm's 7-D action (6 joint targets + 1 gripper) is concatenated into a 14-D action. See `mounted_yam.py`, `reverse_mounted_yam.py`, and `yam_gripper.py` under `mesa/sim/envs/robots`.