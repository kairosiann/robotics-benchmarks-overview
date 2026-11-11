"""
Generate MimicGen config classes and json templates, one per TASK FOLDER under the suite.

Each task folder may contain multiple BDDL files. We emit a single config per task folder,
and the dataset generator will iterate over all BDDL files in that folder.
"""

import os
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from termcolor import colored

import mesa
from mesa import MESA_ROOT
from mesa.mimicgen.configs import generate_mg_config_classes


@dataclass
class GenerateConfigsArgs:
    """Arguments for generating MimicGen config templates and jobs.

    Mirrors the dataclass-based CLI pattern used in scripts/generate_dataset.py.
    """
    # The name of task suite folder from BDDL generation
    task_suite_name: str
    # The max number of failures to save per variant
    max_num_failures: int = 25
    # The number of demos to render at the end of data generation
    num_demo_to_render: int = 10
    # The number of failure demos to render at the end of data generation
    num_fail_demo_to_render: int = 25
    # The number of demos to generate per variant
    num_demos_per_task: int = 1
    # Limits the number of source demos to use for data generation. Not used for stitching generation.
    limit_source_demos: Optional[int] = None
    # Whether to select source demos per subtask
    select_src_per_subtask: bool = True
    # The number of noops to execute at the beginning of the trajectory to allow objects to settle
    init_noops: int = 10
    # The names of the cameras to use for rendering
    camera_names: List[str] = field(default_factory=lambda: ["agentview", "robot0_eye_in_hand"])
    # The height of the camera images
    camera_height: int = 84
    # The width of the camera images
    camera_width: int = 84
    # Whether to automatically remove config directories if they already exist
    auto_remove_exp: bool = False
    # The number of parallel jobs to run per task. If true, these commands will be present in jobs.sh
    num_parallel_jobs: int = 1
    # The directory to store the data generation results and find source data
    data_dir: str = "data"
    # Whether to use stitching data generation
    stitching: bool = False
    # Whether to keep failed demonstrations
    no_keep_failed: bool = False
    # Whether to catch exceptions during data generation. If false, the data generation will crash on the first exception.
    catch_exceptions: bool = False
    # The path to the source dataset in case not using data from the same task suite
    source_dataset_path: Optional[str] = None
    output_dir_name: Optional[str] = None
    # Enable bimanual (dual-arm) generation.
    bimanual: bool = False
    # Robot names for bimanual generation.
    robots: List[str] = field(default_factory=lambda: ["ReverseMountedYam", "ReverseMountedYam"])
    # Which BDDL split to generate from.
    variant_folder: Literal["train", "source", "eval"] = "train"
    # Object asset format: "mesa" (single-arm) or "bimesa" (dual-arm).
    object_format: str = "mesa"
    # Path to a SLURM sbatch wrapper script. When set, each command is wrapped as
    # `sbatch <slurm_script> <command>`; when None, commands run directly.
    slurm_script: Optional[str] = None

