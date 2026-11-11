import os
import re
import xml.etree.ElementTree as ET

import numpy as np
from natsort import natsorted

from mesa.sim import ASSETS_ROOT

from .base_object import (
    BaseObject,
    register_fixture,
    register_in_object,
    register_object,
    register_on_object,
    register_visual_change_object,
)


class ArticulatedObject(BaseObject):
    def __init__(self, name, obj_name=None, rotation=None, joints=[dict(type="free", damping="0.0005")], xml_path=None):
        super().__init__(
            xml_path if xml_path is not None else os.path.join(str(ASSETS_ROOT), f"objects/articulated_objects/{obj_name}.xml"),
            name=name,
            joints=joints,
            obj_type="all",
            duplicate_collision_geoms=False,
        )
        self.category_name = "_".join(
            re.sub(r"([A-Z])", r" \1", self.__class__.__name__).split()
        ).lower()
        self.rotation = rotation
        self.rotation_axis = "x"

        articulation_object_properties = {
            "default_open_ranges": [],
            "default_close_ranges": [],
        }
        self.object_properties = {
            "articulation": articulation_object_properties,
            "vis_site_names": {},
        }

    # Generic texture override applier; subclasses can call this during __init__
    def _apply_texture_overrides(self, overrides):
        if not overrides:
            return
        # Convert to absolute paths and set on textures with matching names
        base_dir = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects")
        for tex in self.asset.findall("./texture"):
            tex_name = tex.get("name")
            # Texture names are prefixed by robosuite with self.naming_prefix; match both raw and stripped names
            raw_name = tex_name[len(self.naming_prefix):] if tex_name and tex_name.startswith(self.naming_prefix) else tex_name
            override_key = None
            if tex_name in overrides:
                override_key = tex_name
            elif raw_name in overrides:
                override_key = raw_name
            if override_key is not None:
                path_rel = overrides[override_key]
                abs_path = path_rel if os.path.isabs(path_rel) else os.path.join(base_dir, path_rel)
                tex.set("file", abs_path)

        # Handle overrides for textures that don't exist in the base XML: create them and link materials
        for key_name, path_rel in overrides.items():
            # Determine prefixed texture name that materials will reference
            pref_name = self.naming_prefix + key_name
            # Check if texture already exists (prefixed or raw)
            tex_el = None
            for cand_name in (pref_name, key_name):
                tex_el = next((t for t in self.asset.findall("./texture") if t.get("name") == cand_name), None)
                if tex_el is not None:
                    break
            if tex_el is None:
                abs_path = path_rel if os.path.isabs(path_rel) else os.path.join(base_dir, path_rel)
                tex_el = ET.Element("texture", attrib={
                    "name": pref_name,
                    "type": "cube",
                    "height": "1",
                    "width": "1",
                    "file": abs_path,
                })
                self.asset.append(tex_el)
            # If this is the black texture, ensure micro_black material references it
            if key_name == "T_micro_black":
                for mat in self.asset.findall("./material"):
                    mat_name = mat.get("name") or ""
                    if mat_name == self.naming_prefix + "micro_black" or mat_name == "micro_black":
                        mat.set("texture", tex_el.get("name"))

    def is_open(self, qpos):
        raise NotImplementedError

    def is_close(self, qpos):
        raise NotImplementedError


def _make_articulated_class(
    class_name,
    obj_name,
    regions,
    *,
    xml_path=None,
    texture_overrides=None,
    default_open_ranges=None,
    default_close_ranges=None,
    rotation=None,
):
    def __init__(self, name=obj_name, obj_name_arg=obj_name, joints=[dict(type="free", damping="0.0005")], xml_path_arg=xml_path):
        ArticulatedObject.__init__(self, name, obj_name_arg, rotation, joints, xml_path=xml_path_arg)
        # Apply any texture overrides defined on the class
        self._apply_texture_overrides(getattr(self.__class__, "TEXTURE_OVERRIDES", None))
        if default_open_ranges is not None:
            self.object_properties["articulation"]["default_open_ranges"] = list(default_open_ranges)
        if default_close_ranges is not None:
            self.object_properties["articulation"]["default_close_ranges"] = list(default_close_ranges)

    def is_open(self, qpos):
        articulation = self.object_properties["articulation"]
        open_ranges = articulation.get("default_open_ranges")
        if not open_ranges:
            return False
        open_min = min(open_ranges)
        open_max = max(open_ranges)
        return open_min <= qpos <= open_max

    def is_close(self, qpos):
        articulation = self.object_properties["articulation"]
        close_ranges = articulation.get("default_close_ranges")
        if not close_ranges:
            return False
        close_min = min(close_ranges)
        close_max = max(close_ranges)
        return close_min <= qpos <= close_max

    cls_dict = {
        "__init__": __init__,
        "is_open": is_open,
        "is_close": is_close,
        "__module__": __name__,
    }

    # Attach helpers on the class definition itself so they're available at instantiation
    if texture_overrides is not None:
        cls_dict["TEXTURE_OVERRIDES"] = texture_overrides
    cls = type(class_name, (ArticulatedObject,), cls_dict)
    # Apply decorators programmatically to mimic @register_*
    cls = register_object(cls)
    cls = register_on_object(cls)
    cls = register_in_object(regions=regions)(cls)
    cls = register_fixture(cls)
    return cls


