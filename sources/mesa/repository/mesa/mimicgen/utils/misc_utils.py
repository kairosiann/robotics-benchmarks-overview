# Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the NVIDIA Source Code License [see LICENSE for details].

"""
A collection of miscellaneous utilities.
"""
import time


def get_controller(env):
    return env.robots[0].composite_controller.part_controllers['right']



def deep_update(d, u):
    """
    Recursively update a mapping.
    """
    import collections
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def get_important_stats(
    new_dataset_folder_path,
    num_success,
    num_failures,
    num_attempts,
    num_problematic,
    start_time=None,
    ep_length_stats=None,
):
    """
    Return a summary of important stats to write to json.

    Args:
        new_dataset_folder_path (str): path to folder that will contain generated dataset
        num_success (int): number of successful trajectories generated
        num_failures (int): number of failed trajectories
        num_attempts (int): number of total attempts
        num_problematic (int): number of problematic trajectories that failed due
            to a specific exception that was caught
        start_time (float or None): starting time for this run from time.time()
        ep_length_stats (dict or None): if provided, should have entries that summarize
            the episode length statistics over the successfully generated trajectories

    Returns:
        important_stats (dict): dictionary with useful summary of statistics
    """
    important_stats = dict(
        generation_path=new_dataset_folder_path,
        success_rate=((100. * num_success) / num_attempts),
        failure_rate=((100. * num_failures) / num_attempts),
        num_success=num_success,
        num_failures=num_failures,
        num_attempts=num_attempts,
        num_problematic=num_problematic,
    )
    if (ep_length_stats is not None):
        important_stats.update(ep_length_stats)
    if start_time is not None:
        # add in time taken
        important_stats["time spent (hrs)"] = "{:.2f}".format((time.time() - start_time) / 3600.)
    return important_stats