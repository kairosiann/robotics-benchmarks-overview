from dataclasses import dataclass
from typing import List, Tuple

from .object_categories import (
    ArticulatedObjectSpec,
    DestObjectSpec,
    GraspObjectSpec,
    get_dest_object_spec,
    get_grasp_object_spec,
)
from .task import BaseTask, BaseTaskConfig, register_task
from .utils import (
    make_named_dest_object_spec,
    make_named_grasp_object_spec,
)


@dataclass(kw_only=True)
class PickAndPlaceTaskConfig(BaseTaskConfig):
    """Configuration for generating pick-and-place task suites."""

    # The name of the pick object category
    pick_objects: str | List[str]
    # The name of the destination object category
    dest_object: str
    # The region of the destination object to place the pick objects on
    dest_region: str = "on"
    # The name of the class of the task
    key: str = "pick_and_place"


@register_task("pick_and_place", config_cls=PickAndPlaceTaskConfig)
class PickAndPlaceTask(BaseTask):
    def __init__(self, config: PickAndPlaceTaskConfig) -> None:
        super().__init__(config=config)

        if isinstance(config.pick_objects, str):
            pick_objects = [config.pick_objects]
        else:
            pick_objects = config.pick_objects
        pick_objects = [get_grasp_object_spec(object_name) for object_name in pick_objects]
        self._pick_objects: List[GraspObjectSpec] = []
        for i, spec in enumerate(pick_objects):
            object_name = f"object_{i}"
            self._pick_objects.append(make_named_grasp_object_spec(object_name, spec))

        # if self.task_id == "squash_ai_pan_ai_on":
        #     breakpoint()

        dest_object = get_dest_object_spec(config.dest_object)
        self._dest_object: DestObjectSpec = make_named_dest_object_spec("dest_object", dest_object)
        self._dest_region = config.dest_region
        # if config.goal_predicate is None:
        #     if len(self._dest_object.regions) == 1 and self._dest_object.regions[0] == "on":
        #         self._goal_predicate = "on"
        #     else:
        #         self._goal_predicate = "in"
        # else:
        #     self._goal_predicate = config.goal_predicate

        # if self._goal_predicate == "in":
        #     if len(self._dest_object.regions) == 1:
        #         self._dest_region = self._dest_object.regions[0]
        #     else:
        #         assert config.dest_region is not None
        #         self._dest_region = config.dest_region

    def build_task_objects(
        self
    ) -> Tuple[List[GraspObjectSpec], List[DestObjectSpec], List[ArticulatedObjectSpec]]:
        return self._pick_objects, [self._dest_object], []

    def build_goal_state(
        self
    ) -> List[object]:
        goal_state: List[object] = ["and"]
        assert self._dest_object.id is not None
        for pick_object in self._pick_objects:
            assert pick_object.id is not None
            if self._dest_region == "on":
                goal_state.append(["on", pick_object.id, self._dest_object.id])
            else:
                contain_region_name = f"{self._dest_object.id}_{self._dest_region}"
                goal_state.append(["in", pick_object.id, contain_region_name])
        return goal_state

    def build_demonstration_states(
        self,
    ) -> List[list]:
        steps: List[list] = []
        assert self._dest_object.id is not None
        for pick_object in self._pick_objects:
            assert pick_object.id is not None
            steps.append(["grasp", pick_object.id])
            if self._dest_region == "on":
                steps.append(["on", pick_object.id, self._dest_object.id])
            else:
                contain_region_name = f"{self._dest_object.id}_{self._dest_region}"
                steps.append(["in", pick_object.id, contain_region_name])
        return steps
