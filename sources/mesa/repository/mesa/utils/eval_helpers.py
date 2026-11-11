import dataclasses
import json
import logging
import pathlib
from typing import Any, Mapping

import imageio
import numpy as np


@dataclasses.dataclass
class EvalArgs:
    # Model server parameters
    host: str = "0.0.0.0"
    port: int = 8001
    replan_steps: int = 5
    randomize_task_instruction: bool = False

    # VLA Benchmark evaluation parameters
    eval_set_name: str = "mesa-70"
    num_rollouts_per_task: int = 10
    max_steps: int = 500
    per_subtask_extra_steps: int = 300

    # Parallelism / performance (used by parallel evaluator)
    num_env_workers: int = 8
    inference_batch_window_ms: float = 2.0
    max_inference_queue_size: int = 256
    batch_actions: bool = False

    # Video / logging
    write_videos: bool = True
    video_fps: int = 20
    video_stride: int = 1
    render: bool = False

    # Policy input and output shapes
    camera_names: list[str] = dataclasses.field(default_factory=lambda: ["leftshoulder", "robot0_eye_in_hand"])
    state_keys: list[str] = dataclasses.field(default_factory=lambda: ["robot0_joint_pos", "robot0_gripper_jaw_width"])
    controller_type: str = "osc_pose"
    control_delta: bool = False
    camera_height: int = 224
    camera_width: int = 224
    visualization_camera_name: str | None = None
    # Bimanual contract: ["ReverseMountedYam", "ReverseMountedYam"]. None keeps
    # the env's default (single-arm ["Panda"]).
    robots: list[str] | None = None
    eval_split: str = "eval"
    task_filter: list[str] | None = None

    # Utils
    exp_name: str | None = None
    variant_name: str | None = None
    video_out_path: str = "experiments"
    seed: int = 7


def ensure_not_scalar(x: np.ndarray) -> np.ndarray:
    if np.isscalar(x):
        return np.array([x])
    return x


@dataclasses.dataclass(frozen=True)
class EvalRunPaths:
    """Filesystem layout for an evaluation run."""

    run_id: str
    base_dir: pathlib.Path
    video_dir: pathlib.Path
    stats_dir: pathlib.Path
    progress_file: pathlib.Path
    final_summary_file: pathlib.Path


