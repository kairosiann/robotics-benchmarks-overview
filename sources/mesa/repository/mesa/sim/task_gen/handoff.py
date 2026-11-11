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


HANDOFF_DIRECTIONS = ("pick_left_dest_right", "pick_right_dest_left")


@dataclass(kw_only=True)
class HandoffTaskConfig(BaseTaskConfig):
    """Configuration for generating handoff tasks (bimanual).

    One arm grasps an object, lifts it to a handoff point, the other arm
    receives it mid-air, then places it at a destination. The pick object
    spawns on one side and the destination on the opposite side.
    """

    pick_object: str = "bottled_drink"
    dest_object: str = "tray"
    dest_region: str = "on"
    # Direction of the handoff. "pick_left_dest_right" (default, back-compat):
    # pick spawns left, dest spawns right, left arm grasps then right arm
    # receives. "pick_right_dest_left": mirrored — pick spawns right, dest
    # spawns left, right arm grasps then left arm receives.
    direction: str = "pick_left_dest_right"
    key: str = "handoff"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.direction not in HANDOFF_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {HANDOFF_DIRECTIONS}, got '{self.direction}'"
            )


@register_task("handoff", config_cls=HandoffTaskConfig)
class HandoffTask(BaseTask):
    def __init__(self, config: HandoffTaskConfig) -> None:
        super().__init__(config=config)

        self._direction = config.direction
        if self._direction == "pick_left_dest_right":
            pick_side, dest_side = "left", "right"
            self._first_grasp = "grasp_left"
            self._second_grasp = "grasp_right"
        else:
            pick_side, dest_side = "right", "left"
            self._first_grasp = "grasp_right"
            self._second_grasp = "grasp_left"

        pick_object = get_grasp_object_spec(config.pick_object)
        self._pick_object: GraspObjectSpec = make_named_grasp_object_spec(
            "object_0", pick_object
        )
        self._pick_object.spawn_region = pick_side

        dest_object = get_dest_object_spec(config.dest_object)
        self._dest_object: DestObjectSpec = make_named_dest_object_spec(
            "dest_object", dest_object
        )
        self._dest_object.spawn_region = dest_side

        self._dest_region = config.dest_region

    def build_task_objects(
        self,
    ) -> Tuple[List[GraspObjectSpec], List[DestObjectSpec], List[ArticulatedObjectSpec]]:
        return [self._pick_object], [self._dest_object], []

    def build_goal_state(self) -> List[object]:
        assert self._pick_object.id is not None
        assert self._dest_object.id is not None
        if self._dest_region == "on":
            return ["and", ["on", self._pick_object.id, self._dest_object.id]]
        contain_region_name = f"{self._dest_object.id}_{self._dest_region}"
        return ["and", ["in", self._pick_object.id, contain_region_name]]

    def build_demonstration_states(self) -> List[list]:
        assert self._pick_object.id is not None
        assert self._dest_object.id is not None
        steps: List[list] = [
            [self._first_grasp, self._pick_object.id],
            ["lifted", self._pick_object.id],
            [self._second_grasp, self._pick_object.id],
        ]
        if self._dest_region == "on":
            steps.append(["on", self._pick_object.id, self._dest_object.id])
        else:
            contain_region_name = f"{self._dest_object.id}_{self._dest_region}"
            steps.append(["in", self._pick_object.id, contain_region_name])
        return steps
