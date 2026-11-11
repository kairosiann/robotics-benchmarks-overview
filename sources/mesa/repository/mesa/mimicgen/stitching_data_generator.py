"""
stitching data generator.

This generator mirrors the original MimicGen data generator in how it stitches
subtask trajectories, but differs by selecting a relevant subset of source
demonstrations per subtask. The subset is determined by a (stubbed) search
function that will return a list of (hdf5_path, demo_key) pairs derived from a
folder containing a demo_lookup.json.
"""
import os
from typing import List

import numpy as np
from scipy.spatial.transform import Rotation as R

import mesa.mimicgen.utils.file_utils as MG_FileUtils
import mesa.mimicgen.utils.pose_utils as PoseUtils
import mesa.mimicgen.utils.trajectory_optimization as TrajOpt
import mesa.sim.envs.objects.utils as object_utils
from mesa.mimicgen.configs.task_spec import MG_TaskSpec
from mesa.mimicgen.data_generator import DataGenerator
from mesa.mimicgen.datagen.datagen_info import DatagenInfo
from mesa.mimicgen.datagen.selection_strategy import (
    MG_SelectionStrategy,
    make_selection_strategy,
)
from mesa.mimicgen.datagen.waypoint import (
    WaypointSequence,
    WaypointTrajectory,
)
from mesa.mimicgen.env_interfaces.base import MG_EnvInterface
from mesa.sim.envs.bddl_base_domain import BDDLBaseDomain


def get_rotation_correction_matrix(rotation_axis: str) -> np.ndarray:
    """
    Calculates the 3x3 rotation matrix (R_corr) that transforms rotations 
    from the canonical Z-axis to the specified object's rotation axis.

    Args:
        rotation_axis: The object's actual 'up' axis ("x", "y", or "z").

    Returns:
        A 3x3 numpy array representing the correction rotation matrix.
    """
    # The canonical frame where rotations are about the Z-axis (0, 0, 1)

    if rotation_axis == "z":
        # Case 1: Canonical Z-up is already the object's Z-up. No rotation needed.
        # R_corr maps z to z.
        R_corr = np.identity(3)
        
    elif rotation_axis == "x":
        # Case 2: Object's up axis is X. R_corr must map z to x.
        # This is a rotation of -90 degrees about the Y-axis.
        # R = R_y(-90 degrees)
        R_corr = R.from_euler('y', -90, degrees=True).as_matrix()
        
    elif rotation_axis == "y":
        # Case 3: Object's up axis is Y. R_corr must map z to y.
        # This is a rotation of +90 degrees about the X-axis.
        # R = R_x(+90 degrees)
        R_corr = R.from_euler('x', 90, degrees=True).as_matrix()
        
    else:
        raise ValueError(f"Invalid rotation_axis: {rotation_axis}. Must be 'x', 'y', or 'z'.")

    return R_corr


def _search_and_walk(tree, keys):
    """
    Input is a tree defined as a python dictionary and a list of keys. 
    
    It should be the case that every leaf node has depth equal to len(keys) + 1,
    so each key corresponds to a depth level below the root.

    For each depth, if a node with a name matching the corresponding key exists, 
    we will only return outputs from its subtree. Otherwise, we recurse on all nodes at
    that depth and return the union of all outputs.

    Args:
        tree (dict): dictionary to search
        keys (list): list of keys to search for

    Returns:
        pairs: list of (hdf5_path, demo_key) pairs
    """
    if len(keys) == 0:
        # assert type(tree) == list, "leaf node should be a list"
        # return tree
        if isinstance(tree, list):
            return tree
        else:
            out = []
            for k, v in tree.items():
                out.extend(_search_and_walk(v, keys))
            return out

    key, rest = keys[0], keys[1:]

    if key not in tree:
        pairs = []
        for k, v in tree.items():
            pairs.extend(_search_and_walk(v, rest))
        return pairs
    else:
        return _search_and_walk(tree[key], rest)


