from __future__ import annotations

import abc
import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Type

import numpy as np
from tqdm import trange

from mesa.sim.envs.arenas.style import ALL_TYPES, get_num_styles, get_style_from_index
from mesa.sim.envs.objects import (
    GRASPABLE_OBJECTS_DICT,
    IN_OBJECTS_DICT,
    ON_OBJECTS_DICT,
)
from mesa.utils.camera_specs import (
    EGOCENTRIC_CAMERA_PARAMETERS,
    MIDSHOULDER_CAMERA_PARAMETERS,
)

from .arenas import ARENAS, ArenaSpec
from .object_categories import (
    ARTICULATED_OBJECTS,
    CONFUSING_OBJECTS_LIST,
    DEST_OBJECTS,
    GRASP_OBJECTS,
    ArticulatedObjectSpec,
    DestObjectSpec,
    GraspObjectSpec,
    ObjectSpec,
    get_articulated_object_spec,
    get_dest_object_spec,
    get_grasp_object_spec,
)
from .utils import (
    camelize_instruction,
    get_num_to_place,
    make_region_dict,
    resolve_object_key,
    search_by_regex,
    workspace_name_for_problem,
)

DEFAULT_CAMERA_PARAMETERS = {
    "rightshoulder": {
        "r": 1.2,
        "theta": np.pi / 3,
        "phi": np.pi / 2,
        "r_radius": 0.15,
        "theta_radius": 0.15,
        "phi_radius": np.pi / 2,
    },
    "leftshoulder": {
        "r": 1.2,
        "theta": np.pi / 3,
        "phi": -np.pi / 2,
        "r_radius": 0.15,
        "theta_radius": 0.15,
        "phi_radius": np.pi / 2,
    },
    "midshoulder": copy.deepcopy(MIDSHOULDER_CAMERA_PARAMETERS),
    "egocentric": copy.deepcopy(EGOCENTRIC_CAMERA_PARAMETERS),
}

# Large flat surfaces; three or more exhaust the placer, so distractors of these
# categories are capped in _add_distractors.
LARGE_FLAT_GRASP_OBJECTS = {"plate", "plate_ai"}
LARGE_FLAT_DEST_OBJECTS = {
    "pan", "pan_ai", "cutting_board", "cutting_board_ai",
    "tray", "tray_ai", "baking_sheet_ai",
}


