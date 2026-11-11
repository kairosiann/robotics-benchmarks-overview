"""
Script to extract observations from a dataset of states and actions.

Example usage:
    python scripts/data/replay_dataset.py \
        --dataset /path/to/dataset.hdf5 \
        --output_format hdf5 \
        --hdf5_output_file /path/to/output.hdf5 \
        --render
"""

from dataclasses import dataclass, field
from typing import Literal

from mesa.utils.replay import replay_dataset


@dataclass
class ReplayDatasetArgs:
    dataset: str
    n: int | None = None
    start_idx: int = 0
    end_idx: int | None = None
    camera_names: list[str] = field(
        default_factory=lambda: ["leftshoulder", "rightshoulder", "robot0_eye_in_hand"]
    )
    camera_height: int = 224
    camera_width: int = 224
    camera_depths: bool = False
    depth_uint16_mm: bool = True
    return_2d_bboxes: bool = False
    return_3d_bboxes: bool = False
    render: bool = False
    remove_done_frames: bool = False
    output_format: Literal["hdf5", "lerobot", "video"] | None = None
    hdf5_compress: bool = False
    hdf5_output_file: str | None = None
    lerobot_root_dir: str | None = None
    lerobot_repo_id: str | None = None
    lerobot_fps: int = 20
    lerobot_visual_mode: Literal["image", "video"] = "image"
    video_output_dir: str | None = None
    video_fps: int = 15
    video_speedup: float = 1.0

    def __post_init__(self):
        if self.output_format == "hdf5":
            assert self.hdf5_output_file is not None, "hdf5_output_file must be provided"
        elif self.output_format == "lerobot":
            assert self.lerobot_root_dir is not None, "lerobot_root_dir must be provided"
            assert self.lerobot_repo_id is not None, "lerobot_repo_id must be provided"
        elif self.output_format == "video":
            assert self.video_output_dir is not None, "video_output_dir must be provided"

        if self.output_format is None and not self.render:
            raise ValueError("output_format must be provided if render is False. This configuration will do nothing.")


if __name__ == "__main__":
    import tyro

    args = tyro.cli(ReplayDatasetArgs)
    replay_dataset(
        dataset=args.dataset,
        n=args.n,
        start_idx=args.start_idx,
        end_idx=args.end_idx,
        camera_names=args.camera_names,
        camera_height=args.camera_height,
        camera_width=args.camera_width,
        camera_depths=args.camera_depths,
        depth_uint16_mm=args.depth_uint16_mm,
        return_2d_bboxes=args.return_2d_bboxes,
        return_3d_bboxes=args.return_3d_bboxes,
        render=args.render,
        remove_done_frames=args.remove_done_frames,
        output_format=args.output_format,
        hdf5_output_file=args.hdf5_output_file,
        hdf5_compress=args.hdf5_compress,
        lerobot_root_dir=args.lerobot_root_dir,
        lerobot_repo_id=args.lerobot_repo_id,
        lerobot_fps=args.lerobot_fps,
        lerobot_visual_mode=args.lerobot_visual_mode,
        video_output_dir=args.video_output_dir,
        video_fps=args.video_fps,
        speedup=args.video_speedup,
    )
