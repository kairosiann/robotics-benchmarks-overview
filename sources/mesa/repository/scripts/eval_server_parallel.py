"""
VLA Benchmark Evaluation Script
"""

import collections
import dataclasses
import json
import logging
import os
import queue
import time
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

# When batching inference, how long the broker waits to assemble a full batch
# before serving whatever it has. Longer than the micro-batch window so the GPU
# can fill a batch under load, but bounded so it never blocks forever at a
# shard's tail (where fewer than num_env_workers workers remain).
_BATCH_FILL_TIMEOUT_S = 0.5


@dataclasses.dataclass(frozen=True)
class EpisodeSpec:
    task_id: int
    task_name: str
    task_description: str
    episode_idx: int


@dataclasses.dataclass(frozen=True)
class InferenceRequest:
    worker_id: int
    request_id: int
    images: dict[str, np.ndarray]
    state: np.ndarray
    prompt: str


@dataclasses.dataclass(frozen=True)
class InferenceResponse:
    worker_id: int
    request_id: int
    actions: list[list[float]]


@dataclasses.dataclass(frozen=True)
class EpisodeResult:
    spec: EpisodeSpec
    success: bool
    num_steps: int
    subtask_completion_rate: float
    distractor_completed: bool
    completed_subtasks: list[Any]
    completed_distractor_tasks: list[Any]
    total_subtasks: int
    video_frames: list[np.ndarray] | None


def _set_worker_seeds(*, base_seed: int, worker_id: int) -> None:
    np.random.seed(int(base_seed + 10_000 * worker_id))