@dataclass(kw_only=True)
class BaseTaskConfig:
    """Shared configuration values across all task generators."""

    # The natural language instruction for the task.
    language_instruction: str
    # The name of the task suite folder where this should be stored.
    task_suite_name: str = "debug"
    # unique identifier for the task within the task suite.
    task_id: Optional[str] = None
    # Whether to make the source variants.
    make_source: bool = False
    # Number of source variants. None -> cover all assets (get_num_source_variants);
    # an int overrides that and round-robins assets via variant_index % num_assets.
    num_source_variants: Optional[int] = None
    # The number of train variants to generate.
    num_train_variants: int = 0
    # The number of eval variants to generate.
    num_eval_variants: int = 0
    # First train/eval variant index (also the {idx:03d}.json name); lets you append
    # variants without overwriting existing ones. Does not affect source variants.
    variant_start: int = 0
    # The directory where the task suite will be stored.
    output_dir: str = "mesa/task_suites/bddl_files"
    # The name of the arena to use for the task.
    arena_name: str = "mimiclabs_lab1_tabletop_manipulation"
    # Asset format to sample objects from: "mesa" (single-arm) or "bimesa" (dual-arm YAM).
    object_format: str = "mesa"
    # The name of the class of the task. This should be overridden by the subclass and left alone
    key: Optional[str] = None
    # Whether to randomize the table, floor, and wall textures.
    randomize_style: bool = False
    # Whether to randomize camera positions.
    randomize_camera: bool = False
    
    # Whether to add distractors to the task. If False, the min/max number of objects and destinations will be ignored.
    add_distractors: bool = False
    # Also add distractors to source variants. Needed for raw-path tasks (handoff,
    # articulated) where the source demo IS the training demo. Requires add_distractors.
    source_add_distractors: bool = False
    # The minimum and maximum number of objects to place in the task.
    min_num_objects: int = 4
    max_num_objects: int = 4
    # The minimum and maximum number of destinations to place in the task.
    min_num_dests: int = 1
    max_num_dests: int = 2
    # The minimum and maximum number of articulated objects to place in the task.
    min_num_articulated: int = 1
    max_num_articulated: int = 1
    # Shorthand: constrain pick, dest, and fixture to the same side (sets the three
    # per-role fields below; mutually exclusive with them). One of left/right/center/
    # alternate/spatial-right. "alternate" flips by variant index; "spatial-right" keeps
    # y in [0, 0.3], reserving the far edge [0.3, 0.4] for the spatial OOD eval.
    constrain_side: Optional[str] = None
    # Per-role side constraints (same values); distractors stay on full_table.
    constrain_pick_side: Optional[str] = None
    constrain_dest_side: Optional[str] = None
    # Place the fixture on a different side than the pick object.
    fixture_side: Optional[str] = None
    # Exclude *_mirror fixtures when sampling new BDDLs. Default True keeps fresh
    # generation mirror-free (the shipped convention); the classes stay registered
    # so historical mirror-bearing BDDLs still load. Opt in to sample mirrors.
    exclude_mirror_fixtures: bool = True

    def __post_init__(self) -> None:
        assert self.key is not None, "Task key must be overridden by the subclass"
        allowed_sides = ("left", "right", "center", "alternate", "spatial-right")
        for field_name, value in (
            ("constrain_side", self.constrain_side),
            ("constrain_pick_side", self.constrain_pick_side),
            ("constrain_dest_side", self.constrain_dest_side),
            ("fixture_side", self.fixture_side),
        ):
            if value is not None and value not in allowed_sides:
                raise ValueError(
                    f"{field_name} must be one of {allowed_sides}, got '{value}'"
                )

        per_role_set = (
            self.constrain_pick_side is not None
            or self.constrain_dest_side is not None
            or self.fixture_side is not None
        )
        if self.constrain_side is not None and per_role_set:
            raise ValueError(
                "constrain_side is a back-compat shorthand and cannot be combined with "
                "constrain_pick_side / constrain_dest_side / fixture_side."
            )

        if self.constrain_side is not None:
            self.constrain_pick_side = self.constrain_side
            self.constrain_dest_side = self.constrain_side
            self.fixture_side = self.constrain_side


@dataclass(frozen=True)
class TaskRegistration:
    """Registry metadata binding a task key to its implementation and config."""

    key: str
    task_cls: Type["BaseTask"]
    config_cls: Type[BaseTaskConfig]


TASK_REGISTRY: Dict[str, TaskRegistration] = {}


def register_task(key: str, *, config_cls: Type[BaseTaskConfig]) -> Callable[[Type["BaseTask"]], Type["BaseTask"]]:
    """Decorator used by task subclasses to register themselves for CLI instantiation."""

    def decorator(task_cls: Type["BaseTask"]) -> Type["BaseTask"]:
        if key in TASK_REGISTRY:
            existing = TASK_REGISTRY[key]
            raise ValueError(
                f"Task key '{key}' is already registered to {existing.task_cls.__name__}. "
                f"Cannot register {task_cls.__name__}."
            )
        TASK_REGISTRY[key] = TaskRegistration(key=key, task_cls=task_cls, config_cls=config_cls)
        setattr(task_cls, "task_key", key)
        setattr(task_cls, "config_cls", config_cls)
        return task_cls

    return decorator


def get_task_registration(key: str) -> TaskRegistration:
    """Retrieve the registration for a task key, raising if it does not exist."""

    try:
        return TASK_REGISTRY[key]
    except KeyError as exc:
        available = ", ".join(sorted(TASK_REGISTRY))
        raise KeyError(f"Unknown task key '{key}'. Available keys: {available}") from exc


def available_task_keys() -> List[str]:
    """Return all registered task keys sorted for stable presentation."""

    return sorted(TASK_REGISTRY)


def instantiate_task(config: BaseTaskConfig) -> "BaseTask":
    """Instantiate a registered task using the provided configuration."""

    registration = get_task_registration(config.key)
    if not isinstance(config, registration.config_cls):
        raise TypeError(
            f"Configuration for task '{config.key}' must be an instance of {registration.config_cls.__name__}, "
            f"received {type(config).__name__}."
        )
    return registration.task_cls(config=config)