class VideoWriter:
    def __init__(self, fps: int = 20, stride: int = 1) -> None:
        self._fps = fps
        self._stride = stride

    def _format_frames(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        selected = frames if self._stride <= 1 else frames[:: self._stride]
        formatted: list[np.ndarray] = []
        for img in selected:
            if img.dtype != np.uint8:
                img = img.astype(np.uint8)
            formatted.append(np.ascontiguousarray(img))
        return formatted

    def write(self, path: pathlib.Path, frames: list[np.ndarray]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        formatted = self._format_frames(frames)
        imageio.mimwrite(path, formatted, fps=self._fps)


def _load_json_with_trailing_fix(path: pathlib.Path) -> Any:
    text = path.read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        stripped = text.lstrip()
        decoder = json.JSONDecoder()
        try:
            payload, end = decoder.raw_decode(stripped)
        except json.JSONDecodeError:
            logging.error(f"Failed to load JSON from {path}: {exc}")
            raise
        trailing = stripped[end:]
        if trailing.strip():
            logging.warning(f"Trimming trailing content in {path} after JSON parse error.")
            save_json(path, payload, indent=2)
        return payload


def init_eval_run_paths(
    *,
    base_out_path: str | pathlib.Path,
    suite_name: str,
    exp_name: str | None,
    variant_name: str | None,
    train_step: int | None = None,
    timestamp: str | None = None,
) -> EvalRunPaths:
    """
    Create folders for a run and return canonical file locations.

    Layout:
    - {base_out_path}/{run_id}/videos/
    - {base_out_path}/{run_id}/statistics/
      - progress.json
      - final_summary.json
    """
    run_id = build_run_id(
        suite_name=suite_name,
        exp_name=exp_name,
        variant_name=variant_name,
        train_step=train_step,
        timestamp=timestamp,
    )
    base = pathlib.Path(base_out_path)
    video_dir = base / run_id / "videos"
    stats_dir = base / run_id / "statistics"
    video_dir.mkdir(parents=True, exist_ok=True)
    stats_dir.mkdir(parents=True, exist_ok=True)
    return EvalRunPaths(
        run_id=run_id,
        base_dir=base / run_id,
        video_dir=video_dir,
        stats_dir=stats_dir,
        progress_file=stats_dir / "progress.json",
        final_summary_file=stats_dir / "final_summary.json",
    )


def build_run_id(
    suite_name: str,
    exp_name: str | None = None,
    variant_name: str | None = None,
    train_step: int | None = None,
    *,
    timestamp: str | None = None,
) -> str:
    """
    Build a stable run id used for output folder structure.
    """
    if exp_name is None:
        if variant_name is not None:
            raise ValueError("variant_name must be None if exp_name is None")
        if timestamp is None:
            import datetime as _dt

            timestamp = _dt.datetime.now().strftime("%Y-%m-%d/%H-%M-%S")
        return f"{suite_name}/{timestamp}"

    run_id = f"{suite_name}/{exp_name}"
    if variant_name is not None:
        run_id = f"{run_id}/{variant_name}"
    if train_step is not None:
        run_id = f"{run_id}/train_step_{train_step}"
    return run_id


def save_json(path: pathlib.Path, payload: object, *, indent: int = 2) -> None:
    """Write JSON with consistent formatting."""
    if path.exists():
        logging.warning(f"Overwriting existing file: {path}")
        path.unlink()

    with path.open("w") as f:
        json.dump(payload, f, indent=indent)


def init_episode_stats_dir(run_paths: EvalRunPaths) -> pathlib.Path:
    episodes_dir = run_paths.stats_dir / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    return episodes_dir


def build_episode_summary(
    *,
    task_id: int,
    task_name: str,
    task_description: str,
    episode_idx: int,
    success: bool,
    num_steps: int,
    completed_subtasks: list[Any],
    completed_distractor_tasks: list[Any],
    total_subtasks: int,
    subtask_completion_rate: float,
    distractor_completed: bool,
) -> dict[str, Any]:
    return {
        "task_id": int(task_id),
        "task_name": str(task_name),
        "task_description": str(task_description),
        "episode_idx": int(episode_idx),
        "success": bool(success),
        "num_steps": int(num_steps),
        "completed_subtasks": completed_subtasks,
        "completed_distractor_tasks": completed_distractor_tasks,
        "num_completed_subtasks": int(len(completed_subtasks)),
        "total_subtasks": int(total_subtasks),
        "subtask_completion_rate": float(subtask_completion_rate),
        "distractor_completed": bool(distractor_completed),
    }


def episode_summary_path(
    episode_dir: pathlib.Path,
    *,
    task_id: int,
    task_name: str,
    episode_idx: int,
    num_rollouts_per_task: int,
) -> pathlib.Path:
    if int(num_rollouts_per_task) > 1:
        task_dir = episode_dir / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{int(episode_idx)}.json"
        return task_dir / filename
    else:
        filename = f"{task_name}.json"
        return episode_dir / filename


def save_episode_summary(
    episode_dir: pathlib.Path,
    summary: dict[str, Any],
    *,
    num_rollouts_per_task: int,
) -> None:
    path = episode_summary_path(
        episode_dir,
        task_id=summary["task_id"],
        task_name=summary["task_name"],
        episode_idx=summary["episode_idx"],
        num_rollouts_per_task=num_rollouts_per_task,
    )
    save_json(path, summary, indent=2)


def load_episode_summaries(episode_dir: pathlib.Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(episode_dir.rglob("*.json")):
        try:
            summaries.append(_load_json_with_trailing_fix(path))
        except json.JSONDecodeError as e:
            logging.error(f"Failed to load episode summary from {path}: {e}")
            raise
    return summaries


def build_video_path(
    *, run_paths: EvalRunPaths, task_name: str, episode_idx: int, success: bool, per_task_folder: bool = False
) -> pathlib.Path:
    suffix = "success" if success else "failure"
    task_name_clean = task_name.replace(" ", "_")
    if per_task_folder:
        return run_paths.video_dir / f"rollout_{task_name_clean}/{episode_idx}_{suffix}.mp4"
    else:
        return run_paths.video_dir / f"rollout_{task_name_clean}_{episode_idx}_{suffix}.mp4"


def build_experiment_config(args: EvalArgs, extra_fields: Mapping[str, Any] | None = None) -> dict:
    config = {
        "eval_set_name": args.eval_set_name,
        "num_rollouts_per_task": args.num_rollouts_per_task,
        "max_steps": args.max_steps,
        "camera_names": args.camera_names,
        "state_keys": args.state_keys,
        "controller_type": args.controller_type,
        "control_delta": args.control_delta,
        "camera_height": args.camera_height,
        "camera_width": args.camera_width,
        "visualization_camera_name": args.visualization_camera_name,
        "seed": args.seed,
        "exp_name": args.exp_name,
        "variant_name": args.variant_name,
    }
    if extra_fields:
        config.update(extra_fields)
    return config


def build_final_summary_from_episode_summaries(
    *,
    episode_dir: pathlib.Path,
    args: EvalArgs | None = None,
    run_paths: EvalRunPaths | None = None,
    extra_experiment_config: Mapping[str, Any] | None = None,
) -> dict:
    summaries = load_episode_summaries(episode_dir)
    if len(summaries) == 0:
        raise ValueError(
            "No episode summaries found; cannot build final summary without episode statistics."
        )
    total_episodes = 0
    total_successes = 0
    total_subtask_completion = 0.0
    total_distractor_completed = 0
    total_episodes_with_distractor_stats = 0

    per_task_episodes: dict[str, int] = {}
    per_task_successes: dict[str, int] = {}

    for summary in summaries:
        task_name = str(summary["task_name"])
        success = bool(summary["success"])
        subtask_completion_rate = float(summary["subtask_completion_rate"])
        distractor_completed = summary.get("distractor_completed")

        total_episodes += 1
        if success:
            total_successes += 1
        total_subtask_completion += subtask_completion_rate

        if distractor_completed is not None:
            total_episodes_with_distractor_stats += 1
            total_distractor_completed += int(bool(distractor_completed))

        per_task_episodes[task_name] = per_task_episodes.get(task_name, 0) + 1
        if success:
            per_task_successes[task_name] = per_task_successes.get(task_name, 0) + 1

    per_task_success_rates: dict[str, float] = {}
    for task_name, count in per_task_episodes.items():
        successes = int(per_task_successes.get(task_name, 0))
        per_task_success_rates[task_name] = float(successes) / float(count) if count > 0 else 0.0

    out = {
        "overall_success_rate": float(total_successes) / float(total_episodes) if total_episodes > 0 else 0.0,
        "total_episodes": int(total_episodes),
        "total_successes": int(total_successes),
        "per_task_success_rates": per_task_success_rates,
        "per_task_successes": {task_name: int(per_task_successes.get(task_name, 0)) for task_name in per_task_episodes},
        "per_task_episodes": {task_name: int(count) for task_name, count in per_task_episodes.items()},
        "overall_subtask_completion_rate": float(total_subtask_completion) / float(total_episodes)
        if total_episodes > 0
        else 0.0,
        "overall_distractor_completion_rate": float(total_distractor_completed) / float(total_episodes_with_distractor_stats)
        if total_episodes_with_distractor_stats > 0
        else 0.0,
        "total_episodes_with_distractor_stats": int(total_episodes_with_distractor_stats),
    }
    if args is not None:
        out["experiment_config"] = build_experiment_config(args, extra_fields=extra_experiment_config)
    if run_paths is not None:
        out["output_paths"] = {
            "run_id": run_paths.run_id,
            "video_dir": str(run_paths.video_dir),
            "stats_dir": str(run_paths.stats_dir),
            "progress_file": str(run_paths.progress_file),
        }
    return out

