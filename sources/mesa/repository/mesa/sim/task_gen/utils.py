from __future__ import annotations

import copy
import random
import re
from typing import Dict, List, Optional, Tuple

from mesa.sim.envs.bddl_base_domain import TASK_MAPPING, BDDLBaseDomain
from mesa.sim.envs.objects import get_object_dict

from .object_categories import ArticulatedObjectSpec, DestObjectSpec, GraspObjectSpec


def camelize_instruction(text: str) -> List[str]:
    return [tok for tok in re.split(r"\s+", text.strip().lower()) if tok]


def make_region_dict(
    *,
    region_name: str,
    target: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    yaw_rotation_min: float = 0.0,
    yaw_rotation_max: float = 0.0,
    rgba: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 0.0),
) -> Tuple[str, Dict[str, object]]:
    name = f"{target}_{region_name}"
    region_dict: Dict[str, object] = {
        "target": target,
        "ranges": [[float(x_min), float(y_min), float(x_max), float(y_max)]],
        "extra": [],
        "yaw_rotation": [float(yaw_rotation_min), float(yaw_rotation_max)],
        "rgba": [float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3])],
    }
    return name, region_dict

def make_named_grasp_object_spec(object_name: str, spec: GraspObjectSpec) -> GraspObjectSpec:
    spec = copy.deepcopy(spec)
    spec.id = object_name
    return spec

def make_named_dest_object_spec(object_name: str, spec: DestObjectSpec) -> DestObjectSpec:
    spec = copy.deepcopy(spec)
    spec.id = object_name
    return spec

def make_named_articulated_object_spec(object_name: str, spec: ArticulatedObjectSpec) -> ArticulatedObjectSpec:
    spec = copy.deepcopy(spec)
    spec.id = object_name
    return spec

def resolve_dest_region_site(
    *,
    key: str,
    regions,
    dest_region: Optional[str],
) -> str:
    if isinstance(regions, dict):
        if dest_region is not None:
            if dest_region not in regions:
                raise ValueError(f"dest_region '{dest_region}' not valid for destination '{key}'")
            return regions[dest_region]
        if len(regions) == 1:
            return next(iter(regions.values()))
        raise ValueError(
            f"Destination '{key}' exposes multiple regions; dest_region must be specified"
        )

    # assume iterable sequence
    if dest_region is not None:
        if dest_region in regions:
            return dest_region  # type: ignore[index]
        else:
            raise ValueError(
                f"dest_region '{dest_region}' not valid for destination '{key}'"
            ) from None
    if len(regions) == 1:
        return regions[0]
    raise ValueError(
        f"Destination '{key}' exposes multiple regions; dest_region must be specified"
    )

def workspace_name_for_problem(problem_name: str) -> str:
    problem_class: BDDLBaseDomain = TASK_MAPPING[problem_name]
    return problem_class.workspace_name

def get_num_to_place(num_distractors: int | Tuple[int, int], rng: random.Random) -> int:
    if isinstance(num_distractors, int):
        return num_distractors
    return rng.randint(num_distractors[0], num_distractors[1])

_object_key_cache = {}
def search_by_regex(search_pattern: str, object_format: str = "mesa") -> List[str]:
    cache_key = (object_format, search_pattern)
    if cache_key not in _object_key_cache:
        regex = re.compile(search_pattern)
        matches = [key for key in get_object_dict(object_format).keys() if regex.search(key)]
        _object_key_cache[cache_key] = matches
    return _object_key_cache[cache_key]

def resolve_object_key(search_pattern: str, variant_index: int, source: bool, seed: int = 0, exclude_mirror: bool = False, object_format: str = "mesa") -> str:
    matches = search_by_regex(search_pattern, object_format)
    if not matches:
        raise ValueError(f"No registered objects match pattern: {search_pattern}")
    if exclude_mirror:
        # Mirror fixtures open away from the +x robot; fall back to the full set only if
        # a pattern matches nothing but mirror assets.
        non_mirror = [m for m in matches if not m.endswith("_mirror")]
        if non_mirror:
            matches = non_mirror
    if source:
        return matches[variant_index % len(matches)]
    else:
        rng = random.Random(seed + variant_index)
        return rng.choice(matches)
