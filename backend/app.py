import os
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import captions
import clipper
import downloader
import transcriber
from config import ASPECT_RATIOS, CLIPS_DIR
from highlighter import find_highlights
from models import ClipRequest, ClipResult, Job, jobs

app = FastAPI(title="ClipForge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/styles")
def list_styles():
    return {
        "caption_effects": ["pop", "karaoke", "wave", "slide", "solid"],
        "caption_colors": {k: v["label"] for k, v in captions.COLOR_PRESETS.items()},
        "caption_placements": ["top", "center", "bottom"],
        "caption_backgrounds": ["none", "box", "bar"],
        "aspect_ratios": list(ASPECT_RATIOS.keys()),
    }


@app.post("/api/clip")
def create_clip_job(request: ClipRequest, background_tasks: BackgroundTasks):
    if request.min_duration >= request.max_duration:
        raise HTTPException(400, "min_duration must be less than max_duration")
    job = jobs.create(request)
    background_tasks.add_task(_run_pipeline, job.id)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/download/{clip_id}")
def download_clip(clip_id: str):
    path = os.path.join(CLIPS_DIR, f"{clip_id}.mp4")
    if not os.path.exists(path):
        raise HTTPException(404, "Clip not found")
    return FileResponse(path, media_type="video/mp4", filename=f"{clip_id}.mp4")


def _run_pipeline(job_id: str):
    job = jobs.get(job_id)
    req = job.request
    try:
        jobs.update(job_id, status="downloading", progress_message="Downloading source video…")
        source = downloader.download_source(req.url)
        jobs.update(job_id, source_title=source["title"])

        jobs.update(job_id, status="transcribing", progress_message="Transcribing audio in chunks…")
        segments = transcriber.build_full_transcript(
            source["video_path"], source["subtitle_path"], source["duration"]
        )

        jobs.update(job_id, status="analyzing", progress_message="Finding the best moments with Gemini…")
        candidates = find_highlights(
            segments, req.min_duration, req.max_duration, req.max_clips
        )
        if not candidates:
            raise RuntimeError("Gemini didn't return any usable clip candidates for this video.")

        jobs.update(job_id, status="rendering", progress_message=f"Rendering 0/{len(candidates)} clips…")

        results = []
        target_w, target_h = ASPECT_RATIOS[req.aspect_ratio]

        for i, c in enumerate(candidates):
            clip_id = str(uuid.uuid4())
            ass_path = None

            if req.burn_captions:
                clip_words = transcriber.get_clip_words(source["video_path"], c["start"], c["end"])
                if clip_words:
                    ass_path = os.path.join(CLIPS_DIR, f"{clip_id}.ass")
                    style = captions.CaptionStyle(
                        key="custom",
                        label="Custom",
                        effect=req.caption_effect,
                        color_preset=req.caption_color,
                        custom_color=req.caption_custom_color,
                        font_size=req.caption_font_size,
                        bold=req.caption_bold,
                        italic=req.caption_italic,
                        outline_width=req.caption_outline_width,
                        shadow=req.caption_shadow,
                        background=req.caption_background,
                        placement=req.caption_placement,
                    )
                    captions.write_ass_file(
                        ass_path, style, clip_words, c["start"],
                        target_w, target_h,
                    )

            clipper.render_clip(
                source["video_path"], clip_id, c["start"], c["end"],
                req.aspect_ratio, ass_path, track_faces=req.track_faces,
            )

            results.append(ClipResult(
                clip_id=clip_id,
                title=c["title"],
                hook=c["hook"],
                start=c["start"],
                end=c["end"],
                duration=round(c["end"] - c["start"], 1),
                virality_score=c["virality_score"],
                reasoning=c["reasoning"],
                file=f"/api/download/{clip_id}",
            ))
            jobs.update(
                job_id,
                clips=sorted(results, key=lambda r: r.virality_score, reverse=True),
                progress_message=f"Rendering {i + 1}/{len(candidates)} clips…",
            )

        jobs.update(job_id, status="done", progress_message="Done")

    except Exception as e:
        jobs.update(job_id, status="error", error=str(e), progress_message="Failed")


app.mount("/clips", StaticFiles(directory=CLIPS_DIR), name="clips")
