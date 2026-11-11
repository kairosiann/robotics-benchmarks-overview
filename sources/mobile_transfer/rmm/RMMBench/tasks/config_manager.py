from RMMBench.utils.paths import PROJECT_ROOT
import copy
import random
import numpy as np
import os
import json
import re

from numpy.lib.user_array import container
from torch.sparse import sampled_addmm

from RMMBench.configs import name2config
from RMMBench.configs.constant import name2class_xml
import RMMBench.tasks.components as components

from RMMBench.utils.utils import flatten_list, grid_sample, find_key_by_value,xml_path_completion
# from  RMMBench.utils.robocasa_utils import FixtureStack,get_relative_position,load_style_config,xml_path_completion,check_syntax
import yaml

from RMMBench.utils.create_task.workspace_object_layout import get_work_info,layout_objects_with_robot
from RMMBench.tasks.components.robocasa_scene import FIXTURES_CONFIG


DEFAULT_RABDOMNESS = dict(
    pos=[0.02, 0.02, 0],
    quat=[0, 0, 0.05],
)



class BenchTaskConfigManager():
    """
    Config manager class for task configuration load and management.
    The items of config should include: robot, task, engine.
    For each children classes, they differs from the task-specific assets, layouts, conditions and instructions.
    Basic assets layout include: 
        (un)seen objects - the objects that can be manipulated.
        (un)seen containers - the cintainer that is empty at the begining but can be used to hold objects.
        (un)seen init_containers - the container that is filled with objects at the begining. 
    """

    def __init__(self, 
                 task_name,
                 num_objects=[3],
                 **kwargs):
        """
        param:
            config: base config from yaml file
        """
        self. distractions = []
        self.direct_limit = None
        self.grasp_task = None
        self.target_bbox = None
        self.center_pos = None
        self.destination_position = None
        self.objects = None
        self.work_info = None
        # default config
        self.config = dict(
            task=dict(
                ngrid=[10, 10],
                n_distractor=1,
                workspace=[-0.3, 0.3, -0.2, 0.2, 0.8, 1.5]
            )
        )
        self.task_name = task_name
        # load additional config from task_config.json
        with open(os.path.join(PROJECT_ROOT, "configs/task_config.json"), "r") as f:
            configs = json.load(f)
        config = configs.get("default", {})
        config.update(configs.get(find_key_by_value(name2config, task_name), None))
        if config is None: 
            raise ValueError(f"Task {task_name} is invalid. Check the valid ones task_config.json file.")
        self.config.update(config)
        if "components" not in self.config["task"]:
            self.config["task"]["components"] = []
        # init assets config
        self.num_objects = num_objects

        if "asset" not in self.config["task"]: self.config["task"]["asset"] = {}
        for attr in["fixed_fixture","random_scene","destination_position","fixture_surface","robocasa_scene","mid_contain","mid_container","sample_strategy","split_ratio","class_1","class_2","distractor","seen_object", "unseen_object", "seen_container", "unseen_container", "seen_init_container", "unseen_init_container"]:
            if attr not in self.config["task"]["asset"]:
                value = kwargs[attr] if attr in kwargs else None
            else:
                value = self.config["task"]["asset"][attr]                     
            setattr(self, attr, value)




        # Compatibility: distractor is the preferred name for unseen_object
        if self.distractor is None and self.unseen_object is not None:
            self.distractor = self.unseen_object
        elif self.unseen_object is None and self.distractor is not None:
            self.unseen_object = self.distractor


        self.mid_container_mapping = {}
        self.container_mapping = {}



        if "work_region" in self.config["task"]:
            region_config = self.config["task"]["work_region"]
            for attr in ["workspace", "anchor", "offset", "target_dim", "grid_nums"]:
                if attr in region_config:
                    value = region_config[attr]
                else:
                    # If a config item is missing, try to get it from kwargs, otherwise set to None
                    value = kwargs[attr] if attr in kwargs else None
                setattr(self, attr, value)


        if getattr(self, "fixed_fixture", None) is not None:
            for fixture in self.fixed_fixture:
                scene_name = self.robocasa_scene.rsplit("_",1)[0]
                fixture_info = FIXTURES_CONFIG[scene_name][self.extract_base_name(fixture)]
                fixture_config = self.get_entity_config(fixture, fixture_info["position"], fixture_info["orientation"])
                self.config["task"]["components"].append(fixture_config)
        self.kwargs = kwargs


    def get_all_entities(self,seen_object=None,distractor=None,seen_container=None,init_container=None):
        self.all_entities = flatten_list(seen_object)+flatten_list(distractor)+flatten_list(seen_container)+flatten_list(init_container)
        self.all_object = []
        self.all_object.append(seen_object)
        self.all_object.append(distractor)
        self.all_cleaned_entities = [self.extract_base_name(entity) for entity in self.all_entities ]

    def extract_base_name(self, name):

        if isinstance(name, list):
            name = flatten_list(name)[0]
        return re.sub(r'_\d+$', '', name)

    def get_camera_config(self):
        camera_task_name = find_key_by_value(name2config, self.task_name)
        self.config["task"]["camera_task_name"] = camera_task_name

    @staticmethod
    def _flatten_entities(entities):
        """Like flatten_list but preserves dict items as single entities (for mid-contain parent-child)."""
        if isinstance(entities, (str, dict)):
            return [entities]
        if entities is not None:
            new_list = []
            for item in entities:
                if isinstance(item, list):
                    new_list.extend(BenchTaskConfigManager._flatten_entities(item))
                elif isinstance(item, (str, dict)):
                    new_list.append(item)
            return new_list
        return []

    def get_object_info(self,workregion_offset = 0,workregion_y_set = 0,target_dim = (0.8,0.4),grid_size=[10,10]):
        if self.fixture_surface:
            with open(os.path.join(PROJECT_ROOT, "configs/robocasa_scenes_config/robocasa_scene_config.json"), "r") as f:
                configs = json.load(f)
            scene_name = self.robocasa_scene.rsplit("_",1)[0]
            workspace = configs[scene_name][self.fixture_surface]["workspace"]
            self.work_info = get_work_info(workspace,target_dim=target_dim, anchor=self.destination_position,offset_dist=workregion_offset,y_set=workregion_y_set)
            workregion = self.work_info["workregion"]
            mid_children_count = sum(len(children) for children in self.mid_container_mapping.values())
            mid_parents_count = len(self.mid_container_mapping)
            container_mid_children_count=sum(len(children) for children in self.container_mapping.values())


            n_samples = len(self._flatten_entities(self.target_entity)+self._flatten_entities(self.distractor)) + mid_parents_count - mid_children_count-container_mid_children_count


            self.sampled_points = grid_sample(
                workregion,
                grid_size=grid_size,
                n_samples=n_samples,
                mid_container_sample=self.sample_strategy,
                n_mid=mid_parents_count,
                destination_position=self.destination_position,
                split_ratio=self.split_ratio if self.split_ratio is not None else 0.5,
            )


        # self.object_configs = layout_objects_with_robot(work_info, self.seen_container[0], self.all_object,
        #                                     arrange_type="long")

    def get_container_info_from_workregion(self, work_info, anchor="left", direction="left", offset=0.1,y_set=0.1, z_set=0.01,orient_offset=[0,0,0]):
        workregion = work_info["workregion"]
        orientation = work_info["object_orientation"]
        xmin, xmax, ymin, ymax, zmin, zmax = workregion
        x_mid = (xmin + xmax) / 2
        y_mid = (ymin + ymax) / 2

        mapping = {
            "left": {  # Robot looks rightward from Xmin
                "left": [x_mid+y_set, ymax + offset],  # Left-hand side is Y+
                "right": [x_mid+y_set, ymin - offset],  # Right-hand side is Y-
                "top": [xmax + y_set, ymin - offset]  # Right-hand side is Y-

            },
            "right": {  # Robot looks leftward from Xmax
                "left": [x_mid-y_set, ymin - offset],  # Left-hand side is Y-
                "right": [x_mid-y_set, ymax + offset] ,# Right-hand side is Y+
                "top": [x_mid + y_set, ymax + offset]  # Right-hand side is Y+

            },
            "bottom": {  # Robot looks upward from Ymin
                "left": [xmin - offset, y_mid+y_set],  # Left-hand side is X-
                "right": [xmax + offset, y_mid+y_set],
                "top": [x_mid+offset , ymax + y_set]  # Right-hand side is Y-
                # Right-hand side is X+
            },
            "top": {  # Robot looks downward from Ymax
                "left": [xmax + offset, y_mid-y_set],  # Left-hand side is X+
                "right": [xmin - offset, y_mid-y_set],  # Right-hand side is X-
                "top": [x_mid - offset, ymin - y_set]  # Right-hand side is Y-

            }
        }

        container_xy = mapping[anchor][direction]
        container_pos = [container_xy[0], container_xy[1], zmax + z_set]
        container_info = {
            "position": container_pos,
            "orientation": np.array(orientation)+orient_offset,
        }
        return container_info




    def get_seen_task_config(self):
        self.mid_mapping()
        # Load single or multiple targets by default
        self.get_all_entities(self.seen_object, self.distractor, self.seen_container)
        # Add mid_container parents to all_entities
        if self.mid_container_mapping:
            mid_parents = list(self.mid_container_mapping.keys())
            self.all_entities = self.all_entities + mid_parents
            self.all_cleaned_entities = self.all_cleaned_entities + [self.extract_base_name(p) for p in mid_parents]

        if len(self.num_objects)>0 and self.distractor is not None:
            self.distractor = random.sample(self.distractor, self.num_objects[0])

        target_entity = random.choice(self.seen_object)
        if isinstance(target_entity, list):
            target_entity = random.choice(target_entity)
        if self.seen_container is not None:
            container = random.choice(self.seen_container)
        else:
            container = None
        if self.seen_init_container is not None:
            init_container = random.choice(self.seen_init_container)
        else:
            init_container= None

        mid_contain=self.mid_contain
        return self.get_task_config(target_entity=target_entity,
                                    target_container=container,
                                    init_container=init_container,
                                    mid_contain = mid_contain,
                                    **self.kwargs)


    def get_unseen_task_config(self):
        target_entity = random.choice(self.unseen_object)

        if isinstance(target_entity, list):
            target_entity = random.choice(target_entity)

        if self.unseen_container is not None:
            container = random.choice(self.unseen_container)
        else:
            container = None
        if self.unseen_init_container is not None:
            init_container = random.choice(self.unseen_init_container)
        else:
            init_container= None
        return self.get_task_config(target_entity=target_entity, 
                                    target_container=container, 
                                    init_container=init_container,
                                    **self.kwargs)


    def get_entity_config(self, target_entity:str, position=[0,0,0.8], orientation=[0, 0, 0], randomness=None, **kwargs):
        name = kwargs.get("specific_name", f"{target_entity}")
        xml_path = name2class_xml[target_entity][-1]
        if isinstance(xml_path, list):
            xml_path = random.choice(xml_path)
        entity_config = dict(
            name=name,
            xml_path=xml_path,
            position=position,
            orientation=orientation
        )
        entity_config.update(**kwargs)
        entity_config["class"] = kwargs.get("dclass", name2class_xml[target_entity][0])
        entity_config["randomness"] = randomness.copy() if randomness is not None else None
        # print("vlabench_entity_config", entity_config)
        return entity_config
    
    def get_instruction(self, target_entity,target_container,init_container=None,**kwargs):
        """
        automatically generate instruction for the task
        """
        self.cleaned_entity = self.extract_base_name(target_entity)
        if target_container is not None:
            self.cleaned_container = self.extract_base_name(target_container)
        if init_container is not None:
            self.cleaned_init_container = self.extract_base_name(init_container)


    def get_task_config(self, target_entity, target_container, init_container, mid_contain=None,**kwargs):
        """
        Load task related entity configs.
        param:
            target_entity: target entity to manipulate in most common tasks
            target_container: target container to place the target entity
            init_container: task the target entity from the init containers 
        """
        # Backward compat: old callers may pass other_entity=, redirect to distractor
        other_entity = kwargs.pop("other_entity", None)
        if other_entity is not None:
            self.distractor = other_entity

        self.target_entity, self.target_container, self.init_container = target_entity, target_container, init_container
        self.get_object_info()
        self.load_robocasa_scene()


        self.load_containers(target_container=target_container)
        self.load_init_containers(init_container=init_container)
        self.load_mid_contain(mid_contain=mid_contain)

        self.load_objects( target_entity=target_entity)
        self.get_condition_config(target_entity=target_entity, target_container=target_container, init_container=init_container)
        self.get_instruction(target_entity=target_entity, target_container=target_container, init_container=init_container)
        self.get_camera_config()
        return self.config


    def get_condition_config(self, target_entity, target_container, **kwargs):
        """
        Load the task-specific condition config, including condition names and their parameters
        param:
            config: base config from yaml file
        """
        raise NotImplementedError


    def load_robocasa_scene(self):
        if self.robocasa_scene is not None:

            if self.random_scene:
                base_name = "_".join(self.robocasa_scene.split('_')[:-1]) if self.robocasa_scene.endswith(
                    tuple(map(str, range(5)))) else self.robocasa_scene
                if not base_name:
                    base_name = self.robocasa_scene
                random_num = random.choice([0, 2, 4, 5])
                self.robocasa_scene = f"{base_name}_{random_num}"
            else:
                if not self.robocasa_scene[-1].isdigit():
                    self.robocasa_scene = f"{self.robocasa_scene}_0"
            entity_config = dict(
                name=self.robocasa_scene,
                position=[0,0,0],
                orientation=[0,0,0]
            )
            # print("self.robocasa_scene:",self.robocasa_scene)

            entity_config["class"] = components.robocasa_scene.RobocasaScene
            entity_config["randomness"] = None
            # print("robocasa_entity_config:",entity_config)
            self.config["task"]["components"].append(entity_config)


    def load_containers(self, target_container,offset=0.3,y_set = 0.1,direction="left",z_set=0,orient_offset=[0,0,0]):
        if target_container is not None:
            if self.work_info and self.target_container:
                container_info = self.get_container_info_from_workregion(self.work_info,
                                                                         anchor=self.destination_position,
                                                                         offset=offset,
                                                                         y_set = y_set,
                                                                         z_set = z_set,
                                                                        direction = direction
                                                                         )
                container_config = self.get_entity_config(target_container,
                                                          position=container_info["position"],
                                                          orientation=np.array(container_info["orientation"])+orient_offset,)


                for parent, children in self.container_mapping.items():
                    if parent == target_container:

                        container_config["subentities"] = []
                        for j, child in enumerate(children):

                            child_config = self.get_entity_config(child,
                                                                  position=[j * 0.1 - 0.05 * (len(children) - 1), 0, 0],
                                                                  orientation=[0, 0, 0])
                            container_config["subentities"].append(child_config)


                self.config["task"]["components"].append(container_config)

            else:
                container_config = self.get_entity_config(target_container)
                self.config["task"]["components"].append(container_config)


    def load_mid_contain(self, mid_contain,position=[0,0,0],orientation=[0,0,0],randomness=None):
        if mid_contain is not None:
            for container_key, items in mid_contain.items():
                container_config = self.get_entity_config(container_key,position,orientation,randomness)
                self.config["task"]["components"].append(container_config)
                self.config["task"]["components"][-1]["subentities"]=[]
                for item_info in items:
                    name = item_info["name"]
                    pos = item_info["pos"]
                    if item_info["orien"]:
                        orien = item_info["orien"]
                    else:
                        orien = [0,0,0]
                    object_config = self.get_entity_config(name,
                                                           position=pos,
                                                           orientation=orien)
                    self.config["task"]["components"][-1]["subentities"].append(object_config)

    def load_init_containers(self, init_container):
        if init_container is not None:
            init_container_config = self.get_entity_config(init_container)
            self.config["task"]["components"].append(init_container_config)

    def mid_mapping(self):
        self.mid_container_mapping = {}
        self.container_mapping = {}

        if self.mid_container:
            seen_flat = set(flatten_list(self.seen_container)) if self.seen_container is not None else set()

            for item in self.mid_container:
                if isinstance(item, dict):
                    for parent, children in item.items():
                        target_map = self.container_mapping if parent in seen_flat else self.mid_container_mapping
                        target_map[parent] = children

    def load_objects(self, target_entity):
        if self.work_info:
            orientation = self.work_info["object_orientation"]
            all_objects = flatten_list(self.target_entity) + flatten_list(self.distractor)
            
            # Mid_container children go as subentities on parents, not on grid points
            mid_children = set()
            for children in self.mid_container_mapping.values():
                mid_children.update(children)
            for children in self.container_mapping.values():
                mid_children.update(children)

            regular_objects = [obj for obj in all_objects if obj not in mid_children]
            self.objects = regular_objects + list(self.mid_container_mapping.keys())
            
            z = self.work_info["z"]
            points_3d = [[x, y, z] for x, y in self.sampled_points]
            point_idx = 0

            for obj in regular_objects:
                object_config = self.get_entity_config(obj,
                                                       position=points_3d[point_idx],
                                                       orientation=orientation)
                self.config["task"]["components"].append(object_config)
                point_idx += 1
            
            # Place mid_container parents on grid points, with children as subentities

            for parent, children in self.mid_container_mapping.items():
                parent_config = self.get_entity_config(parent,
                                                       position=points_3d[point_idx],
                                                       orientation=orientation)
                parent_config["subentities"] = []
                for j, child in enumerate(children):
                    child_config = self.get_entity_config(child, position=[j * 0.1 - 0.05 * (len(children) - 1), 0, 0], orientation=[0, 0, 0])
                    parent_config["subentities"].append(child_config)
                self.config["task"]["components"].append(parent_config)
                point_idx += 1
        else:
            objects = []
            objects.append(target_entity)
            # self.other_objects = flatten_list(self.seen_object) + flatten_list(self.unseen_object)
            self.other_objects = flatten_list(self.seen_object)

            self.other_objects.remove(target_entity)
            objects.extend(random.sample(self.other_objects, self.num_object-1))

            for i, object in enumerate(objects):
                object_config = self.get_entity_config(object, position=[-0.1+i*0.1, 0.2, 0.8])
                self.config["task"]["components"].append(object_config)
    

    def get_entity_class(self,target_entity ):
        entity_cls = name2class_xml[target_entity][0]
        entity_class = str(entity_cls).split('.')[-1].replace("'>", "").replace("'", "")
        return entity_class

    def transform_position(self,position, parent_orient):
        x, y, z = position
        z_orient = round(parent_orient[2], 2)

        mapping = {
            0.00: [x, y, z],
            1.57: [-y, x, z],
            -1.57: [y, -x, z],
            3.14: [-x, -y, z],
            -3.14: [-x, -y, z]
        }

        return mapping.get(z_orient, position)


