"""
Generate a sequential bimanual task from a single-arm articulated multistep skeleton.

Unlike ``compose_bimanual_variants.py`` (which merges two independent single-arm
tasks and duplicates objects), this script keeps a single shared set of objects
and splits the demonstration_states across arms with subtask dependency constraints.

Sidecars specify ``arm_assignment_options`` — all valid ways to distribute
subtasks across arms (left opens / right places, right opens / left places,
single arm does everything).  During MimicGen generation, one option is randomly
sampled per attempt for diversity.  ``subtask_dependencies`` enforce ordering
(place waits for open).  The operator freely chooses arms during collection;
``parse_dataset`` infers ``source_arm`` per demo from actual action energy.

Example (sliding_top_box)::

    uv run scripts/mimicgen/generate_sequential_task.py \
        --task-suite-name bimesa \
        --pick-object apple \
        --fixture sliding_top_box \
        --fixture-contain-region contain_region \
        --make-source

Example (cabinet)::

    uv run scripts/mimicgen/generate_sequential_task.py \
        --task-suite-name bimesa \
        --task-id open_and_apple_cabinet_top_region__sequential \
        --language-instruction "Open the top drawer of the cabinet and put the apple in it" \
        --pick-object apple \
        --fixture cabinet \
        --fixture-articulation-region top_region \
        --fixture-contain-region top_region \
        --make-source
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tyro
from natsort import natsorted

from mesa.sim.task_gen import (
    ArticulatedMultistepTaskConfig,
    generate_from_config,
)
from mesa.mimicgen.dex.sidecar import validate_arm_assignment_options, validate_subtask_dependencies


@dataclass
class Args:
    """Generate a sequential bimanual task with dex sidecars."""

    # Task suite name under mesa/task_suites/bddl_files.
    task_suite_name: str
    # Output task ID.
    task_id: str = "open_and_apple_sliding_top_box__sequential"
    # Language instruction for the task.
    language_instruction: str = "Open the box and then put the apple in it"
    # Grasp object category (from object_categories.py).
    pick_object: str = "apple"
    # Articulated fixture category.
    fixture: str = "sliding_top_box"
    # Articulation region of the fixture (e.g. top_region for cabinet, None for sliding_top_box).
    fixture_articulation_region: Optional[str] = None
    # Containment region of the fixture.
    fixture_contain_region: Optional[str] = "contain_region"
    # Whether the fixture starts closed (True for "open and place" tasks).
    start_closed: bool = True
    # Whether the fixture ends closed.
    end_closed: bool = False
    # Only include mixed-arm assignment options (exclude single-arm-does-all).
    # Use for coordination tasks where both arms must participate.
    coordination_only: bool = False
    # Output directory for BDDL files.
    output_dir: str = "mesa/task_suites/bddl_files"
    # Generate source variants (iterates over object assets).
    make_source: bool = False
    # Number of source variants to generate. When None, defaults to the asset cap.
    # Set this to override (e.g. 100) for raw-path tasks where source/ holds the
    # actual training scenes.
    num_source_variants: Optional[int] = None
    # Number of training variants to generate.
    num_train_variants: int = 0
    # Number of evaluation variants to generate.
    num_eval_variants: int = 0
    # Add distractor objects to non-source variants.
    add_distractors: bool = False
    # Also add distractors to source variants. Required for raw-path tasks
    # (no MimicGen) where the source demo IS the training demo. Requires
    # add_distractors=True.
    source_add_distractors: bool = False
    # Per-role spatial constraints. When ANY of these is set, the legacy
    # `constrain_side="center"` default is dropped and only the per-role values
    # apply. Useful for raw-path single-arm articulated tasks (bimesa) that
    # want pick-side and fixture-side aligned via "alternate" so each variant
    # index lands on the matching arm. When all three are None, fall back to
    # constrain_side="center" (back-compat with the existing turn-taking flow).
    constrain_pick_side: Optional[str] = None
    constrain_dest_side: Optional[str] = None
    fixture_side: Optional[str] = None
    # Overwrite existing output.
    overwrite: bool = False
    # Print what would be generated without writing files.
    dry_run: bool = False


def _variant_jsons(folder: Path) -> list[Path]:
    """List BDDL variant JSON files in *folder*, excluding dex sidecars."""
    if not folder.exists():
        return []
    return [
        p
        for p in natsorted(folder.iterdir())
        if p.is_file() and p.suffix == ".json" and not p.name.endswith(".dex.json")
    ]


def _build_arm_assignment_options(
    num_subtasks: int,
    open_subtasks: list[int],
    place_subtasks: list[int],
    *,
    mixed_only: bool = False,
) -> list[dict]:
    """Build valid arm assignment options for a sequential task.

    Always includes the two mixed-arm options (left opens / right places and
    vice versa).  When *mixed_only* is ``False`` (default), also includes the
    two single-arm-does-all options.  Use ``mixed_only=True`` for coordination
    tasks where both arms must participate.
    """
    options = [
        {"left": list(open_subtasks), "right": list(place_subtasks)},
        {"left": list(place_subtasks), "right": list(open_subtasks)},
    ]
    if not mixed_only:
        all_subtasks = sorted(open_subtasks + place_subtasks)
        options.extend([
            {"left": list(all_subtasks), "right": []},
            {"left": [], "right": list(all_subtasks)},
        ])
    validate_arm_assignment_options(options, num_subtasks)
    return options


def _build_subtask_dependencies(
    open_subtasks: list[int],
    place_subtasks: list[int],
) -> dict[str, list[int]]:
    """Build subtask dependency constraints from phase ordering.

    Demonstration states follow a fixed phase order: open → place → close.
    Each phase transition creates a dependency — the first subtask of the
    next phase must wait for the last subtask of the previous phase.

    Patterns:
        [open → place]:       grasp depends on open        {"1": [0]}
        [place → close]:      close depends on in (place)  {"2": [1]}
        [open → place → close]: grasp depends on open,
                                close depends on in         {"1": [0], "3": [2]}
    """
    deps: dict[str, list[int]] = {}

    # open subtasks before place subtasks → first place depends on prior opens
    opens_before_place = [i for i in open_subtasks if i < min(place_subtasks)]
    if opens_before_place:
        first_place = min(place_subtasks)
        deps[str(first_place)] = opens_before_place

    # open subtasks after place subtasks (i.e. close) → close depends on last place
    closes_after_place = [i for i in open_subtasks if i > max(place_subtasks)]
    if closes_after_place:
        last_place = max(place_subtasks)
        first_close = min(closes_after_place)
        deps[str(first_close)] = [last_place]

    return deps


def _write_sidecars(
    task_dir: Path,
    variant_folders: list[str],
    num_subtasks: int,
    open_subtasks: list[int],
    place_subtasks: list[int],
    dry_run: bool,
    *,
    mixed_only: bool = False,
) -> int:
    """Write dex sidecars with randomized arm assignment options for all variants.

    Each sidecar contains ``arm_assignment_options`` — a list of all valid ways
    to distribute subtasks across arms.  During generation, one is randomly
    sampled per attempt.  Returns the number of sidecars written.
    """
    options = _build_arm_assignment_options(
        num_subtasks, open_subtasks, place_subtasks, mixed_only=mixed_only,
    )

    subtask_dependencies = _build_subtask_dependencies(open_subtasks, place_subtasks)
    validate_subtask_dependencies(subtask_dependencies, num_subtasks)

    written = 0
    for folder_name in variant_folders:
        folder = task_dir / folder_name
        for variant_path in _variant_jsons(folder):
            sidecar_data = {
                "arm_assignment_options": options,
                "subtask_dependencies": subtask_dependencies,
                "inference": {
                    "method": "sequential",
                },
            }

            sidecar_path = variant_path.with_suffix("").with_suffix(".dex.json")
            print(f"  {variant_path.parent.name}/{sidecar_path.name}: {len(options)} arm assignment options")

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

    # Step 1: Generate BDDL files using the articulated multistep skeleton.
    # Default: objects spawn in the center of the table so both arms can always
    # reach everything (turn-taking). When the caller passes any per-role side
    # constraint, drop the center default and use the per-role values instead.
    side_kwargs: dict[str, object] = {}
    if (
        args.constrain_pick_side is None
        and args.constrain_dest_side is None
        and args.fixture_side is None
    ):
        side_kwargs["constrain_side"] = "center"
    else:
        if args.constrain_pick_side is not None:
            side_kwargs["constrain_pick_side"] = args.constrain_pick_side
        if args.constrain_dest_side is not None:
            side_kwargs["constrain_dest_side"] = args.constrain_dest_side
        if args.fixture_side is not None:
            side_kwargs["fixture_side"] = args.fixture_side

    config = ArticulatedMultistepTaskConfig(
        language_instruction=args.language_instruction,
        task_id=args.task_id,
        task_suite_name=args.task_suite_name,
        output_dir=args.output_dir,
        pick_object=args.pick_object,
        fixture=args.fixture,
        fixture_articulation_region=args.fixture_articulation_region,
        fixture_contain_region=args.fixture_contain_region,
        start_closed=args.start_closed,
        end_closed=args.end_closed,
        make_source=args.make_source,
        num_source_variants=args.num_source_variants,
        num_train_variants=args.num_train_variants,
        num_eval_variants=args.num_eval_variants,
        add_distractors=args.add_distractors,
        source_add_distractors=args.source_add_distractors,
        **side_kwargs,
    )

    if not args.dry_run:
        generate_from_config(config, valid_distractor_map=None, verbose=True)

    # Step 2: Determine subtask split.
    #
    # ArticulatedMultistepTask produces demonstration_states like:
    #   [0] ["open", "articulated_object_top_region"]   -> open arm
    #   [1] ["grasp", "object_0"]                       -> place arm
    #   [2] ["in", "object_0", "..."]                   -> place arm
    #   (optionally [3] ["close", "..."]                -> open arm)
    #
    # We split: open/close subtasks go to one arm, grasp/place to the other.

    # Read a sample variant to discover the actual demonstration_states.
    sample = None
    for folder in ["source", "train", "eval"]:
        candidates = _variant_jsons(task_dir / folder)
        if candidates:
            sample = candidates[0]
            break

    if sample is None:
        if args.dry_run:
            # Estimate from config
            num_open = 1 if args.start_closed else 0
            num_close = 1 if args.end_closed else 0
            num_pick = 2 if args.pick_object else 0
            num_subtasks = num_open + num_pick + num_close
            open_subtasks = [0] if args.start_closed else []
            place_subtasks = list(range(num_open, num_open + num_pick))
            if args.end_closed:
                open_subtasks.append(num_subtasks - 1)
        else:
            raise RuntimeError("No variants generated — nothing to write sidecars for.")
    else:
        with open(sample) as f:
            problem = json.load(f)
        demo_states = problem["demonstration_states"]
        num_subtasks = len(demo_states)

        open_subtasks = []
        place_subtasks = []
        for i, state in enumerate(demo_states):
            if state[0] in ("open", "close"):
                open_subtasks.append(i)
            else:
                place_subtasks.append(i)

    print(f"\nSubtask split ({num_subtasks} total):")
    print(f"  open/close arm: {open_subtasks}")
    print(f"  grasp/place arm: {place_subtasks}")
    print()

    # Step 3: Write dex sidecars with arm assignment options.
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
        open_subtasks=open_subtasks,
        place_subtasks=place_subtasks,
        dry_run=args.dry_run,
        mixed_only=args.coordination_only,
    )

    print(f"\nDone. sidecars_written={written} dry_run={args.dry_run}")
    print(f"Task ID: {args.task_id}")
    print(f"Output:  {task_dir}")


if __name__ == "__main__":
    main(tyro.cli(Args))
