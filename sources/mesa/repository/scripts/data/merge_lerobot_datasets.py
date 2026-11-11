"""Merge multiple LeRobot datasets into a single dataset.

Usage:
    uv run scripts/data/merge_lerobot_datasets.py \
        --dataset-dirs /path/to/ds1 /path/to/ds2 \
        --out /path/to/merged_dataset

    uv run scripts/data/merge_lerobot_datasets.py \
        --dataset-root /path/to/datasets_root \
        --train-set-name mesa-70 \
        --out /path/to/merged_dataset
"""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import tyro
from tqdm import tqdm

from mesa.task_suites.task_sets import TRAIN_SETS


def _ensure_out_dir_empty(out_dir: Path, auto_remove_exp: bool) -> None:
    if out_dir.exists():
        if auto_remove_exp:
            shutil.rmtree(out_dir)
        elif any(out_dir.iterdir()):
            raise FileExistsError(
                f"Output directory already exists and is not empty: {str(out_dir)!r}"
            )
        else:
            shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_jsonlines(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False)


def _write_jsonlines(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row))
            f.write("\n")


def _task_mappings(subdataset_paths: Sequence[Path]) -> tuple[list[str], dict[Path, dict[int, int]]]:
    tasks: list[str] = []
    task_to_index: dict[str, int] = {}
    per_dataset_map: dict[Path, dict[int, int]] = {}

    for path in subdataset_paths:
        tasks_path = path / "meta" / "tasks.jsonl"
        rows = _read_jsonlines(tasks_path)
        rows = sorted(rows, key=lambda r: int(r["task_index"]))
        mapping: dict[int, int] = {}
        for row in rows:
            task = row["task"]
            if task not in task_to_index:
                task_to_index[task] = len(tasks)
                tasks.append(task)
            mapping[int(row["task_index"])] = task_to_index[task]
        per_dataset_map[path] = mapping

    return tasks, per_dataset_map


def _video_keys_from_info(info: dict) -> list[str]:
    return [k for k, v in info.get("features", {}).items() if v.get("dtype") == "video"]