class Multi_traget_container(BenchTaskConfigManager):# Handles both flat and nested target objects
    def __init__(self, task_name, num_objects=[2,2], **kwargs):# num_objects = [num distractors, num targets]
        super().__init__(task_name,num_objects, **kwargs)
        self.CONTAINER_CONFIG_TABLE = [
                    {"offset": 0.2, "y_set": 0.05, "direction": "left", "z_set": 0.01},  # 1st container config
                    {"offset": 0.2, "y_set": 0.05, "direction": "right", "z_set": 0.01},  # 2nd container config (staggered position)
                    {"offset": 0, "y_set": 0.1, "direction": "top", "z_set": 0.01},  # 3rd container config (staggered position)
                ]

    def get_seen_task_config(self):
        self.mid_mapping()
        # Load single or multiple targets by default
        self.get_all_entities(self.seen_object, self.distractor, self.seen_container)
        # Add mid_container parents to all_entities
        if self.mid_container_mapping:
            mid_parents = list(self.mid_container_mapping.keys())
            self.all_entities = self.all_entities + mid_parents
            self.all_cleaned_entities = self.all_cleaned_entities + [self.extract_base_name(p) for p in mid_parents]
        if len(self.num_objects)>0 and self.distractor is not None:
            self.distractor = random.sample(self.distractor, self.num_objects[0])
        if isinstance(self.seen_object[0],str):
            seen = self.seen_object
            k = min(self.num_objects[1], len(seen))
            idx = sorted(random.sample(range(len(seen)), k))
            target_entity = [seen[i] for i in idx]
        else:# Handle the [[],[]] format; the result is a list where each inner [] represents a class, so target_entity should be in [[],[]] format
            target_entity = random.sample(self.seen_object, len(self.seen_container))
        if self.seen_container is not None:  # list
            container = self.seen_container
        else:
            container = None
        if self.seen_init_container is not None:
            init_container = random.choice(self.seen_init_container)
        else:
            init_container= None
        mid_contain=self.mid_contain
        return self.get_task_config(target_entity=target_entity,
                                    target_container=container,
                                    init_container=init_container,
                                    mid_contain = mid_contain,
                                    **self.kwargs)

    def get_task_config(self, target_entity, target_container, init_container, mid_contain=None,**kwargs):
        """
        Load task related entity configs.
        param:
            target_entity: target entity to manipulate in most common tasks
            target_container: target container to place the target entity
            init_container: task the target entity from the init containers
        """
        # Backward compat: old callers may pass other_entity=, redirect to distractor

        self.target_entity, self.target_container, self.init_container = target_entity, target_container, init_container
        self.get_object_info()
        self.load_robocasa_scene()
        # self.load_objects( target_entity=target_entity)
        if isinstance(target_container, list):
            for idx , container in enumerate(target_container):
                self.load_containers_for_layout(idx=idx,target_container=container)
        else:
            self.load_containers(target_container=target_container)

        self.load_init_containers(init_container=init_container)
        self.load_mid_contain(mid_contain=mid_contain)
        self.load_objects( target_entity=target_entity)
        self.get_condition_config(target_entity=target_entity, target_container=target_container, init_container=init_container)
        self.get_instruction(target_entity=target_entity, target_container=target_container, init_container=init_container)
        self.get_camera_config()
        return self.config

    def load_containers_for_layout(self, idx,target_container):
        """Load container config automatically based on the layout idx, and route to load_containers"""
        if idx < 0 or idx >= len(self.CONTAINER_CONFIG_TABLE):
            idx = 0
        layout_config = self.CONTAINER_CONFIG_TABLE[idx]
        if "orient_offset" in layout_config.keys():
            return self.load_containers(target_container, layout_config["offset"], layout_config["y_set"],
                                        layout_config["direction"],layout_config["z_set"], layout_config["orient_offset"])
        else:
            return self.load_containers(target_container,layout_config["offset"],layout_config["y_set"],layout_config["direction"],layout_config["z_set"])




