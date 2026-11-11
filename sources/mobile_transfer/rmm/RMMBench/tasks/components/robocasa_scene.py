from RMMBench.utils.paths import PROJECT_ROOT
import json
import os

import numpy as np
from dm_control import composer
from dm_control import mjcf

from RMMBench.utils.register import register
from RMMBench.utils.utils import euler_to_quaternion, quaternion_multiply

ONE_WALL_SMALL = 0
ONE_WALL_LARGE = 1
L_SHAPED_SMALL = 2
L_SHAPED_LARGE = 3
GALLEY = 4
U_SHAPED_SMALL = 5
U_SHAPED_LARGE = 6
G_SHAPED_SMALL = 7
G_SHAPED_LARGE = 8
WRAPAROUND = 9

# negative values correspond to groups (see LAYOUT_GROUPS_TO_IDS)
ALL = -1
NO_ISLAND = -2
ISLAND = -3
DINING = -4

#param boundary: [xmin, xmax, ymin, ymax] or None
FIXTURES_CONFIG ={
    "U_SHAPED_LARGE": {
        "sink":{ "position": [3.200039841043554, -2.295000001845708, 0.9381176470588236],
        "orientation": [0, 0, 3.1415]},
        "stove":{
            "position": [3.6900000000000004, -0.3, 0.9261971830985917],
            "orientation": [0, 0, 0]}
    },
    "ONE_WALL_LARGE": {
            "stove":{ "position": [ 2.75,-0.3,0.9402205882352941],
            "orientation": [0, 0, 0]},

        }

}

MAP_CONFIG = {
    "ONE_WALL_LARGE": {
        "obstacles": ["island_counter_island_group"],
        "boundary": None,
    },
    "G_SHAPED_SMALL": {
        "obstacles": ["counter_1_front_group"],
        "boundary": None,
    },
    "L_SHAPED_SMALL": {
        "obstacles": None,
        "boundary": None,
    },
    "ONE_WALL_SMALL": {
        "obstacles": None,
        "boundary": None,
    },
    "WRAPAROUND": {
        "obstacles": None,
        "boundary": None,
    },
    "U_SHAPED_LARGE": {
        "obstacles": None,
        "boundary": None,
    },
    "GALLEY": {
        "obstacles": None,
        "boundary": None,
    }

}

# Fixtures for which each scene needs a workspace computed, along with the allowed placement
# directions (destination_positions) for each fixture.
# "around" means the fixture (typically an island-type fixture) can be placed on any of the four
# sides; the expansion logic is handled by the direction-selection logic at a higher level.
SCENE_FIXTURE_CONFIG = {
    "G_SHAPED_LARGE": {
        "stovetop_main_group": ["bottom"],
        "counter_main_main_group": ["bottom"],
        "sink_left_group": ["right"],
        "counter_1_left_group": ["right"],
        "counter_1_front_group": ["right", "bottom", "top"],
    },
    "G_SHAPED_SMALL": {
        "sink_right_group": ["left"],
        "counter_1_right_group": ["left"],
        "counter_main_main_group": ["bottom"],
        "counter_1_left_group": ["right"],
        "stove_left_group": ["right"],
        "counter_2_left_group": ["right"],
        "counter_1_front_group": ["left", "bottom", "top"],
    },
    "GALLEY": {
        "sink_left_group": ["right"],
        "counter_left_group": ["right"],
        "counter_main_main_group": ["left"],
        "stove_main_group": ["left"],
        "counter_right_main_group": ["left"],
    },
    "L_SHAPED_LARGE": {
        "counter_main_main_group": ["bottom"],
        "stovetop_main_group": ["bottom"],
        "counter_1_right_main_group": ["bottom"],
        "sink_left_group": ["right"],
        "counter_1_left_left_group": ["right"],
        "island_left_group": ["around"],
    },
    "L_SHAPED_SMALL": {
        "sink_main_group": ["bottom"],
        "counter_main_main_group": ["bottom"],
        "counter_1_right_group": ["left"],
        "stove_right_group": ["left"],
        "counter_2_right_group": ["left"],
    },
    "ONE_WALL_SMALL": {
        "sink_main_group": ["bottom"],
        "counter_main_main_group": ["bottom"],
        "stove_main_group": ["bottom"],
        "counter_right_main_group": ["bottom"],
    },
    "U_SHAPED_LARGE": {
        "counter_1_main_group": ["bottom"],
        "stovetop_main_group": ["bottom"],
        "counter_main_main_group": ["bottom"],
        "counter_1_left_group": ["right"],
        "counter_1_right_group": ["left"],
        "sink_island_group": ["top"],
        "island_island_group": ["around"],
    },
    "U_SHAPED_SMALL": {
        "sink_main_group": ["bottom"],
        "counter_main_main_group": ["bottom"],
        "counter_1_right_group": ["left"],
        "stove_right_group": ["left"],
        "counter_2_right_group": ["left"],
        "counter_1_left_group": ["right"],
    },
    "WRAPAROUND": {
        "counter_main_main_group": ["bottom"],
        "stove_main_group": ["bottom"],
        "counter_1_main_group": ["bottom"],
        "sink_right_group": ["left"],
        "counter_1_right_group": ["left"],
        "island_island_group": ["top", "bottom", "left"],
        "counter_1_front_group": ["top"],
    },
    "ONE_WALL_LARGE": {
        "counter_main_main_group": ["bottom"],
        "stovetop_main_group": ["bottom"],
        "counter_2_main_group": ["bottom"],
        "sink_island_group": ["top"],
        "island_counter_island_group": ["around"],
    },
}

