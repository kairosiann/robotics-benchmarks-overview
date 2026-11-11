# Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the NVIDIA Source Code License [see LICENSE for details].

"""
Dataclass-based config for mimicgen data generation.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceConfig:
    """Configuration for source dataset."""
    dataset_path: Optional[str] = None
    """Path to either a source hdf5 dataset or a dataset folder with demo_lookup.json"""
    filter_key: Optional[str] = None
    """Filter key to select a subset of trajectories in the source hdf5 dataset."""
    n: Optional[int] = None
    """If provided, use only the first @n trajectories in source hdf5 dataset."""
    start: Optional[int] = None
    """If provided, exclude the first @start trajectories in source hdf5 dataset."""


@dataclass
class GenerationConfig:
    """Configuration for data generation."""
    path: Optional[str] = None
    """Path where new dataset folder will be created."""
    stitching: bool = False
    """Whether to use a stitching source dataset."""
    guarantee: bool = False
    """Whether to keep running data collection until we have @num_trials successful trajectories."""
    keep_failed: bool = True
    """Whether to keep failed trajectories as well."""
    filter_joint_limit: bool = True
    """Whether to filter out trajectories that hit joint limits."""
    n_reuse_initial_state: int = 0
    """Number of times to retry one initial state in case of failure."""
    num_trials: int = 10
    """Number of attempts to collect new data."""
    init_noops: int = 0
    """Number of noops to execute at the beginning of the trajectory."""
    select_src_per_subtask: bool = False
    """If True, select a different source demonstration for each subtask during data generation."""
    transform_first_robot_pose: bool = False
    """If True, each subtask segment will consist of the first robot pose and the target poses."""
    interpolate_from_last_target_pose: bool = True
    """If True, each interpolation segment will start from the last target pose in the previous subtask segment."""


@dataclass
class TaskConfig:
    """Configuration for task used for data generation."""
    name: Optional[str] = None
    """If provided, override the env name in env meta."""
    robot: Optional[str] = None
    """If provided, override the robot name in env meta."""
    gripper: Optional[str] = None
    """If provided, override the gripper in env meta."""
    env_meta_update_kwargs: Dict[str, Any] = field(default_factory=dict)
    """If provided, override the arguments passed to the environment constructor."""
    interface: Optional[str] = None
    """If provided, override the environment interface class to use for this task."""
    interface_type: Optional[str] = None
    """If provided, specify environment interface type to use for this task."""


@dataclass
class ExperimentConfig:
    """Configuration for experiment settings."""
    name: str = "demo"
    """Name of the experiment - used to name the dataset folder that is generated."""
    source: SourceConfig = field(default_factory=SourceConfig)
    """Settings related to source dataset."""
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    """Settings related to data generation."""
    task: TaskConfig = field(default_factory=TaskConfig)
    """Settings related to task used for data generation."""
    max_num_failures: int = 50
    """Maximum number of failure demos to save."""
    render_video: bool = True
    """Whether to render some generated demos to video."""
    num_demo_to_render: int = 50
    """Maximum number of demos to render to video."""
    num_fail_demo_to_render: int = 50
    """Maximum number of failure demos to render to video."""
    log_every_n_attempts: int = 50
    """Logs important info every N generation attempts."""
    seed: int = 1
    """Random seed for generation."""


@dataclass
class ObsConfig:
    """Configuration for observations."""
    collect_obs: bool = True
    """Whether to collect observations."""
    camera_names: List[str] = field(default_factory=list)
    """Which cameras to render observations from."""
    camera_height: int = 84
    """Camera height."""
    camera_width: int = 84
    """Camera width."""


@dataclass
class TaskSpecConfig:
    """Configuration for task specification."""
    task_spec: Dict[str, Any] = field(default_factory=dict)
    """Task specification dictionary."""


@dataclass
class MGConfig:
    """Main MimicGen configuration dataclass."""
    name: str
    """Name of the config."""
    task_suite_name: str
    """Name of the task suite."""
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    """Experiment configuration."""
    obs: ObsConfig = field(default_factory=ObsConfig)
    """Observation configuration."""
    task: TaskSpecConfig = field(default_factory=TaskSpecConfig)
    """Task specification configuration."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the config to a dictionary."""
        return {
            "name": self.name,
            "task_suite_name": self.task_suite_name,
            "experiment": {
                "name": self.experiment.name,
                "source": {
                    "dataset_path": self.experiment.source.dataset_path,
                    "filter_key": self.experiment.source.filter_key,
                    "n": self.experiment.source.n,
                    "start": self.experiment.source.start,
                },
                "generation": {
                    "path": self.experiment.generation.path,
                    "stitching": self.experiment.generation.stitching,
                    "guarantee": self.experiment.generation.guarantee,
                    "keep_failed": self.experiment.generation.keep_failed,
                    "filter_joint_limit": self.experiment.generation.filter_joint_limit,
                    "n_reuse_initial_state": self.experiment.generation.n_reuse_initial_state,
                    "num_trials": self.experiment.generation.num_trials,
                    "init_noops": self.experiment.generation.init_noops,
                    "select_src_per_subtask": self.experiment.generation.select_src_per_subtask,
                    "transform_first_robot_pose": self.experiment.generation.transform_first_robot_pose,
                    "interpolate_from_last_target_pose": self.experiment.generation.interpolate_from_last_target_pose,
                },
                "max_num_failures": self.experiment.max_num_failures,
                "render_video": self.experiment.render_video,
                "num_demo_to_render": self.experiment.num_demo_to_render,
                "num_fail_demo_to_render": self.experiment.num_fail_demo_to_render,
                "log_every_n_attempts": self.experiment.log_every_n_attempts,
                "seed": self.experiment.seed,
            },
            "obs": {
                "collect_obs": self.obs.collect_obs,
                "camera_names": self.obs.camera_names,
                "camera_height": self.obs.camera_height,
                "camera_width": self.obs.camera_width,
            },
            "task": {
                "task_spec": self.task.task_spec,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MGConfig":
        """Create a config from a dictionary."""
        experiment_data = data.get("experiment", {})
        source_data = experiment_data.get("source", {})
        generation_data = experiment_data.get("generation", {})
        task_data = experiment_data.get("task", {})
        obs_data = data.get("obs", {})
        task_spec_data = data.get("task", {})

        return cls(
            name=data["name"],
            task_suite_name=data["task_suite_name"],
            experiment=ExperimentConfig(
                name=experiment_data.get("name", "demo"),
                source=SourceConfig(
                    dataset_path=source_data.get("dataset_path"),
                    filter_key=source_data.get("filter_key"),
                    n=source_data.get("n"),
                    start=source_data.get("start"),
                ),
                generation=GenerationConfig(
                    path=generation_data.get("path"),
                    stitching=generation_data.get("stitching", False),
                    guarantee=generation_data.get("guarantee", False),
                    keep_failed=generation_data.get("keep_failed", True),
                    filter_joint_limit=generation_data.get("filter_joint_limit", True),
                    n_reuse_initial_state=generation_data.get("n_reuse_initial_state", 0),
                    num_trials=generation_data.get("num_trials", 10),
                    init_noops=generation_data.get("init_noops", 0),
                    select_src_per_subtask=generation_data.get("select_src_per_subtask", False),
                    transform_first_robot_pose=generation_data.get("transform_first_robot_pose", False),
                    interpolate_from_last_target_pose=generation_data.get("interpolate_from_last_target_pose", True),
                ),
                task=TaskConfig(
                    name=task_data.get("name"),
                    robot=task_data.get("robot"),
                    gripper=task_data.get("gripper"),
                    env_meta_update_kwargs=task_data.get("env_meta_update_kwargs", {}),
                    interface=task_data.get("interface"),
                    interface_type=task_data.get("interface_type"),
                ),
                max_num_failures=experiment_data.get("max_num_failures", 50),
                render_video=experiment_data.get("render_video", True),
                num_demo_to_render=experiment_data.get("num_demo_to_render", 50),
                num_fail_demo_to_render=experiment_data.get("num_fail_demo_to_render", 50),
                log_every_n_attempts=experiment_data.get("log_every_n_attempts", 50),
                seed=experiment_data.get("seed", 1),
            ),
            obs=ObsConfig(
                collect_obs=obs_data.get("collect_obs", True),
                camera_names=obs_data.get("camera_names", []),
                camera_height=obs_data.get("camera_height", 84),
                camera_width=obs_data.get("camera_width", 84),
            ),
            task=TaskSpecConfig(
                task_spec=task_spec_data.get("task_spec", {}),
            ),
        )

    def dump(self, filename: str) -> None:
        """Save the config to a JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)

    @classmethod
    def load(cls, filename: str) -> "MGConfig":
        """Load a config from a JSON file."""
        with open(filename, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def update(self, other: Dict[str, Any]) -> None:
        """Update the config with values from another dictionary."""
        # Update experiment settings
        if "experiment" in other:
            exp_data = other["experiment"]
            if "name" in exp_data:
                self.experiment.name = exp_data["name"]
            if "source" in exp_data:
                source_data = exp_data["source"]
                for key, value in source_data.items():
                    if hasattr(self.experiment.source, key):
                        setattr(self.experiment.source, key, value)
            if "generation" in exp_data:
                gen_data = exp_data["generation"]
                for key, value in gen_data.items():
                    if hasattr(self.experiment.generation, key):
                        setattr(self.experiment.generation, key, value)
            # Update other experiment fields
            for key, value in exp_data.items():
                if key not in ["name", "source", "generation", "task"] and hasattr(self.experiment, key):
                    setattr(self.experiment, key, value)
        
        # Update obs settings
        if "obs" in other:
            obs_data = other["obs"]
            for key, value in obs_data.items():
                if hasattr(self.obs, key):
                    setattr(self.obs, key, value)
        
        # Update task settings
        if "task" in other:
            task_data = other["task"]
            for key, value in task_data.items():
                if hasattr(self.task, key):
                    setattr(self.task, key, value)