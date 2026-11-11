from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from .object_categories import (
    GRASP_OBJECTS,
    ArticulatedObjectSpec,
    DestObjectSpec,
    GraspObjectSpec,
    get_grasp_object_spec,
)
from .task import BaseTask, BaseTaskConfig, register_task
from .utils import make_named_grasp_object_spec


@dataclass(kw_only=True)
class StackTaskConfig(BaseTaskConfig):
    """Configuration for generating stack task suites."""

    object_pattern: str
    key: str = "stack"
    class_name: str = "StackTask"


@register_task("stack", config_cls=StackTaskConfig)
class StackTask(BaseTask):
    """Task generator for stacking identical objects."""

    def __init__(self, config: StackTaskConfig) -> None:
        super().__init__(config=config)
        object_pattern_regex = re.compile(config.object_pattern)

        stackable_objects = [
            key
            for key, spec in GRASP_OBJECTS.items()
            if spec.stackable and object_pattern_regex.search(key)
        ]
        if not stackable_objects:
            raise ValueError(
                f"No stackable objects found matching pattern '{config.object_pattern}'"
            )
        self._stackable_objects = sorted(stackable_objects)
        primary_object = self._stackable_objects[0]
        top_spec = get_grasp_object_spec(primary_object)
        base_spec = get_grasp_object_spec(primary_object)
        self._top_object = make_named_grasp_object_spec("object_0", top_spec)
        self._base_object = make_named_grasp_object_spec("object_1", base_spec)

    def build_task_objects(
        self,
    ) -> Tuple[List[GraspObjectSpec], List[DestObjectSpec], List[ArticulatedObjectSpec]]:
        return [self._top_object, self._base_object], [], []

    def build_goal_state(
        self,
    ) -> List[object]:
        assert self._top_object.id is not None
        assert self._base_object.id is not None
        return [
            "or",
            ["stack", self._top_object.id, self._base_object.id],
            ["stack", self._base_object.id, self._top_object.id],
        ]

    def build_demonstration_states(
        self,
    ) -> List[list]:
        assert self._top_object.id is not None
        assert self._base_object.id is not None
        return [
            ["grasp", self._top_object.id],
            ["stack", self._top_object.id, self._base_object.id],
        ]

    def get_num_source_variants(self) -> int:
        return 1