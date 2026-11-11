"""
Register the common containers/recaptacles in daily life, without interactive functions and triggerd mechanism
"""
import numpy as np
import random
import os
from RMMBench.tasks.components.container import CommonContainer, FlatContainer, ContainerWithDoor
from RMMBench.utils.register import register

MATERIALS = ["wood0", "wood1", "wood2", "wood3", "wood4", "stone0", "stone", "stone2", "stone3", "stone4"]

@register.add_entity("Table")
class Table(FlatContainer):
    def _build(self, name="table", **kwargs):
        # print("kwargs[materials]:", kwargs["materials"])
        self.materials = kwargs.get("materials", MATERIALS)
        super()._build(name=name, **kwargs)
        # bodys = self.mjcf_model.find_all("body")
        # for i in bodys:
        #     print("i.pos:",i.pos)
        #     i.pos = [0,-2,0]

    def set_texture(self, physics, texture):
        vis_body = self.mjcf_model.worldbody.find("body", "table_vis")
        target_geoms = vis_body.find_all("geom")
        # print("-----------")
        # print("self.materials:",self.materials)
        new_material = random.choice(self.materials)
        # print("new_material:",new_material)

        materials = self.mjcf_model.find_all("material")
        material_names = [material.name for material in materials]
        if new_material not in material_names:
            self.mjcf_model.asset.add("texture", name=new_material, type="cube", file=os.path.join(self.texture_root, f"{new_material}.png"))
            self.mjcf_model.asset.add("material", name=new_material, texture=new_material, shininess=0)
        
        materials = self.mjcf_model.find_all("material")
        for material in materials: # get mjcf element
            if material.name == new_material:
                target_material = material
                break
        for geom in target_geoms:
            geom.material = target_material
    
    def save(self, physics):
        info = super().save(physics)
        if self.mjcf_model.worldbody.find("body", "table_vis") is not None:
            info["materials"] = [self.mjcf_model.worldbody.find("body", "table_vis").find_all("geom")[0].material.name]
        return info
    
@register.add_entity("Counter")
class Counter(CommonContainer):
    grasp_type = 2                  # Layer 1: z is always vertical; the long-axis/handle direction must be aligned
    grasp_approach = "horizontal"  # Layer 2A: the structure requires a horizontal grasp
    grasp_roll_offset = 90          # Layer 2B: gripper roll of 90° (broad face goes from parallel → perpendicular to the ground)

    def _build(self, name="counter", **kwargs):
        super()._build(name=name, **kwargs)

    # ── Drawer-related methods──────────────────────────────────────

    def get_drawer_joint(self):
        """Return the drawer's slide joint (the slidejoint on inner_box in counter_0/model.xml)"""
        return self._mjcf_model.find("joint", "slidejoint")

    def get_drawer_distance(self, physics):
        """Get the drawer's current slide displacement (meters). 0 when closed, negative along -y once pulled out"""
        joint = self.get_drawer_joint()
        if joint is None:
            return 0.0
        return physics.bind(joint).qpos[0]

    def is_open(self, physics, threshold=0.05):
        """
        Determine whether the drawer is pulled open.
        slidejoint range: [-0.6, 0]; qpos grows in the negative direction from 0 as it is pulled out.
        It is considered open when the absolute displacement exceeds the threshold.
        """
        return abs(self.get_drawer_distance(physics)) > threshold

@register.add_entity("BilliardTable")
class BilliardTable(Table):
    def _build(self, target_hole="container_mid_1", **kwargs):
        super()._build(**kwargs)
        self.target_hole = target_hole
        collision_body = self.mjcf_model.worldbody.find("body", "collision")
        target_hole = collision_body.find("body", target_hole)
        target_hole.add("site", dclass="keypoint", pos="0.07 0.07 0.1")
        target_hole.add("site", dclass="keypoint", pos="-0.07 -0.07 0")
        target_hole.add("site", dclass="placepoint", pos="0 0 0.2")
        
    def contain(self, point, physics):
        """Check whether the point is in the hole"""
        sites = self.mjcf_model.worldbody.find_all("site")
        keypoints = np.array([physics.bind(kp).xpos for kp in sites if physics.bind(kp).group == 3])
        max_x, min_x, max_y, min_y, max_z, min_z = keypoints[:, 0].max(), keypoints[:, 0].min(), keypoints[:, 1].max(), keypoints[:, 1].min(), keypoints[:, 2].max(), keypoints[:, 2].min()
        if min_x <= point[0] <= max_x and \
            min_y <= point[1] <= max_y and \
                min_z <= point[2] <= max_z:
            return True
        return False
    
    def save(self, physics):
        data_to_save = super().save(physics)
        data_to_save["target_hole"] = self.target_hole
        return data_to_save
        
@register.add_entity("Plate")
class Plate(FlatContainer):
    def _build(self, name="plate", **kwargs):
        super()._build(name=name, **kwargs)
        
@register.add_entity("PlaceMat")
class PlaceMat(FlatContainer):
    def _build(self, **kwargs):
        super()._build(**kwargs)

@register.add_entity("CuttingBoard")
class CuttingBoard(FlatContainer):
    def _build(self, **kwargs):
        super()._build(**kwargs)

