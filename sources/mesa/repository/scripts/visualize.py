"""
Visualize one or more objects by generating a minimal JSON problem and rendering it.

This script:
- Takes one or more object keys as input (matching keys in OBJECTS_DICT or FIXTURES_DICT)
- Writes a minimal problem JSON placing all objects within the workspace
- Loads the environment from that JSON and renders continuously, stepping with no-op actions
- Optional: if a data collection device is connected (quest or spacemouse), allows live teleoperation

Usage:
    python scripts/visualize.py --object-names apple orange --rotation-deg 90 --device quest
    python scripts/visualize.py --task-json-path /abs/path/to/source/000.json --device none

Notes:
- Refer to scripts/generate_pick_place.py for JSON structure inspiration
- Refer to scripts/collect_data.py for how a JSON (parsed_problem) becomes an env
"""

import json
import math
import os
import signal
import time
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

from mesa.data_collection.sim.teleop_runner import TeleopRunner
from mesa.sim.envs import TASK_MAPPING
from mesa.sim.envs.bddl_base_domain import BDDLBaseDomain
from mesa.sim.envs.objects import FIXTURES_DICT, get_object_dict

# Table bounds used in other generation scripts; the center is around x=-0.2, y=0.0
_TABLE_MIN_X = 0.0
_TABLE_MAX_X = 0.4
_TABLE_MIN_Y = -0.4
_TABLE_MAX_Y = 0.4

# Default source problem to host the workspace / fixtures
_DEFAULT_SOURCE_PROBLEM_NAME = "mimiclabs_lab1_tabletop_manipulation"


_DEFAULT_CAMERA_PARAMETERS = {
    "rightshoulder": {
        "r": 1.2,
        "theta": np.pi / 3,
        "phi": np.pi / 4,
        "r_radius": 0.0,
        "theta_radius": 0.0,
        "phi_radius": 0.0,
    },
    "leftshoulder": {
        "r": 1.2,
        "theta": np.pi / 3,
        "phi": -np.pi / 4,
        "r_radius": 0.0,
        "theta_radius": 0.0,
        "phi_radius": 0.0,
    },
    "egocentric": {
        "r": 1.2,
        "theta": np.pi / 3,
        "phi": 0.0,
        "r_radius": 0.0,
        "theta_radius": 0.0,
        "phi_radius": 0.0,
    },
}


def _make_region_dict(
    region_name: str,
    target: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    yaw: float = 0.0,
) -> Dict:
    name = f"{target}_{region_name}"
    return name, {
        "target": target,
        "ranges": [[x_min, y_min, x_max, y_max]],
        "extra": [],
        "yaw_rotation": [yaw, yaw],
        "rgba": [0, 0, 1, 0],
    }


def _linspace_with_center(min_val: float, max_val: float, count: int) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [(min_val + max_val) / 2.0]
    return list(np.linspace(min_val, max_val, count))


def _compute_object_positions(num_objects: int, half_w: float, half_h: float) -> list[tuple[float, float]]:
    if num_objects <= 0:
        return []

    cols = math.ceil(math.sqrt(num_objects))
    rows = math.ceil(num_objects / cols)

    x_min = _TABLE_MIN_X + half_w
    x_max = _TABLE_MAX_X - half_w
    y_min = _TABLE_MIN_Y + half_h
    y_max = _TABLE_MAX_Y - half_h

    xs = _linspace_with_center(x_min, x_max, cols)
    ys = _linspace_with_center(y_min, y_max, rows)

    positions: list[tuple[float, float]] = []
    for row in range(rows):
        for col in range(cols):
            if len(positions) == num_objects:
                break
            positions.append((xs[col], ys[row]))
        if len(positions) == num_objects:
            break
    return positions


