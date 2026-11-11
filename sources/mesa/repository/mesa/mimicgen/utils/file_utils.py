# Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the NVIDIA Source Code License [see LICENSE for details].

"""
A collection of utilities related to files.
"""
import datetime
import json
import os
import shutil
import time
from glob import glob
from typing import List, Tuple

import h5py
import numpy as np
from tqdm import tqdm

import mesa.utils.tensor_utils as TensorUtils
from mesa.mimicgen.datagen.datagen_info import DatagenInfo


def _create_single_demo_hdf5(folder, prefix=None):
    """
    Create and initialize a single-demo HDF5 writer.

    Returns:
        tuple: (data_writer, data_grp, ep_data_grp, timestamp, time_str)
    """
    timestamp = time.time()
    time_str = datetime.datetime.fromtimestamp(timestamp).strftime('date_%m_%d_%Y_time_%H_%M_%S')
    if prefix is not None:
        fname = "{}__{}.hdf5".format(prefix, time_str)
    else:
        fname = "{}.hdf5".format(time_str)
    dataset_path = os.path.join(folder, fname)
    data_writer = h5py.File(dataset_path, "w")
    data_grp = data_writer.create_group("data")
    data_grp.attrs["timestamp"] = timestamp
    data_grp.attrs["readable_timestamp"] = time_str
    ep_data_grp = data_grp.create_group("demo_0")
    return data_writer, data_grp, ep_data_grp, timestamp, time_str


def _write_actions_states_obs(ep_data_grp, actions, abs_actions, states, observations):
    """
    Write actions, abs_actions, states, and optionally observations for a demo group.
    """
    ep_data_grp.create_dataset("actions", data=np.array(actions))
    ep_data_grp.create_dataset("abs_actions", data=np.array(abs_actions))

    if isinstance(states[0], dict):
        states_dict = TensorUtils.list_of_flat_dict_to_dict_of_list(states)
        for k in states_dict:
            ep_data_grp.create_dataset("states/{}".format(k), data=np.array(states_dict[k]))
    else:
        ep_data_grp.create_dataset("states", data=np.array(states))

    if observations is not None:
        obs = TensorUtils.list_of_flat_dict_to_dict_of_list(observations)
        for k in obs:
            ep_data_grp.create_dataset("obs/{}".format(k), data=np.array(obs[k]), compression="gzip")


def _write_common_episode_and_global_attrs(data_grp, ep_data_grp, env, initial_state, num_samples):
    """
    Write common episode-level and global metadata attrs.
    """
    if ("model" in initial_state) and (initial_state["model"] is not None):
        # only for robosuite envs
        ep_data_grp.attrs["model_file"] = initial_state["model"] # model xml for this episode
    ep_data_grp.attrs["num_samples"] = num_samples # number of transitions in this episode

    data_grp.attrs["total"] = num_samples
    data_grp.attrs["env_args"] = json.dumps(env.serialize(), indent=4) # environment info


def write_json(json_dic, json_path):
    """
    Write dictionary to json file.
    """
    with open(json_path, 'w') as f:
        # preserve original key ordering
        json.dump(json_dic, f, sort_keys=False, indent=4)


def get_all_demos_from_dataset(
    dataset_path,
    filter_key=None,
    start=None,
    n=None,
):
    """
    Helper function to get demonstration keys from robomimic hdf5 dataset.

    Args:
        dataset_path (str): path to hdf5 dataset
        filter_key (str or None): name of filter key
        start (int or None): demonstration index to start from
        n (int or None): number of consecutive demonstrations to retrieve

    Returns:
        demo_keys (list): list of demonstration keys
    """
    f = h5py.File(dataset_path, "r")

    # list of all demonstration episodes (sorted in increasing number order)
    if filter_key is not None:
        print("using filter key: {}".format(filter_key))
        demos = [elem.decode("utf-8") for elem in np.array(f["mask/{}".format(filter_key)])]
    else:
        demos = list(f["data"].keys())
    inds = np.argsort([int(elem[5:]) for elem in demos])
    demo_keys = [demos[i] for i in inds]
    if start is not None:
        demo_keys = demo_keys[start:]
    if n is not None:
        demo_keys = demo_keys[:n]

    f.close()
    return demo_keys


