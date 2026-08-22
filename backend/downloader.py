"""
Downloads a source video (and, when available, its subtitles/captions) using yt-dlp.
yt-dlp supports YouTube plus a wide range of other platforms (Vimeo, X/Twitter,
Facebook, Twitch clips, etc.) out of the box. Platforms with hard DRM or that
require login (e.g. most Instagram/TikTok posts) are not guaranteed to work in
a free, cookie-less deploy -- see README for notes.
"""
import os
import uuid

import yt_dlp

from config import SOURCE_DIR, MAX_SOURCE_SECONDS


class DownloadError(Exception):
    pass


def download_source(url: str) -> dict:
    """Downloads video + auto/manual subtitles if present. Returns metadata dict."""
    video_id = str(uuid.uuid4())
    out_template = os.path.join(SOURCE_DIR, f"{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-orig"],
        "subtitlesformat": "vtt",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        duration = info.get("duration") or 0
        if duration and duration > MAX_SOURCE_SECONDS:
            raise DownloadError(
                f"Video is {int(duration/60)} min long; this deploy caps at "
                f"{MAX_SOURCE_SECONDS // 60} min. Adjust MAX_SOURCE_SECONDS if you "
                f"control the server."
            )
        ydl.download([url])

    # Locate the actual output file (extension resolved by yt-dlp/ffmpeg merge).
    video_path = None
    subtitle_path = None
    for fname in os.listdir(SOURCE_DIR):
        if not fname.startswith(video_id):
            continue
        full = os.path.join(SOURCE_DIR, fname)
        if fname.endswith(".vtt"):
            subtitle_path = full
        elif fname.endswith((".mp4", ".mkv", ".webm")):
            video_path = full

    if not video_path:
        raise DownloadError("yt-dlp finished but no video file was found on disk.")

    return {
        "video_id": video_id,
        "video_path": video_path,
        "subtitle_path": subtitle_path,
        "title": info.get("title") or "Untitled",
        "duration": info.get("duration") or 0,
    }