def _fast_copy_parquet(
    dataset_paths: Sequence[Path],
    *,
    out_dir: Path,
    max_episodes_per_dataset: Sequence[int] | None = None,
) -> None:
    if max_episodes_per_dataset is not None and len(max_episodes_per_dataset) != len(dataset_paths):
        raise ValueError(
            "If provided, max_episodes_per_dataset must match dataset_paths length."
        )

    reference_path = dataset_paths[0]
    info = _read_json(reference_path / "meta" / "info.json")
    chunks_size = int(info["chunks_size"])
    data_path_tpl = info["data_path"]
    video_path_tpl = info["video_path"]
    total_videos = int(info.get("total_videos", 0))
    video_keys = _video_keys_from_info(info) if total_videos else []

    tasks, per_dataset_task_map = _task_mappings(dataset_paths)

    episodes_rows: list[dict] = []
    episodes_stats_rows: list[dict] = []
    current_episode_index = 0
    current_frame_index = 0

    for ds_idx, ds_root in tqdm(
        list(enumerate(dataset_paths)),
        total=len(dataset_paths),
        desc="Copying parquet episodes",
    ):
        ds_info = _read_json(ds_root / "meta" / "info.json")
        ds_chunks_size = int(ds_info["chunks_size"])
        ds_data_path_tpl = ds_info["data_path"]
        ds_video_path_tpl = ds_info["video_path"]

        if ds_chunks_size != chunks_size:
            raise ValueError(
                f"chunks_size mismatch for {str(ds_root)!r}: expected {chunks_size}, got {ds_chunks_size}"
            )
        if ds_data_path_tpl != data_path_tpl:
            raise ValueError(
                f"data_path mismatch for {str(ds_root)!r}: expected {data_path_tpl}, got {ds_data_path_tpl}"
            )
        if ds_video_path_tpl != video_path_tpl:
            raise ValueError(
                f"video_path mismatch for {str(ds_root)!r}: expected {video_path_tpl}, got {ds_video_path_tpl}"
            )

        episodes_path = ds_root / "meta" / "episodes.jsonl"
        episodes_stats_path = ds_root / "meta" / "episodes_stats.jsonl"
        episode_rows = _read_jsonlines(episodes_path)
        stats_rows = _read_jsonlines(episodes_stats_path) if episodes_stats_path.exists() else []
        stats_by_episode = {int(r["episode_index"]): r for r in stats_rows}
        selected = sorted(episode_rows, key=lambda r: int(r["episode_index"]))

        ds_max_episodes = (
            max_episodes_per_dataset[ds_idx] if max_episodes_per_dataset is not None else None
        )
        if ds_max_episodes is not None:
            if ds_max_episodes < 0:
                raise ValueError(
                    f"Negative demos_per_task is invalid for dataset {str(ds_root)!r}: {ds_max_episodes}"
                )
            if len(selected) < ds_max_episodes:
                print(
                    "Warning: requested"
                    f" {ds_max_episodes} demos for {ds_root.name!r},"
                    f" but only {len(selected)} available. Using all available demos."
                )
            selected = selected[:ds_max_episodes]

        task_map = per_dataset_task_map[ds_root]

        for row in selected:
            old_ep_idx = int(row["episode_index"])
            src_parquet = ds_root / data_path_tpl.format(
                episode_chunk=old_ep_idx // chunks_size,
                episode_index=old_ep_idx,
            )
            dst_parquet = out_dir / data_path_tpl.format(
                episode_chunk=current_episode_index // chunks_size,
                episode_index=current_episode_index,
            )
            dst_parquet.parent.mkdir(parents=True, exist_ok=True)

            table = pq.read_table(src_parquet)
            n_frames = table.num_rows

            episode_type = table.schema.field("episode_index").type
            frame_type = table.schema.field("frame_index").type
            index_type = table.schema.field("index").type
            task_type = table.schema.field("task_index").type

            episode_arr = pa.array(
                np.full(n_frames, current_episode_index, dtype=np.int64),
                type=episode_type,
            )
            frame_arr = pa.array(
                np.arange(n_frames, dtype=np.int64),
                type=frame_type,
            )
            index_arr = pa.array(
                np.arange(current_frame_index, current_frame_index + n_frames, dtype=np.int64),
                type=index_type,
            )

            task_vals = table.column("task_index").to_numpy(zero_copy_only=False)
            remapped = np.vectorize(task_map.get, otypes=[np.int64])(task_vals)
            task_arr = pa.array(remapped, type=task_type)

            table = table.set_column(
                table.schema.get_field_index("episode_index"),
                "episode_index",
                episode_arr,
            )
            table = table.set_column(
                table.schema.get_field_index("frame_index"),
                "frame_index",
                frame_arr,
            )
            table = table.set_column(
                table.schema.get_field_index("index"),
                "index",
                index_arr,
            )
            table = table.set_column(
                table.schema.get_field_index("task_index"),
                "task_index",
                task_arr,
            )

            pq.write_table(table, dst_parquet)

            if total_videos:
                for vid_key in video_keys:
                    src_video = ds_root / video_path_tpl.format(
                        episode_chunk=old_ep_idx // chunks_size,
                        episode_index=old_ep_idx,
                        video_key=vid_key,
                    )
                    dst_video = out_dir / video_path_tpl.format(
                        episode_chunk=current_episode_index // chunks_size,
                        episode_index=current_episode_index,
                        video_key=vid_key,
                    )
                    dst_video.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_video, dst_video)

            new_row = dict(row)
            new_row["episode_index"] = current_episode_index
            episodes_rows.append(new_row)

            stats_row = stats_by_episode.get(old_ep_idx)
            if stats_row is not None:
                new_stats = dict(stats_row)
                new_stats["episode_index"] = current_episode_index
                episodes_stats_rows.append(new_stats)

            current_episode_index += 1
            current_frame_index += n_frames

    total_episodes = current_episode_index
    total_frames = current_frame_index
    total_chunks = int(math.ceil(total_episodes / chunks_size)) if total_episodes else 0

    out_info = dict(info)
    out_info["total_episodes"] = total_episodes
    out_info["total_frames"] = total_frames
    out_info["total_chunks"] = total_chunks
    out_info["total_tasks"] = len(tasks)
    out_info["splits"] = {"train": f"0:{total_episodes}"}

    _write_json(out_dir / "meta" / "info.json", out_info)
    _write_jsonlines(
        out_dir / "meta" / "tasks.jsonl",
        [{"task_index": i, "task": t} for i, t in enumerate(tasks)],
    )
    _write_jsonlines(out_dir / "meta" / "episodes.jsonl", episodes_rows)
    if episodes_stats_rows:
        _write_jsonlines(out_dir / "meta" / "episodes_stats.jsonl", episodes_stats_rows)


