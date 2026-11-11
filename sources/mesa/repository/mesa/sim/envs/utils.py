from typing import Tuple

import numpy as np
from transforms3d import euler
from transforms3d.axangles import axangle2mat
from transforms3d.quaternions import mat2quat, quat2mat

from mesa.sim.envs.objects import BaseObject


def angle_from_quaternion(q, axis):
    """
    q: numpy array [w, x, y, z]
    axis: "x", "y", or "z"
    returns rot_angle
    """
    x, y, z, w = q

    if axis == "x":
        comp = x
    elif axis == "y":
        comp = y
    elif axis == "z":
        comp = z
    else:
        raise ValueError("axis must be x, y, or z")

    # atan2 ensures correct sign and handles all quadrants
    return 2 * np.arctan2(comp, w)


def obb_intersect_2d(
    object_1: BaseObject,
    pos_1: np.ndarray, 
    quat_1: float, 
    object_2: BaseObject,
    pos_2: np.ndarray, 
    quat_2: float, 
    expansion: float = 0.0,
    eps: float = 1e-8,
) -> bool:
    """
    Exact 2D OBB intersection test using SAT.

    pos*: np.array([x, y]) world positions (projection of object position to ground plane)
    angle*: yaw angle (radians, rotation about vertical axis)
    half_extents*: np.array([hx, hy]) half-sizes in local (unrotated) frame

    Args:
        object_1: First object whose horizontal OBB is used.
        pos_1: World position of ``object_1`` projected onto the xy-plane.
        quat_1: Quaternion (wxyz) for ``object_1``.
        object_2: Second object whose horizontal OBB is used.
        pos_2: World position of ``object_2`` projected onto the xy-plane.
        quat_2: Quaternion (wxyz) for ``object_2``.
        expansion: Scalar amount (in meters) by which to uniformly expand the
            half-extents of **both** boxes in the xy-plane before testing for
            intersection. This effectively inflates both boxes.
        eps: Small numerical epsilon used when computing the SAT terms.

    Returns True if the oriented bounding boxes intersect, False otherwise.
    """

    angle_1 = angle_from_quaternion(quat_1, object_1.rotation_axis)
    angle_2 = angle_from_quaternion(quat_2, object_2.rotation_axis)

    # Unpack half extents and apply uniform expansion in the xy-plane
    e1x, e1y, _ = np.abs(object_1.horizontal_offset)
    e2x, e2y, _ = np.abs(object_2.horizontal_offset)

    # Expand all half-extents in the ground plane by the same scalar amount.
    # The z-dimension is intentionally left unchanged because this is a 2D test.
    e1x = e1x + expansion
    e1y = e1y + expansion
    e2x = e2x + expansion
    e2y = e2y + expansion

    # Local axes in world frame for box 1
    c1, s1 = np.cos(angle_1), np.sin(angle_1)
    u10 = np.array([c1, s1])      # local x-axis
    u11 = np.array([-s1, c1])     # local y-axis

    # Local axes in world frame for box 2
    c2, s2 = np.cos(angle_2), np.sin(angle_2)
    u20 = np.array([c2, s2])
    u21 = np.array([-s2, c2])

    # Rotation matrix R: R[i, j] = dot(u1_i, u2_j)
    R = np.array([
        [np.dot(u10, u20), np.dot(u10, u21)],
        [np.dot(u11, u20), np.dot(u11, u21)],
    ])

    # Add small epsilon to guard against numerical issues when angles are near parallel
    R_abs = np.abs(R) + eps

    # Vector between centers, expressed in box 1 frame
    t = np.array(pos_2) - np.array(pos_1)
    t_local = np.array([np.dot(t, u10), np.dot(t, u11)])

    # Test axes of box 1: u10, u11
    # Axis L = u10
    ra = e1x
    rb = e2x * R_abs[0, 0] + e2y * R_abs[0, 1]
    if np.abs(t_local[0]) > ra + rb:
        return False

    # Axis L = u11
    ra = e1y
    rb = e2x * R_abs[1, 0] + e2y * R_abs[1, 1]
    if np.abs(t_local[1]) > ra + rb:
        return False

    # Test axes of box 2: u20, u21
    # Express t along u20/u21 using R and t_local
    # t · u2j = t_local[0] * R[0, j] + t_local[1] * R[1, j]

    # Axis L = u20
    ra = e1x * R_abs[0, 0] + e1y * R_abs[1, 0]
    rb = e2x
    proj_t = t_local[0] * R[0, 0] + t_local[1] * R[1, 0]
    if np.abs(proj_t) > ra + rb:
        return False

    # Axis L = u21
    ra = e1x * R_abs[0, 1] + e1y * R_abs[1, 1]
    rb = e2y
    proj_t = t_local[0] * R[0, 1] + t_local[1] * R[1, 1]
    if np.abs(proj_t) > ra + rb:
        return False

    # No separating axis found → boxes intersect
    return True


