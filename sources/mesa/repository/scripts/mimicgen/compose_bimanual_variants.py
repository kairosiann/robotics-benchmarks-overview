"""
Compose bimanual BDDL variants from independent single-arm tasks.

Pairs left-arm variants (Y < 0) with right-arm variants (Y >= 0) to create
composed BDDL problems where each arm independently works on its own subtask.

The output is a new task directory under the same task suite with composed
variant files and dex sidecars containing mixed arm assignments.  The composed
variants can be used directly with the existing ``generate_dataset.py``
pipeline with ``--bimanual``.

Pre-requisites:
    Dex sidecars must already exist for the source tasks.  Run
    ``generate_dex_sidecars.py`` first.

    For cross-task composition the source demo_lookup.json used at generation
    time must cover object categories from *both* tasks.

Examples::

    # Pair left and right variants within the same task:
    uv run scripts/mimicgen/compose_bimanual_variants.py \\
        --task-suite-name bimesa \\
        --left-task-id apple_tray_on

    # Pair variants across two different tasks:
    uv run scripts/mimicgen/compose_bimanual_variants.py \\
        --task-suite-name bimesa \\
        --left-task-id apple_tray_on \\
        --right-task-id orange_bowl_on
"""

from __future__ import annotations

import copy
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tyro
from natsort import natsorted

from mesa import MESA_ROOT
import mesa.sim.envs.bddl_utils as BDDLUtils
from mesa.mimicgen.dex.sidecar import load_dex_sidecar, validate_arm_assignment_options

# Instance names that refer to shared physical scene elements and must never
# be duplicated or renamed during composition.
_SHARED_INSTANCES = frozenset({"table"})


@dataclass
class Args:
    """Compose bimanual BDDL variants from independent single-arm tasks."""

    # Task suite name under mesa/task_suites/bddl_files.
    task_suite_name: str
    # Task ID providing left-arm variants.
    left_task_id: str
    # Task ID providing right-arm variants.  Defaults to left_task_id.
    right_task_id: Optional[str] = None
    # Variant folder to read from and write to.
    variant_folder: str = "source"
    # Override the output task ID.  Auto-generated if omitted.
    output_task_id: Optional[str] = None
    # Maximum number of composed variant pairs to emit.
    max_pairs: Optional[int] = None
    # Print composed variants without writing files.
    dry_run: bool = False
    # Overwrite existing composed variants.
    overwrite: bool = False
    # Compose sequentially: right arm waits for all left arm subtasks to complete.
    sequential: bool = False


def _variant_jsons(folder: Path) -> list[Path]:
    """List BDDL variant JSON files in *folder*, excluding dex sidecars."""
    if not folder.exists():
        return []
    return [
        p
        for p in natsorted(folder.iterdir())
        if p.is_file() and p.suffix == ".json" and not p.name.endswith(".dex.json")
    ]


def _classify_variants_by_arm(
    variant_paths: list[Path],
) -> tuple[list[Path], list[Path]]:
    """Split variants into left-arm and right-arm lists using dex sidecars.

    Only classifies variants that have a single arm_assignment_option with all
    subtasks on one arm.  Variants with mixed or multiple options are skipped.
    """
    left: list[Path] = []
    right: list[Path] = []
    for vp in variant_paths:
        sidecar = load_dex_sidecar(str(vp))
        options = sidecar["arm_assignment_options"]
        if len(options) != 1:
            continue
        arm = options[0]
        if arm["right"] and not arm["left"]:
            right.append(vp)
        elif arm["left"] and not arm["right"]:
            left.append(vp)
    return left, right


def _build_rename_map(problem: dict, suffix: str) -> dict[str, str]:
    """Map every non-shared instance name in *problem* to a suffixed version."""
    rename: dict[str, str] = {}
    for _cat, instances in problem.get("objects", {}).items():
        for inst in instances:
            rename[inst] = f"{inst}{suffix}"
    for _cat, instances in problem.get("fixtures", {}).items():
        for inst in instances:
            if inst in _SHARED_INSTANCES:
                continue
            rename[inst] = f"{inst}{suffix}"
    return rename


def _rename_in_string(s: str, rename: dict[str, str]) -> str:
    """Replace instance names inside *s* (longest-first to avoid partial matches)."""
    for old, new in sorted(rename.items(), key=lambda kv: len(kv[0]), reverse=True):
        s = s.replace(old, new)
    return s


def _rename_predicate(
    pred: list,
    instance_rename: dict[str, str],
    region_rename: dict[str, str],
) -> list:
    """Rename instance and region references inside a single predicate list."""
    return [pred[0]] + [
        instance_rename.get(a, region_rename.get(a, a)) if isinstance(a, str) else a
        for a in pred[1:]
    ]


