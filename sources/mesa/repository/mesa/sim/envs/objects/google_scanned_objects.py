import os
import pathlib
import re

import numpy as np

from .base_object import (
    BaseObject,
    register_graspable_object,
    register_in_object,
    register_object,
    register_on_object,
)

absolute_path = pathlib.Path(__file__).parent.parent.parent.absolute()


class GoogleScannedObject(BaseObject):
    def __init__(self, name, obj_name, joints=[dict(type="free", damping="0.0005")]):
        super().__init__(
            os.path.join(
                str(absolute_path),
                f"assets/objects/stable_scanned_objects/{obj_name}/{obj_name}.xml",
            ),
            name=name,
            joints=joints,
            obj_type="all",
            duplicate_collision_geoms=False,
        )
        self.category_name = "_".join(
            re.sub(r"([A-Z])", r" \1", self.__class__.__name__).split()
        ).lower()
        self.rotation = None
        self.rotation_axis = "x"
        self.object_properties = {"vis_site_names": {}}


@register_object
@register_graspable_object
class WhiteBowl(GoogleScannedObject):
    def __init__(self, name="white_bowl", obj_name="white_bowl"):
        super().__init__(name, obj_name)


@register_object
@register_graspable_object
class AkitaBlackBowl(GoogleScannedObject):
    def __init__(self, name="akita_black_bowl", obj_name="akita_black_bowl"):
        super().__init__(name, obj_name)


@register_object
@register_in_object(regions=["contain_region"])
class Basket(GoogleScannedObject):
    def __init__(self, name="basket", obj_name="basket"):
        super().__init__(name, obj_name)
        self.rotation = (np.pi / 2, np.pi / 2)


@register_object
@register_graspable_object
@register_on_object
class Chefmate8Frypan(GoogleScannedObject):
    def __init__(self, name="chefmate_8_frypan", obj_name="chefmate_8_frypan"):
        super().__init__(name, obj_name)


@register_object
@register_graspable_object
class GlazedRimPorcelainRamekin(GoogleScannedObject):
    def __init__(
        self,
        name="glazed_rim_porcelain_ramekin",
        obj_name="glazed_rim_porcelain_ramekin",
    ):
        super().__init__(name, obj_name)
