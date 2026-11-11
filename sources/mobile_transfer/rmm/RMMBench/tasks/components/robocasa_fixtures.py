from copy import deepcopy

import numpy as np
from sympy.physics.units import velocity
import os

from torch.distributed.elastic.utils import macros
from trimesh.util import tolist

from RMMBench.tasks.components.entity import Entity
from RMMBench.utils.utils import xml_path_completion
from RMMBench.utils.utils import euler_to_quaternion, quaternion_multiply
from dm_control import composer

from RMMBench.utils.register import register
from dm_control import mjcf
import sys
sys.path.append("/Users/lh/work/robosuite")

ROBOCASA_ROOT="/Users/lh/work/robocasa/robocasa/models/assets"

GEOMTYPE2GROUP = {
    "collision": {0},  # If we want to use a geom for physics, but NOT visualize
    "visual": {1},  # If we want to use a geom for visualization, but NOT physics
    "all": {0, 1},  # If we want to use a geom for BOTH physics + visualization
}

DEFAULT_CHILD_TAGS = [
    "geom", "mesh", "joint", "site", "material",
]

@register.add_entity("Arena")
class RoboCasaArana(Entity):
    def _build(self,
               *args, **kwargs):
        super()._build(**kwargs)



class RobocasaEntity(Entity):




    def _build(self, *args, **kwargs):
        """
        parameter:
            -name: str, the name of the entity
            -xml_path: str, the path of the xml file
            -position: 3d list/np.array, the initial position of the entity in the parent entity frame
            -orientation: 3d/4d list/np.array, the initial orientation of the entity in the parent entity frame, by euler or quanternion
            -randomness: dict, the randomness config for domain randomization, including offset of pose, texture, mesh scale, etc.
            -subentities: list, the subentities of the entity. The subentities will be attached to the entity or initilized in entity's frame.
            -parent_entity: Entity, the parent entity of the entity. If the parent entity is not None, the entity will be attached to the parent entity.
        """
        self.asset_root = ROBOCASA_ROOT

        if kwargs.get("xml",None):
            xml_path = kwargs.get("xml")
        else:
            xml_path = self.xml
        self.xml_path=xml_path_completion(xml_path, root=ROBOCASA_ROOT)
        if xml_path is not None:
            self._mjcf_model = mjcf.from_path(self.xml_path)
        else:
            self._mjcf_model = mjcf.RootElement()
            # print("kwargs:", kwargs)
            # self.relative_xml_path = xml_path.split(self.asset_root)[-1][1:] if xml_path is not None else None # for save the entity info
        # self.name = kwargs.get("name", "entity")

        self._mjcf_model.model = self.name
        self.init_pos = kwargs.get("position",None)
        self.init_quat = kwargs.get("orientation",[1,0,0,0])
        # self.size = np.array(kwargs.get("size", [1, 1,1]))
        # print("entity_size:",self.size)
        self.randomness = kwargs.get("randomness", None)
        self.subentities = kwargs.get("subentities", None)
        self.parent_entity = kwargs.get("parent_entity", None)
        if self.randomness is not None:
            assert isinstance(self.randomness, dict), "randomness config should be a dictionary"
            for k, v in self.randomness.items():
                if isinstance(v, list):
                    self.randomness[k] = np.array(v)
        if len(self.init_quat) == 3:
            self.init_quat = np.array(euler_to_quaternion(self.init_quat[0], self.init_quat[1], self.init_quat[2]))

        # Format the xml: inline the defaults and remove them
        self.obj = self._mjcf_model.find("body","object")
        model = self._mjcf_model
        defaults = model.default
        # print("defaults:", self.mjcf_model.default.find("default","test"))
        # print("ddd:",def)
        """
        DEFAULT_CHILD_TAGS
        [
    "geom", "mesh", "joint", "site", "material", 
    "texture", "light", "camera", "numeric"
]
        """
        default_geom_children = []
        default_geom_class_map = {}

        # Step 1: first iterate over the <geom> elements under all <body> elements and inline them
        # via dclass directly (no need to collect the defaults in advance)
        body_elements = model.find_all("body")
        for body_elem in body_elements:
            geom_elements = body_elem.find_all("geom")
            for geom_elem in geom_elements:
                try:
                    # Step 2: get the inner <default> element object corresponding to the geom (key point:
                    # geom_elem.dclass links directly)
                    #corresponding_default <default class="counter">...</default>
                    corresponding_default = geom_elem.dclass
                    # Step 3: verify that the default contains geom config (avoid pointless work)
                    if not hasattr(corresponding_default, "geom") or corresponding_default.geom is None:
                        continue
                except AttributeError:
                    # no dclass association (no default referenced), skip
                    continue

                # Step 4: extract the geom attributes from the corresponding default
                #OrderedDict([('group', 0), ('density', 10.0)])
                default_geom_attrs = corresponding_default.geom.get_attributes()

                #current_geom_attrs OrderedDict([('name', 'base_back'),
                # ('dclass', MJCF Element: <default class="counter">...</default>),
                # ('type', 'box'), ('size', array([0.5, 0.5, 1. ])),
                # ('material', MJCF Element: <material name="counter_base" class="/" texture="tex_base" shininess="0.10000000000000001" reflectance="0.10000000000000001"/>), ('pos', array([0., 0., 0.]))])
                current_geom_attrs = geom_elem.get_attributes()
                # print("current_geom_attrs", current_geom_attrs)
                # Step 5: inline the attributes (the geom's own attributes take priority; do not
                # overwrite existing config)
                # Step 4 (revised): fixed inlining logic (skip the current_geom_attrs dict and
                # validate the geom's own attributes directly)
                for attr_name, attr_value in default_geom_attrs.items():
                    # print("attr_name:", attr_name, attr_value)
                    if getattr(geom_elem,attr_name) is None:
                        geom_elem.set_attributes(**{attr_name: attr_value})
                        # print("getattr(geom_elem,attr_name):", getattr(geom_elem, attr_name))
                # Step 6: remove the redundant class attribute from the geom (already inlined, no
                # need to keep it)
                try:
                    # only removes the attribute from the geom itself; the corresponding default is not deleted
                    geom_elem._remove_attribute("class")
                    # print(
                    #     f"geom {geom_elem.name} inlined its default (class: {corresponding_default.dclass}), and the redundant class attribute was removed")
                    # print("after removal:",geom_elem.pos)
                except (AttributeError, RuntimeError):
                    print(f"geom {geom_elem.name} 的 class 属性已不存在，跳过删除")

        # Step 7: remove all <default> nodes (outer + inner, cleaned up recursively)

        # Key change: locate and remove the outer <default> directly, no find_all cached list needed
        # print("model.find_all(default)", model.find_all("default"))
        if hasattr(model.root_model, 'default'):
            # 1. get the outer default directly (model.root_node.default is a shortcut reference to it)
            # print("model.root_model",model.root_model.default)
            outer_default = model.root_model.default
            # print("outer_default:", outer_default)
            # 2. only delete when the parent node is valid (recursively cleans up the inner defaults)
            if outer_default._parent is not None:
                outer_default.remove()

        self._get_object_subtree(model)

    def _get_object_subtree(self,model):
        for i,el in enumerate(model.find_all("geom")):
            if el.group in {0,1}:
                # avoid unnamed geoms; keep the name if there is one
                g_name = el.name
                g_name = g_name if g_name is not None else f"g{i}"
                el.name = g_name
                if self.duplicate_collision_geoms and el.group == 0:
                    vis_geom = self._duplicate_visual_from_collision(el)

                    # parent node of the original geom (usually a body element)
                    parent_body = el.parent
                    parent_body.add(
                        "geom",  # the first argument is the tag string directly, no tag=, aligned with the example
                        **vis_geom  # expand the keyword arguments, matching the name=/type= style in your example
                    )
                    el.rgba = [0.5, 0, 0, 1]
                    if el.material is not None:
                        el._remove_attribute("material")
                    # print("vis_geom:", model.find("geom",el.name + "_visual"))
                    # print("el:",el)




            else:
                model._remove_attribute(el)
