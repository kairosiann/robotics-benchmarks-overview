"""
Script to initialize an environment multiple times and capture initial leftshoulder images as a video.

This script takes a task_suite and task_name, creates a MESA environment using robosuite.make(),
resets it multiple times, and stores the first image capture ("leftshoulder_image" key in observations) 
from each reset as frames in a video.

Example usage:

    For a MESA task:

    python scripts/capture_reset_frames.py \
        --file-names /abs/path/to/task_a.bddl /abs/path/to/task_b.bddl \
        --num-files 20 \
        --output-video reset_frames.mp4 \
        --fps 10
    
"""

import os
from dataclasses import dataclass
from typing import List, Optional

import imageio
import numpy as np
import robosuite
import tyro
from tqdm import tqdm

import mesa
from mesa.sim.envs.bddl_base_domain import BDDLBaseDomain


@dataclass
class CaptureResetFramesArgs:
    """Arguments for the capture_reset_frames script.
    
    This script initializes an environment multiple times and captures initial leftshoulder images as a video.
    """
    file_names: List[str]
    """Paths to one or more BDDL files."""
    
    num_resets: int = 1
    """Number of environment resets to perform (number of frames to capture)."""

    num_files: int | None = None
    """Number of files to capture frames from. If None, all files will be captured."""
    
    output_video: str = "vids/initial_frames.mp4"
    """Output video file path (used if --output_images_dir is not set)."""
    
    output_images_dir: Optional[str] = None
    """If set, save frames as images in this directory instead of a video."""
    
    fps: int = 10
    """Frames per second for output video."""
    
    robots: List[str] = None
    """Robot types to use."""

    camera_name: str = "leftshoulder"
    """Camera names to capture."""
    
    image_height: int = 1080
    """Height of captured images."""
    
    image_width: int = 1920
    """Width of captured images."""

    transparent_robot: bool = False
    """Whether to make the robot transparent."""

    def __post_init__(self):
        if self.robots is None:
            self.robots = ["Panda"]


def capture_reset_frames(args: CaptureResetFramesArgs):
    """
    Initialize environment multiple times and capture initial leftshoulder images.
    """
    print(
        f"Setting up capture. files: {args.file_names}"
    )

    # Collect initial frames
    frames = []
    saved_image_count = 0
    if args.output_images_dir:
        os.makedirs(args.output_images_dir, exist_ok=True)
    
    # Iterate each file, create env, capture frames
    for bddl_file_name in args.file_names[:args.num_files]:
        if not os.path.exists(bddl_file_name):
            raise FileNotFoundError(f"BDDL file not found: {bddl_file_name}")

        env: BDDLBaseDomain = mesa.make_env(
            json_file=bddl_file_name,
            robots=args.robots,
            has_renderer=False,
            has_offscreen_renderer=True,
            camera_names=[args.camera_name],
            camera_heights=args.image_height,
            camera_widths=args.image_width,
            horizon=1000,
        )

        print(f"Collecting {args.num_resets} initial frames for {os.path.basename(bddl_file_name)}...")
        for i in tqdm(range(args.num_resets), desc=f"Capturing frames ({os.path.basename(bddl_file_name)})"):
            obs = env.stable_reset()

            if args.transparent_robot:
                for geom_id in range(env.sim.model.ngeom):
                    name = env.sim.model.geom_id2name(geom_id)
                    if name is not None and "robot" in name:
                        env.sim.model.geom_rgba[geom_id, 3] = 0.2  # alpha

            frame = obs[f"{args.camera_name}_image"]

            flip_img = 1
            if robosuite.macros.IMAGE_CONVENTION == "opengl":
                flip_img = -1
            frame = frame[::flip_img, :, :]

            if frame.dtype != np.uint8:
                frame = (
                    (frame * 255).astype(np.uint8)
                    if frame.max() <= 1.0
                    else frame.astype(np.uint8)
                )

            if len(frame.shape) == 3 and frame.shape[2] == 3:
                pass
            elif len(frame.shape) == 3 and frame.shape[2] == 4:
                frame = frame[:, :, :3]
            else:
                raise ValueError(f"Unexpected image shape: {frame.shape}")

            if args.output_images_dir:
                out_path = os.path.join(args.output_images_dir, f"{saved_image_count:06d}.png")
                imageio.imwrite(out_path, frame)
                saved_image_count += 1
            else:
                frames.append(frame)

        env.close()

    # Save output
    if args.output_images_dir:
        out_dir = args.output_images_dir
        print(f"Saved {saved_image_count} images to {out_dir}")
    else:
        print(f"Saving video to: {args.output_video}")
        os.makedirs(
            (
                os.path.dirname(args.output_video)
                if os.path.dirname(args.output_video)
                else "."
            ),
            exist_ok=True,
        )

        try:
            with imageio.get_writer(args.output_video, fps=args.fps, quality=8) as writer:
                for frame in frames:
                    writer.append_data(frame)

            print(f"Video saved successfully!")
            print(f"Video details:")
            print(f"  - Frames: {len(frames)}")
            print(f"  - Resolution: {frames[0].shape[1]}x{frames[0].shape[0]}")
            print(f"  - FPS: {args.fps}")
            print(f"  - Duration: {len(frames) / args.fps:.2f} seconds")

        except Exception as e:
            print(f"Error saving video: {e}")
            raise


def main(args: CaptureResetFramesArgs):
    """Main function to capture reset frames from environment resets."""
    # Validate arguments
    if args.num_resets < 1 or (args.num_files is not None and args.num_files < 1):
        raise ValueError("num_resets and num_files must be positive")
    if not args.file_names:
        raise ValueError("At least one task file is required")
    capture_reset_frames(args)


if __name__ == "__main__":
    args = tyro.cli(CaptureResetFramesArgs)
    main(args)
