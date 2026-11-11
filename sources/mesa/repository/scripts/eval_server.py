"""
Single-process VLA benchmark evaluator for debugging.

This script mirrors the behavior of `eval_server_parallel.py` but removes all
multiprocessing and batching infrastructure to make stepping through episodes
and policy I/O easier.
"""

import collections
import dataclasses
import json
import logging
import os
from typing import Any

import numpy as np
import tqdm
import tyro
from openpi_client import websocket_client_policy as _websocket_client_policy

from mesa import make_env
from mesa.sim.envs.bddl_base_domain import BDDLBaseDomain
from mesa.task_suites.eval_set import EvalSet
from mesa.utils.eval_helpers import (
    EvalArgs,
    EvalRunPaths,
    VideoWriter,
    build_episode_summary,
    build_final_summary_from_episode_summaries,
    build_video_path,
    ensure_not_scalar,
    episode_summary_path,
    init_episode_stats_dir,
    init_eval_run_paths,
    save_episode_summary,
    save_json,
)


@dataclasses.dataclass(frozen=True)
class EpisodeSpec:
    task_id: int
    task_name: str
    task_description: str
    episode_idx: int


def _load_existing_episode_summary(
    *,
    episode_stats_dir: Any,
    spec: EpisodeSpec,
    num_rollouts_per_task: int,
) -> dict[str, Any] | None:
    summary_path = episode_summary_path(
        episode_stats_dir,
        task_id=spec.task_id,
        task_name=spec.task_name,
        episode_idx=spec.episode_idx,
        num_rollouts_per_task=num_rollouts_per_task,
    )
    if not summary_path.exists():
        return None
    with summary_path.open("r") as f:
        return json.load(f)


def _num_task_instances(eval_set: EvalSet, task_name: str) -> int:
    """Number of eval variants (BDDL files) for a task, so episode_idx wraps over
    the real variant count rather than the task count."""
    task_dir = os.path.join(eval_set.task_suite_path, task_name, eval_set.split)
    if not os.path.isdir(task_dir):
        return 1
    return max(
        1,
        sum(1 for f in os.listdir(task_dir) if f.endswith(".json") and not f.endswith(".dex.json")),
    )


def _run_single_episode(
    *,
    args: EvalArgs,
    spec: EpisodeSpec,
    client: _websocket_client_policy.WebsocketClientPolicy,
    episode_stats_dir: Any,
    run_paths: EvalRunPaths,
    video_writer: VideoWriter,
    eval_set: EvalSet,
) -> dict[str, Any]:
    existing = _load_existing_episode_summary(
        episode_stats_dir=episode_stats_dir,
        spec=spec,
        num_rollouts_per_task=args.num_rollouts_per_task,
    )
    if existing is not None:
        logging.info(
            "Skipping existing episode summary for task=%s episode=%d",
            spec.task_name,
            spec.episode_idx,
        )
        return existing

    instance_idx = spec.episode_idx % _num_task_instances(eval_set, spec.task_name)
    parsed_problem = eval_set.get_parsed_problem(spec.task_id, instance_idx)
    init_state = eval_set.get_init_state(spec.task_id, instance_idx)
    env: BDDLBaseDomain = make_env(
        parsed_problem=parsed_problem,
        controller_type=args.controller_type,
        control_delta=args.control_delta,
        camera_heights=args.camera_height,
        camera_widths=args.camera_width,
        camera_names=args.camera_names,
        has_renderer=args.render,
        deterministic_reset=init_state is not None,
        **({"robots": args.robots} if args.robots is not None else {}),
    )

    try:
        if init_state is None:
            logging.warning(
                "No init_state for task=%s episode=%d; falling back to env.stable_reset().",
                spec.task_name,
                spec.episode_idx,
            )
            obs = env.stable_reset()
        else:
            obs = env.reset_to(init_state)
        if args.render:
            env.render()
        action_plan: collections.deque[np.ndarray] = collections.deque()
        t = 0
        success = False
        success_replay_steps = 0
        last_action: np.ndarray | None = None
        all_completed_subtasks: set[Any] = set()
        all_completed_dist_tasks: set[Any] = set()
        last_num_subtasks_completed = 0
        max_steps = args.max_steps

        video_frames: list[np.ndarray] | None = [] if args.write_videos else None

        while t < max_steps:
            images = {k: obs[f"{k}_image"] for k in args.camera_names}
            if video_frames is not None:
                video_frames.append(np.ascontiguousarray(images[args.visualization_camera_name]))

            if not success and not action_plan:
                state = np.concatenate([ensure_not_scalar(obs[k]) for k in args.state_keys], axis=-1)
                element = {
                    "images": images,
                    "state": state,
                    "prompt": str(spec.task_description),
                }
                response = client.infer(element)
                action_chunk = response["actions"]
                if len(action_chunk) < args.replan_steps:
                    raise ValueError(
                        f"Expected at least {args.replan_steps} actions but got {len(action_chunk)}."
                    )
                action_plan.extend(np.asarray(a, dtype=np.float32) for a in action_chunk[: args.replan_steps])

            if success:
                if last_action is None:
                    raise RuntimeError("Missing last action for success replay steps.")
                action = last_action
            else:
                action = action_plan.popleft()

            last_action = action
            obs, _, _, info = env.step(action.tolist())
            t += 1
            if args.render:
                env.render()
            step_success = bool(info.get("success", False))
            subtask_complete = info.get("subtask_complete")
            distractor_complete = info.get("distractor_complete")

            if subtask_complete is not None:
                all_completed_subtasks.update(subtask_complete)
            if distractor_complete is not None:
                all_completed_dist_tasks.update(distractor_complete)

            num_new_subtasks = len(all_completed_subtasks) - last_num_subtasks_completed
            if num_new_subtasks > 0:
                max_steps += num_new_subtasks * args.per_subtask_extra_steps
                last_num_subtasks_completed = len(all_completed_subtasks)

            if step_success and not success:
                success = True
                success_replay_steps = 20

            if success:
                success_replay_steps -= 1
                if success_replay_steps <= 0:
                    break

        all_subtasks = len(env.parsed_problem.get("demonstration_states", []))
        subtask_rate = len(all_completed_subtasks) / all_subtasks if all_subtasks > 0 else 0.0
        episode_summary = build_episode_summary(
            task_id=spec.task_id,
            task_name=spec.task_name,
            task_description=spec.task_description,
            episode_idx=spec.episode_idx,
            success=success,
            num_steps=t,
            completed_subtasks=sorted(all_completed_subtasks, key=str),
            completed_distractor_tasks=sorted(all_completed_dist_tasks, key=str),
            total_subtasks=all_subtasks,
            subtask_completion_rate=subtask_rate,
            distractor_completed=len(all_completed_dist_tasks) > 0,
        )
        save_episode_summary(
            episode_stats_dir,
            episode_summary,
            num_rollouts_per_task=args.num_rollouts_per_task,
        )

        if args.write_videos and video_frames and len(video_frames) > 0:
            video_path = build_video_path(
                run_paths=run_paths,
                task_name=spec.task_name,
                episode_idx=spec.episode_idx,
                success=success,
                per_task_folder=args.num_rollouts_per_task > 1,
            )
            video_writer.write(video_path, video_frames)

        return episode_summary
    finally:
        env.close()


