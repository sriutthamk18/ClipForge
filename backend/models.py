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
    caption_style: Literal["bold_pop", "minimal_clean", "karaoke"] = "bold_pop"
    min_duration: int = Field(15, ge=5, le=180)
    max_duration: int = Field(60, ge=5, le=180)
    max_clips: int = Field(8, ge=1, le=10)
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
    file: Optional[str] = None  # relative download path, set once rendered


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
