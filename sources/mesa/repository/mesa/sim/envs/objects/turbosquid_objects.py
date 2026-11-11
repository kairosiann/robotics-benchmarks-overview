import os
import pathlib
import re

import numpy as np

from .base_object import (
    BaseObject,
    register_fixture,
    register_graspable_object,
    register_in_object,
    register_object,
    register_on_object,
)

absolute_path = pathlib.Path(__file__).parent.parent.parent.absolute()


class TurbosquidObjects(BaseObject):
    def __init__(self, name, obj_name, joints=[dict(type="free", damping="0.0005")]):
        super().__init__(
            os.path.join(
                str(absolute_path),
                f"assets/objects/turbosquid_objects/{obj_name}/{obj_name}.xml",
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
@register_on_object
class WoodenTray(TurbosquidObjects):
    def __init__(
        self,
        name="wooden_tray",
        obj_name="wooden_tray",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)


@register_object
@register_in_object(regions=["bottom_region", "middle_region", "top_region"])
@register_fixture
@register_on_object
class WoodenShelf(TurbosquidObjects):
    def __init__(
        self,
        name="wooden_shelf",
        obj_name="wooden_shelf",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)
        self.rotation_axis = "x"
        self.rotation = (np.pi / 2, np.pi / 2)


@register_object
@register_in_object(regions=["bottom_region", "top_region"])
@register_fixture
@register_on_object
class WoodenTwoLayerShelf(TurbosquidObjects):
    def __init__(
        self,
        name="wooden_two_layer_shelf",
        obj_name="wooden_two_layer_shelf",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)
        self.rotation_axis = "x"
        self.rotation = (np.pi / 2, np.pi / 2)

@register_object
@register_in_object(regions=["top_region"])
@register_fixture
class WineRack(TurbosquidObjects):
    def __init__(
        self,
        name="wine_rack",
        obj_name="wine_rack",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)
        self.rotation_axis = "z"


@register_object
@register_in_object(regions=["center_region"])
class DiningSetGroup(TurbosquidObjects):
    """This dining set group is mostly for visualization"""

    def __init__(
        self,
        name="dining_set_group",
        obj_name="dining_set_group",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)


@register_object
@register_in_object(regions=["left_region", "right_region"])
class BowlDrainer(TurbosquidObjects):
    def __init__(
        self,
        name="bowl_drainer",
        obj_name="bowl_drainer",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)
        self.rotation = (0, 0)


@register_object
@register_graspable_object
class BlackBook(TurbosquidObjects):
    def __init__(
        self,
        name="black_book",
        obj_name="black_book",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)
        self.rotation = (-np.pi / 2, -np.pi / 4)


@register_object
@register_graspable_object
class YellowBook(TurbosquidObjects):
    def __init__(
        self,
        name="yellow_book",
        obj_name="yellow_book",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)
        self.rotation = (-np.pi / 2, -np.pi / 4)




@register_object
@register_in_object(
    regions=[
        "left_contain_region",
        "right_contain_region",
        "front_contain_region",
        "back_contain_region",
    ]
)
@register_fixture
class DeskCaddy(TurbosquidObjects):
    def __init__(
        self,
        name="desk_caddy",
        obj_name="desk_caddy",
        joints=[dict(type="free", damping="0.0005")],
    ):
        super().__init__(name, obj_name, joints)
