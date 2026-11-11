import threading
import time

import hid
import numpy as np
import transforms3d as t3d

from mesa.sim.macros import SPACEMOUSE_PRODUCT_ID

from .base import BaseAgent


class SpaceMouseAgent(BaseAgent):
    def __init__(
        self,
        robot_interface,
        debug=False,
    ):

        controller_names = ["r"]
        self._controller_name_to_robot_id = {"r": 0}
        # NOTE only one device/robot is supported for now

        self.vendor_id = 9583
        self.product_id = SPACEMOUSE_PRODUCT_ID

        self.devices = dict()
        self._running = True
        for controller_name in controller_names:
            self.devices[controller_name] = hid.device()
            self.devices[controller_name].open(self.vendor_id, self.product_id)

        self.grip_pressed = False

        self.pos_sensitivity = 1.0
        self.rot_sensitivity = 0.1

        self._display_controls()

        super().__init__(
            robot_interface=robot_interface,
            controller_names=controller_names,
            debug=debug,
        )

        # thread to continuously read from device
        self._read_thread = threading.Thread(
            target=self._read_device,
            name="SpaceMouseAgent",
            daemon=True,
        )
        self._read_thread.start()

    def close(self):
        # Stop reader thread and close devices
        self._running = False
        try:
            if self._read_thread.is_alive():
                self._read_thread.join(timeout=1.0)
        except Exception:
            pass
        for dev in self.devices.values():
            try:
                dev.close()
            except Exception:
                pass
        self.devices.clear()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _convert_buffer(self, b1, b2, axis_scale=350.0, min_v=-1.0, max_v=1.0):
        """
        Converts raw spacemouse readings to commands.

        Args:
            b1: 8-bit byte
            b2: 8-bit byte
            axis_scale: (inverted) scaling factor for mapping raw input value
            min_v: lower limit after scaling
            max_v: upper limit after scaling
        Returns:
            Scaled value from spacemouse message
        """
        # convert to signed 16-bit int
        x = (b1) | (b2 << 8)
        if x >= 32768:
            x = -(65536 - x)

        # scale and limit
        x = x / axis_scale
        return min(max(x, min_v), max_v)

    def _read_device(self):
        while self._running:
            new_controller_state = {}
            controller_name = self._controller_names[0]

            try:
                data = self.devices[controller_name].read(13)
            except Exception:
                # Device likely closed; exit loop
                break
            if data is not None:
                dpos = np.zeros(3)  # (x, y, z)
                dori = np.array([1.0, 0.0, 0.0, 0.0])
                left_button_pressed = False
                right_button_pressed = False

                if self.verbose:
                    print("data:", data)

                # reading from joystick
                if self.product_id == 50741:
                    # logic for older model
                    if data[0] == 1:
                        dpos[1] = self.pos_sensitivity * self._convert_buffer(
                            data[1], data[2]
                        )
                        dpos[0] = self.pos_sensitivity * self._convert_buffer(
                            data[3], data[4]
                        )
                        dpos[2] = (
                            self.pos_sensitivity
                            * self._convert_buffer(data[5], data[6])
                            * -1.0
                        )
                    elif data[0] == 2:
                        dori[1] = self.rot_sensitivity * self._convert_buffer(
                            data[1], data[2]
                        )
                        dori[0] = self.rot_sensitivity * self._convert_buffer(
                            data[3], data[4]
                        )
                        dori[2] = (
                            self.rot_sensitivity
                            * self._convert_buffer(data[5], data[6])
                            * -1.0
                        )
                        dori = t3d.euler.euler2quat(
                            dori[0], dori[1], dori[2], axes="rxyz"
                        )  # (w, x, y, z)
                else:
                    # default logic for other models
                    if data[0] == 1:
                        dpos[1] = self.pos_sensitivity * self._convert_buffer(
                            data[1], data[2]
                        )
                        dpos[0] = self.pos_sensitivity * self._convert_buffer(
                            data[3], data[4]
                        )
                        dpos[2] = (
                            self.pos_sensitivity
                            * self._convert_buffer(data[5], data[6])
                            * -1.0
                        )

                        dori[1] = self.rot_sensitivity * self._convert_buffer(
                            data[7], data[8]
                        )
                        dori[0] = self.rot_sensitivity * self._convert_buffer(
                            data[9], data[10]
                        )
                        dori[2] = (
                            self.rot_sensitivity
                            * self._convert_buffer(data[11], data[12])
                            * -1.0
                        )
                        dori = t3d.euler.euler2quat(
                            dori[0], dori[1], dori[2], axes="rxyz"
                        )  # (w, x, y, z)

                # reading from side buttons
                if data[0] == 3:
                    # press left button
                    if data[1] == 1:
                        left_button_pressed = True
                    # press right button
                    if data[1] == 2:
                        right_button_pressed = True
                    # press both buttons
                    if data[1] == 3:
                        left_button_pressed = True
                        right_button_pressed = True

                if self.engaged and right_button_pressed:
                    new_controller_state["delete_demo"] = True

                if self.engaged and left_button_pressed:
                    self.grip_pressed = not self.grip_pressed

                if not self.engaged and right_button_pressed:
                    self.engaged = True

                if self.grip_pressed:
                    gripper_act = [1]
                else:
                    gripper_act = [-1]

                # Computing absolute pose
                target_pos = self.ee_init_pos[controller_name] + dpos
                dori_mat = t3d.quaternions.quat2mat(dori)
                target_ori = t3d.quaternions.mat2quat(
                    dori_mat
                    @ t3d.quaternions.quat2mat(self.ee_init_rot[controller_name])
                )  # (w, x, y, z)
                target_pose = target_pos.tolist() + target_ori.tolist()
                if self.verbose:
                    print("target_pose:", target_pose)

                new_controller_state[controller_name] = dict(
                    target_pose=target_pose,
                    target_pos=target_pos.tolist(),
                    target_ori=target_ori.tolist(),
                    delta_pos=dpos.tolist(),
                    delta_ori=dori.tolist(),  # (w, x, y, z)
                    gripper_act=gripper_act,
                    engaged=self.engaged,
                )

            else:
                new_controller_state[controller_name] = dict(
                    delta_pos=[0.0, 0.0, 0.0],
                    delta_ori=[1.0, 0.0, 0.0, 0.0],  # (w, x, y, z)
                )

            self.controller_state = self._nested_dict_update(
                self.controller_state, new_controller_state
            )

    def get_controller_state(self):
        return self.controller_state

    def reset_internal_state(self):
        self.grip_pressed = False
        return super().reset_internal_state()

    def _display_controls(self):
        """
        Method to pretty print controls.
        """

        def print_command(char, info):
            char += " " * (30 - len(char))
            print("{}\t{}".format(char, info))

        print("")
        print_command("Control", "Command")
        print_command("Right Button", "Start Teleop / Delete demo")
        print_command("Left Button", "Toggle gripper")
        print_command("Joystick", "Move robot")
        print("")


if __name__ == "__main__":
    import robosuite

    from mesa.data_collection.sim.robosuite_teleop import RobosuiteTeleop

    env = robosuite.make("Lift", robots=["Panda"], has_renderer=True)
    teleop_env = RobosuiteTeleop(env=env, control_delta=False)
    sm_controller = SpaceMouseAgent(robot_interface=teleop_env, debug=True)
    while True:
        state = sm_controller.get_controller_state()
        print(state)
        time.sleep(0.05)
