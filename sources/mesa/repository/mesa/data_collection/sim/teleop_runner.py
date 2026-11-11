from dataclasses import dataclass
from typing import Any

import numpy as np

import mesa
import mesa.sim.envs.bddl_utils as BDDLUtils
from mesa.data_collection.sim.devices.base import BaseAgent
from mesa.data_collection.sim.devices.dummy_teleop_device import DummyTeleopDevice
from mesa.data_collection.sim.robosuite_teleop import RobosuiteTeleop
from mesa.sim.envs import TASK_MAPPING


@dataclass
class TeleopStepResult:
    stepped: bool
    controller_state: dict[str, Any] | None = None
    action: Any | None = None
    action_abs: Any | None = None


def make_teleop_env_kwargs(
    render_camera: str,
    horizon: int,
    control_freq: int,
    camera_size: int,
) -> dict[str, Any]:
    return dict(
        render_camera=render_camera,
        horizon=horizon,
        control_freq=control_freq,
        camera_heights=camera_size,
        camera_widths=camera_size,
    )


class TeleopRunner:
    def __init__(
        self,
        problem_file_path: str,
        robots: list[str],
        device: str,
        control_delta: bool,
        gain: float,
        render_camera: str,
        horizon: int,
        camera_size: int,
        control_freq: int,
    ):
        self.problem_file_path = problem_file_path
        self.robots = robots
        self.device = device
        self.control_delta = control_delta
        self.gain = gain
        self.render_camera = render_camera
        self.horizon = horizon
        self.camera_size = camera_size
        self.control_freq = control_freq

        self.teleop_env: RobosuiteTeleop | None = None
        self.teleop_agent: BaseAgent | Any | None = None
        self.env: Any | None = None
        self.active_device: str | None = None
        self.using_real_teleop = False
        self._zero_action: np.ndarray | None = None

    @property
    def kwargs_update_dict(self) -> dict[str, Any]:
        return make_teleop_env_kwargs(
            render_camera=self.render_camera,
            horizon=self.horizon,
            control_freq=self.control_freq,
            camera_size=self.camera_size,
        )

    def create(self, reset: bool = False) -> None:
        teleop_env = None
        teleop_agent = None
        active_device = None
        parsed_problem = None

        if self.device in ("quest", "spacemouse"):
            parsed_problem = BDDLUtils.load_problem(self.problem_file_path)
            env_name, env_kwargs = mesa.gen_env_name_and_kwargs(
                parsed_problem=parsed_problem,
                controller_type=self.device,
                control_delta=self.control_delta,
                robots=self.robots,
                has_renderer=True,
                **self.kwargs_update_dict,
            )
            teleop_env = RobosuiteTeleop(
                env_name=env_name,
                env_kwargs=env_kwargs,
                control_delta=self.control_delta,
            )
            if self.device == "quest":
                from mesa.data_collection.sim.devices.quest_agent import QuestAgent

                teleop_agent = QuestAgent(robot_interface=teleop_env, gain=self.gain)
            else:
                from mesa.data_collection.sim.devices.spacemouse_agent import (
                    SpaceMouseAgent,
                )

                teleop_agent = SpaceMouseAgent(robot_interface=teleop_env)
            active_device = self.device
        elif self.device == "auto":
            raise ValueError("device='auto' is no longer supported.")
        elif self.device != "none":
            raise ValueError(
                f"Unsupported device '{self.device}'. Use 'quest', 'spacemouse', or 'none'."
            )

        if teleop_env is not None and teleop_agent is not None:
            self.teleop_env = teleop_env
            self.teleop_agent = teleop_agent
            self.env = teleop_env.env
            self.active_device = active_device
            self.using_real_teleop = True
            self._zero_action = None
            if reset:
                self.teleop_env.reset()
            return

        # in case 

        if parsed_problem is None:
            parsed_problem = BDDLUtils.load_problem(self.problem_file_path)
        source_problem_name = parsed_problem["problem_name"]
        env_class = TASK_MAPPING[source_problem_name]
        self.env = env_class(
            parsed_problem=parsed_problem,
            robots=self.robots,
            has_renderer=True,
            has_offscreen_renderer=True,
            render_camera=self.render_camera,
            control_freq=self.control_freq,
            ignore_done=True,
            hard_reset=True,
            camera_names=[self.render_camera],
            camera_heights=self.camera_size,
            camera_widths=self.camera_size,
        )
        self.teleop_env = None
        self.teleop_agent = DummyTeleopDevice(num_robots=len(self.robots))
        self.active_device = None
        self.using_real_teleop = False
        self._zero_action = np.zeros(self.env.action_dim)
        if reset:
            self.env.reset()

    def reset(self):
        if self.using_real_teleop:
            return self.teleop_env.reset()
        return self.env.reset()

    def render(self) -> None:
        if self.using_real_teleop:
            self.teleop_env.render()
            return
        self.env.render()

    def get_observation(self):
        if self.teleop_env is None:
            raise RuntimeError("get_observation() is only supported for teleop envs.")
        return self.teleop_env.get_observation()

    def get_state(self):
        if self.teleop_env is None:
            raise RuntimeError("get_state() is only supported for teleop envs.")
        return self.teleop_env.get_state()

    def done(self) -> bool:
        if self.teleop_env is None:
            raise RuntimeError("done() is only supported for teleop envs.")
        return self.teleop_env.done()

    def init_noops(self, num_steps: int) -> None:
        if self.teleop_env is None:
            raise RuntimeError("init_noops() is only supported for teleop envs.")
        self.teleop_env.init_noops(num_steps)

    def reset_controller_state(self) -> None:
        if self.teleop_agent is None:
            raise RuntimeError("TeleopRunner is not created. Call create() first.")
        if hasattr(self.teleop_agent, "reset_internal_state"):
            self.teleop_agent.reset_internal_state()

    def get_control_dt(self) -> float:
        control_dt = getattr(self.env, "control_timestep", None)
        if not isinstance(control_dt, (int, float)) or control_dt <= 0:
            return 1.0 / float(self.control_freq)
        return float(control_dt)

    def set_robot_alpha(self, alpha: float) -> None:
        if self.env is None:
            raise RuntimeError("TeleopRunner is not created. Call create() first.")
        for geom_id in range(self.env.sim.model.ngeom):
            name = self.env.sim.model.geom_id2name(geom_id)
            if name is not None and "robot" in name:
                self.env.sim.model.geom_rgba[geom_id, 3] = alpha

    def get_controller_state(self) -> dict[str, Any] | None:
        if self.teleop_agent is None:
            raise RuntimeError("TeleopRunner is not created. Call create() first.")
        return self.teleop_agent.get_controller_state()

    def step(
        self,
        *,
        render: bool = True,
        require_single_arm_engaged: bool = True,
    ) -> TeleopStepResult:
        controller_state = self.get_controller_state()
        if self.using_real_teleop:
            result = run_teleop_step(
                teleop_env=self.teleop_env,
                teleop_agent=self.teleop_agent,
                controller_state=controller_state,
                render=render,
                require_single_arm_engaged=require_single_arm_engaged,
            )
            result.controller_state = controller_state
            return result

        self.env.step(self._zero_action)
        if render:
            self.env.render()
        return TeleopStepResult(
            stepped=True,
            controller_state=controller_state,
            action=self._zero_action,
            action_abs=self._zero_action,
        )

    def close(self) -> None:
        if self.teleop_agent is not None and hasattr(self.teleop_agent, "close"):
            self.teleop_agent.close()
        if self.teleop_env is not None and hasattr(self.teleop_env, "close"):
            self.teleop_env.close()
        if self.env is not None and hasattr(self.env, "close"):
            self.env.close()
        self.teleop_agent = None
        self.teleop_env = None
        self.env = None

    def serialize(self) -> dict[str, Any]:
        if self.teleop_env is None:
            raise RuntimeError("serialize() is only supported for teleop envs.")
        return self.teleop_env.serialize()


def run_teleop_step(
    teleop_env: RobosuiteTeleop,
    teleop_agent: BaseAgent | Any,
    controller_state: dict[str, Any] | None,
    *,
    render: bool = True,
    require_single_arm_engaged: bool = True,
) -> TeleopStepResult:
    if not controller_state:
        return TeleopStepResult(stepped=False)

    if len(teleop_env._robots) == 1:
        if require_single_arm_engaged and not controller_state["r"].get("engaged", True):
            return TeleopStepResult(stepped=False)
        action, action_abs = teleop_env.step([controller_state["r"]])
        if render:
            teleop_env.render()
        return TeleopStepResult(stepped=True, action=action, action_abs=action_abs)

    if hasattr(teleop_agent, "_controller_name_to_robot_id"):
        controller_order = [
            name
            for name, _ in sorted(
                teleop_agent._controller_name_to_robot_id.items(),
                key=lambda kv: kv[1],
            )
            if name in controller_state
        ]
    else:
        controller_order = ["r", "l"]

    action, action_abs = teleop_env.step(
        [controller_state[name] for name in controller_order[: len(teleop_env._robots)]]
    )
    if render:
        teleop_env.render()
    return TeleopStepResult(stepped=True, action=action, action_abs=action_abs)
