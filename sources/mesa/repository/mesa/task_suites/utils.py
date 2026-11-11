from collections import defaultdict
from typing import Any, Dict, List, Tuple

from mesa.sim.task_gen import (
    ArticulatedMultistepTaskConfig,
    CloseTaskConfig,
    OpenTaskConfig,
    PickAndPlaceTaskConfig,
)
from mesa.sim.task_gen.object_categories import (
    ARTICULATED_OBJECTS,
    DEST_OBJECTS,
    GRASP_OBJECTS,
    ArticulatedObjectSpec,
    DestObjectSpec,
    GraspObjectSpec,
    grasp_object_height,
)


# Task generators
def make_articulated_primitives(
    default_config: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, OpenTaskConfig | CloseTaskConfig], Dict[str, Dict[str, Any]]]:
    """
    Generate all possible open and close tasks for articulated objects.
    Args:
        default_config: A dictionary of default configuration values.

    Returns:
        A tuple of two dictionaries:
            - The first dictionary maps task IDs to task configs.
            - The second dictionary maps task IDs to task meta information for distractors.
    """
    default_config = default_config or {}
    all_configs: Dict[str, OpenTaskConfig | CloseTaskConfig] = {}
    for articulated_object in ARTICULATED_OBJECTS:
        articulated_info: ArticulatedObjectSpec = ARTICULATED_OBJECTS[articulated_object]
        if not articulated_info.supports_open_close:
            continue
        dest_natural = articulated_info.natural_language

        # For some objects, like the cabinet, there are multiple articulation regions, meaning that
        # the intended one must be specified. For others, like the microwave, there is only one so
        # it can automatically be inferred.
        if articulated_info.articulation_regions:
            articulation_regions = articulated_info.articulation_regions
            articulation_regions_natural = articulated_info.articulation_regions_natural
        else:
            articulation_regions = [None] * len(articulated_info.regions)
            articulation_regions_natural = [None] * len(articulated_info.regions_natural)

        # Iterate over all possible articulation regions.
        for articulation_region, articulation_region_natural in zip(articulation_regions, articulation_regions_natural):
            # Resolve natural language suffix and unique task ID prefix.
            if articulation_region is None:
                suffix = dest_natural
                task_id_prefix = articulated_object
            else:
                suffix = f"{articulation_region_natural} of the {dest_natural}"
                task_id_prefix = f"{articulated_object}_{articulation_region}"

            # Instantiate the open task config.
            config = OpenTaskConfig(
                language_instruction=f"Open the {suffix}",
                task_id=f"{task_id_prefix}_open",
                fixture=articulated_object,
                fixture_articulation_region=articulation_region,
                **default_config,
            )
            all_configs[config.task_id] = config

            # Instantiate the close task config.
            config = CloseTaskConfig(
                language_instruction=f"Close the {suffix}",
                task_id=f"{task_id_prefix}_close",
                fixture=articulated_object,
                fixture_articulation_region=articulation_region,
                **default_config,
            )
            all_configs[config.task_id] = config
    return all_configs, {}

def make_pick_and_place_tasks(
    default_config: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, PickAndPlaceTaskConfig], Dict[str, Dict[str, Any]]]:
    default_config = default_config or {}
    all_configs: Dict[str, PickAndPlaceTaskConfig] = {}
    all_meta: Dict[str, Dict[str, Any]] = {}
    for grasp_object in GRASP_OBJECTS:
        grasp_info: GraspObjectSpec = GRASP_OBJECTS[grasp_object]
        grasp_natural = grasp_info.natural_language

        # We used cursor to specify semantically plausible destinations for each object.
        # For example, it makes sense to put a water bottle on a tray but not in a bowl.
        valid_dests = grasp_info.valid_dests

        # Iterate over all possible destinations.
        for dest_object in valid_dests:
            if dest_object not in DEST_OBJECTS:
                continue
            dest_info: DestObjectSpec = DEST_OBJECTS[dest_object]
            dest_natural = dest_info.natural_language
            
            # Some objects have multiple regions, like the dish drainer which has a left 
            # and right region. We iterate over these
            for region, region_natural in zip(dest_info.regions, dest_info.regions_natural):

                task_id = f"{grasp_object}_{dest_object}_{region}"
                
                config = PickAndPlaceTaskConfig(
                    language_instruction=f"Put the {grasp_natural} {region_natural} the {dest_natural}",
                    task_id=task_id,
                    pick_objects=[grasp_object],
                    dest_object=dest_object,
                    dest_region=region,
                    **default_config,
                )

                all_configs[task_id] = config
                all_meta[task_id] = {
                    "grasp_objects": [grasp_object],
                    "dest_object": dest_object,
                }
    return all_configs, all_meta


