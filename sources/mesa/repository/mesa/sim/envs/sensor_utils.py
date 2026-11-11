import itertools
import re
from typing import Callable

import mujoco
import numpy as np
import robosuite.utils.camera_utils as cu
import robosuite.utils.transform_utils as T
from robosuite.utils.observables import sensor

import mesa.utils.vis_utils as vu


def create_object_pose_sensors(
    obj_name: str,
    obj_body_id: int,
    sim,
    modality: str = "object",
    robot_naming_prefix: str = "robot0",
) -> tuple[Callable, str]:
    """
    Helper function to create sensors for a given object. This is abstracted in a separate function call so that we
    don't have local function naming collisions during the _setup_observables() call.

    Args:
        obj_name (str): Name of object to create sensors for
        modality (str): Modality to assign to all sensors

    Returns:
        2-tuple:
            sensors (list): Array of sensors for the given obj
            names (list): array of corresponding observable names
    """
    pf = robot_naming_prefix

    @sensor(modality=modality)
    def obj_pos(obs_cache):
        return np.array(sim.data.body_xpos[obj_body_id])

    @sensor(modality=modality)
    def obj_quat(obs_cache):
        return T.convert_quat(
            sim.data.body_xquat[obj_body_id], to="xyzw"
        )

    @sensor(modality=modality)
    def obj_to_eef_pos(obs_cache):
        # Immediately return default value if cache is empty
        if any(
            [
                name not in obs_cache
                for name in [
                    f"{obj_name}_pos",
                    f"{obj_name}_quat",
                    "world_pose_in_gripper",
                ]
            ]
        ):
            return np.zeros(3)
        obj_pose = T.pose2mat(
            (obs_cache[f"{obj_name}_pos"], obs_cache[f"{obj_name}_quat"])
        )
        rel_pose = T.pose_in_A_to_pose_in_B(
            obj_pose, obs_cache["world_pose_in_gripper"]
        )
        rel_pos, rel_quat = T.mat2pose(rel_pose)
        obs_cache[f"{obj_name}_to_{pf}eef_quat"] = rel_quat
        return rel_pos

    @sensor(modality=modality)
    def obj_to_eef_quat(obs_cache):
        return (
            obs_cache[f"{obj_name}_to_{pf}eef_quat"]
            if f"{obj_name}_to_{pf}eef_quat" in obs_cache
            else np.zeros(4)
        )

    sensors = [obj_pos, obj_quat, obj_to_eef_pos, obj_to_eef_quat]
    names = [
        f"{obj_name}_pos",
        f"{obj_name}_quat",
        f"{obj_name}_to_{pf}eef_pos",
        f"{obj_name}_to_{pf}eef_quat",
    ]

    return sensors, names


def create_object_2d_bbox_sensor(
    obj_name: str,
    obj_body_id: int,
    sim,
    modality: str = "object",
    camera_name: list[str] = [],
    camera_height: list[int] = [],
    camera_width: list[int] = [],
):
    # Bounding box sensor
    sensor_name = f"{obj_name}_{camera_name}_2d_bbox"

    @sensor(modality=modality)
    def obj_bbox_2d(obs_cache):
        pts_world = _get_object_world_bbox_points(obj_body_id, sim)
        camera_transform_matrix = cu.get_camera_transform_matrix(sim, camera_name, camera_height, camera_width)
        pts_2d, valid = vu.project_points_to_image(
            pts_world, camera_transform_matrix, camera_height, camera_width
        )

        if valid.any():
            u = pts_2d[valid, 0]
            v = pts_2d[valid, 1]
            xmin_px = np.clip(np.min(u), 0, camera_width - 1)
            xmax_px = np.clip(np.max(u), 0, camera_width - 1)
            ymin_px = np.clip(np.min(v), 0, camera_height - 1)
            ymax_px = np.clip(np.max(v), 0, camera_height - 1)
            # Normalize to [0, 1] relative bbox (x/W, y/H)
            xmin = float(xmin_px) / float(camera_width)
            xmax = float(xmax_px) / float(camera_width)
            ymin = float(ymin_px) / float(camera_height)
            ymax = float(ymax_px) / float(camera_height)
            # Ensure in-range
            xmin = np.clip(xmin, 0.0, 1.0)
            xmax = np.clip(xmax, 0.0, 1.0)
            ymin = np.clip(ymin, 0.0, 1.0)
            ymax = np.clip(ymax, 0.0, 1.0)
            return np.array([xmin, ymin, xmax, ymax], dtype=np.float32)
        else:
            return np.array([-1.0, -1.0, -1.0, -1.0], dtype=np.float32)

    return obj_bbox_2d, sensor_name


