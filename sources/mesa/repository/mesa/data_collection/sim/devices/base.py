import numpy as np
import transforms3d as t3d


class BaseAgent:
    def __init__(
        self,
        robot_interface=None,
        controller_names=None,
        debug=False,
    ):
        self.robot_interface = robot_interface
        self.verbose = debug

        self._controller_names = controller_names

        self.ee_init_pos = dict(
            [(name, np.zeros(3)) for name in self._controller_names]
        )
        self.ee_init_rot = dict(
            [(name, np.array([1.0, 0.0, 0.0, 0.0])) for name in self._controller_names]
        )

        self.controller_state = None
        self.engaged = False

        self.set_robot_transform_and_controller_state()

    def get_controller_state(self):
        """
        Computes new_controller_state based on controller input and
        updates self.controller_state.
        """
        raise NotImplementedError

    def _nested_dict_update(self, curr_dict, update_dict):
        for k, v in update_dict.items():
            if (
                k in curr_dict
                and isinstance(v, dict)
                and isinstance(curr_dict[k], dict)
            ):
                curr_dict[k] = self._nested_dict_update(curr_dict[k], v)
            else:
                curr_dict[k] = v
        return curr_dict

    def set_robot_transform_and_controller_state(self):
        """
        Uses current robot pose to initialize self.ee_init_pos, self.ee_init_rot, and
        a no-action self.controller_state.
        """

        for i_robot in range(len(self.robot_interface._robots)):
            # Get robot's current pose.
            current_pose = self.robot_interface.last_eef_pose[i_robot]
            current_pos = current_pose[:3, 3]
            current_rot = current_pose[:3, :3]
            current_quat = t3d.quaternions.mat2quat(current_rot)  # (w, x, y, z)
            if self.verbose:
                print(
                    f"DEBUG: set_robot_transform_and_controller_state() robot {i_robot} current_pos: {current_pos}"
                )

            # Set eef pose to robot's current pose.
            controller_name = self._controller_names[i_robot]
            self.ee_init_pos[controller_name] = np.array(
                [current_pos[0], current_pos[1], current_pos[2]]
            )
            self.ee_init_rot[controller_name] = current_quat

            # if controller_state is None, set controller state to robot's current pose.
            if self.controller_state is None:
                self.controller_state = dict(
                    [(name, None) for name in self._controller_names]
                )
                self.controller_state["save_demo"] = False
                self.controller_state["delete_demo"] = False
            if self.controller_state[controller_name] is None:
                print("Resetting controller states to robot pose.")
                target_pose = current_pos.tolist() + current_quat.tolist()
                self.controller_state[controller_name] = dict(
                    target_pose=target_pose,
                    target_pos=current_pos.tolist(),
                    target_ori=current_quat.tolist(),
                    delta_pos=[0.0, 0.0, 0.0],
                    delta_ori=[1.0, 0.0, 0.0, 0.0],
                    gripper_act=[-1],
                    engaged=False,
                )
                if self.verbose:
                    print(self.controller_state)

    def reset_internal_state(self):
        self.controller_state = None
        self.set_robot_transform_and_controller_state()  # intializes robot pose and controller_state
        self.engaged = False

    def close(self):
        """
        Optional cleanup hook for device-backed agents.
        Subclasses should override to release resources.
        """
        return