def get_env_interface_info_from_dataset(
    dataset_path,
    demo_keys,
):
    """
    Gets environment interface information from source dataset.

    Args:
        dataset_path (str): path to hdf5 dataset
        demo_keys (list): list of demonstration keys to extract info from

    Returns:
        env_interface_name (str): name of environment interface class
        env_interface_type (str): type of environment interface
    """
    f = h5py.File(dataset_path, "r")
    env_interface_names = []
    env_interface_types = []
    for ep in demo_keys:
        datagen_info_key = "data/{}/datagen_info".format(ep)
        assert datagen_info_key in f, "Could not find MimicGen metadata in dataset {}. Ensure you have run prepare_src_dataset.py on this hdf5".format(dataset_path)
        env_interface_names.append(f[datagen_info_key].attrs["env_interface_name"])
        env_interface_types.append(f[datagen_info_key].attrs["env_interface_type"])
    f.close()

    # ensure all source demos are consistent
    env_interface_name = env_interface_names[0]
    env_interface_type = env_interface_types[0]
    assert all(elem == env_interface_name for elem in env_interface_names)
    assert all(elem == env_interface_type for elem in env_interface_types)
    return env_interface_name, env_interface_type


def parse_source_dataset(
    dataset_path,
    demo_keys,
    task_spec=None,
    subtask_term_signals=None,
    subtask_term_offset_ranges=None,
    disable_tqdm=False,
) -> Tuple[List[DatagenInfo], np.ndarray, List[str], List[Tuple[int, int]]]:
    """
    Parses a source dataset to extract info needed for data generation (DatagenInfo instances) and 
    subtask indices that split each source dataset trajectory into contiguous subtask segments.

    Args:
        dataset_path (str): path to hdf5 dataset
        demo_keys (list): list of demo keys to use from dataset path
        task_spec (MG_TaskSpec instance or None): task spec object, which will be used to
            infer the sequence of subtask termination signals and offset ranges.
        subtask_term_signals (list or None): sequence of subtask termination signals, which 
            should only be provided if not providing @task_spec. Should have an entry per subtask 
            and the last subtask entry should be None, since the final subtask ends when the 
            task ends.
        subtask_term_offset_ranges (list or None): sequence of subtask termination offset ranges, which 
            should only be provided if not providing @task_spec. Should have an entry per subtask 
            and the last subtask entry should be None or (0, 0), since the final subtask ends when the 
            task ends.

    Returns:

        datagen_infos (list): list of DatagenInfo instances, one per source
            demonstration. Each instance has entries with leading dimension [T, ...], 
            the length of the trajectory.

        subtask_indices (np.array): array of shape (N, S, 2) where N is the number of
                demos and S is the number of subtasks for this task. Each entry is
                a pair of integers that represents the index at which a subtask 
                segment starts and where it is completed.

        subtask_term_signals (list): sequence of subtask termination signals

        subtask_term_offset_ranges (list): sequence of subtask termination offset ranges
    """

    # should provide either task_spec or the subtask termination lists, but not both
    assert (task_spec is not None) or ((subtask_term_signals is not None) and (subtask_term_offset_ranges is not None))
    assert (task_spec is None) or ((subtask_term_signals is None) and (subtask_term_offset_ranges is None))

    if task_spec is not None:
        subtask_term_signals = [subtask_spec["subtask_term_signal"] for subtask_spec in task_spec]
        subtask_term_offset_ranges = [subtask_spec["subtask_term_offset_range"] for subtask_spec in task_spec]

    assert len(subtask_term_signals) == len(subtask_term_offset_ranges)
    # breakpoint()
    assert subtask_term_signals[-1] is None, "end of final subtask does not need to be detected"
    assert (subtask_term_offset_ranges[-1] is None) or (subtask_term_offset_ranges[-1] == (0, 0)), "end of final subtask does not need to be detected"
    subtask_term_offset_ranges[-1] = (0, 0)

    f = h5py.File(dataset_path, "r")

    datagen_infos = []
    subtask_indices = []
    for ind in tqdm(range(len(demo_keys)), disable=disable_tqdm):
        ep = demo_keys[ind]
        try:
            ep_grp = f["data/{}".format(ep)]

            # extract datagen info
            ep_datagen_info = ep_grp["datagen_info"]
            ep_datagen_info_obj = DatagenInfo(
                eef_pose=ep_datagen_info["eef_pose"][:],
                object_poses={ k : ep_datagen_info["object_poses"][k][:] for k in ep_datagen_info["object_poses"] },
                subtask_term_signals={ k : ep_datagen_info["subtask_term_signals"][k][:] for k in ep_datagen_info["subtask_term_signals"] },
                target_pose=ep_datagen_info["target_pose"][:],
                gripper_action=ep_datagen_info["gripper_action"][:],
            )

            # parse subtask indices using subtask termination signals
            ep_subtask_indices = []
            prev_subtask_term_ind = 0
            for subtask_ind in range(len(subtask_term_signals)):
                subtask_term_signal = subtask_term_signals[subtask_ind]
                if subtask_term_signal is None:
                    # final subtask, finishes at end of demo
                    subtask_term_ind = ep_grp["actions"].shape[0]
                else:
                    # detect indices where 0 -> 1 transition occurs - this will be the end of the subtask
                    subtask_indicators = ep_datagen_info_obj.subtask_term_signals[subtask_term_signal]
                    diffs = subtask_indicators[1:] - subtask_indicators[:-1]
                    # find the first index where the subtask is completed, after the previous subtask termination index
                    end_ind = next((int(nz) + 1 for nz in diffs.nonzero()[0] if int(nz) + 1 >= prev_subtask_term_ind), None)
                    if end_ind is None:
                        raise AssertionError(f"No valid subtask termination found for {subtask_term_signal} in demo {ep}")

                    subtask_term_ind = end_ind + 1 # increment to support indexing like demo[start:end]
                ep_subtask_indices.append([prev_subtask_term_ind, subtask_term_ind])
                prev_subtask_term_ind = subtask_term_ind

            # run sanity check on subtask_term_offset_range in task spec to make sure we can never
            # get an empty subtask in the worst case when sampling subtask bounds:
            #
            #   end index of subtask i + max offset of subtask i < end index of subtask i + 1 + min offset of subtask i + 1
            #
            assert len(ep_subtask_indices) == len(subtask_term_signals), "mismatch in length of extracted subtask info and number of subtasks"
            for i in range(1, len(ep_subtask_indices)):
                prev_max_offset_range = subtask_term_offset_ranges[i - 1][1]
                assert ep_subtask_indices[i - 1][1] + prev_max_offset_range < ep_subtask_indices[i][1] + subtask_term_offset_ranges[i][0], \
                    "subtask sanity check violation in demo key {} with subtask {} end ind {}, subtask {} max offset {}, subtask {} end ind {}, and subtask {} min offset {}".format(
                        demo_keys[ind], i - 1, ep_subtask_indices[i - 1][1], i - 1, prev_max_offset_range, i, ep_subtask_indices[i][1], i, subtask_term_offset_ranges[i][0])

            # only append after all checks pass
            datagen_infos.append(ep_datagen_info_obj)
            subtask_indices.append(ep_subtask_indices)

        except AssertionError as e:
            print(f"WARNING: skipping demo {ep} due to assertion failure: {e}")
            continue
    f.close()

    # convert list of lists to array for easy indexing
    subtask_indices = np.array(subtask_indices)

    return datagen_infos, subtask_indices, subtask_term_signals, subtask_term_offset_ranges


