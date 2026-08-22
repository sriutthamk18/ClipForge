"""
Sends the timestamped transcript to Gemini and asks it to propose the best
short-form clip candidates, each with a virality score used for ranking.
"""
import json
import re
from typing import List

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from transcriber import Segment, segments_to_prompt_text

_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set on the server.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


PROMPT_TEMPLATE = """You are an expert short-form video producer who has cut hundreds of \
viral TikTok/Reels/Shorts clips from long-form podcasts, interviews and talks.

Below is a timestamped transcript of a video (format: [mm:ss] text).

Find up to {max_clips} of the best possible short clips for vertical short-form video -- \
but only ones that are genuinely strong. If this video only contains 3 or 5 truly \
clip-worthy moments, return 3 or 5. Never pad the list with mediocre or repetitive \
clips just to reach {max_clips}.

Each clip you do include must:
- Be between {min_duration} and {max_duration} seconds long.
- Start and end on a clean sentence/thought boundary -- never mid-sentence.
- Work with ZERO context from the rest of the video (a cold viewer must understand \
and be hooked within the first 2 seconds).
- Have a strong hook, a payoff (insight, punchline, twist, emotional beat, or \
concrete takeaway), and ideally a natural "loop" or ending line.
- Not overlap with another clip you propose.

Score each clip 0-100 on realistic short-form virality potential (hook strength, \
emotional charge, quotability, novelty, pacing) -- be a harsh, discerning judge, \
not everything is a 90.

Return ONLY a JSON array (no markdown fences, no commentary), sorted by \
virality_score descending, in this exact shape:
[
  {{
    "start_seconds": 123.0,
    "end_seconds": 168.0,
    "title": "Short punchy title for the clip (under 60 chars)",
    "hook": "The exact opening line/hook, verbatim from the transcript",
    "virality_score": 87,
    "reasoning": "One sentence on why this clip works for short-form"
  }}
]

TRANSCRIPT:
{transcript}
"""


def find_highlights(
    segments: List[Segment], min_duration: int, max_duration: int, max_clips: int
) -> List[dict]:
    client = _get_client()
    prompt = PROMPT_TEMPLATE.format(
        max_clips=max_clips,
        min_duration=min_duration,
        max_duration=max_duration,
        transcript=segments_to_prompt_text(segments),
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        candidates = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini returned non-JSON output: {e}\n{raw[:500]}")

    cleaned = []
    for c in candidates:
        try:
            start = float(c["start_seconds"])
            end = float(c["end_seconds"])
            if end <= start:
                continue
            cleaned.append({
                "start": start,
                "end": end,
                "title": str(c.get("title", "Untitled clip"))[:80],
                "hook": str(c.get("hook", "")),
                "virality_score": int(c.get("virality_score", 50)),
                "reasoning": str(c.get("reasoning", "")),
            })
        except (KeyError, TypeError, ValueError):
            continue

    cleaned.sort(key=lambda c: c["virality_score"], reverse=True)
    return cleaned[:max_clips]