def _build_problem_json(object_keys: Sequence[str], yaw_rad: float, source_problem_name: str) -> dict:
    assert source_problem_name in TASK_MAPPING, (
        f"Problem {source_problem_name} not found in TASK_MAPPING"
    )
    problem_class: BDDLBaseDomain = TASK_MAPPING[source_problem_name]
    workspace_name = problem_class.workspace_name

    if not object_keys:
        raise ValueError("object_keys must contain at least one entry")

    # if os.path.exists(out_dir):
    #     return out_dir / "source.json"

    half_w = 0.02
    half_h = 0.02
    positions = _compute_object_positions(len(object_keys), half_w, half_h)

    fixtures_dict: Dict[str, list[str]] = {workspace_name: [workspace_name]}
    objects_dict: Dict[str, list[str]] = {}
    regions: Dict[str, Dict] = {}
    initial_state: list[list[str]] = []
    obj_of_interest: list[str] = []

    instance_counters: Dict[str, int] = {}

    for key, (cx, cy) in zip(object_keys, positions):
        count = instance_counters.get(key, 0) + 1
        instance_counters[key] = count

        obj_instance_name = f"{key}_{count}"
        x_min, x_max = cx - half_w, cx + half_w
        y_min, y_max = cy - half_h, cy + half_h
        region_name, region_dict = _make_region_dict(
            region_name=f"{obj_instance_name}_init_region",
            target=workspace_name,
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            yaw=yaw_rad,
        )

        regions[region_name] = region_dict
        initial_state.append(["on", obj_instance_name, region_name])
        obj_of_interest.append(obj_instance_name)

        if key in FIXTURES_DICT:
            fixtures_dict.setdefault(key, []).append(obj_instance_name)
        else:
            objects_dict.setdefault(key, []).append(obj_instance_name)

    problem = {
        "problem_name": source_problem_name,
        "fixtures": fixtures_dict,
        "regions": regions,
        "objects": objects_dict,
        "textures": {},
        "camera": _DEFAULT_CAMERA_PARAMETERS,
        "lighting": {},
        "styles": {},
        "scene_properties": {},
        "initial_state": initial_state,
        # Minimal placeholders for completeness
        "goal_state": ["and"],
        "demonstration_states": [],
        "language_instruction": [],
        "obj_of_interest": obj_of_interest,
    }

    return problem


