"""
Advanced caption system with multiple text effects, color themes, custom colors,
font sizing, styling, shadows, backgrounds, and placement presets.
"""
from dataclasses import dataclass
from typing import List, Literal

from transcriber import Word


@dataclass
class CaptionStyle:
    key: str
    label: str
    effect: Literal["pop", "karaoke", "wave", "slide", "solid"]
    color_preset: str
    custom_color: str  # &HAABBGGRR or None for preset
    font_size: int
    bold: bool
    italic: bool
    outline_width: int
    shadow: bool
    background: Literal["none", "box", "bar"]
    placement: Literal["top", "center", "bottom"]


# Popular color presets (primary, highlight, outline)
COLOR_PRESETS = {
    "neon": {
        "primary": "&H00FFFFFF",
        "highlight": "&H00FF00FF",
        "outline": "&H00000000",
        "label": "Neon",
    },
    "pastel": {
        "primary": "&H00E8D5F2",
        "highlight": "&H00F5A9D0",
        "outline": "&H00705070",
        "label": "Pastel",
    },
    "classic": {
        "primary": "&H00FFFFFF",
        "highlight": "&H00FFFFFF",
        "outline": "&H00000000",
        "label": "Classic",
    },
    "retro": {
        "primary": "&H0000D0FF",
        "highlight": "&H0000F0FF",
        "outline": "&H00000000",
        "label": "Retro Gold",
    },
    "minimal": {
        "primary": "&H00D0D0D0",
        "highlight": "&H00D0D0D0",
        "outline": "&H00000000",
        "label": "Minimal",
    },
    "vibrant": {
        "primary": "&H0000FFFF",
        "highlight": "&H00FF0080",
        "outline": "&H00000000",
        "label": "Vibrant",
    },
}

# Placement alignment (ASS numpad: 1=bottom-left, 2=bottom-center, 3=bottom-right, etc.)
PLACEMENT_ALIGNMENT = {
    "top": 8,
    "center": 5,
    "bottom": 2,
}

PLACEMENT_MARGIN = {
    "top": 60,
    "center": 0,
    "bottom": 140,
}


def _get_color_values(style: CaptionStyle) -> dict:
    """Resolve color from custom or preset."""
    if style.custom_color:
        c = style.custom_color
        return {
            "primary": c,
            "highlight": c,
            "outline": "&H00000000",
        }
    return COLOR_PRESETS.get(style.color_preset, COLOR_PRESETS["classic"])


def _fmt_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _build_pop_effect(word: Word, color: str) -> str:
    """Word grows as spoken, shrinks after."""
    dur_cs = int(round((word.end - word.start) * 100))
    half = dur_cs // 2
    return (
        f"{{\\k0\\scale120}}{word.text}{{\\k{half}\\scale100}}"
        f"{{\\k{half}\\scale80}}"
    )


def _build_karaoke_effect(word: Word, highlight: str, primary: str) -> str:
    """Word fills in with highlight color as spoken."""
    dur_cs = max(1, int(round((word.end - word.start) * 100)))
    return f"{{\\k{dur_cs}\\1c{highlight}}}{word.text}{{\\1c{primary}}}"


def _build_wave_effect(word: Word, index: int, color: str) -> str:
    """Word bobs up and down in a wave."""
    import math
    offset = int(round(8 * math.sin(index * 0.5)))
    return f"{{\\pos(,{offset})}}{word.text}"


def _build_slide_effect(word: Word, color: str) -> str:
    """Word slides in from left."""
    dur_cs = max(1, int(round((word.end - word.start) * 100)))
    return f"{{\\k0\\move(-500,0,0,0,0,{dur_cs})}}{word.text}"


def _build_solid_effect(word: Word, color: str) -> str:
    """Plain text, no effect."""
    return word.text


def _group_words(words: List[Word], group_size: int):
    for i in range(0, len(words), group_size):
        yield words[i:i + group_size]


def _build_events(style: CaptionStyle, words: List[Word]) -> List[str]:
    colors = _get_color_values(style)
    primary = colors["primary"]
    highlight = colors["highlight"]
    outline = colors["outline"]
    
    events = []
    word_idx = 0

    for group in _group_words(words, max(1, style.font_size // 20)):
        if not group:
            continue
        g_start, g_end = group[0].start, group[-1].end

        text_parts = []
        for w in group:
            if style.effect == "pop":
                text_parts.append(_build_pop_effect(w, primary))
            elif style.effect == "karaoke":
                text_parts.append(_build_karaoke_effect(w, highlight, primary))
            elif style.effect == "wave":
                text_parts.append(_build_wave_effect(w, word_idx, primary))
                word_idx += 1
            elif style.effect == "slide":
                text_parts.append(_build_slide_effect(w, primary))
            else:  # solid
                text_parts.append(_build_solid_effect(w, primary))
            text_parts.append(" ")

        text = "".join(text_parts).strip()
        events.append(
            f"Dialogue: 0,{_fmt_ts(g_start)},{_fmt_ts(g_end)},Default,,0,0,0,,{text}"
        )

    return events


def _build_header(style: CaptionStyle, video_w: int, video_h: int) -> str:
    """ASS file header with style definition."""
    colors = _get_color_values(style)
    primary = colors["primary"]
    highlight = colors["highlight"]
    outline = colors["outline"]
    
    font = "Arial Black" if style.bold else "Arial"
    weight = -1 if style.bold else 0
    italic = -1 if style.italic else 0
    alignment = PLACEMENT_ALIGNMENT[style.placement]
    margin_v = PLACEMENT_MARGIN[style.placement]
    shadow = 2 if style.shadow else 0
    
    bg_color = "&H80000000" if style.background == "box" else "&H00000000"

    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{style.font_size},{primary},{highlight},{outline},{bg_color},{weight},{italic},0,0,100,100,0,0,1,{style.outline_width},{shadow},{alignment},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass_file(
    path: str,
    style: CaptionStyle,
    clip_words: List[Word],
    clip_start: float,
    video_w: int,
    video_h: int,
) -> None:
    # Rebase words to clip-relative time
    rebased = [
        Word(start=w.start - clip_start, end=w.end - clip_start, text=w.text)
        for w in clip_words
    ]

    header = _build_header(style, video_w, video_h)
    events = _build_events(style, rebased)

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