def _env_worker_loop(
    *,
    worker_id: int,
    args: EvalArgs,
    episode_stats_dir: Any,
    task_queue: Any,
    result_queue: Any,
    inference_request_queue: Any,
    inference_response_queue: Any,
) -> None:
    """
    Env worker process:
    - Creates/steps environments (CPU-heavy)
    - Requests an action chunk from the broker whenever it needs to replan
    """
    _set_worker_seeds(base_seed=args.seed, worker_id=worker_id)

    # Cache EvalSet in the worker so we don't re-read metadata every episode.
    eval_set = EvalSet(args.eval_set_name, split=args.eval_split)
    if args.task_filter:
        eval_set.tasks = [t for t in eval_set.tasks if t in args.task_filter]
        eval_set.n_tasks = len(eval_set.tasks)

    # Number of eval variants (BDDL files) per task, so episode_idx wraps over
    # the real variant count rather than the task count.
    n_instances_per_task: dict[str, int] = {}
    for task_name in eval_set.get_task_names():
        task_dir = os.path.join(eval_set.task_suite_path, task_name, eval_set.split)
        if os.path.isdir(task_dir):
            n_instances_per_task[task_name] = sum(
                1 for f in os.listdir(task_dir)
                if f.endswith(".json") and not f.endswith(".dex.json")
            )
        else:
            n_instances_per_task[task_name] = 1

    action_plan: collections.deque[np.ndarray] = collections.deque()
    request_id = 0

    while True:
        spec = task_queue.get()
        if spec is None:
            break
        assert isinstance(spec, EpisodeSpec)

        summary_path = episode_summary_path(
            episode_stats_dir,
            task_id=spec.task_id,
            task_name=spec.task_name,
            episode_idx=spec.episode_idx,
            num_rollouts_per_task=args.num_rollouts_per_task,
        )
        if summary_path.exists():
            with summary_path.open("r") as f:
                summary = json.load(f)
            result_queue.put(
                EpisodeResult(
                    spec=spec,
                    success=bool(summary["success"]),
                    num_steps=int(summary["num_steps"]),
                    subtask_completion_rate=float(summary["subtask_completion_rate"]),
                    distractor_completed=bool(summary["distractor_completed"]),
                    completed_subtasks=list(summary.get("completed_subtasks", [])),
                    completed_distractor_tasks=list(summary.get("completed_distractor_tasks", [])),
                    total_subtasks=int(summary.get("total_subtasks", 0)),
                    video_frames=None,
                )
            )
            continue

        n_instances = n_instances_per_task.get(spec.task_name, 1)
        instance_idx = spec.episode_idx % n_instances
        parsed_problem = eval_set.get_parsed_problem(spec.task_id, instance_idx)
        init_state = eval_set.get_init_state(spec.task_id, instance_idx)
        make_env_kwargs = dict(
            parsed_problem=parsed_problem,
            controller_type=args.controller_type,
            control_delta=args.control_delta,
            camera_heights=args.camera_height,
            camera_widths=args.camera_width,
            camera_names=args.camera_names,
            deterministic_reset=init_state is not None,
        )
        if args.robots is not None:
            make_env_kwargs["robots"] = args.robots
        env: BDDLBaseDomain = make_env(**make_env_kwargs)

        if init_state is None:
            if request_id == 0:
                print("WARNING: No init_states found for this task suite. Resetting randomly.")
            obs = env.stable_reset()
        else:
            obs = env.reset_to(init_state)
        action_plan.clear()
        t = 0
        success = False
        success_replay_steps = 0
        last_action: np.ndarray | None = None
        all_completed_subtasks: set[Any] = set()
        all_completed_dist_tasks: set[Any] = set()
        last_num_subtasks_completed = 0

        video_frames: list[np.ndarray] | None = [] if args.write_videos else None

        max_steps = args.max_steps

        while t < max_steps:
            # Existing evaluation code flips images vertically.
            images = {k: obs[f"{k}_image"] for k in args.camera_names}

            if video_frames is not None:
                video_frames.append(np.ascontiguousarray(images[args.visualization_camera_name]))

            if not success and not action_plan:
                state = np.concatenate([ensure_not_scalar(obs[k]) for k in args.state_keys], axis=-1)
                req = InferenceRequest(
                    worker_id=worker_id,
                    request_id=request_id,
                    images=images,
                    state=state,
                    prompt=str(spec.task_description),
                )
                request_id += 1
                inference_request_queue.put(req)

                resp: InferenceResponse = inference_response_queue.get()
                if resp.worker_id != worker_id or resp.request_id != req.request_id:
                    raise RuntimeError(
                        f"Worker {worker_id} got mismatched inference response: "
                        f"expected (worker_id={worker_id}, request_id={req.request_id}), "
                        f"got (worker_id={resp.worker_id}, request_id={resp.request_id})"
                    )

                action_chunk = resp.actions
                if len(action_chunk) < args.replan_steps:
                    raise ValueError(
                        f"Expected at least {args.replan_steps} actions but got {len(action_chunk)}."
                    )
                action_plan.extend(np.asarray(a, dtype=np.float32) for a in action_chunk[:args.replan_steps])

            if success:
                if last_action is None:
                    raise RuntimeError("Missing last action for success replay steps.")
                action = last_action
            else:
                action = action_plan.popleft()
            last_action = action
            obs, _, _, info = env.step(action.tolist())
            t += 1
            step_success = bool(info.get("success", False))
            subtask_complete = info.get("subtask_complete")
            distractor_complete = info.get("distractor_complete")
            if subtask_complete is not None:
                all_completed_subtasks.update(subtask_complete)
            if distractor_complete is not None:
                all_completed_dist_tasks.update(distractor_complete)

            max_steps += (
                len(all_completed_subtasks) - last_num_subtasks_completed
            ) * args.per_subtask_extra_steps
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
        result_queue.put(
            EpisodeResult(
                spec=spec,
                success=success,
                num_steps=t,
                subtask_completion_rate=subtask_rate,
                distractor_completed=len(all_completed_dist_tasks) > 0,
                completed_subtasks=sorted(all_completed_subtasks, key=str),
                completed_distractor_tasks=sorted(all_completed_dist_tasks, key=str),
                total_subtasks=all_subtasks,
                video_frames=video_frames,
            )
        )

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


