#!/usr/bin/env python3
"""Download zipped mesa source data and move it to data/source/mesa-source."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from zipfile import ZipFile

import gdown

DATA_URL = "https://drive.google.com/file/d/12dwsNYaC7kzbboOvUBHO46ffE5ncgMq6/view?usp=sharing"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download a zip archive from DATA_URL, unzip it, and move the "
            f"extracted data folder to data/source/mesa-source."
        )
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=f"Overwrite data/source/mesa-source if it already exists.",
    )
    return parser.parse_args()


def _find_extracted_data(extract_root: Path) -> Path:
    direct_data_path = extract_root / "mesa-source"
    return direct_data_path



def main() -> None:
    args = parse_args()

    if Path("data/source/mesa-source").exists():
        if not args.overwrite:
            raise FileExistsError(
                f"Destination already exists: data/source/mesa-source. "
                "Use --overwrite to replace it."
            )
        shutil.rmtree("data/source/mesa-source")

    with tempfile.TemporaryDirectory(prefix="mesa_source_data_download_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_path = tmp_path / "mesa-source.zip"
        extract_root = tmp_path / "extracted"

        download_path = gdown.download(
            url=DATA_URL,
            output=str(zip_path),
            quiet=False,
            fuzzy=True,
        )
        if download_path is None or not zip_path.is_file():
            raise RuntimeError("Download failed: expected zip file was not created.")

        with ZipFile(zip_path) as archive:
            archive.extractall(extract_root)

        extracted_data = _find_extracted_data(extract_root)
        shutil.move(str(extracted_data), "data/source/mesa-source")

    print(f"Moved extracted data to: data/source/mesa-source")


if __name__ == "__main__":
    main()