def _make_stove_class(class_name, obj_name, regions=["cook_region"], *, xml_path=None, texture_overrides=None):
    def __init__(self, name=obj_name, obj_name_arg=obj_name, joints=[dict(type="free", damping="0.0005")], xml_path_arg=xml_path):
        ArticulatedObject.__init__(self, name, obj_name_arg, joints=joints, xml_path=xml_path_arg)
        # The released stove XML reuses the knob texture name for the button.
        knob_texture = self.naming_prefix + "tex-stove_knob"
        textures = [tex for tex in self.asset.findall("./texture") if tex.get("name") == knob_texture]
        if len(textures) == 2:
            button_texture = knob_texture + "_button"
            textures[1].set("name", button_texture)
            for material in self.asset.findall("./material"):
                if material.get("name") == self.naming_prefix + "stove_knob_button":
                    material.set("texture", button_texture)
        self.rotation = (0.0, 0.0)
        self.rotation_axis = "z"

        tracking_sites_dict = {}
        tracking_sites_dict["burner"] = (self.naming_prefix + "burner", False)
        self.object_properties["vis_site_names"].update(tracking_sites_dict)
        self.object_properties["articulation"]["default_turnon_ranges"] = [0.5, 2.1]
        self.object_properties["articulation"]["default_turnoff_ranges"] = [-0.005, 0.0]

        # Apply any texture overrides defined on the class
        self._apply_texture_overrides(getattr(self.__class__, "TEXTURE_OVERRIDES", None))

    def turn_on(self, qpos):
        if min(self.object_properties["articulation"]["default_turnon_ranges"]) <= qpos <= max(self.object_properties["articulation"]["default_turnon_ranges"]):
            self.object_properties["vis_site_names"]["burner"] = (
                self.naming_prefix + "burner",
                True,
            )
            return True
        else:
            self.object_properties["vis_site_names"]["burner"] = (
                self.naming_prefix + "burner",
                False,
            )
            return False

    def turn_off(self, qpos):
        if min(self.object_properties["articulation"]["default_turnoff_ranges"]) <= qpos <= max(self.object_properties["articulation"]["default_turnoff_ranges"]):
            self.object_properties["vis_site_names"]["burner"] = (
                self.naming_prefix + "burner",
                False,
            )
            return True
        else:
            self.object_properties["vis_site_names"]["burner"] = (
                self.naming_prefix + "burner",
                True,
            )
            return False

    cls_dict = {
        "__init__": __init__,
        "turn_on": turn_on,
        "turn_off": turn_off,
        "__module__": __name__,
    }
    if texture_overrides is not None:
        cls_dict["TEXTURE_OVERRIDES"] = texture_overrides

    cls = type(class_name, (ArticulatedObject,), cls_dict)
    cls = register_object(cls)
    cls = register_in_object(regions=regions)(cls)
    cls = register_fixture(cls)
    cls = register_visual_change_object(cls)
    return cls

def _list_textures(name, exclude=[]):
    path = os.path.join(str(ASSETS_ROOT), "textures", name)
    return [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f not in exclude]


MICROWAVE_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "microwave.xml")
CABINET_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "blue_cabinet.xml")
SLIDE_CABINET_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "wooden_slide_cabinet.xml")
SLIDING_TOP_BOX_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "sliding_top_box.xml")
MICROWAVE_MIRROR_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "microwave_mirror.xml")
CABINET_MIRROR_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "blue_cabinet_mirror.xml")
SLIDE_CABINET_MIRROR_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "wooden_slide_cabinet_mirror.xml")
SLIDING_TOP_BOX_MIRROR_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "sliding_top_box_mirror.xml")
SHORT_FRIDGE_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "short_fridge.xml")
FLAT_STOVE_BASE_XML = os.path.join(str(ASSETS_ROOT), "objects", "articulated_objects", "flat_stove.xml")


wood_textures = natsorted(_list_textures("wood"))
metal_textures = natsorted(_list_textures("metal"))
flat_textures = natsorted(_list_textures("flat"))

# This is buggy
wood_textures.remove(os.path.join(str(ASSETS_ROOT), "textures", "wood", "table_light_wood.png"))

microwave_idx = 0
for body_tex in metal_textures:
    for handle_tex in metal_textures:
        class_name = f"Microwave{microwave_idx}"
        _make_articulated_class(
            class_name,
            obj_name=class_name.lower(),
            regions=["heating_region"],
            rotation=(np.pi / 2, np.pi / 2),
            xml_path=MICROWAVE_BASE_XML,
            default_open_ranges=[-2.094, -1.3],
            default_close_ranges=[-0.005, 0.001],
            texture_overrides={
                "T_micro_metal": handle_tex,
                "T_micro_black": body_tex,
            },
        )
        mirror_class_name = f"Microwave{microwave_idx}Mirror"
        _make_articulated_class(
            mirror_class_name,
            obj_name=mirror_class_name.lower(),
            regions=["heating_region"],
            rotation=(np.pi / 2, np.pi / 2),
            xml_path=MICROWAVE_MIRROR_BASE_XML,
            default_open_ranges=[1.3, 2.094],
            default_close_ranges=[-0.001, 0.005],
            texture_overrides={
                "T_micro_metal": handle_tex,
                "T_micro_black": body_tex,
            },
        )
        microwave_idx += 1

