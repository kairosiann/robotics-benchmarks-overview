import os
import re
from collections import defaultdict

import numpy as np
from mesa.sim.envs.objects.robocasa_mjcf_object import MJCFObject
from robosuite.utils.mjcf_utils import string_to_array

from mesa.sim import ASSETS_ROOT
from mesa.sim.envs.objects.utils import get_category, get_obj_info

from .base_object import (
    BaseObject,
    register_graspable_object,
    register_object,
    register_on_object,
    register_stackable_object,
)

MESA_ASSET_PATH = os.path.join(ASSETS_ROOT, "objects", "robocasa")
MESA_AI_ASSET_PATH = os.path.join(ASSETS_ROOT, "objects", "robocasa_ai")

BIMESA_ASSET_PATH = os.path.join(ASSETS_ROOT, "objects", "objaverse")
BIMESA_AI_ASSET_PATH = os.path.join(ASSETS_ROOT, "objects", "aigen_objs")

SCALE_MAP_MESA = defaultdict(lambda: None)
SCALE_MAP_MESA.update({
    "bell_pepper_1": 0.9, # makes it much easier to grasp
    "bar_0": 0.8, # The original asset is just a bit too big
    "bar_2": 0.6, # The original asset is an absurdly large snickers bar
    "bar_3": 0.8, # The original asset is just a bit too big
    "bar_4": 0.8, # The original asset is just a bit too big
    "bar_6": 0.8, # The original asset is just a bit too big
    "bar_7": 0.8, # The original asset is just a bit too big
    "bar_8": 0.8, # The original asset is just a bit too big
    "bar_9": 0.8, # The original asset is just a bit too big
    "bar_10": 0.8, # The original asset is just a bit too big
    "bar_11": 0.8, # The original asset is just a bit too big
})

SCALE_MAP_AI_MESA = defaultdict(lambda: None)
SCALE_MAP_AI_MESA.update({
    "baking_sheet_2": 1.4, # The original asset is just a bit too small
    "tray_1": 1.6, # The original asset is just a bit too small
    "tray_4": 1.6, # The original asset is just a bit too small
    "tray_5": 1.6, # The original asset is just a bit too small
    "tray_6": 1.6, # The original asset is just a bit too small
    "tray_9": 1.6, # The original asset is just a bit too small
    "cutting_board_0": 1.8,
    "cutting_board_1": 1.8,
    "cutting_board_2": 1.8,
    "cutting_board_3": 1.8,
    "cutting_board_4": 1.8,
    "cutting_board_5": 1.8,
    "cutting_board_6": 1.8,
    "cutting_board_7": 1.8,
    "cutting_board_8": 1.8,
    "cutting_board_10": 1.8,
    "pot": 2.25,
    "squash_0": 0.7,
    "beet_2": 0.8,
})

# BiMESA objaverse objects are unscaled (x1.0); these override maps stay empty.
SCALE_MAP_BIMESA = defaultdict(lambda: None)
SCALE_MAP_AI_BIMESA = defaultdict(lambda: None)

# BiMESA aigen scales bypass OBJ_INFO (which holds MESA's single-arm values) so both
# formats can share one object_info.py; these reproduce the published BiMESA baseline.
BIMESA_AIGEN_SCALE = {
    "bowl": 1.75,
    "coffee_cup": 1.35,
    "cup": 1.35,
    "cutting_board": 2.0,
    "mug": 1.3,
    "pan": 2.25,
    "pot": 2.25,
    "plate": 1.65,
    "tray": 2.0,
    "pitcher": 1.75,
    "ice_cube_tray": 2.0,
    "baking_sheet": 1.75,
}


class RobocasaObjectMesa(BaseObject):
    """MESA (single-arm) robocasa365 object: model.xml with bottom/top/
    horizontal_radius sites, curated collision decomposition."""

    def __init__(
        self,
        relative_path,
        name,
        joints=[dict(type="free", damping="0.0005")],
        scale=None,
    ):
        super().__init__(
            os.path.join(MESA_ASSET_PATH, relative_path),
            name=name,
            joints=joints,
            obj_type="all",
            duplicate_collision_geoms=True,
            scale=scale,
        )
        self.category_name = "_".join(
            re.sub(r"([A-Z]|\d+)", r" \1", self.__class__.__name__).split()
        ).lower()
        self.rotation = None
        self.rotation_axis = "x"

        articulation_object_properties = {
            "default_open_ranges": [],
            "default_close_ranges": [],
        }
        self.object_properties = {
            "articulation": articulation_object_properties,
            "vis_site_names": {},
        }


class RobocasaObjectBimesa(MJCFObject):
    """BiMESA (bimanual) robocasa365 object adapter.

    Inherits from robocasa's MJCFObject which natively handles the robocasa365
    asset format (reg_bbox, collision class defaults, scaling). Adds the
    horizontal_offset property and object metadata needed by mesa.
    """

    def __init__(self, mjcf_path, name, scale=None):
        super().__init__(
            name=name,
            mjcf_path=mjcf_path,
            scale=scale if scale is not None else 1.0,
        )
        self.category_name = "_".join(
            re.sub(r"([A-Z]|\d+)", r" \1", self.__class__.__name__).split()
        ).lower()
        self.rotation = None
        self.rotation_axis = "x"

        self.object_properties = {
            "articulation": {
                "default_open_ranges": [],
                "default_close_ranges": [],
            },
            "vis_site_names": {},
        }

    @property
    def horizontal_offset(self) -> np.ndarray:
        """Half-extents of the bounding box as (hx, hy, hz).

        Used by OBB collision tests, placement sorting, and containment checks.
        Computed from the reg_bbox region set up by MJCFObject._setup_region_dict.
        """
        size = string_to_array(self._regions["bbox"]["elem"].get("size"))
        return np.array([size[0], size[1], 0.0])


