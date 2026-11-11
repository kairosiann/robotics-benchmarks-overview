"""
Utilities for writing trajectories to HDF5 in the "robomimic-style" dataset format.

This module exists to keep dataset-writing logic out of scripts (e.g. replay / conversion),
and to centralize behaviors like:
- creating the output file / `data` group
- copying global attrs from a source dataset
- resuming and skipping already-written episodes
- cleaning up incomplete episode groups
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

import h5py
import numpy as np

from mesa.utils.data_saver.base_saver import EpisodeSaver


class HDF5Saver(EpisodeSaver):
    """
    HDF5 writer for trajectories under `data/<episode_key>/...`.

    Intended to be instantiated by scripts that *read* a source dataset and *write* a derived dataset.
    """

    def __init__(
        self,
        *,
        hdf5_output_file: str,
        data_attrs: dict[str, Any],
        compress: bool = False,
    ) -> None:
        super().__init__()
        parent_dir = os.path.dirname(hdf5_output_file)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        self.output_file = hdf5_output_file

        self.data_attrs = data_attrs
        self.compress = compress

        self._file: h5py.File | None = None
        self._data_grp: h5py.Group | None = None

    @property
    def destination(self) -> str:
        return self.output_file

    def open(self) -> None:
        """
        Open the output file in a way that supports resume:
        - If the file exists, open in append mode, delete incomplete episodes, and record existing keys.
        - If it doesn't exist, create it and copy global attrs from the source dataset.
        """
        if self._file is not None:
            raise RuntimeError("HDF5Saver is already open")

        if os.path.exists(self.output_file):
            self._file = h5py.File(self.output_file, "a")
            if "data" in self._file:
                self._data_grp = self._file["data"]
                self._cleanup_incomplete_episodes(self._data_grp)
                self._existing_demos = set(self._data_grp.keys())
            else:
                # output exists but doesn't contain the expected group; treat like "fresh"
                self._data_grp = self._file.create_group("data")
                self._copy_global_attrs(self._data_grp)
        else:
            self._file = h5py.File(self.output_file, "w")
            self._data_grp = self._file.create_group("data")
            self._copy_global_attrs(self._data_grp)

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
        self._file = None
        self._data_grp = None
        self._existing_demos = set()

    def write_episode(
        self,
        *,
        episode_key: str,
        trajectory: dict[str, Any],
        initial_state: dict[str, Any],
        task: str,
    ) -> None:
        """
        Write a single episode group under `data/<episode_key>`.

        Expected keys in `trajectory` match `scripts/replay_dataset.extract_trajectory`.
        """
        _ = task
        if self._data_grp is None:
            raise RuntimeError("HDF5Saver must be opened before writing")

        ep_data_grp = self._data_grp.create_group(episode_key)
        ep_data_grp.create_dataset("actions", data=np.array(trajectory["actions"]))
        ep_data_grp.create_dataset("abs_actions", data=np.array(trajectory["abs_actions"]))
        if 'actions_joint_pos' in trajectory:
            ep_data_grp.create_dataset("actions_joint_pos", data=np.array(trajectory["actions_joint_pos"]))
        ep_data_grp.create_dataset("states", data=np.array(trajectory["states"]))
        ep_data_grp.create_dataset("rewards", data=np.array(trajectory["rewards"]))
        ep_data_grp.create_dataset("dones", data=np.array(trajectory["dones"]))

        for obs_key in trajectory["obs"]:
            if self.compress:
                ep_data_grp.create_dataset(
                    f"obs/{obs_key}",
                    data=np.array(trajectory["obs"][obs_key]),
                    compression="gzip",
                )
            else:
                ep_data_grp.create_dataset(
                    f"obs/{obs_key}",
                    data=np.array(trajectory["obs"][obs_key]),
                )

        # copy episode metadata
        ep_data_grp.attrs["model_file"] = initial_state["model"]  # model xml for this episode
        ep_data_grp.attrs["num_samples"] = trajectory["actions"].shape[0]  # number of transitions

    def _copy_global_attrs(self, data_grp: h5py.Group) -> None:
        for k, v in self.data_attrs.items():
            if type(v) is dict:
                v = json.dumps(v)
            data_grp.attrs[k] = v

    @staticmethod
    def _cleanup_incomplete_episodes(data_grp: h5py.Group) -> None:
        """
        Remove any incomplete episode groups (defined as missing an 'actions' dataset).
        Matches logic in `scripts/replay_dataset.py`.
        """
        keys_to_check: Iterable[str] = list(data_grp.keys())
        for ep_key in keys_to_check:
            if "actions" not in data_grp[ep_key]:
                del data_grp[ep_key]