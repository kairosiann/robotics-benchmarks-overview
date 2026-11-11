"""
Generate .dex.json sidecars for bimanual MimicGen.

Determines per-variant arm assignments based on object placement regions:
  Y < 0 => left arm (robot0)
  Y >= 0 => right arm (robot1)

The resulting sidecar schema matches generate_dataset.py expectations:
{
  "arm_assignment_options": [
    {"left": [...], "right": [...]}
  ],
  "subtask_dependencies": {}
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tyro
from natsort import natsorted

from mesa import MESA_ROOT
import mesa.sim.envs.bddl_utils as BDDLUtils
from mesa.mimicgen.dex.sidecar import validate_arm_assignment_options


@dataclass
class Args:
    # Task suite name under mesa/task_suites/bddl_files
    task_suite_name: str
    # Optional single task id to process; if omitted, process all tasks in suite
    task_id: Optional[str] = None
    # Root for source demos (expects <root>/<suite>/<task>/demo.hdf5)
    source_data_root: str = "data/source"
    # Variant folders to emit sidecars into
    variant_folders: list[str] = field(default_factory=lambda: ["source", "eval", "train"])
    # Overwrite existing sidecars
    overwrite: bool = True
    # Print inferred assignments without writing files
    dry_run: bool = False
    # If true, raise on missing source demos; otherwise skip those tasks
    strict_source: bool = False


def _iter_task_ids(task_suite_path: Path, task_id: Optional[str]) -> list[str]:
    if task_id is not None:
        task_path = task_suite_path / task_id
        if not task_path.is_dir():
            raise FileNotFoundError(f"Task folder not found: {task_path}")
        return [task_id]
    return [p.name for p in sorted(task_suite_path.iterdir()) if p.is_dir()]


def _variant_jsons(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return [
        p
        for p in natsorted(folder.iterdir())
        if p.is_file() and p.suffix == ".json" and (not p.name.endswith(".dex.json"))
    ]


def _infer_arm_from_variant(variant_path: Path, num_subtasks: int) -> dict:
    """Determine arm assignment based on where objects spawn in the variant.

    Looks at table-based object init regions and checks the Y-range midpoint:
      Y < 0 => left side => left arm (robot0)
      Y >= 0 => right side => right arm (robot1)
    """
    with open(variant_path) as f:
        variant = json.load(f)

    y_values = []
    for region_name, region in variant.get("regions", {}).items():
        if not region_name.startswith("table_"):
            continue
        for rect in region.get("ranges", []):
            if len(rect) >= 4:
                y_mid = (rect[1] + rect[3]) / 2.0
                y_values.append(y_mid)

    if not y_values:
        # Fallback: assign all to left
        return {"left": list(range(num_subtasks)), "right": []}

    avg_y = sum(y_values) / len(y_values)
    if avg_y < 0:
        return {"left": list(range(num_subtasks)), "right": []}
    else:
        return {"left": [], "right": list(range(num_subtasks))}


def main(args: Args) -> None:
    suite_path = Path(MESA_ROOT) / "task_suites" / "bddl_files" / args.task_suite_name
    if not suite_path.is_dir():
        raise FileNotFoundError(f"Task suite path not found: {suite_path}")

    source_root = Path(args.source_data_root)
    if not source_root.is_absolute():
        source_root = (Path(MESA_ROOT).parent / source_root).resolve()

    task_ids = _iter_task_ids(suite_path, args.task_id)
    total_written = 0
    total_skipped_existing = 0

    for task in task_ids:
        task_path = suite_path / task
        sample_variant_path = None
        for variant_folder in args.variant_folders:
            candidates = _variant_jsons(task_path / variant_folder)
            if candidates:
                sample_variant_path = candidates[0]
                break
        if sample_variant_path is None:
            print(f"[skip] {task}: no variants found in folders {args.variant_folders}")
            continue

        parsed_problem = BDDLUtils.load_problem(str(sample_variant_path))
        num_subtasks = len(parsed_problem["demonstration_states"])
        if num_subtasks <= 0:
            print(f"[skip] {task}: no demonstration_states in {sample_variant_path}")
            continue

        if args.strict_source:
            source_demo_path = source_root / args.task_suite_name / task / "demo.hdf5"
            if not source_demo_path.exists():
                raise FileNotFoundError(
                    f"[skip] {task}: missing source demo {source_demo_path}"
                )

        print(f"[task] {task}: inferring per-variant arm assignments")

        seen_sidecar_paths: set[Path] = set()
        for variant_folder in args.variant_folders:
            variant_paths = _variant_jsons(task_path / variant_folder)
            if len(variant_paths) == 0:
                continue
            for variant_path in variant_paths:
                sidecar_path = variant_path.with_suffix(".dex.json")
                resolved = sidecar_path.resolve()
                if resolved in seen_sidecar_paths:
                    continue
                seen_sidecar_paths.add(resolved)
                if sidecar_path.exists() and (not args.overwrite):
                    total_skipped_existing += 1
                    continue

                arm_assignments = _infer_arm_from_variant(variant_path, num_subtasks)
                arm_assignment_options = [arm_assignments]
                sidecar_data = {
                    "arm_assignment_options": arm_assignment_options,
                    "subtask_dependencies": {},
                    "inference": {
                        "method": "variant_region_y_range",
                        "variant_path": str(variant_path),
                    },
                }
                validate_arm_assignment_options(arm_assignment_options, num_subtasks=num_subtasks)

                side = "left" if arm_assignments["left"] else "right"
                print(f"  {variant_path.name}: {side} arm")

                if args.dry_run:
                    continue
                with open(sidecar_path, "w", encoding="utf-8") as f:
                    json.dump(sidecar_data, f, indent=2, sort_keys=False)
                total_written += 1

    print(
        f"Done. wrote={total_written} "
        f"skipped_existing={total_skipped_existing} dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main(tyro.cli(Args))
