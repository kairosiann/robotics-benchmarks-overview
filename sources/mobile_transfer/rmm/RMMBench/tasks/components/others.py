import numpy as np
from sympy.physics.units import velocity
import os
from RMMBench.tasks.components.entity import Entity
from RMMBench.utils.utils import xml_path_completion

from RMMBench.utils.register import register
from dm_control import mjcf
import sys
sys.path.append("/Users/lh/work/robosuite")

ROBOCASA_ROOT="/Users/lh/work/robocasa/robocasa/models/assets"

class BoxObject(Entity):
    """
    A box object.

    Args:
        size (3-tuple of float): (half-x, half-y, half-z) size parameters for this box object
    """

    def __init__(
            self,
            # size_max=None,
            # size_min=None,
            # density=None,
            # friction=None,
            # rgba=None,
            # solref=None,
            # solimp=None,
            # material=None,
            # joints="default",
            # obj_type="all",
            # duplicate_collision_geoms=True,
            # rng=None,
            **kwargs
    ):
        # Random size
        # if size is None:
        #     size = self.get_size(size, size_max, size_min, [0.07, 0.07, 0.07], [0.03, 0.03, 0.03], rng=rng)

        # Save parameters to the instance
        # print("size_object:",self.size)
        # self.density = density
        # self.friction = friction
        # self.rgba = rgba
        # self.solref = solref
        # self.solimp = solimp
        # self.material = material
        # # self.joints = joints
        # self.obj_type = obj_type
        # self.duplicate_collision_geoms = duplicate_collision_geoms
        # self.rng = rng

        # Call the RMMBench Entity constructor
        if kwargs.get("rgba",None):
            self.rgba = kwargs.get("rgba")
        else:
            self.rgba = [1, 0, 0, 1]
        super().__init__(**kwargs)


    def sanity_check(self):
        """
        Checks to make sure inputted size is of correct length

        Raises:
            AssertionError: [Invalid size length]
        """
        assert len(self.size) == 3, "box size should have length 3"

    def get_size(size, size_max, size_min, default_max, default_min, rng=None):
        """
        Helper method for providing a size, or a range to randomize from

        Args:
            size (n-array): Array of numbers that explicitly define the size
            size_max (n-array): Array of numbers that define the custom max size from which to randomly sample
            size_min (n-array): Array of numbers that define the custom min size from which to randomly sample
            default_max (n-array): Array of numbers that define the default max size from which to randomly sample
            default_min (n-array): Array of numbers that define the default min size from which to randomly sample
            rng (None or np.random.RandomState): Random number generator to use. If None, will use np.random.default_rng()

        Returns:
            np.array: size generated

        Raises:
            ValueError: [Inconsistent array sizes]
        """
        if rng is None:
            rng = np.random.default_rng()
        if len(default_max) != len(default_min):
            raise ValueError(
                "default_max = {} and default_min = {}".format(str(default_max), str(default_min))
                + " have different lengths"
            )
        if size is not None:
            if (size_max is not None) or (size_min is not None):
                raise ValueError("size = {} overrides size_max = {}, size_min = {}".format(size, size_max, size_min))
        else:
            if size_max is None:
                size_max = default_max
            if size_min is None:
                size_min = default_min
            size = np.array([rng.uniform(size_min[i], size_max[i]) for i in range(len(default_max))])
        return np.array(size)
    # Changed: generation now uses the build method
    # def _get_object_subtree(self):
    #     return self._get_object_subtree_(ob_type="box")

    # # The following is generic geometry computation
    # @property
    # def bottom_offset(self):
    #     return np.array([0, 0, -1 * self.size[2]])
    #
    # @property
    # def top_offset(self):
    #     return np.array([0, 0, self.size[2]])
    #
    # @property
    # def horizontal_radius(self):
    #     return np.linalg.norm(self.size[0:2], 2)
    #
    # def get_bounding_box_half_size(self):
    #     return np.array([self.size[0], self.size[1], self.size[2]])

