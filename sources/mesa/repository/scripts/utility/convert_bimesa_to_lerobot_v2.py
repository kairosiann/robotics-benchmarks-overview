"""Driver: build per-task LeRobot datasets for the bimesa training split (v2).

This is the second-pass merge that combines MimicGen (MG) output with manually
collected raw demos. It produces one LeRobot dataset per *training task*
(not per MG variant family). Per-block caps are set in ``BLOCK_CAPS``.

Output is in LeRobot v3.0 dataset format (the openpi-mesa converter uses the
`pairlab/lerobot` fork which writes v3.0 natively). The "v2" in this script's
name refers to the *merge pass* version, not the LeRobot dataset format.

Sources
-------
- MG output:  ``data/gen_data/bimesa/<variant>/demo/tmp/*.hdf5``
- Raw demos:  ``<RAW_SOURCE_ROOT>/<variant>/*.hdf5``  (manually collected;
              one HDF5 per demo, no demo/tmp subdir.)

Per-task budget
---------------
- Block A (spatial pnp, 27 tasks): 3 non-held-out combos. Aligned combos
  (`left_left`, `right_right`) use MG output. Cross combos
  (`pick_left_dest_right`, `pick_right_dest_left`) use raw. Cap each combo
  at ~33, then backfill from combos with extra demos until total = 100.
- Block B (handoff, 17 tasks): single raw source. min(100, available).
- Block C MG (#1-#13, 13 tasks): single MG source. min(100, available).

Tasks with fewer than --min-demos demos available are skipped.

Subsampling: first N HDF5s by sorted filename (deterministic).

Output
------
A new lerobot home is written to ``HF_LEROBOT_HOME`` or ``--lerobot-home``
(default ``data/lerobot/bimesa``); one dataset per task.

The openpi-mesa converter is invoked per task. Each source variant is staged
as a symlink tree at ``<staging>/<variant_label>/demo/tmp/<NNNN>.hdf5`` so the
converter's existing ``--raw-dirs`` glob works for both MG (which is already
in ``demo/tmp/`` layout) and raw (which has flat HDF5 files).

Usage
-----
  uv run --no-sync scripts/utility/convert_bimesa_to_lerobot_v2.py --dry-run
  uv run --no-sync scripts/utility/convert_bimesa_to_lerobot_v2.py \
      --task apple_tray_on --task handoff_water_bottle_tray_on
  uv run --no-sync scripts/utility/convert_bimesa_to_lerobot_v2.py  # all tasks
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import h5py

REPO_ROOT = Path(__file__).resolve().parents[2]

# ----------------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------------
# Block A aligned-combo MG output (legacy gen_data/ path; no mirror-fixture issue).
DEFAULT_MG_ROOT = REPO_ROOT / "data" / "gen_data" / "bimesa"
# Block C MG output (v5 no-mirror re-run). Kept separate: the regen remapped
# variant_idx -> BDDL, so mixing with the old gen_data/ corrupts the dataset.
DEFAULT_BLOCKC_MG_ROOT = REPO_ROOT / "data" / "gen_data" / "bimesa_blockc_v5"
DEFAULT_RAW_ROOT = REPO_ROOT / "data" / "source" / "bimesa"
DEFAULT_BDDL_ROOT = REPO_ROOT / "mesa" / "task_suites" / "bddl_files" / "bimesa"
# openpi-mesa converter: sibling checkout by default (override with --openpi-dir).
DEFAULT_OPENPI = REPO_ROOT.parent / "openpi-mesa"
DEFAULT_VENV = DEFAULT_OPENPI / ".venv"
DEFAULT_LEROBOT_HOME = REPO_ROOT / "data" / "lerobot" / "bimesa"

MIN_DEMOS_DEFAULT = 10

# Per-block source caps: (mg_per_source, raw_per_source). Block A caps each MG
# aligned combo at 40 and takes all cross-combo raw; the rest are single-source.
BLOCK_CAPS: dict[str, tuple[int, int]] = {
    "A":     (40, 100),
    "B":     (0, 100),
    "C_MG":  (80, 0),
}

# ----------------------------------------------------------------------------
# Task specification
# ----------------------------------------------------------------------------
# Block A spatial pnp: task_id -> held-out combo (the other 3 combos train).
BLOCK_A: dict[str, str] = {
    "apple_tray_on":                       "left_left",
    "onion_tray_on":                       "pick_left_dest_right",
    "lime_tray_on":                        "right_right",
    "tangerine_tray_on":                   "pick_right_dest_left",
    "bell_pepper_tray_on":                 "left_left",
    "candle_tray_on":                      "pick_right_dest_left",
    "coffee_cup_tray_on":                  "pick_right_dest_left",
    "lemon_plate_on":                      "pick_right_dest_left",
    "orange_plate_on":                     "pick_left_dest_right",
    "mango_plate_on":                      "right_right",
    "kiwi_plate_on":                       "pick_right_dest_left",
    "beer_plate_on":                       "right_right",
    "lime_bowl_on":                        "left_left",
    "mushroom_bowl_on":                    "pick_left_dest_right",
    "apple_bowl_on":                       "right_right",
    "jam_basket_contain_region":           "pick_left_dest_right",
    "yogurt_basket_contain_region":        "pick_right_dest_left",
    "mango_basket_contain_region":         "left_left",
    "bell_pepper_basket_contain_region":   "pick_left_dest_right",
    "bottled_drink_basket_contain_region": "right_right",
    "orange_cutting_board_on":             "left_left",
    "kiwi_cutting_board_on":               "pick_left_dest_right",
    "tangerine_cutting_board_on":          "right_right",
    "onion_cutting_board_on":              "pick_right_dest_left",
    "garlic_pan_on":                       "pick_left_dest_right",
    "onion_pan_on":                        "right_right",
    "can_pan_on":                          "right_right",
}

# Block B handoff: single raw source, no combo split.
BLOCK_B: list[str] = [
    "handoff_water_bottle_tray_on",
    "handoff_beer_plate_on",
    "handoff_wine_cutting_board_on",
    "handoff_bottled_water_basket_contain_region",
    "handoff_can_pan_on",
    "handoff_jam_bowl_drainer_right_region",
    "handoff_bottled_drink_basket_contain_region",
    "handoff_coffee_cup_tray_on",
    "handoff_spray_basket_contain_region",
    "handoff_milk_tray_on",
    "handoff_candle_tray_on",
    "handoff_alcohol_basket_contain_region",
    "handoff_jug_basket_contain_region",
    "handoff_ketchup_plate_on",
    "handoff_condiment_plate_on",
    "handoff_soap_dispenser_tray_on",
    "handoff_yogurt_bowl_on",
]

# Block C single-arm articulated MG (#1-13): single MG source.
BLOCK_C_MG: list[str] = [
    "open_and_candle_slide_cabinet_contain_region",
    "open_and_book_slide_cabinet_contain_region",
    "open_and_can_slide_cabinet_contain_region",
    "open_and_beer_slide_cabinet_contain_region",
    "open_and_can_sliding_top_box_contain_region",
    "open_and_apple_sliding_top_box_contain_region",
    "beer_slide_cabinet_contain_region_and_close",
    "mango_slide_cabinet_contain_region_and_close",
    "apple_sliding_top_box_contain_region_and_close",
    "lemon_sliding_top_box_contain_region_and_close",
    "open_and_mango_sliding_top_box_contain_region_and_close",
    "open_and_can_sliding_top_box_contain_region_and_close",
    "open_and_orange_slide_cabinet_contain_region_and_close",
]

ALL_COMBOS = ("left_left", "right_right", "pick_left_dest_right", "pick_right_dest_left")
ALIGNED_COMBOS = {"left_left", "right_right"}


# ----------------------------------------------------------------------------
# Per-task source resolution
# ----------------------------------------------------------------------------
@dataclass
class Source:
    """One source of demos for a task."""

    label: str           # variant label (used as subdir name when staging)
    path: Path           # directory containing the source HDF5s
    kind: str            # "mg" or "raw"
    files: list[Path] = field(default_factory=list)  # populated by scan()

    def scan(self) -> None:
        if self.kind == "mg":
            tmp = self.path / "demo" / "tmp"
            self.files = sorted(tmp.glob("*.hdf5")) if tmp.is_dir() else []
        else:  # raw
            self.files = sorted(self.path.glob("*.hdf5")) if self.path.is_dir() else []


@dataclass
class TaskPlan:
    task_id: str
    block: str
    sources: list[Source]
    selected: dict[str, list[Path]] = field(default_factory=dict)  # label -> files

    @property
    def total_available(self) -> int:
        return sum(len(s.files) for s in self.sources)

    @property
    def total_selected(self) -> int:
        return sum(len(v) for v in self.selected.values())


def make_sources(
    task_id: str,
    block: str,
    mg_root: Path,
    raw_root: Path,
    blockc_mg_root: Path,
) -> list[Source]:
    if block == "A":
        held_out = BLOCK_A[task_id]
        used_combos = [c for c in ALL_COMBOS if c != held_out]
        out = []
        for combo in used_combos:
            label = f"{task_id}__{combo}"
            if combo in ALIGNED_COMBOS:
                out.append(Source(label=label, path=mg_root / label, kind="mg"))
            else:
                out.append(Source(label=label, path=raw_root / label, kind="raw"))
        return out
    if block == "B":
        return [Source(label=task_id, path=raw_root / task_id, kind="raw")]
    if block == "C_MG":
        return [Source(label=task_id, path=blockc_mg_root / task_id, kind="mg")]
    raise ValueError(f"unknown block: {block}")


# ----------------------------------------------------------------------------
# Per-task selection (subsample to budget)
# ----------------------------------------------------------------------------
_RAW_REQUIRED_KEYS = ("obs/robot0_joint_pos", "obs/robot1_joint_pos", "actions")


def _raw_hdf5_is_valid(path: Path) -> bool:
    """Probe a raw HDF5 for the keys the converter needs.

    A handful of files under ``bimesa_sim/source/`` are partial recordings
    that are missing ``obs/robot{0,1}_joint_pos`` and ``actions`` entirely.
    Without this check the converter crashes mid-task at the first such file
    (build_state / build_action_joint_pos both KeyError).
    """
    try:
        with h5py.File(path, "r") as f:
            ep = f["data/demo_0"]
            for k in _RAW_REQUIRED_KEYS:
                if k not in ep:
                    return False
        return True
    except (OSError, KeyError):
        return False


def select_demos(
    sources: list[Source], mg_per_source: int, raw_per_source: int
) -> dict[str, list[Path]]:
    """Take up to mg_per_source MG demos and raw_per_source raw demos per source.

    Returns label -> selected file list (first-N by sorted filename). Raw
    sources are validated lazily and corrupt HDF5s are skipped silently.
    """
    out: dict[str, list[Path]] = {}
    for s in sources:
        cap = mg_per_source if s.kind == "mg" else raw_per_source
        if s.kind == "mg":
            out[s.label] = s.files[: min(len(s.files), cap)]
            continue
        chosen: list[Path] = []
        for f in s.files:
            if len(chosen) >= cap:
                break
            if _raw_hdf5_is_valid(f):
                chosen.append(f)
        out[s.label] = chosen
    return out


# ----------------------------------------------------------------------------
# Language instruction
# ----------------------------------------------------------------------------
def language_instruction(bddl_root: Path, sources: list[Source]) -> str:
    """Read language instruction from the first source variant's BDDL.

    All variants of a task share the same instruction. Prefer ``source/000.json``
    because handoff/lift tasks have no ``train/`` split.
    """
    for s in sources:
        for split in ("source", "train"):
            bddl = bddl_root / s.label / split / "000.json"
            if bddl.is_file():
                with bddl.open() as f:
                    data = json.load(f)
                tokens = data.get("language_instruction") or []
                if tokens:
                    return " ".join(tokens)
    raise FileNotFoundError(
        f"No BDDL with language_instruction found for sources: {[s.label for s in sources]}"
    )


# ----------------------------------------------------------------------------
# Staging + conversion
# ----------------------------------------------------------------------------
def stage_demos(plan: TaskPlan, staging_root: Path) -> Path:
    """Symlink selected demos into ``staging_root/<variant_label>/demo/tmp/<NNNN>.hdf5``.

    Returns the per-task staging dir. The converter is invoked with one
    ``--raw-dirs`` entry per variant subdir (each in the
    ``<variant>/demo/tmp/`` layout it expects).
    """
    task_root = staging_root / plan.task_id
    if task_root.exists():
        shutil.rmtree(task_root)
    task_root.mkdir(parents=True)
    for label, files in plan.selected.items():
        if not files:
            continue
        tmp = task_root / label / "demo" / "tmp"
        tmp.mkdir(parents=True)
        for i, src in enumerate(files):
            # Zero-padded index prefixes the original name: stable order + traceable.
            link = tmp / f"{i:04d}__{src.name}"
            link.symlink_to(src.resolve())
    return task_root


def build_command(*, repo_id: str, task: str, raw_dirs: list[Path], fps: int) -> list[str]:
    cmd = [
        "uv", "run", "--no-sync",
        "examples/mesa/convert_mesa_data_to_lerobot.py",
        "--repo-id", repo_id,
        "--task", task,
        "--fps", str(fps),
        "--raw-dirs",
        *[str(p.resolve()) for p in raw_dirs],
    ]
    return cmd


def run_task(
    plan: TaskPlan,
    *,
    bddl_root: Path,
    openpi_dir: Path,
    venv: Path,
    lerobot_home: Path,
    repo_id_prefix: str,
    fps: int,
    staging_root: Path,
    dry_run: bool,
) -> int:
    repo_id = f"{repo_id_prefix}{plan.task_id}"
    task_lang = language_instruction(bddl_root, plan.sources)
    target = lerobot_home / repo_id

    print(f"\n=== task={plan.task_id}  block={plan.block} ===")
    print(f"  lang : {task_lang!r}")
    print(f"  repo : {repo_id}  -> {target}")
    for s in plan.sources:
        chosen = len(plan.selected.get(s.label, []))
        print(f"  src  : {s.label:<60s} kind={s.kind:<3s} avail={len(s.files):3d}  used={chosen:3d}  ({s.path})")
    mg_cap, raw_cap = BLOCK_CAPS[plan.block]
    print(f"  total: {plan.total_selected} (caps mg/src={mg_cap} raw/src={raw_cap})")

    if dry_run:
        if target.exists():
            print(f"  (would skip: target exists at {target})")
        return 0

    if target.exists():
        print(f"  [skip] target already exists: {target}")
        return 0

    task_stage = stage_demos(plan, staging_root)
    variant_dirs = [task_stage / s.label for s in plan.sources if plan.selected.get(s.label)]
    cmd = build_command(repo_id=repo_id, task=task_lang, raw_dirs=variant_dirs, fps=fps)

    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(venv)
    env["HF_LEROBOT_HOME"] = str(lerobot_home)
    env["HDF5_USE_FILE_LOCKING"] = "FALSE"
    env["GIT_LFS_SKIP_SMUDGE"] = "1"

    print(f"  cmd  : {' '.join(cmd)}")
    rc = subprocess.run(cmd, cwd=str(openpi_dir), env=env).returncode

    # Clean up symlink staging for this task (small but accumulates).
    try:
        shutil.rmtree(task_stage)
    except OSError:
        pass

    return rc


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def collect_all_tasks() -> list[tuple[str, str]]:
    return (
        [(t, "A") for t in BLOCK_A]
        + [(t, "B") for t in BLOCK_B]
        + [(t, "C_MG") for t in BLOCK_C_MG]
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mg-root", type=Path, default=DEFAULT_MG_ROOT,
                   help="Block A aligned-combo MG output root.")
    p.add_argument("--blockc-mg-root", type=Path, default=DEFAULT_BLOCKC_MG_ROOT,
                   help="Block C single-arm MG output root (v5 no-mirror).")
    p.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    p.add_argument("--bddl-root", type=Path, default=DEFAULT_BDDL_ROOT)
    p.add_argument("--openpi-dir", type=Path, default=DEFAULT_OPENPI)
    p.add_argument("--venv", type=Path, default=DEFAULT_VENV)
    p.add_argument("--lerobot-home", type=Path, default=DEFAULT_LEROBOT_HOME,
                   help="Output HF_LEROBOT_HOME dir. Override via env or flag.")
    p.add_argument("--repo-id-prefix", type=str, default="")
    p.add_argument("--task", action="append", default=[],
                   help="Restrict to listed task ids (repeatable).")
    p.add_argument("--block", choices=["A", "B", "C_MG"],
                   action="append", default=[],
                   help="Restrict to listed blocks (repeatable).")
    p.add_argument("--min-demos", type=int, default=MIN_DEMOS_DEFAULT,
                   help="Skip tasks whose total available demos < this (default 10).")
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--staging-root", type=Path, default=None,
                   help="Where to symlink demos before conversion. "
                        "Default: tempfile.mkdtemp() under TMPDIR.")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    # Allow env override of HF_LEROBOT_HOME.
    if "HF_LEROBOT_HOME" in os.environ:
        args.lerobot_home = Path(os.environ["HF_LEROBOT_HOME"])

    # Build task list.
    all_tasks = collect_all_tasks()
    if args.block:
        all_tasks = [(t, b) for t, b in all_tasks if b in args.block]
    if args.task:
        known = {t for t, _ in all_tasks}
        missing = [t for t in args.task if t not in known]
        if missing:
            print(f"Unknown task ids: {missing}", file=sys.stderr)
            print(f"Available: {sorted(known)}", file=sys.stderr)
            return 1
        all_tasks = [(t, b) for t, b in all_tasks if t in args.task]

    # Plan every task (scan sources, pick selection).
    plans: list[TaskPlan] = []
    skipped: list[tuple[str, str, int]] = []  # (task, reason, total_avail)
    for task_id, block in all_tasks:
        sources = make_sources(
            task_id, block, args.mg_root, args.raw_root, args.blockc_mg_root
        )
        for s in sources:
            s.scan()
        avail = sum(len(s.files) for s in sources)
        if avail < args.min_demos:
            skipped.append((task_id, f"only {avail} demos (need >= {args.min_demos})", avail))
            continue
        plan = TaskPlan(task_id=task_id, block=block, sources=sources)
        mg_cap, raw_cap = BLOCK_CAPS[block]
        plan.selected = select_demos(sources, mg_cap, raw_cap)
        plans.append(plan)

    print(f"Plan: {len(plans)} tasks, {len(skipped)} skipped.")
    if skipped:
        print("Skipped:")
        for t, r, n in skipped:
            print(f"  - {t}  ({r})")

    # Choose staging dir.
    if args.staging_root is None:
        staging_root = Path(tempfile.mkdtemp(prefix="bimesa_lerobot_stage_"))
        cleanup_staging = True
    else:
        args.staging_root.mkdir(parents=True, exist_ok=True)
        staging_root = args.staging_root
        cleanup_staging = False

    failures: list[str] = []
    try:
        for plan in plans:
            rc = run_task(
                plan,
                bddl_root=args.bddl_root,
                openpi_dir=args.openpi_dir,
                venv=args.venv,
                lerobot_home=args.lerobot_home,
                repo_id_prefix=args.repo_id_prefix,
                fps=args.fps,
                staging_root=staging_root,
                dry_run=args.dry_run,
            )
            if rc != 0:
                failures.append(plan.task_id)
                print(f"  [fail] task {plan.task_id} exit={rc}", file=sys.stderr)
    finally:
        if cleanup_staging:
            shutil.rmtree(staging_root, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} tasks failed: {failures}", file=sys.stderr)
        return 1
    print(f"\nDone. {len(plans)} tasks processed, {len(skipped)} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
