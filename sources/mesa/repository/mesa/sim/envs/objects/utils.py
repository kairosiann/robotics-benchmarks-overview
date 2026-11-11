import re
from typing import Iterable, Dict

from mesa.sim.envs.objects.object_info import (
    OBJ_INFO, 
    NON_ROBOCASA_CATEGORY_MAP,
    VERTICAL_CATEGORIES, 
    SEMISPHERICAL_CATEGORIES, 
    CYLINDRICAL_CATEGORIES,
    STACKABLE_XY_THRESHOLDS,
    STACKABLE_Z_THRESHOLDS,
    VERTICAL_INSERT_CATEGORIES,
    HORIZONTAL_INSERT_CATEGORIES,
)


PREFIXES = ("robocasa_", "objaverse_")
COLORS = {
    "white","black","blue","yellow","red","green","orange","brown","gray","grey",
    "marble","lava","metal","colorful","light","dark"
}
PROPER = {"akita","chefmate"}  # capitalize these when present

# Only tokens where key != value. Default fallback uses the key.
TOKEN_MAP = {
    "frypan": "frying pan",
    "bbq": "barbecue",
    "mayo": "mayonnaise",
}

FULL_MAP = {
    "short_fridge": "mini fridge",
    "flat_stove": "stovetop",
    "wine_bottle": "wine bottle",
    "wine_rack": "wine rack",
    "desk_caddy": "desk caddy",
    "bowl_drainer": "bowl drainer",
    "glazed_rim_porcelain_ramekin": "glazed-rim porcelain ramekin",
    "dining_set_group": "dining set",
    "white_yellow_mug": "white and yellow mug",
}

def _strip_prefixes(s: str) -> str:
    for p in PREFIXES:
        if s.startswith(p):
            return s[len(p):]
    return s

def _strip_trailing_index(s: str) -> str:
    return re.sub(r"_\d+$", "", s)

def _tokens(name: str):
    return [t for t in name.split("_") if t]

def _capitalize_proper(tokens):
    return [t.capitalize() if t in PROPER else t for t in tokens]

def _merge_two_layer(tokens):
    out, i = [], 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i] == "two" and tokens[i+1] == "layer":
            out.append("two-layer")
            i += 2
        else:
            out.append(tokens[i])
            i += 1
    return out

def _size_token_as_inches(tokens):
    out = []
    for i, t in enumerate(tokens):
        if t.isdigit() and i + 1 < len(tokens):
            out.append(f"{t}-inch")
        else:
            out.append(t)
    return out

def _join_colors(tokens):
    if not tokens:
        return tokens
    i = 0
    while i < len(tokens) and tokens[i] in COLORS:
        i += 1
    if i >= 2 and i < len(tokens):
        colors = " and ".join(tokens[:i])
        return [colors] + tokens[i:]
    return tokens

def _map_tokens(tokens):
    out = []
    for t in tokens:
        rep = TOKEN_MAP.get(t, t)
        out.extend(rep.split() if " " in rep else [rep])
    return out

def humanize_id(name: str) -> str:
    s = name.lower()
    s = _strip_prefixes(_strip_trailing_index(s))
    if s in FULL_MAP:
        return FULL_MAP[s]
    toks = _tokens(s)
    toks = _map_tokens(toks)
    toks = _join_colors(toks)
    toks = _size_token_as_inches(toks)
    toks = _capitalize_proper(toks)
    toks = _merge_two_layer(toks)
    phrase = " ".join(toks)
    phrase = phrase.replace("light wood", "light-wood")
    return re.sub(r"\s+", " ", phrase).strip()

def names_to_natural(names: Iterable[str]) -> Dict[str, str]:
    return {n: humanize_id(n) for n in names}

def get_category(name: str) -> str:
    is_robocasa = "robocasa" in name
    name = _strip_prefixes(_strip_trailing_index(name))

    # if 'cabinet' in name and 'slide' not in name:
    #     breakpoint()

    if is_robocasa:
        category_name = fix_robocasa_category_name(name)
    elif name in NON_ROBOCASA_CATEGORY_MAP:
        category_name = NON_ROBOCASA_CATEGORY_MAP[name]
    else:
        category_name = name
    return category_name


def fix_robocasa_category_name(name: str) -> str:
    """
    Fix the name of the robocasa object to the correct category name.
    """
    if name == "alcohol":
        return "liquor"
    elif name == "kettle":
        return "kettle_electric"
    elif name == "condiment":
        return "condiment_bottle"
    return name


# TODO: refactor so this is a method that makes sense for all objects
def get_obj_info(object_name):
    if object_name is None:
        return None
    
    try:
        category = get_category(object_name)
        obj_info = OBJ_INFO[category]

        if object_name in STACKABLE_XY_THRESHOLDS:
            obj_info["stack_xy_threshold"] = STACKABLE_XY_THRESHOLDS[object_name]
        if object_name in STACKABLE_Z_THRESHOLDS:
            obj_info["stack_z_threshold"] = STACKABLE_Z_THRESHOLDS[object_name]

        return obj_info
    except KeyError:  # currently this will cover non robocasa object cases
        return {}

def get_shape_category(name: str) -> str:
    category = get_category(name)
    if category in VERTICAL_CATEGORIES:
        return "vertical"
    elif category in SEMISPHERICAL_CATEGORIES:
        return "semispherical"
    elif category in CYLINDRICAL_CATEGORIES:
        return "cylindrical"
    else:
        return "unknown"

def get_insertion_category(name: str) -> str:
    if name in VERTICAL_INSERT_CATEGORIES:
        return "vertical"
    elif name in HORIZONTAL_INSERT_CATEGORIES:
        return "horizontal"
    else:
        return "unknown"