def generate_config_templates(args: GenerateConfigsArgs):
    """
    Generates config templates for MimicGen data generation for all BDDL files
    under task_suite_name.
    """
    if not args.stitching:
        raise ValueError("Non stitching generation is no longer supported.")

    # directory for storing template config jsons
    if args.output_dir_name is None:
        output_dir_name = args.task_suite_name
    else:
        output_dir_name = args.output_dir_name
    target_dir = os.path.join(
        MESA_ROOT, "..", args.data_dir, "mimicgen_configs", output_dir_name
    )

    # check if target_dir exists and prompt before overriding
    if os.path.exists(target_dir) and not args.auto_remove_exp:
        inp = input(
            f"Directory {target_dir} already exists. Would you like to overwrite it? [y/n]\n"
        )
        if inp.lower() not in ["y", "yes"]:
            print("Exiting without generating config templates.")
            return None

    # Ensure both wrist cameras are included for bimanual generation.
    if args.bimanual and "robot1_eye_in_hand" not in args.camera_names:
        args.camera_names.append("robot1_eye_in_hand")

    # generate config instances for all tasks
    all_configs = generate_mg_config_classes(
        task_suite_name=args.task_suite_name,
        camera_names=args.camera_names,
        camera_height=args.camera_height,
        camera_width=args.camera_width,
        # pick_place=args.pick_place,
        stitching=args.stitching,
        variant_folder=args.variant_folder,
        object_format=args.object_format,
    )
    
    # store config json by config type
    os.makedirs(target_dir, exist_ok=True)
    for task_name, mg_config in all_configs.items():

        # Source demos assumed per unique task (folder-level); derive folder from class name prefix
        if args.source_dataset_path is not None:
            source_dataset_path = args.source_dataset_path
        else:
            if args.stitching:
                source_parts = [args.data_dir, "source", args.task_suite_name]
                if args.bimanual:
                    source_parts.append(task_name)
                source_dataset_path = os.path.join(*source_parts)
            else:
                source_dataset_path = os.path.join(
                    args.data_dir,
                    "source",
                    args.task_suite_name,
                    task_name,
                    "demo.hdf5"
                )
        mg_config.experiment.source.dataset_path = source_dataset_path

        # set remaining config params based on args
        mg_config.experiment.generation.path = os.path.join(
            args.data_dir,
            "gen_data",
            args.task_suite_name,
            task_name,
        )
        mg_config.experiment.generation.guarantee = True
        mg_config.experiment.generation.num_trials = args.num_demos_per_task
        mg_config.experiment.generation.init_noops = args.init_noops
        mg_config.experiment.generation.stitching = args.stitching
        mg_config.experiment.generation.keep_failed = not args.no_keep_failed
        mg_config.experiment.max_num_failures = args.max_num_failures
        mg_config.experiment.num_demo_to_render = args.num_demo_to_render
        mg_config.experiment.num_fail_demo_to_render = args.num_fail_demo_to_render
        mg_config.experiment.source.n = args.limit_source_demos
        mg_config.experiment.generation.select_src_per_subtask = args.select_src_per_subtask or args.stitching
        mg_config.experiment.generation.filter_joint_limit = True
        mg_config.experiment.generation.n_reuse_initial_state = 10

        # dump to json
        # Save one config per BDDL file
        json_path = os.path.join(target_dir, f"{task_name}.json")
        mg_config.dump(json_path)
    return target_dir


def generate_configs_and_jobs(args: GenerateConfigsArgs):
    if args.num_parallel_jobs < 1:
        raise ValueError("num_parallel_jobs must be at least 1")
    config_dir = generate_config_templates(args)
    if config_dir is not None:
        print(colored(f"Generated config templates", "green"), f"--> {config_dir}")

        jobs_file_path = os.path.join(config_dir, "jobs.sh")
        with open(jobs_file_path, "w") as f:
            for config_file in sorted(os.listdir(config_dir)):

                if config_file.endswith(".json"):
                    command = f"uv run scripts/mimicgen/generate_dataset.py --config {os.path.join(config_dir, config_file)}"
                    if args.bimanual:
                        robots_str = " ".join(args.robots)
                        command += f" --bimanual --robots {robots_str}"
                    else:
                        command += " --no-bimanual"
                    command += f" --variant-folder {args.variant_folder}"
                    if args.slurm_script is not None:
                        command = f"sbatch {args.slurm_script} {command}"
                    if args.catch_exceptions:
                        command += " --catch-exceptions"
                    if args.num_parallel_jobs == 1:
                        command += " --auto-remove-exp"
                        f.write(command + "\n")
                    else:
                        task_suite_path = os.path.join(MESA_ROOT, "task_suites", "bddl_files", args.task_suite_name)
                        task_folder_path = os.path.join(task_suite_path, config_file.replace(".json", ""))
                        num_variants = len([
                            name for name in os.listdir(os.path.join(task_folder_path, args.variant_folder))
                            if name.endswith(".json") and (not name.endswith(".dex.json"))
                        ])
                        if num_variants == 0:
                            raise ValueError(f"No variants found for {config_file}")
                        num_jobs = min(args.num_parallel_jobs, num_variants)
                        for i in range(num_jobs):
                            start_variant = i * num_variants // num_jobs
                            end_variant = (i + 1) * num_variants // num_jobs - 1
                            variant_command = command + f" --auto-keep-exp --disable-merge --variant-start {start_variant} --variant-end {end_variant}"
                            f.write(variant_command + "\n")

        # Make the jobs.sh file executable
        os.chmod(jobs_file_path, 0o755)

        print(
            colored(f"Exported datagen jobs", "green"),
            f"--> {jobs_file_path}",
        )


if __name__ == "__main__":
    import tyro

    def main(args: GenerateConfigsArgs) -> None:
        generate_configs_and_jobs(args)

    args = tyro.cli(GenerateConfigsArgs)
    main(args)