def _write_problem_json(parsed_problem: dict, out_dir: Path) -> Path:
    """Write the problem JSON to disk and return the file path.

    `TeleopRunner` expects a JSON problem file path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "source.json"
    out_path.write_text(
        # Use deterministic formatting for easier diffs / debugging.
        json.dumps(parsed_problem, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return out_path


def visualize_objects(
    object_names: list[str] | None = None,
    task_json_path: str | None = None,
    output_root: str = "task_suites/visualize",
    source_problem_name: str = _DEFAULT_SOURCE_PROBLEM_NAME,
    robots: list[str] | None = None,
    control_freq: int = 20,
    render_camera: str = "behindview",
    rotation_deg: float = 0,
    device: str = "none",
    control_delta: bool = False,
    gain: float = 1.5,
    horizon: int = 2000,
    camera_size: int = 256,
):
    """Visualize a task JSON or generate one from object names and visualize it.

    Args:
        object_names: Keys in OBJECTS_DICT or FIXTURES_DICT to visualize (generation mode).
        task_json_path: Existing task JSON path to visualize directly (file mode).
        output_root: Root directory where the JSON will be written.
        source_problem_name: Key in TASK_MAPPING to use as the base "source" problem.
        robots: List of robot names; defaults to ["Panda"].
        control_freq: Control frequency for stepping.
        render_camera: Camera name to render.
        rotation_deg: Yaw rotation for the object(s) in degrees.
        device: "none" to disable teleop, "quest", or "spacemouse".
        control_delta: Use delta control when device supports it.
        gain: Positional gain for Quest controller.
    """
    if task_json_path is None:
        if object_names is None:
            raise ValueError("Provide either task_json_path or object_names.")
        if isinstance(object_names, str):
            object_names = [object_names]
        else:
            object_names = list(object_names)
        if not object_names:
            raise ValueError("object_names must contain at least one entry")
    else:
        if object_names is not None:
            raise ValueError("Provide only one mode: task_json_path or object_names.")
        task_json_path = str(Path(task_json_path).expanduser())
        if not os.path.exists(task_json_path):
            raise FileNotFoundError(f"task_json_path does not exist: {task_json_path}")
        object_names = []

    if robots is None:
        robots = ["Panda"]

    if task_json_path is None:
        if source_problem_name not in TASK_MAPPING:
            candidates = [k for k in TASK_MAPPING.keys() if source_problem_name in k]
            suggestion = f" Did you mean one of: {', '.join(candidates[:10])}?" if candidates else ""
            raise KeyError(
                f"source_problem_name '{source_problem_name}' not found in TASK_MAPPING.{suggestion}"
            )

        object_format = "bimesa" if len(robots) == 2 else "mesa"
        objects = get_object_dict(object_format)
        invalid = [name for name in object_names if name not in objects and name not in FIXTURES_DICT]
        if invalid:
            all_keys = list(objects.keys()) + list(FIXTURES_DICT.keys())
            first_invalid = invalid[0]
            candidates = [k for k in all_keys if first_invalid in k]
            suggestion = f" Did you mean one of: {', '.join(candidates[:10])}?" if candidates else ""
            raise KeyError(
                f"Name '{first_invalid}' not found in the {object_format} object or fixture registry."
                f" Invalid entries: {', '.join(invalid)}.{suggestion}"
            )

        safe_dir_name = "__".join(name.replace(os.sep, "_").replace("/", "_") for name in object_names)
        out_dir = Path(output_root) / safe_dir_name
        yaw_rad = float(rotation_deg) * np.pi / 180.0
        parsed_problem = _build_problem_json(
            object_names, yaw_rad=yaw_rad, source_problem_name=source_problem_name
        )
        problem_file_path = str(_write_problem_json(parsed_problem, out_dir))
        names_display = ", ".join(object_names)
    else:
        problem_file_path = task_json_path
        names_display = Path(problem_file_path).name

    teleop_runner: TeleopRunner | None = None
    previous_handler = signal.getsignal(signal.SIGINT)
    stop = False

    def _handle_sigint(signum, frame):  # type: ignore[no-untyped-def]
        nonlocal stop
        stop = True

    try:
        teleop_runner = TeleopRunner(
            problem_file_path=problem_file_path,
            robots=robots,
            device=device,
            control_delta=control_delta,
            gain=gain,
            render_camera=render_camera,
            horizon=horizon,
            camera_size=camera_size,
            control_freq=control_freq,
        )
        teleop_runner.create(reset=True)

        signal.signal(signal.SIGINT, _handle_sigint)
        teleop_runner.set_robot_alpha(alpha=0.2)
        control_dt = teleop_runner.get_control_dt()

        if teleop_runner.using_real_teleop:
            print(
                f"Teleop enabled with device='{teleop_runner.active_device}'. Rendering '{names_display}' (yaw={rotation_deg} deg). Press Ctrl+C to exit."
            )
        else:
            print(
                f"No teleop device detected, using dummy teleop device. Rendering '{names_display}' (yaw={rotation_deg} deg). Press Ctrl+C to exit."
            )

        reset_button_held = False
        while not stop:
            start_time = time.time()
            step_result = teleop_runner.step(
                render=True,
                require_single_arm_engaged=True,
            )
            controller_state = step_result.controller_state or {}
            reset_requested = bool(controller_state.get("delete_demo", False))
            if reset_requested and not reset_button_held:
                teleop_runner.reset()
                teleop_runner.set_robot_alpha(alpha=0.2)
                reset_button_held = True
            elif not reset_requested:
                reset_button_held = False
            time.sleep(max(0.0, float(control_dt) - (time.time() - start_time)))
    finally:
        signal.signal(signal.SIGINT, previous_handler)
        if teleop_runner is not None:
            teleop_runner.close()


if __name__ == "__main__":
    import tyro

    tyro.cli(visualize_objects)
