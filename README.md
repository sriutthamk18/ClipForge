# ClipForge — Free AI-Powered Clip Cutter

Paste a video link (YouTube, Vimeo, Twitter, etc.) → Gemini reads the transcript, finds the strongest short-form moments, scores them for virality, and ffmpeg cuts + crops + captions each one in your chosen aspect ratio. **Ranked by virality score**, fully customizable captions (5 text effects, 6+ colors, custom colors, fonts, shadows, backgrounds, placement).

No accounts, no watermarks, no paywall. Bring your own free Gemini API key.

## What's inside

```
clipforge/
  backend/
    app.py                 FastAPI routes + job pipeline
    downloader.py          yt-dlp: downloads video + captions
    transcriber.py         chunked Whisper: transcribes with overlap
    highlighter.py         Gemini: finds clips + virality scores
    captions.py            caption styles: pop, karaoke, wave, slide, solid
    clipper.py             ffmpeg: cuts, crops, face-tracks, burns captions
    facetrack.py           face detection + panning crop
    models.py              request/response/job models
    config.py              env vars
    requirements.txt
  frontend/
    index.html             single-page UI (responsive mobile-first)
  README.md

```

## How it works

1. **Download** — yt-dlp grabs the source video (+ captions if available) from YouTube/Vimeo/Twitter/etc.
2. **Transcribe** — Long videos are split into 20-min chunks with 15-sec overlap so no clips miss boundaries. Faster-Whisper transcribes each chunk (memory-efficient on free tiers).
3. **Analyze** — Gemini reads the timestamped transcript and proposes up to 10 genuinely strong clips (never pads with weak ones), scoring each 0–100 for viral potential.
4. **Render** — For each clip:
   - Cuts the segment from the source
   - Scales & crops to your aspect ratio (9:16, 1:1, 4:5, 16:9) with blurred-background fill (no black bars)
   - Detects speaker's face and pans the crop to follow them (optional, falls back to center-crop if no faces found)
   - Burns in captions with your chosen effect (pop, karaoke, wave, slide, solid), colors, fonts, shadows, backgrounds, placement
5. **Serve** — Clips ranked by virality score, download links in the UI.

## Setup & Deployment

### Local testing (Mac/Linux/Windows with Python 3.10+)

```bash
cd clipforge/backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Make sure ffmpeg is installed:
#   macOS:   brew install ffmpeg
#   Ubuntu:  sudo apt install ffmpeg
#   Windows: winget install ffmpeg

echo "GEMINI_API_KEY=your_key_here" > .env
uvicorn app:app --reload --port 8000
```

Get a free Gemini API key at https://aistudio.google.com/apikey

In another terminal, serve the frontend:
```bash
cd clipforge/frontend
python -m http.server 8080
```

Open `http://localhost:8080` in your browser. Leave "Backend URL" blank (both on same origin).

### Deploy to Render (free tier, always-on)

Render's free tier sleeps if idle, so it's slower than paid but totally free.

1. **Push to GitHub** (you've already done this!)

2. **Create Render service:**
   - Go to https://render.com
   - Sign in with GitHub
   - **New Web Service** → connect your `clipforge` repo
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Add environment variable: `GEMINI_API_KEY=your_key_here`
   - Deploy

3. **You'll get a public URL** like `https://clipforge-xyz.up.railway.app`. That's your backend.

4. **Host the frontend anywhere static:**
   - GitHub Pages (free, easiest)
   - Netlify / Vercel (free tiers)
   - Cloudflare Pages (free)
   - Or just open `frontend/index.html` directly and paste the backend URL in the "Backend URL" field

5. **Open on your phone** — just a bookmark away.

## Configuration (environment variables)

| Variable | Default | Notes |
|----------|---------|-------|
| `GEMINI_API_KEY` | (required) | Get at https://aistudio.google.com/apikey |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Switch to a newer model if your key supports it |
| `MAX_SOURCE_SECONDS` | `5400` | 90 minutes; raise if your host can handle longer videos |
| `CHUNK_SECONDS` | `1200` | 20-min chunks; smaller = more memory-efficient but slower |
| `WHISPER_MODEL_SIZE` | `base` | CPU-friendly default; try `small` or `medium` on a stronger host |

## Free tier limits & realistic expectations

**Gemini API:** Free tier limits vary (check https://ai.google.dev/pricing). For personal use (handful of videos/day), you won't hit limits.

**Render free tier:**
- **0.1 CPU, 512MB RAM** — fine for clips up to ~30 min source videos, slower on longer ones
- **Sleep after 15 min idle** — wakes up when you visit, takes ~30 sec to start
- **~750 compute hours/month** — unlimited for free

For a real, always-on experience, upgrade to **Render Starter** ($7/month) with real CPU and no sleep.

**Processing times** (rough, on free tier):
- 10-min video: ~5 min (download + transcribe + analyze + render 5-8 clips)
- 30-min video: ~15 min
- 60+ min: slow, might time out on free tier (consider splitting into parts and processing separately, or use the paid tier)

## Features

✅ **Text effects:** Pop (grows/shrinks), Karaoke (color fill), Wave (bounces), Slide (enters from side), Solid (none)  
✅ **Colors:** 6 presets (Neon, Pastel, Classic, Retro Gold, Minimal, Vibrant) + custom RGB color picker  
✅ **Typography:** Font size (20–150px), Bold, Italic, Outline width (none/thin/medium/thick), Shadow  
✅ **Captions placement:** Top, Center, Bottom  
✅ **Background options:** None, Semi-transparent box, Full bar  
✅ **Aspect ratios:** 9:16 (Reels/TikTok), 1:1 (Instagram), 4:5 (Instagram), 16:9 (YouTube Shorts)  
✅ **Face tracking:** Auto-pan crop to follow speaker (falls back to center-crop if no faces detected)  
✅ **Virality scoring:** Gemini ranks clips 0–100; only returns genuinely strong ones (never pads a weak list to hit 10)  

## Troubleshooting

**"Video is X min long; this deploy caps at Y min"**
- Raise `MAX_SOURCE_SECONDS` in `config.py` (or as an env var on your host)
- Or split the video manually and process each part

**Render times out or runs out of memory**
- Free tier is 512MB; long videos with many clips push this hard
- Switch `WHISPER_MODEL_SIZE=base` (already default, most CPU-efficient)
- Reduce `max_clips` in the UI (4–6 instead of 10)
- Or upgrade to Render Starter ($7/month)

**"ffmpeg failed" / "OpenCV can't find haarcascade"**
- Make sure ffmpeg is installed on the host
- OpenCV cascade comes bundled with `opencv-python-headless` (already in requirements)

**Captions look cut off or weird**
- Try different `caption_placement` (top/center/bottom)
- Reduce `caption_font_size` if they're clipping edges
- Try a different `caption_background` (box adds padding)

## Customization ideas

- Add more caption styles in `captions.py`
- Swap Whisper for a cloud transcription API (faster on a weak host)
- Add face-blurring or pixelation filters in `clipper.py`
- Store jobs in Redis/PostgreSQL instead of in-memory (for persistence across restarts)
- Add a download queue or batch-processing dashboard

## No credit card, no signup hell

This is designed for personal use. You own your clips, all processing is server-side (no cloud storage), and the free tier is genuinely free.

---

Questions? Open an issue or fork and customize!
```

5. Scroll down → **Commit changes**

Reply **"done"** when it's committed!