def create_object_3d_bbox_sensor(
    obj_name: str,
    obj_body_id: int,
    sim,
    modality: str = "object",
):

    sensor_name = f"{obj_name}_3d_bbox"

    @sensor(modality=modality)
    def obj_bbox_3d(obs_cache):
        corners = _get_object_world_bbox_corners(obj_body_id, sim)
        if corners.size == 0:
            return np.zeros(24, dtype=np.float32)
        return corners.astype(np.float32).reshape(-1)

    return obj_bbox_3d, sensor_name


def create_object_segmentation_mask_sensor(
    obj_name: str,
    obj_body_id: int,
    sim,
    modality: str = "segmentation",
    camera_name: str = "",
    camera_height: int = 0,
    camera_width: int = 0,
):
    """
    Create a per-object segmentation mask sensor for a specific camera.

    The mask is 1 where a pixel belongs to any geom in the object's body subtree,
    and 0 otherwise.
    """
    sensor_name = f"{obj_name}_{camera_name}_segmentation_mask"
    geom_ids = None

    @sensor(modality=modality)
    def obj_segmentation_mask(obs_cache):
        nonlocal geom_ids

        if geom_ids is None:
            geom_ids = _get_object_geom_ids(obj_body_id, sim)

        if not geom_ids:
            return np.zeros((camera_height, camera_width), dtype=np.uint8)

        cache_key = f"{camera_name}_segmentation"
        if cache_key not in obs_cache:
            obs_cache[cache_key] = cu.get_camera_segmentation(
                sim, camera_name, camera_height, camera_width
            )

        seg = obs_cache[cache_key]
        geom_type = int(mujoco.mjtObj.mjOBJ_GEOM)
        mask = (seg[..., 0] == geom_type) & np.isin(seg[..., 1], geom_ids)
        return mask.astype(np.uint8)[..., None]

    return obj_segmentation_mask, sensor_name


def create_gripper_jaw_width_sensor(sim, pf="robot0"):
    _jaw_width_geom_ids = None  # type: ignore[var-annotated]
    _jaw_width_warned = False

    @sensor(modality="robot")
    def gripper_jaw_width(obs_cache):
        nonlocal _jaw_width_geom_ids, _jaw_width_warned

        if _jaw_width_geom_ids is None:
            geom_names = [
                n.decode("utf-8") if isinstance(n, (bytes, bytearray)) else str(n)
                for n in sim.model.geom_names
            ]

            def _pick_unique_geom_id(suffix: str) -> int | None:
                """
                Pick a geom id whose name ends with `suffix`.

                Prefer names containing the robot prefix `pf` (robosuite naming).
                """
                candidates = [
                    gid
                    for gid, name in enumerate(geom_names)
                    if name == suffix or name.endswith(suffix)
                ]
                if not candidates:
                    return None

                # Prefer geoms tied to the requested robot / gripper instance.
                # In bimanual setups, pad geoms are usually namespaced by "gripper{idx}_".
                preferred_tokens = [pf]
                m = re.search(r"(\d+)", pf)
                if m is not None:
                    idx = m.group(1)
                    preferred_tokens.append(f"robot{idx}_")
                    preferred_tokens.append(f"gripper{idx}_")

                preferred = [
                    gid
                    for gid in candidates
                    if any(token and token in geom_names[gid] for token in preferred_tokens)
                ]
                chosen = preferred if preferred else candidates
                if len(chosen) != 1:
                    # Ambiguous: multiple matching geoms (e.g., multiple robots).
                    # Returning None triggers NaN output and a one-time warning.
                    return None
                return chosen[0]

            pad_name_patterns = [
                ("left_pad1", "left_pad2", "right_pad1", "right_pad2"),  # Robotiq
                ("lf_pad1", "lf_pad2", "rf_pad1", "rf_pad2"),            # YAM
            ]

            _jaw_width_geom_ids = ()
            for left_1, left_2, right_1, right_2 in pad_name_patterns:
                left_pad1 = _pick_unique_geom_id(left_1)
                left_pad2 = _pick_unique_geom_id(left_2)
                right_pad1 = _pick_unique_geom_id(right_1)
                right_pad2 = _pick_unique_geom_id(right_2)
                if None not in (left_pad1, left_pad2, right_pad1, right_pad2):
                    _jaw_width_geom_ids = (left_pad1, left_pad2, right_pad1, right_pad2)
                    break

        if not _jaw_width_geom_ids:
            if not _jaw_width_warned:
                # Keep this lightweight: many tasks may use non-Robotiq grippers.
                print(
                    "Warning: gripper_jaw_width observable unavailable; could not "
                    "resolve supported gripper pad geoms in MuJoCo model"
                )
                _jaw_width_warned = True
            return np.array([np.nan], dtype=np.float32)

        left_pad1, left_pad2, right_pad1, right_pad2 = _jaw_width_geom_ids

        left_center = 0.5 * (
            np.asarray(sim.data.geom_xpos[left_pad1])
            + np.asarray(sim.data.geom_xpos[left_pad2])
        )
        right_center = 0.5 * (
            np.asarray(sim.data.geom_xpos[right_pad1])
            + np.asarray(sim.data.geom_xpos[right_pad2])
        )

        width = float(np.linalg.norm(left_center - right_center))
        return np.array([width], dtype=np.float32)
    
    return gripper_jaw_width