def _inference_broker_loop(
    *,
    args: EvalArgs,
    inference_request_queue: Any,
    response_queues_by_worker: dict[int, Any],
) -> None:
    """
    Inference broker process:
    - Owns a single websocket client connection
    - Services inference requests from all env workers
    - Optionally micro-batches requests by waiting briefly to accumulate a group
    """
    client = _websocket_client_policy.WebsocketClientPolicy(args.host, args.port)
    batch_window_s = max(0.0, float(args.inference_batch_window_ms) / 1000.0)

    def handle_one(req: InferenceRequest) -> None:
        element = {"images": req.images, "state": req.state, "prompt": req.prompt}
        response = client.infer(element)
        resp = InferenceResponse(worker_id=req.worker_id, request_id=req.request_id, actions=response["actions"])
        response_queues_by_worker[req.worker_id].put(resp)

    def handle_batch(batch: list[InferenceRequest]) -> None:
        elements = [{"images": req.images, "state": req.state, "prompt": req.prompt} for req in batch]
        response = client.infer(elements)
        if all(isinstance(item, dict) for item in response):
            batched_actions = [item["actions"] for item in response]
        else:
            batched_actions = response

        if len(batched_actions) != len(batch):
            raise RuntimeError(
                "Batched inference response size mismatch: "
                f"expected {len(batch)} entries, got {len(batched_actions)}."
            )
        for req, actions in zip(batch, batched_actions):
            resp = InferenceResponse(worker_id=req.worker_id, request_id=req.request_id, actions=actions)
            response_queues_by_worker[req.worker_id].put(resp)

    while True:
        try:
            first = inference_request_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        if first is None:
            break

        batch: list[InferenceRequest] = [first]
        should_shutdown = False
        if args.batch_actions:
            deadline = time.perf_counter() + max(batch_window_s, _BATCH_FILL_TIMEOUT_S)
            while len(batch) < args.num_env_workers:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    nxt = inference_request_queue.get(timeout=remaining)
                except queue.Empty:
                    break
                if nxt is None:
                    inference_request_queue.put(None)
                    should_shutdown = True
                    break
                batch.append(nxt)
        elif batch_window_s > 0:
            deadline = time.perf_counter() + batch_window_s
            while True:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    nxt = inference_request_queue.get(timeout=remaining)
                except queue.Empty:
                    break
                if nxt is None:
                    inference_request_queue.put(None)
                    break
                batch.append(nxt)

        if args.batch_actions:
            if batch:
                handle_batch(batch)
            if should_shutdown:
                break
        else:
            for req in batch:
                handle_one(req)


def _logger_loop(*, args: EvalArgs, run_paths: EvalRunPaths, log_queue: Any) -> None:
    """
    Logger process:
    - Writes videos asynchronously so env stepping isn't blocked on I/O
    """
    video_writer = VideoWriter(fps=args.video_fps, stride=args.video_stride)
    while True:
        item = log_queue.get()
        if item is None:
            break
        result: EpisodeResult = item
        if not args.write_videos:
            continue
        if result.video_frames is None or len(result.video_frames) == 0:
            continue
        video_path = build_video_path(
            run_paths=run_paths,
            task_name=result.spec.task_name,
            episode_idx=result.spec.episode_idx,
            success=result.success,
            per_task_folder=args.num_rollouts_per_task > 1,
        )
        try:
            video_writer.write(video_path, result.video_frames)
        except Exception as e:
            logging.error(f"Failed to write video {video_path}: {e}")


