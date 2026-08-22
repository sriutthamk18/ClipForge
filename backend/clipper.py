"""
Cuts a clip out of the source video and fits it to the target aspect ratio.

Two crop strategies:
- Face-tracked pan: when the source is wider (relative to its height) than
  the target box -- the common horizontal-video-to-vertical-clip case -- we
  crop a target_w:target_h-shaped window out of full source height and pan
  its x position over time to follow the detected speaker, via facetrack.py.
- Static blurred-fill: fallback for when tracking is off, no faces were
  found, or the source is already narrower than the target (nothing to pan
  across), using a blurred copy of the frame to fill the gap with no bars.

Either way, captions are burned in as a final pass via the `ass` filter.
"""
import json
import os
import subprocess

from config import ASPECT_RATIOS, CLIPS_DIR
import facetrack


def _probe_dims(path: str):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    info = json.loads(proc.stdout or "{}")
    stream = (info.get("streams") or [{}])[0]
    return stream.get("width", 0), stream.get("height", 0)


def _static_fill_filter(target_w: int, target_h: int) -> str:
    """Blurred-background letterbox fill -- no panning, just centers everything."""
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},gblur=sigma=20[bg_blur];"
        f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg_fit];"
        f"[bg_blur][fg_fit]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
    )


def _face_pan_filter(
    source_path: str, start: float, end: float, target_w: int, target_h: int
) -> str:
    """
    Crops a target_w:target_h window (scaled up from source resolution) out
    of the full source height and pans its x-offset over time to track the
    speaker's face, then scales down to the exact output size.
    Returns None if tracking isn't applicable/useful for this source.
    """
    samples, src_w, src_h = facetrack.sample_faces(source_path, start, end)
    if not src_w or not src_h:
        return None

    target_aspect = target_w / target_h
    source_aspect = src_w / src_h

    if source_aspect <= target_aspect:
        return None
    if not samples:
        return None

    samples = facetrack.smooth_samples(samples)

    crop_h = src_h
    crop_w = int(round(crop_h * target_aspect))
    crop_w = min(crop_w, src_w)

    x_expr = facetrack.build_pan_expr(samples, "x", src_w, crop_w)

    return (
        f"crop=w={crop_w}:h={crop_h}:x='{x_expr}':y=0,"
        f"scale={target_w}:{target_h},format=yuv420p"
    )


def render_clip(
    source_path: str,
    clip_id: str,
    start: float,
    end: float,
    aspect_ratio: str,
    ass_path: str = None,
    track_faces: bool = True,
) -> str:
    target_w, target_h = ASPECT_RATIOS[aspect_ratio]
    out_path = os.path.join(CLIPS_DIR, f"{clip_id}.mp4")
    duration = max(0.1, end - start)

    crop_filter = None
    if track_faces:
        try:
            crop_filter = _face_pan_filter(source_path, start, end, target_w, target_h)
        except Exception:
            crop_filter = None

    if crop_filter is None:
        crop_filter = _static_fill_filter(target_w, target_h)

    vf_parts = [crop_filter]
    if ass_path:
        escaped = ass_path.replace("\\", "/").replace(":", "\\:")
        vf_parts.append(f"ass='{escaped}'")

    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", source_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        out_path,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for clip {clip_id}:\n{proc.stderr[-2000:]}")

    return out_path
