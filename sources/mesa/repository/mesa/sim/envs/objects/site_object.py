import pathlib

import numpy as np
from robosuite.utils.mjcf_utils import string_to_array

absolute_path = pathlib.Path(__file__).parent.parent.parent.absolute()


class SiteObject:
    def __init__(
        self,
        name,
        parent_name=None,
        joints=None,
        size=None,
        rgba=None,
        site_type="box",
        site_pos="0 0 0",
        site_quat="1 0 0 0",
        object_properties={},
    ):
        self.name = name
        self.parent_name = parent_name
        self.joints = joints
        self.site_pos = string_to_array(site_pos)
        self.site_quat = string_to_array(site_quat)
        self.size = size if type(size) is not str else string_to_array(size)
        self.rgba = rgba
        self.site_type = site_type
        self.object_properties = object_properties

    def in_box(self, this_position, this_mat, other_position, eps=1e-6):
        # Treat self.size as half-extents in local frame
        p_local = this_mat.T @ (other_position - this_position)

        lb = -self.size.copy()
        ub =  self.size.copy()
        lb[2] -= 0.01  # if you want this tolerance

        inside = np.all(p_local >= lb - eps) and np.all(p_local <= ub + eps)

        return inside

    def __str__(self):
        return (
            f"Object {self.name} : \n geom type: {self.site_type} \n size: {self.size}"
        )

    def under(self, this_position, this_mat, other_position, other_height=0.10):
        """
        Checks whether an object is on this SiteObject.
        Useful for when the CompositeObject has holes and the object should
        be within one of the holes. Makes an approximation by treating the
        object as a point, and the SiteObject as an axis-aligned grid.
        Args:
            this_position: 3D position of this SiteObject
            other_position: 3D position of object to test for insertion
        """
        total_size = self.size

        delta_position = this_mat @ (other_position - this_position)
        return total_size[2] - 0.005 < delta_position[2] < total_size[
            2
        ] + other_height and np.all(np.abs(delta_position[:2]) < total_size[:2])