def _apply_renames(problem: dict, rename: dict[str, str]) -> dict:
    """Deep-copy *problem* and apply *rename* to all instance references."""
    p = copy.deepcopy(problem)

    for cat in list(p["objects"]):
        p["objects"][cat] = [rename.get(i, i) for i in p["objects"][cat]]

    for cat in list(p["fixtures"]):
        p["fixtures"][cat] = [rename.get(i, i) for i in p["fixtures"][cat]]

    region_rename: dict[str, str] = {}
    new_regions: dict[str, dict] = {}
    for rname, rdef in p["regions"].items():
        new_name = _rename_in_string(rname, rename)
        region_rename[rname] = new_name
        new_def = copy.deepcopy(rdef)
        if "target" in new_def:
            new_def["target"] = rename.get(new_def["target"], new_def["target"])
        new_regions[new_name] = new_def
    p["regions"] = new_regions

    p["initial_state"] = [
        _rename_predicate(pred, rename, region_rename)
        for pred in p["initial_state"]
    ]
    if p["goal_state"] and p["goal_state"][0] == "and":
        p["goal_state"] = ["and"] + [
            _rename_predicate(pred, rename, region_rename)
            for pred in p["goal_state"][1:]
        ]
    p["demonstration_states"] = [
        _rename_predicate(pred, rename, region_rename)
        for pred in p["demonstration_states"]
    ]
    if "distractor_goal_specs" in p:
        p["distractor_goal_specs"] = [
            _rename_predicate(pred, rename, region_rename)
            for pred in p["distractor_goal_specs"]
        ]

    return p


def _validate_composed_problem(problem: dict) -> None:
    """Sanity-check that all references in *problem* resolve to known names."""
    all_instances: set[str] = set()
    for _cat, insts in problem["objects"].items():
        all_instances.update(insts)
    for _cat, insts in problem["fixtures"].items():
        all_instances.update(insts)
    all_regions = set(problem["regions"].keys())
    known = all_instances | all_regions

    for rname, rdef in problem["regions"].items():
        target = rdef.get("target")
        if target and target not in all_instances:
            raise ValueError(
                f"Region '{rname}' references unknown target '{target}'"
            )

    def _check_preds(label: str, preds: list) -> None:
        for pred in preds:
            if not isinstance(pred, list):
                continue
            for arg in pred[1:]:
                if isinstance(arg, str) and arg not in known:
                    raise ValueError(
                        f"{label} references unknown name '{arg}': {pred}"
                    )

    _check_preds("initial_state", problem["initial_state"])
    _check_preds("demonstration_states", problem["demonstration_states"])
    _check_preds("goal_state", problem["goal_state"][1:])
    _check_preds("distractor_goal_specs", problem.get("distractor_goal_specs", []))


def compose_problems(
    left: dict,
    right: dict,
    sequential: bool = False,
) -> tuple[dict, dict]:
    """Merge a left-arm and right-arm BDDL problem into a single bimanual problem.

    Right-side instances are suffixed with ``_r`` to avoid name collisions.

    Returns:
        composed: the merged BDDL problem dict.
        arm_assignments: ``{"left": [...], "right": [...]}`` for dex sidecar.
    """
    rename = _build_rename_map(right, "_r")
    right = _apply_renames(right, rename)

    objects: dict[str, list[str]] = copy.deepcopy(left["objects"])
    for cat, insts in right["objects"].items():
        if cat in objects:
            objects[cat] = objects[cat] + insts
        else:
            objects[cat] = list(insts)

    fixtures: dict[str, list[str]] = copy.deepcopy(left["fixtures"])
    for cat, insts in right["fixtures"].items():
        if cat in fixtures:
            existing = set(fixtures[cat])
            for inst in insts:
                if inst not in existing:
                    fixtures[cat].append(inst)
        else:
            fixtures[cat] = list(insts)

    regions = {**copy.deepcopy(left["regions"]), **right["regions"]}

    seen: set[str] = set()
    initial_state: list[list] = []
    for pred in left["initial_state"] + right["initial_state"]:
        key = json.dumps(pred, sort_keys=True)
        if key not in seen:
            seen.add(key)
            initial_state.append(pred)

    left_goals = left["goal_state"][1:] if left["goal_state"][0] == "and" else [left["goal_state"]]
    right_goals = right["goal_state"][1:] if right["goal_state"][0] == "and" else [right["goal_state"]]
    goal_state: list = ["and"] + left_goals + right_goals

    demo_states = left["demonstration_states"] + right["demonstration_states"]

    distractors = (
        left.get("distractor_goal_specs", [])
        + right.get("distractor_goal_specs", [])
    )

    left_lang = left.get("language_instruction", [])
    right_lang = right.get("language_instruction", [])
    if left_lang and right_lang:
        joiner = ["then"] if sequential else ["and"]
        language = left_lang + joiner + right_lang
    else:
        language = left_lang or right_lang

    num_left = len(left["demonstration_states"])
    num_right = len(right["demonstration_states"])
    arm_assignments = {
        "left": list(range(num_left)),
        "right": list(range(num_left, num_left + num_right)),
    }

    composed = {
        "problem_name": left["problem_name"],
        "fixtures": fixtures,
        "regions": regions,
        "objects": objects,
        "textures": left.get("textures", {}),
        "camera": left.get("camera", {}),
        "lighting": left.get("lighting", {}),
        "styles": left.get("styles", {}),
        "scene_properties": left.get("scene_properties", {}),
        "initial_state": initial_state,
        "goal_state": goal_state,
        "distractor_goal_specs": distractors,
        "demonstration_states": demo_states,
        "language_instruction": language,
    }

    _validate_composed_problem(composed)
    return composed, arm_assignments


