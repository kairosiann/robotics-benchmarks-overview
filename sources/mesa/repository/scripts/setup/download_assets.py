#!/usr/bin/env python3
"""Download the MESA simulation assets from Hugging Face into mesa/sim/assets.

The assets are hosted as zip archives in the `albertwilcox/mesa-assets` dataset repo:

  assets.zip      -> mesa/sim/assets/                  scenes, textures and objects for both benchmarks
  objaverse.zip   -> mesa/sim/assets/objects/objaverse  RoboCasa365 objects used by BiMESA
  aigen_objs.zip  -> mesa/sim/assets/objects/aigen_objs RoboCasa365 AI-generated objects used by BiMESA

Usage:
    uv run python scripts/setup/download_assets.py              # everything (~13 GB download)
    uv run python scripts/setup/download_assets.py --no-bimesa  # single-arm MESA only
    uv run python scripts/setup/download_assets.py --overwrite  # re-download
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

REPO_ID = "albertwilcox/mesa-assets"
ASSETS_ROOT = Path(__file__).resolve().parents[2] / "mesa" / "sim" / "assets"

# archive name -> (top-level directory inside the archive, destination)
ARCHIVES = {
    "assets": ("assets", ASSETS_ROOT),
    "objaverse": ("objaverse", ASSETS_ROOT / "objects" / "objaverse"),
    "aigen_objs": ("aigen_objs", ASSETS_ROOT / "objects" / "aigen_objs"),
}
BIMESA_ARCHIVES = ("objaverse", "aigen_objs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-bimesa", action="store_true", help="Skip the BiMESA-only object archives.")
    parser.add_argument("--overwrite", action="store_true", help="Replace assets that are already present.")
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


def _present(dest: Path) -> bool:
    return dest.is_dir() and any(p for p in dest.iterdir() if p.name not in ("objaverse", "aigen_objs", ".gitignore"))


def main() -> None:
    args = parse_args()
    names = [n for n in ARCHIVES if not (args.no_bimesa and n in BIMESA_ARCHIVES)]

    todo = []
    for name in names:
        dest = ARCHIVES[name][1]
        if _present(dest) and not args.overwrite:
            print(f"'{name}' already present at {dest}; skipping (use --overwrite to replace).")
        else:
            todo.append(name)
    if not todo:
        return

    with urllib.request.urlopen(_url(args.repo_id, args.revision, "SHA256SUMS")) as response:
        checksums = dict(
            reversed(line.split()) for line in response.read().decode().splitlines() if line.strip()
        )

    # The base bundle replaces mesa/sim/assets, so install it before the BiMESA objects that live inside it.
    todo.sort(key=lambda n: n != "assets")
    with tempfile.TemporaryDirectory(prefix="mesa_assets_", dir=ASSETS_ROOT.parent) as tmp:
        tmp_dir = Path(tmp)
        for name in todo:
            top, dest = ARCHIVES[name]
            archive = tmp_dir / f"{name}.zip"
            print(f"Downloading {archive.name} from {args.repo_id}...")
            _download(_url(args.repo_id, args.revision, archive.name), archive)
            if _sha256(archive) != checksums.get(archive.name):
                raise RuntimeError(f"Checksum mismatch for {archive.name}; please retry the download.")

            extract_root = tmp_dir / f"{name}_extracted"
            with ZipFile(archive) as zf:
                zf.extractall(extract_root)
            archive.unlink()
            extracted = extract_root / top
            if not extracted.is_dir():
                raise FileNotFoundError(f"{archive.name} does not contain a top-level '{top}/' directory.")

            if name == "assets" and dest.exists():
                # Keep already-installed BiMESA objects when only the base bundle is being replaced.
                for keep in BIMESA_ARCHIVES:
                    if keep not in todo and (dest / "objects" / keep).exists():
                        shutil.move(str(dest / "objects" / keep), str(extracted / "objects" / keep))
            if dest.is_symlink() or dest.is_file():
                dest.unlink()
            elif dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(extracted), str(dest))
            print(f"Installed {name} to {dest}")


if __name__ == "__main__":
    main()
