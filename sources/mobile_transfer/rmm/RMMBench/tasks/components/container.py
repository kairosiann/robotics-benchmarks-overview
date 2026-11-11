import os

import numpy as np
from sympy.physics.units import velocity

from RMMBench.tasks.components.entity import Entity
from RMMBench.utils.register import register
from RMMBench.utils.utils import rotate_point_around_axis, slide_point_along_axis, distance

class ContainerMiXin:
    """
    Abstract mixin class for Container/Receptacle 
    """


    def get_place_points(self, physics):
        """
        Get the place points of the container
        """
        raise NotImplementedError
    
    def caculate_keypoints(self, **kwargs):
        """
        Caculate the keypoints of the container
        """
        raise NotImplementedError
    
    def contain(self, point, physics):
        """
        Judge whether the target point is in the container
        """
        raise NotImplementedError
    
    def generate_point_in_container(self, physics, margin):
        """
        Generate a random point in the container
        """
        raise NotImplementedError

    def stationary(self, vel,physics):
        """
        Judge whether the target entity is stationary
        """
        # self.velocity_threshold = 1e-4

        linear_vel = vel[3:]
        angular_vel = vel[:3]

        linear_speed = np.linalg.norm(linear_vel)
        angular_speed = np.linalg.norm(angular_vel)

        if (linear_speed > self.velocity_threshold or
                angular_speed > self.velocity_threshold):
            return False
        return True
    
@register.add_entity("CommonContainer")
class CommonContainer(Entity, ContainerMiXin):
    """
    Common 3d container/receptacle, which can be used to contain objects.
    Usually can be abstractly modeled as boxes.
    Such as boxes, drawers and etc.
    """
    def _build(self,
               velocity_threshold = 1.5,
               z_angle_threshold = 25,
                **kwargs):

        super()._build(**kwargs)
        self.velocity_threshold = velocity_threshold
        self.z_angle_threshold = z_angle_threshold

    def get_place_point(self, physics):
        placement_sites = self.place_sites(physics)
        # print(f"placement_sites:{placement_sites}")
        place_points = [np.array(physics.bind(site).xpos) for site in placement_sites]
        # print(f"place_points:{place_points}")

        return place_points

    def contain(self, point, physics):
        keysites = self.key_sites(physics)
        self.keypoints = np.array([physics.bind(kp).xpos for kp in keysites])

        # print("?????")
        minX, maxX, minY, maxY, minZ, maxZ = self.keypoints[:, 0].min(), self.keypoints[:, 0].max(), self.keypoints[:, 1].min(), self.keypoints[:, 1].max(), self.keypoints[:, 2].min(), self.keypoints[:, 2].max()

        if minX <= point[0] <= maxX and \
           minY <= point[1] <= maxY and \
            minZ <=point[2] <= maxZ:
               return True
        return False

    def tube_contain(self, point, physics):
        keysites = self.insert_tube_stand_key_sites(physics)
        self.keypoints = np.array([physics.bind(kp).xpos for kp in keysites])
        # print("--------")
        # print("self.keypoints",self.keypoints)
        # print("points:",point)
        minX, maxX, minY, maxY, minZ, maxZ = self.keypoints[:, 0].min(), self.keypoints[:, 0].max(), self.keypoints[:, 1].min(), self.keypoints[:, 1].max(), self.keypoints[:, 2].min(), self.keypoints[:, 2].max()

        if minX <= point[0] <= maxX and \
           minY <= point[1] <= maxY and \
            minZ <=point[2] <= maxZ:
               return True
        return False

    def stationary(self, vel,physics,th=None):
        """
        Judge whether the target entity is stationary
        """
        # self.velocity_threshold = 1e-4
        if not th:
            th = self.velocity_threshold


        linear_vel = vel[3:]
        angular_vel = vel[:3]

        linear_speed = np.linalg.norm(linear_vel)
        angular_speed = np.linalg.norm(angular_vel)
        # print(f"linear_speed{linear_speed},angular_speed{angular_speed}")
        if (linear_speed > th or
                angular_speed > th):
            return False
        return True

    def standing(self ,physics,quat, **kwargs):
        """
        Judge whether the target entity is standing
        quat: [w, x, y, z] quaternion
        """
        # Extract the quaternion components
        w, x, y, z = quat
        # Compute the direction of the object's Z axis in the world frame
        # Z axis of the rotation matrix computed from the quaternion
        zx = 2 * (x * z + w * y)
        zy = 2 * (y * z - w * x)
        zz = 1 - 2 * (x * x + y * y)

        # Compute the angle to the vertical direction (0,0,1)
        dot_product = zz  # the vertical direction is (0,0,1): 0*zx + 0*zy + 1*zz = zz = cosθ
        angle = np.degrees(np.arccos(np.clip(dot_product, -1, 1)))
        print("angle",angle)
        # Return whether it is within the tolerance
        if angle <= self.z_angle_threshold:
            return True
        return False




