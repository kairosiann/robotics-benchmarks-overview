from dataclasses import dataclass
from typing import List


@dataclass
class ArenaSpec:
    source_problem_name: str
    variant_problem_names: List[str]
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    back_min_x: float
    back_max_x: float


ARENAS = {
    "mimiclabs_lab1_tabletop_manipulation": ArenaSpec(
        source_problem_name="mimiclabs_lab1_tabletop_manipulation",
        variant_problem_names=["mimiclabs_lab1_tabletop_manipulation"],
        min_x=0.05,
        max_x=0.3,
        min_y=-0.4,
        max_y=0.4,
        back_min_x=-0.15,
        back_max_x=-0.05,
    ),
}