class BaseTask(abc.ABC):
    """Generic base class for task generation.

    This class orchestrates the common generation flow used by task generators
    like the registered pick-and-place or open-fixture tasks, while leaving task-specific
    logic (object selection, region construction, initial/goal/demo states) to
    subclasses via abstract hooks.

    High-level responsibilities handled here:
    - Selecting environment problem names and retrieving the workspace name
    - Tokenizing language instructions
    - Common utilities for rectangular regions and grids
    - Assembling the problem dict structure shared across tasks
    - Writing source and variant problems to disk

    Subclasses must implement the abstract methods to provide task-specific
    behaviors.
    """

    def __init__(
        self, 
        config: BaseTaskConfig,
    ) -> None:
        self.config: BaseTaskConfig = config
        self.task_suite_name: str = config.task_suite_name
        self.language_instruction_text: str = config.language_instruction
        self.task_id: str = config.task_id if config.task_id is not None else self.language_instruction_text.replace(" ", "_").lower()
        self.num_train_variants: int = int(config.num_train_variants)
        self.num_eval_variants: int = int(config.num_eval_variants)
        self.variant_start: int = int(config.variant_start)
        self.output_dir: str = config.output_dir
        self.make_source: bool = bool(config.make_source)
        self.arena_spec: ArenaSpec = ARENAS[config.arena_name]
        self.randomize_style: bool = config.randomize_style
        self.randomize_camera: bool = config.randomize_camera

        # Persistent configuration (subclasses may override/mutate as needed)
        self.textures: Dict[str, object] = {}
        self.lighting: Dict[str, object] = {}
        self.scene_properties: Dict[str, object] = {}

        self.add_distractors = config.add_distractors
        self.source_add_distractors = config.source_add_distractors
        self.num_objects = (config.min_num_objects, config.max_num_objects)
        self.num_dests = (config.min_num_dests, config.max_num_dests)
        self.num_articulated = (config.min_num_articulated, config.max_num_articulated)
        self.constrain_pick_side = config.constrain_pick_side
        self.constrain_dest_side = config.constrain_dest_side
        self.fixture_side = config.fixture_side
        self.num_source_variants_override: Optional[int] = config.num_source_variants

        if self.source_add_distractors and not self.add_distractors:
            raise ValueError(
                "source_add_distractors=True requires add_distractors=True."
            )


    # ---------- Orchestration API ----------

    def generate(
        self,
        verbose: bool = True,
        valid_distractor_map: Optional[Dict[str, Dict[str, List[str]]]] = None,
        seed: Optional[int] = None,
    ) -> None:
        """
        Generate problem variants as specified by the task configuration.
        """
        if valid_distractor_map is None:
            valid_distractor_map = self._default_valid_distractor_map(self.config.object_format)
        resolved_seed = hash(self.language_instruction_text) % (2 ** 32) if seed is None else seed

        if verbose:
            print('-' * 100)
            print(f"Generating task {self.task_id} with the following instruction: {self.language_instruction_text}")
            print(f"Adding distractors: {self.add_distractors}")
            if self.add_distractors:
                print(f"Min num objects: {self.num_objects[0]}, Max num objects: {self.num_objects[1]}")
                print(f"Min num destinations: {self.num_dests[0]}, Max num destinations: {self.num_dests[1]}")
                print(f"Min num articulated: {self.num_articulated[0]}, Max num articulated: {self.num_articulated[1]}")
            print(f"Save directory: {self._problem_dir()}")
            print('-' * 100)

        source_problem_name = self.arena_spec.source_problem_name
        source_workspace_name = workspace_name_for_problem(source_problem_name)

        problem_dir = self._problem_dir()
        train_dir = problem_dir / "train"
        eval_dir = problem_dir / "eval"
        if self.num_train_variants > 0:
            train_dir.mkdir(parents=True, exist_ok=True)
        if self.num_eval_variants > 0:
            eval_dir.mkdir(parents=True, exist_ok=True)

        if self.num_train_variants == self.num_eval_variants == 0 and not self.make_source:
            raise ValueError("At least one of num_train_variants, num_eval_variants, or make_source must be non-zero, or this script will do nothing.")
        
        # Build SOURCE problem
        if self.make_source:
            source_dir = problem_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            for i in trange(self.get_num_source_variants(), desc="Building source problems", disable=not verbose):
                source_problem_dict = self._build_problem_dict(
                    problem_name=source_problem_name,
                    workspace_name=source_workspace_name,
                    source=True,
                    variant_index=i,
                    valid_distractor_map=valid_distractor_map,
                    seed=resolved_seed,
                )

                self._write_problem(source_dir / f"{i:03d}.json", source_problem_dict)

        # Build VARIANTS
        dirs = [train_dir, eval_dir]
        num_variants = [self.num_train_variants, self.num_eval_variants]
        for seed_offset, (variant_dir, num_variants) in enumerate(zip(dirs, num_variants)):
            for j in trange(num_variants, desc="Building variant problems", disable=not verbose):
                i = self.variant_start + j
                variant_problem_name = self._select_variant_problem_name(i)
                variant_workspace_name = workspace_name_for_problem(variant_problem_name)
                variant_problem_dict = self._build_problem_dict(
                    problem_name=variant_problem_name,
                    workspace_name=variant_workspace_name,
                    source=False,
                    variant_index=i,
                    valid_distractor_map=valid_distractor_map,
                    seed=resolved_seed + seed_offset,
                )

                self._write_problem(variant_dir / f"{i:03d}.json", variant_problem_dict)

    # ---------- Common problem assembly ----------

    def _build_problem_dict(
        self,
        *,
        problem_name: str,
        workspace_name: str,
        source: bool,
        variant_index: int,
        valid_distractor_map: Dict[str, Dict[str, List[str]]],
        seed: int,
    ) -> Dict[str, object]:
        """This is the main method that builds the dictionary for a particular variant."""
        objects, dests, articulateds = self.build_task_objects()

        # Counts so side constraints touch only task objects, not distractors.
        num_task_objects = len(objects)
        num_task_dests = len(dests)
        num_task_articulateds = len(articulateds)

        add_distractors_now = self.add_distractors and (
            (not source) or self.source_add_distractors
        )
        if add_distractors_now:
            objects, dests, articulateds = self._add_distractors(
                variant_index,
                objects,
                dests,
                articulateds,
                valid_distractor_map,
                seed,
            )

        objects = self.resolve_objects(objects, variant_index, source, seed)
        dests = self.resolve_objects(dests, variant_index, source, seed)
        articulateds = self.resolve_objects(articulateds, variant_index, source, seed)

        fixtures_map = self._build_fixtures_map(articulateds, workspace_name)
        objects_map = self._build_objects_map(objects + dests)

        # Distractors keep full_table; only task objects take a side.
        pick_side = self._resolve_side(self.constrain_pick_side, variant_index)
        dest_side = self._resolve_side(self.constrain_dest_side, variant_index)
        fixture_side = self._resolve_side(self.fixture_side, variant_index)
        self._apply_side_to_specs(objects[:num_task_objects], pick_side)
        self._apply_side_to_specs(dests[:num_task_dests], dest_side)
        self._apply_side_to_specs(articulateds[:num_task_articulateds], fixture_side)

        placements = [self._spec_to_placement(spec) for spec in objects + dests + articulateds]

        relevant_regions = []
        for spec in objects + dests + articulateds:
            relevant_regions.extend(self._spec_to_relevant_regions(spec))

        initial_state = self.build_initial_state()

        regions, initial_state_placements = self._compute_regions_and_initial_state(
            placements=placements,
            workspace_name=workspace_name,
            relevant_regions=relevant_regions,
        )

        for placement_state in initial_state_placements:
            placed_object = placement_state[1]
            no_overlap = True
            for initial_state_object in initial_state:
                if initial_state_object[1] == placed_object and initial_state_object[0] in ("on", "in"):
                    no_overlap = False
                    break
            if no_overlap:
                initial_state.append(placement_state)

        styles = self._build_styles_map(variant_index=variant_index, source=source, seed=seed)
        
        goal_state = self.build_goal_state()
        demonstration_states = self.build_demonstration_states()
        distractor_goal_specs = self._build_distractor_goal_specs(
            objects + dests,
            articulateds,
            goal_state,
        )

        # Auto-create any region a distractor goal references but that isn't placed yet
        # (region name is "{object_id}_{suffix}").
        all_spec_ids = {spec.id: spec for spec in objects + dests + articulateds}
        for spec in distractor_goal_specs:
            if spec[0] == "in":
                region_name = spec[2]
                if region_name not in regions:
                    parent_id = next(
                        (sid for sid in all_spec_ids if region_name.startswith(sid + "_")),
                        None,
                    )
                    if parent_id is not None:
                        regions[region_name] = {
                            "target": parent_id,
                            "ranges": [],
                            "extra": [],
                            "yaw_rotation": [0, 0],
                            "rgba": [0, 0, 1, 0],
                        }

        problem = {
            "problem_name": problem_name,
            "fixtures": fixtures_map,
            "regions": regions,
            "objects": objects_map,
            "textures": self.textures,
            "camera": self._build_camera_map(),
            "lighting": self.lighting,
            "styles": styles,
            "scene_properties": self.scene_properties,
            "initial_state": initial_state,
            "goal_state": goal_state,
            "distractor_goal_specs": distractor_goal_specs,
            "demonstration_states": demonstration_states,
            "language_instruction": camelize_instruction(self.language_instruction_text),
        }

        return problem

    @staticmethod
    def _resolve_side(side_value: Optional[str], variant_index: int) -> Optional[str]:
        if side_value is None:
            return None
        if side_value == "alternate":
            return "left" if variant_index % 2 == 0 else "right"
        return side_value

    @staticmethod
    def _apply_side_to_specs(specs: Sequence[ObjectSpec], side: Optional[str]) -> None:
        if side is None:
            return
        for spec in specs:
            if spec.spawn_region == "full_table":
                spec.spawn_region = side
            elif spec.spawn_region == "back" and side in (
                "left", "right", "spatial-right", "center"
            ):
                spec.spawn_region = f"back-{side}"

    # ---------- Abstract task-specific hooks ----------

    @abc.abstractmethod
    def build_goal_state(
        self,
    ) -> List[object]:
        """Return the goal state predicates for the task."""

    @abc.abstractmethod
    def build_demonstration_states(
        self,
    ) -> List[list]:
        """Return a sequence of demonstration predicates for the task."""

    # ---------- Optional hooks with defaults ----------

    def build_task_objects(
        self,
    ) -> Tuple[List[GraspObjectSpec], List[DestObjectSpec], List[ArticulatedObjectSpec]]:
        """Return task-relevant object specs for this task."""
        return [], [], []

    def build_initial_state(
        self,
    ) -> List[list]:
        """
        Return any task-specific parts of the initial state. Object placement is handled by the superclass
        but can be overridden by this method.
        """
        return []

    def get_num_source_variants(self) -> int:
        """
        Return the number of source variants for the task. This should be the
        number of variants necessary to sufficiently cover all the possible object
        variants. For example, if your task is ``put the apple on the plate'' and there
        are 14 apple assets, you should return 14.

        Overridden by config.num_source_variants when set.
        """
        if self.num_source_variants_override is not None:
            return int(self.num_source_variants_override)
        objects, dests, articulateds = self.build_task_objects()
        all_needing_variance = objects + dests
        num_per_object = [len(search_by_regex(object.search_pattern, self.config.object_format)) for object in all_needing_variance]
        if len(num_per_object) == 0:
            return 1
        return max(num_per_object)

    # ---------- Environment selection ----------

    def _select_variant_problem_name(self, variant_index: int) -> str:
        num_variants = len(self.arena_spec.variant_problem_names)
        return self.arena_spec.variant_problem_names[variant_index % num_variants]

    # ---------- Placement helpers and derived structures ----------

    def resolve_objects(self, objects: List[ObjectSpec], variant_index: int, source: bool, seed: int) -> List[ObjectSpec]:
        resolved_objects = []
        for i, object_spec in enumerate(objects):
            object_spec = copy.deepcopy(object_spec)
            if object_spec.id is None:
                object_spec.id = f'{object_spec.name}_{i}'
            if object_spec.key is None:
                object_spec.key = resolve_object_key(
                    object_spec.search_pattern, variant_index, source, seed,
                    exclude_mirror=self.config.exclude_mirror_fixtures,
                    object_format=self.config.object_format,
                )
            resolved_objects.append(object_spec)
        return resolved_objects

    def _add_distractors(
        self, 
        variant_index: int, 
        placed_objects: List[GraspObjectSpec], 
        placed_dests: List[DestObjectSpec],
        placed_articulateds: List[ArticulatedObjectSpec],
        valid_distractor_map: Dict[str, Dict[str, List[str]]],
        seed: int,
    ) -> Tuple[List[GraspObjectSpec], List[DestObjectSpec], List[ArticulatedObjectSpec]]:
        rng = random.Random(seed + variant_index)
        num_objects = get_num_to_place(self.num_objects, rng)
        num_dests = get_num_to_place(self.num_dests, rng)
        num_articulated = get_num_to_place(self.num_articulated, rng)

        # Don't mutate the original lists
        placed_objects = copy.deepcopy(placed_objects)
        placed_dests = copy.deepcopy(placed_dests)
        placed_articulateds = copy.deepcopy(placed_articulateds)


        while len(placed_objects) < num_objects or len(placed_dests) < num_dests:

            if len(placed_objects) < num_objects:
                valid_object_distractors = []
                filtered_objects = self._build_distractor_filter(placed_objects + placed_dests + placed_articulateds)

                for placed_dest in placed_dests:
                    valid_objects = valid_distractor_map['dest_to_object_map'].get(placed_dest.name, [])
                    for object_name in valid_objects:
                        if object_name not in filtered_objects:
                            valid_object_distractors.append(object_name)
                for placed_articulated in placed_articulateds:
                    valid_objects = valid_distractor_map['articulated_to_object_map'].get(placed_articulated.name, [])
                    for object_name in valid_objects:
                        if object_name not in filtered_objects:
                            valid_object_distractors.append(object_name)
                
                if len(valid_object_distractors) == 0:
                    for potential_object_name in valid_distractor_map["all_object"]:
                        if potential_object_name not in filtered_objects:
                            valid_object_distractors.append(potential_object_name)
                
                new_object_name = rng.choice(valid_object_distractors)
                new_object_spec = get_grasp_object_spec(new_object_name)
                placed_objects.append(new_object_spec)

                # plate is a special case because it is very large
                if new_object_name == 'plate':
                    num_dests -= 1

            if len(placed_dests) < num_dests:
                valid_dest_distractors = []
                filtered_objects = self._build_distractor_filter(placed_objects + placed_dests + placed_articulateds)

                for placed_object in placed_objects:
                    valid_dests = valid_distractor_map['object_to_dest_map'].get(placed_object.name, [])
                    for dest_name in valid_dests:
                        if dest_name not in filtered_objects:
                            valid_dest_distractors.append(dest_name)

                if len(valid_dest_distractors) == 0:
                    for potential_dest_name in valid_distractor_map["all_dest"]:
                        if potential_dest_name not in filtered_objects:
                            valid_dest_distractors.append(potential_dest_name)

                # Cap large flat surfaces: once two are placed, prefer a smaller dest.
                large_flat_count = (
                    sum(1 for s in placed_objects if s.name in LARGE_FLAT_GRASP_OBJECTS)
                    + sum(1 for s in placed_dests if s.name in LARGE_FLAT_DEST_OBJECTS)
                )
                if large_flat_count >= 2:
                    smaller = [d for d in valid_dest_distractors if d not in LARGE_FLAT_DEST_OBJECTS]
                    if smaller:
                        valid_dest_distractors = smaller

                new_dest_name = rng.choice(valid_dest_distractors)
                new_dest_spec = get_dest_object_spec(new_dest_name)
                placed_dests.append(new_dest_spec)
        

        if len(placed_articulateds) < num_articulated:
            valid_articulated_dests = []
            filtered_objects = self._build_distractor_filter(placed_objects + placed_dests + placed_articulateds)

            for placed_object in placed_objects + placed_dests:
                valid_articulateds = valid_distractor_map['object_to_articulated_map'].get(placed_object.name, [])
                for articulated_name in valid_articulateds:
                    if articulated_name not in filtered_objects:
                        valid_articulated_dests.append(articulated_name)

            if len(valid_articulated_dests) == 0:
                valid_articulated_dests = valid_distractor_map["all_articulated"]

            new_articulated_name = rng.choice(valid_articulated_dests)
            new_articulated_spec = get_articulated_object_spec(new_articulated_name)
            placed_articulateds.append(new_articulated_spec)

        return placed_objects, placed_dests, placed_articulateds


    def _build_distractor_goal_specs(
        self, 
        all_object_specs: List[ObjectSpec], 
        articulated_specs: List[ArticulatedObjectSpec],
        goal_state: List[object],
    ) -> List[list]:
        in_objects: List[ObjectSpec] = []
        on_objects: List[ObjectSpec] = []
        graspable_objects: List[ObjectSpec] = []
        goal_state_tuples = [tuple(state) for state in goal_state]

        for object_spec in all_object_specs:
            assert object_spec.key is not None, "You must resolve the objects before building the distractor goal specs"
            if object_spec.key in IN_OBJECTS_DICT:
                in_objects.append(object_spec)
            if object_spec.key in ON_OBJECTS_DICT:
                on_objects.append(object_spec)
            if object_spec.key in GRASPABLE_OBJECTS_DICT:
                graspable_objects.append(object_spec)
        for articulated_spec in articulated_specs:
            if articulated_spec.key in IN_OBJECTS_DICT:
                in_objects.append(articulated_spec)

        distractor_goal_specs = []
        for grasp_object in graspable_objects:
            for in_object in in_objects:
                in_regions = IN_OBJECTS_DICT[in_object.key]["regions"]
                for region_name in in_regions:
                    spec = ["in", grasp_object.id, f'{in_object.id}_{region_name}']
                    if tuple(spec) not in goal_state_tuples:
                        distractor_goal_specs.append(spec)
            for on_object in on_objects:
                spec = ["on", grasp_object.id, on_object.id]
                if tuple(spec) not in goal_state_tuples:
                    distractor_goal_specs.append(spec)

        return distractor_goal_specs

    def _compute_regions_and_initial_state(
        self,
        *,
        placements: List[Tuple[str, Tuple[float, float, float, float], Tuple[float, float]]],
        workspace_name: str,
        relevant_regions: List[Tuple[str, str]],
    ) -> Tuple[Dict[str, dict], List[list]]:
        regions: Dict[str, dict] = {}
        initial_state: List[list] = []
        for obj_name, (x_min, x_max, y_min, y_max), (yaw_min, yaw_max) in placements:
            region_key, reg = make_region_dict(
                region_name=f"{obj_name}_init_region",
                target=workspace_name,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                yaw_rotation_min=yaw_min,
                yaw_rotation_max=yaw_max,
            )
            regions[region_key] = reg
            initial_state.append(["on", obj_name, region_key])
        
        for obj_name, region_name in relevant_regions:
            regions[region_name] = {
                "target": obj_name,
                "ranges": [],
                "extra": [],
                "yaw_rotation": [0, 0],
                "rgba": [0, 0, 1, 0],
            }
        return regions, initial_state

    def _build_distractor_filter(self, all_placed_objects: List[ObjectSpec]) -> set[str]:
        filtered_objects: set[str] = set()
        for object_spec in all_placed_objects:
            filtered_objects.add(object_spec.name)
            filtered_objects.update(CONFUSING_OBJECTS_LIST[object_spec.name])
        return filtered_objects

    @staticmethod
    def _default_valid_distractor_map(object_format: str = "mesa") -> Dict[str, Dict[str, List[str]]]:
        # Filter out categories with no matching assets in the current asset bundle.
        valid_grasp = [k for k, v in GRASP_OBJECTS.items() if search_by_regex(v.search_pattern, object_format)]
        valid_dest = [k for k, v in DEST_OBJECTS.items() if search_by_regex(v.search_pattern, object_format)]
        valid_articulated = [
            k for k, v in ARTICULATED_OBJECTS.items()
            if v.is_valid_distractor and search_by_regex(v.search_pattern, object_format)
        ]
        return {
            "object_to_dest_map": {},
            "dest_to_object_map": {},
            "object_to_articulated_map": {},
            "articulated_to_object_map": {},
            "all_object": valid_grasp,
            "all_dest": valid_dest,
            "all_articulated": valid_articulated,
        }

    def _spec_to_placement(
        self, 
        spec: ObjectSpec
    ) -> Tuple[str, Tuple[float, float, float, float], Tuple[float, float]]:
        assert spec.id is not None, "You must resolve the object names before building the placements"
        region = spec.spawn_region
        table_middle = (self.arena_spec.min_y + self.arena_spec.max_y) / 2
        if region == "full_table":
            region_bounds = (self.arena_spec.min_x, self.arena_spec.max_x, self.arena_spec.min_y, self.arena_spec.max_y)
        elif region == "left":
            region_bounds = (self.arena_spec.min_x, self.arena_spec.max_x, self.arena_spec.min_y, table_middle)
        elif region == "right":
            region_bounds = (self.arena_spec.min_x, self.arena_spec.max_x, table_middle, self.arena_spec.max_y)
        elif region == "spatial-right":
            region_bounds = (self.arena_spec.min_x, self.arena_spec.max_x, table_middle, self.arena_spec.max_y - 0.1)
        elif region == "center":
            center_y_half = 0.15
            region_bounds = (self.arena_spec.min_x, self.arena_spec.max_x, table_middle - center_y_half, table_middle + center_y_half)
        elif region == "back":
            region_bounds = (self.arena_spec.back_min_x, self.arena_spec.back_max_x, self.arena_spec.min_y, self.arena_spec.max_y)
        elif region == "back-left":
            region_bounds = (self.arena_spec.back_min_x, self.arena_spec.back_max_x, self.arena_spec.min_y, table_middle)
        elif region == "back-right":
            region_bounds = (self.arena_spec.back_min_x, self.arena_spec.back_max_x, table_middle, self.arena_spec.max_y)
        elif region == "back-center":
            center_y_half = 0.15
            region_bounds = (self.arena_spec.back_min_x, self.arena_spec.back_max_x, table_middle - center_y_half, table_middle + center_y_half)
        elif region == "back-spatial-right":
            region_bounds = (self.arena_spec.back_min_x, self.arena_spec.back_max_x, table_middle, self.arena_spec.max_y - 0.1)
        else:
            raise ValueError(f"Invalid spawn region: {region}")

        yaw_range = (0.0, 0.0) if not spec.allow_rotation else (-np.pi / 2, np.pi / 2)
        return (spec.id, region_bounds, yaw_range)
    
    def _spec_to_relevant_regions(self, spec: ObjectSpec) -> List[Tuple[str, str]]:
        if isinstance(spec, (ArticulatedObjectSpec, DestObjectSpec)):
            return [(spec.id, f'{spec.id}_{region_name}') for region_name in spec.regions]
        return []

    def _build_styles_map(self, variant_index: int, source: bool, seed: int) -> Dict[str, List[str]]:
        if source or not self.randomize_style:
            return {}
        
        rng = random.Random(seed + variant_index)

        styles: Dict[str, List[str]] = {}
        for type_name in ALL_TYPES.keys():
            num_styles = get_num_styles(type_name)
            style_idx = rng.randint(0, num_styles - 1)
            styles[type_name] = get_style_from_index(type_name, style_idx)
        return styles

    def _build_camera_map(self) -> Dict[str, Dict[str, float]]:
        camera_map = copy.deepcopy(DEFAULT_CAMERA_PARAMETERS)
        if not self.randomize_camera:
            for cam in camera_map.values():
                for radius_key in ("r_radius", "theta_radius", "phi_radius", "tilt_radius", "pan_radius"):
                    if radius_key in cam:
                        cam[radius_key] = 0.0
        return camera_map

    def _build_fixtures_map(
        self, 
        articulateds: Sequence[ArticulatedObjectSpec],
        workspace_name: str,
    ) -> Dict[str, List[str]]:
        fixtures: Dict[str, List[str]] = {
            workspace_name: [workspace_name],
        }
        for articulated in articulateds:
            assert articulated.id is not None and articulated.key is not None, "You must resolve the objects before building the fixtures map"
            fixtures[articulated.key] = [articulated.id]
        return fixtures

    def _build_objects_map(self, objects: Sequence[ObjectSpec]) -> Dict[str, List[str]]:
        objects_map: Dict[str, List[str]] = {}
        for object_spec in objects:
            assert object_spec.id is not None and object_spec.key is not None, "You must resolve the objects before building the objects map"
            # Two specs can resolve to the same asset key; append (not overwrite) so
            # neither instance id is dropped and left orphaned (KeyError at reset).
            objects_map.setdefault(object_spec.key, []).append(object_spec.id)
        return objects_map


    # ---------- I/O helpers ----------

    def _problem_dir(self) -> Path:
        assert ' ' not in self.task_id, f"Task ID cannot contain spaces: {self.task_id}"
        return Path(self.output_dir) / self.task_suite_name / self.task_id

    @staticmethod
    def _write_problem(path: Path, data: Mapping[str, object]) -> None:
        with open(path, "w") as f:
            json.dump(dict(data), f, indent=4)