#OBJECT_COLLISION_COLOR = [0.5, 0, 0, 1]

    @staticmethod
    def _duplicate_visual_from_collision(element):

        vis_name = element.name + "_visual"
        vis_geom_attrs = {
            "name": vis_name,
            "type": element.type,
            "size": element.size,
            "pos": element.pos,
            "quat": element.quat,
            "density" : element.density,
            "material": element.material,
            "group": 1,          # visual group, distinct from collision group 0
            "contype": 0,        # disable collisions, aligned with your example
            "conaffinity": 0,    # disable collisions, aligned with your example
            "mass": 1e-8,        # negligible mass so it does not affect the physics simulation
            "rgba": element.rgba
        }
        return vis_geom_attrs





    #
    def set_scale(self, scale):
        """
        scale: float, the scaling factor [x,y,z]
        """
        scale = self.normalize_scale(scale)

        meshes = self.mjcf_model.find_all("mesh")
        geoms = self.mjcf_model.find_all("geom")
        sites = self.mjcf_model.find_all("site")
        bodys = self.mjcf_model.find_all("body")
        #scale_geoms  scale_meshes  scale_bodys  scale_sites
        self.scale_geoms(geoms, scale)
        self.scale_sites(sites, scale)
        self.scale_meshes(meshes, scale)
        self.scale_bodys(bodys, scale)


        # print(dir(self.mjcf_model.default.find("default","counter").geom))
        print("test----",self.mjcf_model.find("geom","base_right"))

        # change_scale = [geoms]
        # for i in change_scale:
        #     for j in i:
        #         print(f"{j.name}:",j.default)

    def normalize_scale(self,scale):
        """
        Normalizes a scale factor to be a 3-element numpy array.

        Args:
            scale (float or array-like): Scale factor (1 or 3 dims)

        Returns:
            np.array: 3-element scale array

        Raises:
            ValueError: If scale is not scalar or 3-element array
        """
        scale_array = np.array(scale).flatten()
        if scale_array.size == 1:
            scale_array = np.repeat(scale_array, 3)
        elif scale_array.size != 3:
            raise ValueError("Scale must be a scalar or a 3-element array.")
        return tolist(scale_array)

    def scale_geoms(self,mjcf_geoms, scale):
        """
        Scales a single geom element's position and size.

        Args:
            element (ET.Element): Geom element to scale
            scale_array (np.array): 3-element scale array


         mjcf_geoms = mjcf.find_all("geom")
        """
        for geom in mjcf_geoms:
            g_pos = geom.pos
            g_size = geom.size

            if g_pos is not None:
                geom.pos = g_pos*scale

            if g_size is not None:
                g_size_np = g_size
                # Handle cases where size is not 3-dimensional
                if len(g_size_np) == 3:
                    g_size_np = g_size_np * scale
                elif len(g_size_np) == 2:
                    # For 2D size, assume [radius, height] for cylinders
                    g_size_np[0] *= np.mean(scale[:2])  # Average scaling in x and y
                    g_size_np[1] *= scale[2]  # Scaling in z
                elif len(g_size_np) == 1:
                    g_size_np *= np.mean(scale)
                else:
                    raise ValueError("Unsupported geom size dimensions.")
                geom.size = g_size_np

    def scale_meshes(self, mjcf_meshes, scale):
        """
        Scales a single mesh element.

        Args:
            element (ET.Element): Mesh element to scale
            scale_array (np.array): 3-element scale array
        """
        for mesh in mjcf_meshes:

            m_scale = mesh.scale
            if m_scale is None:
                m_scale = np.ones(3)
            m_scale *= scale
            mesh.scale = m_scale

    def scale_bodys(self, mjcf_bodys, scale):
        """
        Scales a single body element's position.

        Args:
            element (ET.Element): Body element to scale
            scale_array (np.array): 3-element scale array
        """
        for body in mjcf_bodys:
            b_pos = body.pos
            if b_pos is not None:
                b_pos = b_pos * scale
                body.pos = b_pos

    def scale_sites(self,mjcf_sites ,scale):
        """
        Scales a single site element's position and size.

        Args:
            element (ET.Element): Site element to scale
            scale_array (np.array): 3-element scale array
        """
        for site in mjcf_sites:
            s_pos = site.pos
            if s_pos is not None:
                s_pos = s_pos * scale
                site.pos = s_pos

            s_size = site.size
            if s_size is not None:
                if len(s_size) == 3:
                    s_size = s_size * scale
                elif len(s_size) == 2:
                    s_size[0] *= np.mean(scale[:2])  # Average scaling in x and y
                    s_size[1] *= scale[2]  # Scaling in z
                elif len(s_size) == 1:
                    s_size *= np.mean(scale)
                else:
                    raise ValueError("Unsupported site size dimensions.")
                site.size = s_size





