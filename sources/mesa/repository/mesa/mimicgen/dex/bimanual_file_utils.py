"""
HDF5 writer for bimanual demonstrations.
"""

import json

import numpy as np

import mesa.sim.envs.bddl_utils as BDDLUtils
import mesa.utils.tensor_utils as TensorUtils
from mesa.mimicgen.dex.constants import ARM_ACTION_DIM, GRIPPER_IDX
from mesa.mimicgen.utils.file_utils import (
    _create_single_demo_hdf5,
    _write_actions_states_obs,
    _write_common_episode_and_global_attrs,
)


def _write_merged_group(grp, path_prefix, list_of_dicts):
    """Merge a list of flat dicts and write each key as a dataset under path_prefix."""
    merged = TensorUtils.list_of_flat_dict_to_dict_of_list(list_of_dicts)
    for k, v in merged.items():
        grp.create_dataset(f"{path_prefix}/{k}", data=np.array(v))


def write_bimanual_demo_to_hdf5(
    folder,
    env,
    initial_state,
    states,
    observations,
    datagen_info,
    actions,
    abs_actions,
    actions_joint_pos=None,
    prefix=None,
):
    """
    Write a bimanual demonstration to an HDF5 file.

    Args:
        folder (str): output folder
        env: simulation environment
        initial_state (dict): initial simulator state
        states (list): simulator states per timestep
        observations (list or None): observation dicts per timestep
        datagen_info (list): list of BimanualDatagenInfo instances
        actions (np.array): (T, 14) actions
        abs_actions (np.array): (T, 14) absolute actions
        actions_joint_pos (np.array or None): (T, 14) joint position actions
        prefix (str or None): filename prefix
    """
    # Inactive-arm gripper fix: a delta-mode no-op emits 0 on the gripper dim,
    # which decodes to "hold"; rewrite to -1 (open) so the absolute action
    # reflects the idle arm's physically open gripper.
    l_grip = GRIPPER_IDX
    r_grip = ARM_ACTION_DIM + GRIPPER_IDX
    abs_actions = np.array(abs_actions)
    abs_actions[:, l_grip] = np.where(abs_actions[:, l_grip] == 0, -1.0, abs_actions[:, l_grip])
    abs_actions[:, r_grip] = np.where(abs_actions[:, r_grip] == 0, -1.0, abs_actions[:, r_grip])

    data_writer, data_grp, ep_grp, _, _ = _create_single_demo_hdf5(folder=folder, prefix=prefix)
    _write_actions_states_obs(
        ep_data_grp=ep_grp,
        actions=actions,
        abs_actions=abs_actions,
        states=states,
        observations=observations,
    )

    if actions_joint_pos is not None:
        ep_grp.create_dataset("actions_joint_pos", data=np.array(actions_joint_pos))

    dicts = [x.to_dict() for x in datagen_info]

    for arm in ("left", "right"):
        _write_merged_group(ep_grp, f"datagen_info/{arm}", [d[arm] for d in dicts])

    shared_object_poses = [d.get("object_poses") for d in dicts]
    if shared_object_poses[0] is not None:
        _write_merged_group(ep_grp, "datagen_info/object_poses", shared_object_poses)

    shared_signals = [d.get("subtask_term_signals") for d in dicts]
    if shared_signals[0] is not None:
        _write_merged_group(ep_grp, "datagen_info/subtask_term_signals", shared_signals)

    # Replicate the datagen_info attrs that collect_data writes so downstream
    # parse_dataset.py finds the same schema on MG-generated demos.
    parsed_problem = getattr(env, "parsed_problem", None)
    if parsed_problem is not None:
        subtask_list = parsed_problem["demonstration_states"]
        subtasks = BDDLUtils.get_search_spec_list(
            subtask_list=subtask_list,
            objects_dict=parsed_problem["objects"],
            regions_dict=parsed_problem["regions"],
            fixtures_dict=parsed_problem["fixtures"],
        )
        datagen_grp = ep_grp["datagen_info"]
        datagen_grp.attrs["subtasks"] = json.dumps(subtasks)
        datagen_grp.attrs["demonstration_states"] = json.dumps(subtask_list)
        datagen_grp.attrs["env_interface_name"] = "MESAInterface"
        datagen_grp.attrs["env_interface_type"] = "mesa"

    _write_common_episode_and_global_attrs(
        data_grp=data_grp,
        ep_data_grp=ep_grp,
        env=env,
        initial_state=initial_state,
        num_samples=actions.shape[0],
    )
    data_writer.close()