class PressButtonConfigManager(BenchTaskConfigManager):     
    def get_condition_config(self, target_button, **kwargs):
        self.target_button = target_button
        conditions_config = dict(
            press_button=dict(
                target_button=target_button
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self, **kwargs):
        instruction = ["Press the button."]
        self.config["task"]["instructions"] =instruction
        return self.config
    
    def load_buttons(self, **kwargs):
        for i in range(self.num_object):
            button_config = self.get_entity_config("button", 
                                                   position=[-0.4+i*0.4+random.uniform(-0.05, 0.05), 
                                                             random.uniform(-0.2, 0), 
                                                             0.78],
                                                   specific_name=f"button{i}")
            self.config["task"]["components"].append(button_config)

class ClassifyConfigManager(BenchTaskConfigManager):
    def __init__(self, task_name, sample_nums=None, **kwargs):
        super().__init__(task_name, **kwargs)
        self.sample_nums = sample_nums if sample_nums is not None else [1, 1]

    def get_seen_task_config(self):
        # Nested list [[...], [...]]: multiple groups of objects to manipulate, sample each group by sample_nums
        self.get_all_entities(self.seen_object, self.distractor, self.seen_container)

        if self.seen_object and isinstance(self.seen_object[0], list):
            target_entity = []
            for i, group in enumerate(self.seen_object):
                n = self.sample_nums[i] if i < len(self.sample_nums) else 1
                n = min(n, len(group))
                target_entity.append(random.sample(group, n))
        else:
            target_entity = random.choice(self.seen_object)
        if self.seen_container is not None:
            container = random.choice(self.seen_container)
        else:
            container = None
        mid_contain=self.mid_contain

        return self.get_task_config(target_entity=target_entity,
                                    target_container=container,
                                    mid_contain = mid_contain,
                                    init_container=None,
                                    **self.kwargs)

    def load_containers(self, target_container, offset=0.3, y_set=0.1, direction="left"):
        if isinstance(target_container, str):
            if self.work_info and self.target_container:
                container_info = self.get_container_info_from_workregion(self.work_info,
                                                                         anchor=self.destination_position,
                                                                         offset=offset,
                                                                         y_set=y_set,
                                                                         direction=direction
                                                                         )
                container_config = self.get_entity_config(target_container,
                                                          position=container_info["position"],
                                                          orientation=container_info["orientation"], )
                self.config["task"]["components"].append(container_config)
            else:
                container_config = self.get_entity_config(target_container)
                self.config["task"]["components"].append(container_config)
        elif isinstance(target_container, list):
            for i ,container in enumerate(target_container):
                direction = "left" if i==0 else "right"
                container_info = self.get_container_info_from_workregion(self.work_info,
                                                                         anchor=self.destination_position,
                                                                         offset=offset,
                                                                         y_set=y_set,
                                                                         direction=direction
                                                                         )
                container_config = self.get_entity_config(container,
                                                          position=container_info["position"],
                                                          orientation=container_info["orientation"], )
                self.config["task"]["components"].append(container_config)

    def load_objects(self, target_entity):

        if self.work_info:
            orientation = self.work_info["object_orientation"]
            all_objects = flatten_list(self.target_entity) + flatten_list(self.distractor)
            
            # Mid_container children go as subentities on parents, not on grid points
            mid_children = set()
            for children in self.mid_container_mapping.values():
                mid_children.update(children)
            
            regular_objects = [obj for obj in all_objects if obj not in mid_children]
            self.objects = regular_objects + list(self.mid_container_mapping.keys())

            z = self.work_info["z"]
            points_3d = [[x, y, z] for x, y in self.sampled_points]
            
            point_idx = 0
            for obj in regular_objects:
                object_config = self.get_entity_config(obj,
                                                       position=points_3d[point_idx],
                                                       orientation=[orientation[0],orientation[1],orientation[2]+point_idx*0.05])
                self.config["task"]["components"].append(object_config)
                point_idx += 1
            
            for parent, children in self.mid_container_mapping.items():
                parent_config = self.get_entity_config(parent,
                                                       position=points_3d[point_idx],
                                                       orientation=[orientation[0],orientation[1],orientation[2]+point_idx*0.05])
                parent_config["subentities"] = []
                for j, child in enumerate(children):
                    child_config = self.get_entity_config(child, position=[j * 0.1 - 0.05 * (len(children) - 1), 0, -0.05], orientation=[0, 0, 0])
                    parent_config["subentities"].append(child_config)
                self.config["task"]["components"].append(parent_config)
                point_idx += 1

    def get_instruction(self, **kwargs):
        instruction = ["Classify these objects into two appropriate positions."]
        self.config["task"]["instructions"] = instruction

    def get_condition_config(self, target_entity, target_container, **kwargs):

        conditions_config = dict(
            contain_v=dict(
                container=target_container,
                entities=f"{target_entity}",
                vel_th=0.01,
            )
            ,
            scene_contain=dict(
                scene="ONE_WALL_LARGE_1",
                container_name="sink_island_group",
                entities=f"{target_entity}",
                vel_th=0.01,
            )
        )

        self.config["task"]["conditions"] = conditions_config


class ClusterConfigManager(BenchTaskConfigManager):
    def get_seen_task_config(self):
        assert isinstance(self.seen_object, list) and isinstance(self.seen_object[-1], list), "similar objects in a list"
        target_entities = random.sample(self.seen_object, 2)
        containers = [random.choice(self.seen_container) for _ in range(2)]
        # print("target_entities:",target_entities)
        # print("self.seen_object:",self.seen_object)
        # print("self.seen_container:",self.seen_container)
        # print("containers:",containers)

        return self.get_task_config(target_entity=target_entities, target_container=containers, init_container=None, **self.kwargs)

    def get_unseen_task_config(self):
        assert isinstance(self.unseen_object, list) and isinstance(self.unseen_object[-1], list), "similar objects in a list"
        target_entities = random.sample(self.unseen_object, 2)
        containers = [random.choice(self.unseen_container) for _ in range(2)]
        return self.get_task_config(target_entity=target_entities, target_container=containers, init_container=None, **self.kwargs)
    
    def load_containers(self, target_container):
        assert isinstance(target_container, list), "containers should be more than 2 in clustering tasks"
        for i, container in enumerate(target_container):
            container_config = self.get_entity_config(container,
                                                      position=[(i-0.5)*0.6, random.uniform(-0.1, 0.1), 0.8], 
                                                      specific_name=f"{container}_{i}")
            self.config["task"]["components"].append(container_config)
    
    def load_objects(self, target_entity, **kwargs):
        assert isinstance(target_entity, list) and isinstance(target_entity[0], list), "target entities should be a list"
        self.entities_to_load = dict(
            cls_1 = [], cls_2 = []
        )
        for i, entities in enumerate(target_entity):# Pad a class up to the required count
            if len(entities) < self.num_object:
                for _ in range(self.num_object - len(entities)):
                    entities.append(entities[-1])
            entities_in_same_class = random.sample(entities, self.num_object)   
            self.entities_to_load[f"cls_{i+1}"] = entities_in_same_class
        entities_to_load = []
        for ls in self.entities_to_load.values():
            entities_to_load.extend(ls)
        random.shuffle(entities_to_load)
        positions = grid_sample(workspace=self.config["task"]["workspace"], 
                                grid_size=self.config["task"]["ngrid"],
                                n_samples=self.num_object+self.num_object)
        for i, (entity, pos) in enumerate(zip(entities_to_load, positions)):
            pos = [pos[0], pos[1], 0.8]
            object_config = self.get_entity_config(entity, 
                                                   position=pos)
            self.config["task"]["components"].append(object_config)
            
    def get_instruction(self, **kwargs):
        instruction = ["Cluster the objects into two classes."]
        self.config["task"]["instructions"] = instruction
        
    def get_condition_config(self, target_entity, target_container, **kwargs):
        assert isinstance(target_entity[-1], list) and isinstance(target_container, list), "target entities and containers should be in list"
        for cls, objects in self.entities_to_load.items():
            if objects[0] == objects[-1]:
                objects[-1] = objects[-1] + "_1"
        condition_config = dict()
        # or condition, either one of the two conditions is satisfied
        condition_config["or"] = [
        dict(
            contain_1=dict(
                entities=self.entities_to_load["cls_1"],
                container=f"{target_container[0]}_0"
            ),
            contain_2=dict(
                entities=self.entities_to_load["cls_2"],
                container=f"{target_container[1]}_1"
            )
        ),
        dict(
            contain_1=dict(
                entities=self.entities_to_load["cls_1"],
                container=f"{target_container[1]}_1"
            ),
            contain_2=dict(
                entities=self.entities_to_load["cls_2"],
                container=f"{target_container[0]}_0"
            )
        )]        
        
        self.config["task"]["conditions"] = condition_config




class NavigationConfigManager(BenchTaskConfigManager):
    def center2bbox(self,center, half_len=0.25):
        """
        Generate a bbox from a center point (x/y edge length 0.2, z unchanged)
        :param center: center point in the form [x, y, z] (list/tuple/np.array)
        :param half_len: half edge length, default 0.1 (edge length 0.2)
        :return: bbox in the form [xmin, ymin, zmin, xmax, ymax, zmax]
        """
        # print("center:", center)
        x, y, z = center
        xmin = x - half_len
        ymin = y - half_len
        xmax = x + half_len
        ymax = y + half_len
        return [xmin,xmax,ymin,ymax]

    def load_objects(self, target_entity, **kwargs):
        super().load_objects(target_entity, **kwargs)
        self.get_target_bbox()

    def get_target_bbox(self, target_entity=None, distance=0.5, y_distance=0.15, x_distance=0.15):
        # 1. Basic parameter handling
        self.navigation_entity = target_entity
        target_entity = target_entity or self.target_entity
        dest = self.destination_position

        # print(f"current_destination: {dest}")
        if dest is None or not isinstance(target_entity, str):
            return

        # 2. Find the component (use next instead of a full for-loop search)
        component = next((c for c in self.config["task"]["components"] if c["name"] == target_entity), None)

        if not component:
            print(f"Warning: target_entity '{target_entity}' not found in config.")
            return

        # 3. Data preparation
        self.target_object_info = copy.deepcopy(component)
        # print(f"target_object_info: {self.target_object_info}")
        pos = self.target_object_info["position"]

        # 4. Offset mapping table: {direction: [dx, dy]}
        # This keeps the original sign and offset logic intact
        offset_map = {
            "bottom": [x_distance, -distance],
            "top": [-x_distance, distance],
            "left": [-distance, -y_distance],
            "right": [distance, y_distance]
        }

        # 5. Apply the offset (if dest is not in the dict, fall back to the original 'bottom' offset)
        dx, dy = offset_map.get(dest, [0, -distance])
        pos[0] += dx
        pos[1] += dy


        self.center_pos = pos
        # 6. Compute the result and print
        self.target_bbox = self.center2bbox(pos)



    def get_condition_config(self, target_entity, **kwargs):

        conditions_config = dict(
            contain_robot=dict(
                target_bbox=self.target_bbox,
                robot = "pandaomron"
            )
        )
        self.config["task"]["conditions"] = conditions_config

    def get_instruction(self,target_entity,target_container, **kwargs):
        super().get_instruction(target_entity,target_container, **kwargs)
        instruction = [f"Navigate to the {self.cleaned_entity}."]
        self.config["task"]["instructions"] = instruction
        return self.config



class CompositeNavigationConfigManager(NavigationConfigManager):
    """
    Config manager for composite navigation tasks with multiple independent layouts.

    Structure:
    - composite_configs: list of configs, each config is a separate navigation target
    - Each config can have: seen_object, unseen_object, seen_container, unseen_container,
      seen_init_container, unseen_init_container, destination_position, fixture_surface,
      distractor, mid_contain, etc.

    The manager merges configs and processes them sequentially with index-based naming.
    """

    def __init__(self, task_name, num_objects=[2, 1], **kwargs):

        super().__init__(task_name, num_objects, **kwargs)

        # Extract composite_configs from asset
        self.composite_configs = self.config["task"]["asset"].get("composite_configs", [])
        self.work_info = [None]*len(self.composite_configs)
        self.sampled_points = [None]*len(self.composite_configs)
        if not self.composite_configs:
            raise ValueError(f"Composite navigation task {task_name} requires 'composite_configs'")

        # Default layout/container config tables (subclasses override per-layout)
        if not hasattr(self, 'LAYOUT_CONFIG_TABLE'):
            self.LAYOUT_CONFIG_TABLE = []
        if not hasattr(self, 'CONTAINER_CONFIG_TABLE'):
            self.CONTAINER_CONFIG_TABLE = [{}]

    def get_seen_task_config(self):
        """
        Override base class method to directly call get_task_config without selecting single target.
        Composite navigation task configs are loaded from composite_configs.
        """
        return self.get_task_config(**self.kwargs)

    def get_unseen_task_config(self):
        """
        Override base class method to directly call get_task_config without selecting single target.
        Composite navigation task configs are loaded from composite_configs.
        """
        return self.get_task_config(**self.kwargs)

    def _merge_composite_configs(self):
        """
        Merge composite_configs into unified format: [[config1], [config2], ...]
        Called in get_task_config before processing layouts.
        Each composite_configs element can be a complete single-task config,
        including mid_container, sample_strategy, split_ratio.
        """
        self.merged_seen_object = []
        self.merged_seen_container = []
        self.merged_seen_init_container = []
        self.merged_destination_position = []
        self.merged_fixture_surface = []
        self.merged_distractor = []
        self.merged_mid_contain = []
        self.merged_mid_container = []
        self.merged_sample_strategy = []
        self.merged_split_ratio = []

        for idx, cfg in enumerate(self.composite_configs):

            seen_object = cfg.get("seen_object", [])
            distractor = cfg.get("distractor", [])

            # num_objects format: [[distractor_num, target_num], ...] per layout
            if isinstance(self.num_objects, list) and len(self.num_objects) > 0:
                if idx < len(self.num_objects):
                    layout_num_objects = self.num_objects[idx]
                else:
                    layout_num_objects = self.num_objects[-1] if self.num_objects else []
            else:
                layout_num_objects = []

            # Sample distractor: flat list only
            if distractor and len(layout_num_objects) > 0 and layout_num_objects[0] is not None:
                n_distractor = min(layout_num_objects[0], len(distractor))
                if n_distractor < len(distractor):
                    distractor = random.sample(distractor, n_distractor)

            # Sample seen_object:
            # - nested list [[a],[b]]: clustering, no sampling
            # - flat list [a, b]: sample num_objects[idx][1] targets
            if seen_object and len(layout_num_objects) > 1 and layout_num_objects[1] is not None:
                if seen_object and isinstance(seen_object[0], list):
                    # Nested list: clustering task, no sampling
                    pass
                else:
                    # Flat list: sample target objects
                    n_target = min(layout_num_objects[1], len(seen_object))
                    if n_target < len(seen_object):
                        seen_object = random.sample(seen_object, n_target)

            self.merged_seen_object.append(seen_object)
            self.merged_seen_container.append(cfg.get("seen_container", []))
            self.merged_seen_init_container.append(cfg.get("seen_init_container", []))
            self.merged_distractor.append(distractor)
            self.merged_mid_contain.append(cfg.get("mid_contain", None))
            self.merged_mid_container.append(cfg.get("mid_container", None))
            self.merged_sample_strategy.append(cfg.get("sample_strategy", None))
            self.merged_split_ratio.append(cfg.get("split_ratio", None))

            self.merged_destination_position.append(cfg.get("destination_position", None))
            self.merged_fixture_surface.append(cfg.get("fixture_surface", None))


        self.target_container = self.merged_seen_container  # nested list
        self.target_entity = self.merged_seen_object  # nested list


        self.target_object_info=[]


        self.target_bbox=[]
        # Collect mid_container parent names for composite_entities
        mid_parents_all = []
        for mc in self.merged_mid_container:
            if mc:
                for item in mc:
                    if isinstance(item, dict):
                        mid_parents_all.extend(list(item.keys()))
        self.composite_entities = (flatten_list(self.merged_seen_object)+
                                   flatten_list(self.merged_seen_container)+
                                   flatten_list(self.merged_seen_init_container)+
                                   flatten_list(self.merged_distractor)+
                                   mid_parents_all)


    def get_task_config(self, target_entity=None, target_container=None, init_container=None, **kwargs):
        """
        Load composite navigation task configuration.
        Process each layout sequentially with index-based naming.
        """
        # Merge composite configs first
        self._merge_composite_configs()

        # Load robocasa scene once
        self.load_robocasa_scene()

        # Process each layout
        for idx in range(len(self.composite_configs)):
            self._process_single_layout(idx)

        # Generate composite conditions
        self.get_condition_config()

        # Adjust the order of stop points after conditions are generated (default no-op; subclasses override as needed)
        self.reorder_target_object_info()

        # Generate instruction (fixed sentence)
        self.get_instruction(target_entity=None, target_container=None)

        # Camera config
        self.get_camera_config()

        return self.config

    def _process_single_layout(self, idx):
        """Process a single layout by index"""
        # Set current layout parameters
        self.destination_position = self.merged_destination_position[idx]
        self.fixture_surface = self.merged_fixture_surface[idx]

        # Set per-layout mid_container, sample_strategy, split_ratio
        mid_container = self.merged_mid_container[idx]
        self.sample_strategy = self.merged_sample_strategy[idx]
        self.split_ratio = self.merged_split_ratio[idx]

        # Rebuild mid_container_mapping for this layout
        # Merge logic consistent with BenchTaskConfigManager.mid_mapping:
        # parents appearing in the current layout's seen_container go into container_mapping
        # (loaded by load_containers as containers with children attached), avoiding the same
        # entity being loaded twice; only parents not in seen_container go into
        # mid_container_mapping (placed on grid points).
        self.mid_container_mapping = {}
        self.container_mapping = {}
        seen_flat = set(self.merged_seen_container[idx] or [])
        if mid_container:
            for item in mid_container:
                if isinstance(item, dict):
                    for parent, children in item.items():
                        target_map = self.container_mapping if parent in seen_flat else self.mid_container_mapping
                        target_map[parent] = children

        # Get current layout objects
        current_seen = self.merged_seen_object[idx]
        current_distractor = self.merged_distractor[idx]

        # Get object info for current layout
        if self.fixture_surface:
            if idx < len(self.LAYOUT_CONFIG_TABLE):
                self.get_object_info_for_layout(idx)

        if self.merged_seen_container[idx]:
            self.load_containers_for_layout(idx)

        # Load mid contain for current layout (old format, backward compat)
        mid_contain = self.merged_mid_contain[idx]
        if mid_contain:
            self.load_mid_contain_for_layout(mid_contain, idx)

        # Load objects for current layout (handles mid_container subentities if present)
        self.load_objects_for_layout(idx)

        # Auto-generate navigation stop point from workspace if not already set by subclass
        if len(self.target_bbox) <= idx and self.work_info[idx]:
            self._get_layout_stop_point(idx)


    def get_object_info_for_layout(self, idx):
        if idx < 0 or idx >= len(self.LAYOUT_CONFIG_TABLE):
            idx = 0
        config = self.LAYOUT_CONFIG_TABLE[idx]
        return self.get_object_info(idx = idx,**config)

    def get_object_info(self, idx=None, workregion_offset=0, workregion_y_set=0, target_dim=(0.8, 0.4),
                        grid_size=[10, 10]):
        # Safety guard: if idx is not passed, fall back to 0
        if idx is None:
            idx = 0
        if self.fixture_surface:
            with open(os.path.join(PROJECT_ROOT,
                                   "configs/robocasa_scenes_config/robocasa_scene_config.json"), "r") as f:
                configs = json.load(f)
            scene_name = self.robocasa_scene.rsplit("_", 1)[0]
            workspace = configs[scene_name][self.fixture_surface]["workspace"]
            current_work_info = get_work_info(
                workspace,
                target_dim=target_dim,
                anchor=self.destination_position,
                offset_dist=workregion_offset,
                y_set=workregion_y_set
            )
            self.work_info[idx] = current_work_info
            workregion = self.work_info[idx]["workregion"]
            # Compute n_samples with mid_container accounting
            all_entities = flatten_list(self.merged_seen_object[idx]) + flatten_list(self.merged_distractor[idx])
            mid_children_count = sum(len(children) for children in self.mid_container_mapping.values())
            mid_parents_count = len(self.mid_container_mapping)
            # container_mapping children are loaded with their container as subentities and
            # do not occupy grid sample points (consistent with the base class get_object_info)
            container_mid_children_count = sum(len(children) for children in self.container_mapping.values()) if hasattr(self, "container_mapping") else 0
            n_samples = len(all_entities) + mid_parents_count - mid_children_count - container_mid_children_count
            self.sampled_points[idx] = grid_sample(
                workregion,
                grid_size=grid_size,
                n_samples=n_samples,
                mid_container_sample=self.sample_strategy,
                n_mid=mid_parents_count,
                destination_position=self.destination_position,
                split_ratio=self.split_ratio if self.split_ratio is not None else 0.5,
            )

    def load_objects_for_layout(self, idx):
        """Load objects for a specific layout.
        Supports mid_container: parents placed on grid points with children as subentities.
        """
        seen = flatten_list(self.merged_seen_object[idx] or [])
        distractor = flatten_list(self.merged_distractor[idx] or [])
        all_objects = seen + distractor

        if not all_objects:
            return
        if self.work_info[idx]:
            orientation = self.work_info[idx]["object_orientation"]
            z = self.work_info[idx]["z"]
            current_layout_points = self.sampled_points[idx] or []
            points_3d = [[x, y, z] for x, y in current_layout_points]

            # Note: the parent may be routed into container_mapping (when it also
            # appears in seen_container), leaving mid_container_mapping empty.
            # Enter this branch if EITHER mapping is non-empty, so that children
            # routed via container_mapping are also excluded from regular objects.
            if self.mid_container_mapping or self.container_mapping:
                # Mid_container mode: separate regular objects from mid_container children
                mid_children = set()
                for children in self.mid_container_mapping.values():
                    mid_children.update(children)
                # container_mapping children are loaded with their container and likewise
                # do not occupy grid points (consistent with the base class load_objects)
                for children in (self.container_mapping or {}).values():
                    mid_children.update(children)
                regular_objects = [obj for obj in all_objects if obj not in mid_children]
                mid_parents = list(self.mid_container_mapping.keys())

                # Points are ordered: [regular_points..., mid_points...] (from grid_sample)
                point_idx = 0
                # Place regular objects on grid points
                for obj in regular_objects:
                    if point_idx >= len(points_3d):
                        break
                    object_config = self.get_entity_config(
                        obj,
                        position=points_3d[point_idx],
                        orientation=orientation
                    )
                    self.config["task"]["components"].append(object_config)
                    point_idx += 1
                # Place mid_container parents on grid points, with children as subentities
                for parent, children in self.mid_container_mapping.items():
                    if point_idx >= len(points_3d):
                        break
                    parent_config = self.get_entity_config(
                        parent,
                        position=points_3d[point_idx],
                        orientation=orientation
                    )
                    parent_config["subentities"] = []
                    for j, child in enumerate(children):
                        child_config = self.get_entity_config(
                            child,
                            position=[j * 0.1 - 0.05 * (len(children) - 1), 0, 0],
                            orientation=[0, 0, 0]
                        )
                        parent_config["subentities"].append(child_config)
                    self.config["task"]["components"].append(parent_config)
                    point_idx += 1
                self.objects = regular_objects + mid_parents
            else:
                # Original behavior: sequential placement
                self.objects = all_objects
                for i, obj in enumerate(self.objects):
                    # Safety guard: if there are more objects than sampled points, truncate to avoid points_3d[i] going out of bounds
                    if i >= len(points_3d):
                        break
                    object_config = self.get_entity_config(
                        obj,
                        position=points_3d[i],
                        orientation=orientation
                    )
                    self.config["task"]["components"].append(object_config)
        else:
            for i, obj in enumerate(all_objects):
                specific_name = f"{obj}_layout{idx}_{i}"
                base_pos = [-0.2 + idx * 1.0 + i * 0.1, 0.2, 0.8]
                object_config = self.get_entity_config(obj, position=base_pos, specific_name=specific_name)
                self.config["task"]["components"].append(object_config)

    def load_containers_for_layout(self, idx):
        """Load container config automatically based on the layout idx, and route to load_containers"""
        if self.fixture_surface is not None:
            if idx < 0 or idx >= len(self.CONTAINER_CONFIG_TABLE):
                idx = 0
            layout_config = self.CONTAINER_CONFIG_TABLE[idx]

            return self.load_containers(idx=idx, layout_config=layout_config)
        else:
            return self.load_containers(idx=idx)

        # Pass idx through, and unpack parameters with **config

    def load_containers(self, idx=None, layout_config=None):
        if idx is None:
            idx = 0

        # Get the target container list for the current layout from its slot
        target_container = self.merged_seen_container[idx]

        # Ensure the container list is not empty
        if target_container:
            # Extract the per-container parameter list preset for the current layout; default to an empty list if absent
            sub_configs = layout_config.get("configs", []) if layout_config else []

            # Use enumerate to iterate over containers together with their index i
            for i, container in enumerate(target_container):
                # print("---------------container:", i, container)
                # Key change: if the config table has dedicated parameters for the container at this position, use them; otherwise use the default fallback parameters
                if i < len(sub_configs):
                    current_container_param = sub_configs[i]
                else:
                    # If more containers are created than the config table covers, fall back to a set of safe defaults to prevent crashes
                    current_container_param = {"offset": 0.3, "y_set": 0.1, "direction": "left", "z_set": 0}

                # Key check: verify whether the corresponding work_info[idx] slot holds valid data
                if self.work_info[idx]:
                    # Pass the work info belonging to the current layout, and unpack the specific relative coordinate parameters with **
                    container_info = self.get_container_info_from_workregion(
                        self.work_info[idx],
                        anchor=self.destination_position,
                        **current_container_param  # Neatly pass offset, y_set, direction, z_set in one go
                    )
                    container_config = self.get_entity_config(
                        container,
                        position=container_info["position"],
                        orientation=container_info["orientation"]
                    )
                    # If the container is in container_mapping, attach its children as subentities
                    # (consistent with the base class load_containers)
                    for parent, children in self.container_mapping.items():
                        if parent == container:
                            container_config["subentities"] = []
                            for j, child in enumerate(children):
                                child_config = self.get_entity_config(
                                    child,
                                    position=[j * 0.1 - 0.05 * (len(children) - 1), 0, 0],
                                    orientation=[0, 0, 0]
                                )
                                container_config["subentities"].append(child_config)
                    self.config["task"]["components"].append(container_config)
                else:
                    # Generic fallback placement
                    container_config = self.get_entity_config(container)
                    # The fallback branch also attaches container_mapping children
                    for parent, children in self.container_mapping.items():
                        if parent == container:
                            container_config["subentities"] = []
                            for j, child in enumerate(children):
                                child_config = self.get_entity_config(
                                    child,
                                    position=[j * 0.1 - 0.05 * (len(children) - 1), 0, 0],
                                    orientation=[0, 0, 0]
                                )
                                container_config["subentities"].append(child_config)
                    self.config["task"]["components"].append(container_config)




    def load_init_containers_for_layout(self, idx):
        """Load init containers for a specific layout"""
        # all_init = self.merged_seen_init_container[idx] or []
        # for i, container in enumerate(all_init):
        #     specific_name = f"{container}_layout{idx}_init_{i}"
        #     container_config = self.get_entity_config(container, specific_name=specific_name)
        #     self.config["task"]["components"].append(container_config)
        pass

    def load_mid_contain_for_layout(self, mid_contain, idx):
        """Load mid_contain for a specific layout"""
        for container_key, items in mid_contain.items():
            specific_name = f"{container_key}_layout{idx}"
            container_config = self.get_entity_config(container_key, specific_name=specific_name)
            self.config["task"]["components"].append(container_config)

            self.config["task"]["components"][-1]["subentities"] = []
            for item_info in items:
                name = item_info.get("name")
                pos = item_info.get("pos", [0, 0, 0])
                orien = item_info.get("orien", [0, 0, 0])
                if name:
                    object_config = self.get_entity_config(name, position=pos, orientation=orien)
                    self.config["task"]["components"][-1]["subentities"].append(object_config)



    def _get_layout_stop_point(self, idx):
        """Auto-compute navigation stop point for a layout from its workspace.

        Uses work_info[idx]["robot_xy"] — the robot position derived from the
        workspace edge and destination_position by get_work_info().
        Falls back to edge-center computation if robot_xy is unavailable.

        Produces:
        - target_object_info: {"position": [x, y, 0]}
        - target_bbox: [xmin, xmax, ymin, ymax] via center2bbox()

        These formats are consumed by contain_robot_pose conditions
        and skill_lib's moveforward navigation.
        """
        if not self.work_info[idx]:
            return

        work_info = self.work_info[idx]
        dest = self.destination_position
        if dest is None:
            return

        workregion = work_info["workregion"]
        min_x, max_x, min_y, max_y = workregion[:4]

        # Use pre-computed robot_xy from get_work_info (already accounts for
        # workspace edge + destination_position direction + offset)
        if "robot_xy" in work_info:
            stop_x, stop_y = work_info["robot_xy"]
        else:
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            stop_map = {
                "bottom": [center_x, min_y - 0.5],
                "top":    [center_x, max_y + 0.5],
                "left":   [min_x - 0.5, center_y],
                "right":  [max_x + 0.5, center_y],
            }
            stop_x, stop_y = stop_map.get(dest, [center_x, min_y - 0.5])

        stop_pos = [stop_x, stop_y, 0]

        self.target_object_info.append({"position": stop_pos})
        bbox = self.center2bbox(stop_pos)
        self.target_bbox.append(bbox)

        # print(f"[Layout {idx}] Auto stop point: pos={stop_pos}, dest='{dest}'")
        # print(f"  workregion: x[{min_x:.3f}, {max_x:.3f}] y[{min_y:.3f}, {max_y:.3f}]")
        # print(f"  target_bbox: {bbox}")
        # print(f"  target_object_info: {self.target_object_info[-1]}")

    def get_condition_config(self, **kwargs):
        """Generate composite conditions with multiple contain_robot targets"""
        pass

    def get_instruction(self, target_entity, target_container, **kwargs):
        """Fixed instruction for composite navigation"""
        instruction = ["Navigate to the targets."]
        self.config["task"]["instructions"] = instruction
        return self.config

    def get_target_bbox(self, target_entity=None, distance=0.5, y_distance=0.15, x_distance=0.15):
        # 1. Basic parameter handling

        dest = self.destination_position
        if dest is None or not isinstance(target_entity, str):
            return
        # 2. Find the component (use next instead of a full for-loop search)
        component = next((c for c in self.config["task"]["components"] if c["name"] == target_entity), None)
        if not component:
            print(f"Warning: target_entity '{target_entity}' not found in config.")
            return
        # 3. Data preparation
        component_target_object_info = copy.deepcopy(component)
        pos = component_target_object_info["position"]
        # 'bottom' means the robot is below the object; bottom[x, y], x/y_distance are world-coordinate offsets
        offset_map = {
            "bottom": [x_distance, -distance],
            "top": [-x_distance, distance],
            "left": [-distance, -y_distance],
            "right": [distance, y_distance]
        }

        dx, dy = offset_map.get(dest, [0, -distance])
        pos[0] += dx
        pos[1] += dy
        self.target_object_info.append({"position":pos})
        self.target_bbox.append(self.center2bbox(pos))

        # print("self.center_pos:", self.target_object_info)
        # print(f"target_entity_name: {target_entity}")
        # print(f"self.target_object_info[position]: {pos}")
        # print(f"self.target_bbox: {self.target_bbox}")

    def reorder_target_object_info(self):
        """
        Called after get_condition_config to synchronously adjust the order of target_object_info and
        the contents of navigation-type conditions in conditions_config["asyn_sequence"], keeping the
        two consistent. Default does no reordering; concrete tasks override this method as needed.
        """
        pass


