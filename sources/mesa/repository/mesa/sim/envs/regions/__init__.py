from .base_region_sampler import *
from .object_property_sampler import *
from .workspace_region_sampler import *

REGION_SAMPLERS = {
    "mimiclabs_lab1_tabletop_manipulation": {"table": TableRegionSampler},
    "mimiclabs_lab2_tabletop_manipulation": {"table": TableRegionSampler},
    "mimiclabs_lab3_tabletop_manipulation": {"table": TableRegionSampler},
    "mimiclabs_lab4_tabletop_manipulation": {"table": TableRegionSampler},
    "mimiclabs_lab5_tabletop_manipulation": {"table": TableRegionSampler},
    "mimiclabs_lab6_tabletop_manipulation": {"table": TableRegionSampler},
    "mimiclabs_lab7_tabletop_manipulation": {"table": TableRegionSampler},
    "mimiclabs_lab8_tabletop_manipulation": {"table": TableRegionSampler},
}


def get_region_samplers(problem_name, region_sampler_name):
    return REGION_SAMPLERS[problem_name][region_sampler_name]


__all__ = [name for name in globals() if not name.startswith("_")]
