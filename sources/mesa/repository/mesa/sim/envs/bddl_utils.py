import json

from bddl.parsing import *


def get_search_spec_list(
    *,
    subtask_list,
    objects_dict,
    regions_dict,
    fixtures_dict,
):
    """
    Convert the subtask list into a list of object ids so that we can use it for search
    """
    search_spec_list = {}
    objects_dict_flipped = {}
    for label, instances in {**objects_dict, **fixtures_dict}.items():
        for instance in instances:
            objects_dict_flipped[instance] = label

    for i, subtask in enumerate(subtask_list):
        predicate = subtask[0]
        objects = subtask[1:]
        search_spec = [predicate]
        for j, obj_or_region in enumerate(objects):
            if obj_or_region in objects_dict_flipped:
                obj = objects_dict_flipped[obj_or_region]
                search_spec.append(obj)
            elif obj_or_region in regions_dict:
                obj = regions_dict[obj_or_region]['target']
                region_name = obj_or_region[len(obj) + 1:]
                # breakpoint()
                obj = objects_dict_flipped[obj]
                search_spec.append((obj, region_name))
            else:
                raise ValueError(f"Object or region {obj_or_region} not found in objects or regions")
        search_spec_list[f"subtask_{i+1}"] = search_spec
    return search_spec_list


def load_problem(problem_filename: str):
    if problem_filename.endswith(".json"):
        parsed_problem = json.load(open(problem_filename, "r"))
        return parsed_problem

