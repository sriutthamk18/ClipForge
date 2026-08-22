"""
Advanced caption system with:
- 5 text effects (pop, karaoke, wave, slide, solid)
- 6 color presets + custom HTML color picker (converted to ASS &HAABBGGRR format)
- Font sizing, bold/italic, outline width, shadow, backgrounds, placement
"""
from dataclasses import dataclass
from typing import List, Literal, Optional
import math

from transcriber import Word


@dataclass
class CaptionStyle:
    """Style definition for captions. All colors are in ASS &HAABBGGRR format."""
    key: str
    label: str
    effect: Literal["pop", "karaoke", "wave", "slide", "solid"]
    color_preset: str
    custom_color: Optional[str]  # HTML #RRGGBB if user picked custom color
    font_size: int
    bold: bool
    italic: bool
    outline_width: int
    shadow: bool
    background: Literal["none", "box", "bar"]
    placement: Literal["top", "center", "bottom"]


# Popular color presets (in ASS &HAABBGGRR format)
COLOR_PRESETS = {
    "neon": {
        "primary": "&H00FFFFFF",   # white
        "highlight": "&H00FF00FF",  # magenta
        "outline": "&H00000000",    # black
        "label": "Neon",
    },
    "pastel": {
        "primary": "&H00E8D5F2",   # light pink
        "highlight": "&H00F5A9D0",  # pastel pink
        "outline": "&H00705070",    # dark purple
        "label": "Pastel",
    },
    "classic": {
        "primary": "&H00FFFFFF",   # white
        "highlight": "&H00FFFFFF",  # white
        "outline": "&H00000000",    # black
        "label": "Classic",
    },
    "retro": {
        "primary": "&H0000D0FF",   # gold (BGR: FFD000 -> 0000D0FF)
        "highlight": "&H0000F0FF",  # bright gold
        "outline": "&H00000000",    # black
        "label": "Retro Gold",
    },
    "minimal": {
        "primary": "&H00D0D0D0",   # light gray
        "highlight": "&H00D0D0D0",  # light gray
        "outline": "&H00000000",    # black
        "label": "Minimal",
    },
    "vibrant": {
        "primary": "&H0000FFFF",   # cyan (BGR: FFFF00 -> 0000FFFF)
        "highlight": "&H00FF0080",  # pink (BGR: 8000FF -> FF0080)
        "outline": "&H00000000",    # black
        "label": "Vibrant",
    },
}

PLACEMENT_ALIGNMENT = {
    "top": 8,      # ASS alignment: 8 = top-center
    "center": 5,   # 5 = middle-center
    "bottom": 2,   # 2 = bottom-center
}

PLACEMENT_MARGIN = {
    "top": 60,
    "center": 0,
    "bottom": 140,
}


def _hex_to_ass(hex_color: str) -> str:
    """Convert HTML #RRGGBB to ASS &HAABBGGRR (BGR order, alpha=00)."""
    if not hex_color or not hex_color.startswith("#"):
        return "&H00FFFFFF"  # fallback to white
    
    hex_color = hex_color.lstrip("#").upper()
    if len(hex_color) != 6:
        return "&H00FFFFFF"
    
    try:
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        # ASS format: &HAABBGGRR (swap R and B)
        return f"&H00{b}{g}{r}"
    except Exception:
        return "&H00FFFFFF"


def _get_colors(style: CaptionStyle) -> dict:
    """Resolve primary/highlight/outline colors from preset or custom."""
    if style.custom_color:
        c = _hex_to_ass(style.custom_color)
        return {
            "primary": c,
            "highlight": c,
            "outline": "&H00000000",  # black outline
        }
    return COLOR_PRESETS.get(style.color_preset, COLOR_PRESETS["classic"])


