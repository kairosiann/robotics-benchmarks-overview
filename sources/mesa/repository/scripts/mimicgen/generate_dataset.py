import json
import os
import random
import shutil
import time
from dataclasses import dataclass, field
from typing import List, Literal, Optional

import imageio
import numpy as np
import tyro

from natsort import natsorted

import mesa
import mesa.mimicgen.utils.file_utils as MG_FileUtils
import mesa.sim.envs.bddl_utils as BDDLUtils
from mesa import MESA_ROOT
from mesa.mimicgen.configs import MG_TaskSpec, finish_task_spec
from mesa.mimicgen.configs.config import MGConfig
from mesa.mimicgen.data_generator import DataGenerator
from mesa.mimicgen.env_interfaces.base import make_interface
from mesa.mimicgen.stitching_data_generator import StitchingDataGenerator
from mesa.mimicgen.utils.misc_utils import get_important_stats
from mesa.sim.envs.bddl_base_domain import TASK_MAPPING
from mesa.utils.replay import replay_dataset

from mesa.mimicgen.dex.sidecar import load_dex_sidecar, validate_arm_assignment_options, validate_subtask_dependencies
from mesa.mimicgen.dex.bimanual_env_interface import BimanualEnvInterface
from mesa.mimicgen.dex.bimanual_data_generator import BimanualDataGenerator
from mesa.mimicgen.dex.bimanual_file_utils import write_bimanual_demo_to_hdf5

np.set_printoptions(suppress=True)


def _canonical_robot_name(name: str) -> str:
    key = name.lower().replace("-", "").replace("_", "")
    aliases = {
        "mountedyam": "Yam",
        "yam": "Yam",
        "reversemountedyam": "ReverseMountedYam",
    }
    if key not in aliases:
        raise ValueError(
            f"Unsupported robot name '{name}'. "
            f"Supported aliases: Yam, MountedYAM, ReverseMountedYam, ReverseMountedYAM"
        )
    return aliases[key]


@dataclass
class GenerateDatasetArgs:
    """Arguments for the generate_dataset script.
    
    This script generates datasets using MimicGen for vision-language-action models.
    """
    config: str
    """Path to MimicGen config json (required)."""
    
    debug: bool = False
    """Set this flag to run a quick generation run for debugging purposes."""
    
    auto_remove_exp: bool = False
    """Force delete the experiment folder if it exists."""
    
    auto_keep_exp: bool = False
    """Automatically keep the experiment folder if it exists, adding new files to it instead of overwriting them."""

    render: bool = False
    """Render each data generation attempt on-screen."""

    robots: List[str] = field(default_factory=lambda: ["Panda"])
    """Robot(s) to use for data generation. For bimanual, provide two robot names."""

    bimanual: bool = False
    """Enable bimanual generation with parallel per-arm subtask queues."""

    video_path: Optional[str] = None
    """If provided, render the data generation attempts to the provided video path."""
    
    video_skip: int = 5
    """Skip every nth frame when writing video."""
    
    render_image_names: Optional[List[str]] = None
    """(optional) camera name(s) / image observation(s) to use for rendering on-screen or to video. 
    Default is None, which corresponds to a predefined camera for each env type."""
    
    pause_subtask: bool = False
    """Pause after every subtask during generation for debugging - only useful with render flag."""
    
    source: Optional[str] = None
    """Path to source dataset, to override the one in the config."""
    
    folder: Optional[str] = None
    """Folder that will be created with new data, to override the one in the config."""
    
    num_demos: Optional[int] = None
    """Number of demos to generate, or attempt to generate, per variant, to override the one in the config."""
    
    seed: Optional[int] = None
    """Seed, to override the one in the config."""
    
    variant_start: Optional[int] = None
    """0-based start index (inclusive) of variants to process."""
    
    variant_end: Optional[int] = None
    """0-based end index (inclusive) of variants to process."""
    
    disable_merge: bool = False
    """Disable merging per-episode HDF5s; write a manifest to merge later."""

    catch_exceptions: bool = False
    """Catch exceptions and continue generating data."""

    variant_folder: Literal["train", "source", "eval"] = "train"
    """BDDL variant split to generate from."""