def make_multistep_pick_and_place_tasks(
    task_specs: List[Tuple[str, str, str]],
    default_config: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, PickAndPlaceTaskConfig], Dict[str, Dict[str, Any]]]:
    """
    Generate all possible multistep pick and place tasks.
    Args:
        task_specs: A list of task specifications, each of which is a tuple of three strings:
            - The first string is the name of the first grasp object.
            - The second string is the name of the second grasp object.
            - The third string is the name of the destination object.
        default_config: A dictionary of default configuration values.

    Returns:
        A tuple of two dictionaries:
            - The first dictionary maps task IDs to task configs.
            - The second dictionary maps task IDs to task meta information for distractors.
    """
    default_config = default_config or {}
    all_configs: Dict[str, PickAndPlaceTaskConfig] = {}
    all_meta: Dict[str, Dict[str, Any]] = {}
    for task_spec in task_specs:
        grasp_object_1, grasp_object_2, dest_object = task_spec
        grasp_info_1: GraspObjectSpec = GRASP_OBJECTS[grasp_object_1]
        grasp_info_2: GraspObjectSpec = GRASP_OBJECTS[grasp_object_2]
        grasp_natural_1 = grasp_info_1.natural_language
        grasp_natural_2 = grasp_info_2.natural_language
        
        dest_info: DestObjectSpec = DEST_OBJECTS[dest_object]
        dest_natural = dest_info.natural_language

        for region, region_natural in zip(dest_info.regions, dest_info.regions_natural):
            task_id = f"{grasp_object_1}_{grasp_object_2}_{dest_object}_{region}"
            config = PickAndPlaceTaskConfig(
                language_instruction=f"Put the {grasp_natural_1} and {grasp_natural_2} {region_natural} the {dest_natural}",
                task_id=task_id,
                pick_objects=[grasp_object_1, grasp_object_2],
                dest_object=dest_object,
                dest_region=region,
                **default_config,
            )

            all_configs[task_id] = config
            all_meta[task_id] = {
                "grasp_objects": [grasp_object_1, grasp_object_2],
                "dest_object": dest_object,
            }
    return all_configs, all_meta


def make_articulated_multistep_tasks(
    default_config: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, ArticulatedMultistepTaskConfig], Dict[str, Dict[str, Any]]]:
    """
    Generate all possible multistep pick and place tasks for articulated objects.
    Specifically, these are tasks which involve optionally opening an articulated object,
    putting something in it, and optionally closing it.
    Args:
        default_config: A dictionary of default configuration values.

    Returns:
        A tuple of two dictionaries:
            - The first dictionary maps task IDs to task configs.
            - The second dictionary maps task IDs to task meta information for distractors.
    """
    default_config = default_config or {}
    object_format = default_config.get("object_format", "mesa")
    all_configs: Dict[str, ArticulatedMultistepTaskConfig] = {}
    all_meta: Dict[str, Dict[str, Any]] = {}

    for grasp_object in GRASP_OBJECTS:
        grasp_info: GraspObjectSpec = GRASP_OBJECTS[grasp_object]
        grasp_natural = grasp_info.natural_language
        valid_articulated_dests = grasp_info.valid_articulated_dests

        for articulated_object in valid_articulated_dests:
            articulated_info: ArticulatedObjectSpec = ARTICULATED_OBJECTS[articulated_object]
            articulated_natural = articulated_info.natural_language

            # For some objects, like the cabinet, there are multiple articulation regions, meaning that
            # the intended one must be specified. For others, like the microwave, there is only one so
            # it can automatically be inferred.
            if articulated_info.articulation_regions:
                articulation_regions = articulated_info.articulation_regions
                articulation_regions_natural = articulated_info.articulation_regions_natural
            else:
                articulation_regions = [None] * len(articulated_info.regions)
                articulation_regions_natural = [None] * len(articulated_info.regions_natural)

            iterator = zip(articulated_info.regions, articulation_regions, articulation_regions_natural)
            for region, articulation_region, articulation_region_natural in iterator:

                # Resolve natural language instruction for the target articulation region
                if articulation_region is None:
                    art_instr = articulated_natural
                else:
                    art_instr = f"{articulation_region_natural} of the {articulated_natural}"

                task_id = f"{grasp_object}_{articulated_object}_{region}"

                meta_info = {
                    "grasp_objects": [grasp_object],
                    "articulated_object": articulated_object,
                }

                # Start and end open
                all_configs[task_id] = ArticulatedMultistepTaskConfig(
                    pick_object=grasp_object,
                    language_instruction=f"Put the {grasp_natural} in the {art_instr}",
                    task_id=task_id,
                    start_closed=False,
                    end_closed=False,
                    fixture=articulated_object,
                    fixture_articulation_region=articulation_region,
                    fixture_contain_region=region,
                    **default_config,
                )

                # Open first
                open_task_id = f"open_and_{task_id}"
                all_configs[open_task_id] = ArticulatedMultistepTaskConfig(
                    pick_object=grasp_object,
                    language_instruction=f"Open the {art_instr} and put the {grasp_natural} in it",
                    task_id=open_task_id,
                    start_closed=True,
                    end_closed=False,
                    fixture=articulated_object,
                    fixture_articulation_region=articulation_region,
                    fixture_contain_region=region,
                    **default_config,
                )

                all_meta[task_id] = meta_info
                all_meta[open_task_id] = meta_info

                # Check if the grasp object is too tall or long to fit in the articulated object.
                # If so, do not generate tasks trying to close it
                height_ok = (
                    articulated_info.height_limit is None
                    or grasp_object_height(grasp_info, object_format) < articulated_info.height_limit
                )
                length_ok = not articulated_info.length_limit or not grasp_info.long
                if height_ok and length_ok:
                    # Start closed, end closed
                    open_close_task_id = f"open_and_{task_id}_and_close"
                    all_configs[open_close_task_id] = ArticulatedMultistepTaskConfig(
                        pick_object=grasp_object,
                        language_instruction=f"Open the {art_instr} and put the {grasp_natural} in it and close it",
                        task_id=open_close_task_id,
                        start_closed=True,
                        end_closed=True,
                        fixture=articulated_object,
                        fixture_articulation_region=articulation_region,
                        fixture_contain_region=region,
                        **default_config,
                    )
                    all_meta[open_close_task_id] = meta_info

                    close_task_id = f"{task_id}_and_close"
                    # start open, end closed
                    all_configs[close_task_id] = ArticulatedMultistepTaskConfig(
                        pick_object=grasp_object,
                        language_instruction=f"Put the {grasp_natural} in the {art_instr} and close it",
                        task_id=close_task_id,
                        start_closed=False,
                        end_closed=True,
                        fixture=articulated_object,
                        fixture_articulation_region=articulation_region,
                        fixture_contain_region=region,
                        **default_config,
                    )

                    all_meta[close_task_id] = meta_info
    return all_configs, all_meta


