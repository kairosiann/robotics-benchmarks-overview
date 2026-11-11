# Processing Data

Our main script for data processing is `scripts/data/replay_dataset.py`. This script uses metadata from the HDF5 file to replay the trajectories in their original environment and save according to your specifications. 

Replay accepts absolute actions as `abs_actions` (generated demonstrations) or
`actions_abs` (collected demonstrations). For source demonstrations recorded
with `agentview`, use
`--camera-names agentview robot0_eye_in_hand`.

## Example Usage: Rendering data to the screen

To replay the dataset and render it to the screen, you would run:

```bash
uv run scripts/data/replay_dataset.py \
  --dataset data/gen_data/<task_suite_name>/<task_id>/demo/demo.hdf5 \
  --render
```

## Example Usage: Saving to HDF5

To replay the dataset and save it in HDF5 format, you would run:

```bash
uv run scripts/data/replay_dataset.py \
  --dataset data/gen_data/<task_suite_name>/<task_id>/demo/demo.hdf5 \
  --output-format hdf5 \
  --hdf5-output-file data/processed_data/<task_suite_name>/<task_id>.hdf5 \
  --camera-height 224 \
  --camera-width 224 \
  --camera-names "leftshoulder" "rightshoulder" "robot0_eye_in_hand" \
  --remove-done-frames
```

`--remove-done-frames` removes noop transitions after the first successful transition.

## Example Usage: Saving to LeRobot

To replay the dataset and save it in LeRobot v2.1 format, you would run:

```bash
uv run scripts/data/replay_dataset.py \
  --dataset data/gen_data/<task_suite_name>/<task_id>/demo/demo.hdf5 \
  --output-format lerobot \
  --remove-done-frames \
  --lerobot-root-dir data/lerobot_data/<task_suite_name> \
  --lerobot-repo-id <task_suite_name> \
  --lerobot-fps 20 \
  --lerobot-visual-mode video
```

LeRobot datasets support image saving as either images, saved in the `.parquet` files, or videos, saved in a separate `videos` directory. Empirically, we found that images are faster to load but use more disk space. Different VLA repositories seem to have different preferences here. For example, [openpi](https://github.com/Physical-Intelligence/openpi) uses images while [GR00T](https://github.com/NVIDIA/Isaac-GR00T) uses videos. You can choose which to export into using the `--lerobot-visual-mode` argument.

For BiMESA, use
`--camera-names egocentric robot0_eye_in_hand robot1_eye_in_hand`.

This will create separate subdatasets for each task in the task suite, which we found to be very slow for large sets of tasks. To merge them into a single dataset, you can use the `merge_lerobot_datasets.py` script:

```bash
uv run scripts/data/merge_lerobot_datasets.py \
  --dataset-dirs data/lerobot_data/<task_suite_name>/* \
  --out data/lerobot_data/<task_suite_name>_merged
```

## Example Usage: Exporting videos of your data

To export videos of your data, you can use the `export_videos.py` script. To export separate videos for the left and right shoulder cameras and wrist camera per episode, you could run:

```bash
uv run scripts/data/replay_dataset.py \
  --dataset data/gen_data/<task_suite_name>/<task_id>/demo/demo.hdf5 \
  --output-format video \
  --video-output-dir data/videos/<task_suite_name>/<task_id> \
  --camera-names "leftshoulder" "rightshoulder" "robot0_eye_in_hand" \
  --remove-done-frames
```

To export a single video with sped up replays of all the episodes in the dataset, you could run:

```bash
uv run scripts/data/replay_dataset.py \
  --dataset data/gen_data/<task_suite_name>/<task_id>/demo/demo.hdf5 \
  --output-format video \
  --video-output-dir data/videos/<task_suite_name>/<task_id>.mp4 \
  --video-speedup 4.0 \
  --camera-names "leftshoulder" \
  --remove-done-frames
```
