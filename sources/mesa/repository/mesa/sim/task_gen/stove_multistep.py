from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .object_categories import (
    ArticulatedObjectSpec,
    DestObjectSpec,
    GraspObjectSpec,
    get_articulated_object_spec,
    get_grasp_object_spec,
)
from .task import BaseTask, BaseTaskConfig, register_task
from .utils import (
    make_named_articulated_object_spec,
    make_named_grasp_object_spec,
    resolve_dest_region_site,
)

FLAT_STOVE_OBJECT = "flat_stove"
FLAT_STOVE_REGION_NAME = "cook_region"


@dataclass(kw_only=True)
class StoveMultistepTaskConfig(BaseTaskConfig):
    """Configuration for generating stove multistep task suites."""

    key: str = "stove_multistep"
    start_on: bool = False
    end_on: bool = True

    cook_objects: Optional[List[str]] = None


@dataclass(kw_only=True)
class TurnOnStoveTaskConfig(StoveMultistepTaskConfig):
    """Configuration for generating turn on the stove task suites."""

    key: str = "turn_on_stove"

    def __post_init__(self):
        super().__post_init__()
        assert self.cook_objects is None, "TurnOnStoveTaskConfig: cook_objects must be None"


@dataclass(kw_only=True)
class TurnOffStoveTaskConfig(StoveMultistepTaskConfig):
    """Configuration for generating turn off the stove task suites."""

    key: str = "turn_off_stove"
    start_on: bool = True
    end_on: bool = False

    def __post_init__(self):
        super().__post_init__()
        assert self.cook_objects is None, "TurnOffStoveTaskConfig: cook_objects must be None"


@register_task("stove_multistep", config_cls=StoveMultistepTaskConfig)
class StoveMultistepTask(BaseTask):
    def __init__(self, config: StoveMultistepTaskConfig) -> None:
        super().__init__(config=config)

        self._start_on = config.start_on
        self._end_on = config.end_on

        stove_spec = get_articulated_object_spec(FLAT_STOVE_OBJECT)
        self._stove: ArticulatedObjectSpec = make_named_articulated_object_spec("stove", stove_spec)

        if self._stove.regions:
            self._cook_region = resolve_dest_region_site(
                key=self._stove.name,
                regions=self._stove.regions,
                dest_region=None,
            )
        elif config.cook_objects:
            raise ValueError(
                f"Fixture '{self._stove.name}' does not expose containment regions."
            )
        else:
            self._cook_region = None

        self._cook_objects: List[GraspObjectSpec] = []
        if config.cook_objects is not None:
            for i, object_name in enumerate(config.cook_objects):
                cook_spec = get_grasp_object_spec(object_name)
                self._cook_objects.append(make_named_grasp_object_spec(f"object_{i}", cook_spec))

    def build_task_objects(
        self,
    ) -> Tuple[List[GraspObjectSpec], List[DestObjectSpec], List[ArticulatedObjectSpec]]:
        return self._cook_objects, [], [self._stove]

    def build_initial_state(
        self,
    ) -> List[list]:
        if not self._start_on:
            return []
        assert self._stove.id is not None
        return [["turnon", self._stove.id]]

    def build_goal_state(
        self,
    ) -> List[object]:
        assert self._stove.id is not None
        goal_state: List[object] = ["and"]

        if self._end_on:
            goal_state.append(["turnon", self._stove.id])
        else:
            goal_state.append(["turnoff", self._stove.id])

        for cook_object in self._cook_objects:
            assert cook_object.id is not None
            if self._cook_region is None:
                raise ValueError("Stove cook region is not configured.")
            goal_state.append(["on", cook_object.id, f"{self._stove.id}_{self._cook_region}"])

        return goal_state

    def build_demonstration_states(
        self,
    ) -> List[list]:
        assert self._stove.id is not None
        steps: List[list] = []

        if self._start_on:
            steps.append(["turnoff", self._stove.id])

        for cook_object in self._cook_objects:
            assert cook_object.id is not None
            if self._cook_region is None:
                raise ValueError("Stove cook region is not configured.")
            steps.append(["grasp", cook_object.id])
            steps.append(["on", cook_object.id, f"{self._stove.id}_{self._cook_region}"])

        if self._end_on:
            steps.append(["turnon", self._stove.id])

        return steps


@register_task("turn_on_stove", config_cls=TurnOnStoveTaskConfig)
class TurnOnStoveTask(StoveMultistepTask):
    pass


@register_task("turn_off_stove", config_cls=TurnOffStoveTaskConfig)
class TurnOffStoveTask(StoveMultistepTask):
    pass