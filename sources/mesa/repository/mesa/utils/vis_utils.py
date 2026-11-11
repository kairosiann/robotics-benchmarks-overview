from typing import Sequence, Union

import cv2
import numpy as np
import robosuite.macros as macros

ArrayLike = Union[np.ndarray, Sequence[np.ndarray]]


def _ensure_bgr_uint8(frame: np.ndarray) -> np.ndarray:
    """
    Helper to ensure an image is uint8 BGR for OpenCV.
    """
    if frame.dtype != np.uint8:
        frame = np.clip(frame, 0, 255).astype(np.uint8)

    if frame.ndim == 2:
        frame = np.stack([frame, frame, frame], axis=-1)

    # Assume incoming is RGB (robosuite convention); convert to BGR for OpenCV.
    if frame.shape[-1] == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    return frame


def visualize_poses(
    images: ArrayLike,
    poses: ArrayLike,
    camera_transform_matrix: np.ndarray,
    camera_height: int,
    camera_width: int,
    output_path: str,
    axis_length: float = 0.05,
    fps: int = 10,
) -> None:
    """
    Render a video visualizing a sequence of SE(3) poses as coordinate frames overlaid on images.

    Each pose is assumed to be a 4x4 homogeneous transform in the world frame. The
    `camera_transform_matrix` should be the 4x4 matrix mapping world points to pixel
    coordinates, e.g. from `robosuite.utils.camera_utils.get_camera_transform_matrix`.

    Args:
        images: Single image of shape (H, W, 3) or a sequence / array of images of shape
            (T, H, W, 3). If a single image is provided, it is reused for all poses.
        poses: SE(3) poses as either:
            - np.ndarray of shape (4, 4)               (single pose)
            - np.ndarray of shape (T, 4, 4)            (sequence of poses)
            - Sequence of (4, 4) arrays
        camera_transform_matrix: 4x4 matrix that projects world coordinates to pixel
            coordinates (same convention as `project_points_to_image`).
        camera_height: Height of the camera image (pixels).
        camera_width: Width of the camera image (pixels).
        output_path: Path to the video file to write (e.g. "poses.mp4").
        axis_length: Length (in world units) of each axis drawn from the pose origin.
        fps: Frames per second for the output video.
    """
    # Normalize poses to (T, 4, 4)
    poses_arr = np.asarray(poses)
    if poses_arr.ndim == 2 and poses_arr.shape == (4, 4):
        poses_arr = poses_arr[None, ...]
    elif poses_arr.ndim == 3 and poses_arr.shape[1:] == (4, 4):
        pass
    else:
        raise ValueError(
            f"`poses` must be (4, 4) or (T, 4, 4); got shape {poses_arr.shape}."
        )

    num_frames = poses_arr.shape[0]

    # Normalize images to (T, H, W, C)
    images_arr = np.asarray(images)
    images_arr = images_arr[..., ::-1, :, :]
    if images_arr.ndim == 3:
        # Single image -> broadcast across all poses
        images_arr = np.repeat(images_arr[None, ...], num_frames, axis=0)
    elif images_arr.ndim == 4:
        if images_arr.shape[0] != num_frames:
            raise ValueError(
                f"Number of images ({images_arr.shape[0]}) must match number of poses "
                f"({num_frames}) when a sequence of images is provided."
            )
    else:
        raise ValueError(
            f"`images` must be (H, W, C) or (T, H, W, C); got shape {images_arr.shape}."
        )

    # Sanity check spatial dimensions
    if images_arr.shape[1] != camera_height or images_arr.shape[2] != camera_width:
        raise ValueError(
            "Image spatial dimensions must match (camera_height, camera_width); "
            f"got images ({images_arr.shape[1]}, {images_arr.shape[2]}) vs "
            f"camera ({camera_height}, {camera_width})."
        )

    # Use MJPG, which is widely supported (e.g. in VS Code previews). Prefer using a
    # `.avi` extension for best compatibility with this codec.
    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"MJPG"),
        float(fps),
        (camera_width, camera_height),
    )

    try:
        for img, pose in zip(images_arr, poses_arr):
            # Extract origin and axes in world frame
            origin = pose[:3, 3]
            R = pose[:3, :3]
            x_axis_end = origin + axis_length * R[:, 0]
            y_axis_end = origin + axis_length * R[:, 1]
            z_axis_end = origin + axis_length * R[:, 2]

            points_world = np.stack(
                [origin, x_axis_end, y_axis_end, z_axis_end],
                axis=0,
            )  # (4, 3)

            points_2d, valid = project_points_to_image(
                points_world,
                camera_transform_matrix,
                camera_height,
                camera_width,
            )

            # Flip across the horizontal line through the middle of the image
            # so that the overlaid coordinate frames are mirrored vertically.
            # points_2d[:, 1] = (camera_height - 1) - points_2d[:, 1]

            frame_bgr = _ensure_bgr_uint8(img)

            # Only draw axes if origin is visible
            if valid[0]:
                o = tuple(points_2d[0].astype(int))

                # X-axis: red
                if valid[1]:
                    cv2.line(
                        frame_bgr,
                        o,
                        tuple(points_2d[1].astype(int)),
                        color=(0, 0, 255),
                        thickness=2,
                    )
                # Y-axis: green
                if valid[2]:
                    cv2.line(
                        frame_bgr,
                        o,
                        tuple(points_2d[2].astype(int)),
                        color=(0, 255, 0),
                        thickness=2,
                    )
                # Z-axis: blue
                if valid[3]:
                    cv2.line(
                        frame_bgr,
                        o,
                        tuple(points_2d[3].astype(int)),
                        color=(255, 0, 0),
                        thickness=2,
                    )

                # Draw origin as a small circle
                cv2.circle(frame_bgr, o, radius=3, color=(255, 255, 255), thickness=-1)

            frame_bgr = frame_bgr
            writer.write(frame_bgr)
    finally:
        writer.release()



def project_points_to_image(points_world, camera_transform_matrix, camera_height, camera_width):
    """
    Project Nx3 world points to image pixel coordinates (u, v).
    Returns (points_2d: Nx2, valid_mask: N).
    Coordinates are aligned with the image arrays returned by camera sensors,
    considering macros.IMAGE_CONVENTION.
    """
    if points_world.ndim == 1:
        points_world = points_world[None, :]
    N = points_world.shape[0]
    homog = np.concatenate([points_world, np.ones((N, 1))], axis=1).T  # 4xN
    proj = camera_transform_matrix @ homog  # 4xN
    x = proj[0, :]
    y = proj[1, :]
    z = proj[2, :]
    # Valid if in front of camera
    eps = 1e-6
    valid = z > eps
    u = np.where(valid, x / z, -1.0)
    v = np.where(valid, y / z, -1.0)
    # Adjust for image convention: our projection assumes OpenCV (origin at top-left).
    # If using OpenGL convention (no vertical flip applied to images), invert v.
    if macros.IMAGE_CONVENTION == "opengl":
        v = np.where(valid, (camera_height - 1) - v, v)
    pts = np.stack([u, v], axis=1)
    # Additionally mark points outside image as invalid
    in_bounds = (
        (pts[:, 0] >= 0)
        & (pts[:, 0] < camera_width)
        & (pts[:, 1] >= 0)
        & (pts[:, 1] < camera_height)
    )
    valid = valid & in_bounds
    return pts, valid
