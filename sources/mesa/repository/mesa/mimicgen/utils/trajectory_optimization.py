import numpy as np

import mesa.mimicgen.utils.pose_utils as PoseUtils


def rot_align(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotation that maps unit vector u to unit vector v."""
    eps = 1e-12
    nu = u / (np.linalg.norm(u) + eps)
    nv = v / (np.linalg.norm(v) + eps)
    c = float(np.dot(nu, nv))
    c = np.clip(c, -1.0, 1.0)
    if 1.0 - c < 1e-12:
        return np.eye(3)                # already aligned
    if c + 1.0 < 1e-12:
        # Opposite: 180° about any axis ⟂ u. Pick a stable one.
        a = np.array([1.0, 0.0, 0.0])
        if abs(nu[0]) > 0.9:
            a = np.array([0.0, 1.0, 0.0])
        k = np.cross(nu, a)
        k /= np.linalg.norm(k)
        return PoseUtils.so3_exp(k * np.pi)
    k = np.cross(nu, nv)
    s = np.linalg.norm(k)
    K = PoseUtils._hat(k / (s + 1e-12))
    theta = np.arctan2(s, c)
    return np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * (K @ K)


_AXIS_VEC = {
    "x": np.array([1.0, 0.0, 0.0]),
    "y": np.array([0.0, 1.0, 0.0]),
    "z": np.array([0.0, 0.0, 1.0]),
}

def rot_align_about_xyz_axes(
    u: np.ndarray,
    v: np.ndarray,
    axes: list[str] | tuple[str, ...],
    *,
    max_iters: int = 30,
    damping: float = 1e-3,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Minimize ||R u - v|| by rotating ONLY about a subset of world axes in `axes`,
    applied in the given order.

    axes: subset of {"x","y","z"}, e.g. ["z"] (yaw only), ["z","y"], ["x","y","z"].

    Returns
    -------
    R : (3,3) rotation matrix
    thetas : (k,) angles (radians) corresponding to `axes` order
    """
    u = np.asarray(u, dtype=float).reshape(3)
    v = np.asarray(v, dtype=float).reshape(3)

    if not axes:
        return np.eye(3), np.zeros((0,), dtype=float)

    axes = [a.lower() for a in axes]
    if any(a not in _AXIS_VEC for a in axes):
        raise ValueError(f"axes must be a subset of ['x','y','z']; got {axes}")
    k = len(axes)
    if k > 3:
        raise ValueError("axes can contain at most 3 elements")

    A = np.stack([_AXIS_VEC[a] for a in axes], axis=0)  # (k,3)

    # Closed-form for single axis: best rotation about that axis.
    if k == 1:
        a = A[0]
        u_perp = u - a * float(np.dot(a, u))
        v_perp = v - a * float(np.dot(a, v))
        nu = float(np.linalg.norm(u_perp))
        nv = float(np.linalg.norm(v_perp))
        if nu < 1e-12 or nv < 1e-12:
            return np.eye(3), np.array([0.0], dtype=float)
        u_perp /= nu
        v_perp /= nv
        sin_t = float(np.dot(a, np.cross(u_perp, v_perp)))
        cos_t = float(np.dot(u_perp, v_perp))
        theta = float(np.arctan2(sin_t, cos_t))
        return PoseUtils.so3_exp(a * theta), np.array([theta], dtype=float)

    def compose(thetas_: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
        Rs = [PoseUtils.so3_exp(A[i] * float(thetas_[i])) for i in range(k)]
        R = np.eye(3)
        for Ri in Rs:
            R = R @ Ri
        return R, Rs

    def wrap_pi(x: np.ndarray) -> np.ndarray:
        return (x + np.pi) % (2.0 * np.pi) - np.pi

    # Init: project the unconstrained align rotation's axis-angle onto the allowed axes.
    R_full = rot_align(u, v)
    phi0 = PoseUtils.so3_log(R_full)                    # (3,) axis-angle vector
    thetas = (A @ phi0).astype(float)         # small-angle projection

    for _ in range(max_iters):
        R, Rs = compose(thetas)
        ru = R @ u
        r = ru - v                             # (3,)

        # Jacobian wrt each angle
        prefix = [np.eye(3)]
        for i in range(k):
            prefix.append(prefix[-1] @ Rs[i])

        suffix_u = [None] * (k + 1)
        suffix_u[k] = u
        for i in range(k - 1, -1, -1):
            suffix_u[i] = Rs[i] @ suffix_u[i + 1]

        J = np.zeros((3, k), dtype=float)
        for i in range(k):
            Ki = PoseUtils._hat(A[i])  # uses your existing _hat
            J[:, i] = prefix[i] @ (Rs[i] @ (Ki @ suffix_u[i + 1]))

        # Levenberg-Marquardt step
        H = J.T @ J + damping * np.eye(k)
        g = J.T @ r
        try:
            delta = -np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            delta = -np.linalg.lstsq(H, g, rcond=None)[0]

        if float(np.linalg.norm(delta)) < 1e-12:
            break

        thetas = wrap_pi(thetas + delta)

    R, _ = compose(thetas)
    return R, thetas


def slerp(R_start: np.ndarray, R_end: np.ndarray, s: float) -> np.ndarray:
    """
    General Geodesic interpolation using so3 log/exp.
    Interpolates from R_start (s=0) to R_end (s=1).
    """
    # 1. Compute the relative rotation matrix
    # R_rel is the rotation that takes you from R_start to R_end
    R_rel = R_end @ R_start.T
    
    # 2. Get the axis-angle representation (Lie Algebra)
    phi = PoseUtils.so3_log(R_rel)
    
    # 3. Interpolate the relative rotation and apply it to the start
    # R(s) = exp(s * log(R_end @ R_start^T)) @ R_start
    return PoseUtils.so3_exp(s * phi) @ R_start


def slerp_to_identity(R_star: np.ndarray, s: float) -> np.ndarray:
    """
    Special case: Interpolates from R_star (s=0) to Identity (s=1).
    Wraps the general slerp function.
    """
    # Note: R_end is np.eye(3). 
    # The relative rotation R_rel becomes (I @ R_star.T) = R_star.T
    # The interpolation becomes: so3_exp(s * so3_log(R_star.T)) @ R_star
    # Which simplifies to your original: so3_exp((1-s) * so3_log(R_star))
    return slerp(R_start=R_star, R_end=np.eye(3), s=s)


def smoothstep_schedule(n: int) -> np.ndarray:
    """Monotone C1 schedule: s[0]=0, s[-1]=1."""
    if n < 2:
        return np.array([1.0])
    tau = np.linspace(0.0, 1.0, n)
    return tau * tau * (3.0 - 2.0 * tau)


# ---------- SE(3) helpers ----------


def pose_loc(P: np.ndarray) -> np.ndarray:
    return P[:3, 3]


def left_multiply_rotation(P: np.ndarray, R: np.ndarray, multiply_translation: bool = True) -> np.ndarray:
    """Return (R ⊕ 0) * P. Keeps SE(3)."""
    out = P.copy()
    out[:3, :3] = R @ P[:3, :3]
    if multiply_translation:
        out[:3, 3]  = R @ P[:3, 3]
    return out


def smoothstep(t):
    return t*t*(3.0 - 2.0*t)


def shaped_smoothstep_schedule(n: int, beta: float = 1.0) -> np.ndarray:
    """Return-to-identity earlier with beta<1, later with beta>1."""
    if n < 2:
        return np.array([1.0])
    tau = np.linspace(0.0, 1.0, n)
    s = smoothstep(tau)
    s[0], s[-1] = 0.0, 1.0
    return np.power(s, beta)


def schedule_with_knee(n: int, knee_tau: float = 0.4, knee_level: float = 0.9) -> np.ndarray:
    """
    Choose beta so that s(knee_tau) = knee_level for smoothstep^beta.
    Example: knee_tau=0.4, knee_level=0.9 => ~90% returned by 40% of steps.
    """
    base = smoothstep(knee_tau)
    base = np.clip(base, 1e-6, 1 - 1e-6)
    knee_level = np.clip(knee_level, 1e-6, 1 - 1e-6)
    beta = np.log(knee_level) / np.log(base)
    return shaped_smoothstep_schedule(n, beta)


def get_schedule(schedule: str, n: int, **schedule_params) -> np.ndarray:
    """
    Get the schedule for the fadeout.

    Args:
        schedule: str, schedule for the fadeout.
        n: int, number of steps in the trajectory.
        **schedule_params: additional parameters for the schedule.

    Returns:
        s: (n,) array of schedule values.
    """
    if "schedule_ratio" in schedule_params:
        schedule_ratio = schedule_params["schedule_ratio"]
    else:
        schedule_ratio = 1.0
    n_schedule = int(schedule_ratio * n)
    n_fixed = n - n_schedule

    if schedule == "none":
        return np.zeros(n)
    elif schedule == "linear":
        s = np.linspace(0.0, 1.0, n_schedule)
    elif schedule == "smoothstep":
        s = smoothstep_schedule(n_schedule)
    elif schedule == "shaped":
        beta = float(schedule_params.get("beta", 1.0))
        s = shaped_smoothstep_schedule(n_schedule, beta)
    elif schedule == "knee":
        knee_tau = float(schedule_params.get("knee_tau", 0.4))
        knee_level = float(schedule_params.get("knee_level", 0.9))
        s = schedule_with_knee(n_schedule, knee_tau, knee_level)
    else:
        raise ValueError(f"Unknown schedule '{schedule}'")
    s = np.concatenate([s, np.ones(n_fixed)])
    return s


def optimize_trajectory_for_pos(
    Ps: np.ndarray, 
    x: np.ndarray,
    cur_object_pose: np.ndarray,
    offset: int = 0,
    schedule: str = "none",
    transform_rot: bool = False,
    **schedule_params,
):
    """
    This function rotates the trajectory so that the position of out[0] is as close as possible to x.

    schedule options:
      - "linear"
      - "smoothstep"
      - "shaped"         (+ beta: float, default 1.0)
      - "knee"           (+ knee_tau: float in [0,1], knee_level: float in (0,1))

    Args:
        Ps: (n, 4, 4) array of poses.
        x: (3,) array of target position.
        offset: int, offset of the trajectory.
        schedule: str, schedule for the fadeout.
        schedule_ratio: float, how much of the trajectory to use the schedule for.
        **schedule_params: additional parameters for the schedule.

    Returns:
        Rks: (n, 3, 3) array of rotation matrices.
    """
    assert Ps.ndim == 3 and Ps.shape[1:] == (4, 4)
    n = Ps.shape[0]

    tn = pose_loc(cur_object_pose)
    best_dist = np.inf
    best_R_star = np.eye(3)
    best_i = None
    for i in range(n // 2): # We only want to use potential starting points in the first half of the trajectory
        ti = pose_loc(Ps[i])
        R_star, _ = rot_align_about_xyz_axes(ti - tn, x - tn, axes=["z"])
        R_star = np.eye(3) if (np.linalg.norm(ti) < 1e-12 or np.linalg.norm(x) < 1e-12) else R_star

        transform_matrix = np.eye(4)
        transform_matrix[:3, :3] = R_star
        transform_matrix[:3, 3] = (np.eye(3) - R_star) @ tn
        translated_pose = transform_matrix @ Ps[i]
        translated_pos = pose_loc(translated_pose)
        dist = np.linalg.norm(translated_pos - x)

        if dist < best_dist:
            best_dist = dist
            best_R_star = R_star
            best_i = i
    

    R_star = best_R_star

    s = get_schedule(schedule, n - offset, **schedule_params)
    s = np.concatenate([s, np.ones(offset)])

    # Rotate about the z-axis through the end of the trajectory
    transform_matrices = np.zeros((n, 4, 4), dtype=Ps.dtype)
    for k in range(n):
        R = slerp_to_identity(R_star, float(s[k]))

        transform_matrices[k, :3, :3] = R
        transform_matrices[k, :3, 3] = (np.eye(3) - R) @ tn
        transform_matrices[k, 3, 3] = 1.0

    out = Ps.copy()
    for k in range(Ps.shape[0]):
        pos = transform_matrices[k] @ Ps[k, :, 3]
        pos = pos[:3]
        
        if transform_rot:
            rot = transform_matrices[k, :3, :3] @ Ps[k, :3, :3]
        else:
            rot = Ps[k, :3, :3]
        out[k] = PoseUtils.make_pose(pos, rot)

    out = out[best_i:]
    return out


def optimize_trajectory_for_rot(
    Ps: np.ndarray, 
    x: np.ndarray,
    offset: int = 0,
    schedule: str = "smoothstep",
    do_breakpoint=False,
    **schedule_params,
):
    """
    This function rotates the trajectory so that the rotation of out[0] is as close as possible to x.

    Args:
        Ps: (n, 4, 4) array of poses.
        x: (4, 4) array of target SE(3)matrix.
        schedule: str, schedule for the fadeout.
        **schedule_params: additional parameters for the schedule.

    Returns:
        out: (n, 4, 4) array of optimized poses.
        Rks: (n, 3, 3) array of rotation matrices.
    """
    n = Ps.shape[0]

    pos_orig = Ps[0]

    wrist_rot = np.array([
        [-1, 0, 0, 0],
        [0, -1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ])
    pos_rot = pos_orig @ wrist_rot

    dist_orig = PoseUtils.se3_distance(pos_orig, x)
    dist_rot = PoseUtils.se3_distance(pos_rot, x)
    # print(f"dist_orig: {dist_orig}")
    # print(f"dist_rot: {dist_rot}")

    if dist_rot < dist_orig:
        Ps = Ps @ wrist_rot


    R_star = x[:3, :3] @ Ps[0, :3, :3].T


    # if do_breakpoint:
    #     breakpoint()

    
    s = get_schedule(schedule, n - offset, **schedule_params)
    s = np.concatenate([s, np.ones(offset)])



    Rks = np.empty((n, 3, 3), dtype=Ps.dtype)
    for k in range(n):
        Rks[k] = slerp_to_identity(R_star, float(s[k]))
    # Rks[0] = R_star
    # Rks[-offset:] = np.eye(3)

    out = Ps.copy()
    for k in range(n):
        out[k] = left_multiply_rotation(Ps[k], Rks[k], multiply_translation=False)

    return out, Rks