cabinet_idx = 0
for body_tex in wood_textures + flat_textures + metal_textures:
    for handle_tex in metal_textures:
        class_name = f"Cabinet{cabinet_idx}"
        overrides = {
            "tex-wooden_cabinet": body_tex,
            "tex-wooden_cabinet_base": body_tex,
            "tex-wooden_cabinet_handle": handle_tex,
        }
        _make_articulated_class(
            class_name,
            obj_name=class_name.lower(),
            regions=["bottom_region", "middle_region", "top_region"],
            rotation=(np.pi / 2, np.pi / 2),
            texture_overrides=overrides,
            default_open_ranges=[-0.16, -0.1],
            default_close_ranges=[0.0, 0.005],
            xml_path=CABINET_BASE_XML,
        )
        mirror_class_name = f"Cabinet{cabinet_idx}Mirror"
        _make_articulated_class(
            mirror_class_name,
            obj_name=mirror_class_name.lower(),
            regions=["bottom_region", "middle_region", "top_region"],
            rotation=(np.pi / 2, np.pi / 2),
            texture_overrides=overrides,
            default_open_ranges=[0.1, 0.16],
            default_close_ranges=[-0.001, 0.01],
            xml_path=CABINET_MIRROR_BASE_XML,
        )
        cabinet_idx += 1

slide_cabinet_idx = 0
for body_tex in wood_textures + flat_textures + metal_textures:
    for handle_tex in metal_textures:
        class_name = f"SlideCabinet{slide_cabinet_idx}"
        overrides = {
            "T_wood": body_tex,
            "T_slide_metal": handle_tex,
        }
        _make_articulated_class(
            class_name,
            obj_name=class_name.lower(),
            regions=["contain_region"],
            rotation=(np.pi / 2, np.pi / 2),
            texture_overrides=overrides,
            default_open_ranges=[0.3, 0.5],
            default_close_ranges=[-0.005, 0.001],
            xml_path=SLIDE_CABINET_BASE_XML,
        )
        mirror_class_name = f"SlideCabinet{slide_cabinet_idx}Mirror"
        _make_articulated_class(
            mirror_class_name,
            obj_name=mirror_class_name.lower(),
            regions=["contain_region"],
            rotation=(np.pi / 2, np.pi / 2),
            texture_overrides=overrides,
            default_open_ranges=[0.3, 0.44],
            default_close_ranges=[-0.005, 0.001],
            xml_path=SLIDE_CABINET_MIRROR_BASE_XML,
        )
        slide_cabinet_idx += 1

sliding_top_box_idx = 0
for body_tex in wood_textures + flat_textures + metal_textures:
    for handle_tex in metal_textures:
        class_name = f"SlidingTopBox{sliding_top_box_idx}"
        overrides = {
            "T_wood": body_tex,
            "T_slide_metal": handle_tex,
        }
        _make_articulated_class(
            class_name,
            obj_name=class_name.lower(),
            regions=["contain_region"],
            rotation=None,
            texture_overrides=overrides,
            default_open_ranges=[0.13, 0.18],
            default_close_ranges=[-0.005, 0.01],
            xml_path=SLIDING_TOP_BOX_BASE_XML,
        )
        mirror_class_name = f"SlidingTopBox{sliding_top_box_idx}Mirror"
        _make_articulated_class(
            mirror_class_name,
            obj_name=mirror_class_name.lower(),
            regions=["contain_region"],
            rotation=None,
            texture_overrides=overrides,
            default_open_ranges=[-0.17, -0.13],
            default_close_ranges=[-0.01, 0.005],
            xml_path=SLIDING_TOP_BOX_MIRROR_BASE_XML,
        )
        sliding_top_box_idx += 1

for flat_stove_idx, metal_tex in enumerate(metal_textures):
    class_name = f"FlatStove{flat_stove_idx}"
    _make_stove_class(
        class_name,
        obj_name=class_name.lower(),
        regions=["cook_region"],
        texture_overrides={"tex-stove_knob": metal_tex, "tex-stove_metal": metal_tex},
        xml_path=FLAT_STOVE_BASE_XML,
    )

# short_fridge_idx = 0
# for body_tex in metal_textures:
#     class_name = f"ShortFridge{short_fridge_idx}"
#     overrides = {
#         "tex-base_vis": body_tex,
#     }
#     _make_articulated_class(
#         class_name,
#         obj_name=class_name.lower(),
#         regions=["lower_region", "middle_region", "upper_region"],
#         default_open_ranges=[2.0, 2.7],
#         default_close_ranges=[-0.005, 0.0],
#         texture_overrides=overrides,
#         xml_path=SHORT_FRIDGE_BASE_XML,
#     )
#     short_fridge_idx += 1

