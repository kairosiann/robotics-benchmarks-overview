"""
Register the interactive containers/recaptacles in daily life, such as electrical device
"""
import numpy as np
import os
from RMMBench.utils.register import register
from RMMBench.tasks.components.container import CommonContainer, ContainerWithDoor
from RMMBench.tasks.components.specific_entities.common_containers import FlatContainer

@register.add_entity("CoffeeMachine")
class CoffeeMachine(CommonContainer):
    """
    Coffee manchine that can be interactived by the user, press the button and the coffee fluid will be shown
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_pressed = False
    
    @property
    def fluid_sites(self):
        fluid_sites = []
        sites = self.mjcf_model.worldbody.find_all("site")
        for site in sites:
            if hasattr(site, "name") and ("fluid" in site.name or "liquid" in site.name):
                fluid_sites.append(site)
        return fluid_sites
    
    @property
    def start_button(self):
        return self.mjcf_model.worldbody.find("geom", "start_button")
        
    def get_start_button_pos(self, physics):
        return physics.bind(self.start_button).xpos
    
    def show_fluid(self, physics):
        for fluid_site in self.fluid_sites:
            physics.bind(fluid_site).rgba = np.concatenate([physics.bind(fluid_site).rgba[:3], [1]])
    
    def hidden_fluid(self, physics):
        for fluid_site in self.fluid_sites:
            physics.bind(fluid_site).rgba = np.concatenate([physics.bind(fluid_site).rgba[:3], [0]])   
    
    def is_activate(self, physics):
        contacts = physics.data.contact
        contact_goems = [contact.geom1 for contact in contacts] + [contact.geom2 for contact in contacts]
   
        if physics.bind(self.start_button).element_id in contact_goems:
            self._is_pressed = True
            return True
        else:
            self._is_pressed = False
            return False
    
    def after_substep(self, physics, random_state):
        if self.is_activate(physics): self.show_fluid(physics)
        else: self.hidden_fluid(physics)
    
    def initialize_episode(self, physics, random_state):
        if self.is_activate(physics): self.show_fluid(physics)
        else: self.hidden_fluid(physics)
        return super().initialize_episode(physics, random_state)
    
    def is_pressed(self):
        return self._is_pressed

@register.add_entity("Juicer")
class Juicer(CommonContainer):
    """
    Juicer that can be interactived by the user, press the button and the juicer will be activated
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_pressed = False
    
    @property
    def start_button(self):
        return self.mjcf_model.worldbody.find("geom", "start_button")
    
    def is_activate(self, physics):
        contacts = physics.data.contact
        contact_goems = [contact.geom1 for contact in contacts] + [contact.geom2 for contact in contacts]
   
        if physics.bind(self.start_button).element_id in contact_goems:
            self._is_pressed = True
            return True
        else:
            self._is_pressed = False
            return False
    
    def initialize_episode(self, physics, random_state):
        return super().initialize_episode(physics, random_state)
    
    def is_pressed(self):
        return self._is_pressed

