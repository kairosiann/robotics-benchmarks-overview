#!/usr/bin/env python3
"""Download the fixed evaluation initial states for MESA and BiMESA.

The archives are hosted on Hugging Face and extracted to
``mesa/task_suites/init_states/<suite>/<task>/<NNN>.json``, which is where
``EvalSet.get_init_state`` looks for them.

Usage:
    uv run python scripts/setup/download_init_states.py              # both suites
    uv run python scripts/setup/download_init_states.py --suites mesa
    uv run python scripts/setup/download_init_states.py --overwrite  # re-download
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path
from zipfile import ZipFile

REPO_ID = "albertwilcox/mesa-init-states"
SUITES = ("mesa", "bimesa")
INIT_STATES_DIR = Path(__file__).resolve().parents[2] / "mesa" / "task_suites" / "init_states"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suites", nargs="+", choices=SUITES, default=list(SUITES))
    parser.add_argument("--overwrite", action="store_true", help="Replace suites that are already present.")
    parser.add_argument("--repo-id", default=REPO_ID, help="Hugging Face dataset repo hosting the archives.")
    parser.add_argument("--revision", default="main")
    return parser.parse_args()


def _url(repo_id: str, revision: str, filename: str) -> str:
    endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    return f"{endpoint}/datasets/{repo_id}/resolve/{revision}/{filename}"


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url) as response, dest.open("wb") as f:
        total = int(response.headers.get("Content-Length", 0))
        done = 0
        while chunk := response.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {dest.name}: {done / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
    print()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    args = parse_args()
    INIT_STATES_DIR.mkdir(parents=True, exist_ok=True)

    todo = []
    for suite in args.suites:
        dest = INIT_STATES_DIR / suite
        if dest.exists() and any(dest.iterdir()) and not args.overwrite:
            print(f"Init states for '{suite}' already present at {dest}; skipping (use --overwrite to replace).")
        else:
            todo.append(suite)
    if not todo:
        return

    with urllib.request.urlopen(_url(args.repo_id, args.revision, "SHA256SUMS")) as response:
        checksums = dict(
            reversed(line.split()) for line in response.read().decode().splitlines() if line.strip()
        )

    with tempfile.TemporaryDirectory(prefix="mesa_init_states_") as tmp:
        tmp_dir = Path(tmp)
        for suite in todo:
            archive = tmp_dir / f"{suite}.zip"
            print(f"Downloading {archive.name} from {args.repo_id}...")
            _download(_url(args.repo_id, args.revision, archive.name), archive)

            expected = checksums.get(archive.name)
            if expected is None or _sha256(archive) != expected:
                raise RuntimeError(f"Checksum mismatch for {archive.name}; please retry the download.")

            extract_root = tmp_dir / f"{suite}_extracted"
            with ZipFile(archive) as zf:
                zf.extractall(extract_root)
            extracted = extract_root / suite
            if not extracted.is_dir():
                raise FileNotFoundError(f"{archive.name} does not contain a top-level '{suite}/' directory.")

            dest = INIT_STATES_DIR / suite
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(extracted), str(dest))
            n_tasks = sum(1 for p in dest.iterdir() if p.is_dir())
            print(f"Extracted {n_tasks} tasks to {dest}")


if __name__ == "__main__":
    main()
