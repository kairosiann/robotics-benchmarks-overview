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


@dataclass(kw_only=True)
class ArticulatedMultistepTaskConfig(BaseTaskConfig):
    """Configuration for generating articulated object multistep tasks."""

    # The name of the fixture group (eg. "cabinet")
    fixture: str
    # The region of the fixture which will be articulated
    fixture_articulation_region: Optional[str] = None
    # The region of the fixture where objects will be placed
    fixture_contain_region: Optional[str] = None

    # Whether the fixture is started closed
    start_closed: bool = True
    # Whether the fixture is ended closed
    end_closed: bool = True

    # The name of the pick object group
    pick_object: Optional[str] = None
    # The name of the class of the task
    key: str = "articulated_multistep"


@dataclass(kw_only=True)
class OpenTaskConfig(ArticulatedMultistepTaskConfig):
    """Configuration for opening an articulated object."""

    def __post_init__(self) -> None:
        self.start_closed = True
        self.end_closed = False
        self.pick_object = None
        self.key = "open_fixture"


@dataclass(kw_only=True)
class CloseTaskConfig(ArticulatedMultistepTaskConfig):
    """Configuration for closing an articulated object."""

    def __post_init__(self) -> None:
        self.start_closed = False
        self.end_closed = True
        self.pick_object = None
        self.key = "close_fixture"


@register_task("articulated_multistep", config_cls=ArticulatedMultistepTaskConfig)
class ArticulatedMultistepTask(BaseTask):
    def __init__(self, config: ArticulatedMultistepTaskConfig) -> None:
        super().__init__(config=config)

        self._start_closed = config.start_closed
        self._end_closed = config.end_closed

        articulated = get_articulated_object_spec(config.fixture)
        self._articulated_object: ArticulatedObjectSpec = make_named_articulated_object_spec(
            "articulated_object",
            articulated,
        )

        if self._articulated_object.articulation_regions:
            self._articulation_region = resolve_dest_region_site(
                key=self._articulated_object.name,
                regions=self._articulated_object.articulation_regions,
                dest_region=config.fixture_articulation_region,
            )
        else:
            if config.fixture_articulation_region is not None:
                raise ValueError(
                    f"Fixture '{self._articulated_object.name}' does not expose articulation regions."
                )
            self._articulation_region = None

        self._pick_object: Optional[GraspObjectSpec]
        if config.pick_object is not None:
            pick_spec = get_grasp_object_spec(config.pick_object)
            self._pick_object = make_named_grasp_object_spec("object_0", pick_spec)
        else:
            self._pick_object = None

        if self._articulated_object.regions:
            if config.fixture_contain_region is not None or self._pick_object is not None:
                self._contain_region = resolve_dest_region_site(
                    key=self._articulated_object.name,
                    regions=self._articulated_object.regions,
                    dest_region=config.fixture_contain_region,
                )
            else:
                self._contain_region = None
        else:
            if config.fixture_contain_region is not None:
                raise ValueError(
                    f"Fixture '{self._articulated_object.name}' does not expose containment regions."
                )
            self._contain_region = None

    def build_task_objects(
        self,
    ) -> Tuple[List[GraspObjectSpec], List[DestObjectSpec], List[ArticulatedObjectSpec]]:
        pick_objects: List[GraspObjectSpec] = []
        if self._pick_object is not None:
            pick_objects.append(self._pick_object)
        return pick_objects, [], [self._articulated_object]

    def build_initial_state(
        self,
    ) -> List[list]:
        if self._start_closed:
            return []
        assert self._articulated_object.id is not None
        return [["open", self._articulation_target_name()]]

    def build_goal_state(
        self,
    ) -> List[object]:
        goal_state: List[object] = ["and"]
        assert self._articulated_object.id is not None

        if self._end_closed:
            goal_state.append(["close", self._articulation_target_name()])
        elif self._start_closed and not self._end_closed:
            goal_state.append(["open", self._articulation_target_name()])

        if self._pick_object is not None:
            assert self._pick_object.id is not None
            goal_state.append(["in", self._pick_object.id, self._contain_target_name()])

        return goal_state

    def build_demonstration_states(
        self,
    ) -> List[list]:
        steps: List[list] = []
        assert self._articulated_object.id is not None

        if self._start_closed:
            steps.append(["open", self._articulation_target_name()])

        if self._pick_object is not None:
            assert self._pick_object.id is not None
            steps.append(["grasp", self._pick_object.id])
            steps.append(["in", self._pick_object.id, self._contain_target_name()])

        if self._end_closed:
            steps.append(["close", self._articulation_target_name()])

        return steps

    def _articulation_target_name(self) -> str:
        if self._articulation_region is None:
            return self._articulated_object.id
        return f"{self._articulated_object.id}_{self._articulation_region}"

    def _contain_target_name(self) -> str:
        if self._contain_region is None:
            return self._articulated_object.id
        return f"{self._articulated_object.id}_{self._contain_region}"


@register_task("open_fixture", config_cls=OpenTaskConfig)
class OpenTask(ArticulatedMultistepTask):
    pass


@register_task("close_fixture", config_cls=CloseTaskConfig)
class CloseTask(ArticulatedMultistepTask):
    pass
    