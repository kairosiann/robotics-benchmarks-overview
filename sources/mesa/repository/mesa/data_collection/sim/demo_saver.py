import json
import os
import pathlib
from collections import defaultdict

import h5py
import natsort
import numpy as np
from termcolor import colored


class DemoSaver:
    """
    Saves demonstration data to an hdf5 file.

    Example usage:
    ==============

    env = ... # some environment
    env_args = {...} # dictionary of environment arguments

    # create a demo saver
    demo_saver = DemoSaver("demo.hdf5", env_args, model_file)

    # start collecting data
    for i in range(100):
        obs, action = env.step()
        demo_saver.append({"obs": obs, "action": action})

    if env.is_done():
        # done collecting data
        demo_saver.done()
    else:
        # discard data
        demo_saver.discard()

    File structure:
    ===============
    The saved hdf5 file will have the following structure:
    data
    ├── .attrs
    │   ├── env_args (contains env_name, env_kwargs)
    ├── demo_0
    │   ├── .attrs
    │   │   ├── model_file
    │   |   ├── num_samples
    │   ├── obs
    │   │   ├── image
    │   │   |   ...
    │   ├── actions
    │   ├── actions_abs
    │   ├── states
    ├── demo_1
    │   │   ...
    """

    def __init__(self, save_path, env_args, model_file, flush_freq=50):
        self.flush_freq = flush_freq
        self.save_path = save_path
        self.file = h5py.File(save_path, "w")
        self._f_grp = self.file.create_group("data")
        self._f_grp.attrs["env_args"] = json.dumps(env_args)
        self._ep_data_grp = self._f_grp.create_group("demo_0")
        self._ep_data_grp.attrs["model_file"] = model_file
        self._chunk_count = 0

        self.data_buffer = {
            "obs": [],
            "actions": [],
            "actions_abs": [],
            "states": [],
        }
        self.buffer_len = 0

        self.env_args = env_args

    @staticmethod
    def merge_hdf5s(
        demo_dir,
        out_file="demo.hdf5",
        verbose=False,
        multi_env_args=False,
        delete_source_files=False,
    ):
        files = natsort.natsorted([f for f in os.listdir(demo_dir) if f.endswith(".hdf5")])
        if verbose:
            print(f"Found {len(files)} files in {demo_dir}")

        out_path = os.path.join(demo_dir, out_file)
        if os.path.exists(out_path):
            return
            # os.system(f"rm {out_path}")
        f_dst = h5py.File(out_path, "w")
        f_dst_grp = f_dst.create_group("data")

        if multi_env_args:
            all_env_args = {}

        merged_src_paths = []
        for i_demo, filename in enumerate(files):
            if verbose:
                print(f"Processing {filename}...", end=" ")

            demo_str = f"demo_{i_demo}"
            src_path = os.path.join(demo_dir, filename)
            if src_path != out_path:
                with h5py.File(os.path.join(demo_dir, filename), "r") as f_src:
                    if multi_env_args:
                        env_args = json.loads(f_src["data"].attrs["env_args"])
                        all_env_args[demo_str] = env_args
                    elif i_demo == 0:
                            f_dst_grp.attrs["env_args"] = f_src["data"].attrs["env_args"]

                    assert (
                        len(f_src["data"].keys()) == 1
                    ), "This script assumes a single demo per hdf5."
                    src_demo_key = list(f_src["data"].keys())[0]

                    f_src.copy(f"data/{src_demo_key}", f_dst_grp, name=demo_str)
                merged_src_paths.append(src_path)
            if verbose:
                print("done.")

        if multi_env_args:
            f_dst_grp.attrs["env_args"] = json.dumps(all_env_args, indent=4)

        f_dst.close()
        if delete_source_files:
            for src_path in merged_src_paths:
                os.remove(src_path)
            if verbose:
                print(
                    f"Deleted {len(merged_src_paths)} source files after merge.",
                    colored("delete_source_files=True", "yellow"),
                )
        if verbose:
            print(f"Merged {len(files)} demos into", colored(out_file, "green"))

    def _flush_buffer_to_disk(self, verbose=False):
        if self.buffer_len > 0:
            if verbose:
                print(
                    colored(
                        f"flushing chunk_{self._chunk_count} of size {self.buffer_len} to disk",
                        "yellow",
                    )
                )
            # flush data to disk
            for k in self.data_buffer:
                if k == "obs":
                    for k in self.data_buffer["obs"][0]:
                        obs_chunk_to_flush = np.stack(
                            [
                                self.data_buffer["obs"][i][k]
                                for i in range(self.buffer_len)
                            ],
                            0,
                        )
                        self._ep_data_grp.create_dataset(
                            f"chunk_{self._chunk_count}/obs/{k}",
                            data=obs_chunk_to_flush,
                        )
                else:
                    chunk_to_flush = np.stack(self.data_buffer[k], 0)
                    self._ep_data_grp.create_dataset(
                        f"chunk_{self._chunk_count}/{k}", data=chunk_to_flush
                    )

            # empty buffer
            for k in self.data_buffer:
                self.data_buffer[k] = []
            self.buffer_len = 0

    def append(self, data, verbose=False):
        for k in self.data_buffer:
            self.data_buffer[k].append(data[k])
        self.buffer_len += 1

        if self.buffer_len == self.flush_freq:
            self._flush_buffer_to_disk(verbose=verbose)
            self._chunk_count += 1

    def _merge_chunks(self):
        tmp_path = pathlib.Path(self.save_path).parent / "tmp.hdf5"
        os.system(f"mv {self.save_path} {tmp_path}")

        with h5py.File(tmp_path, "r") as f_src:
            src_grp = f_src["data"]["demo_0"]

            with h5py.File(self.save_path, "w") as f_dst:
                # create data group
                f_dst_grp = f_dst.create_group("data")
                # copy data attributes
                for k in f_src["data"].attrs.keys():
                    f_dst_grp.attrs[k] = f_src["data"].attrs[k]
                # create demo group
                dst_grp = f_dst_grp.create_group("demo_0")
                # copy demo attributes
                for k in f_src["data/demo_0"].attrs.keys():
                    dst_grp.attrs[k] = f_src["data/demo_0"].attrs[k]

                # merge chunks
                ordered_chunk_names = sorted(
                    [chunk for chunk in src_grp.keys()],
                    key=lambda x: int(x.split("_")[1]),
                )
                for k in self.data_buffer:
                    if k == "obs":
                        obs_merged = defaultdict(list)
                        for chunk in ordered_chunk_names:
                            all_obs = src_grp[chunk]["obs"]
                            for obs_key in all_obs:
                                obs_merged[obs_key].append(all_obs[obs_key])
                        for obs_key in obs_merged:
                            merged_obs = np.concatenate(obs_merged[obs_key], axis=0)
                            # NOTE(VS): might want to resize images here
                            dst_grp.create_dataset(
                                f"obs/{obs_key}", data=np.array(merged_obs)
                            )
                    else:
                        data_merged = []
                        for chunk in ordered_chunk_names:
                            data = src_grp[chunk][k]
                            data_merged.append(data)
                        data_merged = np.concatenate(data_merged, axis=0)
                        dst_grp.create_dataset(k, data=np.array(data_merged))

                # add num_samples attribute to demo
                num_samples = sum(
                    [
                        src_grp[chunk]["actions"].shape[0]
                        for chunk in ordered_chunk_names
                    ]
                )
                dst_grp.attrs["num_samples"] = num_samples

                # assume sparse rewards for now, that occur at the end of a demonstration
                rewards = np.zeros(dst_grp["actions"].shape[0])
                rewards[-1] = 1.0
                dones = np.zeros(dst_grp["actions"].shape[0])
                dones[-1] = 1.0
                dones = dones.astype(int)
                dst_grp.create_dataset("rewards", data=np.array(rewards))
                dst_grp.create_dataset("dones", data=np.array(dones))

        os.system(f"rm {tmp_path}")

    def done(self):
        # flush remaining buffer to disk
        self._flush_buffer_to_disk()

        # close file
        self.file.close()

        # merge chunks
        self._merge_chunks()

    def __len__(self):
        return self._chunk_count * self.flush_freq + self.buffer_len

    def discard(self):
        self.file.close()
        os.system(f"rm {self.save_path}")
