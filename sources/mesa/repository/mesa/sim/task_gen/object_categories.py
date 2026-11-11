import copy
import re
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from mesa.sim.envs.objects.base_object import get_object_dict

USE_AI_AS_DISTRACTORS = False


@dataclass
class ObjectSpec:
    # the general class of object, e.g. "apple", "banana", "bottle", etc.
    name: str
    # the regex pattern to match the object name, e.g. "robocasa_apple_\d+", "robocasa_banana_\d+", "robocasa_bottle_\d+", etc.
    search_pattern: str
    # the unique identifier for the object in the BDDL file, which can be anything
    id: str | None = None
    # the key in the global object dictionary, eg "robocasa_apple_1", "robocasa_banana_1", "robocasa_bottle_1", etc.
    key: str | None = None
    natural_language: str | None = None
    natural_language_plural: str | None = None
    allow_rotation: bool = True
    spawn_region: str = "full_table"
    is_valid_distractor: bool = True

    def __post_init__(self) -> None:
        if self.natural_language is None:
            natural = self.name.replace("_ai", "")
            self.natural_language = natural.replace("_", " ")
        if self.natural_language_plural is None:
            self.natural_language_plural = self.natural_language + "s"
        assert self.spawn_region in [
            "full_table", "left", "right", "center", "back",
            "back-left", "back-right", "back-center", "back-spatial-right", "spatial-right",
        ]

@dataclass
class GraspObjectSpec(ObjectSpec):
    valid_dests: list[str] = field(default_factory=list)
    valid_articulated_dests: list[str] = field(default_factory=list)
    # None -> computed per object_format on demand (see grasp_object_height); set
    # explicitly for objects whose asset top sites are mislabeled (e.g. flat produce).
    height: float | None = None
    stackable: bool = False
    long: bool = False


@dataclass
class DestObjectSpec(ObjectSpec):
    regions: list[str] = field(default_factory=list)
    regions_natural: list[str] = field(default_factory=list)
    spawn_region: str = "full_table"

    def __post_init__(self) -> None:
        super().__post_init__()

        assert len(self.regions) == len(self.regions_natural), "The number of regions and regions_natural must be the same"
        

@dataclass
class ArticulatedObjectSpec(ObjectSpec):
    supports_open_close: bool = True
    regions: list[str] = field(default_factory=list)
    regions_natural: list[str] = field(default_factory=list)
    height_limit: float | None = None
    length_limit: bool | None = None
    articulation_regions: list[str] = field(default_factory=list)
    articulation_regions_natural: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__post_init__()
        assert len(self.regions) == len(self.regions_natural), "The number of regions and regions_natural must be the same"
        assert len(self.articulation_regions) == len(self.articulation_regions_natural), "The number of articulation_regions and articulation_regions_natural must be the same"


_grasp_height_cache: dict[tuple[str, str], float] = {}
def grasp_object_height(spec: GraspObjectSpec, object_format: str = "mesa") -> float:
    """Tallest matching asset's top offset for the given format; an explicit spec.height wins.

    Mesa and bimesa register different meshes/scales under the same keys, so the
    height differs by format; resolve it against the format the task generates with.
    """
    if spec.height is not None:
        return spec.height
    cache_key = (object_format, spec.search_pattern)
    if cache_key not in _grasp_height_cache:
        pattern = re.compile(spec.search_pattern)
        heights = [
            cls().top_offset[-1]
            for key, cls in get_object_dict(object_format).items()
            if pattern.search(key)
        ]
        # Fallback: salt_shaker/pepper_shaker have no robocasa365 asset (the backend
        # consolidated them into a generic `shaker` category not yet mapped here), so
        # they match nothing; the placeholder only avoids np.max([]).
        _grasp_height_cache[cache_key] = float(np.max(heights)) if heights else 0.05
    return _grasp_height_cache[cache_key]


