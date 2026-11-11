
# RoboChallenge Dataset
## Tasks and Embodiments
The dataset includes 30 diverse manipulation tasks (Table30) across 4 embodiments:

### Available Tasks
- `arrange_flowers`
- `arrange_fruits_in_basket` 
- `arrange_paper_cups` 
- `clean_dining_table` 
- `fold_dishcloth` 
- `hang_toothbrush_cup` 
- `make_vegetarian_sandwich` 
- `move_objects_into_box` 
- `open_the_drawer` 
- `place_shoes_on_rack` 
- `plug_in_network_cable` 
- `pour_fries_into_plate` 
- `press_three_buttons` 
- `put_cup_on_coaster` 
- `put_opener_in_drawer` 
- `put_pen_into_pencil_case` 
- `scan_QR_code` 
- `search_green_boxes` 
- `set_the_plates` 
- `shred_scrap_paper` 
- `sort_books` 
- `sort_electronic_products` 
- `stack_bowls` 
- `stack_color_blocks` 
- `stick_tape_to_box`
- `sweep_the_rubbish` 
- `turn_on_faucet` 
- `turn_on_light_switch` 
- `water_potted_plant` 
- `wipe_the_table` 
### Embodiments
- **ARX5** - Single-arm with triple camera setup (wrist + global + right-side views)
- **UR5** - Single-arm with dual camera setup (wrist + global views)
- **FRANKA** - Single-arm with triple perspective setup (wrist + main + side views)
- **ALOHA** - Dual-arm with triple wrist camera setup (left wrist + right wrist + global views)


## Dataset Structure
### Hierarchy
The dataset is organized by tasks, with each task containing multiple demonstration episodes:
```
.
├── <task_name>/                    # e.g., arrange_flowers, fold_dishcloth
│   ├── task_desc.json              # Task description
│   ├── meta/                       # Task-level metadata
│   │   ├── task_info.json         
│   └── data/                       # Episode data
│       ├── episode_000000/         # Individual episode
│       │   ├── meta/
│       │   │   └── episode_meta.json    # Episode metadata
│       │   ├── states/
│       │   │   # for single-arm (ARX5, UR5, Franka)
│       │   │   ├── states.jsonl         # Single-arm robot states
│       │   │   # for dual-arm (ALOHA)
│       │   │   ├── left_states.jsonl    # Left arm states
│       │   │   └── right_states.jsonl   # Right arm states
│       │   └── videos/
│       │       # Video configurations vary by robot model:
│       │       # ARX5
│       │       ├── arm_realsense_rgb.mp4       # Wrist view 
│       │       ├── global_realsense_rgb.mp4    # Global view 
│       │       └── right_realsense_rgb.mp4     # Side view
│       │       # UR5
│       │       ├── global_realsense_rgb.mp4    # Global view 
│       │       └── handeye_realsense_rgb.mp4   # Wrist view
│       │       # Franka
│       │       ├── handeye_realsense_rgb.mp4   # Wrist view
│       │       ├── main_realsense_rgb.mp4      # Global view 
│       │       └── side_realsense_rgb.mp4      # Side view 
│       │       # ALOHA
│       │       ├── cam_high_rgb.mp4            # Global view 
│       │       ├── cam_wrist_left_rgb.mp4      # Left wrist view
│       │       └── cam_wrist_right_rgb.mp4     # Right wrist view
│       ├── episode_000001/
│       └── ...
├── convert_to_lerobot.py           # Conversion script
└── README.md
```
### Metadata Schema
`task_info.json`
```json
{
    "robot_id": "arx5_1",                    // Robot model identifier
    "task_desc": {
        "task_name": "arrange_flowers",      // Task identifier
        "prompt": "insert the three flowers on the table into the vase one by one",
        "scoring": "...",                    // Scoring criteria
        "task_tag": [                        // Task characteristics
            "repeated",
            "single-arm", 
            "ARX5",
            "precise3d"
        ]
    },
    "video_info": {
        "fps": 30,                           // Video frame rate
        "ext": "mp4",                        // Video format
        "encoding": {
            "vcodec": "libx264",             // Video codec
            "pix_fmt": "yuv420p"             // Pixel format
        }
    }
}
```
`episode_meta.json`
```json
{
    "episode_index": 0,                      // Episode number
    "start_time": 1750405586.3430033,       // Unix timestamp (start)
    "end_time": 1750405642.5247612,         // Unix timestamp (end)
    "frames": 1672                          // Total video frames
}
```

### Robot States Schema
Each episode contains states data stored in JSONL format. Depending on the embodiment, the structure differs slightly:
- **Single-arm robots (ARX5, UR5, Franka)** → `states.jsonl`  
- **Dual-arm robots (ALOHA)** → `left_states.jsonl` and `right_states.jsonl`  

