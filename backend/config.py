import os
from dotenv import load_dotenv

load_dotenv()

# --- Required ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# --- Tunable ---
# Safe default that is broadly available. You can switch to a newer model
# (e.g. "gemini-3.5-flash") once you've confirmed it's enabled on your key.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Where downloaded source videos and rendered clips live.
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
SOURCE_DIR = os.path.join(DATA_DIR, "sources")
CLIPS_DIR = os.path.join(DATA_DIR, "clips")
JOBS_DIR = os.path.join(DATA_DIR, "jobs")

for d in (DATA_DIR, SOURCE_DIR, CLIPS_DIR, JOBS_DIR):
    os.makedirs(d, exist_ok=True)

# faster-whisper model size. "base" is a good CPU-friendly default.
# Bump to "small" or "medium" for better caption accuracy if your host has the CPU/RAM.
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")

# Long videos are transcribed in chunks (not one giant pass) to keep memory/CPU
# bounded on small free-tier hosts. This is purely an internal processing detail --
# it doesn't change what the final transcript covers, just how it's built.
CHUNK_SECONDS = int(os.environ.get("CHUNK_SECONDS", "1200"))  # 20 min per chunk

# Max source video length ClipForge will process, in seconds (safety limit for a free tool).
MAX_SOURCE_SECONDS = int(os.environ.get("MAX_SOURCE_SECONDS", "5400"))  # 90 min

ASPECT_RATIOS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}