def make_valid_distractor_map(
    task_list: List[str],
    task_gen_meta: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, List[str]]]:
    """
    Returns a dictionary mapping objects to valid distractors. Specifically, we want to 
    guarantee that during task generation, for each variant of a task, there is some task
    in task list such that its task relevant objects are present in the distractor objects.

    The purpose of this function is to generate a mapping to assist with this.

    Args:
        task_list: A list of task names.
        task_gen_meta: meta dictionaries generated in the functions above

    Returns:
        A dictionary mapping objects to valid distractors.
    """
    object_to_dest_map = defaultdict(set)
    object_to_articulated_map = defaultdict(set)
    dest_to_object_map = defaultdict(set)
    articulated_to_object_map = defaultdict(set)
    all_objects = set()
    all_dests = set()
    all_articulateds = set()

    for task_name in task_list:
        if task_name not in task_gen_meta:
            continue

        meta = task_gen_meta[task_name]
        grasp_objects = meta['grasp_objects']
        dest_object = meta.get('dest_object', None)
        articulated_object = meta.get('articulated_object', None)
        for grasp_object in grasp_objects:
            all_objects.add(grasp_object)
        if dest_object is not None:
            all_dests.add(dest_object)
        if articulated_object is not None:
            all_articulateds.add(articulated_object)
        if dest_object is not None:
            for grasp_object in grasp_objects:
                object_to_dest_map[grasp_object].add(dest_object)   
                dest_to_object_map[dest_object].add(grasp_object)
        if articulated_object is not None:
            for grasp_object in grasp_objects:
                object_to_articulated_map[grasp_object].add(articulated_object)
                articulated_to_object_map[articulated_object].add(grasp_object)

    valid_distractor_map = {
        "object_to_dest_map": dict(object_to_dest_map),
        "object_to_articulated_map": dict(object_to_articulated_map),
        "dest_to_object_map": dict(dest_to_object_map),
        "articulated_to_object_map": dict(articulated_to_object_map),
    }

    for dict_ in valid_distractor_map.values():
        for k in dict_:
            dict_[k] = list(dict_[k])

    valid_distractor_map["all_object"] = list(all_objects)
    valid_distractor_map["all_dest"] = list(all_dests)
    valid_distractor_map["all_articulated"] = list(all_articulateds)
    return valid_distractor_map
