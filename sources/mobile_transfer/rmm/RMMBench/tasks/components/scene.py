from RMMBench.utils.paths import PROJECT_ROOT
import os
import numpy as np
import random
import json
from dm_control import composer
from dm_control import mjcf
from RMMBench.utils.utils import euler_to_quaternion, quaternion_multiply, rotate_point_by_quaternion

FLOOR_TEXTURE = [f"floor{i}" for i in range(13)]

class Scene(composer.Entity):
    def __init__(self,  *args, **kwargs):
        self.scene_asset_root = os.path.join(PROJECT_ROOT, "assets/scenes")
        super().__init__(*args, **kwargs)
        
    def _build(self, *args, **kwargs):
        self.shadow = kwargs.get("shadow", False)
        # self.shadow = True
        self.light_position = kwargs.get("robot", None)
        # if self.light_position is not None:
        #     quat = self.light_position.get("euler", [0, 0, -1.57])
        #     quat = quat[2]
        #     off_set = 0.2
        #     map_set = {
        #         0: (-off_set, 0),
        #         1.57: (0, -off_set),
        #         -1.57: (0, off_set),
        #         3.14: (off_set, 0),
        #         -3.14: (off_set, 0),
        #     }
        #     map_dir = {
        #         0: [0.2, 0, -1],
        #         1.57: [0, 0.2, -1],
        #         -1.57: [0, -0.2, -1],
        #         3.14: [-0.2, 0, -1],
        #         -3.14: [-0.2, 0, -1],
        #     }
        #     self.light_dir = map_dir[quat]
        #     x_set, y_set = map_set[quat]
        #     # print("x_set:", x_set)
        #     # print("y_set:", y_set)
        #     self.light_position = [self.light_position["position"][0] + x_set,
        #                            self.light_position["position"][1] + y_set, self.light_position["position"][2] + 3]
        #
        # else:
        #     self.light_position = [0, -0.8, 3]

        if self.shadow:
            return self.build_default_scene()

        # self.build_default_scene()
        scene_name = kwargs.get("name", None)
        with open(os.path.join(PROJECT_ROOT, "configs/scene_config.json"), "r") as f:
            all_scene_config = json.load(f)
        if scene_name is None or scene_name not in all_scene_config:
            scene_name = random.choice(list(all_scene_config.keys()))
        
        self.scene_config = all_scene_config[scene_name]
        self.scene_config.update(**kwargs)
        assert isinstance(self.scene_config, dict), "scene_config must be a dictionary"
        # load offset pose to world frame
        self.init_pos = self.scene_config.get("position", [0, 0, 0])
        self.init_quat = self.scene_config.get("orientation", [1, 0, 0, 0]) 
        if len(self.init_quat) == 3:
            self.init_quat = euler_to_quaternion(*self.init_quat)
        self.candidate_pos = self.scene_config.get("candidate_pos", None)
        
        # other initialization
        self.randomness = self.scene_config.get("randomness", None)
        self.floor_textures = self.scene_config.get("floor_textures", FLOOR_TEXTURE)
        # build the scene from the xml file
        self._mjcf_model = mjcf.from_path(os.path.join(self.scene_asset_root, self.scene_config["xml_path"]))
        self._mjcf_model.model = scene_name


    @property
    def mjcf_model(self):
        return self._mjcf_model
    
    @property
    def name(self):
        return self.mjcf_model.model
    
    def initialize_episode(self, physics, random_state:np.random.RandomState):
        """
        Set the initial pose of the background scene.
        """
        if self.shadow:
            lights = self._mjcf_model.find_all("light")
            light = lights[0]
            light.pos = self.light_position
            light.dir = self.light_dir
            # print("light.pos:", light.pos)
            # print("light.dir:", light.dir)
            light.castshadow = "true"
            # light.directional = "false"

        if self.candidate_pos is not None:
            new_xpos = random.choice(self.candidate_pos)
        else:
            new_xpos = self.init_pos
        new_xquat = self.init_quat
        if self.randomness is not None:
            if self.randomness.get("quat", None) is not None:
                rotate_quat = euler_to_quaternion(*(self.randomness["quat"] * random_state.uniform([-np.pi, -np.pi, -np.pi], [np.pi, np.pi, np.pi])))
                new_xquat = quaternion_multiply(new_xquat, 
                                               rotate_quat)
            if self.randomness.get("pos", None) is not None:
                new_xpos = rotate_point_by_quaternion(new_xpos, rotate_quat)
                new_xpos += self.randomness["pos"] * random_state.uniform([-1, -1, -1], [1, 1, 1])
            
            if self.randomness.get("texture", None) is not None:
                # modify the texture of the floor or walls
                self.set_texture(physics, self.randomness.get("texture"))
        self.set_pose(physics, new_xpos, new_xquat)   
        return super().initialize_episode(physics, random_state)
    
    def set_texture(self, physics, texture):
        floor = self.mjcf_model.worldbody.find("geom", "floor")
        new_material = random.choice(self.floor_textures)
        materials = self.mjcf_model.find_all("material")
        material_names = [material.name for material in materials]
        if new_material not in material_names:
            self.mjcf_model.asset.add("texture", name=new_material, type="2d", file=os.path.join(self.scene_asset_root, "../obj/assets/textures", f"{new_material}.png"))
            self.mjcf_model.asset.add("material", name=new_material, texture=new_material, texrepeat="3 3")
        materials = self.mjcf_model.find_all("material")
        for material in materials:
            if material.name == new_material:
                target_material = material
                break
        floor.material = target_material
    
    def save(self, physics):
        info_to_save = dict(
            name=self._mjcf_model.model,
            position=physics.bind(self.mjcf_model.worldbody).xpos.tolist(),
            orientation=physics.bind(self.mjcf_model.worldbody).xquat.tolist(),
            floor_textures=[self.mjcf_model.find("geom", "floor").material.name],
            shadow=self.shadow
        )
        return info_to_save
    
    def build_default_scene(self):
        self._mjcf_model = mjcf.from_path(os.path.join(self.scene_asset_root, "default/empty.xml"))
        self._mjcf_model.model = "default"
        self.init_pos = [0, 0, 0]
        self.init_quat = [1, 0, 0, 0]
        self.randomness = None
        self.candidate_pos = None