def create_obj_sensors(
    sim, 
    obj_name, 
    obj_body_id, 
    modality="object",
    robot_naming_prefix="robot0",
    return_2d_bboxes=False,
    return_3d_bboxes=False,
    return_segmentation_masks=False,
    camera_names=None,
    camera_heights=None,
    camera_widths=None,
):
    """
    Helper function to create sensors for a given object. This is abstracted in a separate function call so that we
    don't have local function naming collisions during the _setup_observables() call.

    Args:
        obj_name (str): Name of object to create sensors for
        modality (str): Modality to assign to all sensors

    Returns:
        2-tuple:
            sensors (list): Array of sensors for the given obj
            names (list): array of corresponding observable names
    """
    # pf = robot_naming_prefix

    sensors, names = create_object_pose_sensors(
        obj_name=obj_name, 
        obj_body_id=obj_body_id, 
        sim=sim, 
        modality=modality, 
        robot_naming_prefix=robot_naming_prefix
    )

    if return_2d_bboxes:
        for camera_name in camera_names:
            bbox_sensor, bbox_sensor_name = create_object_2d_bbox_sensor(
                obj_name=obj_name, 
                obj_body_id=obj_body_id, 
                sim=sim, 
                modality=modality, 
                camera_name=camera_name, 
                camera_height=camera_heights[camera_names.index(camera_name)], 
                camera_width=camera_widths[camera_names.index(camera_name)]
            )
            sensors.append(bbox_sensor)
            names.append(bbox_sensor_name)

    if return_segmentation_masks:
        for camera_name in camera_names:
            seg_sensor, seg_sensor_name = create_object_segmentation_mask_sensor(
                obj_name=obj_name,
                obj_body_id=obj_body_id,
                sim=sim,
                modality="segmentation",
                camera_name=camera_name,
                camera_height=camera_heights[camera_names.index(camera_name)],
                camera_width=camera_widths[camera_names.index(camera_name)],
            )
            sensors.append(seg_sensor)
            names.append(seg_sensor_name)

    if return_3d_bboxes:
        bbox_sensor, bbox_sensor_name = create_object_3d_bbox_sensor(
            obj_name=obj_name, 
            obj_body_id=obj_body_id, 
            sim=sim, 
            modality=modality
        )
        sensors.append(bbox_sensor)
        names.append(bbox_sensor_name)

    return sensors, names


# ------------------ Geometry / BBox utilities ------------------


def _get_object_geom_ids(
    obj_body_id: int,
    sim,
) -> list[int]:
    """
    Return all geom ids in the object's body subtree.
    """
    nbody = sim.model.nbody
    children = [[] for _ in range(nbody)]
    for bid in range(1, nbody):
        parent = sim.model.body_parentid[bid]
        if parent >= 0:
            children[parent].append(bid)

    subtree = {obj_body_id}
    stack = [obj_body_id]
    while stack:
        b = stack.pop()
        for ch in children[b]:
            if ch not in subtree:
                subtree.add(ch)
                stack.append(ch)

    return [
        gid
        for gid in range(sim.model.ngeom)
        if sim.model.geom_bodyid[gid] in subtree
    ]

def _get_object_world_bbox_corners(
    obj_body_id: int,
    sim,
) -> np.ndarray:
    """Return 8 oriented bbox corners for an object in world coordinates."""
    pts_world = np.asarray(_get_object_world_bbox_points(obj_body_id, sim), dtype=np.float32)
    if pts_world.ndim == 1:
        pts_world = pts_world.reshape(1, -1)
    if pts_world.shape[0] == 0:
        return np.zeros((0, 3), dtype=np.float32)
    if pts_world.shape[1] != 3:
        pts_world = pts_world.reshape(-1, 3)

    body_pos = sim.data.body_xpos[obj_body_id]
    body_rot = sim.data.body_xmat[obj_body_id].reshape(3, 3)

    pts_body = (body_rot.T @ (pts_world - body_pos).T).T

    mins = pts_body.min(axis=0)
    maxs = pts_body.max(axis=0)

    corners_body = np.array(
        list(itertools.product([mins[0], maxs[0]], [mins[1], maxs[1]], [mins[2], maxs[2]])),
        dtype=np.float32,
    )

    corners_world = (body_rot @ corners_body.T).T + body_pos
    return corners_world.astype(np.float32)

