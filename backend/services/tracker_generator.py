import asyncio
import logging

import numpy as np

logger = logging.getLogger(__name__)

MAX_CORNERS = 40
QUALITY_LEVEL = 0.3
MIN_DISTANCE = 30
REDETECT_INTERVAL = 15
LINE_DISTANCE_THRESHOLD = 150
CYAN = (255, 255, 0, 200)  # BGRA
GLOW_CYAN = (255, 255, 0, 80)


def _draw_tracker_frame(
    canvas: np.ndarray,
    points: np.ndarray,
) -> None:
    """Draw tracker visualization on a transparent BGRA canvas."""
    import cv2

    if points is None or len(points) < 2:
        return

    pts = points.reshape(-1, 2)

    # Draw connecting lines between nearby points
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dist = np.linalg.norm(pts[i] - pts[j])
            if dist < LINE_DISTANCE_THRESHOLD:
                p1 = tuple(pts[i].astype(int))
                p2 = tuple(pts[j].astype(int))
                # Glow layer (thicker, semi-transparent)
                cv2.line(canvas, p1, p2, GLOW_CYAN, 3, cv2.LINE_AA)
                # Core line
                cv2.line(canvas, p1, p2, CYAN, 1, cv2.LINE_AA)

    # Draw points
    for pt in pts:
        center = tuple(pt.astype(int))
        cv2.circle(canvas, center, 4, CYAN, -1, cv2.LINE_AA)
        cv2.circle(canvas, center, 7, GLOW_CYAN, 1, cv2.LINE_AA)


async def generate_tracker_overlay(
    source_path: str,
    start_time: float,
    end_time: float,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> str:
    """Generate a transparent WebM overlay with tracked feature points."""
    import cv2

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {source_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Seek to start
    cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)

    duration = end_time - start_time
    total_out_frames = max(1, round(duration * fps))

    # Start FFmpeg process for VP9 WebM with alpha
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "bgra",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "pipe:",
        "-c:v", "libvpx-vp9",
        "-pix_fmt", "yuva420p",
        "-auto-alt-ref", "0",
        "-b:v", "1M",
        "-an",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    prev_gray = None
    points = None
    frame_idx = 0

    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    feature_params = dict(
        maxCorners=MAX_CORNERS,
        qualityLevel=QUALITY_LEVEL,
        minDistance=MIN_DISTANCE,
    )

    # Scale factors from source to output resolution
    sx = width / src_w if src_w > 0 else 1
    sy = height / src_h if src_h > 0 else 1

    for out_idx in range(total_out_frames):
        # Compute which source time this output frame corresponds to
        out_time = start_time + out_idx / fps
        cap.set(cv2.CAP_PROP_POS_MSEC, out_time * 1000)
        ret, frame = cap.read()

        canvas = np.zeros((height, width, 4), dtype=np.uint8)

        if not ret:
            proc.stdin.write(canvas.tobytes())
            await proc.stdin.drain()
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect or re-detect features
        if points is None or frame_idx % REDETECT_INTERVAL == 0 or len(points) < 5:
            new_points = cv2.goodFeaturesToTrack(gray, **feature_params)
            if new_points is not None:
                # Scale points to output resolution
                points = new_points.copy()
                points[:, :, 0] *= sx
                points[:, :, 1] *= sy
                # Keep unscaled for tracking
                points_src = new_points
        elif prev_gray is not None and points is not None:
            # Track existing points
            next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                prev_gray, gray, points_src, None, **lk_params
            )
            if next_pts is not None and status is not None:
                good = status.ravel() == 1
                points_src = next_pts[good].reshape(-1, 1, 2)
                # Scale to output resolution
                points = points_src.copy()
                points[:, :, 0] *= sx
                points[:, :, 1] *= sy

        prev_gray = gray

        # Draw on canvas
        _draw_tracker_frame(canvas, points)

        proc.stdin.write(canvas.tobytes())
        await proc.stdin.drain()
        frame_idx += 1

    cap.release()
    proc.stdin.close()
    await proc.stdin.wait_closed()
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode()[-500:]
        raise RuntimeError(f"Tracker overlay encoding failed: {err}")

    logger.info("Generated tracker overlay: %s (%d frames)", output_path, total_out_frames)
    return output_path
