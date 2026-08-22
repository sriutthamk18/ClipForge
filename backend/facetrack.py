"""
Face detection + smoothing to drive a dynamic panning crop.
Samples faces across a clip's time range and produces a smoothed, time-varying
horizontal (and vertical) center so the crop can pan to follow the speaker,
instead of a dumb static center-crop. Uses OpenCV's built-in Haar cascade --
no model download required, so it works out of the box on any host.

Falls back cleanly (empty sample list) if OpenCV can't open the video or no
faces are found anywhere in the sampled frames -- callers should treat that
as "use a static center crop."
"""
from dataclasses import dataclass
from typing import List, Tuple

import cv2

_FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


@dataclass
class FaceSample:
    t: float
    cx: float
    cy: float


def sample_faces(
    video_path: str, start: float, end: float, sample_rate_hz: float = 2.0
) -> Tuple[List[FaceSample], int, int]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], 0, 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not src_w or not src_h:
        cap.release()
        return [], 0, 0

    step_frames = max(1, int(round(fps / sample_rate_hz)))
    start_frame = int(start * fps)
    end_frame = int(end * fps)

    samples: List[FaceSample] = []
    frame_idx = start_frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

    prev_cx, prev_cy = 0.5, 0.5

    while frame_idx <= end_frame:
        ok, frame = cap.read()
        if not ok:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _FACE_CASCADE.detectMultiScale(
            gray, scaleFactor=1.15, minNeighbors=5, minSize=(50, 50)
        )

        if len(faces):
            def score(f):
                fx, fy, fw, fh = f
                cx, cy = (fx + fw / 2) / src_w, (fy + fh / 2) / src_h
                dist = ((cx - prev_cx) ** 2 + (cy - prev_cy) ** 2) ** 0.5
                area = fw * fh
                return area - dist * src_w * src_h * 0.5

            fx, fy, fw, fh = max(faces, key=score)
            cx, cy = (fx + fw / 2) / src_w, (fy + fh / 2) / src_h
            prev_cx, prev_cy = cx, cy
            samples.append(FaceSample(t=(frame_idx - start_frame) / fps, cx=cx, cy=cy))

        frame_idx += step_frames
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

    cap.release()
    return samples, src_w, src_h


def smooth_samples(samples: List[FaceSample], window: int = 3) -> List[FaceSample]:
    """Simple moving average to kill frame-to-frame jitter before panning."""
    if len(samples) <= window:
        return samples
    smoothed = []
    for i in range(len(samples)):
        lo, hi = max(0, i - window), min(len(samples), i + window + 1)
        chunk = samples[lo:hi]
        cx = sum(s.cx for s in chunk) / len(chunk)
        cy = sum(s.cy for s in chunk) / len(chunk)
        smoothed.append(FaceSample(t=samples[i].t, cx=cx, cy=cy))
    return smoothed


def build_pan_expr(samples: List[FaceSample], attr: str, src_dim: int, crop_dim: int) -> str:
    """
    Builds an ffmpeg eval expression (in terms of `t`) for the crop filter's
    x or y offset in source pixels, piecewise-linearly interpolating between
    smoothed face-center samples and clamping so the crop never leaves frame.
    """
    max_offset = max(0, src_dim - crop_dim)

    def offset_for(sample: FaceSample) -> float:
        center_frac = sample.cx if attr == "x" else sample.cy
        px = center_frac * src_dim - crop_dim / 2
        return min(max(px, 0), max_offset)

    if not samples:
        return str(max_offset // 2)

    times = [s.t for s in samples]
    offsets = [offset_for(s) for s in samples]

    expr = f"{offsets[-1]:.1f}"
    for i in range(len(times) - 2, -1, -1):
        t0, t1 = times[i], times[i + 1]
        v0, v1 = offsets[i], offsets[i + 1]
        if t1 <= t0:
            continue
        seg = f"({v0:.1f}+({v1:.1f}-{v0:.1f})*(t-{t0:.2f})/({t1:.2f}-{t0:.2f}))"
        expr = f"if(lt(t,{t1:.2f}),{seg},{expr})"
    expr = f"if(lt(t,{times[0]:.2f}),{offsets[0]:.1f},{expr})"
    return expr
