"""
This script is used to generate and save initial states for deterministic evaluation
"""

from __future__ import annotations

import dataclasses
import json
import logging
import multiprocessing as mp
import pathlib

import numpy as np
import tyro

import mesa
from mesa import make_env


@dataclasses.dataclass
class Args:
    task_suite_name: str
    output_dir: str = "init_states"
    target_object: str = "object_0"
    camera_name: str = "leftshoulder"
    min_target_object_pixels: int = 60
    max_reset_attempts: int = 50
    num_workers: int = 1
    ensure_object_visibility: bool = False


def _get_task_suite_root(task_suite_name: str) -> pathlib.Path:
    task_suite_root = (
        pathlib.Path(mesa.__path__[0]) / "task_suites" / "bddl_files" / task_suite_name
    )
    if not task_suite_root.is_dir():
        raise FileNotFoundError(f"Task suite path not found: {task_suite_root}")
    return task_suite_root


def _iterate_suite_tasks(
    task_suite_root: pathlib.Path,
) -> list[tuple[int, str, pathlib.Path]]:
    jobs: list[tuple[int, str, pathlib.Path]] = []
    task_folders = sorted(path for path in task_suite_root.iterdir() if path.is_dir())
    for task_idx, task_folder in enumerate(task_folders):
        eval_folder = task_folder / "eval"
        if not eval_folder.is_dir():
            continue
        for json_file in sorted(eval_folder.glob("*.json")):
            jobs.append((task_idx, task_folder.name, json_file))
    return jobs


def _build_binary_mask_for_target_object(
    obs: dict, *, camera_name: str, image_shape: tuple[int, int], target_object: str
) -> np.ndarray:
    mask_keys = [
        key for key in obs if key.endswith(f"_{camera_name}_segmentation_mask")
    ]
    if not mask_keys:
        return np.zeros(image_shape, dtype=np.uint8)

    target_object_keys = [key for key in mask_keys if key.startswith(target_object)]
    if len(target_object_keys) != 1:
        raise ValueError(f"Expected 1 {target_object} key, got {len(target_object_keys)}")
    target_object_mask = obs[target_object_keys[0]]
    if target_object_mask.ndim == 3 and target_object_mask.shape[-1] == 1:
        target_object_mask = target_object_mask[..., 0]
    return (target_object_mask > 0).astype(np.uint8)


def _get_state(env) -> dict:
    return {
        "model": env.sim.model.get_xml(),
        "states": env.sim.get_state().flatten().tolist(),
    }

def _process_variant(job: tuple[int, str, str], args_dict: dict) -> str:
    args = Args(**args_dict)
    task_id, task_name, problem_path_str = job
    problem_path = pathlib.Path(problem_path_str)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    parsed_problem = json.loads(problem_path.read_text())
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    state_dir = output_dir / task_name
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / problem_path.name
    if state_path.exists():
        logging.info("Skipping existing init state: %s", state_path)
        return str(state_path)

    logging.info(
        "Rendering task %d: %s (problem %s)",
        task_id,
        task_name,
        problem_path.name,
    )

    env = make_env(
        parsed_problem=parsed_problem,
        controller_type="osc_pose",
        control_delta=False,
        camera_names=[args.camera_name],
        return_segmentation_masks=True,
    )

    try:
        obs = None
        mask = None
        min_pixels = args.min_target_object_pixels
        for attempt in range(1, args.max_reset_attempts + 1):
            obs = env.stable_reset()
            image = np.asarray(obs[f"{args.camera_name}_image"])
            if env._check_success():
                logging.info(
                    "Reset attempt %d/%d rejected (env already successful).",
                    attempt,
                    args.max_reset_attempts,
                )
                continue
            if args.ensure_object_visibility:
                mask = _build_binary_mask_for_target_object(
                    obs,
                    camera_name=args.camera_name,
                    image_shape=image.shape[:2],
                    target_object=args.target_object,
                )
                if int(mask.sum()) >= min_pixels:
                    logging.info(
                        "Reset attempt %d/%d rejected (target object pixels=%d < %d)",
                        attempt,
                        args.max_reset_attempts,
                        int(mask.sum()),
                        min_pixels,
                    )
                    min_pixels -= 1 # hack: each time we decrease the min pixels, we try again
                else:
                    break
            else:
                break
        else:
            raise RuntimeError(
                f"Failed to reach {min_pixels} target object pixels after "
                f"{args.max_reset_attempts} reset attempts."
            )

        state_payload = _get_state(env)
        if not state_path.exists():
            state_path.write_text(
                json.dumps(state_payload, indent=2, sort_keys=True)
            )
    finally:
        env.close()

    return str(state_path)


def render_task_set(args: Args) -> None:
    logging.info("Loading task suite: %s", args.task_suite_name)
    task_suite_root = _get_task_suite_root(args.task_suite_name)
    output_dir = pathlib.Path(args.output_dir) / "mesa-eval"
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs = _iterate_suite_tasks(task_suite_root)
    if not jobs:
        raise RuntimeError(f"No eval JSON tasks found under: {task_suite_root}")

    if args.num_workers <= 1:
        args_dict = dataclasses.asdict(args)
        args_dict["output_dir"] = output_dir
        for task_id, task_name, problem_path in jobs:
            job = (task_id, task_name, str(problem_path))
            _process_variant(job, args_dict)
        return

    args_dict = dataclasses.asdict(args)
    args_dict["output_dir"] = output_dir
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=args.num_workers) as pool:
        for _ in pool.starmap(
            _process_variant,
            (
                ((task_id, task_name, str(problem_path)), args_dict)
                for task_id, task_name, problem_path in jobs
            ),
        ):
            pass
    
    print(f"Rendered {len(jobs)} tasks")
    print(f"Saved to {args.output_dir}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    render_task_set(tyro.cli(Args))