# Alias kept for the front-door script (scripts/utility/add_robocasa_object.py).
RobocasaObject = RobocasaObjectBimesa


def _list_asset_dirs(base_path):
    """List the per-object directories (depth 1) under an asset tree."""
    asset_dirs = []
    for root, dirs, _ in os.walk(base_path):
        depth = root[len(base_path):].count(os.sep)
        if depth == 1:
            for dir_name in dirs:
                full_path = os.path.join(root, dir_name)
                asset_dirs.append(os.path.relpath(full_path, base_path))
    return asset_dirs


def _register_aux(cls, obj_info):
    if obj_info["graspable"]:
        register_graspable_object(cls)
    if obj_info["on_dest"]:
        register_on_object(cls)
    if obj_info["types"] and "stackable" in obj_info["types"]:
        xy_threshold = obj_info["stack_xy_threshold"] if "stack_xy_threshold" in obj_info else 0.03
        z_threshold = obj_info["stack_z_threshold"] if "stack_z_threshold" in obj_info else 0.07
        register_stackable_object(cls, xy_threshold=xy_threshold, z_threshold=z_threshold)


def _make_init_mesa(xml_path, default_name, base_cls, scale):
    def __init__(self, *args, name=default_name, joints=None, scale=scale, **kwargs):
        if joints is None:
            joints = [dict(type="free")]
        base_cls.__init__(self, xml_path, *args, name=name, joints=joints, scale=scale, **kwargs)
    return __init__


def register_mesa_object(asset_dir, is_ai=False):
    last = asset_dir.split(os.sep)[-1]
    obj_info = get_obj_info(f'robocasa_{last}')

    if is_ai:
        scale = SCALE_MAP_AI_MESA[last]
        if scale is None and 'scale' in obj_info['aigen']:
            scale = obj_info['aigen']['scale']

        class_name = f"RobocasaAI{last.title().replace('_', '')}"
        default_name = f"robocasa_ai_{last}"
        xml_path = os.path.join(MESA_AI_ASSET_PATH, asset_dir, "model.xml")
    else:
        if 'exclude' in obj_info['objaverse'] and \
            last in obj_info['objaverse']['exclude']:
            return

        scale = SCALE_MAP_MESA[last]

        class_name = f"Robocasa{last.title().replace('_', '')}"
        default_name = f"robocasa_{last}"
        xml_path = os.path.join(MESA_ASSET_PATH, asset_dir, "model.xml")

    cls = type(
        class_name,
        (RobocasaObjectMesa,),
        {
            "__init__": _make_init_mesa(xml_path, default_name, RobocasaObjectMesa, scale=scale),
            "__module__": __name__,
        },
    )

    register_object(cls, object_format="mesa")
    _register_aux(cls, obj_info)


def _make_init_bimesa(xml_path, default_name, base_cls, scale):
    def __init__(self, *args, name=default_name, scale=scale, **kwargs):
        base_cls.__init__(self, mjcf_path=xml_path, *args, name=name, scale=scale, **kwargs)
    return __init__


def register_bimesa_object(asset_dir, is_ai=False):
    last = asset_dir.split(os.sep)[-1]

    obj_info = get_obj_info(f'robocasa_{last}')

    if not obj_info:
        return

    if is_ai:
        scale = SCALE_MAP_AI_BIMESA[last]
        if scale is None:
            scale = BIMESA_AIGEN_SCALE.get(get_category(f"robocasa_{last}"))

        class_name = f"RobocasaAI{last.title().replace('_', '')}"
        default_name = f"robocasa_ai_{last}"
        xml_path = os.path.join(BIMESA_AI_ASSET_PATH, asset_dir, "model.xml")
    else:
        objaverse_info = obj_info.get('objaverse', {})
        if 'exclude' in objaverse_info and \
            last in objaverse_info['exclude']:
            return

        scale = SCALE_MAP_BIMESA[last]

        class_name = f"Robocasa{last.title().replace('_', '')}"
        default_name = f"robocasa_{last}"
        xml_path = os.path.join(BIMESA_ASSET_PATH, asset_dir, "model.xml")

    cls = type(
        class_name,
        (RobocasaObjectBimesa,),
        {
            "__init__": _make_init_bimesa(xml_path, default_name, RobocasaObjectBimesa, scale=scale),
            "__module__": __name__,
        },
    )

    register_object(cls, object_format="bimesa")
    _register_aux(cls, obj_info)


# Discover and register all robocasa365 objects in both formats.
for asset_dir in _list_asset_dirs(MESA_ASSET_PATH):
    register_mesa_object(asset_dir, is_ai=False)
for asset_dir in _list_asset_dirs(MESA_AI_ASSET_PATH):
    register_mesa_object(asset_dir, is_ai=True)

for asset_dir in _list_asset_dirs(BIMESA_ASSET_PATH):
    register_bimesa_object(asset_dir, is_ai=False)
for asset_dir in _list_asset_dirs(BIMESA_AI_ASSET_PATH):
    register_bimesa_object(asset_dir, is_ai=True)