def _fmt_ts(seconds: float) -> str:
    """Format seconds as ASS timestamp: h:mm:ss.cc"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _smart_group_size(font_size: int, effect: str) -> int:
    """Decide how many words to group based on font size and effect."""
    # Larger font = fewer words visible at once; effects like pop/wave need smaller groups
    if effect in ("pop", "wave", "slide"):
        # These effects are visually busy, keep groups small
        if font_size >= 100:
            return 2
        elif font_size >= 70:
            return 3
        else:
            return 4
    elif effect == "karaoke":
        # Karaoke works well with slightly larger groups
        if font_size >= 100:
            return 3
        elif font_size >= 70:
            return 4
        else:
            return 5
    else:  # solid
        # Plain text can handle larger groups
        if font_size >= 100:
            return 4
        else:
            return 6


def _build_pop_effect(word: Word, highlight_color: str) -> str:
    """Word grows as spoken, shrinks after."""
    dur_cs = max(1, int(round((word.end - word.start) * 100)))
    half = dur_cs // 2
    return (
        f"{{\\k0\\scale120}}{word.text}{{\\k{half}\\scale100}}"
        f"{{\\k{half}\\scale80}}"
    )


def _build_karaoke_effect(word: Word, highlight_color: str, primary_color: str) -> str:
    """Word fills in with highlight color as spoken."""
    dur_cs = max(1, int(round((word.end - word.start) * 100)))
    return f"{{\\k{dur_cs}\\1c{highlight_color}}}{word.text}{{\\1c{primary_color}}}"


def _build_wave_effect(word: Word, word_index: int, primary_color: str) -> str:
    """Word bobs up and down in a wave."""
    offset = int(round(6 * math.sin(word_index * 0.4)))
    dur_cs = max(1, int(round((word.end - word.start) * 100)))
    return f"{{\\k0\\move(0,{offset},0,{offset},{dur_cs})}}{word.text}"


def _build_slide_effect(word: Word, primary_color: str) -> str:
    """Word slides in from left."""
    dur_cs = max(1, int(round((word.end - word.start) * 100)))
    return f"{{\\k0\\move(-300,0,0,0,0,{dur_cs})}}{word.text}"


def _build_solid_effect(word: Word, primary_color: str) -> str:
    """Plain text, no effect."""
    return word.text


def _build_events(style: CaptionStyle, words: List[Word]) -> List[str]:
    """Build ASS Dialogue events for all words."""
    if not words:
        return []
    
    colors = _get_colors(style)
    primary = colors["primary"]
    highlight = colors["highlight"]
    
    group_size = _smart_group_size(style.font_size, style.effect)
    events = []
    word_idx = 0

    for group in _group_words(words, group_size):
        if not group:
            continue
        g_start, g_end = group[0].start, group[-1].end

        text_parts = []
        for w in group:
            if style.effect == "pop":
                text_parts.append(_build_pop_effect(w, highlight))
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


def _group_words(words: List[Word], group_size: int):
    """Yield groups of words."""
    for i in range(0, len(words), group_size):
        yield words[i:i + group_size]


def _build_header(style: CaptionStyle, video_w: int, video_h: int) -> str:
    """Build ASS file header with style definition."""
    colors = _get_colors(style)
    primary = colors["primary"]
    highlight = colors["highlight"]
    outline = colors["outline"]
    
    font = "Arial Black" if style.bold or style.effect == "karaoke" else "Arial"
    weight = "-1" if style.bold else "0"
    italic = "-1" if style.italic else "0"
    alignment = PLACEMENT_ALIGNMENT[style.placement]
    margin_v = PLACEMENT_MARGIN[style.placement]
    shadow = "2" if style.shadow else "0"
    
    # Background: none = transparent, box = semi-transparent box, bar = full-width bar
    if style.background == "box":
        bg_color = "&H80000000"  # semi-transparent black
    else:
        bg_color = "&H00000000"  # fully transparent

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
    """Write a complete ASS subtitle file for the clip."""
    if not clip_words:
        return
    
    # Rebase word times to clip-relative (0 = start of clip)
    rebased = [
        Word(start=w.start - clip_start, end=w.end - clip_start, text=w.text)
        for w in clip_words
    ]

    header = _build_header(style, video_w, video_h)
    events = _build_events(style, rebased)

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