def run_eval_server(args: EvalArgs) -> None:
    np.random.seed(args.seed)

    if args.visualization_camera_name is None:
        args.visualization_camera_name = args.camera_names[0]

    run_paths = init_eval_run_paths(
        base_out_path=args.video_out_path,
        suite_name=args.eval_set_name,
        exp_name=args.exp_name,
        variant_name=args.variant_name,
    )
    episode_stats_dir = init_episode_stats_dir(run_paths)
    video_writer = VideoWriter(fps=args.video_fps, stride=args.video_stride)

    logging.info("Loading task set: %s", args.eval_set_name)
    eval_set = EvalSet(args.eval_set_name, split=args.eval_split)
    if args.task_filter:
        eval_set.tasks = [task for task in eval_set.tasks if task in args.task_filter]
        eval_set.n_tasks = len(eval_set.tasks)
    task_names = eval_set.get_task_names()
    logging.info("Found %d tasks", eval_set.n_tasks)
    logging.info("Task names: %s", task_names)
    logging.info("Connecting to policy server at %s:%d", args.host, args.port)
    client = _websocket_client_policy.WebsocketClientPolicy(args.host, args.port)

    specs: list[EpisodeSpec] = []
    for task_id in range(eval_set.n_tasks):
        task_name = task_names[task_id]
        if args.randomize_task_instruction:
            task_description = str(eval_set.get_random_task_instruction())
        else:
            task_description = str(eval_set.get_task_instruction(task_id))
        for episode_idx in range(args.num_rollouts_per_task):
            specs.append(
                EpisodeSpec(
                    task_id=task_id,
                    task_name=task_name,
                    task_description=task_description,
                    episode_idx=episode_idx,
                )
            )

    if len(specs) == 0:
        logging.info("No episodes to run.")
        return

    successes = 0
    pbar = tqdm.tqdm(specs, desc="episodes")
    for spec in pbar:
        episode_summary = _run_single_episode(
            args=args,
            spec=spec,
            client=client,
            episode_stats_dir=episode_stats_dir,
            run_paths=run_paths,
            video_writer=video_writer,
            eval_set=eval_set,
        )
        successes += int(bool(episode_summary["success"]))
        completed = pbar.n + 1
        pbar.set_postfix(success_rate=f"{(successes / completed):.3f}")

    final_summary = build_final_summary_from_episode_summaries(
        episode_dir=episode_stats_dir,
        args=args,
        run_paths=run_paths,
        extra_experiment_config={
            "mode": "single_process_debug",
            "write_videos": args.write_videos,
            "video_fps": args.video_fps,
            "video_stride": args.video_stride,
        },
    )
    save_json(run_paths.final_summary_file, final_summary, indent=2)

    logging.info("Total success rate: %s", final_summary["overall_success_rate"])
    logging.info("Total episodes: %s", final_summary["total_episodes"])
    logging.info("Results saved to: %s", run_paths.stats_dir)
    logging.info("Final summary saved to: %s", run_paths.final_summary_file)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    run_eval_server(tyro.cli(EvalArgs))
