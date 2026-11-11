import argparse
import json
import os
import sys

import numpy as np

import mesa.mimicgen.utils.file_utils as MG_FileUtils
from mesa.utils.replay import replay_dataset


def merge_from_config(config_path: str) -> None:
    # Load external config used for generation
    with open(config_path, "r") as f:
        cfg = json.load(f)

    exp = cfg.get("experiment", {})
    gen = exp.get("generation", {})

    base_folder = os.path.expandvars(os.path.expanduser(gen.get("path", "")))
    run_name = exp.get("name", "demo")
    run_folder = os.path.join(base_folder, run_name)

    # Infer folders and output paths
    tmp_success_folder = os.path.join(run_folder, "tmp")
    tmp_failed_folder = os.path.join(run_folder, "tmp_failed")
    output_success_path = os.path.join(run_folder, "demo.hdf5")
    output_failed_path = os.path.join(run_folder, "demo_failed.hdf5")
    per_demo_env_args = True
    keep_failed = bool(gen.get("keep_failed", False))
    if not os.path.isdir(run_folder):
        raise FileNotFoundError(f"Generation run folder not found: {run_folder}")
    has_successes = os.path.isdir(tmp_success_folder)
    has_failures = keep_failed and os.path.isdir(tmp_failed_folder)
    if not has_successes and not has_failures:
        raise FileNotFoundError(
            f"No per-episode generation folders found in {run_folder}"
        )
    succ_count, succ_horizons = 0, []
    fail_count, fail_horizons = 0, []

    if has_successes:
        # Pre-compute horizons before deletion for stats
        succ_count, succ_horizons = MG_FileUtils.merge_all_hdf5(
            folder=tmp_success_folder,
            new_hdf5_path=os.path.join(run_folder, "_ignore.hdf5"),
            dry_run=True,
            return_horizons=True,
            per_demo_env_args=per_demo_env_args,
        )
    if has_failures:
        fail_count, fail_horizons = MG_FileUtils.merge_all_hdf5(
            folder=tmp_failed_folder,
            new_hdf5_path=os.path.join(run_folder, "_ignore_failed.hdf5"),
            dry_run=True,
            return_horizons=True,
            per_demo_env_args=per_demo_env_args,
        )

    if succ_count + fail_count == 0:
        raise ValueError(f"No readable per-episode HDF5 files found in {run_folder}")

    if succ_count > 0:
        print("Merging successes...")
        MG_FileUtils.merge_all_hdf5(
            folder=tmp_success_folder,
            new_hdf5_path=output_success_path,
            delete_folder=True,
            per_demo_env_args=per_demo_env_args,
            delete_images=True,
        )
    if fail_count > 0:
        print("Merging failures...")
        MG_FileUtils.merge_all_hdf5(
            folder=tmp_failed_folder,
            new_hdf5_path=output_failed_path,
            delete_folder=True,
            per_demo_env_args=per_demo_env_args,
        )

    # Mirror stats/video behavior from config
    render_video = bool(exp.get("render_video", False))
    num_demo_to_render = int(exp.get("num_demo_to_render", 10))
    num_fail_demo_to_render = int(exp.get("num_fail_demo_to_render", 25))

    # Compute stats analogous to generate_dataset
    num_success = succ_count
    num_failures = fail_count if keep_failed else 0
    num_attempts = num_success + num_failures
    num_problematic = 0

    ep_length_stats = None
    if len(succ_horizons) > 0:
        arr = np.array(succ_horizons)
        ep_length_mean = float(np.mean(arr))
        ep_length_std = float(np.std(arr))
        ep_length_max = int(np.max(arr))
        ep_length_3std = int(np.ceil(ep_length_mean + 3.0 * ep_length_std))
        ep_length_stats = dict(
            ep_length_mean=ep_length_mean,
            ep_length_std=ep_length_std,
            ep_length_max=ep_length_max,
            ep_length_3std=ep_length_3std,
        )

    def make_stats_dict():
        rate_div = (num_attempts if num_attempts > 0 else 1)
        return dict(
            generation_path=run_folder,
            success_rate=((100.0 * num_success) / rate_div),
            failure_rate=((100.0 * num_failures) / rate_div),
            num_success=num_success,
            num_failures=num_failures,
            num_attempts=num_attempts,
            num_problematic=num_problematic,
            **(ep_length_stats or {}),
        )

    stats = make_stats_dict()
    print("\nStats Summary")
    print(json.dumps(stats, indent=4))

    # Write stats file
    stats_path = os.path.join(run_folder, "important_stats.json")
    MG_FileUtils.write_json(json_dic=stats, json_path=stats_path)

    # Optional video rendering
    if render_video:
        run_name = os.path.basename(run_folder.rstrip(os.sep))
        if num_success > 0:
            print("Rendering successful trajectories...")
            playback_video_path = os.path.join(run_folder, f"playback_{run_name}.mp4")
            replay_dataset(
                dataset=output_success_path,
                n=num_demo_to_render,
                output_format="video",
                video_output_dir=playback_video_path,
                video_fps=20,
                speedup=5.0,
                camera_names=["leftshoulder"],
            )
        else:
            print("\n" + "*" * 80)
            print("\nWARNING: skipping dataset video creation since no successes")
            print("\n" + "*" * 80 + "\n")
        if keep_failed and num_failures > 0 and output_failed_path:
            print("Rendering failure trajectories...")
            playback_fail_video_path = os.path.join(run_folder, f"playback_{run_name}_failed.mp4")
            replay_dataset(
                dataset=output_failed_path,
                n=num_fail_demo_to_render,
                output_format="video",
                video_output_dir=playback_fail_video_path,
                video_fps=20,
                speedup=5.0,
                camera_names=["leftshoulder"],
            )
        elif keep_failed:
            print("\n" + "*" * 80)
            print("\nWARNING: skipping dataset video creation since no failures")
            print("\n" + "*" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Merge per-episode HDF5s produced by generate_dataset (config-only)")
    parser.add_argument("--config", type=str, required=True, help="Path to the MimicGen config JSON used for generation")

    args = parser.parse_args()

    merge_from_config(args.config)


if __name__ == "__main__":
    main()