def stitching_parse_source_dataset(
    dataset_path,
    demo_keys,
    disable_tqdm=False,
    source_arms=None,
) -> Tuple[List[DatagenInfo], np.ndarray, List[str], List[Tuple[int, int]]]:
    """
    Parses a source dataset to extract info needed for data generation (DatagenInfo instances) and
    subtask indices that split each source dataset trajectory into contiguous subtask segments.

    Args:
        dataset_path (str): path to hdf5 dataset
        demo_keys (list): list of demo keys to use from dataset path
        source_arms (list or None): per-demo arm name ("left"/"right") for bimanual
            datasets where eef_pose/target_pose/gripper_action live under
            datagen_info/{arm}/ instead of datagen_info/.

    Returns:

        datagen_infos (list): list of DatagenInfo instances, one per source
            demonstration. Each instance has entries with leading dimension [T, ...],
            the length of the trajectory.

        subtask_indices (np.array): array of shape (N, S, 2) where N is the number of
                demos and S is the number of subtasks for this task. Each entry is
                a pair of integers that represents the index at which a subtask
                segment starts and where it is completed.

    """

    f = h5py.File(dataset_path, "r")

    datagen_infos = []
    subtask_indices  = []
    valid_indices = []
    for ind in tqdm(range(len(demo_keys)), disable=disable_tqdm):
        ep = demo_keys[ind]
        try:
            ep_grp = f["data/{}".format(ep)]

            # extract datagen info
            ep_datagen_info = ep_grp["datagen_info"]

            # For bimanual data, per-arm fields live under datagen_info/{arm}/
            arm = source_arms[ind] if source_arms is not None else None
            if arm is not None and arm in ep_datagen_info:
                arm_info = ep_datagen_info[arm]
            else:
                arm_info = ep_datagen_info

            ep_datagen_info_obj = DatagenInfo(
                eef_pose=arm_info["eef_pose"][:],
                object_poses={ k : ep_datagen_info["object_poses"][k][:] for k in ep_datagen_info["object_poses"] },
                subtask_term_signals={ k : ep_datagen_info["subtask_term_signals"][k][:] for k in ep_datagen_info["subtask_term_signals"] },
                target_pose=arm_info["target_pose"][:],
                gripper_action=arm_info["gripper_action"][:],
            )

            # parse subtask indices using subtask termination signals
            ep_subtask_indices = []
            prev_subtask_term_ind = 0
            for subtask_ind in range(len(ep_datagen_info_obj.subtask_term_signals)):
                # subtask_term_signal = subtask_term_signals[subtask_ind]
                if subtask_ind == len(ep_datagen_info_obj.subtask_term_signals) - 1:
                    # final subtask, finishes at end of demo
                    subtask_term_ind = ep_grp["actions"].shape[0]
                else:
                    # detect indices where 0 -> 1 transition occurs - this will be the end of the subtask
                    subtask_term_signal = f"subtask_{subtask_ind + 1}"
                    subtask_indicators = ep_datagen_info_obj.subtask_term_signals[subtask_term_signal]
                    diffs = subtask_indicators[1:] - subtask_indicators[:-1]
                    # find the first index where the subtask is completed, after the previous subtask termination index
                    end_ind = next((int(nz) + 1 for nz in diffs.nonzero()[0] if int(nz) + 1 >= prev_subtask_term_ind), None)
                    if end_ind is None:
                        raise AssertionError(f"No valid subtask termination found for {subtask_term_signal} in demo {ep}")

                    subtask_term_ind = end_ind + 1 # increment to support indexing like demo[start:end]
                ep_subtask_indices.append([prev_subtask_term_ind, subtask_term_ind])
                prev_subtask_term_ind = subtask_term_ind

            # run sanity check on subtask_term_offset_range in task spec to make sure we can never
            # get an empty subtask in the worst case when sampling subtask bounds:
            #
            #   end index of subtask i + max offset of subtask i < end index of subtask i + 1 + min offset of subtask i + 1
            #
            # assert len(ep_subtask_indices) == len(subtask_term_signals), "mismatch in length of extracted subtask info and number of subtasks"
            # for i in range(1, len(ep_subtask_indices)):
            #     prev_max_offset_range = subtask_term_offset_ranges[i - 1][1]
            #     assert ep_subtask_indices[i - 1][1] + prev_max_offset_range < ep_subtask_indices[i][1] + subtask_term_offset_ranges[i][0], \
            #         "subtask sanity check violation in demo key {} with subtask {} end ind {}, subtask {} max offset {}, subtask {} end ind {}, and subtask {} min offset {}".format(
            #             demo_keys[ind], i - 1, ep_subtask_indices[i - 1][1], i - 1, prev_max_offset_range, i, ep_subtask_indices[i][1], i, subtask_term_offset_ranges[i][0])

            # only append after all checks pass
            datagen_infos.append(ep_datagen_info_obj)
            subtask_indices.append(ep_subtask_indices)
            valid_indices.append(ind)
        except AssertionError as e:
            print(f"WARNING: skipping demo {ep} due to assertion failure: {e}")
            continue
    f.close()

    # convert list of lists to array for easy indexing
    subtask_indices = np.array(subtask_indices)

    return datagen_infos, subtask_indices, valid_indices