@register.add_entity("FlatContainer")
class FlatContainer(Entity, ContainerMiXin):
    """
    Flat container/receptacle, which can be used to contain objects.
    Usually can be abstractly modeled as a plane.
    Such as plates, palce mats and etc.
    """

    def _build(self, 
               z_threshold=0.1,
               velocity_threshold=1.5,
               z_angle_threshold=25,
               **kwargs):
        """
        Parameter:
            -z_threshold: the threshold of the height to confirm a point is in the container
        """
        super()._build(**kwargs)
        self.z_threshold = z_threshold
        self.velocity_threshold = velocity_threshold
        self.z_angle_threshold = z_angle_threshold
    
    def get_radius(self, physics):
        """
        If the container is as a circle shape, return the radius of the container
        """
        radius_site = self.mjcf_model.worldbody.find("site", "horizontal_radius_site")
        if radius_site:
            center_pos = self.get_xpos(physics)
            radius = distance(physics.bind(radius_site).xpos[:2], center_pos[:2])
            return radius
        return None
    
    def contain(self, point, physics,z_th=None):
        """
        Judge whether the target point is in the plant area
        """
        if not z_th:
            z_th = self.z_threshold

        radius = self.get_radius(physics)
        if radius:
            center_pos = self.get_xpos(physics)
            if distance(point[:2], center_pos[:2]) < radius and \
                (point[-1] - center_pos[-1]) > 0 and (point[-1] - center_pos[-1]) < z_th:
                return True
        else:
            self.keypoints = np.array([physics.bind(kp).xpos for kp in self.key_sites(physics)])
            minX, maxX, minY, maxY = self.keypoints[:, 0].min(), self.keypoints[:, 0].max(), self.keypoints[:, 1].min(), self.keypoints[:, 1].max()
            platform_z = self.keypoints[:, -1].min()
            # print(f"X:({minX},{maxX})")
            # print(f"Y:({minY},{maxY})")
            # print(f"Z:({platform_z},{platform_z + z_th})")
            # print("point:",point)
            # print("????")

            if minX <= point[0] <= maxX and \
            minY <= point[1] <= maxY and \
            point[2] > platform_z and point[2] < platform_z + z_th:
                return True
            return False

    def stationary(self, vel,physics,th=None):
        """
        Judge whether the target entity is stationary
        """
        # self.velocity_threshold = 1e-4

        if not th:
            th = self.velocity_threshold

        linear_vel = vel[3:]
        angular_vel = vel[:3]

        linear_speed = np.linalg.norm(linear_vel)
        angular_speed = np.linalg.norm(angular_vel)
        # print(f"linear_speed{linear_speed},angular_speed{angular_speed}")
        if (linear_speed > th or
                angular_speed > th):
            return False
        return True

    def standing(self ,physics,quat, **kwargs):
        """
        Judge whether the target entity is standing
        quat: [w, x, y, z] quaternion
        """
        # Extract the quaternion components
        w, x, y, z = quat
        # Compute the direction of the object's Z axis in the world frame
        # Z axis of the rotation matrix computed from the quaternion
        zx = 2 * (x * z + w * y)
        zy = 2 * (y * z - w * x)
        zz = 1 - 2 * (x * x + y * y)

        # Compute the angle to the vertical direction (0,0,1)
        dot_product = zz  # the vertical direction is (0,0,1): 0*zx + 0*zy + 1*zz = zz = cosθ
        angle = np.degrees(np.arccos(np.clip(dot_product, -1, 1)))
        print("angle",angle)
        # Return whether it is within the tolerance
        if angle <= self.z_angle_threshold:
            return True
        return False



    def generate_point_in_container(self, physics, margin=[0.1, 0.1, 0.1]):
        pos = physics.bind(self.mjcf_model.worldbody).xpos
        minX, maxX, minY, maxY = self.keypoints[:, 0].min(), self.keypoints[:, 0].max(), self.keypoints[:, 1].min(), self.keypoints[:, 1].max()
        x = np.random.uniform(minX+margin[0], maxX-margin[0])
        y = np.random.uniform(minY+margin[1], maxY-margin[1])
        z = pos[-1] + margin[2]
        return np.array([x, y, z])
    
    def get_place_point(self, physics):
        placement_sites = self.place_sites(physics)
        place_points = [np.array(physics.bind(site).xpos) for site in placement_sites]
        if len(place_points) == 0:  
            place_points.append(self.get_xpos(physics) + np.array([0, 0, self.z_threshold]))
        return place_points

    def grasp_sites(self, physics):
        """
        Special type of sites, group = 4.
        Annotating the recommonded grasp points of the entity.
        E.g. the grasp point of an apple is the center point
        """
        grasp_sites = []
        for site in self.sites:
            # print("site:",site)
            if site.name == "grasp_site":
                grasp_sites.append(site)
            # print("grasp_sites:",grasp_sites)
        return grasp_sites

    def get_grasped_keypoints(self, physics,body_name=None):
        """
        Return a valid grasp position and quaternion.
        If there are no annotated grasp sites, the center point of the entity is returned.
        """

        grasp_keypoints = []
        if len(self.grasp_sites(physics)) > 0:
            grasp_keypoints.extend([physics.bind(site).xpos for site in self.grasp_sites(physics)])
        else:
            grasp_keypoints.append(self.get_xpos(physics))
        # print("grasp_keypoints:",grasp_keypoints)
        print("grasp_keypoints:", grasp_keypoints)
        return grasp_keypoints

    def is_grasped(self, physics, robot):
        """
        Judge whether the entity is grasped by the robot with the contact force
        """
        gripper_geoms = robot.gripper_geoms
        gripper_geom_ids = [physics.bind(geom).element_id for geom in gripper_geoms]
        entity_geom_ids = [physics.bind(geom).element_id for geom in self.geoms]
        contacts = physics.data.contact
        for contact in contacts:
            if (contact.geom1 in gripper_geom_ids and contact.geom2 in entity_geom_ids) or \
                (contact.geom2 in gripper_geom_ids and contact.geom1 in entity_geom_ids):
                return True
        return False

