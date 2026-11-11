"""Load and validate .dex.json sidecar files for bimanual arm assignments."""

import json
import os


def load_dex_sidecar(variant_path):
    """
    Load the dex sidecar JSON for a given BDDL variant.

    Resolves ``<stem>.dex.json`` next to the variant file.

    Args:
        variant_path (str): path to BDDL variant file (e.g. ``.../train/000.json``)

    Returns:
        sidecar (dict): parsed sidecar contents with ``arm_assignment_options``
            and ``subtask_dependencies`` keys
    """
    stem, _ = os.path.splitext(variant_path)
    sidecar_path = stem + ".dex.json"
    if not os.path.exists(sidecar_path):
        raise FileNotFoundError(
            f"Dex sidecar not found at {sidecar_path}. "
            f"Expected a file matching <variant>.dex.json next to the BDDL variant."
        )
    with open(sidecar_path, "r") as f:
        return json.load(f)


def _validate_single_arm_assignment(assignments, num_subtasks):
    """
    Validate a single arm assignment dict.

    Rules:
    - ``assignments`` must have exactly ``left`` and ``right`` keys.
    - Values are lists of integer indices into demonstration_states.
    - Left and right sets may overlap (e.g. coordination tasks).
    - Their union must cover ``range(num_subtasks)`` exactly.
    - All indices must be in ``[0, num_subtasks)``.

    Args:
        assignments (dict): ``{"left": [...], "right": [...]}``
        num_subtasks (int): total number of subtasks (len of demonstration_states)

    Raises:
        ValueError: if any rule is violated
    """
    if set(assignments.keys()) != {"left", "right"}:
        raise ValueError(
            f"arm_assignments must have exactly 'left' and 'right' keys, "
            f"got {sorted(assignments.keys())}"
        )

    left = assignments["left"]
    right = assignments["right"]

    if not isinstance(left, list) or not isinstance(right, list):
        raise ValueError("arm_assignments values must be lists of integers")

    left_set = set(left)
    right_set = set(right)

    if len(left_set) != len(left):
        raise ValueError(f"left arm_assignments contains duplicate indices: {left}")
    if len(right_set) != len(right):
        raise ValueError(f"right arm_assignments contains duplicate indices: {right}")

    union = left_set | right_set
    expected = set(range(num_subtasks))
    if union != expected:
        missing = expected - union
        extra = union - expected
        parts = []
        if missing:
            parts.append(f"missing {sorted(missing)}")
        if extra:
            parts.append(f"extra {sorted(extra)}")
        raise ValueError(
            f"arm_assignments must cover exactly [0, {num_subtasks}): {', '.join(parts)}"
        )

    for label, indices in [("left", left), ("right", right)]:
        for idx in indices:
            if not isinstance(idx, int) or idx < 0 or idx >= num_subtasks:
                raise ValueError(
                    f"{label} assignment index {idx} out of range [0, {num_subtasks})"
                )


def validate_arm_assignment_options(options, num_subtasks):
    """Validate a list of arm assignment options from a dex sidecar.

    Each option must be a valid arm assignment (see ``_validate_single_arm_assignment``).
    The list must contain at least one option.

    Args:
        options (list[dict]): list of ``{"left": [...], "right": [...]}`` dicts
        num_subtasks (int): total number of subtasks

    Raises:
        ValueError: if any rule is violated
    """
    if not isinstance(options, list) or len(options) == 0:
        raise ValueError("arm_assignment_options must be a non-empty list")
    for i, option in enumerate(options):
        try:
            _validate_single_arm_assignment(option, num_subtasks)
        except ValueError as e:
            raise ValueError(f"arm_assignment_options[{i}]: {e}") from e


def validate_subtask_dependencies(subtask_dependencies, num_subtasks):
    """Validate a per-subtask dependency DAG from a dex sidecar.

    Rules:
    - ``subtask_dependencies`` must be a dict.
    - Keys are subtask indices (string-encoded ints, as required by JSON).
    - Values are lists of prerequisite subtask indices (ints).
    - All indices must be in ``[0, num_subtasks)``.
    - No self-dependencies.
    - The dependency graph must be acyclic.

    Args:
        subtask_dependencies (dict): e.g. ``{"1": [0], "3": [2]}``
        num_subtasks (int): total number of subtasks

    Raises:
        ValueError: if any rule is violated
    """
    if not isinstance(subtask_dependencies, dict):
        raise ValueError("subtask_dependencies must be a dict")

    normalized = {}
    for k, v in subtask_dependencies.items():
        try:
            ki = int(k)
        except (ValueError, TypeError):
            raise ValueError(
                f"subtask_dependencies key '{k}' is not a valid integer index"
            )
        if ki < 0 or ki >= num_subtasks:
            raise ValueError(
                f"subtask_dependencies key {ki} out of range [0, {num_subtasks})"
            )
        if not isinstance(v, list):
            raise ValueError(
                f"subtask_dependencies['{k}'] must be a list of integers"
            )
        deps = []
        for dep in v:
            if not isinstance(dep, int) or dep < 0 or dep >= num_subtasks:
                raise ValueError(
                    f"subtask_dependencies['{k}'] contains invalid index {dep!r}; "
                    f"must be int in [0, {num_subtasks})"
                )
            if dep == ki:
                raise ValueError(
                    f"subtask_dependencies['{k}'] contains a self-dependency"
                )
            deps.append(dep)
        normalized[ki] = deps

    # Cycle detection via DFS coloring: 0=unvisited, 1=in-stack, 2=done
    adj = {i: [] for i in range(num_subtasks)}
    for node, deps in normalized.items():
        for dep in deps:
            adj[dep].append(node)

    color = [0] * num_subtasks

    def dfs(u):
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                raise ValueError(
                    f"subtask_dependencies contains a cycle involving "
                    f"subtask {u} -> {v}"
                )
            if color[v] == 0:
                dfs(v)
        color[u] = 2

    for i in range(num_subtasks):
        if color[i] == 0:
            dfs(i)