def _get_object_world_bbox_points(
    obj_body_id: int,
    sim,
) -> np.ndarray:
    """
    Collect 3D corner points approximating the object's bounding box by aggregating
    corners from all geoms in the object's body subtree. Falls back to the object's
    root body position if no geoms are found.
    """

    # Build body children adjacency
    nbody = sim.model.nbody
    children = [[] for _ in range(nbody)]
    for bid in range(1, nbody):
        parent = sim.model.body_parentid[bid]
        if parent >= 0:
            children[parent].append(bid)

    # BFS to get subtree body ids
    subtree = set([obj_body_id])
    stack = [obj_body_id]
    while stack:
        b = stack.pop()
        for ch in children[b]:
            if ch not in subtree:
                subtree.add(ch)
                stack.append(ch)

    geom_ids_all = [gid for gid in range(sim.model.ngeom) if sim.model.geom_bodyid[gid] in subtree]

    collision_geom_ids = []
    if hasattr(sim.model, "geom_group"):
        for gid in geom_ids_all:
            if sim.model.geom_group[gid] == 0:
                collision_geom_ids.append(gid)
    geom_ids = collision_geom_ids if len(collision_geom_ids) > 0 else geom_ids_all

    points = []
    for gid in geom_ids:
        pts = _get_geom_corners_world(gid, sim)
        if pts is not None and len(pts) > 0:
            points.extend(pts)

    if len(points) == 0:
        points = [np.array(sim.data.body_xpos[obj_body_id])]
    return np.array(points)

def _get_geom_corners_world(
    geom_id: int,
    sim,
) -> np.ndarray:
    """Returns 8 corner points (approx) for a geom in world frame."""
    gtype = sim.model.geom_type[geom_id]
    size = sim.model.geom_size[geom_id]

    if gtype == mujoco.mjtGeom.mjGEOM_BOX:
        half = np.array([size[0], size[1], size[2]])
    elif gtype == mujoco.mjtGeom.mjGEOM_SPHERE:
        r = size[0]
        half = np.array([r, r, r])
    elif gtype == mujoco.mjtGeom.mjGEOM_CYLINDER:
        r = size[0]
        half_len = size[1]
        half = np.array([r, r, half_len])
    elif gtype == mujoco.mjtGeom.mjGEOM_CAPSULE:
        r = size[0]
        half_len = size[1]
        half = np.array([r, r, half_len + r])
    elif gtype == mujoco.mjtGeom.mjGEOM_MESH:
        if hasattr(sim.model, "geom_dataid") and hasattr(sim.model, "mesh_vert"):
            mesh_id = int(sim.model.geom_dataid[geom_id])
            if mesh_id >= 0:
                vadr = int(sim.model.mesh_vertadr[mesh_id])
                vnum = int(sim.model.mesh_vertnum[mesh_id])
                verts = np.array(sim.model.mesh_vert[vadr : (vadr + vnum)])
                if hasattr(sim.model, "mesh_scale"):
                    scale = np.array(sim.model.mesh_scale[mesh_id])
                    if scale.shape[0] == 3:
                        verts = verts * scale[None, :]
                Rm = sim.data.geom_xmat[geom_id].reshape(3, 3)
                tm = sim.data.geom_xpos[geom_id]
                verts_w = (Rm @ verts.T).T + tm[None, :]
                mn = verts_w.min(axis=0)
                mx = verts_w.max(axis=0)
                corners = np.array(
                    [
                        [mn[0], mn[1], mn[2]],
                        [mx[0], mn[1], mn[2]],
                        [mn[0], mx[1], mn[2]],
                        [mn[0], mn[1], mx[2]],
                        [mx[0], mx[1], mx[2]],
                        [mn[0], mx[1], mx[2]],
                        [mx[0], mn[1], mx[2]],
                        [mx[0], mx[1], mn[2]],
                    ],
                    dtype=np.float64,
                )
                return corners
        r = float(getattr(sim.model, "geom_rbound", np.zeros(sim.model.ngeom))[geom_id])
        half = np.array([r, r, r])
    else:
        return None

    local = np.array(
        [
            [-1, -1, -1],
            [1, -1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
            [1, 1, 1],
            [-1, 1, 1],
            [1, -1, 1],
            [1, 1, -1],
        ],
        dtype=np.float64,
    ) * half[None, :]

    R = sim.data.geom_xmat[geom_id].reshape(3, 3)
    t = sim.data.geom_xpos[geom_id]
    pts_world = (R @ local.T).T + t[None, :]
    return pts_world