@register.add_entity("ContainerWithDoor")
class ContainerWithDoor(CommonContainer):
    """
    Container/Receptacle with door connected hinge joint.
    Default state is closed.
    Such as fridge, safe and etc. 
    """
    def __init__(self, 
                 open_threshold=np.pi/3,
                 close_threshold=np.pi/10,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.open_threshold = open_threshold
        self.closed_threshold = close_threshold
    
    @property
    def door_joint(self):
        for joint in self.joints:
            if "door" in joint.name:
                return joint
            
    def is_open(self, physics):
        joint_pos = physics.bind(self.door_joint).qpos
        if abs(joint_pos) > self.open_threshold: return True
        else: return False
    
    def is_closed(self, physics):
        """
        Note that the open & close state can not be transfered directly. 
        There exists a intermediate state.
        """
        joint_pos = physics.bind(self.door_joint).qpos
        if abs(joint_pos) < self.closed_threshold: return True
        else: return False
    
    def get_handle_pos(self, physics):
        grasp_sites = self.grasp_sites(physics)
        if len(grasp_sites) > 0: return physics.bind(np.random.choice(grasp_sites)).xpos
        else: raise ValueError("No handle site found")
        
    def get_open_trajectory(self, physics):
        trajectory = []
        init_pos = self.get_handle_pos(physics)
        rotation_axis = physics.bind(self.door_joint).xaxis
        rotaion_anchor = physics.bind(self.door_joint).xanchor
        current_joint_qpos = physics.bind(self.door_joint).qpos
        target_joint_qpos = physics.bind(self.door_joint).range[-1]
        delta_angles = np.arange(0.1, target_joint_qpos-current_joint_qpos[0], 0.1)
        for delta_angle in delta_angles:
            new_pos = rotate_point_around_axis(init_pos, rotaion_anchor, rotation_axis, delta_angle)
            trajectory.append(new_pos)
        return trajectory
    
    def get_close_trajectory(self, physics):
        trajectory = []
        init_pos = self.get_handle_pos(physics)
        rotation_axis = physics.bind(self.door_joint).xaxis
        rotaion_anchor = physics.bind(self.door_joint).xanchor
        current_joint_qpos = physics.bind(self.door_joint).qpos
        target_joint_qpos = physics.bind(self.door_joint).range[0]
        delta_angles = np.arange(-0.1, target_joint_qpos-current_joint_qpos[0], -0.1)
        for delta_angle in delta_angles:
            new_pos = rotate_point_around_axis(init_pos, rotaion_anchor, rotation_axis, delta_angle)
            trajectory.append(new_pos)
        return trajectory
    
    def get_grasped_keypoints(self, physics):
        grasp_sites = self.grasp_sites(physics)
        grasp_keypoints = []
        grasp_keypoints.extend([physics.bind(site).xpos for site in grasp_sites])
        return grasp_keypoints
    
    def is_grasped(self, physics, robot):
        # FIXME
        return True
    
@register.add_entity("ContainerWithDrawer")
class ContainerWithDrawer(CommonContainer):
    """
    Container/Receptacle with drawer connected slide joint.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drawers = []
        for body in self.bodies:
            if "drawer" in body.name:
                self.drawers.append(body)
        self.n_drawer = len(self.drawers)    
    
    def get_drawer_open_level(self, physics):
        open_levels = []
        for joint in self.joints:
            qpos = physics.bind(joint).qpos
            range = physics.bind(joint).range
            open_level = (qpos - range[0])/(range[1] - range[0])
            open_levels.append(open_level)
        return open_levels
    
    def get_drawer_handle_pos(self, physics, drawer_id):
        drawer = self.drawers[drawer_id]
        sites = drawer.find_all("site")
        for site in sites:
            if physics.bind(site).group == 4:
                return physics.bind(site).xpos
        raise ValueError("No handle site found")
    
    def get_drawer_open_trajectory(self, physics, drawer_id):
        handle_init_pos = self.get_drawer_handle_pos(physics, drawer_id)
        init_joint_qpos = physics.bind(self.joints[drawer_id]).qpos
        range = physics.bind(self.joints[drawer_id]).range
        axis = physics.bind(self.joints[drawer_id]).xaxis
        max_distance = range[1] if abs(range[1]) > abs(range[0]) else range[0]
        trajectory = []
        step = -0.05 if max_distance < init_joint_qpos else 0.05
        for distance in np.arange(0.05, max_distance - init_joint_qpos, step):
            new_pos = slide_point_along_axis(handle_init_pos, axis, distance)
            trajectory.append(new_pos)
        return trajectory
    
    def get_grasped_keypoints(self, physics,body_name=None):
        """
        This is a special function in container classes.
        """
        grasp_sites = self.grasp_sites(physics)
        grasp_keypoints = []
        grasp_keypoints.extend([physics.bind(site).xpos for site in grasp_sites])
        return grasp_keypoints