def write_demo_to_hdf5(
    folder,
    env,
    initial_state,
    states,
    observations,
    datagen_info,
    actions,
    abs_actions,
    prefix=None,
    src_demo_inds=None,
    src_demo_labels=None,
):
    """
    Helper function to write demonstration to an hdf5 file (robomimic format) in a folder. It will be 
    named using a timestamp.

    Args:
        folder (str): folder to write hdf5 to 
        env (BDDLBaseDomain instance): simulation environment
        initial_state (dict): dictionary corresponding to initial simulator state (see robomimic dataset structure for more information)
        states (list): list of simulator states
        observations (list): list of observation dictionaries
        datagen_info (list): list of DatagenInfo instances
        actions (np.array): actions per timestep
        src_demo_inds (list or None): if provided, list of selected source demonstration indices for each subtask
        src_demo_labels (np.array or None): same as @src_demo_inds, but repeated to have a label for each timestep of the trajectory
    """

    data_writer, data_grp, ep_data_grp, _, _ = _create_single_demo_hdf5(folder=folder, prefix=prefix)

    _write_actions_states_obs(
        ep_data_grp=ep_data_grp,
        actions=actions,
        abs_actions=abs_actions,
        states=states,
        observations=observations,
    )

    # write datagen info
    datagen_info = TensorUtils.list_of_flat_dict_to_dict_of_list([x.to_dict() for x in datagen_info])
    for k in datagen_info:
        if k in ["object_poses", "subtask_term_signals"]:
            # convert list of dict to dict of list again
            datagen_info[k] = TensorUtils.list_of_flat_dict_to_dict_of_list(datagen_info[k])
            for k2 in datagen_info[k]:
                datagen_info[k][k2] = np.array(datagen_info[k][k2])
                ep_data_grp.create_dataset("datagen_info/{}/{}".format(k, k2), data=np.array(datagen_info[k][k2]))
        else:
            ep_data_grp.create_dataset("datagen_info/{}".format(k), data=np.array(datagen_info[k]))

    # maybe write which source demonstrations generated this episode
    if src_demo_inds is not None:
        ep_data_grp.create_dataset("src_demo_inds", data=np.array(src_demo_inds))
    if src_demo_labels is not None:
        ep_data_grp.create_dataset("src_demo_labels", data=np.array(src_demo_labels))

    _write_common_episode_and_global_attrs(
        data_grp=data_grp,
        ep_data_grp=ep_data_grp,
        env=env,
        initial_state=initial_state,
        num_samples=actions.shape[0],
    )
    data_writer.close()


