"""
Builds a segment-level transcript for the whole video (used for highlight
finding), and later, word-level transcripts for just the clips that get
selected (used for caption timing).

To keep memory/CPU bounded on small hosts, long videos are never decoded by
Whisper in one pass -- audio is pulled and transcribed in CHUNK_SECONDS
pieces. Each chunk is transcribed with a small overlap into its neighbors so
a sentence sitting exactly on a chunk boundary is never heard "cut in half";
when stitching results back together, each segment is credited to whichever
chunk's core (non-overlapping) range its midpoint falls in, so nothing is
duplicated. Platform-provided captions (vtt), when available, skip Whisper
entirely for this pass.
"""
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional

from faster_whisper import WhisperModel

from config import CHUNK_SECONDS, WHISPER_MODEL_SIZE

_whisper_model: Optional[WhisperModel] = None

# Extra audio pulled in on each side of a chunk purely so Whisper hears full
# context around the boundary. Segments from this padding are only kept if
# their midpoint lands in the *next/prev* chunk's core range (see below).
OVERLAP_SECONDS = 15.0


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str


def segments_to_prompt_text(segments: List[Segment]) -> str:
    """Compact [mm:ss] tagged transcript for the Gemini prompt."""
    lines = []
    for seg in segments:
        m, s = divmod(int(seg.start), 60)
        lines.append(f"[{m:02d}:{s:02d}] {seg.text.strip()}")
    return "\n".join(lines)


def _extract_audio_slice(video_path: str, start: float, end: float) -> str:
    """Extracts a mono 16kHz wav slice -- small and fast for Whisper to chew on."""
    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    duration = max(0.1, end - start)
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-i", video_path, "-t", str(duration),
        "-vn", "-ac", "1", "-ar", "16000", out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        os.unlink(out_path)
        raise RuntimeError(f"ffmpeg audio extraction failed:\n{proc.stderr[-1500:]}")
    return out_path


def _parse_vtt(path: str) -> List[Segment]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    time_re = re.compile(
        r"(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3}) --> "
        r"(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})"
    )

    def to_seconds(ts: str) -> float:
        parts = ts.split(":")
        if len(parts) == 3:
            h, m, s = parts
        else:
            h, (m, s) = 0, parts
        return int(h) * 3600 + int(m) * 60 + float(s)

    segments = []
    blocks = content.split("\n\n")
    for block in blocks:
        match = time_re.search(block)
        if not match:
            continue
        start, end = to_seconds(match.group(1)), to_seconds(match.group(2))
        text_lines = [
            l for l in block.split("\n")
            if l.strip() and not time_re.search(l) and "-->" not in l
        ]
        text = " ".join(text_lines)
        text = re.sub(r"<[^>]+>", "", text)
        if text.strip():
            segments.append(Segment(start=start, end=end, text=text.strip()))
    return segments


def build_full_transcript(
    video_path: str, subtitle_path: Optional[str], duration: float
) -> List[Segment]:
    """Segment-level transcript for the whole video, for highlight-finding."""
    if subtitle_path:
        try:
            segments = _parse_vtt(subtitle_path)
            if segments:
                return segments
        except Exception:
            pass

    model = _get_whisper()
    all_segments: List[Segment] = []
    core_start = 0.0

    while core_start < duration:
        core_end = min(duration, core_start + CHUNK_SECONDS)
        is_first, is_last = core_start == 0.0, core_end >= duration

        fetch_start = core_start if is_first else max(0.0, core_start - OVERLAP_SECONDS)
        fetch_end = core_end if is_last else min(duration, core_end + OVERLAP_SECONDS)

        audio_path = _extract_audio_slice(video_path, fetch_start, fetch_end)
        try:
            whisper_segments, _info = model.transcribe(
                audio_path, word_timestamps=False, vad_filter=True
            )
            for seg in whisper_segments:
                abs_start = seg.start + fetch_start
                abs_end = seg.end + fetch_start
                midpoint = (abs_start + abs_end) / 2
                if core_start <= midpoint < core_end or (is_last and midpoint == core_end):
                    all_segments.append(Segment(start=abs_start, end=abs_end, text=seg.text))
        finally:
            os.unlink(audio_path)

        core_start = core_end

    all_segments.sort(key=lambda s: s.start)
    return all_segments


def get_clip_words(video_path: str, start: float, end: float) -> List[Word]:
    """Word-level timestamps for a single short, already-selected clip -- used
    for caption timing. Cheap: only decodes the clip's own duration, not the
    whole source video."""
    model = _get_whisper()
    audio_path = _extract_audio_slice(video_path, start, end)
    words: List[Word] = []
    try:
        whisper_segments, _info = model.transcribe(
            audio_path, word_timestamps=True, vad_filter=True
        )
        for seg in whisper_segments:
            for w in (seg.words or []):
                words.append(Word(start=w.start + start, end=w.end + start, text=w.word.strip()))
    finally:
        os.unlink(audio_path)
    return words