class StitchingDataGenerator(DataGenerator):
    """
    This data generator takes in a full, diverse dataset and generates new 
    trajectories by selecting source demonstrations from the dataset per subtask.
    """
    def __init__(
        self,
        task_spec,
        dataset_path,
        demo_keys=None,
    ):
        """
        Args:
            task_spec (MG_TaskSpec instance): task specification that will be
                used to generate data
            dataset_path (str): path to hdf5 dataset to use for generation
            demo_keys (list of str): list of demonstration keys to use
                in file. If not provided, all demonstration keys will be
                used.
        """
        assert isinstance(task_spec, MG_TaskSpec)
        self.task_spec = task_spec
        # In stitching mode, dataset_path points to a folder containing demo_lookup.json
        self.dataset_path = dataset_path  # folder path

        # sanity check on task spec offset ranges - final subtask should not have any offset randomization
        assert self.task_spec[-1]["subtask_term_offset_range"][0] == 0
        assert self.task_spec[-1]["subtask_term_offset_range"][1] == 0

        # Load demo lookup from folder (used by search function); tolerate missing file for now
        self.demo_lookup_path = os.path.join(self.dataset_path, "demo_lookup.json")
        self.demo_lookup = None
        if os.path.exists(self.demo_lookup_path):
            try:
                with open(self.demo_lookup_path, "r") as f:
                    import json
                    self.demo_lookup = json.load(f)
            except Exception as e:
                print(f"WARNING: failed to load demo_lookup.json at {self.demo_lookup_path}: {e}")
                self.demo_lookup = None

    def search_relevant_demos(self, subtask_spec):
        """
        Stub: search for relevant demos for a given subtask.

        For now, returns all pairs from demo_lookup.json. Replace this with logic
        that uses subtask_spec to filter.
        """
        search_spec = subtask_spec["search_spec"]
        predicate = search_spec[0]

        if predicate in ("grasp", "grasp_left", "grasp_right"):
            obj_name = search_spec[1]
            shape_category = object_utils.get_shape_category(obj_name)
            obj_category = object_utils.get_category(obj_name)
            keys = ["grasp", shape_category, obj_category, obj_name]
            backup_keys = ["grasp", shape_category, obj_category]
        elif predicate == "in":
            pick, dest = search_spec[1:]
            dest_obj, dest_region = dest
            pick_shape_category = object_utils.get_shape_category(pick)
            dest_insertion_category = object_utils.get_insertion_category(dest_obj)
            pick_obj_category = object_utils.get_category(pick)
            dest_obj_category = object_utils.get_category(dest_obj)
            keys = [predicate, dest_obj_category, dest_insertion_category, pick_shape_category, pick_obj_category, dest_region]
            backup_keys = [predicate, dest_obj_category, dest_insertion_category, pick_shape_category, pick_obj_category]
        elif predicate == "on":
            dest = search_spec[-1]
            dest_obj_category = object_utils.get_category(dest)
            keys = [predicate, dest_obj_category]
            backup_keys = [predicate, dest_obj_category]
        elif predicate == "open":
            dest = search_spec[-1]
            if isinstance(dest, list) or isinstance(dest, tuple):
                dest_obj, dest_region = dest
            else:
                dest_obj = dest
                dest_region = None
            dest_obj_category = object_utils.get_category(dest_obj)
            keys = [predicate, dest_obj_category, dest_region]
            backup_keys = [predicate, dest_obj_category]
        elif predicate == "close":
            dest = search_spec[-1]
            if isinstance(dest, tuple):
                dest_obj, dest_region = dest
            else:
                dest_obj = dest
                dest_region = None
            dest_obj_category = object_utils.get_category(dest_obj)
            keys = [predicate, dest_obj_category, dest_region]
            backup_keys = [predicate, dest_obj_category, dest_region]
        elif predicate == "stack":
            bottom, top = search_spec[1:]
            assert bottom == top, "Bottom and top of stack must be the same object"
            bottom_obj_category = object_utils.get_category(bottom)
            keys = [predicate, bottom_obj_category, bottom]
            backup_keys = [predicate, bottom_obj_category]
        elif predicate == "turnon":
            obj = search_spec[-1]
            obj_category = object_utils.get_category(obj)
            keys = [predicate, obj_category]
            backup_keys = [predicate, obj_category]
        elif predicate == "turnoff":
            obj = search_spec[-1]
            obj_category = object_utils.get_category(obj)
            keys = [predicate, obj_category]
            backup_keys = [predicate, obj_category]
        else:
            raise NotImplementedError(f"Predicate {predicate} not implemented")

        leaves = _search_and_walk(self.demo_lookup, keys)
        backup_leaves = _search_and_walk(self.demo_lookup, backup_keys)
        # Flatten list of lists in one line using list comprehension
        # return [pair for leaf in leaves for pair in leaf]
        return leaves, backup_leaves

    def __repr__(self):
        """
        Pretty print this object.
        """
        msg = str(self.__class__.__name__)
        msg += " (\n\tdataset_path={} (folder)\n)".format(
            self.dataset_path,
        )
        return msg

    # randomize_subtask_boundaries and select_source_demo are inherited from DataGenerator
    def randomize_subtask_boundaries(self, src_subtask_indices, cur_subtask_ind):
        """
        Apply random offsets to sample subtask boundaries according to the task spec.
        Recall that each demonstration is segmented into a set of subtask segments, and the
        end index of each subtask can have a random offset.
        """

        # initial subtask start and end indices - shape (N, S, 2)
        src_subtask_indices = np.array(src_subtask_indices)

        # for each subtask (except last one), sample all end offsets at once for each demonstration
        # add them to subtask end indices, and then set them as the start indices of next subtask too
        end_offsets = np.random.randint(
            low=self.task_spec[cur_subtask_ind]["subtask_term_offset_range"][0],
            high=self.task_spec[cur_subtask_ind]["subtask_term_offset_range"][1] + 1,
            size=src_subtask_indices.shape[0]
        )
        src_subtask_indices[:, 0, 1] = src_subtask_indices[:, 0, 1] + end_offsets

        # ensure non-empty subtasks
        assert np.all((src_subtask_indices[:, :, 1] - src_subtask_indices[:, :, 0]) > 0), "got empty subtasks!"

        # ensure subtask indices increase (both starts and ends)
        assert np.all((src_subtask_indices[:, 1:, :] - src_subtask_indices[:, :-1, :]) > 0), "subtask indices do not strictly increase"

        # ensure subtasks are in order
        subtask_inds_flat = src_subtask_indices.reshape(src_subtask_indices.shape[0], -1)
        assert np.all((subtask_inds_flat[:, 1:] - subtask_inds_flat[:, :-1]) >= 0), "subtask indices not in order"

        return src_subtask_indices, end_offsets


    def select_source_demo(
        self,
        relevant_subtasks,
        cur_eef_pose,
        cur_object_pose,
        src_update_fn,
        # src_subtask_inds,
        subtask_object_name,
        selection_strategy_name,
        cur_subtask_ind,
        selection_strategy_kwargs=None,
        ignore_roll_pitch=False,
        ignore_yaw=False,
    ):
        # group by hdf5 path
        from collections import defaultdict
        grouped = defaultdict(lambda: defaultdict(list))
        for ind, subtask in enumerate(relevant_subtasks):
            h5_abs = os.path.normpath(os.path.join(self.dataset_path, subtask['hdf5_path']))
            grouped[h5_abs]['demo_keys'].append(subtask['demo_key'])
            grouped[h5_abs]['object_refs'].append(subtask['object_ref'])
            grouped[h5_abs]['other_object_refs'].append(subtask['other_object_ref'])
            grouped[h5_abs]['subtask_indices'].append(subtask['subtask_index'])
            grouped[h5_abs]['indices'].append(ind)
            grouped[h5_abs]['source_arms'].append(subtask.get('source_arm'))

        src_subtask_datagen_infos: List[DatagenInfo] = []
        all_object_refs: List[str] = []
        all_other_object_refs: List[str] = []
        all_indices: List[int] = []
        all_offsets: List[int] = []
        all_paths: List[str] = []
        for h5_abs, data in grouped.items():
            demo_keys = data['demo_keys']
            object_refs = data['object_refs']
            other_object_refs = data['other_object_refs']
            subtask_indices = np.array(data['subtask_indices'])
            source_arms = data['source_arms']
            # Pass source_arms if any are non-None (bimanual data)
            arms_arg = source_arms if any(a is not None for a in source_arms) else None
            infos, subtask_start_end_indices, valid_indices = MG_FileUtils.stitching_parse_source_dataset(
                dataset_path=h5_abs,
                demo_keys=demo_keys,
                disable_tqdm=True,
                source_arms=arms_arg,
            )
            if len(valid_indices) == 0:
                # All demos in this shard were filtered out (e.g. invalid subtask term signals).
                continue
            subtask_indices = subtask_indices[valid_indices]
            subtask_start_end_indices = np.array(subtask_start_end_indices)
            subtask_start_end_indices = subtask_start_end_indices[np.arange(len(subtask_indices)), subtask_indices][:, None]
            subtask_start_end_indices, offsets = self.randomize_subtask_boundaries(subtask_start_end_indices, cur_subtask_ind)
            subtask_start_end_indices = subtask_start_end_indices.squeeze(1)
            filtered_demo_keys = [demo_keys[i] for i in valid_indices]
            filtered_indices = [data['indices'][i] for i in valid_indices]
            object_refs = [object_refs[i] for i in valid_indices]
            other_object_refs = [other_object_refs[i] for i in valid_indices]


            for i in range(len(infos)):
                info = infos[i]
                start_end_index = subtask_start_end_indices[i]
                object_ref = object_refs[i]
                other_object_ref = other_object_refs[i]
                offset = offsets[i]
                start_index = start_end_index[0]
                end_index = start_end_index[1]
                object_poses = { object_ref : info.object_poses[object_ref][start_index : end_index] }
                if other_object_ref is not None:
                    object_poses[other_object_ref] = info.object_poses[other_object_ref][start_index : end_index]
                src_subtask_datagen_infos.append(DatagenInfo(
                    eef_pose=info.eef_pose[start_index : end_index],
                    object_poses=object_poses,
                    subtask_term_signals=None,
                    target_pose=info.target_pose[start_index : end_index],
                    gripper_action=info.gripper_action[start_index : end_index],
                    offset=offset,
                ))
                all_object_refs.append(object_ref)
                all_other_object_refs.append(other_object_ref)
                all_indices.append(filtered_indices[i])
                all_offsets.append(offset)
                all_paths.append((h5_abs, filtered_demo_keys[i]))

        if len(src_subtask_datagen_infos) == 0:
            raise AssertionError(
                f"No valid source subtasks available for selection at subtask {cur_subtask_ind}. "
                "All candidate demos were filtered out due to invalid subtask term signals."
            )
        # make selection strategy object
        selection_strategy_obj: MG_SelectionStrategy = make_selection_strategy(selection_strategy_name)

        # run selection
        if selection_strategy_kwargs is None:
            selection_strategy_kwargs = dict()

        if ignore_roll_pitch:
            cur_eef_pose = PoseUtils.remove_roll_pitch(cur_eef_pose)
            cur_object_pose = PoseUtils.remove_roll_pitch(cur_object_pose)
        if ignore_yaw:
            cur_eef_pose = PoseUtils.remove_yaw(cur_eef_pose)
            cur_object_pose = PoseUtils.remove_yaw(cur_object_pose)

        selected_src_demo_ind = selection_strategy_obj.select_source_demo(
            eef_pose=cur_eef_pose,
            object_pose=cur_object_pose,
            src_subtask_datagen_infos=src_subtask_datagen_infos,
            object_refs=all_object_refs,
            src_update_fn=src_update_fn,
            **selection_strategy_kwargs,
        )

        # get subtask segment, consisting of the sequence of robot eef poses, target poses, gripper actions
        selected_datagen_info: DatagenInfo = src_subtask_datagen_infos[selected_src_demo_ind]
        selected_object_ref: str = all_object_refs[selected_src_demo_ind]
        selected_other_object_ref: str = all_other_object_refs[selected_src_demo_ind]
        src_subtask_eef_poses = selected_datagen_info.eef_pose
        src_subtask_target_poses = selected_datagen_info.target_pose
        src_subtask_gripper_actions = selected_datagen_info.gripper_action
        src_subtask_object_pose = selected_datagen_info.object_poses[selected_object_ref]
        selected_index = all_indices[selected_src_demo_ind]
        selected_offset = all_offsets[selected_src_demo_ind]
        if selected_other_object_ref is not None:
            src_subtask_other_object_pose = selected_datagen_info.object_poses[selected_other_object_ref]
        else:
            src_subtask_other_object_pose = None

        out = {
            "src_subtask_eef_poses": src_subtask_eef_poses,
            "src_subtask_target_poses": src_subtask_target_poses,
            "src_subtask_gripper_actions": src_subtask_gripper_actions,
            "src_subtask_object_pose": src_subtask_object_pose,
            "src_subtask_other_object_pose": src_subtask_other_object_pose,
            "selected_index": selected_index,
            "selected_offset": selected_offset,
        }

        return out

    def _build_single_subtask_trajectory(
        self,
        subtask_ind,
        cur_eef_pose,
        cur_object_pose,
        initial_state,
        is_first_subtask,
        transform_first_robot_pose,
        interpolate_from_last_target_pose,
        prev_executed_traj,
        subtask_is_last,
        noop_tail_steps=30,
        print_num_candidates=False,
    ):
        """
        Build a subtask trajectory from current state and selected source segment.
        """
        # Load the relevant subset for this subtask
        relevant_subtasks, backup_relevant_subtasks = self.search_relevant_demos(self.task_spec[subtask_ind])

        # First attempt prefers strict instance-level matches; second attempt
        # (initial_state is not None) broadens to category-level backup matches.
        # If the strict set is empty (e.g. the variant references an object
        # instance not collected in source), fall back to backup immediately
        # rather than crashing in select_source_demo.
        if initial_state is None and len(relevant_subtasks) > 0:
            subtasks_to_use = relevant_subtasks
        else:
            subtasks_to_use = backup_relevant_subtasks

        def src_update_fn(src_eef_poses, cur_eef_pose, cur_object_pose, offset):
            if self.task_spec[subtask_ind]["optimize_start"]:
                src_eef_poses = TrajOpt.optimize_trajectory_for_pos(
                    src_eef_poses,
                    cur_eef_pose[:3, 3],
                    cur_object_pose,
                    offset=offset,
                    **self.task_spec[subtask_ind]["optimize_start_kwargs"]["pos"],
                )
                src_eef_poses, _ = TrajOpt.optimize_trajectory_for_rot(
                    src_eef_poses,
                    cur_eef_pose,
                    offset=offset,
                    **self.task_spec[subtask_ind]["optimize_start_kwargs"]["rot"],
                )
            return src_eef_poses

        if print_num_candidates:
            print(len(subtasks_to_use))

        subtask_object_name = self.task_spec[subtask_ind]["object_ref"]
        source_demo_info = self.select_source_demo(
            relevant_subtasks=subtasks_to_use,
            cur_eef_pose=cur_eef_pose,
            cur_object_pose=cur_object_pose,
            subtask_object_name=subtask_object_name,
            src_update_fn=src_update_fn,
            cur_subtask_ind=subtask_ind,
            selection_strategy_name=self.task_spec[subtask_ind]["selection_strategy"],
            selection_strategy_kwargs=self.task_spec[subtask_ind]["selection_strategy_kwargs"],
            ignore_roll_pitch=self.task_spec[subtask_ind]["ignore_roll_pitch"],
            ignore_yaw=self.task_spec[subtask_ind]["ignore_yaw"],
        )

        src_subtask_eef_poses = source_demo_info["src_subtask_eef_poses"]
        src_subtask_target_poses = source_demo_info["src_subtask_target_poses"]
        src_subtask_gripper_actions = source_demo_info["src_subtask_gripper_actions"]
        src_subtask_object_poses = source_demo_info["src_subtask_object_pose"]
        selected_offset = source_demo_info["selected_offset"]

        # use the middle to avoid issues where the pose is wrong because it isn't stable at the beginning
        src_subtask_object_pose = src_subtask_object_poses[len(src_subtask_object_poses) // 6]

        rotation_axis = self.task_spec[subtask_ind]["rotation_axis"]
        R_corr = get_rotation_correction_matrix(rotation_axis)
        R_corr_inv = np.linalg.inv(R_corr)

        # Transform the object pose so that rotation about the vertical axis is always
        # about the z-axis
        cur_object_pose[:3,:3] = R_corr_inv @ cur_object_pose[:3,:3] @ R_corr
        src_subtask_object_pose[:3,:3] = R_corr_inv @ src_subtask_object_pose[:3,:3] @ R_corr

        if is_first_subtask or transform_first_robot_pose:
            # Source segment consists of first robot eef pose and the target poses. This ensures that
            # we will interpolate to the first robot eef pose in this source segment, instead of the
            # first robot target pose.
            src_eef_poses = np.concatenate([src_subtask_eef_poses[0:1], src_subtask_target_poses], axis=0)
        else:
            # Source segment consists of just the target poses.
            src_eef_poses = np.array(src_subtask_target_poses)

        # account for extra timestep added to @src_eef_poses
        src_subtask_gripper_actions = np.concatenate([src_subtask_gripper_actions[0:1], src_subtask_gripper_actions], axis=0)

        if self.task_spec[subtask_ind]["ignore_roll_pitch"]:
            cur_object_pose = PoseUtils.remove_roll_pitch(cur_object_pose)
            src_subtask_object_pose = PoseUtils.remove_roll_pitch(src_subtask_object_pose)

        if self.task_spec[subtask_ind]["ignore_yaw"]:
            cur_object_pose = PoseUtils.remove_yaw(cur_object_pose)
            src_subtask_object_pose = PoseUtils.remove_yaw(src_subtask_object_pose)

        # Transform source demonstration segment using relevant object pose.
        if subtask_object_name is not None:
            transformed_eef_poses = PoseUtils.transform_source_data_segment_using_object_pose(
                obj_pose=cur_object_pose,
                src_eef_poses=src_eef_poses,
                src_obj_pose=src_subtask_object_pose,
            )
        else:
            # skip transformation if no reference object is provided
            transformed_eef_poses = src_eef_poses

        # This transforms the trajectory so that the start is as near as possible to the
        # current robot eef pose, and then slerps the poses so that the match at the end
        if self.task_spec[subtask_ind]["optimize_start"]:
            orig = transformed_eef_poses
            transformed_eef_poses = TrajOpt.optimize_trajectory_for_pos(
                transformed_eef_poses,
                cur_eef_pose[:3, 3],
                cur_object_pose,
                offset=selected_offset,
                do_breakpoint=True,
                **self.task_spec[subtask_ind]["optimize_start_kwargs"]["pos"],
            )

            # In case we chop off the start of the trajectory, use the start gripper actions of the original trajectory
            # instead of the ones in the middle of the trajectory
            if len(orig) != len(transformed_eef_poses):
                diff = len(orig) - len(transformed_eef_poses)
                orig_start_gripper_actions = src_subtask_gripper_actions[0:diff]
                src_subtask_gripper_actions = src_subtask_gripper_actions[diff:]
                src_subtask_gripper_actions[:diff] = orig_start_gripper_actions

            transformed_eef_poses, _ = TrajOpt.optimize_trajectory_for_rot(
                transformed_eef_poses,
                cur_eef_pose,
                offset=selected_offset,
                do_breakpoint=True,
                **self.task_spec[subtask_ind]["optimize_start_kwargs"]["rot"],
            )

        # We will construct a WaypointTrajectory instance to keep track of robot control targets
        # that will be executed and then execute it.
        traj_to_execute = WaypointTrajectory()

        if interpolate_from_last_target_pose and (not is_first_subtask):
            # Interpolation segment will start from last target pose (which may not have been achieved).
            assert prev_executed_traj is not None
            last_waypoint = prev_executed_traj.last_waypoint
            init_sequence = WaypointSequence(sequence=[last_waypoint])
        else:
            # Interpolation segment will start from current robot eef pose.
            init_sequence = WaypointSequence.from_poses(
                poses=cur_eef_pose[None],
                gripper_actions=src_subtask_gripper_actions[0:1],
                action_noise=self.task_spec[subtask_ind]["action_noise"],
            )
        traj_to_execute.add_waypoint_sequence(init_sequence)

        # Construct trajectory for the transformed segment.
        transformed_seq = WaypointSequence.from_poses(
            poses=transformed_eef_poses,
            gripper_actions=src_subtask_gripper_actions,
            action_noise=self.task_spec[subtask_ind]["action_noise"],
        )
        transformed_traj = WaypointTrajectory()
        transformed_traj.add_waypoint_sequence(transformed_seq)

        # Merge this trajectory into our trajectory using linear interpolation.
        # Interpolation will happen from the initial pose (@init_sequence) to the first element of @transformed_seq.
        traj_to_execute.merge(
            transformed_traj,
            num_steps_interp=self.task_spec[subtask_ind]["num_interpolation_steps"],
            num_steps_fixed=self.task_spec[subtask_ind]["num_fixed_steps"],
            action_noise=(float(self.task_spec[subtask_ind]["apply_noise_during_interpolation"]) * self.task_spec[subtask_ind]["action_noise"]),
        )

        if subtask_is_last:
            noops_actions = WaypointSequence([traj_to_execute.last_waypoint] * noop_tail_steps)
            traj_to_execute.add_waypoint_sequence(noops_actions)

        # We initialized @traj_to_execute with a pose to allow @merge to handle linear interpolation
        # for us. However, we can safely discard that first waypoint now, and just start by executing
        # the rest of the trajectory (interpolation segment and transformed subtask segment).
        traj_to_execute.pop_first()
        return traj_to_execute

    def generate(
        self,
        env: BDDLBaseDomain,
        env_interface: MG_EnvInterface,
        select_src_per_subtask=False,
        transform_first_robot_pose=False,
        interpolate_from_last_target_pose=True,
        render=False,
        video_writer=None,
        video_skip=5,
        camera_names=None,
        pause_subtask=False,
        init_noops=0,
        initial_state=None,
    ):
        """
        Attempt to generate a new demonstration.

        Args:
            env (BDDLBaseDomain instance): environment to use for data collection
            
            env_interface (MG_EnvInterface instance): environment interface for some data generation operations

            select_src_per_subtask (bool): if True, select a different source demonstration for each subtask 
                during data generation, else keep the same one for the entire episode

            transform_first_robot_pose (bool): if True, each subtask segment will consist of the first
                robot pose and the target poses instead of just the target poses. Can sometimes help
                improve data generation quality as the interpolation segment will interpolate to where 
                the robot started in the source segment instead of the first target pose. Note that the
                first subtask segment of each episode will always include the first robot pose, regardless
                of this argument.

            interpolate_from_last_target_pose (bool): if True, each interpolation segment will start from
                the last target pose in the previous subtask segment, instead of the current robot pose. Can
                sometimes improve data generation quality.

            render (bool): if True, render on-screen

            video_writer (imageio writer): video writer

            video_skip (int): determines rate at which environment frames are written to video

            camera_names (list): determines which camera(s) are used for rendering. Pass more than
                one to output a video with multiple camera views concatenated horizontally.

            pause_subtask (bool): if True, pause after every subtask during generation, for
                debugging.

            init_noops (int): number of noops to execute at the beginning of the trajectory

        Returns:
            results (dict): dictionary with the following items:
                initial_state (dict): initial simulator state for the executed trajectory
                states (list): simulator state at each timestep
                observations (list): observation dictionary at each timestep
                datagen_infos (list): datagen_info at each timestep
                actions (np.array): action executed at each timestep
                success (bool): whether the trajectory successfully solved the task or not
                src_demo_inds (list): list of selected source demonstration indices for each subtask
                src_demo_labels (np.array): same as @src_demo_inds, but repeated to have a label for each timestep of the trajectory
        """
        assert select_src_per_subtask, "select_src_per_subtask must be True for stitching data generation"

        # sample new task instance
        if initial_state is None:
            env.stable_reset()
        else:
            env.reset_to(initial_state)

        new_initial_state = env.get_state()
        # some state variables used during generation
        # selected_src_demo_ind = None
        prev_executed_traj = None

        # save generated data in these variables
        generated_states = []
        generated_obs = []
        generated_datagen_infos = []
        generated_actions = []
        generated_abs_actions = []
        any_joint_limit = False

        for subtask_ind in range(len(self.task_spec)):

            # some things only happen on first subtask
            is_first_subtask = (subtask_ind == 0)

            # get datagen info in current environment to get required info for selection (e.g. eef pose, object pose)
            cur_datagen_info = env_interface.get_datagen_info()

            # name of object for this subtask
            subtask_object_name = self.task_spec[subtask_ind]["object_ref"]

            # corresponding current object pose
            cur_object_pose = cur_datagen_info.object_poses[subtask_object_name] if (subtask_object_name is not None) else None

            traj_to_execute = self._build_single_subtask_trajectory(
                subtask_ind=subtask_ind,
                cur_eef_pose=cur_datagen_info.eef_pose,
                cur_object_pose=cur_object_pose,
                initial_state=initial_state,
                is_first_subtask=is_first_subtask,
                transform_first_robot_pose=transform_first_robot_pose,
                interpolate_from_last_target_pose=interpolate_from_last_target_pose,
                prev_executed_traj=prev_executed_traj,
                subtask_is_last=(subtask_ind == len(self.task_spec) - 1),
                noop_tail_steps=30,
                print_num_candidates=True,
            )

            # Execute the trajectory and collect data.
            exec_results = traj_to_execute.execute(
                env=env,
                env_interface=env_interface,
                render=render,
                video_writer=video_writer,
                video_skip=video_skip,
                camera_names=camera_names,
                subtask_ind=subtask_ind,
            )

            # check that trajectory is non-empty
            if len(exec_results["states"]) > 0:
                generated_states += exec_results["states"]
                generated_obs += exec_results["observations"]
                generated_datagen_infos += exec_results["datagen_infos"]
                generated_actions.append(exec_results["actions"])
                generated_abs_actions.append(exec_results["abs_actions"])
                any_joint_limit = any_joint_limit or np.any(exec_results['joint_limit_hit'])

            # remember last trajectory
            prev_executed_traj = traj_to_execute

            if pause_subtask:
                input("Pausing after subtask {} execution. Press any key to continue...".format(subtask_ind))

        # merge numpy arrays
        if len(generated_actions) > 0:
            generated_actions = np.concatenate(generated_actions, axis=0)
            generated_abs_actions = np.concatenate(generated_abs_actions, axis=0)

        results = dict(
            initial_state=new_initial_state,
            states=generated_states,
            observations=generated_obs,
            datagen_infos=generated_datagen_infos,
            actions=generated_actions,
            abs_actions=generated_abs_actions,
            success = exec_results["success"], # we use the success of the last subtask. This is to avoid si
            joint_limit_hit = any_joint_limit,
        )
        return results