@register.add_entity("TubeStand")
class TubeStand(CommonContainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.col_pos = [-0.16, -0.08, 0, 0.08, 0.16]
        self.row_pos = [-0.05, 0.05]
        
@register.add_entity("Fridge")
class Fridge(ContainerWithDoor):
    def _build(self, name="fridge", **kwargs):
        super()._build(name=name,  **kwargs)

@register.add_entity("SmallFridge")
class SmallFridge(ContainerWithDoor):
    def _build(self,  name="small_fridge",**kwargs):
        super()._build(name=name,  **kwargs)

    # ── Door open/close detection ───────────────────────────────────────────

    def get_door_joint(self):
        """Return the fridge door's hinge joint (the joint with name="door" on the door body in fridge_small_1/mobility.xml; note it is distinct from the handle joint "handle")"""
        return self._mjcf_model.find("joint", "door")

    def get_door_angle(self, physics):
        """Get the door's current opening angle (radians). 0 when closed, max ~1.508 rad"""
        joint = self.get_door_joint()
        if joint is None:
            return 0.0
        return physics.bind(joint).qpos[0]

    def is_open(self, physics, threshold=0.2):
        """
        Determine whether the fridge door is open.
        Joint range: [0, 1.50796]; qpos is the opening angle,
        and the door is considered open when the angle exceeds the threshold (default 0.2 rad ≈ 11.5°).
        """
        return abs(self.get_door_angle(physics)) > threshold

    # ── body_name identification (referring to Sink) ───────────────────────────────
    def get_grasped_keypoints(self, physics, body_name=None):
        if body_name is not None and body_name != "handle":
            return []

        body = self._mjcf_model.find("body", "handle")
        if body is None:
            return []

        grasp_sites = [s for s in body.find_all("site") if physics.bind(s).group == 4]
        if not grasp_sites:
            return []

        return [physics.bind(s).xpos for s in grasp_sites]


@register.add_entity("Safe")
class Safe(ContainerWithDoor):
    def _build(self, name:str="safe", **kwargs):
        super()._build(name=name, **kwargs)

@register.add_entity("GiftBox")
class GiftBox(CommonContainer):
    def _build(self, **kwargs):
        super()._build(**kwargs)
        
@register.add_entity("Vase")
class Vase(CommonContainer):
    def _build(self, **kwargs):
        super()._build(**kwargs)

@register.add_entity("HammerHead")
class HammerHead(CommonContainer):
    """
    The hammer head is modeled as a container, because whether it contained the hammer handle should be judged!
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

@register.add_entity("Mirrors")
class Mirrors(FlatContainer):    
    def _build(self,
               reflectance:list,
               **kwargs):
        super()._build(**kwargs)
        assert isinstance(reflectance, list) and len(reflectance) >= 1
        for i, ratio in enumerate(reflectance):
            # BUG here. Mujoco only support the reflectance of the first geom. It's strange right?
            self.mjcf_model.asset.add("material", name=f"reflectance_{i}", rgba="1 1 1 1", reflectance=ratio)
            target_body = self.mjcf_model.worldbody.find("body", f"mirror_{i}")   
            target_body.add("geom", type="box", pos="0.2102 0 0.02", size="0.199 0.098 0.005", dclass="visual", material=f"reflectance_{i}")
            target_body.add("geom", type="box", pos="0.2102 0 0.02", size="0.199 0.098 0.005", dclass="collision")

@register.add_entity("Shelf")
class Shelf(CommonContainer):
    def _build(self, **kwargs):
        super()._build(**kwargs)
    
    def contain(self, point, physics, layer=None):
        if layer is None:
            return super().contain(point, physics)
        else:
            assert isinstance(layer, int), "layer should be an integer"
            target_body = self.mjcf_model.worldbody.find("body", f"layer_{layer}")
            self.keypoints = np.array([physics.bind(kp).xpos for kp in target_body.find_all("site") if physics.bind(kp).group == 3])
            minX, maxX, minY, maxY, minZ, maxZ = self.keypoints[:, 0].min(), self.keypoints[:, 0].max(), self.keypoints[:, 1].min(), self.keypoints[:, 1].max(), self.keypoints[:, 2].min(), self.keypoints[:, 2].max()
            if minX <= point[0] <= maxX and \
            minY <= point[1] <= maxY and \
                minZ <=point[2] <= maxZ:
                return True
            return False

@register.add_entity("BoxFlatContainer")
class BoxFlatContainer(FlatContainer):
    def __init__(self, 
                 size=[0.05, 0.05, 0.02],
                 rgba=None,
                 **kwargs):
        self.size = size
        if rgba is None:
            rgba = [random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1), random.uniform(0.4, 1)]
        self.rgba = rgba
        super().__init__(**kwargs)
    
    def _build(self, **kwargs):
        super()._build(**kwargs)
        self.mjcf_model.worldbody.add("geom", type="box", size=self.size, contype="0", conaffinity="0", rgba=self.rgba)
        self.mjcf_model.worldbody.add("geom", type="box", size=self.size, solref="0.001 1")
        self.mjcf_model.worldbody.add("site", group="3", type="sphere", size="0.01", pos=f"{self.size[0]} {self.size[1]} {self.size[2]+0.02}")
        self.mjcf_model.worldbody.add("site", group="3", type="sphere", size="0.01", pos=f"{-self.size[0]} {-self.size[1]} {-self.size[2]}")
        


