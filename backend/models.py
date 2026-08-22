import threading
import time
import uuid
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

JobStatus = Literal[
    "queued", "downloading", "transcribing", "analyzing",
    "rendering", "done", "error",
]


class ClipRequest(BaseModel):
    url: str
    aspect_ratio: Literal["9:16", "1:1", "4:5", "16:9"] = "9:16"
    min_duration: int = Field(15, ge=5, le=180)
    max_duration: int = Field(60, ge=5, le=180)
    max_clips: int = Field(8, ge=1, le=10)
    
    # Caption styling
    caption_effect: Literal["pop", "karaoke", "wave", "slide", "solid"] = "karaoke"
    caption_color: Literal["neon", "pastel", "classic", "retro", "minimal", "vibrant"] = "neon"
    caption_custom_color: Optional[str] = None
    caption_font_size: int = Field(76, ge=20, le=150)
    caption_bold: bool = False
    caption_italic: bool = False
    caption_outline_width: int = Field(2, ge=0, le=6)
    caption_shadow: bool = True
    caption_background: Literal["none", "box", "bar"] = "none"
    caption_placement: Literal["top", "center", "bottom"] = "bottom"
    
    burn_captions: bool = True
    track_faces: bool = True


class ClipResult(BaseModel):
    clip_id: str
    title: str
    hook: str
    start: float
    end: float
    duration: float
    virality_score: int
    reasoning: str
    file: Optional[str] = None


class Job(BaseModel):
    id: str
    status: JobStatus = "queued"
    progress_message: str = "Queued"
    error: Optional[str] = None
    request: ClipRequest
    source_title: Optional[str] = None
    clips: List[ClipResult] = []
    created_at: float = Field(default_factory=time.time)


class JobStore:
    """Simple thread-safe in-memory job store (fine for a single-process deploy)."""

    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()

    def create(self, request: ClipRequest) -> Job:
        job = Job(id=str(uuid.uuid4()), request=request)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for k, v in kwargs.items():
                setattr(job, k, v)
            return job


jobs = JobStore()
