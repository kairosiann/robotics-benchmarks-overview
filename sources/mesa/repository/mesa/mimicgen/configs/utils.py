import os
from typing import Dict, List

import mesa.sim.envs.bddl_utils as BDDLUtils
from mesa import MESA_ROOT
from mesa.mimicgen.configs.config import MGConfig
from mesa.sim.envs.objects import get_object_fn
from mesa.sim.envs.objects.robocasa_objects import get_obj_info


def generate_mg_config_classes(
    task_suite_name: str,
    camera_names: List[str],
    camera_height: int,
    camera_width: int,
    # pick_place: bool = False,
    stitching: bool = False,
    variant_folder: str = "train",
    object_format: str = "mesa",
) -> Dict[str, MGConfig]:
    """
    Generates MimicGen config instances for all BDDL files under the specified task suite name.
    This function creates MGConfig instances with task specifications populated based on the 
    parsed BDDL files and observation configurations based on the provided camera settings.

    Args:
        task_suite_name (str): The name of the task suite, which corresponds to a directory
            containing BDDL files.
        camera_names (list): List of camera names to be used for observations.
        camera_height (int): Height of the camera images.
        camera_width (int): Width of the camera images.
        pick_place (bool): Whether this is a pick and place task.

    Returns:
        Dict[str, MGConfig]: Dictionary mapping task names to their corresponding config instances.
    """
    base_path = os.path.join(MESA_ROOT, "task_suites", "bddl_files")
    task_suite_path = os.path.join(base_path, task_suite_name)
    if not os.path.isdir(task_suite_path):
        raise FileNotFoundError(f"Task suite path not found for {task_suite_name}")

    configs = {}
    
    for task_name in sorted(os.listdir(task_suite_path)):
        folder_path = os.path.join(task_suite_path, task_name)
        if not os.path.isdir(folder_path):
            continue

        
        task_file_path = os.path.join(folder_path, variant_folder, "000.json")
        if not os.path.isfile(task_file_path):
            print(f"Skipping {task_name}: no {variant_folder}/000.json found")
            continue
        parsed_problem = BDDLUtils.load_problem(task_file_path)
    
        # Create task specification
        task_spec = {}
        num_subtasks = len(parsed_problem["demonstration_states"])
        
        for i, subtask in enumerate(parsed_problem["demonstration_states"]):
            subtask_id = f"subtask_{i+1}"

            selection_strategy_kwargs = dict(nn_k=3)
            object_ref = None
            
            mapping_inv = {}
            for k, values in parsed_problem["fixtures"].items():
                for v in values:
                    mapping_inv[v] = k
            for k, values in parsed_problem["objects"].items():
                for v in values:
                    mapping_inv[v] = k

            for obj_name in mapping_inv:
                # Currently, we assume that the reference object is the
                # last entity in the subtask predicate that starts with the object name.
                # This is a heuristic and may need to be adjusted based on the demonstration predicate.
                if subtask[-1].startswith(obj_name):
                    object_ref = obj_name
                    break
                    
            object_name_ref = None
            for object_name, refs in parsed_problem["objects"].items():
                if object_ref in refs:
                    object_name_ref = object_name
                    break
            if object_name_ref is None:
                for fixture_name, refs in parsed_problem["fixtures"].items():
                    if object_ref in refs:
                        object_name_ref = fixture_name
                        break

            if i == num_subtasks - 1:
                subtask_term_offset_range = None
            else:
                subtask_term_offset_range = (10, 20)  # AM: could be low (0,0) if demo states are precise
            object_instance = get_object_fn(object_name_ref, object_format)()
            obj_info = get_obj_info(object_name_ref)
            
            ignore_roll_pitch = False
            ignore_yaw = False
            optimize_start = True
            selection_strategy = "nearest_neighbor_object"
            object_centric_transform = False
            optimize_start_kwargs = {
                "pos": {
                    "schedule": "none",
                    "transform_rot": obj_info.get("axisymmetric", False),
                },
                "rot": {
                    "schedule": "shaped",
                    "beta": 0.3,
                    "do_slerp": True,
                },
            }

            subtask_predicate = subtask[0]
            if subtask_predicate == 'grasp':
                ignore_roll_pitch = True
                ignore_yaw = obj_info.get("axisymmetric", False)
                if not ignore_yaw:
                    optimize_start_kwargs["rot"]["schedule"] = "shaped"
                    optimize_start_kwargs["rot"]["beta"] = 0.5
                    optimize_start_kwargs["rot"]["do_slerp"] = True
            elif subtask_predicate == 'in':
                ignore_roll_pitch = True
                ignore_yaw = obj_info.get("axisymmetric", False)
                if 'slide_cabinet' in object_name_ref:
                    selection_strategy = "nearest_neighbor_eef_object_translation"
                else:
                    selection_strategy = "nearest_neighbor_robot_distance"
                if 'slide_cabinet' in object_name_ref or "microwave" in object_name_ref:
                    optimize_start_kwargs["pos"]["schedule"] = "shaped"
                    optimize_start_kwargs["pos"]["beta"] = 0.5
                    optimize_start_kwargs["pos"]["schedule_ratio"] = 0.5
            elif subtask_predicate == 'on':
                ignore_roll_pitch = True
                ignore_yaw = True
                selection_strategy = "nearest_neighbor_robot_distance"
                optimize_start_kwargs["rot"]["schedule"] = "none"
            elif subtask_predicate == 'stack':
                ignore_roll_pitch = True
                ignore_yaw = obj_info.get("axisymmetric", False)
                selection_strategy = "nearest_neighbor_robot_distance"
            elif subtask_predicate == 'open':
                selection_strategy = "nearest_neighbor_robot_distance"
                optimize_start = False
            elif subtask_predicate == 'close':
                selection_strategy = "nearest_neighbor_eef_object_translation"
                optimize_start_kwargs["pos"]["schedule"] = "shaped"
                optimize_start_kwargs["pos"]["beta"] = 0.3
                optimize_start_kwargs["pos"]["schedule_ratio"] = 0.3
            
            if ignore_yaw:
                optimize_start_kwargs["rot"]["beta"] = 1.0
        

            task_spec[subtask_id] = {
                "subtask_term_offset_range": subtask_term_offset_range,
                "selection_strategy": selection_strategy,
                "selection_strategy_kwargs": selection_strategy_kwargs,
                "action_noise": 0.01,  # adds noise to actions
                "num_interpolation_steps": -1 if optimize_start else 5,
                "num_fixed_steps": 0,
                "apply_noise_during_interpolation": False,
                "ignore_roll_pitch": ignore_roll_pitch,
                "ignore_yaw": ignore_yaw,
                "rotation_axis": object_instance.rotation_axis,
                "optimize_start": optimize_start,
                "optimize_start_kwargs": optimize_start_kwargs,
                "object_centric_transform": object_centric_transform,
            }

        # Create the config instance
        config = MGConfig(
            name=task_name,
            task_suite_name=task_suite_name,
        )
        
        # Set observation configuration
        config.obs.camera_names = camera_names
        config.obs.camera_height = camera_height
        config.obs.camera_width = camera_width
        
        # Set task specification
        config.task.task_spec = task_spec
        
        configs[task_name] = config
    
    return configs

def finish_task_spec(task_spec, parsed_problem):
    search_spec_list = BDDLUtils.get_search_spec_list(
        subtask_list=parsed_problem["demonstration_states"],
        objects_dict=parsed_problem["objects"],
        regions_dict=parsed_problem["regions"],
        fixtures_dict=parsed_problem["fixtures"],
    )
    for i, subtask_predicate in enumerate(parsed_problem["demonstration_states"]):
        subtask_id = f"subtask_{i+1}"
        task_spec[subtask_id]["object_ref"] = subtask_predicate[-1]
        if len(subtask_predicate) == 3: # "on" and "in" subtasks
            task_spec[subtask_id]["other_object_ref"] = subtask_predicate[1]
        task_spec[subtask_id]["search_spec"] = search_spec_list[subtask_id]
        if i == len(parsed_problem["demonstration_states"]) - 1:
            task_spec[subtask_id]["subtask_term_signal"] = None
        else:
            task_spec[subtask_id]["subtask_term_signal"] = subtask_id
    return task_spec