@register.add_entity("Box")
class Box(BoxObject):
    """
    Initializes a box object. Mainly used for filling in gaps in the environment like in corners or beneath bottom cabinets

    Args:
        pos (list): position of the object

        size (list): size of the object

        name (str): name of the object

        texture (str): path to texture file

        mat_attrib (dict): material attributes

        tex_attrib (dict): texture attributes
    """

    def __init__(
        self,
        # pos,
        # size,
        name="box",
        texture="textures/wood/dark_wood_parquet.png",
        mat_attrib={"shininess": "0.1"},
        tex_attrib={"type": "cube"},
        rng=None,
        *args,
        **kwargs
    ):
        if kwargs.get("texture", None):
            texture = kwargs.get("texture", None)
        self.texture = xml_path_completion(texture, root=ROBOCASA_ROOT)
        self.size = np.array(kwargs.get("size", [1,1,1]))
        self.pos = np.array(kwargs.get("position", [0, 0, 0]))
        self.mat_attrib = mat_attrib
        self.tex_attrib = tex_attrib



        # for relative positioning
        self.origin_offset = np.array([0, 0, 0])
        self.scale = 1

        if rng is not None:
            self.rng = rng
        else:
            self.rng = np.random.default_rng()
        super().__init__( *args,**kwargs)

    def _build(self, **kwargs):
        super()._build(**kwargs)

        # Print the size
        print("box_size:", self.size)

        # Add texture
        tex = self.mjcf_model.asset.add(
            "texture",
            name=f"{self.name}_tex",
            file=self.texture,
            **self.tex_attrib
        )

        # Add material
        mat = self.mjcf_model.asset.add(
            "material",
            name=f"{self.name}_mat",
            texture=tex,
            **self.mat_attrib
        )

        # Visual geometry
        self.mjcf_model.worldbody.add(
            "geom",
            type="box",
            size=self.size,
            pos=self.pos,
            material=mat,
            contype="0",
            conaffinity="0",
            rgba=self.rgba
        )

        # Physics geometry
        self.mjcf_model.worldbody.add(
            "geom",
            type="box",
            size=self.size,
            pos=self.pos,
            solref="0.001 1",
            rgba=[0, 0, 0, 0]  # transparent, used for physics only
        )


    def update_state(self, env):
        pass