Each file records the robot’s proprioceptive signals per frame, including joint angles, 
end-effector poses, gripper states, and timestamps.  The exact field definitions and coordinate conventions vary by platform, 
as summarized below.

#### ARX5
| Data Name | Data Key |Shape | Semantics |
|:---------:|:-----:|:----:|:----:|
| Joint control |joint_positions | (6,) | Joint angle (in radians) from the base to the end effector. |
| Pose control | end_effector_pose | (6,) | End effector pose (tx, ty, tz, roll, pitch, yaw), where (roll, pitch, yaw) is relative euler angles from the arm base coordinate. X : back to front; Y: right to left; Z: down to up. |
| Gripper control |gripper_width | (1,) | Actual gripper width measurement in meter. | 
| Time stamp |timestamp | (1,) | Floating point timestamp (in milliseconds) of each frame. |

#### UR5
| Data Name | Data Key |Shape | Semantics |
|:---------:|:-----:|:----:|:----:|
| Joint control |joint_positions | (6,) | Joint angle (in radians) from the base to the end effector. |
| Pose control | ee_positions | (7,) | End effector pose (tx, ty, tz, rx, ry, rz, rw), where (tx, ty, tz) is relative position from the arm base coordinate , (rx, ry, rz, rw) is quaternion rotation. X : front to back; Y: left to right; Z: down to up. |
| Gripper control |gripper | (1,) | Gripper closing angle, 0 for fully open, 255 for fully closed. | 
| Time stamp |timestamp | (1,) | Floating point timestamp (in milliseconds) of each frame. | 

#### Franka
| Data Name | Data Key |Shape | Semantics |
|:---------:|:-----:|:----:|:----:|
| Joint control |joint_positions | (7,) | Joint angle (in radians) from the base to the end effector. |
| Pose control | ee_positions | (7,) | End effector pose (tx, ty, tz, rx, ry, rz, rw), where (tx, ty, tz) is relative position from the arm base coordinate , (rx, ry, rz, rw) is quaternion rotation. X : back to front; Y: right to left; Z: down to up. |
| Gripper control |gripper | (2,) | Gripper trigger signals in the (close_button, open_button) order. |
| Gripper width |gripper_width | (1,) | Actual gripper width measurement |
| Time stamp |timestamp | (1,) | Floating point timestamp (in milliseconds) of each frame. |


#### ALOHA
| Data Name | Data Key |Shape | Semantics |
|:---------:|:-----:|:----:|:----:|
| Master joint control |joint_positions | (6,) | Maste joint angle (in radians) from the base to the end effector. |
|Joint  velocity| joint_vel | (7,) | Speed of 6 joint and gripper |
| Puppet joint control |qpos | (6,) | Puppet joint angle (in radians) from the base to the end effector. |
| Puppet pose control | ee_pose_quaternion | (7,) | End effector pose (tx, ty, tz, rx, ry, rz, rw), where (tx, ty, tz) is relative position from the arm base coordinate , (rx, ry, rz, rw) is quaternion rotation. X : back to front; Y: right to left ; Z: down to up. |
| Puppet pose control | ee_pose_rpy | (6,) | End effector pose (tx, ty, tz, rr, rp, ry), where (tx, ty, tz) is relative position from the arm base coordinate , (rr, rp, ry) is euler (in radians). X : back to front; Y: right to left ; Z: down to up. |
| Gripper control |gripper | (1,) |  Actual gripper width measurement in meter.|
| Time stamp |timestamp | (1,) | Floating point timestamp (in mileseconds) of each frame. |


## Convert to LeRobot

While you can implement a custom Dataset class to read RoboChallenge data directly, **we strongly recommend converting to LeRobot format** to take advantage of [LeRobot](https://github.com/huggingface/lerobot)'s comprehensive data processing and loading utilities.

The example script **`convert_to_lerobot.py`** converts **ARX5** data to the LeRobot dataset as a example. For other robot embodiments (UR5, Franka, ALOHA), you can adapt the script accordingly.

### Prerequisites
- Python 3.9+ with the following packages:
  - `lerobot==0.1.0`
  - `opencv-python`
  - `numpy`
- Configure `$LEROBOT_HOME`  (defaults to `~/.lerobot` if unset).

```bash
pip install lerobot==0.1.0 opencv-python numpy
export LEROBOT_HOME="/path/to/lerobot_home"
```

### Usage

Run the converter from the repository root (or provide an absolute path):

```bash
python convert_to_lerobot.py \
  --repo-name example_repo \
  --raw-dataset /path/to/example_dataset \
  --frame-interval 1 
```

### Output
- Frames and metadata are saved to `$LEROBOT_HOME/<repo-name>`.
- At the end, the script calls `dataset.consolidate(run_compute_stats=False)`. If you require aggregated statistics, run it with `run_compute_stats=True` or execute a separate stats job.