def generate_dataset(mg_config: MGConfig, args: GenerateDatasetArgs):
    """
    Main function to collect a new dataset with MimicGen.

    Args:
        mg_config (MGConfig): MimicGen config object
        args (GenerateDatasetArgs): Command line arguments containing all configuration
    """

    start_time = time.time()

    write_video = (args.video_path is not None)
    assert not (args.render and write_video) # either on-screen or video but not both
    if args.pause_subtask:
        assert args.render, "should enable on-screen rendering for pausing to be useful"

    if write_video:
        if len(mg_config.obs.camera_names) > 0:
            assert args.render_image_names is None
            render_image_names = list(mg_config.obs.camera_names)

    source_dataset_path = os.path.expandvars(os.path.expanduser(mg_config.experiment.source.dataset_path))

    random.seed(mg_config.experiment.seed)
    np.random.seed(mg_config.experiment.seed)

    base_folder = os.path.expandvars(os.path.expanduser(mg_config.experiment.generation.path))
    new_dataset_folder_name = mg_config.experiment.name
    new_dataset_folder_path = os.path.join(
        base_folder,
        new_dataset_folder_name,
    )
    print("\nData will be generated at: {}".format(new_dataset_folder_path))

    exist_ok = False
    if os.path.exists(new_dataset_folder_path):
        assert not (args.auto_remove_exp and args.auto_keep_exp), "cannot both auto-remove and auto-keep experiment folder"
        if args.auto_keep_exp:
            print("Keeping old dataset folder. Note that individual files may still be overwritten.")
            exist_ok = True
        else:
            if not args.auto_remove_exp:
                ans = input("\nWARNING: dataset folder ({}) already exists! \noverwrite? (y/n)\n".format(new_dataset_folder_path))
            else:
                ans = "y"
                
            if ans == "y":
                print("Removed old results folder at {}".format(new_dataset_folder_path))
                shutil.rmtree(new_dataset_folder_path)
            else:
                print("Keeping old dataset folder. Note that individual files may still be overwritten.")
                exist_ok = True
    os.makedirs(new_dataset_folder_path, exist_ok=exist_ok)

    mg_config.dump(os.path.join(new_dataset_folder_path, "mg_config.json"))

    print("\n============= Config =============")
    print(mg_config)
    print("")

    new_dataset_path = os.path.join(new_dataset_folder_path, "demo.hdf5")
    tmp_dataset_folder_path = os.path.join(new_dataset_folder_path, "tmp")
    os.makedirs(tmp_dataset_folder_path, exist_ok=exist_ok)
    json_log_path = os.path.join(new_dataset_folder_path, "logs")
    os.makedirs(json_log_path, exist_ok=exist_ok)

    if mg_config.experiment.generation.keep_failed:
        new_failed_dataset_path = os.path.join(new_dataset_folder_path, "demo_failed.hdf5")
        tmp_dataset_failed_folder_path = os.path.join(new_dataset_folder_path, "tmp_failed")
        os.makedirs(tmp_dataset_failed_folder_path, exist_ok=exist_ok)

    if not mg_config.experiment.generation.stitching:
        all_demos = MG_FileUtils.get_all_demos_from_dataset(
            dataset_path=source_dataset_path,
            filter_key=mg_config.experiment.source.filter_key,
            start=mg_config.experiment.source.start,
            n=mg_config.experiment.source.n,
        )

    if args.render_image_names is not None:
        render_image_names = args.render_image_names
    else:
        render_image_names = ["leftshoulder"]
    if args.render:
        # on-screen rendering can only support one camera
        assert len(render_image_names) == 1

    camera_names = (mg_config.obs.camera_names if not write_video else render_image_names)

    task_folder = os.path.join(
        MESA_ROOT,
        "task_suites",
        "bddl_files",
        mg_config.task_suite_name,
        mg_config.name,
        args.variant_folder,
    )
    print(f"Using BDDL variant folder: {args.variant_folder}")

    variants = [
        name
        for name in natsorted(os.listdir(task_folder))
        if name.endswith(".json") and (not name.endswith(".dex.json"))
    ]
    total_variants = len(variants)
    sel_start = 0 if (args.variant_start is None) else max(0, int(args.variant_start))
    sel_end = (total_variants - 1) if (args.variant_end is None) else min(total_variants - 1, int(args.variant_end))
    if sel_start > sel_end:
        raise ValueError(f"variant_start ({sel_start}) > variant_end ({sel_end}) after bounding; nothing to process")
    print(f"\nVariant selection: total={total_variants}, processing indices [{sel_start}, {sel_end}] inclusive")

    total_num_success = 0
    total_num_failures = 0
    total_num_attempts = 0
    total_num_problematic = 0
    total_ep_lengths = []
    existing_variants = set()
    for name in os.listdir(tmp_dataset_folder_path):
        prefix = name.split("__")[0]
        if prefix:
            existing_variants.add(prefix)

    for i, variant in enumerate(variants):
        
        if variant.split(".")[0] in existing_variants:
            print(f"Skipping variant {variant} because it already exists")
            continue

        try:

            # skip variants before start; break after end for efficiency
            if i < sel_start:
                continue
            if i > sel_end:
                break
            variant_path = os.path.join(task_folder, variant)

            parsed_problem = BDDLUtils.load_problem(variant_path)
            is_bimanual = args.bimanual

            robots_list = (
                [_canonical_robot_name(r) for r in args.robots]
                if is_bimanual else list(args.robots)
            )
            arm_assignment_options = None
            subtask_dependencies = {}
            if is_bimanual:
                if len(robots_list) != 2:
                    raise ValueError(
                        f"Bimanual mode requires exactly 2 robots, got {len(robots_list)}: {robots_list}"
                    )
                canonical = frozenset(r.lower().replace("-", "").replace("_", "") for r in robots_list)
                expected_opposite_side = frozenset({"yam", "reversemountedyam"})
                expected_same_side = frozenset({"reversemountedyam"})
                if canonical not in {expected_opposite_side, expected_same_side}:
                    raise ValueError(
                        "Bimanual mode supports either "
                        "['Yam', 'ReverseMountedYam'] (opposite-side) or "
                        "['ReverseMountedYam', 'ReverseMountedYam'] (same-side), "
                        f"got {robots_list}"
                    )
                sidecar = load_dex_sidecar(variant_path)
                num_subtasks = len(parsed_problem["demonstration_states"])
                arm_assignment_options = sidecar["arm_assignment_options"]
                validate_arm_assignment_options(arm_assignment_options, num_subtasks)
                subtask_dependencies = sidecar["subtask_dependencies"]
                if subtask_dependencies:
                    validate_subtask_dependencies(subtask_dependencies, num_subtasks)
            elif len(robots_list) != 1:
                raise ValueError(
                    f"Single-arm mode requires exactly 1 robot, got {len(robots_list)}: {robots_list}"
                )

            env = mesa.make_env(
                parsed_problem=parsed_problem,
                robots=robots_list,
                camera_names=camera_names,
                camera_heights=mg_config.obs.camera_height,
                camera_widths=mg_config.obs.camera_width,
                has_renderer=args.render,
                control_delta=True,
            )

            if i == 0:
                print("\n==== Using MESA environment with the following BDDL ====")
                print(json.dumps(parsed_problem, indent=4))
                print("")

            if is_bimanual:
                env_interface = BimanualEnvInterface(env=env)
            else:
                env_interface = make_interface(
                    name="MESAInterface",
                    interface_type="mesa",
                    env=env,
                )
            if i == 0:
                print("Created environment interface: {}".format(env_interface))
                print("")

            task_spec_json_string = json.dumps(mg_config.task.task_spec)
            task_spec_json_dict = json.loads(task_spec_json_string)
            task_spec_json_dict = finish_task_spec(task_spec_json_dict, parsed_problem)
            task_spec = MG_TaskSpec.from_json(json_dict=task_spec_json_dict)

            if is_bimanual:
                data_generator = BimanualDataGenerator(
                    task_spec=task_spec,
                    dataset_path=source_dataset_path,
                    arm_assignment_options=arm_assignment_options,
                    subtask_dependencies=subtask_dependencies,
                    demo_keys=None,
                )
            elif mg_config.experiment.generation.stitching:
                data_generator = StitchingDataGenerator(
                    task_spec=task_spec,
                    dataset_path=source_dataset_path,
                    demo_keys=None,
                )
            else:
                all_demos = MG_FileUtils.get_all_demos_from_dataset(
                    dataset_path=source_dataset_path,
                    filter_key=mg_config.experiment.source.filter_key,
                    start=mg_config.experiment.source.start,
                    n=mg_config.experiment.source.n,
                )
                data_generator = DataGenerator(
                    task_spec=task_spec,
                    dataset_path=source_dataset_path,
                    demo_keys=all_demos,
                )

            if i == 0:
                print("\n==== Created Data Generator ====")
                print(data_generator)
                print("")

            video_writer = None
            if write_video:
                video_writer = imageio.get_writer(args.video_path, fps=20)

            num_success = 0
            num_failures = 0
            num_attempts = 0
            num_problematic = 0
            ep_lengths = []
            num_trials = mg_config.experiment.generation.num_trials
            guarantee_success = mg_config.experiment.generation.guarantee
            initial_state = None
            n_reuse_initial_state = 0

            while True:

                generated_traj = data_generator.generate(
                    env=env,
                    env_interface=env_interface,
                    select_src_per_subtask=mg_config.experiment.generation.select_src_per_subtask,
                    transform_first_robot_pose=mg_config.experiment.generation.transform_first_robot_pose,
                    interpolate_from_last_target_pose=mg_config.experiment.generation.interpolate_from_last_target_pose,
                    render=args.render,
                    video_writer=video_writer,
                    video_skip=args.video_skip,
                    camera_names=render_image_names,
                    pause_subtask=args.pause_subtask,
                    init_noops=mg_config.experiment.generation.init_noops,
                    initial_state=initial_state,
                )
                
                success = bool(generated_traj["success"])
                if mg_config.experiment.generation.filter_joint_limit:
                    success = success and not generated_traj['joint_limit_hit']

                initial_state = generated_traj["initial_state"]

                _write_fn = write_bimanual_demo_to_hdf5 if is_bimanual else MG_FileUtils.write_demo_to_hdf5

                _extra_kwargs = {}
                if is_bimanual and "actions_joint_pos" in generated_traj:
                    _extra_kwargs["actions_joint_pos"] = generated_traj["actions_joint_pos"]

                if success:
                    num_success += 1
                    total_num_success += 1

                    ep_lengths.append(generated_traj["actions"].shape[0])
                    total_ep_lengths.append(generated_traj["actions"].shape[0])
                    _write_fn(
                        folder=tmp_dataset_folder_path,
                        env=env,
                        prefix=variant.split(".")[0],
                        initial_state=initial_state,
                        states=generated_traj["states"],
                        observations=(generated_traj["observations"] if mg_config.obs.collect_obs else None),
                        datagen_info=generated_traj["datagen_infos"],
                        actions=generated_traj["actions"],
                        abs_actions=generated_traj["abs_actions"],
                        **_extra_kwargs,
                    )
                    initial_state = None
                else:
                    num_failures += 1
                    total_num_failures += 1

                    if n_reuse_initial_state < mg_config.experiment.generation.n_reuse_initial_state:
                        n_reuse_initial_state += 1
                    else:
                        initial_state = None

                    if mg_config.experiment.generation.keep_failed and \
                        ((mg_config.experiment.max_num_failures is None) or (num_failures <= mg_config.experiment.max_num_failures)):

                        _write_fn(
                            folder=tmp_dataset_failed_folder_path,
                            env=env,
                            prefix=variant.split(".")[0],
                            initial_state=generated_traj["initial_state"],
                            states=generated_traj["states"],
                            observations=(generated_traj["observations"] if mg_config.obs.collect_obs else None),
                            datagen_info=generated_traj["datagen_infos"],
                            actions=generated_traj["actions"],
                            abs_actions=generated_traj["abs_actions"],
                            **_extra_kwargs,
                        )

                num_attempts += 1
                total_num_attempts += 1
                print("")
                print("*" * 50)
                print("trial {} success: {}".format(total_num_attempts, success))
                print("have {} successes out of {} trials so far".format(total_num_success, total_num_attempts))
                print("have {} failures out of {} trials so far".format(total_num_failures, total_num_attempts))
                print("*" * 50)

                if (num_attempts % mg_config.experiment.log_every_n_attempts) == 0:
                    summary_stats = get_important_stats(
                        new_dataset_folder_path=new_dataset_folder_path,
                        num_success=total_num_success,
                        num_failures=total_num_failures,
                        num_attempts=total_num_attempts,
                        num_problematic=num_problematic,
                        start_time=start_time,
                        ep_length_stats=None,
                    )

                    max_digits = len(str(num_trials * 1000)) + 1
                    json_file_path = os.path.join(json_log_path, "attempt_{}_succ_{}_rate_{}.json".format(
                        str(num_attempts).zfill(max_digits),
                        num_success,
                        np.round((100. * num_success) / num_attempts, 2),
                    ))
                    MG_FileUtils.write_json(json_dic=summary_stats, json_path=json_file_path)

                check_val = num_success if guarantee_success else num_attempts
                if check_val >= num_trials:
                    break
                if mg_config.experiment.max_num_failures is not None and num_failures >= mg_config.experiment.max_num_failures:
                    print(f"Abandoning variant {variant}: hit max_num_failures={mg_config.experiment.max_num_failures} with {num_success} successes")
                    break

        except Exception as e:
            if args.catch_exceptions:
                print(f"Error generating data for variant {variant}")
                print(f"Error: {e}")
                continue
            else:
                raise e
    if write_video:
        video_writer.close()

    if args.disable_merge:
        print("\nFinished data generation. Skipping merge due to --disable-merge. Writing merge manifest...\n")
        print("To merge later, run: uv run scripts/mimicgen/merge_generated_dataset.py --config "
              f"{args.config}")
        
        return None
    else:
        print("\nFinished data generation. Merging per-episode hdf5s together...\n")
        MG_FileUtils.merge_all_hdf5(
            folder=tmp_dataset_folder_path,
            new_hdf5_path=new_dataset_path,
            delete_folder=True,
            per_demo_env_args=True,
        )
        if mg_config.experiment.generation.keep_failed:
            MG_FileUtils.merge_all_hdf5(
                folder=tmp_dataset_failed_folder_path,
                new_hdf5_path=new_failed_dataset_path,
                delete_folder=True,
                per_demo_env_args=True,
            )

        ep_length_stats = None
        if len(total_ep_lengths) > 0:
            ep_lengths_arr = np.array(total_ep_lengths)
            ep_length_mean = float(np.mean(ep_lengths_arr))
            ep_length_std = float(np.std(ep_lengths_arr))
            ep_length_max = int(np.max(ep_lengths_arr))
            ep_length_3std = int(np.ceil(ep_length_mean + 3. * ep_length_std))
            ep_length_stats = dict(
                ep_length_mean=ep_length_mean,
                ep_length_std=ep_length_std,
                ep_length_max=ep_length_max,
                ep_length_3std=ep_length_3std,
            )

        stats = get_important_stats(
            new_dataset_folder_path=new_dataset_folder_path,
            num_success=total_num_success,
            num_failures=total_num_failures,
            num_attempts=total_num_attempts,
            num_problematic=total_num_problematic,
            start_time=start_time,
            ep_length_stats=ep_length_stats,
        )
        print("\nStats Summary")
        print(json.dumps(stats, indent=4))

        if mg_config.experiment.render_video:
            if (num_success > 0):
                playback_video_path = os.path.join(new_dataset_folder_path, "playback_{}.mp4".format(new_dataset_folder_name))
                num_render = mg_config.experiment.num_demo_to_render
                print("Rendering successful trajectories...")
                replay_dataset(
                    dataset=new_dataset_path,
                    n=num_render,
                    output_format="video",
                    video_output_dir=playback_video_path,
                    video_fps=20,
                    speedup=5.0,
                    camera_names=render_image_names,
                )
            else:
                print("\n" + "*" * 80)
                print("\nWARNING: skipping dataset video creation since no successes")
                print("\n" + "*" * 80 + "\n")
            if mg_config.experiment.generation.keep_failed:
                if (num_failures > 0):
                    playback_video_path = os.path.join(new_dataset_folder_path, "playback_{}_failed.mp4".format(new_dataset_folder_name))
                    num_render = mg_config.experiment.num_fail_demo_to_render
                    print("Rendering failure trajectories...")
                    replay_dataset(
                        dataset=new_failed_dataset_path,
                        n=num_render,
                        output_format="video",
                        video_output_dir=playback_video_path,
                        video_fps=20,
                        speedup=5.0,
                        camera_names=render_image_names,
                    )
                else:
                    print("\n" + "*" * 80)
                    print("\nWARNING: skipping dataset video creation since no failures")
                    print("\n" + "*" * 80 + "\n")

        final_important_stats = get_important_stats(
            new_dataset_folder_path=new_dataset_folder_path,
            num_success=total_num_success,
            num_failures=total_num_failures,
            num_attempts=total_num_attempts,
            num_problematic=total_num_problematic,
            start_time=start_time,
            ep_length_stats=ep_length_stats,
        )

        json_file_path = os.path.join(new_dataset_folder_path, "important_stats.json")
        MG_FileUtils.write_json(json_dic=final_important_stats, json_path=json_file_path)

        return final_important_stats