def obb_corners_2d(pos_xy: np.ndarray, quat_xyzw: np.ndarray, obj, expansion: float = 0.0) -> np.ndarray:
    """
    Compute 4 corners (counter-clockwise) of the object's horizontal OBB in world XY.

    Requires:
      - obj.horizontal_offset: array-like with (hx, hy, hz) half-extents (or similar); only hx,hy used.
      - optionally obj.rotation_axis: e.g. 'z' (defaults to 'z' if missing).
    """
    pos_xy = np.asarray(pos_xy, dtype=float).reshape(2,)
    angle = angle_from_quaternion(quat_xyzw, obj.rotation_axis)

    # Half extents in the ground plane
    hx, hy = np.abs(np.asarray(obj.horizontal_offset, dtype=float).reshape(3,))[:2]
    hx += expansion
    hy += expansion

    # Local corners (CCW): (-hx,-hy), (hx,-hy), (hx,hy), (-hx,hy)
    local = np.array(
        [[-hx, -hy],
         [ hx, -hy],
         [ hx,  hy],
         [-hx,  hy]],
        dtype=float,
    )

    c, s = np.cos(angle), np.sin(angle)
    R = np.array([[c, -s],
                  [s,  c]], dtype=float)

    world = local @ R.T + pos_xy
    return world

def draw_bboxes_2d(
    tuples,
    ax=None,
    expansion: float = 0.0,
    annotate: bool = False,
    linewidth: float = 1.5,
):
    """
    Draw all horizontal OBBs to a matplotlib plot.

    Args:
        tuples: iterable of (pos, quat, obj) where
            - pos: array-like (x,y) or (x,y,z) (only x,y used)
            - quat: array-like (w,x,y,z)
            - obj: has .horizontal_offset (hx,hy,hz) and optionally .rotation_axis
        ax: optional matplotlib Axes
        expansion: inflate half-extents by this much (meters) in x/y before drawing
        annotate: if True, label boxes with their index at the center
        linewidth: polygon edge width

    Returns:
        (fig, ax)
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure

    xs, ys = [], []
    for i, (pos, quat, obj) in enumerate(tuples):
        pos = np.asarray(pos, dtype=float).reshape(-1,)
        pos_xy = pos[:2]
        corners = obb_corners_2d(pos_xy, quat, obj, expansion=expansion)

        poly = Polygon(corners, closed=True, fill=False, linewidth=linewidth)
        ax.add_patch(poly)

        xs.extend(corners[:, 0].tolist())
        ys.extend(corners[:, 1].tolist())

        if annotate:
            ax.text(pos_xy[0], pos_xy[1], obj.name, ha="center", va="center")

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.invert_yaxis()
    ax.invert_xaxis()

    if xs and ys:
        pad = 0.05 * max(np.ptp(xs), np.ptp(ys), 1e-6)
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)

    return fig, ax


def convert_spherical_to_pos_quat(r, theta, phi):
    """
    Converts spherical coordinates (physics convention) into Euclidean position
    and quaternion rotation, such that +z points at the origin.
    """
    pos = [
        r * np.sin(theta) * np.cos(phi),
        r * np.sin(theta) * np.sin(phi),
        r * np.cos(theta),
    ]
    euler_zxy = (np.pi / 2 + phi, theta, 0)
    quat_wxyz = euler.euler2quat(*euler_zxy, axes="rzxy")
    return pos, quat_wxyz

def rectangle2xyrange(rect_ranges):
    x_ranges = []
    y_ranges = []
    for rect_range in rect_ranges:
        x_ranges.append([rect_range[0], rect_range[2]])
        y_ranges.append([rect_range[1], rect_range[3]])
    return x_ranges, y_ranges


def compute_scene_camera_pose(
    camera_name: str,
    randomize: bool = False,
    table_offset: Tuple[float, float, float] = (0.0, 0.0, 0.9),
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute the camera pose for the given camera name.
    """
    assert camera_name in ['leftshoulder', 'rightshoulder']
    # base_pos = [1.0, 0, 1.6]
    # base_quat = [0.5963678, 0.3799282, 0.3799282, 0.5963678]

    r = 1.2
    theta = np.pi / 3
    tilt = 0.0
    pan = 0.0
    if camera_name == "leftshoulder":
        phi = -np.pi / 4
    elif camera_name == "rightshoulder":
        phi = np.pi / 4
    else:
        raise ValueError(f"Invalid camera name: {camera_name}")
    
    r_radius = 0.1 if randomize else None
    theta_radius = 0.1 if randomize else None
    phi_radius = 0.1 if randomize else None
    tilt_radius = 0.1 if randomize else None
    pan_radius = 0.1 if randomize else None

    return sample_camera_pose(
        table_offset=table_offset,
        r=r, 
        theta=theta, 
        phi=phi, 
        tilt=tilt, 
        pan=pan, 
        r_radius=r_radius, 
        theta_radius=theta_radius, 
        phi_radius=phi_radius, 
        tilt_radius=tilt_radius, 
        pan_radius=pan_radius,
    )

