"""
Bimanual data generator with parallel per-arm subtask queues.

Extends StitchingDataGenerator to run independent left/right subtask
streams concurrently, composing 14D actions each tick.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

import random

import numpy as np
from scipy.spatial.transform import Rotation

from mesa.mimicgen.stitching_data_generator import (
    StitchingDataGenerator,
)
from mesa.mimicgen.dex.bimanual_env_interface import BimanualEnvInterface
from mesa.mimicgen.dex.arm_interface import ArmInterface
from mesa.mimicgen.dex.constants import ARM_ACTION_DIM, BIMANUAL_ACTION_DIM, GRIPPER_IDX
from mesa.mimicgen.datagen.waypoint import (
    WaypointTrajectory,
    _get_robot_joint_names_for_limits,
    _build_joint_limit_spec,
    _check_joint_limits,
)


NOOP_TAIL_STEPS = 30
MAX_STABLE_RESET_ATTEMPTS = 20
MIN_UPRIGHT_COS = 0.8


@dataclass
class _ArmState:
    """Mutable state for one arm during bimanual generation."""

    arm: ArmInterface
    arm_name: str
    queue: list
    traj: WaypointTrajectory | None = None
    traj_idx: int = 0
    active_subtask_idx: int | None = None
    prev_executed_traj: WaypointTrajectory | None = None

    def has_work(self):
        return self.traj is not None or len(self.queue) > 0


class BimanualDataGenerator(StitchingDataGenerator):
    """
    Bimanual data generator that runs independent per-arm subtask queues
    in parallel, composing 14D actions ``[left7, right7]`` each tick.
    """

    def __init__(
        self,
        task_spec,
        dataset_path,
        arm_assignment_options,
        subtask_dependencies,
        demo_keys=None,
        use_backup_subtasks_on_retry=False,
    ):
        """
        Args:
            task_spec: MG_TaskSpec instance
            dataset_path (str): path to source dataset folder
            arm_assignment_options (list[dict]): list of ``{"left": [...], "right": [...]}``
                dicts to randomly sample from per ``generate()`` call.
            subtask_dependencies (dict): per-subtask DAG, e.g.
                ``{"1": [0], "3": [2]}`` — subtask 1 waits for 0, subtask 3 waits for 2.
            demo_keys: optional demo key filter
        """
        super().__init__(task_spec=task_spec, dataset_path=dataset_path, demo_keys=demo_keys)
        self.arm_assignment_options = arm_assignment_options
        self.subtask_dependencies = {
            int(k): v for k, v in subtask_dependencies.items()
        }
        self.use_backup_subtasks_on_retry = bool(use_backup_subtasks_on_retry)
        self._current_arm_filter = None

        if self.arm_assignment_options is not None and self.demo_lookup is not None:
            self.arm_assignment_options = self._filter_viable_options(self.arm_assignment_options)
            if not self.arm_assignment_options:
                raise ValueError(
                    "No viable arm assignment options — source demos don't cover any "
                    "configuration. Collect more diverse source demos."
                )

    def _filter_viable_options(self, options):
        """Filter arm assignment options to those with matching source demos.

        For each option, checks that every (arm, subtask) pair has at least one
        source demo with the matching ``source_arm``.
        """
        available_arms = {}
        for subtask_ind in range(len(self.task_spec)):
            relevant, backup = super().search_relevant_demos(self.task_spec[subtask_ind])
            arms = set()
            for d in relevant + backup:
                arm = d.get("source_arm")
                if arm is not None:
                    arms.add(arm)
            available_arms[subtask_ind] = arms

        viable = []
        for option in options:
            ok = True
            for arm_name in ("left", "right"):
                for subtask_idx in option[arm_name]:
                    if arm_name not in available_arms.get(subtask_idx, set()):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                viable.append(option)

        if len(viable) < len(options):
            print(
                f"[BimanualDataGenerator] Pre-filtered arm_assignment_options: "
                f"{len(viable)}/{len(options)} viable "
                f"(available arms per subtask: {dict(available_arms)})"
            )
        return viable

    def search_relevant_demos(self, subtask_spec):
        """Override to strictly filter source demos by arm when _current_arm_filter is set."""
        relevant, backup = super().search_relevant_demos(subtask_spec)
        if self._current_arm_filter is not None:
            relevant = [d for d in relevant if d.get("source_arm") == self._current_arm_filter]
            backup = [d for d in backup if d.get("source_arm") == self._current_arm_filter]
        return relevant, backup

    @contextmanager
    def _arm_filter(self, arm_name):
        """Scope source-demo filtering to one arm for a single subtask build.

        ``_build_single_subtask_trajectory`` calls ``search_relevant_demos`` through
        the parent's fixed interface, so the arm is passed via this attribute rather
        than an argument; the ``finally`` guarantees it is cleared even on error.
        """
        self._current_arm_filter = arm_name
        try:
            yield
        finally:
            self._current_arm_filter = None

    def _build_subtask_trajectory(
        self,
        arm_state,
        env_interface,
        subtask_ind,
        initial_state,
        transform_first_robot_pose,
    ):
        """
        Build a WaypointTrajectory for a single subtask on a single arm.
        """
        is_first_subtask_for_arm = arm_state.prev_executed_traj is None
        cur_eef_pose = arm_state.arm.get_robot_eef_pose()
        object_poses = env_interface.get_object_poses()
        subtask_object_name = self.task_spec[subtask_ind]["object_ref"]
        cur_object_pose = (
            object_poses[subtask_object_name] if subtask_object_name is not None else None
        )
        if cur_object_pose is not None:
            cur_object_pose = cur_object_pose.copy()
        # In bimanual mode the arm often hasn't reached the previous subtask's
        # final target (limited controller bandwidth shared across two arms), so
        # interpolate_from_last_target_pose is forced False: always interpolate from
        # the *actual* EEF pose to avoid a brief reversal toward the unreached target
        # at subtask transitions.
        with self._arm_filter(arm_state.arm_name):
            traj = self._build_single_subtask_trajectory(
                subtask_ind=subtask_ind,
                cur_eef_pose=cur_eef_pose,
                cur_object_pose=cur_object_pose,
                # In bimanual mode, retry-time fallback candidate pools often introduce
                # abrupt target-pose discontinuities. Keep primary candidates by default.
                initial_state=initial_state if self.use_backup_subtasks_on_retry else None,
                is_first_subtask=is_first_subtask_for_arm,
                transform_first_robot_pose=transform_first_robot_pose,
                interpolate_from_last_target_pose=False,
                prev_executed_traj=arm_state.prev_executed_traj,
                subtask_is_last=(len(arm_state.queue) == 0),
                noop_tail_steps=NOOP_TAIL_STEPS,
                print_num_candidates=False,
            )
        return traj

    def generate(
        self,
        env,
        env_interface,
        select_src_per_subtask=False,
        transform_first_robot_pose=False,
        interpolate_from_last_target_pose=True,
        render=False,
        video_writer=None,
        video_skip=5,
        camera_names=None,
        pause_subtask=False,
        init_noops=0,
        initial_state=None,
    ):
        """
        Generate a bimanual demonstration with parallel per-arm subtask queues.
        """
        assert isinstance(env_interface, BimanualEnvInterface)
        # Accepted for signature parity with the single-arm generator but unused:
        # interpolate_from_last_target_pose is forced False per-subtask (see
        # _build_subtask_trajectory).
        _ = select_src_per_subtask, pause_subtask, interpolate_from_last_target_pose

        noop_action = np.array(env.get_noop_action())
        if initial_state is None:
            for _ in range(MAX_STABLE_RESET_ATTEMPTS):
                env.stable_reset()
                for _ in range(init_noops):
                    env.step(noop_action)
                if self._objects_upright(env):
                    break
        else:
            env.reset_to(initial_state)
            for _ in range(init_noops):
                env.step(noop_action)

        arm_states = self._init_arm_states(env_interface)
        left_state = arm_states["left"]
        right_state = arm_states["right"]
        new_initial_state = env.get_state()

        generated_states = []
        generated_obs = []
        generated_datagen_infos = []
        generated_actions = []
        generated_abs_actions = []
        any_joint_limit = False

        write_video = video_writer is not None
        video_count = 0

        robot_joint_names = _get_robot_joint_names_for_limits(env)
        joint_limit_spec = _build_joint_limit_spec(env, robot_joint_names)

        accumulated_success = False
        while left_state.has_work() or right_state.has_work():
            for arm_st in (left_state, right_state):
                self._maybe_start_next_subtask(
                    arm_state=arm_st,
                    env_interface=env_interface,
                    initial_state=initial_state,
                    transform_first_robot_pose=transform_first_robot_pose,
                    arm_states=arm_states,
                )

            left_wp = self._pop_waypoint(left_state)
            right_wp = self._pop_waypoint(right_state)

            if left_wp is None and right_wp is None:
                # Don't break if an arm still has queued subtasks – the next
                # iteration will call _maybe_start_next_subtask to begin them.
                if left_state.has_work() or right_state.has_work():
                    continue
                break

            left_action = self._waypoint_to_action(left_wp, env_interface.left, env)
            right_action = self._waypoint_to_action(right_wp, env_interface.right, env)

            action_14d = np.concatenate([left_action, right_action])

            if render:
                env.render()
            if write_video:
                if (camera_names is not None) and (video_count % video_skip == 0):
                    frames = []
                    for cam_name in camera_names:
                        frames.append(
                            env.render(mode="rgb_array", height=512, width=512, camera_name=cam_name)
                        )
                    video_writer.append_data(np.concatenate(frames, axis=1))
                video_count += 1

            state = env.get_state()["states"]
            obs = env.get_observation()

            hit_any, _, _, _ = _check_joint_limits(env.sim, joint_limit_spec, tol=1e-3)
            any_joint_limit = any_joint_limit or hit_any

            datagen_info = env_interface.get_datagen_info(
                left_action=left_action, right_action=right_action
            )

            env.step(action_14d)

            left_abs = self._to_abs_action(env_interface.left, left_action)
            right_abs = self._to_abs_action(env_interface.right, right_action)
            abs_action_14d = np.concatenate([left_abs, right_abs])

            generated_states.append(state)
            generated_obs.append(obs)
            generated_datagen_infos.append(datagen_info)
            generated_actions.append(action_14d)
            generated_abs_actions.append(abs_action_14d)

            cur_success = env.is_success()
            accumulated_success = accumulated_success or bool(cur_success.get("task", False))

        success = accumulated_success

        if len(generated_actions) > 0:
            generated_actions = np.stack(generated_actions, axis=0)
            generated_abs_actions = np.stack(generated_abs_actions, axis=0)
        else:
            generated_actions = np.zeros((0, BIMANUAL_ACTION_DIM))
            generated_abs_actions = np.zeros((0, BIMANUAL_ACTION_DIM))

        # actions_joint_pos[t] = (joint_pos[t+1], gripper[t]) per arm; last step repeats joint_pos.
        if len(generated_obs) > 0:
            r0_jp = np.array([o["robot0_joint_pos"] for o in generated_obs])  # (T, 6)
            r1_jp = np.array([o["robot1_joint_pos"] for o in generated_obs])  # (T, 6)
            r0_next = np.concatenate([r0_jp[1:], r0_jp[-1:]], axis=0)
            r1_next = np.concatenate([r1_jp[1:], r1_jp[-1:]], axis=0)
            l_grip = GRIPPER_IDX
            r_grip = ARM_ACTION_DIM + GRIPPER_IDX
            grip0 = generated_actions[:, l_grip:l_grip + 1]
            grip1 = generated_actions[:, r_grip:r_grip + 1]
            actions_joint_pos = np.concatenate([r0_next, grip0, r1_next, grip1], axis=1)  # (T, 14)
        else:
            actions_joint_pos = np.zeros((0, BIMANUAL_ACTION_DIM))

        return dict(
            initial_state=new_initial_state,
            states=generated_states,
            observations=generated_obs,
            datagen_infos=generated_datagen_infos,
            actions=generated_actions,
            abs_actions=generated_abs_actions,
            actions_joint_pos=actions_joint_pos,
            success=success,
            joint_limit_hit=any_joint_limit,
        )

    def _init_arm_states(self, env_interface):
        assignments = random.choice(self.arm_assignment_options)
        left_queue = list(assignments["left"])
        right_queue = list(assignments["right"])
        return {
            "left": _ArmState(
                arm=env_interface.left,
                arm_name="left",
                queue=left_queue,
            ),
            "right": _ArmState(
                arm=env_interface.right,
                arm_name="right",
                queue=right_queue,
            ),
        }

    def _subtask_deps_satisfied(self, subtask_idx, arm_states):
        """Check whether all per-subtask dependencies for *subtask_idx* are met.

        A dependency on index *dep* is satisfied when *dep* is no longer
        in any arm's queue and is not currently active on any arm.
        """
        required = self.subtask_dependencies.get(subtask_idx, [])
        if not required:
            return True
        all_active = {
            st.active_subtask_idx
            for st in arm_states.values()
            if st.active_subtask_idx is not None
        }
        all_queued = set()
        for st in arm_states.values():
            all_queued.update(st.queue)
        return not any(dep in all_queued or dep in all_active for dep in required)

    def _maybe_start_next_subtask(
        self,
        arm_state,
        env_interface,
        initial_state,
        transform_first_robot_pose,
        arm_states=None,
    ):
        if (arm_state.traj is not None) or (len(arm_state.queue) == 0):
            return
        if arm_states is not None:
            if not self._subtask_deps_satisfied(arm_state.queue[0], arm_states):
                return
        subtask_idx = arm_state.queue.pop(0)
        arm_state.traj = self._build_subtask_trajectory(
            arm_state=arm_state,
            env_interface=env_interface,
            subtask_ind=subtask_idx,
            initial_state=initial_state,
            transform_first_robot_pose=transform_first_robot_pose,
        )
        arm_state.traj_idx = 0
        arm_state.active_subtask_idx = subtask_idx

    @staticmethod
    def _to_abs_action(arm_interface, action):
        ctrl = arm_interface.controller
        return np.concatenate(
            [
                ctrl.goal_pos,
                Rotation.from_matrix(ctrl.goal_ori).as_rotvec(),
                action[-1:],
            ]
        )

    @staticmethod
    def _pop_waypoint(arm_state):
        """Pop next waypoint from the arm's active trajectory, or return None."""
        if arm_state.traj is None:
            return None
        if arm_state.traj_idx >= len(arm_state.traj):
            arm_state.prev_executed_traj = arm_state.traj
            arm_state.traj = None
            arm_state.traj_idx = 0
            arm_state.active_subtask_idx = None
            return None
        wp = arm_state.traj[arm_state.traj_idx]
        arm_state.traj_idx += 1
        return wp

    @staticmethod
    def _objects_upright(env, min_up_cos=MIN_UPRIGHT_COS):
        world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        for obj_name in env.objects_dict:
            body_id = env.obj_body_id.get(obj_name, None)
            if body_id is None:
                continue
            rot = np.array(env.sim.data.body_xmat[body_id]).reshape(3, 3)
            local_up_world = rot[:, 2]
            if float(np.dot(local_up_world, world_up)) < min_up_cos:
                return False
        return True

    @staticmethod
    def _get_arm_noop_action(env, arm_interface):
        """Get this arm's 7D no-op action from env.get_noop_action()."""
        noop = np.array(env.get_noop_action())
        start = int(arm_interface.robot_index) * ARM_ACTION_DIM
        end = start + ARM_ACTION_DIM
        if noop.shape[0] < end:
            raise ValueError(
                f"Invalid noop action size {noop.shape[0]} for robot index {arm_interface.robot_index}"
            )
        return noop[start:end].copy()

    def _waypoint_to_action(self, waypoint, arm_interface, env):
        """
        Convert a Waypoint to a 7D action for one arm.

        If waypoint is None (arm idle/done), use the environment's true
        per-arm no-op action.
        """
        if waypoint is None:
            return self._get_arm_noop_action(env=env, arm_interface=arm_interface)

        if waypoint.pose is not None:
            action_pose = arm_interface.target_pose_to_action(target_pose=waypoint.pose)
        else:
            action_pose = self._get_arm_noop_action(env=env, arm_interface=arm_interface)[:6]

        if waypoint.noise is not None:
            action_pose += waypoint.noise * np.random.randn(*action_pose.shape)
            action_pose = np.clip(action_pose, -1.0, 1.0)

        return np.concatenate([action_pose, waypoint.gripper_action])