def main(args: Args) -> None:
    suite_path = Path(MESA_ROOT) / "task_suites" / "bddl_files" / args.task_suite_name
    if not suite_path.is_dir():
        raise FileNotFoundError(f"Task suite not found: {suite_path}")

    right_task_id = args.right_task_id or args.left_task_id
    same_task = right_task_id == args.left_task_id

    left_dir = suite_path / args.left_task_id / args.variant_folder
    right_dir = suite_path / right_task_id / args.variant_folder

    left_all = _variant_jsons(left_dir)
    right_all = _variant_jsons(right_dir)
    if not left_all:
        raise FileNotFoundError(f"No variants found in {left_dir}")
    if not right_all:
        raise FileNotFoundError(f"No variants found in {right_dir}")

    left_arm_variants, _ = _classify_variants_by_arm(left_all)
    _, right_arm_variants = _classify_variants_by_arm(right_all)

    if not left_arm_variants:
        raise ValueError(
            f"No left-arm variants found for {args.left_task_id}. "
            f"Run generate_dex_sidecars.py first."
        )
    if not right_arm_variants:
        raise ValueError(
            f"No right-arm variants found for {right_task_id}. "
            f"Run generate_dex_sidecars.py first."
        )

    print(f"Left-arm variants  ({args.left_task_id}): {len(left_arm_variants)}")
    print(f"Right-arm variants ({right_task_id}): {len(right_arm_variants)}")

    pairs = list(itertools.product(left_arm_variants, right_arm_variants))
    if args.max_pairs is not None:
        pairs = pairs[: args.max_pairs]
    if not pairs:
        print("No valid pairs found.")
        return

    print(f"Composing {len(pairs)} variant pair(s)\n")

    if args.output_task_id:
        output_task_id = args.output_task_id
    elif same_task:
        suffix = "__sequential" if args.sequential else "__composed"
        output_task_id = f"{args.left_task_id}{suffix}"
    else:
        joiner = "__then__" if args.sequential else "__x__"
        output_task_id = f"{args.left_task_id}{joiner}{right_task_id}"

    output_dir = suite_path / output_task_id / args.variant_folder
    if output_dir.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output directory already exists: {output_dir}. "
            f"Use --overwrite to replace."
        )

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for idx, (left_path, right_path) in enumerate(pairs):
        left_problem = BDDLUtils.load_problem(str(left_path))
        right_problem = BDDLUtils.load_problem(str(right_path))

        composed, arm_assignments = compose_problems(left_problem, right_problem, sequential=args.sequential)
        num_subtasks = len(composed["demonstration_states"])
        arm_assignment_options = [arm_assignments]
        validate_arm_assignment_options(arm_assignment_options, num_subtasks)

        subtask_dependencies = {}
        if args.sequential:
            first_right = min(arm_assignments["right"])
            subtask_dependencies = {
                str(first_right): list(arm_assignments["left"])
            }

        variant_name = f"{idx:03d}"
        variant_path = output_dir / f"{variant_name}.json"
        sidecar_path = output_dir / f"{variant_name}.dex.json"

        sidecar_data = {
            "arm_assignment_options": arm_assignment_options,
            "subtask_dependencies": subtask_dependencies,
            "inference": {
                "method": "composed",
                "left_variant": str(left_path),
                "right_variant": str(right_path),
            },
        }

        print(
            f"  {variant_name}: "
            f"L={args.left_task_id}/{left_path.stem} + "
            f"R={right_task_id}/{right_path.stem}  "
            f"arms left={arm_assignments['left']} right={arm_assignments['right']}"
        )

        if args.dry_run:
            continue

        with open(variant_path, "w", encoding="utf-8") as f:
            json.dump(composed, f, indent=2, sort_keys=False)
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(sidecar_data, f, indent=2, sort_keys=False)
        written += 1

    print(f"\nDone. wrote={written} pairs={len(pairs)} dry_run={args.dry_run}")
    print(f"Output task: {output_task_id}")
    if written > 0:
        print(f"Output dir:  {output_dir}")


if __name__ == "__main__":
    main(tyro.cli(Args))
