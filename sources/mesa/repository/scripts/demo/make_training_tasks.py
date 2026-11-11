import os
import shutil
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import tyro

from mesa.sim.task_gen import generate_from_config
from mesa.sim.task_gen.object_categories import register_spatial_gen_object
from mesa.task_suites.task_sets import TRAIN_SETS
from mesa.task_suites.utils import (
    make_articulated_multistep_tasks,
    make_articulated_primitives,
    make_pick_and_place_tasks,
    make_valid_distractor_map,
)

# Set up some default config values that will be used for all tasks in the task suite we're building.
TASK_SUITE_NAME = "mesa-demo-all"
OUTPUT_DIR = "./task_suites/"
DEFAULT_CONFIG = {
    "task_suite_name": TASK_SUITE_NAME,
    "arena_name": "mimiclabs_lab1_tabletop_manipulation",
    "num_train_variants": 100,
    "output_dir": OUTPUT_DIR,
    "make_source": True,
    "add_distractors": True,
}


@dataclass(frozen=True)
class Args:
    """CLI args for generating the benchmark_v5 task suite."""

    no_parallel: bool = False
    """Disable multiprocessing; generate tasks serially in the main process."""


def _generate_task_worker(config: Dict, valid_distractor_map: Dict) -> None:
    """ProcessPool worker entrypoint (must be top-level and picklable)."""
    generate_from_config(
        config,
        valid_distractor_map=valid_distractor_map,
    )


if __name__ == "__main__":
    args = tyro.cli(Args)

    out_dir = Path(OUTPUT_DIR) / TASK_SUITE_NAME
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Object specs specify the locations where an object can spawn. Therefore, a tomato that spawns on the 
    # left side of the table is different from one that spawns on the right side. Since this would create a 
    # huge number of extra objects and corresponding tasks if we established separate tasks possible location
    # for each object, we manually register these objects as objects requiring more granular spawn regions.
    register_spatial_gen_object("tomato")
    register_spatial_gen_object("rolling_pin")
    register_spatial_gen_object("water_bottle")

    # In this, we generate all possible task configurations given our objects and existing skeletons. 
    # Refer to the functions below for details on instantiating these.
    config_map = {}
    all_meta = {}

    task_generators = [
        make_pick_and_place_tasks,
        make_articulated_primitives,
        make_articulated_multistep_tasks,
    ]
    for gen_fn in task_generators:
        configs, meta = gen_fn(DEFAULT_CONFIG)
        config_map.update(configs)
        all_meta.update(meta)

    # Load the task IDs for task suite we are trying to generate.
    task_ids = TRAIN_SETS["mesa-all"]["tasks"]
    
    # Construct a map of valid distractors for each task. This allows us to ensure that for
    # each variant of a task, there is some task in task list such that its task relevant 
    # objects are present in the distractor objects.
    valid_distractor_map = make_valid_distractor_map(task_ids, all_meta)

    all_configs = [config_map[task_id] for task_id in task_ids]
    num_tasks = len(all_configs)

    print(f"Generating {num_tasks} tasks")

    if num_tasks == 0:
        raise RuntimeError("No task configs were generated (all_configs is empty).")

    if args.no_parallel:
        for config in all_configs:
            generate_from_config(
                config, 
                valid_distractor_map=valid_distractor_map, 
                verbose=True,
            )
    else:
        max_workers = os.cpu_count() or 1
 
        # Warm up in the main process to surface errors before spawning workers,
        # then avoid duplicating the first config in the pool.
        _generate_task_worker(all_configs[0], valid_distractor_map)

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            configs = all_configs[1:]
            valid_maps = [valid_distractor_map] * len(configs)
            for _ in executor.map(_generate_task_worker, configs, valid_maps):
                pass

    print(f"Generated {num_tasks} tasks")