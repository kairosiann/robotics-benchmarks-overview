"""
Simple saver that writes observation image streams to per-episode videos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np

from mesa.utils.data_saver.base_saver import EpisodeSaver


class VideoSaver(EpisodeSaver):
    """Dump each `*_image` observation stream into an mp4 video."""

    def __init__(self, *, video_dir: str, fps: int = 15, speedup: float = 1.0) -> None:
        super().__init__()
        self.video_dir = video_dir
        self.fps = fps
        self.speedup = speedup
        self._concat_video_path: Path | None = None
        self._concat_writer: Any | None = None

        if self.fps <= 0:
            raise ValueError(f"fps must be > 0, got {self.fps}")
        if self.speedup <= 0:
            raise ValueError(f"speedup must be > 0, got {self.speedup}")

    @property
    def _effective_fps(self) -> float:
        return self.fps * self.speedup

    @property
    def destination(self) -> str:
        if self._concat_video_path is not None:
            return f"video file {str(self._concat_video_path)!r}"
        return f"video directory {self.video_dir!r}"

    def open(self) -> None:
        output_path = Path(self.video_dir)
        if output_path.suffix.lower() == ".mp4":
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._concat_video_path = output_path
            self._concat_writer = imageio.get_writer(output_path, fps=self._effective_fps)
            # Single output file appends as episodes are processed; no resume metadata.
            self._existing_demos = set()
            return
        else:
            output_path.mkdir(parents=True, exist_ok=True)

            # Resume support: any file with "<episode_key>__" prefix marks the episode as written.
            existing: set[str] = set()
            for video_path in output_path.glob("*.mp4"):
                episode_key = video_path.stem.split("__", maxsplit=1)[0]
                if episode_key:
                    existing.add(episode_key)
            self._existing_demos = existing

    def close(self) -> None:
        if self._concat_writer is not None:
            self._concat_writer.close()
            self._concat_writer = None
        self._concat_video_path = None
        self._existing_demos = set()

    def write_episode(
        self,
        *,
        episode_key: str,
        trajectory: dict[str, Any],
        initial_state: dict[str, Any],
        task: str,
    ) -> None:
        _ = initial_state, task
        obs = trajectory["obs"]
        image_keys = sorted(obs_key for obs_key in obs if obs_key.endswith("_image"))

        if self._concat_writer is not None:
            # Concatenate all image streams into one output file in deterministic order.
            for obs_key in image_keys:
                frames = obs[obs_key]
                for frame in frames:
                    # Ensure uint8 for video encoding.
                    if frame.dtype != np.uint8:
                        frame = np.clip(frame, 0, 255).astype(np.uint8)
                    self._concat_writer.append_data(frame)
            return

        for obs_key, frames in obs.items():
            if not obs_key.endswith("_image"):
                continue

            video_path = Path(self.video_dir) / f"{episode_key}__{obs_key}.mp4"
            with imageio.get_writer(video_path, fps=self._effective_fps) as writer:
                for frame in frames:
                    # Ensure uint8 for video encoding.
                    if frame.dtype != np.uint8:
                        frame = np.clip(frame, 0, 255).astype(np.uint8)
                    writer.append_data(frame)