@register.add_entity("Microwave")
class Microwave(ContainerWithDoor):
    def _build(self, 
               name:str="microwave",
               target_force_range=(1, 5),
               **kwargs):
        self._is_activated = False
        self._min_force, self._max_force = target_force_range
        super()._build(name=name, **kwargs) 

    # ── Door open/close detection ───────────────────────────────────────────

    def get_door_joint(self):
        """Return the microwave door's hinge joint (the micro_door_joint on the door body in microwaves/pack_1/model.xml)"""
        return self._mjcf_model.find("joint", "micro_door_joint")

    def get_door_angle(self, physics):
        """Get the door's current opening angle (radians). 0 when closed, max 1.57 rad"""
        joint = self.get_door_joint()
        if joint is None:
            return 0.0
        return physics.bind(joint).qpos[0]

    def is_open(self, physics, threshold=0.2):
        """
        Determine whether the microwave door is open (overrides the base class's fuzzy-matching
        implementation; hardcodes micro_door_joint).
        Joint range: [0, 1.57]; qpos is the opening angle,
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

    @property
    def start_button(self):
        return self.mjcf_model.worldbody.find("geom", "start_button")
        
    def get_start_button_pos(self, physics):
        return physics.bind(self.start_button).xpos
    
    def is_activate(self, physics):
        contacts = physics.data.contact
        contact_goems = [contact.geom1 for contact in contacts] + [contact.geom2 for contact in contacts]
   
        if physics.bind(self.start_button).element_id in contact_goems:
            self._is_pressed = True
            return True
        else:
            self._is_pressed = False
            return False
    
    def is_pressed(self):
        return self._is_pressed

@register.add_entity("Stove")
class Stove(FlatContainer):
    offset = {
        "basic_sleek_induc":[0.32, 0.275, 0.36],
        "coil_burners_induc":[0.315, 0.275, 0.39],
        "dual_gas":[0.475, 0.25, 0.39],
        "frigidaire_gas":[0.32, 0.275, 0.39],
        "simple_gas":[0.3, 0.28, 0.4],
        "square_gas":[0.35, 0.27, 0.4],
        "whirlpool_induc":[0.32, 0.242, 0],
        "wolf_gas":[0.337, 0.247, 0],
        "zline_gas":[0.425, 0.29, 0]
    }
    def _build(self, name="stove", **kwargs):
        # if the stove is initialized from no config file, compute the offset
        if kwargs.get("has_offset", None) is None:
            for key, offset in self.offset.items():
                if key in kwargs.get("xml_path"):
                    kwargs["position"][0] -= offset[0]
                    break
        super()._build(name=name, **kwargs)
    
    # ── Knob & burner configuration (common to all stoves)──────────────────────────────
    IGNITE_THRESHOLD = np.deg2rad(20)   # lights up starting at 20°
    MAX_THRESHOLD = np.deg2rad(90)      # reaches maximum magnification at 90°
    MAX_SIZE_DELTA = np.array([0.05, 0.015, 0.0])  # maximum increment at 90°

    def _get_knob_bodies(self):
        """Return the list of all knob bodies"""
        return [b for b in self._mjcf_model.find_all("body") if b.name and b.name.startswith("knob_")]

    @staticmethod
    def _knob_to_burner_name(knob_body_name):
        """knob_front_right → burner_on_front_right"""
        return "burner_on_" + knob_body_name.replace("knob_", "", 1)

    @staticmethod
    def _knob_to_grasppoint_name(knob_body_name):
        """knob_front_right → grasppoint_knob_front_right"""
        return "grasppoint_" + knob_body_name

    def get_grasped_keypoints(self, physics, body_name=None):
        """
        Return the grasp point under the specified knob according to body_name.

        Args:
            body_name: str, e.g. "knob_front_right"
            physics: dm_control Physics object

        Returns:
            list: [xpos] or []
        """
        if body_name is None or not body_name.startswith("knob_"):
            return []
        
        # Find the specified body
        body = self._mjcf_model.find("body", body_name)
        if body is None:
            return []
        
        # Find the group=4 sites (grasp points) under the body
        grasp_sites = []
        for site in body.find_all("site"):
            if physics.bind(site).group == 4:
                grasp_sites.append(site)
        
        if len(grasp_sites) == 0:
            return []
        
        # Return a list with a single element
        return [physics.bind(grasp_sites[0]).xpos]

    def get_knob_angle(self, physics, knob_body_name):
        """Get the current rotation angle (radians) of the joint under the specified knob body"""
        body = self._mjcf_model.find("body", knob_body_name)
        if body is None:
            return 0.0
        joints = body.find_all("joint")
        if not joints:
            return 0.0
        return physics.bind(joints[0]).qpos[0]

    def is_open(self, physics, joint_name=None, angle_th=45.0) -> bool:
        """
        Determine whether the stove is on: it is considered on when a knob has been turned by
        more than angle_th (degrees) relative to the closed position (qpos=0).

        Args:
            physics: dm_control Physics object
            joint_name: str, knob body name (e.g. "knob_front_right"), optional;
                        when None, returns True if any knob meets the threshold
            angle_th: float, turn-on threshold (degrees)
        """
        knob_bodies = self._get_knob_bodies()
        if joint_name is None:
            return any(np.rad2deg(abs(self.get_knob_angle(physics, b.name))) >= angle_th
                       for b in knob_bodies)
        for b in knob_bodies:
            if b.name == joint_name:
                return np.rad2deg(abs(self.get_knob_angle(physics, b.name))) >= angle_th
        raise ValueError(
            f"Knob body '{joint_name}' not found on stove. "
            f"Available knobs: {[b.name for b in knob_bodies]}.")

    def _update_burner(self, physics, knob_body_name):
        """
        Continuously update the corresponding burner state from a single knob's angle:
          |angle| < 20°   → extinguished (alpha=0, original size)
          20° ≤ |angle| ≤ 90° → alpha=1, size linearly interpolated from the original value to
                               original + MAX_SIZE_DELTA
          |angle| > 90°  → alpha=1, capped at MAX_SIZE_DELTA
        """
        burner_name = self._knob_to_burner_name(knob_body_name)
        burner = self._mjcf_model.find("site", burner_name)
        if burner is None:
            return

        bound = physics.bind(burner)
        rgba = bound.rgba.copy()
        angle = abs(self.get_knob_angle(physics, knob_body_name))

        if angle < self.IGNITE_THRESHOLD:
            bound.rgba = np.concatenate([rgba[:3], [0]])
            bound.size = self._burner_original_sizes[knob_body_name].copy()
        else:
            bound.rgba = np.concatenate([rgba[:3], [1]])
            ratio = min((angle - self.IGNITE_THRESHOLD) / (self.MAX_THRESHOLD - self.IGNITE_THRESHOLD), 1.0)
            bound.size = self._burner_original_sizes[knob_body_name] + self.MAX_SIZE_DELTA * ratio

    # def test_joint(self):
    #     """Test method: set the damping and armature of all knob joints to 0.1"""
    #     for knob_body in self._get_knob_bodies():
    #         for joint in knob_body.find_all("joint"):
    #             print("joint:",joint)
    #             joint.damping = "0.1"
    #             joint.armature = "0.1"

    def after_substep(self, physics, random_state):
        """Each step, iterate over all knobs and continuously update the corresponding burner state"""
        for knob_body in self._get_knob_bodies():
            self._update_burner(physics, knob_body.name)

    def initialize_episode(self, physics, random_state):
        """At initialization, record the original size of every burner and sync the burner states"""
        self._burner_original_sizes = {}
        for knob_body in self._get_knob_bodies():
            burner_name = self._knob_to_burner_name(knob_body.name)
            burner = self._mjcf_model.find("site", burner_name)
            if burner is not None:
                self._burner_original_sizes[knob_body.name] = physics.bind(burner).size.copy()
            else:
                self._burner_original_sizes[knob_body.name] = np.array([0.036, 0.003, 0.005])
            self._update_burner(physics, knob_body.name)
        # self.test_joint()
        # print("0000----------------")

        return super().initialize_episode(physics, random_state)

    def get_site_by_name(self, site_name, physics):
        """
        Look up a site and its world xpos by its full site_name.

        Args:
            site_name: str, the full name of the site (e.g. "grasp_knob_front_right")
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

    def save(self, physics):
        data_to_save = super().save(physics)
        data_to_save["has_offset"] = True
        return data_to_save

