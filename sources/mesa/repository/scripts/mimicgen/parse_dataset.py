"""
Script to parse a dataset directory and create a lookup dictionary for demos by subtask predicates.

This script walks through a directory, analyzes every hdf5 file, and creates a dictionary
that maps predicates to demo paths for efficient lookup during data generation.

Example usage:
    python scripts/parse_dataset.py \
        --input_dir /path/to/dataset/directory
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import numpy as np
import tyro

import mesa.sim.envs.objects.utils as object_utils


@dataclass
class ParseDatasetArgs:
    """Arguments for the parse_dataset script.
    
    This script parses a dataset directory and creates a lookup dictionary for demos.
    """
    input_dir: str
    """Path to input directory containing hdf5 files to analyze."""
    
    output_filename: str = "demo_lookup.json"
    """Name of the output JSON file to save the lookup dictionary."""


def has_datagen_info(hdf5_file: h5py.File) -> bool:
    """
    Check if the hdf5 file contains demos with datagen_info.
    
    Args:
        hdf5_file: Open h5py file handle
        
    Returns:
        bool: True if any demo has datagen_info, False otherwise
    """
    if "data" not in hdf5_file:
        return False
        
    for demo_key in hdf5_file["data"].keys():
        demo_group = hdf5_file["data"][demo_key]
        if "datagen_info" in demo_group:
            return True
    return False


def extract_subtasks_from_demo(demo_group: h5py.Group) -> Dict[str, List[str]]:
    """
    Extract subtask information from a demo's datagen_info attributes.
    
    Args:
        demo_group: HDF5 group containing demo data
        
    Returns:
        dict: Dictionary mapping subtask names to lists of predicates/objects
    """
    if "datagen_info" not in demo_group:
        return {}
        
    datagen_info = demo_group["datagen_info"]
    if "subtasks" not in datagen_info.attrs:
        return {}
        
    subtasks_json = datagen_info.attrs["subtasks"]
    return json.loads(subtasks_json)


def extract_demonstration_states_from_demo(demo_group: h5py.Group) -> List[str]:
    """
    Extract demonstration states from a demo's datagen_info attributes.
    
    Args:
        demo_group: HDF5 group containing demo data
        
    Returns:
        list: List of demonstration states
    """
    if "datagen_info" not in demo_group:
        return []
        
    datagen_info = demo_group["datagen_info"]
    if "demonstration_states" not in datagen_info.attrs:
        return []
        
    return json.loads(datagen_info.attrs["demonstration_states"])


def _compute_per_subtask_arms(
    demo_group: h5py.Group,
    actions: np.ndarray | None,
    num_subtasks: int,
) -> List[List[str]]:
    """Return per-subtask arm labels using subtask_term_signals to segment the demo.

    For each subtask segment, computes left/right arm energy.  If a single arm
    dominates, returns ``[arm]``.  If both arms are significantly active (e.g.
    coordination), returns ``["left", "right"]``.

    Falls back to whole-demo energy when subtask_term_signals are unavailable.
    """
    if actions is None or actions.ndim != 2 or actions.shape[1] % 2 != 0:
        return [[None]] * num_subtasks

    dim = actions.shape[1]
    per_arm = dim // 2
    T = actions.shape[0]

    # Build segment boundaries from subtask_term_signals
    boundaries = [0]
    signals_grp = None
    if "datagen_info" in demo_group and "subtask_term_signals" in demo_group["datagen_info"]:
        signals_grp = demo_group["datagen_info"]["subtask_term_signals"]

    if signals_grp is not None and num_subtasks > 1:
        signal_keys = sorted(signals_grp.keys())
        prev_boundary = 0
        for sig_key in signal_keys[:-1]:  # last subtask ends at T
            sig = signals_grp[sig_key][:]
            # Find first 0→1 transition at or after the previous boundary,
            # matching the logic in stitching_parse_source_dataset.
            diffs = sig[1:] - sig[:-1]
            nzs = diffs.nonzero()[0]
            end_ind = next(
                (int(nz) + 1 for nz in nzs if int(nz) + 1 >= prev_boundary),
                None,
            )
            if end_ind is not None:
                boundary = end_ind + 1
            else:
                boundary = T
            boundaries.append(boundary)
            prev_boundary = boundary
        boundaries.append(T)
    else:
        # No per-subtask segmentation — use whole demo for all subtasks
        boundaries = [0] + [T] * num_subtasks

    # Compute per-subtask arm labels
    result = []
    for i in range(num_subtasks):
        t_start = boundaries[i] if i < len(boundaries) else 0
        t_end = boundaries[i + 1] if (i + 1) < len(boundaries) else T
        if t_start >= t_end:
            t_start, t_end = 0, T  # fallback

        seg = actions[t_start:t_end]
        left_energy = float(np.abs(seg[:, :per_arm - 1]).sum())
        right_energy = float(np.abs(seg[:, per_arm:(2 * per_arm) - 1]).sum())

        min_e = min(left_energy, right_energy)
        max_e = max(left_energy, right_energy)
        if max_e > 0 and min_e / max_e > 0.3:
            result.append(["left", "right"])
        else:
            result.append(["left"] if left_energy >= right_energy else ["right"])

    return result


def build_demo_lookup(input_dir: str) -> Dict[str, Dict[str, List[Tuple[str, str]]]]:
    """
    Build a lookup dictionary mapping predicates to demo paths.
    
    Args:
        input_dir: Directory containing hdf5 files
        
    Returns:
        dict: Nested dictionary structure: predicate -> "*" -> list of (hdf5_path, demo_id) tuples
    """
    lookup = {
        # grasp: shape category -> object category -> 
        # object name ->list of (hdf5_path, demo_id) tuples
        "grasp": defaultdict(lambda: defaultdict(lambda: defaultdict(list))),
        # in: destination object category -> destination insertion category -> pick shape category 
        #     -> pick object category  -> destination region ->list of (hdf5_path, demo_id) tuples
        "in": defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(
                        lambda: defaultdict(list))))),
        # on: destination object category -> list of (hdf5_path, demo_id) tuples
        "on": defaultdict(list),
        # open: object category -> destination region -> list of (hdf5_path, demo_id) tuples
        "open": defaultdict(lambda: defaultdict(list)),
        # close: object category -> list of (hdf5_path, demo_id) tuples
        "close": defaultdict(lambda: defaultdict(list)),
        # stack: object category -> object name -> list of (hdf5_path, demo_id) tuples
        "stack": defaultdict(lambda: defaultdict(list)),
        # turnon: object category -> list of (hdf5_path, demo_id) tuples
        "turnon": defaultdict(list),
        # turnoff: object category -> list of (hdf5_path, demo_id) tuples
        "turnoff": defaultdict(list),
    }
    
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    
    # Walk through directory to find all hdf5 files
    hdf5_files = list(input_path.rglob("*.hdf5"))
    
    if not hdf5_files:
        print(f"No hdf5 files found in directory: {input_dir}")
        return dict(lookup)
    
    print(f"Found {len(hdf5_files)} hdf5 files to analyze...")

    total_demos = 0
    total_files = 0
    
    for hdf5_path in hdf5_files:
        # print(f"Analyzing: {hdf5_path}")
        
        try:
            with h5py.File(hdf5_path, "r") as f:
                if not has_datagen_info(f):
                    # print(f"  Skipping {hdf5_path} - no datagen_info found")
                    continue
                
                # Get relative path from input directory
                rel_path = hdf5_path.relative_to(input_path)
                
                # Process each demo in the file
                for demo_key in f["data"].keys():
                    demo_group = f["data"][demo_key]
                    
                    # Extract subtasks for this demo
                    subtasks = extract_subtasks_from_demo(demo_group)
                    demonstration_states = extract_demonstration_states_from_demo(demo_group)
                    
                    if not subtasks:
                        continue

                    # Determine source_arm per subtask using action energy.
                    # If subtask_term_signals are available, segment the demo
                    # temporally so each subtask gets its own arm assignment.
                    num_subtasks = len(subtasks)
                    actions = demo_group["actions"][:] if "actions" in demo_group else None
                    per_subtask_arms = _compute_per_subtask_arms(
                        demo_group, actions, num_subtasks,
                    )

                    # Process each subtask
                    for i, (subtask_name, subtask) in enumerate(subtasks.items()):
                        predicate = subtask[0]

                        object_ref = demonstration_states[i][-1]
                        if len(demonstration_states[i]) == 3:
                            other_object_ref = demonstration_states[i][1]
                        else:
                            other_object_ref = None
                        subtask_term_signal = f"{subtask_name}_{'_'.join(demonstration_states[i])}"
                        arm_labels = per_subtask_arms[i]
                        for _arm in arm_labels:
                            demo_path = {
                                "hdf5_path": str(rel_path),
                                "demo_key": demo_key,
                                "object_ref": object_ref,
                                "other_object_ref": other_object_ref,
                                "subtask_index": i,
                                "subtask_term_signal": subtask_term_signal,
                                "source_arm": _arm,
                            }
                            if predicate in ('grasp', 'grasp_left', 'grasp_right'):
                                obj_name = subtask[1]
                                shape_category = object_utils.get_shape_category(obj_name)
                                obj_category = object_utils.get_category(obj_name)
                                lookup["grasp"][shape_category][obj_category][obj_name].append(demo_path)
                            elif predicate == 'in':
                                pick, (dest_obj, dest_region) = subtask[1:]
                                pick_shape_category = object_utils.get_shape_category(pick)
                                pick_obj_category = object_utils.get_category(pick)
                                dest_insertion_category = object_utils.get_insertion_category(dest_obj)
                                dest_obj_category = object_utils.get_category(dest_obj)
                                lookup[predicate][dest_obj_category][dest_insertion_category][pick_shape_category][pick_obj_category][dest_region].append(demo_path)
                            elif predicate == 'on':
                                dest = subtask[-1]
                                dest_obj_category = object_utils.get_category(dest)
                                lookup[predicate][dest_obj_category].append(demo_path)
                            elif predicate == 'open':
                                dest = subtask[-1]
                                if isinstance(dest, list):
                                    dest_obj, dest_region = dest
                                else:
                                    dest_obj = dest
                                    dest_region = None
                                dest_obj_category = object_utils.get_category(dest_obj)
                                lookup[predicate][dest_obj_category][dest_region].append(demo_path)
                            elif predicate == 'close':
                                dest = subtask[-1]
                                if isinstance(dest, list):
                                    dest_obj, dest_region = dest
                                else:
                                    dest_obj = dest
                                    dest_region = None
                                dest_obj_category = object_utils.get_category(dest_obj)
                                lookup[predicate][dest_obj_category][dest_region].append(demo_path)
                            elif predicate == 'stack':
                                bottom, top = subtask[1:]
                                assert bottom == top, "Bottom and top of stack must be the same object"
                                bottom_obj_category = object_utils.get_category(bottom)
                                lookup[predicate][bottom_obj_category][bottom].append(demo_path)
                            elif predicate == 'turnon':
                                obj = subtask[-1]
                                obj_category = object_utils.get_category(obj)
                                lookup[predicate][obj_category].append(demo_path)
                            elif predicate == 'turnoff':
                                obj = subtask[-1]
                                obj_category = object_utils.get_category(obj)
                                lookup[predicate][obj_category].append(demo_path)
                            else:
                                raise NotImplementedError(f"Predicate {predicate} not implemented")

                    total_demos += 1
            total_files += 1
        except Exception as e:
            print(f"  Error processing {hdf5_path}: {e}")
                
    # Convert defaultdict to regular dict for JSON serialization
    result = {}
    for predicate, objects in lookup.items():
        result[predicate] = dict(objects)
    
    return result, total_demos, total_files


def main(args: ParseDatasetArgs):
    """Main function to parse dataset and create lookup dictionary."""
    
    print(f"Parsing dataset directory: {args.input_dir}")
    
    # Build the lookup dictionary
    lookup_dict, total_demos, total_files = build_demo_lookup(args.input_dir)
    
    # Save to JSON file
    output_path = Path(args.input_dir) / args.output_filename
    
    print(f"Saving lookup dictionary to: {output_path}")
    
    with open(output_path, "w") as f:
        json.dump(lookup_dict, f, indent=2)
    
    print(f"\nSummary:")
    print(f"  Total predicates found: {len(lookup_dict)}")
    print(f"  Total demos indexed: {total_demos}")
    print(f"  Total files analyzed: {total_files}")
    print(f"  Lookup dictionary saved to: {output_path}")
    
    # Print some examples
    if lookup_dict:
        print(f"\nExample entries:")
        for i, (predicate, objects) in enumerate(lookup_dict.items()):
            if i >= 3:  # Show only first 3 predicates
                break
            print(f"  {predicate}:")
            for obj, demos in list(objects.items())[:2]:  # Show first 2 objects per predicate
                print(f"    {obj}: {len(demos)} demos")


if __name__ == "__main__":
    args = tyro.cli(ParseDatasetArgs)
    main(args)
