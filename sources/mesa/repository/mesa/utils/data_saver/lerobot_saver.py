"""
Utilities for writing trajectories in LeRobot dataset format.

Design goals:
- Keep LeRobot-specific save logic out of scripts.
- Mirror the "general API" of `HDF5Saver` so scripts can swap formats easily:
  - `existing_demos` (episode keys already written, for resume)
  - context-managed `open/close` lifecycle
  - `write_episode(...)`

Note: `lerobot` is imported lazily during `LeRobotSaver` instantiation so this
module can be imported even when LeRobot isn't installed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from pprint import pprint
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from mesa.utils.data_saver.base_saver import EpisodeSaver

if TYPE_CHECKING:
    from lerobot.common.datasets.lerobot_dataset import LeRobotDataset


def _safe_repo_id(name: str) -> str:
    """
    Produce a filesystem- and LeRobot-friendly repo_id-ish string.

    LeRobot repo_ids are often "namespace/name". For local creation, we mainly need
    something stable and path-safe.
    """
    name = name.strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^a-zA-Z0-9._/-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("-")
    return name or "dataset"


def _proprio_observations(obs: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    proprio = {
        key: value for key, value in obs.items()
        if re.match(r"robot\d+_", key) and "image" not in key and "depth" not in key
    }
    return {
        key: value[:, None] if value.ndim == 1 else value
        for key, value in proprio.items()
    }


class LeRobotSaver(EpisodeSaver):
    """
    Writer that converts a trajectory dict into LeRobot episodes.

    This follows the frame mapping used in `scripts/convert_libero_data_to_lerobot.py`:
    - `actions`: action vector per step
    - `abs_actions`: absolute action vector per step
    - `task`: a string label
    - `camera_names`: a list of camera names
    - `proprio_obs`: a dictionary of proprioceptive observations
    - `camera_names`: a list of camera names
    - `proprio_obs`: a dictionary of proprioceptive observations
    - `camera_names`: a list of camera names
    """

    def __init__(
        self,
        *,
        root_dir: str,
        repo_id: str,
        fps: int = 10,
        robot_type: str = "panda",
        image_writer_threads: int = 10,
        image_writer_processes: int = 5,
        camera_names: list[str] = ["leftshoulder", "rightshoulder", "robot0_eye_in_hand"],
        visual_mode: Literal["image", "video"] = "image",
    ) -> None:
        super().__init__()
        os.makedirs(root_dir, exist_ok=True)

        self.root = root_dir
        self.repo_id = _safe_repo_id(repo_id)
        self.fps = fps
        self.robot_type = robot_type
        self.image_writer_threads = image_writer_threads
        self.image_writer_processes = image_writer_processes
        self.camera_names = camera_names
        self.visual_mode = visual_mode

        self._lerobot_dataset_cls = self._import_lerobot_dataset()
        self._dataset: LeRobotDataset | None = None
        self._manifest_path: Path | None = None

    @property
    def destination(self) -> str:
        return (
            f"LeRobot dataset {self.repo_id!r} under root {self.root!r} "
            f"(visual_mode={self.visual_mode!r})"
        )

    def open(self) -> None:
        """
        Lazily import and create the LeRobot dataset if needed, and load manifest for resume.
        """
        if self._dataset is not None:
            raise RuntimeError("LeRobotSaver is already open")

        dataset_dir = Path(self.root) / self.repo_id
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        # dataset_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = dataset_dir / ".lerobot_episodes.json"
        self._existing_demos = self._load_manifest(self._manifest_path)

    def close(self) -> None:
        # LeRobotDataset doesn't require an explicit close in typical usage.
        self._dataset = None
        self._existing_demos = set()
        self._manifest_path = None

    def write_episode(
        self,
        *,
        episode_key: str,
        trajectory: dict[str, Any],
        initial_state: dict[str, Any],
        task: str,
    ) -> None:
        """
        Convert `trajectory` into LeRobot frames and save as one episode.
        """
        _ = initial_state
        if self._manifest_path is None:
            raise RuntimeError("LeRobotSaver must be opened before writing")

        obs = trajectory["obs"]
        actions = trajectory["actions"].astype(np.float32)
        abs_actions = trajectory["abs_actions"].astype(np.float32)
        proprio_obs = _proprio_observations(obs)

        num_steps = actions.shape[0]
        fields = {**proprio_obs, "abs_actions": abs_actions}
        fields.update({f"{cam}_image": obs[f"{cam}_image"] for cam in self.camera_names})
        if "actions_joint_pos" in trajectory:
            fields["actions_joint_pos"] = trajectory["actions_joint_pos"]
        if any(len(value) != num_steps for value in fields.values()):
            raise ValueError("LeRobot trajectory fields must have matching lengths")
        if self._dataset is None:
            self._dataset = self._create_dataset_from_trajectory(trajectory)
        for i in range(num_steps):
            frame: dict[str, Any] = {
                # match conversion script: reverse channel dimension (RGB<->BGR)
                "actions": actions[i],
                "abs_actions": abs_actions[i],
                "task": task,
            }
            if 'actions_joint_pos' in trajectory:
                frame['actions_joint_pos'] = trajectory['actions_joint_pos'][i].astype(np.float32)
            frame.update({f'{k}_image': obs[f'{k}_image'][i] for k in self.camera_names})
            frame.update({k: proprio_obs[k][i].astype(np.float32) for k in proprio_obs.keys()})
            self._dataset.add_frame(frame)


        self._dataset.save_episode()
        self._dataset.clear_episode_buffer()

        # update manifest for resume
        self._existing_demos.add(episode_key)
        self._write_manifest(self._manifest_path, self._existing_demos)

    def _create_dataset_from_trajectory(self, trajectory: dict[str, Any]) -> LeRobotDataset:
        """
        Create a LeRobotDataset instance using feature shapes inferred from the first episode.
        """
        obs = trajectory["obs"]
        actions = trajectory["actions"]

        agent_img = obs[self.camera_names[0] + "_image"][0]
        h, w, c = agent_img.shape

        action_dim = int(actions.shape[1]) if actions.ndim == 2 else int(actions.size)

        proprio_obs = _proprio_observations(obs)

        features: dict[str, Any] = {
            **{f"{cam}_image": {
                "dtype": self.visual_mode,
                "shape": (h, w, c),
                "names": ["height", "width", "channel"],
            } for cam in self.camera_names},
            "actions": {
                "dtype": "float32",
                "shape": (action_dim,),
                "names": ["actions"],
            },
            "abs_actions": {
                "dtype": "float32",
                "shape": (action_dim,),
                "names": ["abs_actions"],
            },
        }
        if 'actions_joint_pos' in trajectory:
            actions_joint_pos = trajectory['actions_joint_pos']
            action_dim = int(actions_joint_pos.shape[1]) if actions_joint_pos.ndim == 2 else int(actions_joint_pos.size)
            features['actions_joint_pos'] = {
                "dtype": "float32",
                "shape": (action_dim,),
                "names": ["actions_joint_pos"],
            }
        for k, v in proprio_obs.items():
            if len(v.shape) == 2:
                shape = v[0].shape
            else:
                shape = (1,)
            features[k] = {
                "dtype": "float32",
                "shape": shape,
                "names": [k],
            }

        pprint(features)
        return self._lerobot_dataset_cls.create(
            repo_id=self.repo_id,
            root=os.path.join(self.root, self.repo_id),
            robot_type=self.robot_type,
            fps=self.fps,
            features=features,
            use_videos=self.visual_mode == "video",
            image_writer_threads=self.image_writer_threads,
            image_writer_processes=self.image_writer_processes,
        )

    @staticmethod
    def _import_lerobot_dataset() -> type["LeRobotDataset"]:
        try:
            from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
        except ImportError as exc:
            raise ImportError(
                "LeRobotSaver requires the optional 'lerobot' dependency. "
                "Install it before instantiating this saver."
            ) from exc
        return LeRobotDataset

    @staticmethod
    def _load_manifest(path: Path) -> set[str]:
        if not path.exists():
            return set()
        data = json.loads(path.read_text())
        episodes = data.get("episodes", [])
        return set(map(str, episodes))

    @staticmethod
    def _write_manifest(path: Path, episodes: set[str]) -> None:
        payload = {"episodes": sorted(episodes)}
        path.write_text(json.dumps(payload, indent=2))