@register.add_entity("Wall")
class Wall(BoxObject):
    """
    Initializes a wall object. Used for creating walls in the environment

    Args:
        name (str): name of the object

        texture (str): path to texture file

        pos (list): position of the object

        quat (list): quaternion of the object

        size (list): size of the object

        wall_side (str): which side the wall is on (back, front, left, right, floor)

        mat_attrib (dict): material attributes

        tex_attrib (dict): texture attributes

        backing (bool): whether this is a backing wall

        backing_extended (list): whether the backing is extended on the left and right

        default_wall_th (float): default thickness of the wall

        default_backing_th (float): default thickness of the backing
    """


    #build can be inherited as-is; resolution goes to the lowest-level wall class first, then up to boxobject and entity
    def _build(self,
               *args,
               **kwargs):
        super()._build(**kwargs)
        attr_defaults = {
            'texture': 'textures/bricks/white_bricks.png',
            'size': None,
            'mat_attrib': {
                "texrepeat": "3 3",
                "reflectance": "0.1",
                "shininess": "0.1",
                "texuniform": "true",
            },
            'tex_attrib': {"type": "2d"},
            'wall_side': "back",
            'backing': False,
            'backing_extended': [False, False],
            'default_wall_th': 0.02,
            'default_backing_th': 0.1,
            'rng': None,
        }

        for attr_name, default_val in attr_defaults.items():
            # Prefer the value from kwargs; fall back to the dict's default if absent in kwargs
            final_val = kwargs.get(attr_name, default_val)
            # Dynamically assign to self.<attr_name> (e.g. self.texture, self.mat_attrib)
            setattr(self, attr_name, final_val)
        backing_extended = self.backing_extended
        backing = self.backing
        print("kwargs:", kwargs)
        print("backing:", backing)
        print("self.wall_side:", self.wall_side)
        print("backing_extended:", backing_extended)

        default_wall_th = self.default_wall_th
        default_backing_th = self.default_backing_th
        size = self.size

        pos = np.array(kwargs.get("position"))

        if backing:
            self.texture = "textures/flat/light_gray.png"
        # elif kwargs.get("texture", None):
        #     texture = kwargs.get("texture")

        # print(f"before processing: {kwargs.get('name', )}---: ", kwargs)
        if self.wall_side=="floor":
            # swap x, y axes due to rotation
            size = [size[1], size[0], size[2]]

        self.texture = xml_path_completion(self.texture, root="/Users/lh/work/robocasa/robocasa/models/assets")

        # The following all defines size and pos
        if self.wall_side is not None:
            quat = self.get_quat()

        # align everything to account for thickness & backing

        if self.wall_side == "floor":
            size[0] += default_wall_th * 2
            size[1] += default_wall_th * 2
            pos[2] -= size[2]
            if backing:
                pos[2] -= default_wall_th * 2
        else:
            size[0] += default_wall_th * 2
            shift = size[2] if not backing else size[2] + default_wall_th * 2
            if self.wall_side == "left":
                pos[0] -= shift
            elif self.wall_side == "right":
                pos[0] += shift
            elif self.wall_side == "back":
                pos[1] += shift
            elif self.wall_side == "front":
                pos[1] -= shift

            if backing:
                size[1] += default_wall_th + default_backing_th
                pos[2] -= default_wall_th + default_backing_th

                # extend left/right side to form a perfect box
                if backing_extended[0]:
                    size[0] += default_backing_th
                    if self.wall_side in ["left", "right"]:
                        pos[1] += default_backing_th
                    else:
                        pos[0] -= default_backing_th
                if backing_extended[1]:
                    size[0] += default_backing_th
                    if self.wall_side in ["left", "right"]:
                        pos[1] -= default_backing_th
                    else:
                        pos[0] += default_backing_th

        self.quat = quat
        self.pos = pos
        self.size = size
        # self.size = kwargs.get("size", None)
        rng = self.rng
        if rng is not None:
            self.rng = rng
        else:
            self.rng = np.random.default_rng()


        # print("box_size:",self.size)
        # print("self.pos:", self.pos)
        # print("self.quat:", self.quat)
        #
        print(f"{kwargs.get('name',)}---: ", kwargs)
        self.init_pos = [0,0,0]
        self.init_quat = [1,0,0,0]
        # self.init_quat = np.array(kwargs.get("orientation", [1,0,0,0]))
        tex = self.mjcf_model.asset.add(
            "texture",
            name=f"{self.name}_tex",
            file=self.texture,  # the path was already completed in __init__
            **self.tex_attrib
        )

        # 2. Add material
        mat = self.mjcf_model.asset.add(
            "material",
            name=f"{self.name}_mat",
            texture=tex,
            **self.mat_attrib
        )

        # 3. Add geometry (visual)
        self.mjcf_model.worldbody.add(
            "geom",
            name=f"{self.name}_geom",
            type="box",
            size=self.size,
            pos=self.pos,
            quat=self.quat,
            material=mat,
            contype=0,
            conaffinity=0
        )

        # 4. Add physics geometry (optional)
        self.mjcf_model.worldbody.add(
            "geom",
            name=f"{self.name}_collision",
            type="box",
            size=self.size,
            pos=self.pos,
            quat=self.quat,
            solref="0.001 1",
            rgba=[0, 0, 0, 0]  # transparent, used for physics only
        )

        # # 5. Add marker points (optional)
        # print("self.size:", self.size)
        # self.mjcf_model.worldbody.add(
        #     "site",
        #     name=f"{self.name}_site1",
        #     group=3,
        #     type="sphere",
        #     size=np.array([0.01]),
        #     pos=[self.size[0], self.size[1], self.size[2] + 0.02]
        # )
        # self.mjcf_model.worldbody.add(
        #     "site",
        #     name=f"{self.name}_site2",
        #     group=3,
        #     type="sphere",
        #     size=0.01,
        #     pos=[-self.size[0], -self.size[1], -self.size[2]]
        # )

    # Modify the wall's pos
    # def set_pos(self, pos):
    #     """
    #     Set the position of the object
    #
    #     Args:
    #         pos (list): position of the object
    #     """
    #     self.pos = pos
    #     self._obj.set("pos", a2s(pos))
