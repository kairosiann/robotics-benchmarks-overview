import dataclasses
import logging
import socket
from typing import Literal

import numpy as np
import tyro
from openpi_client import base_policy as _base_policy

from mesa.serving import websocket_policy_server


@dataclasses.dataclass
class Args:
    host: str = "0.0.0.0"
    port: int = 8001
    noise_std: float = 0.05
    seed: int = 7
    exit_on_first_disconnect: bool = False
    controller_type: str = "joint_pos"
    control_delta: bool = False


class JointAnglesWithNoisePolicy(_base_policy.BasePolicy):
    def __init__(
        self,
        *,
        action_dim: int,
        action_horizon: int,
        noise_std: float,
        seed: int,
    ) -> None:
        self._action_dim = action_dim
        self._action_horizon = action_horizon
        self._noise_std = noise_std
        self._rng = np.random.default_rng(seed)
        self._metadata = {
            "policy_type": "joint_angles_plus_noise_demo",
            "action_dim": action_dim,
            "action_horizon": action_horizon,
            "noise_std": noise_std,
        }

    @property
    def metadata(self) -> dict:
        return self._metadata

    def infer(self, obs: dict) -> dict:
        if "state" not in obs:
            raise KeyError("Expected observation to contain key 'state'.")

        state = np.asarray(obs["state"], dtype=np.float32).reshape(-1)
        if state.size == 0:
            raise ValueError("Observation state is empty.")

        base_action = np.zeros(self._action_dim, dtype=np.float32)
        copy_dim = min(self._action_dim, state.size)
        base_action[:copy_dim] = state[:copy_dim]

        noise = self._rng.normal(
            loc=0.0,
            scale=self._noise_std,
            size=(self._action_horizon, self._action_dim),
        ).astype(np.float32)
        actions = base_action[None, :] + noise
        return {"actions": actions.tolist()}


class DeltaOSCPolicy(_base_policy.BasePolicy):
    def __init__(
        self,
        *,
        action_dim: int,
        action_horizon: int,
        noise_std: float,
        seed: int,
    ) -> None:
        self._action_dim = action_dim
        self._action_horizon = action_horizon
        self._noise_std = noise_std
        self._rng = np.random.default_rng(seed)
        self._metadata = {
            "policy_type": "osc_delta_noise_demo",
            "action_dim": action_dim,
            "action_horizon": action_horizon,
            "noise_std": noise_std,
        }

    @property
    def metadata(self) -> dict:
        return self._metadata

    def infer(self, obs: dict) -> dict:
        del obs
        actions = self._rng.normal(
            loc=0.0,
            scale=self._noise_std,
            size=(self._action_horizon, self._action_dim),
        ).astype(np.float32)
        return {"actions": actions.tolist()}


class AbsOSCPolicy(_base_policy.BasePolicy):
    def __init__(
        self,
        *,
        action_horizon: int,
        noise_std: float,
        seed: int,
    ) -> None:
        self._action_dim = 6
        self._action_horizon = action_horizon
        self._noise_std = noise_std
        self._rng = np.random.default_rng(seed)
        self._metadata = {
            "policy_type": "osc_abs_pose_plus_noise_demo",
            "action_dim": self._action_dim,
            "action_horizon": action_horizon,
            "noise_std": noise_std,
            "state_layout": "state[:3]=pos, state[3:7]=quat_xyzw",
        }

    @property
    def metadata(self) -> dict:
        return self._metadata

    def infer(self, obs: dict) -> dict:
        if "state" not in obs:
            raise KeyError("Expected observation to contain key 'state'.")

        state = np.asarray(obs["state"], dtype=np.float32).reshape(-1)
        if state.size != 7:
            raise ValueError(
                f"AbsOSCPolicy expected a 7D state [pos(3), quat(4)], got shape ({state.size},). Make sure you added --state-keys robot0_eef_pos robot0_eef_quat to the policy server"
            )

        pos = state[:3]
        quat_xyzw = state[3:7]
        axis_angle = self._quat_xyzw_to_axis_angle(quat_xyzw)
        base_action = np.concatenate([pos, axis_angle], axis=0).astype(np.float32)
        noise = self._rng.normal(
            loc=0.0,
            scale=self._noise_std,
            size=(self._action_horizon, self._action_dim),
        ).astype(np.float32)
        actions = base_action[None, :] + noise
        gripper_action = np.ones((self._action_horizon, 1)).astype(np.float32)
        actions = np.concatenate([actions, gripper_action], axis=1)
        return {"actions": actions.tolist()}

    @staticmethod
    def _quat_xyzw_to_axis_angle(quat_xyzw: np.ndarray) -> np.ndarray:
        quat = np.asarray(quat_xyzw, dtype=np.float64).reshape(4)
        quat_norm = np.linalg.norm(quat)
        if quat_norm < 1e-8:
            return np.zeros(3, dtype=np.float32)
        quat /= quat_norm

        xyz = quat[:3]
        w = float(quat[3])
        if w < 0.0:
            xyz = -xyz
            w = -w

        sin_half = np.linalg.norm(xyz)
        if sin_half < 1e-8:
            return np.zeros(3, dtype=np.float32)

        angle = 2.0 * np.arctan2(sin_half, w)
        axis = xyz / sin_half
        return (axis * angle).astype(np.float32)


def main(args: Args) -> None:
    if args.controller_type == "joint_pos":
        if args.control_delta:
            raise ValueError("Control delta is not supported for joint position control.")
        policy = JointAnglesWithNoisePolicy(
            action_dim=8,
            action_horizon=10,
            noise_std=args.noise_std,
            seed=args.seed,
        )
    elif args.controller_type == "osc_pose":
        if args.control_delta:
            policy = DeltaOSCPolicy(
                action_dim=7,
                action_horizon=10,
                noise_std=args.noise_std,
                seed=args.seed,
            )
        else:
            policy = AbsOSCPolicy(
                action_horizon=10,
                noise_std=args.noise_std,
                seed=args.seed,
            )
    else:
        raise ValueError(f"Invalid controller type: {args.controller_type}")

    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    logging.info("Starting demo policy server on %s:%d", args.host, args.port)
    logging.info("Host: %s, IP: %s", hostname, local_ip)

    server = websocket_policy_server.WebsocketPolicyServer(
        policy=policy,
        host=args.host,
        port=args.port,
        metadata=policy.metadata,
        exit_on_first_disconnect=args.exit_on_first_disconnect,
    )
    server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, force=True)
    main(tyro.cli(Args))