@register.add_entity("C")
class Fixture(RobocasaEntity):
    """
    The Fixture class is a base class for objects (fixtures) in the robosuite kitchen environment.
    It loads models of fixed objects from xml files.

    Args:

        xml: path to the MJCF (MuJoCo model) XML file used to load the Fixture object.

        name: name of the object.

        duplicate_collision_geoms: if set to True, every collision geom will have a visual geom copy.

        pos: (x, y, z) position of the object.

        scale: 3d scaling factor of the object.

        size: dimensions (width, depth, height) of the object.
    """

    # def __init__(
    #     self,
    #     *args, **kwargs
    # ):
    #
    #     super().__init__(*args, **kwargs)

    def _build(self,
               xml,
               # xml="fixtures/counters/counter",
               #     name,
               #     duplicate_collision_geoms=True,
               #     pos=None,
               #     scale=1,
               #     size=None,
               #     placement=None,
               #     rng=None,
               *args,
               **kwargs):
        self.duplicate_collision_geoms = True
        if not xml.endswith(".xml"):
            xml = os.path.join(xml, "model.xml")
        if xml:
            self.xml = xml

        super()._build(**kwargs)

        attr_defaults = {
            'duplicate_collision_geoms': True,
            'scale': 1,
            'size': None,
            'placement': None,
        }

        # 2. Generic bulk-assignment paradigm (core logic, reusing your template)
        for attr_name, default_val in attr_defaults.items():
            # Prefer the value passed in via kwargs; fall back to the dict's default when absent
            final_val = kwargs.get(attr_name, default_val)
            # Dynamically assign to self.<attr_name> (e.g. self.duplicate_collision_geoms, self.scale)
            setattr(self, attr_name, final_val)
        size = self.size
        if size is not None:
            self.set_scale_from_size(size)

        self.size = np.array([self.width, self.depth, self.height])



        placement = self.placement
            # set up exterior and interior sites
        self._bounds_sites = dict()
        for postfix in [
            "ext_p0",
            "ext_px",
            "ext_py",
            "ext_pz",
            "int_p0",
            "int_px",
            "int_py",
            "int_pz",
        ]:
            site = self._mjcf_model.find("site",postfix)

            if site is None:
                continue
            # fully transparent is 0, not 1; conversely, 1 is fully opaque
            site.rgba[-1]=1

            # site.set("rgba", array_to_string(rgba))
            self._bounds_sites[postfix] = site
        # a = self._bounds_sites["ext_p0"]
        # print("site pos:",a.pos)
        # scale based on specified max dimension


        # set offset between center of object and center of exterior bounding boxes
        if self.width is not None:
            try:
                # calculate based on bounding points
                p0 = self._bounds_sites["ext_p0"].pos
                px = self._bounds_sites["ext_px"].pos
                py = self._bounds_sites["ext_py"].pos
                pz = self._bounds_sites["ext_pz"].pos
                self.origin_offset = np.array(
                    [
                        np.mean((p0[0], px[0])),
                        np.mean((p0[1], py[1])),
                        np.mean((p0[2], pz[2])),
                    ]
                )
            except KeyError:
                self.origin_offset = [0, 0, 0]
        else:
            self.origin_offset = [0, 0, 0]
        self.origin_offset = np.array(self.origin_offset)

        # placement config, for determining where to place fixture (most fixture will not use this)
        self._placement = placement