GRASP_OBJECTS: dict[str, GraspObjectSpec] = {
    "alcohol": GraspObjectSpec(
        name="alcohol",
        search_pattern=r"^robocasa_alcohol_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "apple": GraspObjectSpec(
        name="apple",
        search_pattern=r"^robocasa_apple_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "avocado": GraspObjectSpec(
        name="avocado",
        search_pattern=r"^robocasa_avocado_(?!0$|1$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "bagel": GraspObjectSpec(
        name="bagel",
        search_pattern=r"^robocasa_bagel_(?!0$|1$|2$|5$|6$|7$|9$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "baguette": GraspObjectSpec(
        name="baguette",
        search_pattern=r"^robocasa_baguette_(?!0$|5$)\d+$",
        long=True,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "banana": GraspObjectSpec(
        name="banana",
        search_pattern=r"^robocasa_banana_\d+$",
        height=0.02,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "bar": GraspObjectSpec(
        name="bar",
        search_pattern=r"^robocasa_bar_\d+$",
        height=0.02,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "bowl",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "bar_soap": GraspObjectSpec(
        name="bar_soap",
        search_pattern=r"^robocasa_bar_soap_(?!4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "beer": GraspObjectSpec(
        name="beer",
        search_pattern=r"^robocasa_beer_(?!3$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "bell_pepper": GraspObjectSpec(
        name="bell_pepper",
        search_pattern=r"^robocasa_bell_pepper_(?!0$|3$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "book": GraspObjectSpec(
        name="book",
        search_pattern="^.*_book$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "wooden_shelf",
            "wooden_two_layer_shelf",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "bottled_drink": GraspObjectSpec(
        name="bottled_drink",
        search_pattern=r"^robocasa_bottled_drink_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "bottled_water": GraspObjectSpec(
        name="bottled_water",
        search_pattern=r"^robocasa_bottled_water_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "bowl": GraspObjectSpec(
        name="bowl",
        search_pattern=r"^(robocasa_bowl_(?!7$)\d+|.*_bowl)$",
        stackable=True,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "plate",
            "cutting_board",
            "bowl_drainer",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "boxed_drink": GraspObjectSpec(
        name="boxed_drink",
        search_pattern=r"^robocasa_boxed_drink_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "wooden_shelf",
            "wooden_two_layer_shelf",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "boxed_food": GraspObjectSpec(
        name="boxed_food",
        search_pattern=r"^robocasa_boxed_food_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "slide_cabinet",
            "tray",
            "wooden_two_layer_shelf",
        ],
        valid_articulated_dests=[
            "microwave",
            "slide_cabinet",
        ],
    ),
    "bread": GraspObjectSpec(
        name="bread",
        search_pattern=r"^robocasa_bread_(?!0$|2$|3$|4$|5$|7$|8$|9$|10$|11$|12$|13$|14$|18$|19$|21$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "broccoli": GraspObjectSpec(
        name="broccoli",
        search_pattern=r"^robocasa_broccoli_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "cake": GraspObjectSpec(
        name="cake",
        search_pattern=r"^robocasa_cake_(?!2$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "can": GraspObjectSpec(
        name="can",
        search_pattern=r"^robocasa_can_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "candle": GraspObjectSpec(
        name="candle",
        search_pattern=r"^robocasa_candle_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "canned_food": GraspObjectSpec(
        name="canned_food",
        search_pattern=r"^robocasa_canned_food_\d+$",
        natural_language_plural="cans of food",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "carrot": GraspObjectSpec(
        name="carrot",
        search_pattern=r"^robocasa_carrot_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "cereal": GraspObjectSpec(
        name="cereal",
        search_pattern=r"^robocasa_cereal_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "cabinet",
            "slide_cabinet",
            "tray",
            "wooden_shelf",
            "wooden_two_layer_shelf",
        ],
        valid_articulated_dests=[
            "microwave",
            "slide_cabinet",
        ],
    ),
    "cheese": GraspObjectSpec(
        name="cheese",
        search_pattern=r"^robocasa_cheese_(?!4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "coffee_cup": GraspObjectSpec(
        name="coffee_cup",
        search_pattern=r"^robocasa_coffee_cup_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "condiment": GraspObjectSpec(
        name="condiment",
        search_pattern=r"^robocasa_condiment_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "corn": GraspObjectSpec(
        name="corn",
        search_pattern=r"^robocasa_corn_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "croissant": GraspObjectSpec(
        name="croissant",
        search_pattern=r"^robocasa_croissant_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "cucumber": GraspObjectSpec(
        name="cucumber",
        search_pattern=r"^robocasa_cucumber_(?!4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "cup": GraspObjectSpec(
        name="cup",
        search_pattern=r"^robocasa_cup_(?!4$)\d+$",
        stackable=True,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "bowl_drainer",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "cupcake": GraspObjectSpec(
        name="cupcake",
        search_pattern=r"^robocasa_cupcake_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "donut": GraspObjectSpec(
        name="donut",
        search_pattern=r"^robocasa_donut_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "egg": GraspObjectSpec(
        name="egg",
        search_pattern=r"^robocasa_egg_(?!8$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "eggplant": GraspObjectSpec(
        name="eggplant",
        search_pattern=r"^robocasa_eggplant_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "fish": GraspObjectSpec(
        name="fish",
        search_pattern=r"^robocasa_fish_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "garlic": GraspObjectSpec(
        name="garlic",
        search_pattern=r"^robocasa_garlic_(?!2$)\d+$",
        height=0.02,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "hot_dog": GraspObjectSpec(
        name="hot_dog",
        search_pattern=r"^robocasa_hot_dog_(?!1$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "jam": GraspObjectSpec(
        name="jam",
        search_pattern=r"^robocasa_jam_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "jug": GraspObjectSpec(
        name="jug",
        search_pattern=r"^robocasa_jug_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "ketchup": GraspObjectSpec(
        name="ketchup",
        search_pattern=r"^robocasa_ketchup_(?!4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "kiwi": GraspObjectSpec(
        name="kiwi",
        search_pattern=r"^robocasa_kiwi_(?!4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "lemon": GraspObjectSpec(
        name="lemon",
        search_pattern=r"^robocasa_lemon_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "lime": GraspObjectSpec(
        name="lime",
        search_pattern=r"^robocasa_lime_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "mango": GraspObjectSpec(
        name="mango",
        search_pattern=r"^robocasa_mango_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "milk": GraspObjectSpec(
        name="milk",
        search_pattern=r"^robocasa_milk_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "mug": GraspObjectSpec(
        name="mug",
        search_pattern=r"^(robocasa_mug_(?!0$|3$|7$|10$|12$)\d+|.*_mug)$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "bowl_drainer",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "mushroom": GraspObjectSpec(
        name="mushroom",
        search_pattern=r"^robocasa_mushroom_\d+$",
        height=0.02,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "onion": GraspObjectSpec(
        name="onion",
        search_pattern=r"^robocasa_onion_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "orange": GraspObjectSpec(
        name="orange",
        search_pattern=r"^robocasa_orange_(?!12$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "peach": GraspObjectSpec(
        name="peach",
        search_pattern=r"^robocasa_peach_[0-4]$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "peach_ood": GraspObjectSpec(
        name="peach_ood",
        search_pattern=r"^robocasa_peach_([5-9]|[1-9][0-9]|100)$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=False,
    ),
    "pear": GraspObjectSpec(
        name="pear",
        search_pattern=r"^robocasa_pear_(?!3$|5$|10$|11$|16$|19$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
            "pot",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "plate": GraspObjectSpec(
        name="plate",
        search_pattern=r"^robocasa_plate_(?!7$|8$|20$)\d+$",
        stackable=True,
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "bowl_drainer",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "pepper_shaker": GraspObjectSpec(
        name="pepper_shaker",
        search_pattern=r"^robocasa_pepper_shaker_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "potato": GraspObjectSpec(
        name="potato",
        search_pattern=r"^robocasa_potato_(?!17$|18$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
            "baking_sheet_ai",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "rolling_pin": GraspObjectSpec(
        name="rolling_pin",
        search_pattern=r"^robocasa_rolling_pin_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "pan",
            "basket",
            "bowl_drainer",
            "wooden_shelf",
            "wooden_two_layer_shelf",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "salt_shaker": GraspObjectSpec(
        name="salt_shaker",
        search_pattern=r"^robocasa_salt_shaker_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "soap_dispenser": GraspObjectSpec(
        name="soap_dispenser",
        search_pattern=r"^robocasa_soap_dispenser_(?!2$|4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "sponge": GraspObjectSpec(
        name="sponge",
        search_pattern=r"^robocasa_sponge_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "bowl_drainer",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "spray": GraspObjectSpec(
        name="spray",
        search_pattern=r"^robocasa_spray_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "squash": GraspObjectSpec(
        name="squash",
        search_pattern=r"^robocasa_squash_[0-9]$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "squash_ood": GraspObjectSpec(
        name="squash_ood",
        search_pattern=r"^robocasa_squash_([1-9][0-9]+)$|^robocasa_ai_squash_(?!0$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=False,
    ),
    "sweet_potato": GraspObjectSpec(
        name="sweet_potato",
        search_pattern=r"^robocasa_sweet_potato_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "tangerine": GraspObjectSpec(
        name="tangerine",
        search_pattern=r"^robocasa_tangerine_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "tomato": GraspObjectSpec(
        name="tomato",
        search_pattern=r"^robocasa_tomato_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "water_bottle": GraspObjectSpec(
        name="water_bottle",
        search_pattern=r"^robocasa_water_bottle_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "bowl_drainer",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "wine": GraspObjectSpec(
        name="wine",
        search_pattern=r"^robocasa_wine_[0-9]$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
    ),
    "wine_ood": GraspObjectSpec(
        name="wine_ood",
        search_pattern=r"^robocasa_wine_([1-9][0-9]+)$|^robocasa_ai_wine_(?!3$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=False,
    ),
    "yogurt": GraspObjectSpec(
        name="yogurt",
        search_pattern=r"^robocasa_yogurt_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
    ),
    "apple_ai": GraspObjectSpec(
        name="apple_ai",
        search_pattern=r"^robocasa_ai_apple_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "bar_ai": GraspObjectSpec(
        name="bar_ai",
        search_pattern=r"^robocasa_ai_bar_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "bowl",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "beer_ai": GraspObjectSpec(
        name="beer_ai",
        search_pattern=r"^robocasa_ai_beer_(?!5$|6$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "beet_ai": GraspObjectSpec(
        name="beet_ai",
        search_pattern=r"^robocasa_ai_beet_(?!1$|7$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "cutting_board",
            "plate",
            "bowl",
            "pan",
            "pot",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "bell_pepper_ai": GraspObjectSpec(
        name="bell_pepper_ai",
        search_pattern=r"^robocasa_ai_bell_pepper_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=False,
    ),
    "brussel_sprout_ai": GraspObjectSpec(
        name="brussel_sprout_ai",
        search_pattern=r"^robocasa_ai_brussel_sprout_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "carrot_ai": GraspObjectSpec(
        name="carrot_ai",
        search_pattern=r"^robocasa_ai_carrot_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "cheese_ai": GraspObjectSpec(
        name="cheese_ai",
        search_pattern=r"^robocasa_ai_cheese_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "chili_pepper_ai": GraspObjectSpec(
        name="chili_pepper_ai",
        search_pattern=r"^robocasa_ai_chili_pepper_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "fish_ai": GraspObjectSpec(
        name="fish_ai",
        search_pattern=r"^robocasa_ai_fish_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "ginger_ai": GraspObjectSpec(
        name="ginger_ai",
        search_pattern=r"^robocasa_ai_ginger_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "grapes_ai": GraspObjectSpec(
        name="grapes_ai",
        search_pattern=r"^robocasa_ai_grapes_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "ice_cream_ai": GraspObjectSpec(
        name="ice_cream_ai",
        search_pattern=r"^robocasa_ai_ice_cream_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "ice_cube_tray_ai": GraspObjectSpec(
        name="ice_cube_tray_ai",
        search_pattern=r"^robocasa_ai_ice_cube_tray_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "jam_ai": GraspObjectSpec(
        name="jam_ai",
        search_pattern=r"^robocasa_ai_jam_(?!17$|18$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "kebabs_ai": GraspObjectSpec(
        name="kebabs_ai",
        search_pattern=r"^robocasa_ai_kebabs_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "mushroom_ai": GraspObjectSpec(
        name="mushroom_ai",
        search_pattern=r"^robocasa_ai_mushroom_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "olive_oil_bottle_ai": GraspObjectSpec(
        name="olive_oil_bottle_ai",
        search_pattern=r"^robocasa_ai_olive_oil_bottle_(?!7$|11$|12$)\d+$",
        natural_language="olive oil",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "orange_ai": GraspObjectSpec(
        name="orange_ai",
        search_pattern=r"^robocasa_ai_orange_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "pomegranate_ai": GraspObjectSpec(
        name="pomegranate_ai",
        search_pattern=r"^robocasa_ai_pomegranate_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "potato_ai": GraspObjectSpec(
        name="potato_ai",
        search_pattern=r"^robocasa_ai_potato_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "radish_ai": GraspObjectSpec(
        name="radish_ai",
        search_pattern=r"^robocasa_ai_radish_(?!0$|4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "cutting_board",
            "plate",
            "bowl",
            "pan",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "raspberry_ai": GraspObjectSpec(
        name="raspberry_ai",
        search_pattern=r"^robocasa_ai_raspberry_(?!4$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "sausage_ai": GraspObjectSpec(
        name="sausage_ai",
        search_pattern=r"^robocasa_ai_sausage_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
            "baking_sheet_ai",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "scone_ai": GraspObjectSpec(
        name="scone_ai",
        search_pattern=r"^robocasa_ai_scone_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "squash_ai": GraspObjectSpec(
        name="squash_ai",
        search_pattern=r"^robocasa_ai_squash_(?!0$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "pan",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "strawberry_ai": GraspObjectSpec(
        name="strawberry_ai",
        search_pattern=r"^robocasa_ai_strawberry_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "bowl",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "sushi_ai": GraspObjectSpec(
        name="sushi_ai",
        search_pattern=r"^robocasa_ai_sushi_(?!2$)\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "plate",
            "tray",
            "basket",
            "cutting_board",
        ],
        valid_articulated_dests=[
            "microwave",
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
    "thermos_ai": GraspObjectSpec(
        name="thermos_ai",
        search_pattern=r"^robocasa_ai_thermos_\d+$",
        valid_dests=[
            "wooden_shelf_top",
            "wooden_two_layer_shelf_top",
            "microwave",
            "cabinet",
            "slide_cabinet",
            "tray",
            "basket",
            "bowl_drainer",
        ],
        valid_articulated_dests=[
            "cabinet",
            "slide_cabinet",
            "sliding_top_box",
        ],
        is_valid_distractor=USE_AI_AS_DISTRACTORS,
    ),
}


DEST_OBJECTS = {
    "bowl": DestObjectSpec(
        name="bowl",
        search_pattern=r"^(robocasa_bowl_(?!7$)\d+|.*_bowl)$",
        regions=[
            "on",
        ],
        regions_natural=[
            "in",
        ],
    ),
    "plate": DestObjectSpec(
        name="plate",
        search_pattern=r"^(robocasa_plate_\d+|.*_plate)$",
        regions=[
            "on",
        ],
        regions_natural=[
            "on",
        ],
    ),
    "plate_ai": DestObjectSpec(
        name="plate_ai",
        search_pattern=r"^robocasa_ai_plate_\d+$",
        regions=[
            "on",
        ],
        regions_natural=[
            "on",
        ],
    ),
    "tray": DestObjectSpec(
        name="tray",
        search_pattern=r"^(robocasa_tray_\d+|wooden_tray)$",
        regions=[
            "on",
        ],
        regions_natural=[
            "on",
        ],
    ),
    "tray_ai": DestObjectSpec(
        name="tray_ai",
        search_pattern=r"^robocasa_ai_tray_\d+$",
        regions=[
            "on",
        ],
        regions_natural=[
            "on",
        ],
    ),
    "baking_sheet_ai": DestObjectSpec(
        name="baking_sheet_ai",
        search_pattern=r"^robocasa_ai_baking_sheet_\d+$",
        regions=[
            "on",
        ],
        regions_natural=[
            "on",
        ],
    ),
    "pan": DestObjectSpec(
        name="pan",
        search_pattern=r"^(robocasa_pan_(?!6$|9$)\d+|chefmate_8_frypan)$",
        regions=[
            "on",
        ],
        regions_natural=[
            "in",
        ],
    ),
    "pan_ai": DestObjectSpec(
        name="pan_ai",
        search_pattern=r"^robocasa_ai_pan_\d+$",
        regions=[
            "on",
        ],
        regions_natural=[
            "in",
        ],
    ),
    "pot": DestObjectSpec(
        name="pot",
        search_pattern=r"^(robocasa_pot_\d+|robocasa_ai_pot_\d+)$",
        regions=[
            "on",
        ],
        regions_natural=[
            "in",
        ],
    ),
    "basket": DestObjectSpec(
        name="basket",
        search_pattern=r"^basket$",
        allow_rotation=False,
        regions=[
            "contain_region",
        ],
        regions_natural=[
            "in",
        ],
    ),
    "cutting_board": DestObjectSpec(
        name="cutting_board",
        search_pattern=r"^robocasa_cutting_board_\d+$",
        regions=[
            "on",
        ],
        regions_natural=[
            "on",
        ],
    ),
    "cutting_board_ai": DestObjectSpec(
        name="cutting_board_ai",
        search_pattern=r"^robocasa_ai_cutting_board_(?!9$)\d+$",
        regions=[
            "on",
        ],
        regions_natural=[
            "on",
        ],
    ),
    "bowl_drainer": DestObjectSpec(
        name="bowl_drainer",
        search_pattern=r"^bowl_drainer$",
        natural_language="dish drainer",
        allow_rotation=False,
        regions=[
            "left_region",
            "right_region",
        ],
        regions_natural=[
            "in the left side of",
            "in the right side of",
        ],
    ),
}


ARTICULATED_OBJECTS = {
    "flat_stove": ArticulatedObjectSpec(
        name="flat_stove",
        search_pattern=r"^flat_stove_\d+$",
        natural_language="stove",
        allow_rotation=False,
        is_valid_distractor=False,
        supports_open_close=False,
        regions=["cook_region"],
        regions_natural=["on"],
    ),
    "microwave": ArticulatedObjectSpec(
        name="microwave",
        search_pattern=r"^microwave_\d+$",
        spawn_region="back",
        length_limit=False,
        allow_rotation=False,
        regions=[
            "heating_region",
        ],
        regions_natural=[
            "in",
        ],
    ),
    "cabinet": ArticulatedObjectSpec(
        name="cabinet",
        search_pattern=r"^cabinet_\d+$",
        spawn_region="back",
        height_limit=0.03,
        length_limit=True,
        allow_rotation=False,
        regions=[
            "top_region",
            "middle_region",
            "bottom_region",
        ],
        regions_natural=[
            "in the top drawer of",
            "in the middle drawer of",
            "in the bottom drawer of",
        ],
        articulation_regions=[
            "top_region",
            "middle_region",
            "bottom_region",
        ],
        articulation_regions_natural=[
            "top drawer",
            "middle drawer",
            "bottom drawer",
        ],
    ),
    "slide_cabinet": ArticulatedObjectSpec(
        name="slide_cabinet",
        search_pattern=r"^slide_cabinet_\d+$",
        spawn_region="back",
        length_limit=False,
        allow_rotation=False,
        regions=[
            "contain_region",
        ],
        regions_natural=[
            "in",
        ],
    ),
    "sliding_top_box": ArticulatedObjectSpec(
        name="sliding_top_box",
        search_pattern=r"^sliding_top_box_\d+$",
        natural_language="box",
        spawn_region="full_table",
        height_limit=0.05,
        length_limit=True,
        regions=[
            "contain_region",
        ],
        regions_natural=[
            "in",
        ],
    ),
}


for name, spec in GRASP_OBJECTS.items():
    new_valid_dests = []
    for dest in spec.valid_dests:
        if dest + "_ai" in DEST_OBJECTS:
            new_valid_dests.append(dest + "_ai")
        new_valid_dests.append(dest)
    spec.valid_dests = new_valid_dests


CONFUSING_OBJECTS_LIST = defaultdict(list)
CONFUSING_OBJECTS_LIST.update({
    "bottled_water": ["water_bottle"],
    "water_bottle": ["bottled_water"],
    "alcohol": ["beer", "wine", "liquor"],
})
for name in GRASP_OBJECTS:
    if '_ai' in name:
        CONFUSING_OBJECTS_LIST[name].append(name.replace("_ai", ""))
        CONFUSING_OBJECTS_LIST[name.replace("_ai", "")].append(name)
    if "_ood" in name:
        CONFUSING_OBJECTS_LIST[name].append(name.replace("_ood", ""))
        CONFUSING_OBJECTS_LIST[name.replace("_ood", "")].append(name)
for name in DEST_OBJECTS:
    if '_ai' in name:
        CONFUSING_OBJECTS_LIST[name].append(name.replace("_ai", ""))
        CONFUSING_OBJECTS_LIST[name.replace("_ai", "")].append(name)
    




def get_grasp_object_spec(object_name: str) -> GraspObjectSpec:
    return copy.deepcopy(GRASP_OBJECTS[object_name])

def get_dest_object_spec(object_name: str) -> DestObjectSpec:
    return copy.deepcopy(DEST_OBJECTS[object_name])

def get_articulated_object_spec(object_name: str) -> ArticulatedObjectSpec:
    return copy.deepcopy(ARTICULATED_OBJECTS[object_name])


def register_spatial_gen_object(object_name: str):
    base_object: GraspObjectSpec = GRASP_OBJECTS[object_name]
    left = copy.deepcopy(base_object)
    left.spawn_region = "left"
    right = copy.deepcopy(base_object)
    right.spawn_region = "right"
    GRASP_OBJECTS[f"{object_name}_left"] = left
    GRASP_OBJECTS[f"{object_name}_right"] = right
    CONFUSING_OBJECTS_LIST[f'{object_name}_right'].append(f"{object_name}_left")
    CONFUSING_OBJECTS_LIST[f'{object_name}_right'].append(object_name)
    CONFUSING_OBJECTS_LIST[f'{object_name}_left'].append(f"{object_name}_right")
    CONFUSING_OBJECTS_LIST[f'{object_name}_left'].append(object_name)
    CONFUSING_OBJECTS_LIST[object_name].append(f"{object_name}_right")
    CONFUSING_OBJECTS_LIST[object_name].append(f"{object_name}_left")