@register.add_entity("RobocasaScene")
class RobocasaScene(composer.Entity):
    def __init__(self, *args, **kwargs):
        self.scene_asset_root = os.path.join(PROJECT_ROOT, "assets/scenes_fixtures")
        self.scene_fixtures = os.path.join(PROJECT_ROOT, "assets/scenes_fixtures/fixtures")
        super().__init__(*args, **kwargs)

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
        # Check whether the xml component info is complete; fall back to the _1 variant if missing
        name = kwargs.get("name","ONE_WALL_LARGE_1")

        xml_path = os.path.join(self.scene_asset_root, name + ".xml")
        # self.relative_xml_path = xml_path.split(self.scene_asset_root)[-1][1:] if xml_path is not None else None # for save the entity info
        self._mjcf_model = mjcf.from_path(xml_path)
        self._mjcf_model.model = name

        self.init_pos = np.array(kwargs.get("position", [0, 0, 0]))
        self.init_quat = np.array(kwargs.get("orientation", [1, 0, 0, 0]))
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


        # self.f_name = "shelves_main_group"
        # self.set_fixture_sites_visual(self.f_name)
        # self.set_fixture_sites_visual("counter_corner_2_right_group")

        # self.set_fixture_sites_visual("counter_1_main_group")
        # self.set_fixture_sites_visual("counter_right_main_group")

        # self.set_fixture_sites_visual("cab_corner_4_left_group")
        # self.set_fixture_sites_visual("stovetop_main_group")


    def contain(self, point, container_name, physics, z_th=0.1):
        """
        Determine whether a single point lies inside a container; return True or False.

        Args:
            point: the 3D point [x, y, z] to check
            container_name: name of the container, used to identify its type
            physics: MuJoCo physics object
            z_th: detection threshold for the upward extension applied to flat containers
        """
        sites_pos = self.get_sites(physics, container_name)

        # Extract the AABB base reference points
        p0 = sites_pos['_ext_p0']
        px = sites_pos['_ext_px']
        py = sites_pos['_ext_py']
        pz = sites_pos['_ext_pz']

        min_x, max_x = min(p0[0], px[0]), max(p0[0], px[0])
        min_y, max_y = min(p0[1], py[1]), max(p0[1], py[1])

        flat_containers = ["stovetop"]  # list of flat container types, maintained here
        is_flat = any(name in container_name.lower() for name in flat_containers)

        if is_flat:
            min_z = p0[2]
            max_z = p0[2] + z_th
        else:
            min_z, max_z = min(p0[2], pz[2]), max(p0[2], pz[2])

        is_inside = (min_x <= point[0] <= max_x) and \
                    (min_y <= point[1] <= max_y) and \
                    (min_z <= point[2] <= max_z)

        return is_inside




    def get_sites(self,physics,fixture_name):
        suffixes = ["_int_p0","_ext_p0", "_ext_px", "_ext_py","_ext_pz"]
        sites_pos = dict()
        for suffix in suffixes:
            site_name = fixture_name + suffix
            site = self.mjcf_model.find("site", site_name)
            site_pos = physics.bind(site).xpos
            sites_pos[suffix]=np.array(site_pos)
        return sites_pos

    def get_obstacles_bbox(self,physics):
        bbox_list = []
        scene_name = self.mjcf_model.model.rsplit("_",1)[0]
        if MAP_CONFIG[scene_name]["obstacles"] is not None:
            for obstacle in MAP_CONFIG[scene_name]["obstacles"]:
                sites_pos = self.get_sites(physics, obstacle)
                px = sites_pos['_ext_px']
                py = sites_pos['_ext_py']

                min_x, max_x = min(py[0], px[0]), max(py[0], px[0])
                min_y, max_y = min(px[1], py[1]), max(px[1], py[1])
                bbox_list.append([min_x, min_y, max_x, max_y])
        else:
            bbox_list=[]
        return {
            "bbox_list": bbox_list,
            "boundary": MAP_CONFIG[scene_name]["boundary"]
        }

    def set_fixture_sites_visual(self, fixture_name):
        # Define the suffixes to look up
        # The first four are center points
        if isinstance(fixture_name, list):
            for name in fixture_name:
                suffixes = ["_int_p0", "_ext_p0", "_ext_px", "_ext_py", "_ext_pz"]

                for suffix in suffixes:
                    site_name = name + suffix
                    site = self.mjcf_model.find("site", site_name)

                    if site is not None:
                        # Use physics.bind to modify runtime attributes
                        site.rgba = np.array([])
                        site.size = [0.02]
        else:
            suffixes = ["_int_p0","_ext_p0", "_ext_px", "_ext_py", "_ext_pz"]

            for suffix in suffixes:
                site_name = fixture_name + suffix
                site = self.mjcf_model.find("site", site_name)

                if site is not None:
                    # Use physics.bind to modify runtime attributes
                    site.rgba[-1]=1
                    site.size = [0.03]


    def get_site_by_name(self, site_name, physics):
        """
        Look up a site and its world xpos by its full site_name.

        site_name format: the full MJCF site name (without the body path),
        e.g. "stovetop_knob_front_center_0_grasp_knob"

        Args:
            site_name: str, the full name of the site
            physics: dm_control Physics object

        Returns:
            (site, site_xpos): the site object and its world coordinates,
            or (None, None) if not found
        """
        # Option 1: look up directly at the mjcf_model root level
        site = self._mjcf_model.find("site", site_name)
        if site is not None:
            return site, physics.bind(site).xpos

        # Option 2: iterate over sites under all bodies (handles nested cases)
        for body in self._mjcf_model.worldbody.find_all('body'):
            for site in body.find_all('site'):
                if site.name == site_name:
                    return site, physics.bind(site).xpos

        return None, None

    def print_body_xpos(self, physics, body_name):
        """
        Look up the specified body and print its world xpos.

        Args:
            physics: dm_control Physics object
            body_name: str, the full name of the body
        """
        body = self._mjcf_model.find("body", body_name)
        if body is not None:
            xpos = physics.bind(body).xpos
            print(f"[RobocasaScene] Body '{body_name}' world xpos: {xpos}")
        else:
            print(f"[RobocasaScene] Body '{body_name}' not found in scene")

    @property
    def mjcf_model(self):
        return self._mjcf_model

    @property
    def name(self):
        return self.mjcf_model.model

    def initialize_episode(self, physics, random_state):
        """
        Take domain randomization here.
        """
        new_xpos, new_xquat = self.init_pos.copy(), self.init_quat.copy()
        if self.parent_entity is not None:
            if self.parent == self.parent_entity: pass# if the attached parent equals to the value parent_entity, no additional transformaton need to apply
            else: # else, compute the relative pose of the parent entity
                new_xpos += self.parent_entity.init_pos
                new_xquat = quaternion_multiply(self.parent_entity.init_quat, new_xquat)
        if self.randomness is not None:
            if self.randomness.get("pos", None) is not None:
                new_xpos = new_xpos + self.randomness["pos"] * random_state.uniform([-1, -1, -1], [1, 1, 1])
            if self.randomness.get("quat", None) is not None:
                new_xquat = quaternion_multiply(new_xquat,
                                                euler_to_quaternion(*(self.randomness["quat"] * random_state.uniform([-np.pi, -np.pi, -np.pi], [np.pi, np.pi, np.pi]))))
            if self.randomness.get("scale", None) is not None:
                # modify the scale of the mesh, size and relative pos of geom
                self.set_scale(physics, self.randomness.get("scale"))
        self.set_pose(physics, new_xpos, new_xquat)

        # ── Inspect the world xpos of a specified body ─────────────────────
        # self.print_body_xpos(physics, "stovetop_main_group_main")
        # exit()
        # self.print_body_xpos(physics, "stovetop_main_group_knob_front_right")

        # fix_name = "sink_main_group"
        # sites_pos = self.get_sites(physics, self.f_name)
        # print(f"{self.f_name}: sites pos:{sites_pos}")
        # #
        # fix_name = "counter_right_main_group"
        # sites_pos = self.get_sites(physics, fix_name)
        # print(f"{fix_name}: sites pos:{sites_pos}")
        #-----------Process the robocasa scene config
        # fixture_config = SCENE_FIXTURE_CONFIG.get(scene_type)
        # if fixture_config is not None:
        #     results = self.get_fixture_workspaces(physics, fixture_config, scene_type)
        # else:
        #     print(f"Warning: No SCENE_FIXTURE_CONFIG entry found for scene type '{scene_type}', skip workspace computation.")
        # exit()
        #------------Process the robocasa scene config
        # self.deal_robocasa_json(physics)
        # self.contain(physics,"stovetop_main_group")


        return super().initialize_episode(physics, random_state)

    def calculate_workspace_and_center(self,sites_pos):
        """
        Compute the center point and the external bounding range from sites_pos.
        """
        # 1. Get the center point _int_p0
        center_pos = sites_pos.get('_int_p0')
        if center_pos is not None:
            # Convert to a list (if it is a numpy array)
            center_pos = center_pos.tolist() if isinstance(center_pos, np.ndarray) else center_pos

        # 2. Extract all points with the _ext prefix
        ext_points = [pos for key, pos in sites_pos.items() if key.startswith('_ext')]

        if not ext_points:
            return {"workspace": None, "center": center_pos}

        # Convert the point set into a numpy matrix for slicing: shape (N, 3)
        ext_matrix = np.array(ext_points)

        # 3. Compute the min/max value along each axis
        x_min, x_max = np.min(ext_matrix[:, 0]), np.max(ext_matrix[:, 0])
        y_min, y_max = np.min(ext_matrix[:, 1]), np.max(ext_matrix[:, 1])
        z_min, z_max = np.min(ext_matrix[:, 2]), np.max(ext_matrix[:, 2])

        # 4. Assemble the result dictionary
        result = {
            "workspace": [float(x_min), float(x_max), float(y_min), float(y_max), float(z_min), float(z_max)],
            "center": center_pos
        }

        return result

    def deal_robocasa_json(self,physics):
        dir_path = "/Users/lh/work/RMMBench/RMMBench/configs/robocasa_scenes_config"
        file_path = os.path.join(dir_path, "ONE_WALL_LARGE.json")
        counter_list = []
        # 1. Load the JSON file
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                arena_data = json.load(f)

                print(f"{'Name':<35} | {'Size'}")


            # 2. Iterate over the outer list (each element is a group dict, e.g. {'main_group': [...]})
            for group in arena_data:
                # 3. Iterate over the key-value pairs of the dict
                for group_name, fixtures in group.items():
                    # 4. Iterate over each fixture in the group
                    for item in fixtures:
                        # 5. Check whether name contains "counter"
                        if "counter" in item.get("name", ""):
                            name = item.get("name")
                            size = item.get("size", "N/A")  # show N/A if size is absent
                            p = self.mjcf_model.find("site", name+"_int_p0")
                            p1 = physics.bind(p).xpos
                            print("size:{}".format(size))
                            print("p1:", p1)
                            size_z = size[2]/2
                            placecenter = [float(p1[0]), float(p1[1]), float(p1[2] + size_z + 0.1)]
                            print("placecenter:", placecenter)
                            # Store the current counter into the dict
                            counter_info = {
                                "name": name,
                                "placecenter": placecenter,
                                "size": size
                            }
                            counter_list.append(counter_info)
        final_output = {
            "counter": counter_list
        }
        output_file = "/Users/lh/work/RMMBench/RMMBench/configs/robocasa_scenes_config/ONE_WALL_LARGE_points.json"
        # --- Write to a new JSON file ---
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)

        print(f"提取完成，已保存至: {output_file}")
        exit()

    # def save(self, physics):
    #     info_to_save = dict(
    #         name=self._mjcf_model.model,
    #         position=physics.bind(self.mjcf_model.worldbody).xpos.tolist(),
    #         orientation=physics.bind(self.mjcf_model.worldbody).xquat.tolist(),
    #     )
    #     return info_to_save

    def save(self, physics):
        info_to_save=dict(
            name=self.mjcf_model.model,
            # xml_path=self.relative_xml_path,
            position=self.get_xpos(physics).tolist(),
            orientation=self.get_xqaut(physics).tolist(),
        )
        info_to_save["class"] = self.__class__.__name__
        return info_to_save

    def get_xpos(self, physics):
        return physics.bind(self._mjcf_model.worldbody).xpos

    def get_xqaut(self, physics):
        return physics.bind(self._mjcf_model.worldbody).xquat

    def build_from_config(self, config_path, **kwargs):
        config = self.load_config(config_path)
        self._build(**config)

    def get_entity_pcd(self, env):
        """
        Get the point cloud of the entity
        """
        geom_ids = [env.physics.bind(geom).element_id for geom in self.geoms]
        obs = env.get_observation()
        rgb = obs["rgb"]
        depth = obs["depth"]
        segmentation = obs["segmentation"]
        masks = np.where((segmentation[..., 0] <= max(geom_ids))&(segmentation[..., 0] >= min(geom_ids)), 1, 0).astype(np.uint8)
        env.pcd_generator.physics = env.physics
        entity_pcd = env.pcd_generator.generate_pcd_from_rgbd(target_id=list(range(env.physics.model.ncam - 1)),
                                                                rgb=rgb,
                                                                depth=depth,
                                                                mask=masks)
        return entity_pcd

    def get_fixture_workspaces(self, physics, fixture_config, scene_name, save_to_json=True):
        """
        Compute the operational workspace of each fixture using the bounding-box extrema method.

        Args:
            physics: dm_control Physics object
            fixture_config: dict, {fixture_name: [destination_position, ...]},
                            i.e. SCENE_FIXTURE_CONFIG[scene_name]
            scene_name: str, scene type name (e.g. "ONE_WALL_LARGE"), used as the key written into the JSON
            save_to_json: bool, whether to write the result into robocasa_scene_config.json
        """
        scene_data = {}

        for name, destination_positions in fixture_config.items():
            try:
                # 1. Get the physics pose sites
                sites_pos = self.get_sites(physics, name)

                # 2. Call the optimization algorithm to compute the Workspace and Center
                res = self.calculate_workspace_and_center(sites_pos)

                workspace = res["workspace"]
                center = res["center"]

                if workspace is None:
                    print(f"Warning: No _ext sites found for {name}")
                    continue

                # 3. Compute Dimensions (auxiliary, for inspection; still useful)
                dim_x = float(workspace[1] - workspace[0])
                dim_y = float(workspace[3] - workspace[2])
                dim_z = float(workspace[5] - workspace[4])

                # 4. Populate the structure
                scene_data[name] = {
                    "workspace": workspace,
                    "center": center,
                    "dimensions": {
                        "x": round(dim_x, 3),
                        "y": round(dim_y, 3),
                        "z": round(dim_z, 3)
                    },
                    "destination_positions": destination_positions
                }
            except Exception as e:
                print(f"Skipping {name} in {scene_name}: {e}")

        # 5. Save or print
        if save_to_json:
            self._update_scene_config(scene_name, scene_data)
            print(f"Success: Corrected config for {scene_name} saved.")

        return scene_data

    @property
    def geoms(self):
        return self._mjcf_model.find_all('geom')

    def _update_scene_config(self, scene_name, scene_data, filename="/Users/lh/work/RMMBench/RMMBench/configs/robocasa_scenes_config/robocasa_scene_config.json"):
        """
        Deep-update the JSON so that other scenes, or other fixtures within the same scene,
        are not overwritten
        """
        print("1111111")
        all_data = {}
        if os.path.exists(filename):
            print("222222")

            with open(filename, 'r') as f:
                try:
                    all_data = json.load(f)
                    print("all_data", all_data)
                    print("f:",f)
                except:
                    pass

        if scene_name not in all_data:
            all_data[scene_name] = {}

        # Update flattened by fixture_name, without keeping the group_name layer
        all_data[scene_name].update(scene_data)

        with open(filename, 'w') as f:
            json.dump(all_data, f, indent=4)