# Return the rotation quaternion corresponding to the wall_side key.
    def get_quat(self):
        """
        Returns the quaternion of the object based on the wall side

        Returns:
            list: quaternion
        """
        side_rots = {
            "back": [-0.707, 0.707, 0, 0],
            "front": [0, 0, 0.707, -0.707],
            "left": [0.5, 0.5, -0.5, -0.5],
            "right": [0.5, -0.5, -0.5, 0.5],
            "floor": [0.707, 0, 0, 0.707],
        }
        if self.wall_side not in side_rots:
            raise ValueError()
        return side_rots[self.wall_side]

    def update_state(self, env):
        pass

@register.add_entity("Floor")
class Floor(Wall):
    def __init__(
        self,
        texture="textures/bricks/red_bricks.png",
        mat_attrib={
            "texrepeat": "2 2",
            "texuniform": "true",
            "reflectance": "0.1",
            "shininess": "0.1",
        },
        *args,
        **kwargs
    ):


        texture = xml_path_completion(texture, root="/Users/lh/work/robocasa/robocasa/models/assets")

        # everything is the same except the plane is rotated to be horizontal
        super().__init__(
            texture=texture,
            wall_side="floor",
            # horizontal plane
            mat_attrib=mat_attrib,
            *args,
            **kwargs
        )

@register.add_entity("WallAccessory")
class WallAccessory(Entity):
    """
    Class for wall accessories. These are objects that are attached to walls, such as outlets, clocks, paintings, etc.

    Args:
        xml (str): path to mjcf xml file

        name (str): name of the object

        pos (list): position of the object

        attach_to (Wall): The wall to attach the object to

        protrusion (float): How much to protrude out of the wall when placing the object
        xml (str): path to the MJCF XML file

        name (str): name of the object

        pos (list): position of the object

        attach_to (Wall): the wall to attach the object to

        protrusion (float): how far the object protrudes from the wall
    """

    def __init__(
        self,
        xml, name, pos,  protrusion=0.02,
        *args, **kwargs
    ):

        # TODO add in error checking for rotated walls
        # if (pos[1] is None and attach_to is None) or (pos[1] is not None and attach_to is not None):
        #     raise ValueError("Exactly one of y-dimension \"pos\" and \"attach_to\" " \
        #                      "must be specified")
        # if pos[0] is None or pos[2] is None:
        #     raise ValueError("The x and z-dimension position must be specified")

        # the wall to attach accessory to

        self.wall = kwargs.get("attach_to",None)
        # how much to protrude out of wall
        # if protrusion is not None:
        #     self.protrusion = protrusion
        # else:
        #     self.protrusion = self.depth / 2
        if kwargs.get("protrusion",None):
            protrusion = kwargs.get("protrusion")
        self.protrusion = protrusion


        self._place_accessory()

        super().__init__(
            # xml=xml,
            # name=name,
            # duplicate_collision_geoms=False,
            # pos=pos,
            *args,
            **kwargs
        )
    def _build(self, **kwargs):
        # super()._build(**kwargs)
        xml_path = kwargs.get("xml_path", None)
        xml_path=xml_path_completion(xml_path, root="/Users/lh/work/robocasa/robocasa/models/assets")
        if xml_path is not None:
            self._mjcf_model = mjcf.from_path(xml_path)
        else:
            self._mjcf_model = mjcf.RootElement()

    def _place_accessory(self):
        """
        Place the accessory on the wall
        """
        if self.wall is None:
            # absolute position was specified
            return

        x, y, z = self.pos
        # print(self.wall.wall_side, self.name)

        # update position and rotation of the object based on the wall it attaches to
        if self.wall.wall_side == "back":
            y = self.wall.pos[1] - self.protrusion
        elif self.wall.wall_side == "front":
            self.set_euler([0, 0, self.rot + 3.1415])
            y = self.wall.pos[1] + self.protrusion
        elif self.wall.wall_side == "right":
            x = self.wall.pos[0] - self.protrusion
            self.set_euler([0, 0, self.rot - 1.5708])
        elif self.wall.wall_side == "left":
            x = self.wall.pos[0] + self.protrusion
            self.set_euler([0, 0, self.rot + 1.5708])
        elif self.wall.wall_side == "floor":
            raise NotImplementedError()
        else:
            raise ValueError()

        self.set_pos([x, y, z])