def main(args: GenerateDatasetArgs):
    with open(args.config, "r") as f:
        ext_cfg = json.load(f)
        if "meta" in ext_cfg:
            del ext_cfg["meta"]

    mg_config = MGConfig.from_dict(ext_cfg)

    # Delete any subtasks not in the external config.
    source_subtasks = set(mg_config.task.task_spec.keys())
    new_subtasks = set(ext_cfg["task"]["task_spec"].keys())
    for subtask in (source_subtasks - new_subtasks):
        print("deleting subtask {} in original config".format(subtask))
        del mg_config.task.task_spec[subtask]

    if args.source is not None:
        mg_config.experiment.source.dataset_path = args.source

    if args.folder is not None:
        mg_config.experiment.generation.path = args.folder

    if args.num_demos is not None:
        mg_config.experiment.generation.num_trials = args.num_demos

    if args.seed is not None:
        mg_config.experiment.seed = args.seed

    if args.debug:
        mg_config.experiment.source.n = 3
        mg_config.experiment.generation.guarantee = False
        mg_config.experiment.generation.num_trials = 2

    important_stats = generate_dataset(mg_config, args)
    important_stats = json.dumps(important_stats, indent=4)
    print("\nFinal Data Generation Stats")
    print(important_stats)


if __name__ == "__main__":
    args = tyro.cli(GenerateDatasetArgs)
    main(args)