def sample_camera_pose(
    table_offset: Tuple[float, float, float] = (0.0, 0.0, 0.9),
    r: float = 1.2,
    theta: float = np.pi / 3,
    phi: float = 0.0,
    tilt: float = 0.0,
    pan: float = 0.0,
    r_radius: float | None = None,
    theta_radius: float | None = None,
    phi_radius: float | None = None,
    tilt_radius: float | None = None,
    pan_radius: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Sample a camera pose according to physics convention spherical 
    coordinates (r, theta, phi). Camera is defaulted to point at the
    table center, but can be adjusted with tilt and pan.

    Args:
        r: How far the camera should be from the table center.
        theta: The theta angle of the camera.
        phi: Rotation in the xy plane.
        tilt: The tilt angle of the camera.
        pan: The pan angle of the camera.
        r_radius: The range of the radius to randomize.
        theta_radius: The range of the theta angle to randomize.
        phi_radius: The range of the phi angle to randomize.
        tilt_radius: The range of the tilt angle to randomize.
        pan_radius: The range of the pan angle to randomize.
    
    Returns:
        The camera pose as a tuple of position and quaternion.
    """

    if r_radius is not None:
        r = np.random.uniform(r - r_radius, r + r_radius)
    if theta_radius is not None:
        theta = np.random.uniform(theta - theta_radius, theta + theta_radius)
    if phi_radius is not None:
        phi = np.random.uniform(phi - phi_radius, phi + phi_radius)
    if tilt_radius is not None:
        tilt = np.random.uniform(tilt - tilt_radius, tilt + tilt_radius)
    if pan_radius is not None:
        pan = np.random.uniform(pan - pan_radius, pan + pan_radius)
    pos, quat = convert_spherical_to_pos_quat(r, theta, phi)

    # If tilt and pan are specified, compose them as intrinsic rotations (X for tilt, Y for pan).
    # Build the overall camera orientation: (spherical -> pan -> tilt), intrinsic sequence (ZYX or 'rzyx')
    if 'tilt' in locals() or 'pan' in locals():
        # pan and tilt default to 0 if not present
        tilt = tilt if 'tilt' in locals() else 0.0
        pan = pan if 'pan' in locals() else 0.0

        # Spherical gives us some camera orientation, apply pan and tilt as additional local rotations:
        # First convert the quaternion to a matrix
        rot_mat = quat2mat(quat)
        # Compose pan (Y) and tilt (X) as intrinsic rotations, using transforms3d.axangles
        tilt_mat = axangle2mat([1, 0, 0], tilt)  # tilt around X
        pan_mat = axangle2mat([0, 1, 0], pan)    # pan around Y

        # Intrinsic rotations: first tilt, then pan (i.e., rot = pan * tilt * base)
        rot_mat = pan_mat @ tilt_mat @ rot_mat
        quat = mat2quat(rot_mat)

    pos = np.array(table_offset) + pos

    return pos, quat