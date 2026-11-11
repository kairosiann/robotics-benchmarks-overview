from typing import Dict, List

from .articulated_multistep import (
    ArticulatedMultistepTask,
    ArticulatedMultistepTaskConfig,
    CloseTask,
    CloseTaskConfig,
    OpenTask,
    OpenTaskConfig,
)
from .handoff import HandoffTask, HandoffTaskConfig
from .pick_and_place import PickAndPlaceTask, PickAndPlaceTaskConfig
from .stack import StackTask, StackTaskConfig
from .stove_multistep import (
    TurnOffStoveTask,
    TurnOffStoveTaskConfig,
    TurnOnStoveTask,
    TurnOnStoveTaskConfig,
)
from .task import (
    TASK_REGISTRY,
    BaseTask,
    BaseTaskConfig,
    available_task_keys,
    get_task_registration,
    instantiate_task,
    register_task,
)


def generate_from_config(
    config: BaseTaskConfig,
    valid_distractor_map: Dict[str, Dict[str, List[str]]] | None = None,
    verbose: bool = False,
) -> None:
    task: BaseTask = instantiate_task(config)
    task.generate(verbose=verbose, valid_distractor_map=valid_distractor_map)


__all__ = [
    "ArticulatedMultistepTask",
    "ArticulatedMultistepTaskConfig",
    "BaseTask",
    "BaseTaskConfig",
    "HandoffTask",
    "HandoffTaskConfig",
    "CloseTask",
    "CloseTaskConfig",
    "OpenTask",
    "OpenTaskConfig",
    "PickAndPlaceTask",
    "PickAndPlaceTaskConfig",
    "StackTask",
    "StackTaskConfig",
    "TASK_REGISTRY",
    "TurnOffStoveTask",
    "TurnOffStoveTaskConfig",
    "TurnOnStoveTask",
    "TurnOnStoveTaskConfig",
    "available_task_keys",
    "generate_from_config",
    "get_task_registration",
    "instantiate_task",
    "register_task",
]