@register.add_entity("Sink")
class Sink(CommonContainer):
    """
    Sink that supports controlling the faucet on/off via the handle.
    Different sink models may have different handle operations, configured via SINK_CONFIG_MAP.
    """
    
    # ── Sink configuration map ─────────────────────────────────────────────
    SINK_CONFIG_MAP = {
        "sink_0": {
            "open_direction": "lift",       # opens by lifting vertically
            "grasp_direction": "vertical",  # grasp vertically
        },
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sink_type = self._detect_sink_type(kwargs.get("xml_path", ""))
        self._config = self.SINK_CONFIG_MAP.get(self._sink_type, {
            "open_direction": "lift",
            "grasp_direction": "vertical",
        })
    
    def _detect_sink_type(self, xml_path):
        """Extract the sink model from xml_path, e.g. 'sink_0'"""
        if xml_path is None:
            return "sink_0"
        basename = os.path.basename(os.path.dirname(xml_path))
        if basename in self.SINK_CONFIG_MAP:
            return basename
        for key in self.SINK_CONFIG_MAP.keys():
            if key in xml_path:
                return key
        return "sink_0"
    
    @property
    def config(self):
        return self._config
    
    @property
    def open_direction(self):
        """Direction of turning to open: 'lift' or 'arc_down'"""
        return self._config["open_direction"]
    
    @property
    def grasp_direction(self):
        """Grasp direction of the handle: 'vertical' or 'horizontal'"""
        return self._config["grasp_direction"]
    
    # ── Handle-related methods ────────────────────────────────────────────
    
    def get_handle_body(self):
        return self._mjcf_model.find("body", "handle")
    
    def get_handle_joint(self):
        return self._mjcf_model.find("joint", "handle_joint")
    
    def get_handle_angle(self, physics):
        """Get the handle's current rotation angle (radians)"""
        joint = self.get_handle_joint()
        if joint is None:
            return 0.0
        return physics.bind(joint).qpos[0]
    
    def get_grasped_keypoints(self, physics, body_name=None):
        """
        Return the grasp point under the handle according to body_name.

        Args:
            body_name: str, e.g. "handle"
            physics: dm_control Physics object

        Returns:
            list: [xpos] or []
        """
        if body_name is not None and body_name != "handle":
            return []
        
        # Find the handle body
        body = self._mjcf_model.find("body", "handle")
        if body is None:
            return []
        
        # Find the group=4 sites (grasp points) under the body
        grasp_sites = []
        for site in body.find_all("site"):
            if physics.bind(site).group == 4:
                grasp_sites.append(site)
        
        if len(grasp_sites) == 0:
            return []
        
        # Return a list with a single element
        return [physics.bind(grasp_sites[0]).xpos]
    
    def get_site_by_name(self, site_name, physics):
        """
        Look up a site and its world xpos by site_name.
        """
        site = self._mjcf_model.find("site", site_name)
        if site is not None:
            return site, physics.bind(site).xpos
        
        for body in self._mjcf_model.worldbody.find_all('body'):
            for site in body.find_all('site'):
                if site.name == site_name:
                    return site, physics.bind(site).xpos
        
        return None, None
    
    # ── Water-related methods ─────────────────────────────────────
    
    def get_water_site(self):
        """Return the water site (located under the spout body)"""
        # First look under the spout body
        spout_body = self._mjcf_model.find("body", "spout")
        if spout_body is not None:
            for site in spout_body.find_all("site"):
                if site.name == "water":
                    return site
        # Fallback: global lookup
        return self._mjcf_model.find("site", "water")
    
    def show_water(self, physics):
        """Show the water stream (alpha = 1)"""
        water_site = self.get_water_site()
        if water_site is not None:
            bound = physics.bind(water_site)
            bound.rgba = np.concatenate([bound.rgba[:3], [1]])
    
    def hide_water(self, physics):
        """Hide the water stream (alpha = 0)"""
        water_site = self.get_water_site()
        if water_site is not None:
            bound = physics.bind(water_site)
            bound.rgba = np.concatenate([bound.rgba[:3], [0]])
    
    def is_open(self, physics, threshold=0.05):
        """
        Determine whether the faucet is open.
        handle_joint range: [0, 0.52]; considered open when above the threshold.
        """
        angle = self.get_handle_angle(physics)
        return angle > threshold

    def after_substep(self, physics, random_state):
        """Each step, check the handle state and dynamically update the water stream display"""
        if self.is_open(physics):
            self.show_water(physics)
        else:
            self.hide_water(physics)

    # def touch_is_open(self, physics):
    #     """
    #     Determine whether the faucet has been touched/collided.
    #     Check whether any geom under the handle body is involved in any contact.
    #     Returns True on collision (treated as open), False otherwise.
    #     """
    #     handle_body = self.get_handle_body()
    #     if handle_body is None:
    #         return False
    #
    #     # Collect the element_ids of all geoms under the handle body
    #     handle_geoms = handle_body.find_all("geom")
    #     handle_geom_ids = [physics.bind(geom).element_id for geom in handle_geoms]
    #     if not handle_geom_ids:
    #         return False
    #
    #     # Iterate over all contacts in the current frame and check whether any involve the handle's geoms
    #     contacts = physics.data.contact
    #     for contact in contacts:
    #         if (contact.geom1 in handle_geom_ids or
    #                 contact.geom2 in handle_geom_ids):
    #             return True
    #     return False
    # ── Lifecycle callbacks ───────────────────────────────────────────────
    


    # def after_substep(self, physics, random_state):
    #     """Each step, check the handle state and dynamically update the water stream display"""
    #     if self.touch_is_open(physics):
    #         self.show_water(physics)
    #     else:
    #         self.hide_water(physics)
    
    def initialize_episode(self, physics, random_state):
        """At initialization, sync the water stream state"""
        if self.is_open(physics):
            self.show_water(physics)
        else:
            self.hide_water(physics)
        return super().initialize_episode(physics, random_state)
    
    def save(self, physics):
        data_to_save = super().save(physics)
        data_to_save["sink_type"] = self._sink_type
        return data_to_save