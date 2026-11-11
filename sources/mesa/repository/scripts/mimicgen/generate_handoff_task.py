"""
Generate a handoff bimanual task where one arm grasps an object, lifts it to a
handoff point, the other arm receives it mid-air, and places it at a destination.

The pick object spawns on the left side and the destination on the right.
Sidecars assign subtasks 0-1 to the left arm and subtasks 2-3 to the right arm
with a fully sequential dependency chain.

Example::

    uv run scripts/mimicgen/generate_handoff_task.py \
        --task-suite-name bimesa \
        --make-source
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tyro
from natsort import natsorted

from mesa.mimicgen.dex.sidecar import (
    validate_arm_assignment_options,
    validate_subtask_dependencies,
)
from mesa.sim.task_gen import HandoffTaskConfig, generate_from_config


@dataclass
class Args:
    """Generate a handoff bimanual task with dex sidecars."""

    # Task suite name under mesa/task_suites/bddl_files.
    task_suite_name: str
    task_id: str = "handoff_bottled_drink_tray"
    language_instruction: str = "Pick up the bottled drink and hand it off to the other arm, then place it on the tray"
    pick_object: str = "bottled_drink"
    dest_object: str = "tray"
    dest_region: str = "on"
    # Handoff direction. "pick_left_dest_right" (default) → pick on left, dest
    # on right, left arm grasps then right arm receives. "pick_right_dest_left"
    # mirrors all three.
    direction: str = "pick_left_dest_right"
    output_dir: str = "mesa/task_suites/bddl_files"
    make_source: bool = False
    num_source_variants: Optional[int] = None
    num_train_variants: int = 0
    num_eval_variants: int = 0
    add_distractors: bool = False
    source_add_distractors: bool = False
    overwrite: bool = False
    dry_run: bool = False


def _variant_jsons(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return [
        p
        for p in natsorted(folder.iterdir())
        if p.is_file() and p.suffix == ".json" and not p.name.endswith(".dex.json")
    ]


def _write_sidecars(
    task_dir: Path,
    variant_folders: list[str],
    num_subtasks: int,
    dry_run: bool,
    *,
    direction: str = "pick_left_dest_right",
) -> int:
    if direction == "pick_left_dest_right":
        options = [{"left": [0, 1], "right": [2, 3]}]
    else:
        options = [{"left": [2, 3], "right": [0, 1]}]
    validate_arm_assignment_options(options, num_subtasks)

    subtask_dependencies = {"1": [0], "2": [1], "3": [2]}
    validate_subtask_dependencies(subtask_dependencies, num_subtasks)

    written = 0
    for folder_name in variant_folders:
        folder = task_dir / folder_name
        for variant_path in _variant_jsons(folder):
            sidecar_data = {
                "arm_assignment_options": options,
                "subtask_dependencies": subtask_dependencies,
                "inference": {
                    "method": "handoff",
                },
            }

            sidecar_path = variant_path.with_suffix("").with_suffix(".dex.json")
            print(f"  {variant_path.parent.name}/{sidecar_path.name}: {len(options)} arm assignment option(s)")

            if not dry_run:
                with open(sidecar_path, "w", encoding="utf-8") as f:
                    json.dump(sidecar_data, f, indent=2, sort_keys=False)
            written += 1
    return written


def main(args: Args) -> None:
    task_dir = Path(args.output_dir) / args.task_suite_name / args.task_id

    if task_dir.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output directory already exists: {task_dir}. Use --overwrite."
        )

    config = HandoffTaskConfig(
        language_instruction=args.language_instruction,
        task_id=args.task_id,
        task_suite_name=args.task_suite_name,
        output_dir=args.output_dir,
        pick_object=args.pick_object,
        dest_object=args.dest_object,
        dest_region=args.dest_region,
        direction=args.direction,
        make_source=args.make_source,
        num_source_variants=args.num_source_variants,
        num_train_variants=args.num_train_variants,
        num_eval_variants=args.num_eval_variants,
        add_distractors=args.add_distractors,
        source_add_distractors=args.source_add_distractors,
    )

    if not args.dry_run:
        generate_from_config(config, valid_distractor_map=None, verbose=True)

    num_subtasks = 4
    sample = None
    for folder in ["source", "train", "eval"]:
        candidates = _variant_jsons(task_dir / folder)
        if candidates:
            sample = candidates[0]
            break

    if sample is not None:
        with open(sample) as f:
            problem = json.load(f)
        num_subtasks = len(problem["demonstration_states"])

    if args.direction == "pick_left_dest_right":
        first_arm, second_arm = "left", "right"
    else:
        first_arm, second_arm = "right", "left"
    print(f"\nHandoff task ({args.direction}): {num_subtasks} subtask(s)")
    print(f"  subtask 0: {first_arm} arm grasps object")
    print(f"  subtask 1: {first_arm} arm lifts to handoff point")
    print(f"  subtask 2: {second_arm} arm receives object")
    print(f"  subtask 3: {second_arm} arm places at destination")
    print()

    variant_folders = []
    if args.make_source:
        variant_folders.append("source")
    if args.num_train_variants > 0:
        variant_folders.append("train")
    if args.num_eval_variants > 0:
        variant_folders.append("eval")

    written = _write_sidecars(
        task_dir=task_dir,
        variant_folders=variant_folders,
        num_subtasks=num_subtasks,
        dry_run=args.dry_run,
        direction=args.direction,
    )

    print(f"\nDone. sidecars_written={written} dry_run={args.dry_run}")
    print(f"Task ID: {args.task_id}")
    print(f"Output:  {task_dir}")


if __name__ == "__main__":
    main(tyro.cli(Args))
