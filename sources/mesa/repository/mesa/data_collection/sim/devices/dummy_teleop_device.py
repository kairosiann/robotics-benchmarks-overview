from collections import OrderedDict


class DummyTeleopDevice:
    """Fallback teleop device that emits no-op controller commands."""

    def __init__(self, num_robots: int):
        if num_robots <= 0:
            raise ValueError("num_robots must be positive")

        if num_robots >= 2:
            controller_names = ["l", "r"]
        else:
            controller_names = ["r"]

        self._controller_name_to_robot_id = OrderedDict(
            (name, idx) for idx, name in enumerate(controller_names)
        )
        self.controller_state = {
            "save_demo": False,
            "delete_demo": False,
        }
        for name in controller_names:
            self.controller_state[name] = {
                "target_pose": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
                "target_pos": [0.0, 0.0, 0.0],
                "target_ori": [1.0, 0.0, 0.0, 0.0],
                "delta_pos": [0.0, 0.0, 0.0],
                "delta_ori": [1.0, 0.0, 0.0, 0.0],
                "gripper_act": [-1],
                "engaged": True,
            }

    def get_controller_state(self):
        return self.controller_state

    def close(self):
        return
