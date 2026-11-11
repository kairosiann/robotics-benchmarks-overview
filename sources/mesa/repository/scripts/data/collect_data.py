"""
Script for collecting teleop demonstrations in a simulation environment 
using a Meta Quest controller or a SpaceMouse.

Meta Quest Controls:
    - Left controller: move first robot in bimanual mode
    - Right controller: move second robot in bimanual mode (single-arm still uses right)
    - A button: save demo at any stage (saving also automatically happens when task is done)
    - B button: delete current demo, and start a new one
    - ctrl+C: discard current demo and exit
SpaceMouse Controls:
    - Joystick: move robot
    - Right button: start data collection / discard demo
    - Left button: toggle gripper
    - ctrl+C: discard current demo and exit

Args:
    --files: list of BDDL file paths to collect demos for
    --demos_per_file: number of demos to collect for each file
    --gain (optional, default=1.0): positional gain for Quest controller
    --control_delta (optional, default=False): whether to control robot using delta OSC for data collection
    --robots (optional): robot(s) to use for this task
    --device (optional, default=quest): device to use for data collection
    --collect_more (optional, default=5): number of extra timesteps to collect after task success

Example usage:

    Example usage:

        python scripts/collect_data_multiple.py \
            --files /abs/path/to/task_a.bddl /abs/path/to/task_b.bddl \
            --demos_per_file 5 \
            --robots Panda \
            --device spacemouse
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import h5py
import numpy as np
from natsort import natsorted
from termcolor import colored

import mesa.sim.envs.bddl_utils as BDDLUtils
import mesa.utils.tensor_utils as TensorUtils
from mesa import MESA_ROOT
from mesa.data_collection.sim.demo_saver import DemoSaver
from mesa.data_collection.sim.robosuite_teleop import RobosuiteTeleop
from mesa.data_collection.sim.teleop_runner import (
    TeleopRunner,
)
from mesa.mimicgen.env_interfaces.base import make_interface
from mesa.sim.envs.bddl_base_domain import BDDLBaseDomain

np.set_printoptions(precision=3, suppress=True)


@dataclass
class Args:
    # Task suite name used to look up BDDL files and choose output directory
    task_suite_name: str
    # Task id, which should be a member of the task suite
    task_id: str
    # Minimum number of demos to collect in case you want more than the number of source BDDL files
    min_num_demos: Optional[int] = None
    # Number of demos to collect. This takes precedence over min_num_demos.
    num_demos: Optional[int] = None
    # Directory containing BDDL files
    task_dir: str = "task_suites"
    # Gain for the controller
    gain: float = 1.5
    # Whether to control the robot using delta OSC
    control_delta: bool = False
    # Robots to use for this task
    robots: list[str] | None = None
    # Teleoperation device to use for data collection
    device: str = "quest"
    # Number of extra timesteps to collect after task success
    collect_more: int = 5
    # Directory to save the collected data. Defaults to ../data
    output_dir: str | None = None
    # Camera to use for rendering
    render_camera: str = "behindview"
    # How many timesteps before terminating the episode
    horizon: int = 3000
    # Size of the camera
    camera_size: int = 128
    # Control frequency
    control_freq: int = 15
    # Whether to retry the episode if it fails
    force_retry: bool = True
    # Whether to save datagen_info. Enabled by default; disable manually via CLI if needed.
    save_datagen_info: bool = True
    # Name of the environment interface to use in case you want to save datagen_info
    env_interface: str = "MESAInterface"
    # Type of the environment interface to use in case you want to save datagen_info
    env_interface_type: str = "mesa"


def _save_datagen_info_to_hdf5(
    save_path: str,
    env_interface_name: str,
    env_interface_type: str,
    datagen_info: dict[str, np.ndarray | dict[str, np.ndarray]],
    parsed_problem: dict,
) -> None:
    with h5py.File(save_path, "a") as h5_file:
        ep_grp = h5_file["data/demo_0"]
        if "datagen_info" in ep_grp:
            del ep_grp["datagen_info"]

        for key in datagen_info:
            if key in ["object_poses", "subtask_term_signals"]:
                for nested_key in datagen_info[key]:
                    ep_grp.create_dataset(
                        f"datagen_info/{key}/{nested_key}",
                        data=np.array(datagen_info[key][nested_key]),
                    )
            else:
                ep_grp.create_dataset(f"datagen_info/{key}", data=np.array(datagen_info[key]))

        datagen_grp = ep_grp["datagen_info"]
        datagen_grp.attrs["env_interface_name"] = env_interface_name
        datagen_grp.attrs["env_interface_type"] = env_interface_type

        subtask_list = parsed_problem["demonstration_states"]
        subtasks = BDDLUtils.get_search_spec_list(
            subtask_list=subtask_list,
            objects_dict=parsed_problem["objects"],
            regions_dict=parsed_problem["regions"],
            fixtures_dict=parsed_problem["fixtures"],
        )
        datagen_grp.attrs["subtasks"] = json.dumps(subtasks)
        datagen_grp.attrs["demonstration_states"] = json.dumps(subtask_list)


def _stack_datagen_info(datagen_info_steps: list[dict]) -> dict[str, np.ndarray | dict[str, np.ndarray]]:
    all_datagen_infos = TensorUtils.list_of_flat_dict_to_dict_of_list(datagen_info_steps)
    for key in all_datagen_infos:
        if key in ["object_poses", "subtask_term_signals"]:
            all_datagen_infos[key] = TensorUtils.list_of_flat_dict_to_dict_of_list(all_datagen_infos[key])
            for nested_key in all_datagen_infos[key]:
                all_datagen_infos[key][nested_key] = np.array(all_datagen_infos[key][nested_key])
        else:
            all_datagen_infos[key] = np.array(all_datagen_infos[key])
    return all_datagen_infos


def collect_data(args: Args):
    if args.robots is not None:
        robots = args.robots
    else:
        robots = ["Panda"]

    task_file_folder = Path(MESA_ROOT) / "task_suites" / "bddl_files" / args.task_suite_name / args.task_id / "source"
    assert task_file_folder.exists(), f"Task file folder {task_file_folder} does not exist"
    task_file_paths = natsorted(list(task_file_folder.glob("*.json")))

    def make_new_env(demo_idx: int):
        path_idx = demo_idx % len(task_file_paths)
        print(f'Creating new env for {task_file_paths[path_idx]}')
        problem_file_path = str(task_file_paths[path_idx])
        teleop_runner = TeleopRunner(
            problem_file_path=problem_file_path,
            robots=robots,
            device=args.device,
            control_delta=args.control_delta,
            gain=args.gain,
            render_camera=args.render_camera,
            horizon=args.horizon,
            control_freq=args.control_freq,
            camera_size=args.camera_size,
        )
        teleop_runner.create(reset=False)

        env_args = teleop_runner.serialize()
        
        return teleop_runner, env_args

    def restore_env_state(
        teleop_env: RobosuiteTeleop, snapshot: dict[str, object]
    ) -> dict:
        if snapshot is None:
            raise ValueError("No environment snapshot available to restore.")

        states = snapshot.get("states")
        if states is None:
            raise ValueError("Snapshot is missing simulator state under 'states'.")

        model_xml = snapshot.get("model")

        if model_xml is not None and hasattr(teleop_env.env, "reset_to"):
            obs = teleop_env.env.reset_to({"states": states, "model": model_xml})
        else:
            teleop_env.env.sim.reset()
            teleop_env.env.sim.set_state_from_flattened(states)
            teleop_env.env.sim.forward()
            obs = teleop_env.get_observation()

        return obs

    # Prepare save directory per file
    if args.output_dir is None:
        save_dir = os.path.join(
            MESA_ROOT, 
            "..", 
            "data", 
            "source", 
            args.task_suite_name, 
            args.task_id,
        )
    else:
        save_dir = os.path.join(args.output_dir, "source", args.task_suite_name, args.task_id)
    os.makedirs(save_dir, exist_ok=True)

    demos_collected = len(os.listdir(save_dir))
    teleop_runner, env_args = make_new_env(demos_collected)
    teleop_env = teleop_runner.teleop_env
    if teleop_env is None:
        raise RuntimeError("TeleopRunner did not create a teleop environment.")
    if teleop_runner.env is None:
        raise RuntimeError("TeleopRunner did not create an environment.")
    env_interface = None
    if args.save_datagen_info:
        env_interface = make_interface(
            name=args.env_interface,
            interface_type=args.env_interface_type,
            env=teleop_runner.env,
        )
        print(colored(f"Using env interface for datagen_info: {env_interface}", "cyan"))

    cached_initial_snapshot: dict[str, object] | None = None
    reuse_cached_initial_state = False


    need_new_env = False
    assert args.num_demos is None or args.min_num_demos is None, "Only one of num_demos or min_num_demos can be provided"
    if args.min_num_demos is not None:
        num_demos = max(args.min_num_demos, len(task_file_paths))
    elif args.num_demos is None:
        num_demos = len(task_file_paths)
    else:
        num_demos = args.num_demos
    while demos_collected < num_demos:
        print(colored(f"resetting env for {args.task_suite_name} {args.task_id}...", "cyan"))
        if need_new_env:
            teleop_runner.close()
            teleop_runner, env_args = make_new_env(demos_collected)
            teleop_env = teleop_runner.teleop_env
            if teleop_env is None:
                raise RuntimeError("TeleopRunner did not create a teleop environment.")
            if teleop_runner.env is None:
                raise RuntimeError("TeleopRunner did not create an environment.")
            if args.save_datagen_info:
                env_interface = make_interface(
                    name=args.env_interface,
                    interface_type=args.env_interface_type,
                    env=teleop_runner.env,
                )
                print(colored(f"Using env interface for datagen_info: {env_interface}", "cyan"))
            need_new_env = False
            cached_initial_snapshot = None
            reuse_cached_initial_state = False

        if args.force_retry and reuse_cached_initial_state and cached_initial_snapshot is not None:
            print(colored("Restoring environment to saved initial state...", "yellow"))
            obs = restore_env_state(teleop_env, cached_initial_snapshot)
            state, current_xml = teleop_runner.get_state()
            cached_initial_snapshot.setdefault("model", current_xml)
        else:
            obs = teleop_runner.reset()
            state, current_xml = teleop_runner.get_state()
            cached_initial_snapshot = {
                "states": state.copy(),
                "model": current_xml,
            }
        reuse_cached_initial_state = False
        init_xml = (
            cached_initial_snapshot["model"]
            if cached_initial_snapshot is not None
            else current_xml
        )

        # Make robot partially transparent for teleop
        teleop_runner.set_robot_alpha(alpha=0.1)
        
        teleop_runner.init_noops(30)
        teleop_runner.render()

        # Demo saving.
        save_path = os.path.join(save_dir, f"demo_{demos_collected}.hdf5")
        demo_saver = DemoSaver(save_path, env_args, init_xml, flush_freq=50)
        data_buffer = {
            "obs": None,
            "actions": None,
            "actions_abs": None,
            "states": None,
        }
        datagen_info_buffer: list[dict] = []

        teleop_runner.reset_controller_state()
        delete_demo = False
        save_demo = False

        curr_demo_state_idx = 0
        demo_state_printed = False

        collect_n_more = None

        try:

            control_dt = teleop_runner.get_control_dt()

            while True:
                start_time = time.time()
                
                if delete_demo or save_demo:
                    break

                if collect_n_more is not None:
                    if collect_n_more > 0:
                        collect_n_more -= 1
                    else:
                        save_demo = True
                        continue

                if teleop_runner.done() and collect_n_more is None:
                    collect_n_more = args.collect_more
                    print(
                        colored(
                            f"Task done. Collecting {collect_n_more} more timesteps...",
                            "yellow",
                        )
                    )

                if isinstance(teleop_runner.env, BDDLBaseDomain):
                    demo_states = teleop_runner.env.parsed_problem[
                        "demonstration_states"
                    ]
                    if curr_demo_state_idx < len(demo_states):  # otherwise, done
                        curr_demo_state = demo_states[curr_demo_state_idx]
                        done = teleop_runner.env._eval_predicate(curr_demo_state)
                        if not done and not demo_state_printed:
                            print(
                                colored("Current subtask:", "green"),
                                colored(
                                    f"{' '.join(curr_demo_state)}",
                                    "red",
                                    attrs=["bold"],
                                ),
                            )
                            demo_state_printed = True
                        elif done:
                            print(
                                colored(f"Done.", "green", attrs=["bold"]) 
                            )
                            curr_demo_state_idx += 1
                            demo_state_printed = False

                controller_state = teleop_runner.get_controller_state()
                if controller_state:  # sleep if None
                    # save_demo = controller_state.get("save_demo", False)
                    delete_demo = controller_state.get("delete_demo", False)

                    step_result = teleop_runner.step(
                        render=True,
                        require_single_arm_engaged=True,
                    )
                    if step_result.stepped:
                        ac = step_result.action
                        ac_abs = step_result.action_abs
                        # demo saving
                        data_buffer["obs"] = obs
                        data_buffer["actions"] = ac
                        data_buffer["actions_abs"] = ac_abs
                        data_buffer["states"] = state
                        demo_saver.append(data_buffer)
                        if args.save_datagen_info:
                            datagen_info = env_interface.get_datagen_info(action=np.array(ac)).to_dict()
                            datagen_info_buffer.append(datagen_info)

                time.sleep(max(0, control_dt - (time.time() - start_time)))

                obs = teleop_runner.get_observation()
                state, _ = teleop_runner.get_state()

            if not delete_demo:
                print(colored(f"Demo successful. Length: {len(demo_saver)}. Would you like to save it? (Yes = a / no = b)", "cyan"))
                while True:
                    controller_state = teleop_runner.get_controller_state()
                    if controller_state.get("save_demo", False):
                        break
                    elif controller_state.get("delete_demo", False):
                        delete_demo = True
                        break
                    time.sleep(0.001)
            
            if delete_demo:
                print(colored("Discarding current demo...", "red"))
                demo_saver.discard()
                reuse_cached_initial_state = cached_initial_snapshot is not None and len(demo_saver) > 10
            else:
                demo_saver.done()
                if args.save_datagen_info:
                    if len(datagen_info_buffer) == 0:
                        print(colored("No teleop steps recorded. Skipping datagen_info save.", "yellow"))
                    else:
                        datagen_info = _stack_datagen_info(datagen_info_buffer)
                        _save_datagen_info_to_hdf5(
                            save_path=save_path,
                            env_interface_name=args.env_interface,
                            env_interface_type=args.env_interface_type,
                            datagen_info=datagen_info,
                            parsed_problem=teleop_runner.env.parsed_problem,
                        )
                        print(colored("Saved datagen_info in demo file.", "green"))
                demos_collected += 1
                need_new_env = len(task_file_paths) > 1
                cached_initial_snapshot = None
                reuse_cached_initial_state = False
                print(colored(f"Saved demo {demos_collected}/{num_demos} for {args.task_suite_name} {args.task_id}", "green"))

        except KeyboardInterrupt:
            print(colored("Keyboard interrupt received.", "red"))
            print(colored("Discarding current demo...", "red"))
            demo_saver.discard()
            return

    teleop_runner.close()


if __name__ == "__main__":
    import tyro

    args = tyro.cli(Args)
    collect_data(args)
