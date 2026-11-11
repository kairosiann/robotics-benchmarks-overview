# Available Datasets

We provide several versions of our dataset. First, we provide two versions of the canonical MESA-70 train set:

- [MESA-70-hdf5](https://huggingface.co/datasets/albertwilcox/mesa-70-hdf5): The canonical MESA-70 train set in HDF5 format. This is similar to robomimic-style datasets, and should work as a drop-in replacement for settings which use this format for loading data but not for instantiating environments, due to the exceptions described below.
- [MESA-70-lerobot](https://huggingface.co/datasets/albertwilcox/mesa-70-lerobot): The canonical MESA-70 train set in LeRobot format with 224x224 RGB images for the left and right shoulder cameras and wrist camera.

We also provide two versions of the larger dataset, most of which are not included in the canonical MESA-70 train set or evaluation sets.

- [MESA-all-hdf5](https://huggingface.co/datasets/albertwilcox/mesa-all-hdf5): The full set of tasks for which we generated demonstrations in HDF5 format with *only low-dimensional observations*. This is for those hoping to download the data and process it into some format for their own purposes. We include both the training subset in `train/` and data overlapping with some, but not all, held-out tasks in `test/`. To make use of this data, you'll need to process it to add observations as described in the [data processing section](../using_mesa/processing_data.md).
- [MESA-all-train-lerobot](https://huggingface.co/datasets/albertwilcox/mesa-all-train-lerobot): The MESA-70 training tasks plus the auxiliary MESA-aux tasks (806 training tasks, excluding held-out evaluation tasks) in LeRobot v3.0 format with 224x224 RGB video for the left and right shoulder cameras and wrist camera. The MESA-70 tasks intentionally also appear in the in-distribution evaluation suite. Loading it requires `lerobot>=0.4`. An older LeRobot v2.1 release is still available at revision `v2.1`, but it includes two held-out MESA-Composite tasks (`cup_bowl_drainer_left_region` and `open_and_jam_slide_cabinet_contain_region`) and is missing camera videos for some episodes, so we recommend the v3.0 version.

We empirically found naive cotraining on this data to not provide much benefit, but hope they can be useful for future researchers.

```{warning}
MESA-all-hdf5 contains some tasks which are present in the held-out evaluation sets. If you plan to use it, refer to `mesa/task_suites/task_sets.py` for the MESA-aux task list, which excludes held-out tasks.
```

## HDF5 Format

Our HDF5 format is mostly similar to robomimic-style datasets with the following exceptions:

 - We provide several action spaces. `actions` contains delta end-effector poses, `abs_actions` contains absolute end-effector poses, and `actions_joint_pos` contains absolute joint positions.
 - Robomimic-style datasets typically have an `env_args` dictionary stored as an attribute of the `data` group. Since each demonstration corresponds to a unique BDDL file, and therefore a unique set of `env_args`, the `env_args` dictionary is now a dictionary mapping demonstration keys to per-demonstration `env_args`.

An example of the structure of a dataset is shown below:
```
|__data
|   |__demo_0
|   |   |__actions
|   |   |__abs_actions
|   |   |__actions_joint_pos
|   |   |__obs
|   |   |   |__leftshoulder_image
|   |   |   |__rightshoulder_image
|   |   |   |__robot0_eye_in_hand_image
|   |   |   |__robot0_eef_pos
|   |   |   |__<several other low-dimensional observations>
|   |   |__states
```

## BiMESA-57

BiMESA-57 is the dual-arm training set: **57 tasks · 6,833 demonstrations** collected on two [ReverseMountedYam](../appendix/robots.md) arms (`robot0` = left, `robot1` = right). It spans three skill blocks:

| Block | Skill | Tasks | Demos | Generation |
|---|---|---:|---:|---|
| A | Spatial pick-and-place | 27 | 4,690 | MESA-Gen (aligned combos) + teleop (cross combos) |
| B | Cross-arm handoff | 17 | 843 | Teleoperation |
| C | Single-arm articulated | 13 | 1,300 | MESA-Gen |
| **Total** | | **57** | **6,833** | MESA-Gen 4,681 / teleop 2,152 |

As in the single-arm setting, MESA-Gen synthesizes only the aligned Block A combos and all of Block C; the Block A cross combos and every Block B handoff are collected by teleoperation.

- [BiMESA-57-lerobot](https://huggingface.co/datasets/albertwilcox/bimesa-57-lerobot): BiMESA-57 in LeRobot v2.1 format (6,833 episodes, 57 tasks, 20 fps).

Each demonstration carries three 224x224 RGB cameras — `egocentric`, `robot0_eye_in_hand`, and `robot1_eye_in_hand` — together with a 14-D joint state and a 14-D joint-position action (7 per arm: 6 joints + gripper, concatenated `robot0` then `robot1`), recorded at 20 fps. In the LeRobot version these are stored as `observation.images.<camera>`, `observation.state`, and `action`.

The raw HDF5 demonstrations (not currently released) follow the single-arm HDF5 layout with the dual-arm camera set and per-arm joint observations:
```
|__data
|   |__demo_0
|   |   |__actions            (14-D: robot0 | robot1 joint positions)
|   |   |__obs
|   |   |   |__egocentric_image
|   |   |   |__robot0_eye_in_hand_image
|   |   |   |__robot1_eye_in_hand_image
|   |   |   |__robot0_joint_pos
|   |   |   |__robot1_joint_pos
|   |   |   |__<several other low-dimensional observations>
|   |   |__states
```

The held-out combos, reversed handoff directions, and fixture sides that BiMESA-57 excludes are reserved for the evaluation suites — see [Bimanual task suites](task_suites_bimanual.md).