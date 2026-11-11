import threading
import time
from collections import OrderedDict

import numpy as np
import transforms3d as t3d
from oculus_reader import OculusReader
from termcolor import colored

from .base import BaseAgent

DEFAULT_ROBOT_OFFSET = np.array(
    [
        [0, 0, -1],
        [-1, 0, 0],
        [0, 1, 0],
    ]
)


class QuestAgent(BaseAgent):
    def __init__(
        self,
        robot_interface,
        gain: float = 1.0,
        debug=False,
    ):

        self.device = OculusReader()
        self._closed = False

        self.controller_state_lock = threading.Lock()  # lock to ensure safe access

        num_robots = len(getattr(robot_interface, "_robots", []))
        if num_robots >= 2:
            self._controller_name_to_robot_id = OrderedDict(
                {
                    "l": 0,
                    "r": 1,
                }
            )
        else:
            self._controller_name_to_robot_id = OrderedDict(
                {
                    "r": 0,
                    "l": 1,
                }
            )
        controller_names = list(self._controller_name_to_robot_id.keys())
        self._button_names = {
            "l": {
                "trigger_val": "leftTrig",
                "trigger_bool": "LTr",
                "grip_val": "leftGrip",
                "grip_bool": "LG",
            },
            "r": {
                "trigger_val": "rightTrig",
                "trigger_bool": "RTr",
                "grip_val": "rightGrip",
                "grip_bool": "RG",
            },
        }

        self.grip_pressed = dict([(name, False) for name in controller_names])
        self.trigger_pressed = dict([(name, False) for name in controller_names])
        self.initialize_controller_pose = True

        # controller initial poses
        self.controller_init_pos = dict(
            [(name, np.zeros(3)) for name in controller_names]
        )
        self.controller_init_rot = dict(
            [(name, np.array([1, 0, 0, 0])) for name in controller_names]
        )

        # Set controller offset from robot base frame.
        self.controller_offset = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        self.set_constant_controller_offset()

        self._display_controls()

        # Positional gain applied to controller translation deltas
        self.gain = float(gain)

        super().__init__(
            robot_interface=robot_interface,
            controller_names=controller_names,
            debug=debug,
        )

    def get_controller_state(self):
        """
        Returns a dictionary of controller states.

        Example output from OculusReader.get_transformations_and_buttons()
        (
            {
                'l': array([[-0.15662  , -0.0793369,  0.177977 ,  0.012368 ],
                [ 0.0902732, -0.231901 , -0.0239341, -0.0251249],
                [ 0.172688 ,  0.0492721,  0.173929 , -0.0560221],
                [ 0.       ,  0.       ,  0.       ,  1.       ]]),
                'r': array([[ 0.923063 , -0.0438108, -0.382145 ,  0.183798 ],
                [-0.351833 ,  0.305362 , -0.884854 , -0.303325 ],
                [ 0.155459 ,  0.951228 ,  0.266455 , -0.102936 ],
                [ 0.       ,  0.       ,  0.       ,  1.       ]])
            },
            {'A': False, 'B': False, 'RThU': True, 'RJ': False, 'RG': True, 'RTr': False, 'X': False, 'Y': False, 'LThU': True, 'LJ': False, 'LG': False, 'LTr': False, 'leftJS': (0.0, 0.0), 'leftTrig': (0.0,), 'leftGrip': (0.0,), 'rightJS': (0.0, 0.0), 'rightTrig': (0.0,), 'rightGrip': (1.0,)}
        )
        """

        if self._closed:
            return None

        # Poll device outside the lock so we don't block other threads on sleeps
        controller_data = self.device.get_transformations_and_buttons()
        while not controller_data or controller_data[0] == {}:
            # busy wait for the headset to wake up, but yield time
            time.sleep(0.001)
            if self._closed:
                return None
            controller_data = self.device.get_transformations_and_buttons()

        transforms_data, buttons_data = controller_data

        with self.controller_state_lock:
            new_controller_state = {}

            # Parse button data.
            # Primary ('A') button, used to decide whether to save a demo
            if buttons_data["A"]:
                save_demo = True
            else:
                save_demo = False
            # Secondary ('B') button, use to delete the currently recording demo
            if buttons_data["B"]:
                delete_demo = True
            else:
                delete_demo = False
            if save_demo and delete_demo:
                # If both save and delete buttons are pressed, choose to save
                delete_demo = False

            # Check if user wishes to recalibrate headset to robot transform
            if buttons_data["RJ"]:
                while not self.calibrate_controller():
                    continue

            new_controller_state["save_demo"] = save_demo
            new_controller_state["delete_demo"] = delete_demo

            # Parse data per controller.
            for controller in transforms_data:
                new_controller_state[controller] = {}

                controller_state = transforms_data[controller]

                # Trigger
                if buttons_data[self._button_names[controller]["trigger_bool"]]:
                    if not self.trigger_pressed[controller]:
                        # trigger was just pressed, (re)initialize pose
                        self.initialize_controller_pose = True
                    self.trigger_pressed[controller] = True
                else:
                    self.trigger_pressed[controller] = False

                # Grip, used for gripper control
                grip_bool_key = self._button_names[controller]["grip_bool"]
                grip_val_key = self._button_names[controller]["grip_val"]
                grip_bool = bool(buttons_data.get(grip_bool_key, False))
                grip_val_raw = buttons_data.get(grip_val_key, (0.0,))
                if isinstance(grip_val_raw, (tuple, list, np.ndarray)):
                    grip_val = float(grip_val_raw[0]) if len(grip_val_raw) > 0 else 0.0
                else:
                    grip_val = float(grip_val_raw)
                self.grip_pressed[controller] = grip_bool or (grip_val > 0.2)
                gripper_act = [1] if self.grip_pressed[controller] else [-1]

                if self.trigger_pressed[
                    controller
                ]:  # Teleop only works if the trigger is pressed
                    pos_ori_mat = controller_state
                    controller_curr_pos = pos_ori_mat[:3, -1]
                    ori = pos_ori_mat[:3, :3]

                    if self.initialize_controller_pose:
                        # once trigger is (re)pressed, rebase controller's initial pose to current pose, and compute deltas using it
                        self.controller_init_pos[controller] = controller_curr_pos
                        self.controller_init_rot[controller] = (
                            self.controller_offset @ ori
                        )
                        # reset self.ee_init_pos in case robot has moved;
                        # this will be added to dpos to compute absolute pose command for the robot
                        self.set_robot_transform_and_controller_state()
                        if self.verbose:
                            print("initialized pose")
                        self.initialize_controller_pose = False

                    # Computing absolute action for the robot (in the robot's frame).
                    dpos = self.controller_offset @ (
                        controller_curr_pos - self.controller_init_pos[controller]
                    )  # delta command pos
                    target_pos = self.ee_init_pos[controller] + dpos  # abs command pos
                    if self.verbose:
                        print(f"DEBUG get_controller_state(): target_pos: {target_pos}")
                    controller_curr_rot = self.controller_offset @ ori
                    rot_controller_delta = controller_curr_rot @ np.linalg.inv(
                        self.controller_init_rot[controller]
                    )
                    target_ori = t3d.quaternions.mat2quat(
                        rot_controller_delta
                        @ t3d.quaternions.quat2mat(self.ee_init_rot[controller])
                    )  # (w, x, y, z) # abs command ori
                    target_pose = (
                        target_pos.tolist() + target_ori.tolist()
                    )  # abs command pose

                    # Computing delta action for the robot.
                    if self._controller_name_to_robot_id[controller] < len(
                        self.robot_interface.last_eef_pose
                    ):
                        ee_curr_pose = self.robot_interface.last_eef_pose[
                            self._controller_name_to_robot_id[controller]
                        ]
                    else:
                        # If the controller name does not match any robot, use the first robot's pose
                        ee_curr_pose = self.robot_interface.last_eef_pose[0]
                        print(
                            colored(
                                f"WARNING: Controller {controller} does not match any robot, using first robot's pose.",
                                "yellow",
                            )
                        )
                    ee_curr_pos = ee_curr_pose[:3, 3]
                    ee_curr_rot = ee_curr_pose[:3, :3]
                    delta_pos = target_pos - ee_curr_pos  # actual delta action
                    delta_ori = np.dot(
                        t3d.quaternions.quat2mat(target_ori), np.linalg.inv(ee_curr_rot)
                    )  # (w, x, y, z)
                    delta_ori = t3d.quaternions.mat2quat(delta_ori)  # (w, x, y, z)

                    self.engaged = True
                    new_controller_state[controller] = dict(
                        target_pose=target_pose,
                        target_pos=target_pos.tolist(),
                        target_ori=target_ori.tolist(),
                        delta_pos=delta_pos.tolist(),
                        delta_ori=delta_ori.tolist(),
                        gripper_act=gripper_act,
                        engaged=self.engaged,
                    )
                else:
                    self.engaged = False
                    # zero-ing delta actions; creates a minor gap b/w absolute and delta control
                    new_controller_state[controller] = dict(
                        delta_pos=[0, 0, 0],
                        delta_ori=[
                            1,
                            0,
                            0,
                            0,
                        ],  # (w, x, y, z)
                        gripper_act=gripper_act,
                        engaged=self.engaged,
                    )

            self.controller_state = self._nested_dict_update(
                self.controller_state, new_controller_state
            )

            return self.controller_state

    def set_constant_controller_offset(self, inverted=False):
        """Sets the controller rotation offset from the robot base frame."""

        # Headset to robot offset when headset faces same direction as the robot.
        self.controller_offset = np.array(
            [[0, 0, -1], [-1, 0, 0], [0, 1, 0]]  # robot_T_headset
        )
        if inverted:
            # Headset to robot offset when headset is upside down.
            self.controller_offset = np.array(
                [[0, 0, -1], [1, 0, 0], [0, -1, 0]]  # robot_T_invertedHeadset
            )

    def _display_controls(self):
        """
        Method to pretty print controls.
        """

        def print_command(char, info):
            char += " " * (30 - len(char))
            print("{}\t{}".format(char, info))

        print("")
        print_command("Control", "Command")
        print_command("Front Trigger", "Start Teleop")
        print_command("Side Trigger", "Close gripper")
        print_command("A", "Save demo")
        print_command("B", "Delete demo")
        print_command("Press Right Joystick", "Recalibrate headset to robot")
        print("")

    def calibrate_controller(self) -> bool:
        """Calibrate the controller.

        Returns:
            bool: if the calibration was successful.
        """

        print("Press and hold the A button while moving along the x-axis")

        # Wait until the button is pressed for the first time
        ori_tf, buttons = self.device.get_transformations_and_buttons()
        while not buttons.get("A", None):
            ori_tf, buttons = self.device.get_transformations_and_buttons()

        print("Button pressed, hold and move...")

        # Wait until the button is released
        while buttons["A"]:
            end_tf, buttons = self.device.get_transformations_and_buttons()

        print("Button released, calibrating x-axis...")

        ori_tf = ori_tf["r"]
        end_tf = end_tf["r"]
        delta = end_tf[:3, 3] - ori_tf[:3, 3]

        kx = np.argmax(np.abs(delta))
        x_axis = np.zeros(3)
        x_axis[kx] = np.sign(delta[kx])

        print("Press and hold the A button while moving along the y-axis")

        # Wait until the button is pressed for the first time
        ori_tf, buttons = self.device.get_transformations_and_buttons()
        while not buttons.get("A"):
            ori_tf, buttons = self.device.get_transformations_and_buttons()

        print("Button pressed, hold and move...")

        # Wait until the button is released
        while buttons["A"]:
            end_tf, buttons = self.device.get_transformations_and_buttons()

        print("Button released, calibrating y-axis...")

        ori_tf = ori_tf["r"]
        end_tf = end_tf["r"]
        delta = end_tf[:3, 3] - ori_tf[:3, 3]

        ky = np.argmax(np.abs(delta))
        y_axis = np.zeros(3)
        y_axis[ky] = np.sign(delta[ky])

        if kx == ky:
            print("Calibration failed, same axis provided twice")
            return False

        z_axis = np.cross(x_axis, y_axis)
        self.controller_offset = np.array([x_axis, y_axis, z_axis])

        print(f"Headset to Robot:\n{self.controller_offset}")

        return True

    def reset_internal_state(self):
        self.grip_pressed = dict([(name, False) for name in self._controller_names])
        self.trigger_pressed = dict([(name, False) for name in self._controller_names])
        self.initialize_controller_pose = True

        return super().reset_internal_state()

    def close(self):
        """Attempt to cleanly shut down the Oculus reader and release resources."""
        self._closed = True
        try:
            # Try common shutdown methods defensively
            if hasattr(self.device, "close"):
                self.device.close()
            elif hasattr(self.device, "shutdown"):
                self.device.shutdown()
            elif hasattr(self.device, "stop"):
                self.device.stop()
        except Exception:
            pass
        self.device = None


if __name__ == "__main__":
    import robosuite

    from mesa.data_collection.sim.robosuite_teleop import RobosuiteTeleop

    env = robosuite.make("Lift", robots=["Panda"], has_renderer=True)
    teleop_env = RobosuiteTeleop(env=env, control_delta=False)
    quest_controller = QuestAgent(robot_interface=teleop_env, debug=True)
    while True:
        state = quest_controller.get_controller_state()
        print(state)
        time.sleep(0.05)