def merge_all_hdf5(
    folder,
    new_hdf5_path,
    delete_folder=False,
    dry_run=False,
    return_horizons=False,
    per_demo_env_args=False,
    delete_images=False
):
    """
    Helper function to take all hdf5s in @folder and merge them into a single one.
    Returns the number of hdf5s that were merged.
    """
    source_hdf5s = glob(os.path.join(folder, "*.hdf5"))

    # get all timestamps and sort files from lowest to highest
    timestamps = []
    filtered_source_hdf5s = []
    for source_hdf5_path in source_hdf5s:
        try:
            f = h5py.File(source_hdf5_path, "r")
        except Exception as e:
            print("WARNING: problem with file {}".format(source_hdf5_path))
            print("Exception: {}".format(e))
            continue
        filtered_source_hdf5s.append(source_hdf5_path)
        timestamps.append(f["data"].attrs["timestamp"])
        f.close()

    assert len(timestamps) == len(filtered_source_hdf5s)
    inds = np.argsort(timestamps)
    sorted_hdf5s = [filtered_source_hdf5s[i] for i in inds]

    if dry_run:
        if return_horizons:
            horizons = []
            for source_hdf5_path in sorted_hdf5s:
                with h5py.File(source_hdf5_path, "r") as f:
                    horizons.append(f["data"].attrs["total"])
            return len(sorted_hdf5s), horizons
        return len(sorted_hdf5s)

    # write demos in order to new file
    f_new = h5py.File(new_hdf5_path, "w")
    f_new_grp = f_new.create_group("data")

    env_meta_str = None
    all_env_meta_strs = {}
    total = 0
    if return_horizons:
        horizons = []
    for i, source_hdf5_path in enumerate(sorted_hdf5s):
        with h5py.File(source_hdf5_path, "r") as f:
            # copy this episode over under a different name
            demo_str = "demo_{}".format(i)
            f.copy("data/demo_0", f_new_grp, name=demo_str)
            if delete_images:
                # union of single-arm (agentview) and bimanual (egocentric + dual wrist) cameras
                for img_key in (
                    "obs/agentview_image",
                    "obs/egocentric_image",
                    "obs/robot0_eye_in_hand_image",
                    "obs/robot1_eye_in_hand_image",
                ):
                    if img_key in f_new_grp[demo_str]:
                        del f_new_grp[demo_str][img_key]
            if return_horizons:
                horizons.append(f["data"].attrs["total"])
            total += f["data"].attrs["total"]
            if env_meta_str is None:
                env_meta_str = f["data"].attrs["env_args"]
            all_env_meta_strs[demo_str] = json.loads(f["data"].attrs["env_args"])

    f_new["data"].attrs["total"] = total
    if per_demo_env_args:
        f_new["data"].attrs["env_args"] = json.dumps(all_env_meta_strs, indent=4)
    else:
        f_new["data"].attrs["env_args"] = env_meta_str if env_meta_str is not None else ""
    f_new.close()

    if delete_folder:
        print("removing folder at path {}".format(folder))
        shutil.rmtree(folder)

    if return_horizons:
        return len(sorted_hdf5s), horizons
    return len(sorted_hdf5s)