@dataclass(frozen=True)
class Args:
    out: Path
    dataset_dirs: list[Path] | None = None
    dataset_root: Path | None = None
    train_set_name: str | None = None
    auto_remove_exp: bool = False


def _dataset_dirs_and_demos_from_train_set(
    dataset_root: Path, train_set_name: str
) -> tuple[list[Path], list[int] | None]:
    if train_set_name not in TRAIN_SETS:
        available = ", ".join(sorted(TRAIN_SETS.keys()))
        raise KeyError(
            f"Unknown train set {train_set_name!r}. Available train sets: {available}"
        )

    train_set_cfg = TRAIN_SETS[train_set_name]
    tasks = train_set_cfg.get("tasks")
    if not isinstance(tasks, list):
        raise TypeError(
            f"Expected TRAIN_SETS[{train_set_name!r}]['tasks'] to be a list, got {type(tasks).__name__}"
        )
    dataset_dirs = [dataset_root / str(task_name) for task_name in tasks]

    demos_per_task = train_set_cfg.get("demos_per_task")
    if demos_per_task is None:
        return dataset_dirs, None

    if isinstance(demos_per_task, int):
        return dataset_dirs, [demos_per_task] * len(tasks)

    if isinstance(demos_per_task, list):
        if len(demos_per_task) != len(tasks):
            raise ValueError(
                "When demos_per_task is a list, its length must match tasks length for "
                f"{train_set_name!r}: got {len(demos_per_task)} vs {len(tasks)}."
            )
        return dataset_dirs, demos_per_task

    raise TypeError(
        "Expected demos_per_task to be None, int, or list[int] for "
        f"train set {train_set_name!r}; got {type(demos_per_task).__name__}."
    )


def main(args: Args) -> None:
    direct_dirs_mode = args.dataset_dirs is not None and len(args.dataset_dirs) > 0
    train_set_mode = args.dataset_root is not None or args.train_set_name is not None

    if direct_dirs_mode and train_set_mode:
        raise ValueError(
            "Provide either --dataset-dirs OR the pair (--dataset-root, --train-set-name), not both."
        )

    if train_set_mode:
        if args.dataset_root is None or args.train_set_name is None:
            raise ValueError(
                "When using train set mode, both --dataset-root and --train-set-name are required."
            )
        dataset_dirs, max_episodes_per_dataset = _dataset_dirs_and_demos_from_train_set(
            args.dataset_root.expanduser().resolve(),
            args.train_set_name,
        )
    elif direct_dirs_mode:
        dataset_dirs = [p.expanduser().resolve() for p in args.dataset_dirs or []]
        max_episodes_per_dataset = None
    else:
        raise ValueError(
            "Missing dataset inputs. Provide --dataset-dirs or (--dataset-root and --train-set-name)."
        )

    for ds_dir in dataset_dirs:
        if not ds_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {str(ds_dir)!r}")
        if not ds_dir.is_dir():
            raise NotADirectoryError(f"Dataset path is not a directory: {str(ds_dir)!r}")
        required_meta = ds_dir / "meta" / "info.json"
        if not required_meta.exists():
            raise FileNotFoundError(f"Expected LeRobot dataset metadata at {str(required_meta)!r}")

    out_dir = args.out.expanduser().resolve()
    _ensure_out_dir_empty(out_dir, auto_remove_exp=args.auto_remove_exp)

    _fast_copy_parquet(
        dataset_dirs,
        out_dir=out_dir,
        max_episodes_per_dataset=max_episodes_per_dataset,
    )
    print(f"Done. Wrote merged dataset to {str(out_dir)!r} (fast copy mode)")


if __name__ == "__main__":
    main(tyro.cli(Args))
