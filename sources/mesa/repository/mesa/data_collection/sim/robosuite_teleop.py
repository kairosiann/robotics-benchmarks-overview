from copy import deepcopy

import numpy as np
import robosuite
import transforms3d as t3d


class RobosuiteTeleop:
    def __init__(
        self,
        env_name: str,
        env_kwargs: dict,
        control_delta: bool = False,
    ):
        self.env = robosuite.make(env_name, **env_kwargs)
        self.control_delta = bool(control_delta)
        self._env_name = env_name
        self._env_kwargs = deepcopy(env_kwargs)
        self._robots = self.env.robots

    def serialize(self):
        env_kwargs = deepcopy(self._env_kwargs)

        # set input_type="delta" for all robots since "actions" are delta actions
        controller_configs = env_kwargs.get("controller_configs")
        if controller_configs is not None:
            if isinstance(controller_configs, (list, tuple)):
                for i in range(len(controller_configs)):
                    controller_configs[i]["body_parts"]["right"]["input_type"] = "delta"
            else:
                controller_configs["body_parts"]["right"]["input_type"] = "delta"

        # set has_renderer to False
        env_kwargs["has_renderer"] = False

        return dict(
            env_name=self._env_name,
            env_kwargs=env_kwargs,
        )

    def get_state(self):
        """
        Get current environment simulator state
        """
        state = np.array(self.env.sim.get_state().flatten())
        xml = self.env.sim.model.get_xml()
        return state, xml

    def _get_robosuite_arm_pose(self, robot):
        # get pos and ori of "grip_site"
        grip_site_id = robot.eef_site_id["right"]
        ee_pos = np.array(robot.sim.data.site_xpos[grip_site_id])
        ee_ori_mat = np.array(robot.sim.data.site_xmat[grip_site_id].reshape([3, 3]))
        pos_ori_mat = np.eye(4)
        pos_ori_mat[:3, :3] = ee_ori_mat
        pos_ori_mat[:3, -1] = ee_pos
        return pos_ori_mat

    def get_observation(self, di=None):
        # NOTE returning images as-is, not flipping
        if di is None:
            di = self.env._get_observations()
        ret = deepcopy(di)

        return ret

    @property
    def last_eef_pose(self):
        """
        Returns list of pos_ori_mat's containing eef pose of each robot.
        """
        eef_poses = []
        for robot in self._robots:
            pos_ori_mat = self._get_robosuite_arm_pose(robot)
            eef_poses.append(pos_ori_mat)
        return eef_poses

    def init_noops(self, noops):
        """
        Initialize the environment with noops.
        """
        noop_parts = []
        for i_robot in range(len(self._robots)):
            if self.control_delta:
                noop_parts.append(np.zeros(7))
            else:
                pos_mat = self.last_eef_pose[i_robot]
                action_abs_pos = pos_mat[:3, -1]
                action_rot_mat = pos_mat[:3, :3]
                action_rot_quat = t3d.quaternions.mat2quat(action_rot_mat)
                axis, theta = t3d.quaternions.quat2axangle(action_rot_quat)
                action_abs_ori = theta * axis
                noop_parts.append(np.concatenate([action_abs_pos, action_abs_ori, [-1]]))
        noop_action = np.concatenate(noop_parts)

        for _ in range(noops):
            self.env.step(noop_action)

    def step(self, controller_states):
        """
        controller_states: list of dicts, one for each robot
        """
        action = []
        action_abs = []
        for i_robot in range(len(self._robots)):
            #  Computing absolute action
            action_abs_pos = controller_states[i_robot]["target_pose"][:3]
            _vec, _theta = t3d.quaternions.quat2axangle(
                controller_states[i_robot]["target_pose"][3:]
            )
            action_axangle = _theta * _vec
            action_abs += (
                action_abs_pos
                + list(action_axangle)
                + controller_states[i_robot]["gripper_act"]
            )

            # Computing delta action
            action_pos = list(controller_states[i_robot]["delta_pos"])
            _vec, _theta = t3d.quaternions.quat2axangle(
                controller_states[i_robot]["delta_ori"]
            )
            action_axangle = _theta * _vec
            action += (
                action_pos
                + list(action_axangle)
                + controller_states[i_robot]["gripper_act"]
            )

        if self.control_delta:
            self.env.step(action)
        else:
            self.env.step(action_abs)

        return action, action_abs

    def reset(self):
        di = self.env.reset()
        return self.get_observation(di)

    def render(self, mode="human", height=None, width=None, camera_name=None):
        if mode == "human":
            # toggle gripper visualization
            for robot in self._robots:
                robot._visualize_grippers(True)

            if camera_name is not None:
                cam_id = self.env.sim.model.camera_name2id(camera_name)
                self.env.viewer.set_camera(cam_id)  # set OpenCVRenderer camera
            # NOTE by default this uses self.env.render_camera to render the scene,
            # which is not the same as the camera used for saving demos
            self.env.render()

            # toggle gripper visualization
            for robot in self._robots:
                robot._visualize_grippers(False)

        elif mode == "rgb_array":
            flip_img = 1
            if robosuite.macros.IMAGE_CONVENTION == "opengl":
                flip_img = -1  # flip image to convert to opencv convention

            if camera_name is None:
                camera_name = self.env.camera_names[0]
            return self.env.sim.render(
                height=height, width=width, camera_name=camera_name
            )[::flip_img]
        else:
            raise NotImplementedError(f"mode={mode} is not implemented")

    def done(self):
        return self.env._check_success()
