"""
Mapping texture filenames to their style names for floors and walls in MimicLabs
environments. This includes styles added in MimicLabs as well as those packaged
with LIBERO.
"""

import os

from natsort import natsorted

from mesa.sim import ASSETS_ROOT

TEXTURE_ROOT = os.path.join(ASSETS_ROOT, "textures")

TYPE_ROOTS = {
    "floor": os.path.join(TEXTURE_ROOT, "floors"),
    "wall": os.path.join(TEXTURE_ROOT, "walls"),
    "table": os.path.join(TEXTURE_ROOT, "tables"),
}

ALL_FLOORS = natsorted([x for x in os.listdir(os.path.join(TEXTURE_ROOT, "floors")) if x.endswith('.png')])
ALL_WALLS = natsorted([x for x in os.listdir(os.path.join(TEXTURE_ROOT, "walls")) if x.endswith('.png')])
ALL_TABLES = natsorted([x for x in os.listdir(os.path.join(TEXTURE_ROOT, "tables")) if x.endswith('.png')])
ALL_TYPES = {
    "floor": ALL_FLOORS,
    "wall": ALL_WALLS,
    "table": ALL_TABLES,
}

def get_num_styles(type_name):
    assert type_name in ALL_TYPES.keys()
    return len(ALL_TYPES[type_name])


def get_style_from_index(type_name, index):
    assert type_name in ALL_TYPES.keys()
    return ALL_TYPES[type_name][index][:-4] # remove .png extension


def get_texture_path(type_name, style=None):
    assert type_name in ALL_TYPES.keys()
    if style is not None and type(style) is str:
        return os.path.join(TYPE_ROOTS[type_name], f'{style}.png')
    elif style is not None and type(style) is int:
        style_name = get_style_from_index(type_name, style)
        return os.path.join(TYPE_ROOTS[type_name], f"{style_name}.png")
    else:
        raise ValueError(f"Invalid style type: {type(style)}")