#
    def set_bounds_sites(self, pos_dict):
        """
        Set the positions of the exterior and interior bounding box sites of the object

        Args:
            pos_dict (dict): Dictionary of sites and their new positions

        The value for each key is a site object: mjcf.find("site", name)
        """
        for (name, pos) in pos_dict.items():
            self._bounds_sites[name].pos = pos
    # @property
    # def width(self):
    #     return self.size[0]
    #
    # @property
    # def depth(self):
    #     return self.size[1]
    #
    # @property
    # def height(self):
    #     return self.size[2]

    def get_texture_name_from_file(self,file):
        """
        Extract texture name from filename.
        eg: ../robosuite/models/assets/textures/flat/gray.png -> flat/gray
        """
        suffix_path = file.split("textures/")[1]
        name = suffix_path.split(".")[0]
        return name

    def set_scale_from_size(self, size):
        """
        Set the scale of the fixture based on the desired size. If any of the dimensions are None,
        the scaling factor will be the same as one of the other two dimensions

        Args:
            size (3-tuple): (width, depth, height) of the fixture
        """
        # check that the argument is valid
        assert len(size) == 3

        # calculate and set scale according to specification
        scale = [None, None, None]
        cur_size = [self.width, self.depth, self.height]
        for (i, t) in enumerate(size):
            if t is not None:
                scale[i] = t / cur_size[i]

        scale[0] = scale[0] or scale[2] or scale[1]
        scale[1] = scale[1] or scale[0] or scale[2]
        scale[2] = scale[2] or scale[0] or scale[1]

        """
        Scale each geom, mesh, site and body element.
        Called during initialization, and it can also be invoked manually to resize the model.

        Args:
            scale (float or list of float): scaling factor (1d or 3d, for uniform scaling or
            per-axis scaling along x/y/z)
            obj (ET.Element): root object to apply the scale to, defaults to the model's root object.
        """
        self.set_scale(scale)
#
#