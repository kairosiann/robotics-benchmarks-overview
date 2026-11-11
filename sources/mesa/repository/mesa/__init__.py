import json
import os

import robosuite
import robosuite.macros as macros

from mesa.sim.envs.bddl_base_domain import TASK_MAPPING, BDDLBaseDomain

assert macros.IMAGE_CONVENTION == "opencv", "You must run `uv run scripts/setup/setup_robosuite_macros.py` to set up the macros file"

MESA_ROOT = os.path.dirname(__file__)


def get_default_env_kwargs():
    return json.load(open(os.path.join(MESA_ROOT, "config", "envs", "default.json"), "r"))

def get_default_controller_kwargs(controller_type: str = "osc_pose"):
    return json.load(open(os.path.join(MESA_ROOT, "config", "controllers", f"{controller_type}.json"), "r"))


def get_env_name(json_file: str = None, parsed_problem: dict = None):
    assert json_file is not None or parsed_problem is not None, "Either json_file or parsed_problem must be provided"
    assert json_file is None or parsed_problem is None, "Only one of json_file or parsed_problem must be provided"
    
    if json_file is not None:
        parsed_problem = json.load(open(json_file, "r"))

    env_class = TASK_MAPPING[parsed_problem["problem_name"]]
    return env_class.__name__

def get_env_kwargs(
    json_file: str = None, 
    parsed_problem: dict = None,
    controller_type: str = "osc_pose",
    control_delta: bool = False,
    **kwargs
    ):
    assert json_file is not None or parsed_problem is not None, "Either json_file or parsed_problem must be provided"
    assert json_file is None or parsed_problem is None, "Only one of json_file or parsed_problem must be provided"
    
    if json_file is not None:
        parsed_problem = json.load(open(json_file, "r"))

    default_kwargs = get_default_env_kwargs()
    default_controller_kwargs = get_default_controller_kwargs(controller_type)
    default_controller_kwargs["body_parts"]["right"]["input_type"] = "delta" if control_delta else "absolute"
    default_kwargs.update({
        "parsed_problem": parsed_problem,
        "controller_configs": default_controller_kwargs,
    })
    kwargs = default_kwargs | kwargs
    return kwargs


def gen_env_name_and_kwargs(
    json_file: str = None, 
    parsed_problem: dict = None,
    controller_type: str = "osc_pose",
    control_delta: bool = False,
    **kwargs
) -> tuple[str, dict]:
    env_name = get_env_name(json_file, parsed_problem)
    env_kwargs = get_env_kwargs(json_file, parsed_problem, controller_type, control_delta, **kwargs)
    return env_name, env_kwargs


def make_env(
    json_file: str = None, 
    parsed_problem: dict = None,
    controller_type: str = "osc_pose",
    control_delta: bool = False,
    **kwargs
) -> BDDLBaseDomain | tuple[str, dict]:
    env_name = get_env_name(json_file, parsed_problem)
    env_kwargs = get_env_kwargs(json_file, parsed_problem, controller_type, control_delta, **kwargs)
    return robosuite.make(env_name, **env_kwargs)


__all__ = [
    "BDDLBaseDomain",
    "MESA_ROOT",
    "TASK_MAPPING",
    "gen_env_name_and_kwargs",
    "get_default_controller_kwargs",
    "get_default_env_kwargs",
    "get_env_kwargs",
    "get_env_name",
    "make_env",
]