def run_eval_server(args: EvalArgs) -> None:
    """
    Parallel evaluator:
    - N env workers (processes) run environments and request actions when replanning is needed
    - 1 inference broker (process) owns the websocket client and services all inference requests
    - 1 logger (process) writes videos asynchronously
    """
    import multiprocessing as mp

    if args.visualization_camera_name is None:
        args.visualization_camera_name = args.camera_names[0]

    run_paths = init_eval_run_paths(
        base_out_path=args.video_out_path,
        suite_name=args.eval_set_name,
        exp_name=args.exp_name,
        variant_name=args.variant_name,
    )
    episode_stats_dir = init_episode_stats_dir(run_paths)

    logging.info(f"Loading the following eval set: {args.eval_set_name}")
    eval_set = EvalSet(args.eval_set_name, split=args.eval_split)
    if args.task_filter:
        eval_set.tasks = [t for t in eval_set.tasks if t in args.task_filter]
        eval_set.n_tasks = len(eval_set.tasks)
    num_tasks = eval_set.n_tasks
    task_names = eval_set.get_task_names()
    logging.info(f"Found {num_tasks} tasks in eval set")
    logging.info(f"Task names: {task_names}")
    logging.info(
        "Parallel eval config: "
        f"num_env_workers={args.num_env_workers}, "
        f"inference_batch_window_ms={args.inference_batch_window_ms}, "
        f"batch_actions={args.batch_actions}, "
        f"write_videos={args.write_videos}, video_stride={args.video_stride}"
    )

    ctx = mp.get_context("spawn")
    task_queue = ctx.Queue()
    result_queue = ctx.Queue()
    log_queue = ctx.Queue()
    inference_request_queue = ctx.Queue(maxsize=args.max_inference_queue_size)
    response_queues_by_worker: dict[int, Any] = {wid: ctx.Queue() for wid in range(args.num_env_workers)}

    broker = ctx.Process(
        target=_inference_broker_loop,
        kwargs=dict(
            args=args,
            inference_request_queue=inference_request_queue,
            response_queues_by_worker=response_queues_by_worker,
        ),
        daemon=True,
    )
    broker.start()

    logger_proc = ctx.Process(
        target=_logger_loop,
        kwargs=dict(args=args, run_paths=run_paths, log_queue=log_queue),
        daemon=True,
    )
    logger_proc.start()

    workers: list[mp.Process] = []
    for wid in range(args.num_env_workers):
        p = ctx.Process(
            target=_env_worker_loop,
            kwargs=dict(
                worker_id=wid,
                args=args,
                episode_stats_dir=episode_stats_dir,
                task_queue=task_queue,
                result_queue=result_queue,
                inference_request_queue=inference_request_queue,
                inference_response_queue=response_queues_by_worker[wid],
            ),
            daemon=True,
        )
        p.start()
        workers.append(p)

    pending: list[EpisodeSpec] = []
    for task_id in range(num_tasks):
        task_name = task_names[task_id]
        if args.randomize_task_instruction:
            task_description = str(eval_set.get_random_task_instruction())
        else:
            task_description = str(eval_set.get_task_instruction(task_id))
        for episode_idx in range(args.num_rollouts_per_task):
            pending.append(
                EpisodeSpec(
                    task_id=task_id,
                    task_name=task_name,
                    task_description=task_description,
                    episode_idx=episode_idx,
                )
            )

    total_to_run = len(pending)
    if total_to_run == 0:
        logging.info("No pending episodes to run (all tasks already completed).")
        log_queue.put(None)
        inference_request_queue.put(None)
        return

    for spec in pending:
        task_queue.put(spec)
    for _ in range(args.num_env_workers):
        task_queue.put(None)

    pbar = tqdm.tqdm(total=total_to_run, desc="episodes")
    for _ in range(total_to_run):
        result: EpisodeResult = result_queue.get()
        pbar.update(1)

        log_queue.put(result)

    pbar.close()

    log_queue.put(None)
    logger_proc.join(timeout=30)

    inference_request_queue.put(None)
    broker.join(timeout=30)

    for p in workers:
        p.join(timeout=30)

    try:
        final_summary = build_final_summary_from_episode_summaries(
            episode_dir=episode_stats_dir,
            args=args,
            run_paths=run_paths,
            extra_experiment_config={
                "num_env_workers": args.num_env_workers,
                "inference_batch_window_ms": args.inference_batch_window_ms,
                "batch_actions": args.batch_actions,
                "write_videos": args.write_videos,
                "video_fps": args.video_fps,
                "video_stride": args.video_stride,
            },
        )
        save_json(run_paths.final_summary_file, final_summary, indent=2)
    except Exception as e:
        logging.error(f"Error building final summary: {e}")

    logging.info(f"Total success rate: {final_summary['overall_success_rate']}")
    logging.info(f"Total episodes: {final_summary['total_episodes']}")
    logging.info(f"Results saved to: {run_paths.stats_dir}")
    logging.info(f"Final summary saved to: {run_paths.final_summary_file}")


if __name__ == "__main__":
    import multiprocessing as mp

    mp.set_start_method("spawn", force=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    args = tyro.cli(EvalArgs)
    run_eval_server(args)
