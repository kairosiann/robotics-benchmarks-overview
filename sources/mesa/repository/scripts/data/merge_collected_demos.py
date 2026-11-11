"""
This script is used to postprocess demos collected using the data collection scripts.
It merges all hdf5 files in a directory into a single hdf5 file.

Example usage:
    python scripts/postprocess_demos.py \
        --demo_dir ./demos/example_suite/example_task/
        
"""

import os

import tyro
from tqdm import tqdm

from mesa.data_collection.sim.demo_saver import DemoSaver


def main(
    demo_dir: str | None = None,
    demo_dirs: list[str] | None = None,
    delete_source_files: bool = False,
):
    assert demo_dir is not None or demo_dirs is not None
    if demo_dir is not None:
        demo_dirs = [demo_dir]
    else:
        demo_dirs = demo_dirs
    for demo_dir in tqdm(demo_dirs, desc="Merging demos"):
        if not os.path.isdir(demo_dir):
            continue

        DemoSaver.merge_hdf5s(
            demo_dir,
            verbose=False,
            multi_env_args=True,
            delete_source_files=delete_source_files,
        )


if __name__ == "__main__":
    tyro.cli(main)
