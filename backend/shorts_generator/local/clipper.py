"""Local clipping: ffmpeg subclip + OpenCV face-aware vertical crop + burned-in subtitles.

Stages per highlight:
  1. Cut source video to [start, end] with ffmpeg (libx264, aac).
  2. Generate TikTok/Reels style ASS subtitle file from transcript segments.
  3. Reframe to vertical (9:16) with OpenCV face-tracking or center crop.
  4. Mux audio and burn ASS subtitles using FFmpeg libx264 (H.264/yuv420p)
     with +faststart for 100% browser preview and mobile compatibility.
"""
import difflib
import gc
import math
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..config import LOCAL_OUTPUT_DIR
from ..job_manager import JobCancelledException, JobTimeoutException, log_job_message
from .gaming_presets import (
    BOTTOM_HEIGHT,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FACECAM_2L_HEIGHT,
    GAMEPLAY_2L_HEIGHT,
    GAMING_PRESETS,
    build_gameplay_fallback_filter_complex,
    build_gaming_filter_complex,
    get_gaming_layout,
    resolve_gaming_crop_boxes,
)

FONTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts"))


def _ratio(aspect_ratio: str) -> float:
    """Parse '9:16' → 9/16, '1:1' → 1.0."""
    try:
        w, h = aspect_ratio.split(":")
        return float(w) / float(h)
    except (ValueError, ZeroDivisionError):
        return 9.0 / 16.0


def _format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp: H:MM:SS.cc"""
    total_cs = max(0, int(round(seconds * 100)))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _format_vtt_time(seconds: float) -> str:
    """Format seconds into WebVTT timestamp: HH:MM:SS.mmm"""
    total_ms = max(0, int(round(seconds * 1000)))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _parse_ass_time(timestamp_str: str) -> float:
    """Parse ASS timestamp 'H:MM:SS.cc' into seconds (float)."""
    parts = timestamp_str.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid ASS timestamp format: {timestamp_str!r}")
    h = int(parts[0])
    m = int(parts[1])
    s_cs = parts[2].split(".")
    s = int(s_cs[0])
    cs = int(s_cs[1]) if len(s_cs) > 1 else 0
    return h * 3600.0 + m * 60.0 + s + (cs / 100.0)


def _parse_vtt_time(timestamp_str: str) -> float:
    """Parse WebVTT timestamp 'HH:MM:SS.mmm' or 'MM:SS.mmm' into seconds (float)."""
    ts = timestamp_str.strip()
    if "." in ts:
        time_part, ms_part = ts.split(".", 1)
        ms = int(ms_part.ljust(3, "0")[:3])
    else:
        time_part, ms = ts, 0
    parts = [int(p) for p in time_part.split(":")]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        raise ValueError(f"Invalid WebVTT timestamp format: {timestamp_str!r}")
    return h * 3600.0 + m * 60.0 + s + (ms / 1000.0)


def _probe_media_duration(media_path: str) -> float:
    """Extract media duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            media_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        val = float(res.stdout.strip())
        return val if math.isfinite(val) and val > 0 else 0.0
    except Exception:
        return 0.0


def _chunk_words(words: List[str], target_chunk_size: int = 4) -> List[List[str]]:
    """Evenly balance words across small chunks for dynamic TikTok-style captions."""
    n = len(words)
    if n <= target_chunk_size + 1:
        return [words]
    num_chunks = max(1, (n + target_chunk_size - 1) // target_chunk_size)
    k, m = divmod(n, num_chunks)
    chunks = []
    start = 0
    for i in range(num_chunks):
        end = start + k + (1 if i < m else 0)
        chunks.append(words[start:end])
        start = end
    return chunks


def _compute_word_centiseconds(
    words: List[str],
    total_duration: float,
    explicit_words: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Compute per-word centisecond durations for kinetic/karaoke subtitle synchronization."""
    total_cs = max(1, int(round(total_duration * 100)))
    n = len(words)
    if n == 0:
        return []
    if n == 1:
        return [{"word": words[0], "duration_cs": total_cs}]

    # If explicit word timings are available and match count
    if explicit_words and len(explicit_words) == n:
        raw_durs = [
            max(0.01, float(ew.get("end", 0.0) - ew.get("start", 0.0)))
            for ew in explicit_words
        ]
        sum_raw = sum(raw_durs)
        if sum_raw > 0:
            alloc = [max(1, int(round(total_cs * (d / sum_raw)))) for d in raw_durs]
        else:
            alloc = [max(1, total_cs // n)] * n
    else:
        # Character-length weighted distribution for natural speech pacing
        lengths = [max(1, len(w)) for w in words]
        total_len = sum(lengths)
        alloc = [max(1, int(round(total_cs * (l / total_len)))) for l in lengths]

    # Adjust rounding discrepancy on largest allocation to preserve exact cue duration
    diff = total_cs - sum(alloc)
    max_idx = alloc.index(max(alloc))
    alloc[max_idx] = max(1, alloc[max_idx] + diff)

    return [{"word": words[i], "duration_cs": alloc[i]} for i in range(n)]


def build_validated_cues(
    segments: Optional[List[Dict]],
    clip_start: float,
    clip_end: float,
    source_duration: Optional[float] = None,
    untrusted_spans: Optional[List[Dict]] = None,
    target_chunk_size: int = 4,
) -> List[Dict]:
    """Generate a single, authoritative, validated list of subtitle cues for a clip.

    Guarantees:
    1. Input validation & quarantine:
       - Every segment must be a dict with finite float start and end, and non-empty text.
       - Rejects/quarantines inverted segments (end < start).
       - Rejects/quarantines non-finite (NaN, Inf) or negative (start < 0) timestamps.
       - Rejects/quarantines segments exceeding source_duration (+ tolerance 0.5s).
       - Rejects/quarantines segments marked untrusted or overlapping any untrusted_spans.
       - Skips segments that do not intersect [clip_start, clip_end].
    2. Overlap preservation:
       - Valid overlapping segments (e.g. multi-speaker turns) are BOTH preserved.
       - Cues are sorted chronologically by start time, then by end time.
    3. Non-shifting & No hallucination:
       - Cues strictly correspond to actual transcribed words within the segment.
       - Silence or gaps between segments/words are NOT bridged or filled with dummy text/duration.
       - Rejection of an anomaly does NOT shift the timing of subsequent cues.
    4. Single source of truth:
       - Words within each valid segment are chunked using target_chunk_size (default 4).
       - Each cue has:
           'start': float (seconds relative to clip start, rounded to 3 decimals, >= 0.0)
           'end': float (seconds relative to clip start, rounded to 3 decimals, <= clip_dur)
           'text': str (uppercase text)
           'start_abs': float (absolute timestamp in source video)
           'end_abs': float (absolute timestamp in source video)
    """
    if not segments or not isinstance(segments, list):
        return []

    try:
        clip_st = float(clip_start)
        clip_et = float(clip_end)
    except (ValueError, TypeError):
        return []

    if not math.isfinite(clip_st) or not math.isfinite(clip_et) or clip_et <= clip_st:
        return []

    clip_st = max(0.0, clip_st)
    clip_dur = clip_et - clip_st

    max_source_dur = float("inf")
    if source_duration is not None and isinstance(source_duration, (int, float)):
        if math.isfinite(source_duration) and source_duration > 0:
            max_source_dur = float(source_duration) + 0.5

    clean_untrusted: List[Tuple[float, float]] = []
    if untrusted_spans and isinstance(untrusted_spans, list):
        for sp in untrusted_spans:
            if isinstance(sp, dict):
                try:
                    s_u = float(sp.get("start", 0.0))
                    e_u = float(sp.get("end", 0.0))
                    if math.isfinite(s_u) and math.isfinite(e_u) and e_u >= s_u:
                        clean_untrusted.append((s_u, e_u))
                except (ValueError, TypeError):
                    continue

    cues: List[Dict] = []

    for seg in segments:
        if not isinstance(seg, dict):
            continue

        raw_s = seg.get("start")
        raw_e = seg.get("end")
        if isinstance(raw_s, bool) or isinstance(raw_e, bool):
            continue

        try:
            s_start = float(raw_s)
            s_end = float(raw_e)
        except (ValueError, TypeError):
            continue

        if not math.isfinite(s_start) or not math.isfinite(s_end):
            continue

        if s_start < 0.0:
            continue

        # Reject inverted or zero-duration range (end <= start)
        if s_end <= s_start:
            continue

        # Reject segments that exceed source media duration
        if s_start > max_source_dur or s_end > max_source_dur:
            continue

        # Reject segments explicitly marked untrusted
        if bool(seg.get("untrusted", False)):
            continue

        # Reject segments crossing any untrusted span
        crosses_untrusted = False
        for u_st, u_et in clean_untrusted:
            if s_start < u_et - 0.05 and s_end > u_st + 0.05:
                crosses_untrusted = True
                break
        if crosses_untrusted:
            continue

        # Skip segments outside the clip window
        if s_end <= clip_st or s_start >= clip_et:
            continue

        # Extract and validate explicit word timings if present on segment
        seg_explicit_words = seg.get("words")
        clean_explicit: List[Dict] = []
        if isinstance(seg_explicit_words, list) and len(seg_explicit_words) > 0:
            for ew in seg_explicit_words:
                if not isinstance(ew, dict):
                    continue
                w_str = str(ew.get("word", "")).strip()
                if not w_str:
                    continue
                try:
                    w_s = float(ew.get("start", 0.0))
                    w_e = float(ew.get("end", 0.0))
                except (ValueError, TypeError):
                    continue
                if not math.isfinite(w_s) or not math.isfinite(w_e) or w_e <= w_s:
                    continue
                # Only keep words within or overlapping the clip window
                if w_e <= clip_st + 0.02 or w_s >= clip_et - 0.02:
                    continue
                clean_explicit.append({
                    "word": w_str,
                    "start": w_s,
                    "end": w_e,
                    "rel_start": max(0.0, w_s - clip_st),
                    "rel_end": min(clip_dur, w_e - clip_st),
                })

        if clean_explicit:
            word_chunks = _chunk_words(clean_explicit, target_chunk_size=target_chunk_size)
            for idx, ch in enumerate(word_chunks):
                ch_words_text = [w["word"].upper() for w in ch]
                c_start = ch[0]["rel_start"]
                c_end = ch[-1]["rel_end"]
                if c_end <= c_start:
                    c_end = min(clip_dur, c_start + 0.1)

                c_dur = c_end - c_start
                ch_word_timings = _compute_word_centiseconds(
                    ch_words_text,
                    total_duration=c_dur,
                    explicit_words=ch,
                )

                c_start_r = round(c_start, 3)
                c_end_r = round(c_end, 3)
                cue_text = " ".join(ch_words_text)

                cues.append({
                    "start": c_start_r,
                    "end": c_end_r,
                    "text": cue_text,
                    "start_abs": round(clip_st + c_start, 3),
                    "end_abs": round(clip_st + c_end, 3),
                    "words": ch_word_timings,
                })
        else:
            rel_start = max(0.0, s_start - clip_st)
            rel_end = min(clip_dur, s_end - clip_st)
            duration = rel_end - rel_start
            if duration <= 0.05:
                continue

            raw_text = str(seg.get("text", "")).strip().replace("\r", " ").replace("\n", " ")
            if not raw_text:
                continue
            words = raw_text.split()
            if not words:
                continue

            # Proportional trimming for boundary segments
            seg_total_dur = max(0.01, s_end - s_start)
            if s_start < clip_st or s_end > clip_et:
                frac_st = max(0.0, (clip_st - s_start) / seg_total_dur)
                frac_et = min(1.0, (clip_et - s_start) / seg_total_dur)
                w_st_idx = int(math.floor(frac_st * len(words)))
                w_et_idx = max(w_st_idx + 1, int(math.ceil(frac_et * len(words))))
                words = words[w_st_idx:w_et_idx]
                if not words:
                    continue

            chunks = _chunk_words(words, target_chunk_size=target_chunk_size)
            chunk_lens = [sum(max(1, len(w)) for w in ch) for ch in chunks]
            total_chars = max(1, sum(chunk_lens))

            curr_pos = rel_start
            for idx, ch in enumerate(chunks):
                ch_dur = duration * (chunk_lens[idx] / total_chars)
                c_start = curr_pos
                c_end = min(rel_end, curr_pos + ch_dur)
                curr_pos = c_end
                if c_end <= c_start:
                    continue

                c_dur = c_end - c_start
                ch_word_timings = _compute_word_centiseconds(
                    [w.upper() for w in ch],
                    total_duration=c_dur,
                    explicit_words=None,
                )

                c_start_r = round(c_start, 3)
                c_end_r = round(c_end, 3)
                cue_text = " ".join(ch).upper()

                cues.append({
                    "start": c_start_r,
                    "end": c_end_r,
                    "text": cue_text,
                    "start_abs": round(clip_st + c_start, 3),
                    "end_abs": round(clip_st + c_end, 3),
                    "words": ch_word_timings,
                })

    # Preserve order: sort cues chronologically by start time, then end time
    cues.sort(key=lambda c: (c["start"], c["end"]))

    # Smooth micro-gaps between consecutive cues to prevent subtitle blinking
    for i in range(len(cues) - 1):
        curr = cues[i]
        nxt = cues[i + 1]
        gap = nxt["start"] - curr["end"]
        if 0.0 < gap <= 0.35:
            add_sec = round(gap - 0.02, 3)
            if add_sec > 0:
                curr["end"] = round(curr["end"] + add_sec, 3)
                curr["end_abs"] = round(curr["end_abs"] + add_sec, 3)
                if curr.get("words"):
                    curr["words"][-1]["duration_cs"] += int(round(add_sec * 100))
    return cues


def create_ass_subtitle_file(
    segments: List[Dict],
    clip_start: float,
    clip_end: float,
    out_ass_path: str,
    width: int = 1080,
    height: int = 1920,
    source_duration: Optional[float] = None,
    untrusted_spans: Optional[List[Dict]] = None,
    cues: Optional[List[Dict]] = None,
    subtitle_style: str = "karaoke",
    framing_mode: str = "podcast",
    font_family: Optional[str] = None,
    gaming_preset: Optional[str] = None,
    gaming_layout: Optional[str] = None,
) -> bool:
    """Generate TikTok/Reels-style ASS subtitle file for the clip using validated cues."""
    style_norm = (subtitle_style or "karaoke").strip().lower()
    if style_norm == "none":
        return False

    if cues is None:
        cues = build_validated_cues(
            segments=segments,
            clip_start=clip_start,
            clip_end=clip_end,
            source_duration=source_duration,
            untrusted_spans=untrusted_spans,
            target_chunk_size=4,
        )

    if not cues:
        return False

    fontsize = max(24, int(height * 0.042))
    framing_norm = (framing_mode or "podcast").strip().lower()
    if framing_norm == "gaming":
        resolved_layout = get_gaming_layout(
            preset_name=gaming_preset or "auto",
            requested_layout=gaming_layout,
        )
        if resolved_layout == "cam_bottom":
            # Position cleanly above bottom streamer webcam in 1080x1920 stack
            margin_v = int(height * 0.27)
        else:
            # Facecam Atas (Windah style): webcam is at top (0..480px).
            # Gameplay is at bottom (480..1920px). Subtitle sits safely in lower gameplay area!
            margin_v = int(height * 0.16)
    elif framing_norm in ("dual", "split"):
        margin_v = int(height * 0.12)
    else:
        margin_v = int(height * 0.16)

    # Configure style parameters based on creator text preset or legacy style
    if style_norm in ("hormozi", "tiktok_punch", "karaoke_bounce", "hormozi_emerald"):
        font_name = "Montserrat"
        bold = -1
        italic = 0
        primary_col = "&H0000E6FF"   # Neon Yellow #FFE600 (BGR)
        secondary_col = "&H00FFFFFF" # White
        outline_col = "&H00000000"
        back_col = "&H80000000"
        border_style = 1
        outline = 4.5
        shadow = 2.0
        spacing = 0
        uppercase = True
    elif style_norm in ("vox_box", "clean_bottom_bar", "dan_koe", "vox_cinema"):
        font_name = "Inter"
        bold = -1
        italic = 0
        primary_col = "&H00FFFFFF"   # Pure White
        secondary_col = "&H00E0E0E0"
        outline_col = "&H00000000"
        back_col = "&HCC000000"      # 80% Black opaque box
        border_style = 3              # Opaque box background
        outline = 2.0
        shadow = 0.0
        spacing = 0
        uppercase = (style_norm == "clean_bottom_bar")
    elif style_norm in ("nas_daily",):
        font_name = "Montserrat"
        bold = -1
        italic = 0
        primary_col = "&H00FFFFFF"
        secondary_col = "&H00FFFFFF"
        outline_col = "&H00000000"
        back_col = "&HCC0000E6"      # Crimson red box
        border_style = 3
        outline = 1.5
        shadow = 0.0
        spacing = 0
        uppercase = True
    elif style_norm in ("matrix_hacker",):
        font_name = "Space Mono"
        bold = -1
        italic = 0
        primary_col = "&H0066FF00"   # Phosphor green
        secondary_col = "&H00FFFFFF"
        outline_col = "&H00003300"
        back_col = "&HE0051105"
        border_style = 3
        outline = 1.5
        shadow = 0.0
        spacing = 1
        uppercase = True
    elif style_norm in ("netflix_sub",):
        font_name = "Inter"
        bold = -1
        italic = 0
        primary_col = "&H0000E6FF"   # Yellow
        secondary_col = "&H00FFFFFF"
        outline_col = "&H00000000"
        back_col = "&H90000000"
        border_style = 1
        outline = 2.2
        shadow = 1.5
        spacing = 0
        uppercase = False
    elif style_norm in ("ali_abdaal", "ali_cyan"):
        font_name = "Poppins"
        bold = -1
        italic = 0
        primary_col = "&H00FFFFFF"
        secondary_col = "&H0000E6FF" # Yellow highlight
        outline_col = "&H00000000"
        back_col = "&H60000000"
        border_style = 1
        outline = 2.5
        shadow = 1.2
        spacing = 0
        uppercase = False
    elif style_norm in ("aesthetic", "luxury_gold", "pastel_vlog", "aesthetic_warm"):
        font_name = "Bebas Neue" if style_norm != "pastel_vlog" else "Poppins"
        bold = 0
        italic = 0
        primary_col = "&H008AE6FE" if style_norm == "luxury_gold" else ("&H00FFD5E9" if style_norm == "pastel_vlog" else "&H00FFFFFF")
        secondary_col = "&H00E0E0E0"
        outline_col = "&H0018181B"
        back_col = "&HA0000000"
        border_style = 1
        outline = 1.2
        shadow = 2.5
        spacing = 4 if style_norm in ("aesthetic", "aesthetic_warm") else 3
        uppercase = (style_norm != "pastel_vlog")
    elif style_norm in ("devon_bold", "gaming_rage", "fire_flame", "hormozi_fire"):
        font_name = "Anton"
        bold = -1
        italic = -1 if style_norm == "gaming_rage" else 0
        primary_col = "&H001E1EFF" if style_norm == "gaming_rage" else ("&H000066FF" if style_norm in ("fire_flame", "hormozi_fire") else "&H0000FFFF")
        secondary_col = "&H00FFFFFF"
        outline_col = "&H00000000"
        back_col = "&H90000000"
        border_style = 1
        outline = 4.8
        shadow = 2.5
        spacing = 0
        uppercase = True
    elif style_norm in ("mrbeast", "retro_synth", "comic_pow", "cyber_neon", "mrbeast_yellow"):
        font_name = "Oswald" if style_norm == "cyber_neon" else "Bangers"
        bold = -1
        italic = -1 if style_norm in ("mrbeast", "mrbeast_yellow") else 0
        primary_col = "&H00FF00FF" if style_norm == "cyber_neon" else ("&H0000AAFF" if style_norm == "retro_synth" else "&H0000F0FF")
        secondary_col = "&H0000FFFF"
        outline_col = "&H00000000"
        back_col = "&H00FF00EA"      # Comic magenta shadow
        border_style = 1
        outline = 4.8
        shadow = 3.0
        spacing = 1
        uppercase = True
    elif style_norm in ("brat_lime",):
        font_name = "Montserrat"
        bold = -1
        italic = 0
        primary_col = "&H0000E68A"   # Acid Lime #8AE600 BGR
        secondary_col = "&H00FFFFFF"
        outline_col = "&H00000000"
        back_col = "&H90000000"
        border_style = 1
        outline = 3.2
        shadow = 1.5
        spacing = 0
        uppercase = True
    elif style_norm in ("dymo_tape",):
        font_name = "Special Elite"
        bold = -1
        italic = 0
        primary_col = "&H00F0F0F0"   # Typewriter white
        secondary_col = "&H0000E6FF"
        outline_col = "&H00101010"
        back_col = "&HF50A0A0A"      # Heavy black embossed label box
        border_style = 3
        outline = 2.0
        shadow = 0.0
        spacing = 2
        uppercase = True
    elif style_norm in ("luxury_serif",):
        font_name = "Cinzel"
        bold = -1
        italic = 0
        primary_col = "&H00DCF2FE"   # Pearl Gold Ivory #FEF2DC BGR
        secondary_col = "&H00FFFFFF"
        outline_col = "&H0018181B"
        back_col = "&H70000000"
        border_style = 1
        outline = 1.2
        shadow = 2.2
        spacing = 4
        uppercase = True
    elif style_norm in ("sticker_pop",):
        font_name = "Rubik"
        bold = -1
        italic = 0
        primary_col = "&H0000FFFF"   # Bright Yellow #FFFF00
        secondary_col = "&H00FF00FF"
        outline_col = "&H00000000"
        back_col = "&H00201005"      # Offset solid shadow
        border_style = 1
        outline = 5.5
        shadow = 4.0
        spacing = 1
        uppercase = True
    elif style_norm in ("amber_terminal",):
        font_name = "VT323"
        bold = -1
        italic = 0
        primary_col = "&H00009FFF"   # CRT Amber #FF9F00 BGR
        secondary_col = "&H00FFFFFF"
        outline_col = "&H00003060"
        back_col = "&HE80A0502"      # Retro amber monitor box
        border_style = 3
        outline = 1.5
        shadow = 0.0
        spacing = 1
        uppercase = True
    elif style_norm in ("capcut_glow",):
        font_name = "Poppins"
        bold = -1
        italic = 0
        primary_col = "&H00FFFFFF"
        secondary_col = "&H00F5F500" # Cyan highlight #00F5F5 BGR
        outline_col = "&H00D4F500"   # Cyan glow halo #00F5D4 BGR
        back_col = "&H60D4F500"
        border_style = 1
        outline = 3.2
        shadow = 3.5
        spacing = 1
        uppercase = True
    else:
        # Legacy karaoke / kinetic / classic default
        font_name = "Arial"
        bold = -1
        italic = 0
        primary_col = "&H0015CCFA"
        secondary_col = "&H00FFFFFF"
        outline_col = "&H00000000"
        back_col = "&H80000000"
        border_style = 1
        outline = 3.5
        shadow = 1.5
        spacing = 0
        uppercase = False

    # Modular override: allow overriding font family without affecting preset's colors/stroke/animation
    if font_family and font_family.strip():
        font_name = font_family.strip()

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{fontsize},{primary_col},{secondary_col},{outline_col},{back_col},{bold},{italic},0,0,100,100,{spacing},0,{border_style},{outline},{shadow},2,20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogues = []
    for cue in cues:
        t_start = _format_ass_time(cue["start"])
        t_end = _format_ass_time(cue["end"])
        cue_words = cue.get("words", [])
        cue_text = cue["text"].upper() if uppercase else cue["text"]

        if not cue_words:
            raw_words = str(cue.get("text", "")).strip().split()
            if raw_words:
                c_dur = max(0.05, float(cue.get("end", 0.0) - cue.get("start", 0.0)))
                cue_words = _compute_word_centiseconds(
                    raw_words,
                    total_duration=c_dur,
                    explicit_words=None,
                )

        if style_norm in ("hormozi", "karaoke", "karaoke_bounce", "tiktok_punch", "nas_daily", "hormozi_emerald", "brat_lime", "capcut_glow") and cue_words:
            # Smooth karaoke sweep (\kf)
            tag_text = " ".join(f"{{\\kf{w['duration_cs']}}}{w['word'].upper() if uppercase else w['word']}" for w in cue_words)
            dialogues.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{tag_text}")
        elif style_norm in ("mrbeast", "kinetic", "comic_pow", "retro_synth", "gaming_rage", "fire_flame", "mrbeast_yellow", "hormozi_fire", "sticker_pop") and cue_words:
            # Discrete word-by-word beat jump (\k)
            tag_text = " ".join(f"{{\\k{w['duration_cs']}}}{w['word'].upper() if uppercase else w['word']}" for w in cue_words)
            dialogues.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{tag_text}")
        elif style_norm in ("ali_abdaal", "dan_koe", "matrix_hacker", "ali_cyan", "vox_cinema", "amber_terminal", "dymo_tape") and cue_words:
            # Smooth highlighter sweep with active word
            tag_text = " ".join(f"{{\\kf{w['duration_cs']}}}{w['word'].upper() if uppercase else w['word']}" for w in cue_words)
            dialogues.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{tag_text}")
        else:
            # Static text
            dialogues.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{cue_text}")

    content = header + "\n".join(dialogues) + "\n"
    with open(out_ass_path, "w", encoding="utf-8") as f:
        f.write(content)
    return True



def create_vtt_subtitle_file(
    segments: List[Dict],
    clip_start: float,
    clip_end: float,
    out_vtt_path: str,
    source_duration: Optional[float] = None,
    untrusted_spans: Optional[List[Dict]] = None,
    cues: Optional[List[Dict]] = None,
    framing_mode: str = "podcast",
    gaming_preset: Optional[str] = None,
    gaming_layout: Optional[str] = None,
) -> bool:
    """Generate WebVTT subtitle file for web player tracks using validated cues."""
    if cues is None:
        cues = build_validated_cues(
            segments=segments,
            clip_start=clip_start,
            clip_end=clip_end,
            source_duration=source_duration,
            untrusted_spans=untrusted_spans,
            target_chunk_size=4,
        )

    if not cues:
        return False

    is_gaming = (framing_mode or "").strip().lower() == "gaming"
    is_dual = (framing_mode or "").strip().lower() in ("dual", "split")
    if is_gaming:
        resolved_layout = get_gaming_layout(
            preset_name=gaming_preset or "auto",
            requested_layout=gaming_layout,
        )
        pos_tag = " line:72%" if resolved_layout == "cam_bottom" else " line:84%"
    elif is_dual:
        pos_tag = " line:84%"
    else:
        pos_tag = ""

    vtt_lines = ["WEBVTT\n"]
    for cue in cues:
        t_start = _format_vtt_time(cue["start"])
        t_end = _format_vtt_time(cue["end"])
        text = cue["text"]
        vtt_lines.append(f"{t_start} --> {t_end}{pos_tag}")
        vtt_lines.append(text)
        vtt_lines.append("")

    with open(out_vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(vtt_lines))
    return True


def _run_ffmpeg_cmd(cmd: List[str], job_ctx: Optional[Any] = None) -> None:
    """Run an FFmpeg command with cancellation monitoring, periodic deadline check, and process registration."""
    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    stderr_tmp = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stderr=stderr_tmp)
    if job_ctx is not None and hasattr(job_ctx, "register_subprocess"):
        job_ctx.register_subprocess(proc)

    try:
        while True:
            if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                try:
                    job_ctx.check_cancellation_or_timeout()
                except Exception:
                    # Timeout or cancel occurred! Terminate proc immediately
                    try:
                        if proc.poll() is None:
                            proc.terminate()
                            try:
                                proc.wait(timeout=1.5)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                                proc.wait(timeout=1.5)
                    except Exception:
                        pass
                    raise

            try:
                ret = proc.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue

        # Post-exit deadline check
        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            job_ctx.check_cancellation_or_timeout()

        if ret != 0:
            err_line = ""
            try:
                stderr_tmp.seek(0)
                raw_lines = [l.strip().decode("utf-8", errors="replace") for l in stderr_tmp.readlines() if l.strip()]
                if raw_lines:
                    err_line = f": {raw_lines[-1]}"
            except Exception:
                pass
            raise RuntimeError(f"Proses FFmpeg keluar dengan kode error {ret}{err_line}")
    finally:
        try:
            stderr_tmp.close()
        except Exception:
            pass
        if job_ctx is not None and hasattr(job_ctx, "unregister_subprocess"):
            job_ctx.unregister_subprocess(proc)


def _cut_subclip(
    source_path: str,
    start: float,
    end: float,
    out_path: str,
    job_ctx: Optional[Any] = None,
) -> str:
    """Fast input-seeking subclip extraction: -ss before -i for O(1) demuxer seek."""
    dur = max(0.1, end - start)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}",
        "-t", f"{dur:.3f}",
        "-i", source_path,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-threads", "0",
        "-c:a", "aac", "-b:a", "128k",
        "-avoid_negative_ts", "make_zero",
        out_path,
    ]
    _run_ffmpeg_cmd(cmd, job_ctx=job_ctx)
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        # Fallback accurate output-seeking jika input-seeking menghasilkan file kosong
        cmd_fallback = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", source_path,
            "-ss", f"{start:.3f}",
            "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-threads", "0",
            "-c:a", "aac", "-b:a", "128k",
            "-avoid_negative_ts", "make_zero",
            out_path,
        ]
        _run_ffmpeg_cmd(cmd_fallback, job_ctx=job_ctx)
    return out_path


def _box_iou(boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
    """Compute Intersection over Union (IoU) of two bounding boxes (x, y, w, h)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    if interArea == 0:
        return 0.0
    areaA = boxA[2] * boxA[3]
    areaB = boxB[2] * boxB[3]
    unionArea = areaA + areaB - interArea
    return interArea / unionArea if unionArea > 0 else 0.0


_YUNET_DETECTOR = None
_YUNET_DETECTOR_DIMS: Optional[Tuple[int, int]] = None
_YUNET_MODEL_PATH: Optional[str] = None


def _get_yunet_detector(det_w: int = 640, det_h: int = 360) -> Optional[Any]:
    """Retrieve or initialize YuNet deep learning face detector if model artifact exists."""
    global _YUNET_DETECTOR, _YUNET_DETECTOR_DIMS, _YUNET_MODEL_PATH
    try:
        import cv2  # type: ignore

        if not hasattr(cv2, "FaceDetectorYN"):
            return None

        if _YUNET_MODEL_PATH is None:
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "..", "assets", "models", "face_detection_yunet.onnx"),
                os.path.join(os.path.dirname(__file__), "..", "..", "assets", "models", "face_detection_yunet_2023mar.onnx"),
                os.path.abspath("backend/assets/models/face_detection_yunet.onnx"),
            ]
            for p in candidates:
                norm_p = os.path.normpath(p)
                if os.path.exists(norm_p) and os.path.getsize(norm_p) > 100000:
                    _YUNET_MODEL_PATH = norm_p
                    break

        if not _YUNET_MODEL_PATH:
            return None

        if _YUNET_DETECTOR is None:
            _YUNET_DETECTOR = cv2.FaceDetectorYN.create(
                _YUNET_MODEL_PATH,
                "",
                (det_w, det_h),
                score_threshold=0.55,
                nms_threshold=0.30,
            )
            _YUNET_DETECTOR_DIMS = (det_w, det_h)
        elif _YUNET_DETECTOR_DIMS != (det_w, det_h):
            _YUNET_DETECTOR.setInputSize((det_w, det_h))
            _YUNET_DETECTOR_DIMS = (det_w, det_h)

        return _YUNET_DETECTOR
    except Exception:
        return None


def _detect_faces_with_yunet(
    frame_bgr: Any,
    src_w: int,
    src_h: int,
    det_w: int = 640,
    det_h: int = 360,
) -> List[Tuple[int, int, int, int, float]]:
    """Detect human faces with deep learning YuNet (high precision, pose-invariant, zero false positives)."""
    detector = _get_yunet_detector(det_w, det_h)
    if detector is None:
        return []
    try:
        import cv2  # type: ignore

        small_bgr = cv2.resize(frame_bgr, (det_w, det_h), interpolation=cv2.INTER_AREA)
        ret, faces = detector.detect(small_bgr)
        if ret <= 0 or faces is None or len(faces) == 0:
            return []

        sx = src_w / float(det_w)
        sy = src_h / float(det_h)
        out_faces: List[Tuple[int, int, int, int, float]] = []
        for f in faces:
            bx, by, bw, bh = f[:4]
            score = float(f[14])
            if score >= 0.55:
                ox = max(0, min(src_w - 2, int(bx * sx)))
                oy = max(0, min(src_h - 2, int(by * sy)))
                ow = max(2, min(src_w - ox, int(bw * sx)))
                oh = max(2, min(src_h - oy, int(bh * sy)))
                out_faces.append((ox, oy, ow, oh, score))
        return out_faces
    except Exception:
        return []


def _detect_multiview_faces(
    gray_img: Any,
    face_cascade: Optional[Any],
    profile_cascade: Optional[Any] = None,
    scale_factor: float = 1.1,
    min_neighbors: int = 5,
    min_size: Tuple[int, int] = (36, 36),
) -> List[Tuple[int, int, int, int]]:
    """Detect faces combining Frontal and Profile Haar Cascades (with horizontal flip for dual profiles)."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return []

    if face_cascade is None and profile_cascade is None:
        return []

    candidates: List[Tuple[int, int, int, int, float]] = []
    h_img, w_img = gray_img.shape[:2]

    # 1. Frontal faces
    if face_cascade is not None:
        try:
            ff = face_cascade.detectMultiScale(
                gray_img,
                scaleFactor=scale_factor,
                minNeighbors=min_neighbors,
                minSize=min_size,
            )
            for (x, y, w, h) in ff:
                candidates.append((int(x), int(y), int(w), int(h), 1.0))
        except Exception:
            pass

    # 2. Profile faces (facing right / standard orientation)
    if profile_cascade is not None:
        try:
            pf = profile_cascade.detectMultiScale(
                gray_img,
                scaleFactor=scale_factor,
                minNeighbors=min_neighbors,
                minSize=min_size,
            )
            for (x, y, w, h) in pf:
                candidates.append((int(x), int(y), int(w), int(h), 0.8))
        except Exception:
            pass

        # 3. Profile faces flipped horizontally (facing left)
        try:
            flipped = cv2.flip(gray_img, 1)
            pff = profile_cascade.detectMultiScale(
                flipped,
                scaleFactor=scale_factor,
                minNeighbors=min_neighbors,
                minSize=min_size,
            )
            for (fx, fy, fw, fh) in pff:
                orig_x = w_img - int(fx) - int(fw)
                candidates.append((orig_x, int(fy), int(fw), int(fh), 0.8))
        except Exception:
            pass

    if not candidates:
        return []

    # Sort candidates: frontal first, then larger area
    candidates.sort(key=lambda c: (c[4], c[2] * c[3]), reverse=True)

    # Deduplicate overlapping detections (NMS)
    selected: List[Tuple[int, int, int, int]] = []
    for cx, cy, cw, ch, _ in candidates:
        cand_box = (cx, cy, cw, ch)
        cand_area = cw * ch
        keep = True
        for sel_box in selected:
            sel_area = sel_box[2] * sel_box[3]
            iou = _box_iou(cand_box, sel_box)
            ix = max(0, min(cx + cw, sel_box[0] + sel_box[2]) - max(cx, sel_box[0]))
            iy = max(0, min(cy + ch, sel_box[1] + sel_box[3]) - max(cy, sel_box[1]))
            inter = ix * iy
            iom = inter / min(cand_area, sel_area) if min(cand_area, sel_area) > 0 else 0.0
            if iou > 0.25 or iom > 0.40:
                keep = False
                break
        if keep:
            selected.append(cand_box)

    return selected


def _compute_lip_activity(
    frame_gray: Any,
    face_box: Tuple[int, int, int, int],
    prev_mouth_crop: Optional[Any] = None,
) -> Tuple[float, Any]:
    """Compute visual lip/mouth movement score from lower third of face bounding box."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return 0.0, None

    x, y, w, h = face_box
    h_img, w_img = frame_gray.shape[:2]

    # Mouth is located in lower third: ~62% to ~95% height, 20% to 80% width
    mouth_y1 = max(0, min(h_img, y + int(h * 0.62)))
    mouth_y2 = max(0, min(h_img, y + int(h * 0.95)))
    mouth_x1 = max(0, min(w_img, x + int(w * 0.20)))
    mouth_x2 = max(0, min(w_img, x + int(w * 0.80)))

    if mouth_y2 <= mouth_y1 or mouth_x2 <= mouth_x1:
        return 0.0, np.zeros((16, 24), dtype=np.uint8)

    mouth_crop = frame_gray[mouth_y1:mouth_y2, mouth_x1:mouth_x2]
    canonical = cv2.resize(mouth_crop, (24, 16), interpolation=cv2.INTER_AREA)

    if prev_mouth_crop is None or prev_mouth_crop.shape != canonical.shape:
        base_score = float(np.std(canonical)) * 0.05
        return base_score, canonical

    diff = cv2.absdiff(canonical, prev_mouth_crop)
    score = float(np.mean(diff)) + 0.5 * float(np.std(diff))
    return score, canonical


class PodcastFramingTracker:
    """Intelligent face-tracking and framing engine for vertical (9:16) and custom aspect ratios.

    Specialized for podcasts, interviews, and talking-head content:
    1. Multi-view & Continuity Tracking:
       - Frontal & profile face detection with horizontal flip.
       - Centroid/IoU tracking persists face identities and bridges momentary misses.
    2. Active Speaker Detection with Switching Cooldown:
       - Detects visual lip/mouth activity in lower third of face box.
       - Switches camera to active speaker during wide shots with 1.5 - 2.0s cooldown to prevent ping-pong.
    3. Dual-Face Centering (Wide Shots):
       - If two faces fit together in crop_w with safe margins, centers both speakers.
       - If two faces are too wide, follows the active speaker or maintains temporal stickiness.
    4. Fallback Stability & Boundary Safety:
       - Holds last known face center during temporary occlusion (up to max_hold_frames).
       - Only slowly relaxes to center frame if no faces appear for an extended period.
       - Strict boundary clamping [0, src_w - crop_w] and [0, src_h - crop_h].
    """

    def __init__(
        self,
        src_w: int,
        src_h: int,
        crop_w: int,
        crop_h: int,
        fps: float = 30.0,
        safe_margin_ratio: float = 0.08,
        framing_mode: str = "podcast",
        switch_cooldown_sec: float = 1.8,
    ):
        self.src_w = src_w
        self.src_h = src_h
        self.crop_w = crop_w
        self.crop_h = crop_h
        self.fps = fps
        self.safe_margin = max(16, int(crop_w * safe_margin_ratio))
        self.framing_mode = framing_mode.lower() if isinstance(framing_mode, str) else "podcast"
        self.switch_cooldown_sec = switch_cooldown_sec

        self.current_center: Tuple[int, int] = (src_w // 2, src_h // 2)
        self.target_center: Tuple[int, int] = (src_w // 2, src_h // 2)
        self.last_valid_face_center: Optional[Tuple[int, int]] = None
        self.tracked_subject_x: Optional[int] = None

        self.frames_without_face: int = 0
        self.max_hold_frames: int = max(30, int(fps * 2.0))
        self.smoothing: float = 0.12
        self.deadband_px: int = max(36, int(crop_w * 0.08))
        self.deadband_py: int = max(30, int(crop_h * 0.08))
        self.locked_subject_misses: int = 0

        # Continuity tracking & active speaker state
        self.tracked_faces: List[Dict[str, Any]] = []
        self.next_track_id: int = 1
        self.max_track_misses: int = 2
        self.current_time: float = 0.0
        self.last_switch_time: float = -999.0
        self.active_speaker_track_id: Optional[int] = None
        self.last_switch_was_cut: bool = False

    def update_faces(
        self,
        faces: List[Union[Tuple[int, int, int, int], Tuple[int, int, int, int, float]]],
        is_scene_cut: bool = False,
        face_activities: Optional[List[float]] = None,
        current_time: Optional[float] = None,
        frame_gray: Optional[Any] = None,
    ) -> Tuple[int, int]:
        """Update tracker target based on detected faces (in source frame coordinates)."""
        if current_time is not None:
            self.current_time = float(current_time)
        else:
            self.current_time += 1.0 / self.fps

        if self.framing_mode == "center":
            tx, ty = self.src_w // 2, self.src_h // 2
            x0_target = max(0, min(self.src_w - self.crop_w, tx - self.crop_w // 2))
            y0_target = max(0, min(self.src_h - self.crop_h, ty - self.crop_h // 2))
            self.target_center = (x0_target + self.crop_w // 2, y0_target + self.crop_h // 2)
            if is_scene_cut:
                self.current_center = self.target_center
            return self.target_center

        # Filter spurious tiny detections (at least 3.5% of min dimension)
        min_dim = max(24, int(min(self.src_w, self.src_h) * 0.035))
        valid_in: List[Tuple[int, int, int, int, float]] = []
        for i, f in enumerate(faces):
            fx, fy, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
            act = float(f[4]) if len(f) >= 5 else (float(face_activities[i]) if face_activities and i < len(face_activities) else 0.0)
            if fw >= min_dim and fh >= min_dim and fx >= 0 and fy >= 0:
                valid_in.append((fx, fy, fw, fh, act))

        # Filter secondary background clutter: if multiple faces exist and not single mode,
        # eliminate faces that are less than 20% area of the dominant face
        if valid_in and self.framing_mode != "single":
            max_area = max(f[2] * f[3] for f in valid_in)
            valid_in = [f for f in valid_in if (f[2] * f[3] >= 0.20 * max_area)]

        if is_scene_cut:
            self.tracked_faces.clear()
            self.last_switch_time = self.current_time
            self.active_speaker_track_id = None
            self.tracked_subject_x = None
            self.locked_subject_misses = 0

        # If multiple faces detected in this frame, mark them as co-present
        is_multi_shot = len(valid_in) >= 2
        matched_track_ids = set()
        matched_in_indices = set()
        for in_idx, (fx, fy, fw, fh, act) in enumerate(valid_in):
            best_t = None
            best_score = -1.0
            in_cx, in_cy = fx + fw // 2, fy + fh // 2
            for trk in self.tracked_faces:
                if trk["id"] in matched_track_ids:
                    continue
                iou = _box_iou((fx, fy, fw, fh), trk["box"])
                dist = abs(in_cx - trk["center"][0])
                if iou > 0.15 or dist <= max(fw, trk["box"][2]) * 1.25:
                    score = iou * 100.0 - dist * 0.1
                    if score > best_score:
                        best_score = score
                        best_t = trk
            if best_t is not None:
                best_t["box"] = (fx, fy, fw, fh)
                best_t["center"] = (in_cx, in_cy)
                if frame_gray is not None:
                    pmc = best_t.get("prev_mouth_crop")
                    computed_act, cur_mc = _compute_lip_activity(frame_gray, (fx, fy, fw, fh), prev_mouth_crop=pmc)
                    best_t["prev_mouth_crop"] = cur_mc
                    best_t["lip_activity"] = 0.5 * best_t.get("lip_activity", 0.0) + 0.5 * computed_act if best_t.get("lip_activity", 0.0) > 0 else computed_act
                else:
                    best_t["lip_activity"] = 0.5 * best_t["lip_activity"] + 0.5 * act if best_t["lip_activity"] > 0 else act
                best_t["missed"] = 0
                if is_multi_shot:
                    best_t["co_present"] = True
                matched_track_ids.add(best_t["id"])
                matched_in_indices.add(in_idx)

        # Unmatched existing tracks increment missed
        for trk in self.tracked_faces:
            if trk["id"] not in matched_track_ids:
                trk["missed"] += 1

        # Unmatched incoming detections become new tracks
        for in_idx, (fx, fy, fw, fh, act) in enumerate(valid_in):
            if in_idx not in matched_in_indices:
                trk_data = {
                    "id": self.next_track_id,
                    "box": (fx, fy, fw, fh),
                    "center": (fx + fw // 2, fy + fh // 2),
                    "missed": 0,
                    "co_present": is_multi_shot,
                }
                if frame_gray is not None:
                    computed_act, cur_mc = _compute_lip_activity(frame_gray, (fx, fy, fw, fh), prev_mouth_crop=None)
                    trk_data["prev_mouth_crop"] = cur_mc
                    trk_data["lip_activity"] = computed_act
                else:
                    trk_data["lip_activity"] = act
                self.tracked_faces.append(trk_data)
                self.next_track_id += 1

        # Keep active tracks:
        # A track that wasn't matched is only kept if it was verified co_present in a multi-shot
        # OR if no faces were detected at all (full hold fallback).
        active_tracks = []
        for trk in self.tracked_faces:
            if trk["missed"] == 0:
                active_tracks.append(trk)
            elif trk["missed"] <= self.max_track_misses:
                if not valid_in or trk.get("co_present", False):
                    active_tracks.append(trk)
        self.tracked_faces = active_tracks

        is_first_detection = (self.last_valid_face_center is None and bool(active_tracks))

        if not active_tracks:
            self.frames_without_face += 1
            if self.last_valid_face_center is not None and self.frames_without_face <= self.max_hold_frames:
                tx, ty = self.last_valid_face_center
            else:
                tx, ty = self.src_w // 2, self.src_h // 2
                self.tracked_subject_x = None
                self.active_speaker_track_id = None
                self.locked_subject_misses = 0
        elif self.framing_mode == "single":
            self.frames_without_face = 0
            sel = None

            # 1. Pertahankan kunci pada target ID yang sedang aktif
            if self.active_speaker_track_id is not None:
                sel = next((t for t in active_tracks if t["id"] == self.active_speaker_track_id), None)

            # 2. Jika ID sempat putus (miss 1-2 frame), cari wajah terdekat dengan koordinat terakhir target
            if sel is None and self.tracked_subject_x is not None:
                closest_trk = min(active_tracks, key=lambda t: abs(t["center"][0] - self.tracked_subject_x))
                if abs(closest_trk["center"][0] - self.tracked_subject_x) <= max(int(self.crop_w * 0.75), 250):
                    sel = closest_trk
                    self.active_speaker_track_id = sel["id"]

            if sel is not None:
                self.locked_subject_misses = 0
                tx, ty = sel["center"]
                self.last_valid_face_center = (tx, ty)
                self.tracked_subject_x = tx
            else:
                # Target terkunci hilang sementara pada frame ini
                self.locked_subject_misses += 1
                if self.last_valid_face_center is not None and self.locked_subject_misses <= self.max_hold_frames:
                    # TAHAN posisi terakhir target terkunci (jangan lompat ke orang lain)
                    tx, ty = self.last_valid_face_center
                else:
                    # Target terkunci benar-benar hilang > 2 detik, ganti target ke wajah dominan
                    active_tracks.sort(key=lambda t: t["box"][2] * t["box"][3], reverse=True)
                    sel = active_tracks[0]
                    self.active_speaker_track_id = sel["id"]
                    self.locked_subject_misses = 0
                    tx, ty = sel["center"]
                    self.last_valid_face_center = (tx, ty)
                    self.tracked_subject_x = tx
        elif len(active_tracks) == 1:
            self.frames_without_face = 0
            sel = active_tracks[0]
            tx, ty = sel["center"]
            self.last_valid_face_center = (tx, ty)
            self.tracked_subject_x = tx
            self.active_speaker_track_id = sel["id"]
        else:
            # 2 or more faces: Podcast / Wide shot handling
            self.frames_without_face = 0
            active_tracks.sort(key=lambda t: t["box"][2] * t["box"][3], reverse=True)
            t1, t2 = active_tracks[0], active_tracks[1]
            left_t = t1 if t1["box"][0] < t2["box"][0] else t2
            right_t = t2 if t1["box"][0] < t2["box"][0] else t1

            min_x = left_t["box"][0]
            max_x = right_t["box"][0] + right_t["box"][2]
            span_w = max_x - min_x
            required_w = span_w + 2 * self.safe_margin

            if required_w <= self.crop_w:
                # Both faces fit comfortably in crop: center both speakers
                tx = (min_x + max_x) // 2
                ty = (left_t["center"][1] + right_t["center"][1]) // 2
                self.last_valid_face_center = (tx, ty)
                self.tracked_subject_x = tx
            else:
                # Faces are too far apart to fit together in 9:16
                area1 = t1["box"][2] * t1["box"][3]
                area2 = t2["box"][2] * t2["box"][3]
                c1_x = t1["center"][0]
                c2_x = t2["center"][0]

                # Identify currently tracked speaker
                if self.active_speaker_track_id == t1["id"]:
                    curr_t, other_t = t1, t2
                elif self.active_speaker_track_id == t2["id"]:
                    curr_t, other_t = t2, t1
                elif self.tracked_subject_x is not None:
                    d1 = abs(self.tracked_subject_x - c1_x)
                    d2 = abs(self.tracked_subject_x - c2_x)
                    curr_t, other_t = (t1, t2) if d1 <= d2 else (t2, t1)
                else:
                    curr_t, other_t = None, None

                time_since_switch = self.current_time - self.last_switch_time
                cooldown_active = (time_since_switch < self.switch_cooldown_sec)

                if curr_t is not None:
                    curr_act = curr_t["lip_activity"]
                    other_act = other_t["lip_activity"]

                    # Active speaker check with lip movement threshold
                    if other_act >= 3.0 and other_act >= curr_act + 2.0:
                        if not cooldown_active:
                            sel = other_t
                            self.last_switch_time = self.current_time
                            self.last_switch_was_cut = True
                        else:
                            sel = curr_t
                    # Dominance rule fallback: one face significantly larger (>= 1.45x)
                    elif other_t["box"][2] * other_t["box"][3] >= 1.45 * (curr_t["box"][2] * curr_t["box"][3]) and curr_act < 3.0 and not cooldown_active:
                        sel = other_t
                        self.last_switch_time = self.current_time
                    else:
                        # Temporal stickiness: stay locked on current speaker
                        sel = curr_t
                else:
                    # Cold start selection
                    act1, act2 = t1["lip_activity"], t2["lip_activity"]
                    if act1 >= 3.0 and act1 >= act2 + 2.0:
                        sel = t1
                    elif act2 >= 3.0 and act2 >= act1 + 2.0:
                        sel = t2
                    elif area1 >= 1.45 * area2:
                        sel = t1
                    elif area2 >= 1.45 * area1:
                        sel = t2
                    else:
                        d1_c = abs(self.src_w // 2 - c1_x)
                        d2_c = abs(self.src_w // 2 - c2_x)
                        sel = t1 if d1_c <= d2_c else t2
                    self.last_switch_time = self.current_time

                tx, ty = sel["center"]
                self.last_valid_face_center = (tx, ty)
                self.tracked_subject_x = tx
                self.active_speaker_track_id = sel["id"]

        # Dampen minor jitter on face center if target changed only slightly
        if self.last_valid_face_center is not None and not is_scene_cut:
            if abs(tx - self.last_valid_face_center[0]) <= 15:
                tx = self.last_valid_face_center[0]
            if abs(ty - self.last_valid_face_center[1]) <= 15:
                ty = self.last_valid_face_center[1]

        # Clamp target center so crop box is strictly within frame boundaries
        x0_target = max(0, min(self.src_w - self.crop_w, tx - self.crop_w // 2))
        y0_target = max(0, min(self.src_h - self.crop_h, ty - self.crop_h // 2))
        self.target_center = (x0_target + self.crop_w // 2, y0_target + self.crop_h // 2)

        if is_scene_cut or is_first_detection:
            self.current_center = self.target_center

        return self.target_center

    def step(self, is_scene_cut: bool = False) -> Tuple[int, int, int, int]:
        """Perform one frame transition step and return current crop box (x0, y0, crop_w, crop_h)."""
        if is_scene_cut or self.last_switch_was_cut:
            self.current_center = self.target_center
            self.last_switch_was_cut = False
        else:
            cx, cy = self.current_center
            tx, ty = self.target_center

            # Deadband filter to prevent micro-trembling and jitter
            dx = tx - cx
            dy = ty - cy
            new_x = cx if abs(dx) < self.deadband_px else int(cx + dx * self.smoothing)
            new_y = cy if abs(dy) < self.deadband_py else int(cy + dy * self.smoothing)
            self.current_center = (new_x, new_y)

        # Clamping to valid pixel bounds
        x0 = max(0, min(self.src_w - self.crop_w, self.current_center[0] - self.crop_w // 2))
        y0 = max(0, min(self.src_h - self.crop_h, self.current_center[1] - self.crop_h // 2))
        return x0, y0, self.crop_w, self.crop_h


def validate_facecam_area(
    video_path: str,
    bot_crop: Tuple[int, int, int, int],
    job_ctx: Optional[Any] = None,
) -> bool:
    """Sample 1-2 frames from video clip and verify whether a human face is detected in bot_crop."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return True

    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
        return True

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    if not os.path.exists(cascade_path):
        return True

    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        return True

    profile_cascade = None
    prof_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
    if os.path.exists(prof_path):
        pc = cv2.CascadeClassifier(prof_path)
        if not pc.empty():
            profile_cascade = pc

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return True

    bx, by, bw, bh = bot_crop
    face_found = False

    try:
        raw_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        total_frames = int(raw_count) if raw_count and math.isfinite(raw_count) else 0

        # Sample 1-2 frames across the clip (at 25% and 65% duration)
        if total_frames > 2:
            sample_indices = [max(0, int(total_frames * 0.25)), max(0, int(total_frames * 0.65))]
        else:
            sample_indices = [0]

        for s_idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, s_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            fh, fw = frame.shape[:2]
            x0 = max(0, min(fw - 2, bx))
            y0 = max(0, min(fh - 2, by))
            w0 = max(2, min(fw - x0, bw))
            h0 = max(2, min(fh - y0, bh))
            roi = frame[y0:y0 + h0, x0:x0 + w0]
            if roi.size == 0:
                continue

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            min_dim = max(18, int(min(w0, h0) * 0.12))

            # 1. Frontal face detection
            detected = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=3, minSize=(min_dim, min_dim)
            )
            if len(detected) > 0:
                face_found = True
                break

            # 2. Profile face detection (streamers turning head)
            if profile_cascade is not None:
                prof_detected = profile_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=3, minSize=(min_dim, min_dim)
                )
                if len(prof_detected) > 0:
                    face_found = True
                    break
                flipped = cv2.flip(gray, 1)
                prof_detected_flip = profile_cascade.detectMultiScale(
                    flipped, scaleFactor=1.1, minNeighbors=3, minSize=(min_dim, min_dim)
                )
                if len(prof_detected_flip) > 0:
                    face_found = True
                    break
    except Exception as e:
        log_job_message(f"[clip/local] Note: Facecam validation skipped ({e})", job_ctx=job_ctx)
        face_found = True
    finally:
        cap.release()

    return face_found


def detect_facecam_candidate(
    video_path: str,
    clip_start: float = 0.0,
    clip_end: Optional[float] = None,
    num_samples: int = 5,
) -> Dict[str, Any]:
    """Smart auto-detection suggester for gaming facecam:
    1. Restricts search strictly to 4 corner zones to avoid confusing game character faces in mid-screen.
    2. Samples multiple frames across clip duration to prevent single-frame target jump.
    3. Requires consistency (>= 60% sample frames with face in same corner) to claim high confidence.
    4. If confidence is low, does not falsely claim detection; returns low confidence and safe default.
    5. Returns normalized coordinates (x, y, w, h in 0.0..1.0).
    """
    default_box = {"x": 0.53, "y": 0.61, "w": 0.47, "h": 0.37}
    try:
        import cv2  # type: ignore
    except ImportError:
        return {
            "detected": False,
            "confidence": "low",
            "confidence_score": 0.0,
            "corner": "bottom_right",
            "box": default_box,
            "message": "OpenCV tidak tersedia.",
        }

    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
        return {
            "detected": False,
            "confidence": "low",
            "confidence_score": 0.0,
            "corner": "bottom_right",
            "box": default_box,
            "message": "Model Haar Cascade tidak ditemukan.",
        }

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    if not os.path.exists(cascade_path):
        return {
            "detected": False,
            "confidence": "low",
            "confidence_score": 0.0,
            "corner": "bottom_right",
            "box": default_box,
            "message": "Model deteksi wajah tidak ditemukan.",
        }

    face_cascade = cv2.CascadeClassifier(cascade_path)
    profile_cascade = None
    prof_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
    if os.path.exists(prof_path):
        pc = cv2.CascadeClassifier(prof_path)
        if not pc.empty():
            profile_cascade = pc

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "detected": False,
            "confidence": "low",
            "confidence_score": 0.0,
            "corner": "bottom_right",
            "box": default_box,
            "message": "Gagal membuka berkas video.",
        }

    # Corner search definitions (relative to frame dimensions 0.0 - 1.0)
    # Streamer facecams almost exclusively occupy one of the 4 screen corners:
    corners = {
        "bottom_right": {"x": 0.50, "y": 0.50, "w": 0.50, "h": 0.50},
        "bottom_left":  {"x": 0.00, "y": 0.50, "w": 0.50, "h": 0.50},
        "top_right":    {"x": 0.50, "y": 0.00, "w": 0.50, "h": 0.50},
        "top_left":     {"x": 0.00, "y": 0.00, "w": 0.50, "h": 0.50},
    }

    corner_hits = {c: [] for c in corners}
    total_samples = 0

    try:
        raw_fps = cap.get(cv2.CAP_PROP_FPS)
        fps = raw_fps if raw_fps and math.isfinite(raw_fps) and raw_fps > 0 else 30.0
        raw_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        total_frames = int(raw_count) if raw_count and math.isfinite(raw_count) and raw_count > 0 else 0

        st_frame = max(0, int(clip_start * fps))
        et_frame = min(total_frames, int((clip_end if clip_end is not None else clip_start + 30.0) * fps))
        if et_frame <= st_frame or total_frames <= 0:
            st_frame = 0
            et_frame = max(1, total_frames)

        frame_span = et_frame - st_frame
        sample_positions = [0.15, 0.35, 0.50, 0.65, 0.85][:max(1, num_samples)]
        sample_indices = [st_frame + int(frame_span * p) for p in sample_positions]

        for s_idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, s_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            fh, fw = frame.shape[:2]
            if fh < 100 or fw < 100:
                continue

            total_samples += 1

            for c_name, c_roi in corners.items():
                cx0 = int(c_roi["x"] * fw)
                cy0 = int(c_roi["y"] * fh)
                cw0 = int(c_roi["w"] * fw)
                ch0 = int(c_roi["h"] * fh)

                roi_img = frame[cy0:cy0 + ch0, cx0:cx0 + cw0]
                if roi_img.size == 0:
                    continue

                gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)
                min_dim = max(18, int(min(cw0, ch0) * 0.12))

                detected_faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=4, minSize=(min_dim, min_dim)
                )
                if len(detected_faces) == 0 and profile_cascade is not None:
                    detected_faces = profile_cascade.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=4, minSize=(min_dim, min_dim)
                    )

                if len(detected_faces) > 0:
                    # Pick most prominent face in this corner
                    best_f = max(detected_faces, key=lambda f: f[2] * f[3])
                    fx, fy, fw_f, fh_f = best_f
                    global_fx = cx0 + fx
                    global_fy = cy0 + fy
                    face_cx = global_fx + fw_f // 2
                    face_cy = global_fy + fh_f // 2

                    # Target 9:4 (2.25:1) aspect ratio for 1080x480 facecam canvas
                    target_ar = 1080.0 / float(FACECAM_2L_HEIGHT)  # 2.25
                    cam_h = max(int(fh_f * 2.8), int(fh * 0.35), 320)
                    cam_h = min(fh, cam_h)
                    cam_w = int(round(cam_h * target_ar))
                    if cam_w > fw:
                        cam_w = fw
                        cam_h = int(round(cam_w / target_ar))

                    cam_x = int(face_cx - cam_w // 2)
                    cam_y = int(face_cy - cam_h * 0.38)

                    cam_x = max(0, min(fw - cam_w, cam_x))
                    cam_y = max(0, min(fh - cam_h, cam_y))
                    cam_w = max(2, cam_w - (cam_w % 2))
                    cam_h = max(2, cam_h - (cam_h % 2))
                    cam_x = max(0, cam_x - (cam_x % 2))
                    cam_y = max(0, cam_y - (cam_y % 2))

                    corner_hits[c_name].append({
                        "x": cam_x, "y": cam_y, "w": cam_w, "h": cam_h,
                        "fw": fw, "fh": fh,
                    })
    except Exception:
        pass
    finally:
        cap.release()

    if total_samples == 0:
        return {
            "detected": False,
            "confidence": "low",
            "confidence_score": 0.0,
            "corner": "bottom_right",
            "box": default_box,
            "message": "Tidak dapat membaca frame video untuk deteksi facecam.",
        }

    # Find corner with highest consistency
    best_corner = max(corner_hits, key=lambda c: len(corner_hits[c]))
    best_list = corner_hits[best_corner]
    consistency_ratio = len(best_list) / float(total_samples)

    # Require at least 60% consistency in the same corner to claim high confidence
    if consistency_ratio >= 0.60 and len(best_list) >= 2:
        avg_x = sum(b["x"] for b in best_list) / len(best_list)
        avg_y = sum(b["y"] for b in best_list) / len(best_list)
        avg_w = sum(b["w"] for b in best_list) / len(best_list)
        avg_h = sum(b["h"] for b in best_list) / len(best_list)
        ref_fw = best_list[0]["fw"]
        ref_fh = best_list[0]["fh"]

        norm_box = {
            "x": round(max(0.0, min(0.95, avg_x / ref_fw)), 3),
            "y": round(max(0.0, min(0.95, avg_y / ref_fh)), 3),
            "w": round(max(0.05, min(1.0 - (avg_x / ref_fw), avg_w / ref_fw)), 3),
            "h": round(max(0.05, min(1.0 - (avg_y / ref_fh), avg_h / ref_fh)), 3),
        }
        corner_labels = {
            "bottom_right": "Kanan Bawah",
            "bottom_left": "Kiri Bawah",
            "top_right": "Kanan Atas",
            "top_left": "Kiri Atas",
        }
        c_label = corner_labels.get(best_corner, best_corner)
        return {
            "detected": True,
            "confidence": "high",
            "confidence_score": round(consistency_ratio, 2),
            "corner": best_corner,
            "box": norm_box,
            "message": f"Facecam terdeteksi stabil di sudut {c_label} ({len(best_list)}/{total_samples} frame, keyakinan {int(consistency_ratio * 100)}%).",
        }
    else:
        preset_corner_boxes = {
            "bottom_right": {"x": 0.53, "y": 0.61, "w": 0.47, "h": 0.37},
            "bottom_left":  {"x": 0.00, "y": 0.61, "w": 0.47, "h": 0.37},
            "top_right":    {"x": 0.53, "y": 0.00, "w": 0.47, "h": 0.37},
            "top_left":     {"x": 0.00, "y": 0.00, "w": 0.47, "h": 0.37},
        }
        suggested_box = preset_corner_boxes.get(best_corner, default_box)
        return {
            "detected": False,
            "confidence": "low",
            "confidence_score": round(consistency_ratio, 2),
            "corner": best_corner,
            "box": suggested_box,
            "message": "Facecam tidak terdeteksi dengan keyakinan tinggi. Menyarankan preset standar (silakan sesuaikan kotak secara manual).",
        }


def _reframe_gaming_stack(
    in_path: str,
    out_path: str,
    ass_path: Optional[str] = None,
    preset: str = "auto",
    custom_box: Optional[Dict[str, Any]] = None,
    job_ctx: Optional[Any] = None,
    gaming_layout: Optional[str] = None,
) -> str:
    """Render gaming stream stack (1080x1920) in a single-pass FFmpeg filter_complex with auto-fallback support."""
    src_w, src_h = 1920, 1080
    try:
        cmd_probe = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            in_path,
        ]
        res = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
        parts = res.stdout.strip().split(",")
        if len(parts) == 2:
            src_w, src_h = int(parts[0]), int(parts[1])
    except Exception as e:
        log_job_message(f"[clip/local] Warning: ffprobe resolution fallback ({e})", job_ctx=job_ctx)

    preset_norm = (preset or "auto").strip().lower()
    is_auto = preset_norm in ("auto", "auto_detect")
    eff_layout = get_gaming_layout(
        preset_name=preset_norm,
        custom_box=custom_box,
        requested_layout=gaming_layout,
    )
    use_fallback = False
    top_crop = None
    mid_crop = None
    bot_crop = None
    layout_name = "2-Layer Clean (Facecam Atas + Gameplay Bawah)" if eff_layout == "cam_top" else "2-Layer Clean (Gameplay Atas + Facecam Bawah)"

    if is_auto and not custom_box:
        # Auto-Detect Facecam (AI): deteksi wajah di 4 sudut video
        detect_res = detect_facecam_candidate(video_path=in_path, num_samples=5)
        if detect_res.get("detected"):
            best_corner = detect_res.get("corner", "bottom_right")
            eff_preset = f"clean_2layer_{best_corner}"
            eff_box = {"facecam": detect_res.get("box")}
            top_crop, mid_crop, bot_crop = resolve_gaming_crop_boxes(
                preset_name=eff_preset,
                src_w=src_w,
                src_h=src_h,
                custom_box=eff_box,
            )
            layout_desc = "Facecam Atas" if eff_layout == "cam_top" else "Facecam Bawah"
            layout_name = f"2-Layer Clean (Auto Facecam {best_corner}, {layout_desc})"
            log_job_message(
                f"[clip/local] Facecam AI terdeteksi di sudut {best_corner}. Menggunakan layout {layout_name}.",
                job_ctx=job_ctx,
            )
        else:
            # Video gameplay murni tanpa webcam -> Auto-fallback ke Full Gameplay 9:16 Center Crop
            use_fallback = True
            layout_name = "Fallback Full Gameplay 9:16"
            log_job_message(
                "[clip/local] Auto-fallback aktif: Tidak ada wajah/webcam terdeteksi (gameplay murni). Merender Full Gameplay 9:16 Center Crop.",
                job_ctx=job_ctx,
            )
    else:
        top_crop, mid_crop, bot_crop = resolve_gaming_crop_boxes(
            preset_name=preset_norm,
            src_w=src_w,
            src_h=src_h,
            custom_box=custom_box,
        )
        has_face = validate_facecam_area(video_path=in_path, bot_crop=bot_crop, job_ctx=job_ctx)
        if not has_face and not custom_box and preset_norm in ("clean_2layer", "clean_2layer_cam_bottom", "clean_2layer_cam_top"):
            # Preset clean_2layer umum tanpa custom box jika tidak ada wajah sama sekali -> fallback
            cand_res = detect_facecam_candidate(video_path=in_path, num_samples=3)
            if not cand_res.get("detected"):
                use_fallback = True
                layout_name = "Fallback Full Gameplay 9:16"
                log_job_message(
                    "[clip/local] Auto-fallback aktif: Tidak ada wajah/webcam terdeteksi pada video (gameplay murni). Merender Full Gameplay 9:16 Center Crop.",
                    job_ctx=job_ctx,
                )
            else:
                log_job_message(
                    f"[clip/local] Info: Keyakinan deteksi wajah rendah pada area facecam ({bot_crop}). Tetap merender panel facecam sesuai pilihan pengguna.",
                    job_ctx=job_ctx,
                )
        elif not has_face:
            log_job_message(
                f"[clip/local] Info: Keyakinan deteksi wajah rendah pada area facecam ({bot_crop}). Tetap merender panel facecam sesuai pilihan pengguna.",
                job_ctx=job_ctx,
            )

    if use_fallback:
        filter_complex = build_gameplay_fallback_filter_complex(
            src_w=src_w,
            src_h=src_h,
            ass_path=ass_path,
        )
    else:
        filter_complex = build_gaming_filter_complex(
            top_crop=top_crop,
            mid_crop=mid_crop,
            bot_crop=bot_crop,
            ass_path=ass_path,
            layout=eff_layout,
        )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", in_path,
        "-filter_complex", filter_complex,
        "-map", "[v_out]", "-map", "0:a:0?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
        "-threads", "0",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-shortest",
        out_path,
    ]
    t_start = time.perf_counter()
    _run_ffmpeg_cmd(cmd, job_ctx=job_ctx)
    t_dur = time.perf_counter() - t_start
    log_job_message(
        f"[clip/local] Gaming short rendered ({layout_name}): {CANVAS_WIDTH}x{CANVAS_HEIGHT} (timing: {t_dur:.2f}s, preset: {preset})",
        job_ctx=job_ctx,
    )
    return out_path


def _reframe_dual_split(
    in_path: str,
    out_path: str,
    ass_path: Optional[str] = None,
    job_ctx: Optional[Any] = None,
) -> str:
    """Render dual-speaker / split-screen vertical short (1080x1920).
    Scene with 2 people or 2 sections:
    - Top panel (1080x960): Centered on Person 1 (Host / Left speaker)
    - Bottom panel (1080x960): Centered on Person 2 (Guest / Right speaker)
    Stacked vertically with zero distortion and burned-in subtitles.
    """
    src_w, src_h = 1920, 1080
    try:
        cmd_probe = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            in_path,
        ]
        res = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
        parts = res.stdout.strip().split(",")
        if len(parts) == 2:
            src_w, src_h = int(parts[0]), int(parts[1])
    except Exception as e:
        log_job_message(f"[clip/local] Warning: ffprobe resolution fallback ({e})", job_ctx=job_ctx)

    try:
        import cv2  # type: ignore
    except ImportError as e:
        raise RuntimeError("OpenCV diperlukan untuk mode dual split.") from e

    cap = cv2.VideoCapture(in_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    detected_faces_list: List[Tuple[int, int, int, int]] = []

    try:
        sample_fractions = [0.15, 0.30, 0.50, 0.70, 0.85]
        sample_indices = [max(0, min(total_frames - 1, int(total_frames * p))) for p in sample_fractions]
        if not sample_indices:
            sample_indices = [0]

        for s_idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, s_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            fh, fw = frame.shape[:2]
            f_faces = _detect_faces_with_yunet(frame, fw, fh)
            if not f_faces:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                if os.path.exists(cascade_path):
                    fc = cv2.CascadeClassifier(cascade_path)
                    if not fc.empty():
                        h_faces = fc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                        f_faces = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in h_faces]
            for f in f_faces:
                detected_faces_list.append(f)
    except Exception as e:
        log_job_message(f"[clip/local] Note: Face sampling in dual split encountered {e}", job_ctx=job_ctx)
    finally:
        cap.release()

    target_ar = 1080.0 / 960.0  # 1.125 (9:8)

    def _calc_panel_crop(cx: int, cy: int, fh_f: int) -> Tuple[int, int, int, int]:
        panel_h = min(src_h, max(int(fh_f * 2.8), int(src_h * 0.75)))
        panel_w = int(round(panel_h * target_ar))
        if panel_w > src_w:
            panel_w = src_w
            panel_h = int(round(panel_w / target_ar))
        x = max(0, min(src_w - panel_w, int(cx - panel_w // 2)))
        y = max(0, min(src_h - panel_h, int(cy - panel_h * 0.38)))
        panel_w = max(2, panel_w - (panel_w % 2))
        panel_h = max(2, panel_h - (panel_h % 2))
        x = max(0, x - (x % 2))
        y = max(0, y - (y % 2))
        return x, y, panel_w, panel_h

    left_faces = [f for f in detected_faces_list if (f[0] + f[2] // 2) < src_w * 0.52]
    right_faces = [f for f in detected_faces_list if (f[0] + f[2] // 2) >= src_w * 0.48]

    if left_faces and right_faces:
        avg_left_cx = int(sum(f[0] + f[2] // 2 for f in left_faces) / len(left_faces))
        avg_left_cy = int(sum(f[1] + f[3] // 2 for f in left_faces) / len(left_faces))
        avg_left_h = int(sum(f[3] for f in left_faces) / len(left_faces))

        avg_right_cx = int(sum(f[0] + f[2] // 2 for f in right_faces) / len(right_faces))
        avg_right_cy = int(sum(f[1] + f[3] // 2 for f in right_faces) / len(right_faces))
        avg_right_h = int(sum(f[3] for f in right_faces) / len(right_faces))

        top_crop = _calc_panel_crop(avg_left_cx, avg_left_cy, avg_left_h)
        bot_crop = _calc_panel_crop(avg_right_cx, avg_right_cy, avg_right_h)
        desc = "Dual Speaker (Host Kiri Atas + Tamu Kanan Bawah)"
    elif len(detected_faces_list) >= 2:
        detected_faces_list.sort(key=lambda f: f[0])
        f1 = detected_faces_list[0]
        f2 = detected_faces_list[-1]
        top_crop = _calc_panel_crop(f1[0] + f1[2] // 2, f1[1] + f1[3] // 2, f1[3])
        bot_crop = _calc_panel_crop(f2[0] + f2[2] // 2, f2[1] + f2[3] // 2, f2[3])
        desc = "Dual Wajah (Orang 1 Atas + Orang 2 Bawah)"
    elif len(detected_faces_list) == 1:
        f1 = detected_faces_list[0]
        top_crop = _calc_panel_crop(f1[0] + f1[2] // 2, f1[1] + f1[3] // 2, f1[3])
        bot_crop = _calc_panel_crop(src_w // 2, src_h // 2, f1[3])
        desc = "Dual Wajah (Pembicara Atas + Scene Utama Bawah)"
    else:
        top_crop = _calc_panel_crop(int(src_w * 0.30), src_h // 2, int(src_h * 0.3))
        bot_crop = _calc_panel_crop(int(src_w * 0.70), src_h // 2, int(src_h * 0.3))
        desc = "Dual Wajah (Split Kiri-Kanan ke Atas-Bawah)"

    tx, ty, tw, th = top_crop
    bx, by, bw, bh = bot_crop

    PANEL_HEIGHT = 960
    filters = [
        "[0:v]split=2[raw_top][raw_bot]",
        f"[raw_top]crop={tw}:{th}:{tx}:{ty},scale={CANVAS_WIDTH}:{PANEL_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{PANEL_HEIGHT}:(in_w-out_w)/2:max(0\\,(in_h-out_h)*0.15)[v_top]",
        f"[raw_bot]crop={bw}:{bh}:{bx}:{by},scale={CANVAS_WIDTH}:{PANEL_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{PANEL_HEIGHT}:(in_w-out_w)/2:max(0\\,(in_h-out_h)*0.15)[v_bot]",
        "[v_top][v_bot]vstack=inputs=2[v_stacked]",
    ]

    if ass_path and os.path.exists(ass_path):
        escaped_ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        if os.path.isdir(FONTS_DIR):
            escaped_fontsdir = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
            filters.append(f"[v_stacked]ass=filename='{escaped_ass}':fontsdir='{escaped_fontsdir}'[v_out]")
        else:
            filters.append(f"[v_stacked]ass=filename='{escaped_ass}'[v_out]")
    else:
        filters.append("[v_stacked]null[v_out]")

    filter_complex = ";".join(filters)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", in_path,
        "-filter_complex", filter_complex,
        "-map", "[v_out]", "-map", "0:a:0?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
        "-threads", "0",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-shortest",
        out_path,
    ]
    t_start = time.perf_counter()
    _run_ffmpeg_cmd(cmd, job_ctx=job_ctx)
    t_dur = time.perf_counter() - t_start
    log_job_message(
        f"[clip/local] Dual-wajah short rendered ({desc}): {CANVAS_WIDTH}x{CANVAS_HEIGHT} (timing: {t_dur:.2f}s)",
        job_ctx=job_ctx,
    )
    return out_path


def _build_ffmpeg_crop_expression(
    trajectory: List[Any],
    src_w: int,
    src_h: int,
    crop_w: int,
    crop_h: int,
) -> Tuple[str, str]:
    """Convert sampled crop trajectory points into native FFmpeg crop filter expressions with smooth lerp panning and instant cuts."""
    if not trajectory:
        safe_x = max(0, min(src_w - crop_w, (src_w - crop_w) // 2))
        safe_y = max(0, min(src_h - crop_h, (src_h - crop_h) // 2))
        return str(safe_x), str(safe_y)

    xs = [pt[1] for pt in trajectory]
    ys = [pt[2] for pt in trajectory]
    has_cut = any(pt[3] for pt in trajectory if len(pt) > 3)

    # If motion across continuous shot is minimal, lock to rock-solid stable median coordinate
    if not has_cut and (max(xs) - min(xs) <= 48) and (max(ys) - min(ys) <= 48):
        med_x = max(0, min(src_w - crop_w, int(round(sum(xs) / len(xs)))))
        med_y = max(0, min(src_h - crop_h, int(round(sum(ys) / len(ys)))))
        return str(med_x), str(med_y)

    # Segment trajectory into contiguous shot blocks on large jumps or sustained movement
    segments: List[Dict[str, Any]] = []
    curr_pts = [trajectory[0]]
    curr_start_t = trajectory[0][0]

    for i in range(1, len(trajectory)):
        pt = trajectory[i]
        prev_pt = trajectory[i - 1]
        t, x, y = pt[0], pt[1], pt[2]
        explicit_cut = bool(pt[3]) if len(pt) > 3 else False

        # Instantaneous jump: distance >= 120 in consecutive samples or explicit cut
        jump_x = abs(x - prev_pt[1])
        jump_y = abs(y - prev_pt[2])
        is_instant_jump = (jump_x >= 120 or jump_y >= 120)

        # Deviation from current segment median
        curr_xs = [p[1] for p in curr_pts]
        curr_ys = [p[2] for p in curr_pts]
        med_x = curr_xs[len(curr_xs) // 2]
        med_y = curr_ys[len(curr_ys) // 2]
        dev_x = abs(x - med_x)
        dev_y = abs(y - med_y)

        # Split into new segment if jump, cut, or significant deviation over time
        if explicit_cut or is_instant_jump:
            seg_x = max(0, min(src_w - crop_w, int(round(sum(curr_xs) / len(curr_xs)))))
            seg_y = max(0, min(src_h - crop_h, int(round(sum(curr_ys) / len(curr_ys)))))
            segments.append({
                "val_x": seg_x,
                "val_y": seg_y,
                "start_t": curr_start_t,
                "end_t": prev_pt[0],
                "is_cut": explicit_cut or is_instant_jump,
            })
            curr_pts = [pt]
            curr_start_t = t
        elif (dev_x > 50 or dev_y > 50) and (t - curr_start_t) >= 0.40:
            seg_x = max(0, min(src_w - crop_w, int(round(sum(curr_xs) / len(curr_xs)))))
            seg_y = max(0, min(src_h - crop_h, int(round(sum(curr_ys) / len(curr_ys)))))
            segments.append({
                "val_x": seg_x,
                "val_y": seg_y,
                "start_t": curr_start_t,
                "end_t": prev_pt[0],
                "is_cut": False,
            })
            curr_pts = [pt]
            curr_start_t = t
        else:
            curr_pts.append(pt)

    if curr_pts:
        curr_xs = [p[1] for p in curr_pts]
        curr_ys = [p[2] for p in curr_pts]
        seg_x = max(0, min(src_w - crop_w, int(round(sum(curr_xs) / len(curr_xs)))))
        seg_y = max(0, min(src_h - crop_h, int(round(sum(curr_ys) / len(curr_ys)))))
        segments.append({
            "val_x": seg_x,
            "val_y": seg_y,
            "start_t": curr_start_t,
            "end_t": trajectory[-1][0],
            "is_cut": False,
        })

    # Merge contiguous segments where differences are negligible
    merged: List[Dict[str, Any]] = []
    for s in segments:
        if not merged:
            merged.append(s)
        else:
            p = merged[-1]
            if (not s.get("is_cut")) and abs(s["val_x"] - p["val_x"]) <= 35 and abs(s["val_y"] - p["val_y"]) <= 35:
                p["end_t"] = s["end_t"]
            else:
                merged.append(s)
    segments = merged

    # Guard against deep FFmpeg filter expression recursion (exit code -22 / EINVAL):
    # Bound segments to MAX_CROP_SEGMENTS (<= 6) so nested if() depth never exceeds FFmpeg's parser stack
    MAX_CROP_SEGMENTS = 6
    while len(segments) > MAX_CROP_SEGMENTS:
        best_idx = -1
        min_delta = float("inf")
        for idx in range(len(segments) - 1):
            s1 = segments[idx]
            s2 = segments[idx + 1]
            penalty = 120.0 if (s2.get("is_cut") or s1.get("is_cut")) else 0.0
            delta = abs(s1["val_x"] - s2["val_x"]) + abs(s1["val_y"] - s2["val_y"]) + penalty
            if delta < min_delta:
                min_delta = delta
                best_idx = idx
        if best_idx >= 0:
            s1 = segments[best_idx]
            s2 = segments[best_idx + 1]
            dur1 = max(0.01, s1["end_t"] - s1["start_t"])
            dur2 = max(0.01, s2["end_t"] - s2["start_t"])
            s1["val_x"] = int(round((s1["val_x"] * dur1 + s2["val_x"] * dur2) / (dur1 + dur2)))
            s1["val_y"] = int(round((s1["val_y"] * dur1 + s2["val_y"] * dur2) / (dur1 + dur2)))
            s1["end_t"] = s2["end_t"]
            segments.pop(best_idx + 1)
        else:
            break

    def _build_channel_expression(segs: List[Dict[str, Any]], val_key: str, max_bound: int) -> str:
        if max_bound <= 0:
            return "0"
        if not segs:
            return str(max(0, min(max_bound, max_bound // 2)))
        if len(segs) == 1:
            return str(max(0, min(max_bound, int(segs[0][val_key]))))

        vals = [max(0, min(max_bound, int(s[val_key]))) for s in segs]
        # Jika deviasi pergerakan kecil (<= 40px), kunci ke median statis untuk stabilitas maksimal
        if max(vals) - min(vals) <= 40:
            med_val = max(0, min(max_bound, int(round(sum(vals) / len(vals)))))
            return str(med_val)

        expr = str(vals[-1])
        for idx in range(len(segs) - 2, -1, -1):
            curr = segs[idx]
            nxt = segs[idx + 1]
            v_curr = vals[idx]
            v_nxt = vals[idx + 1]
            diff = v_nxt - v_curr

            # Gunakan single-level if switch jika:
            # - Beda posisi kecil (<= 40px)
            # - Ada scene cut eksplisit
            # - Gerakan sangat jauh (> 160px)
            # - Atau jumlah segmen > 3 (mencegah akumulasi nested if ganda lerp)
            if abs(diff) <= 40 or len(segs) > 3 or nxt.get("is_cut", False) or abs(diff) > 160:
                t_switch = max(0.0, float(nxt["start_t"]))
                expr = f"if(lt(t,{t_switch:.3f}),{v_curr},{expr})"
            else:
                # Smooth pan terkontrol khusus segmen sedikit (<= 3)
                ts = max(0.0, float(curr["end_t"]))
                te = max(0.0, float(nxt["start_t"]))
                if te <= ts:
                    dt = 0.50
                    te = ts + dt
                else:
                    dt = max(0.40, min(0.80, te - ts))
                    te = ts + dt
                lerp = f"{v_curr}+({diff})*(t-{ts:.3f})/{dt:.3f}"
                expr = f"if(lt(t,{ts:.3f}),{v_curr},if(lt(t,{te:.3f}),{lerp},{expr}))"

        # Safety valve: jika panjang ekspresi > 260 chars, revert ke median statis
        if len(expr) > 260:
            med_val = max(0, min(max_bound, int(round(sum(vals) / len(vals)))))
            return str(med_val)

        return expr

    x_expr = _build_channel_expression(segments, "val_x", src_w - crop_w)
    y_expr = _build_channel_expression(segments, "val_y", src_h - crop_h)
    return x_expr, y_expr


def _reframe_vertical(
    in_path: str,
    out_path: str,
    aspect_ratio: str,
    ass_path: Optional[str] = None,
    job_ctx: Optional[Any] = None,
    framing_mode: str = "podcast",
    gaming_preset: str = "auto",
    gaming_custom_box: Optional[Dict[str, Any]] = None,
    gaming_layout: Optional[str] = None,
) -> str:
    """Crop cut clip to target aspect ratio (tracking faces) and burn subtitles with native single-pass FFmpeg."""
    framing_norm = (framing_mode or "podcast").strip().lower()
    if framing_norm == "gaming":
        return _reframe_gaming_stack(
            in_path=in_path,
            out_path=out_path,
            ass_path=ass_path,
            preset=gaming_preset,
            custom_box=gaming_custom_box,
            job_ctx=job_ctx,
            gaming_layout=gaming_layout,
        )
    if framing_norm in ("dual", "split"):
        return _reframe_dual_split(
            in_path=in_path,
            out_path=out_path,
            ass_path=ass_path,
            job_ctx=job_ctx,
        )

    try:
        import cv2  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "opencv-python is required for --mode local. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    target_ratio = _ratio(aspect_ratio)
    cap = cv2.VideoCapture(in_path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open {in_path}")

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Compute crop dimensions
    if target_ratio < src_w / src_h:
        crop_h = src_h
        crop_w = int(crop_h * target_ratio)
    else:
        crop_w = src_w
        crop_h = int(crop_w / target_ratio)
    crop_w = max(2, crop_w - (crop_w % 2))
    crop_h = max(2, crop_h - (crop_h % 2))

    face_cascade = None
    profile_cascade = None
    yunet_available = (_get_yunet_detector(640, 360) is not None)
    framing_norm = (framing_mode or "podcast").strip().lower()
    if framing_norm != "center":
        try:
            if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades") and hasattr(cv2, "CascadeClassifier"):
                cascade_alt2 = cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
                cascade_default = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                cascade_path = cascade_alt2 if os.path.exists(cascade_alt2) else cascade_default
                fc = cv2.CascadeClassifier(cascade_path)
                if not fc.empty():
                    face_cascade = fc
                prof_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
                if os.path.exists(prof_path):
                    pc = cv2.CascadeClassifier(prof_path)
                    if not pc.empty():
                        profile_cascade = pc
        except Exception as e:
            log_job_message(f"[clip/local] Note: Face detector unavailable ({e}), defaulting to center crop.", job_ctx=job_ctx)

    t_cv = 0.0
    has_detectors = yunet_available or (face_cascade is not None) or (profile_cascade is not None)
    if framing_norm == "center" or not has_detectors:
        if cap is not None:
            cap.release()
            del cap
        x_safe = max(0, min(src_w - crop_w, (src_w - crop_w) // 2))
        y_safe = max(0, min(src_h - crop_h, (src_h - crop_h) // 2))
        x_expr, y_expr = str(x_safe), str(y_safe)
    else:
        tracker = PodcastFramingTracker(
            src_w=src_w,
            src_h=src_h,
            crop_w=crop_w,
            crop_h=crop_h,
            fps=fps,
            framing_mode=framing_norm,
        )
        detect_interval = max(6, int(round(fps * 0.25)))
        frame_idx = 0
        prev_gray = None
        trajectory: List[Tuple[float, int, int, bool]] = []
        t_cv_start = time.perf_counter()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                current_time = frame_idx / fps
                is_scene_cut = False
                if frame_idx % detect_interval == 0:
                    try:
                        gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        gray = cv2.resize(gray_full, (0, 0), fx=0.5, fy=0.5)
                        if prev_gray is not None:
                            diff = cv2.absdiff(gray, prev_gray)
                            mean_diff = float(cv2.mean(diff)[0])
                            if mean_diff > 35.0:
                                is_scene_cut = True
                        prev_gray = gray

                        # 1. Primary: Ultra-accurate deep learning YuNet detection
                        orig_faces = _detect_faces_with_yunet(frame, src_w, src_h)

                        # 2. Fallback: Multi-view Haar Cascades if YuNet is unavailable or returned 0 faces
                        if not orig_faces and (face_cascade is not None or profile_cascade is not None):
                            faces = _detect_multiview_faces(
                                gray,
                                face_cascade=face_cascade,
                                profile_cascade=profile_cascade,
                                scale_factor=1.1,
                                min_neighbors=5,
                                min_size=(36, 36),
                            )
                            orig_faces = [(int(x * 2), int(y * 2), int(w * 2), int(h * 2)) for (x, y, w, h) in faces]

                        tracker.update_faces(
                            orig_faces,
                            is_scene_cut=is_scene_cut,
                            current_time=current_time,
                            frame_gray=gray_full,
                        )
                        if frame_idx == 0:
                            tracker.current_center = tracker.target_center
                    except Exception:
                        pass

                x0, y0, cw, ch = tracker.step(is_scene_cut=is_scene_cut)
                is_cut_event = is_scene_cut or tracker.last_switch_was_cut
                trajectory.append((current_time, x0, y0, is_cut_event))
                frame_idx += 1

                if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout") and (frame_idx % 60 == 0):
                    job_ctx.check_cancellation_or_timeout()
        finally:
            if cap is not None:
                cap.release()
                del cap
            gc.collect()

        t_cv = time.perf_counter() - t_cv_start
        x_expr, y_expr = _build_ffmpeg_crop_expression(trajectory, src_w, src_h, crop_w, crop_h)

    safe_x = max(0, min(src_w - crop_w, (src_w - crop_w) // 2))
    safe_y = max(0, min(src_h - crop_h, (src_h - crop_h) // 2))

    def _is_valid_output(path: str) -> bool:
        return os.path.exists(path) and os.path.getsize(path) > 1024

    def _cleanup_failed_output(path: str) -> None:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    # Target scaled resolution for vertical (1080x1920) or square (1080x1080)
    out_w, out_h = (1080, 1920) if target_ratio < 0.6 else (1080, 1080)
    scale_filter_str = f"scale={out_w}:{out_h}:flags=lanczos"

    # Single-pass native FFmpeg filter: dynamic crop + scale + burn ASS subtitles + audio mux
    vf_filters = [f"crop={crop_w}:{crop_h}:x='{x_expr}':y='{y_expr}'", scale_filter_str]
    ass_filter_str = None
    if ass_path and os.path.exists(ass_path):
        sub_escaped = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        if os.path.isdir(FONTS_DIR):
            fontsdir_escaped = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
            ass_filter_str = f"ass=filename='{sub_escaped}':fontsdir='{fontsdir_escaped}'"
        else:
            ass_filter_str = f"ass=filename='{sub_escaped}'"
        vf_filters.append(ass_filter_str)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", in_path,
        "-vf", ",".join(vf_filters),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
        "-threads", "0",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    t_mux_start = time.perf_counter()
    success = False

    try:
        _run_ffmpeg_cmd(cmd, job_ctx=job_ctx)
        if _is_valid_output(out_path):
            success = True
        else:
            _cleanup_failed_output(out_path)
            raise RuntimeError("File hasil dynamic crop 0 bytes atau tidak terbentuk.")
    except Exception as e:
        log_job_message(
            f"[clip/local] Peringatan: Render dynamic crop FFmpeg gagal ({e}), mengaktifkan fallback static crop...",
            job_ctx=job_ctx,
        )
        _cleanup_failed_output(out_path)

    # Fallback Tahap 1: Static crop + scale + Subtitles (tanpa dynamic expression & tanpa -shortest)
    if not success:
        fb1_filters = [f"crop={crop_w}:{crop_h}:{safe_x}:{safe_y}", scale_filter_str]
        if ass_filter_str:
            fb1_filters.append(ass_filter_str)
        cmd_fb1 = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", in_path,
            "-vf", ",".join(fb1_filters),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
            "-threads", "0",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            out_path,
        ]
        try:
            _run_ffmpeg_cmd(cmd_fb1, job_ctx=job_ctx)
            if _is_valid_output(out_path):
                success = True
                log_job_message("[clip/local] Sukses render fallback tahap 1 (static crop + subtitles).", job_ctx=job_ctx)
            else:
                _cleanup_failed_output(out_path)
                raise RuntimeError("File hasil fallback tahap 1 kosong (0 bytes).")
        except Exception as e_fb1:
            log_job_message(
                f"[clip/local] Peringatan: Fallback tahap 1 gagal ({e_fb1}), mencoba fallback tahap 2 (pure static crop tanpa subtitle)...",
                job_ctx=job_ctx,
            )
            _cleanup_failed_output(out_path)

    # Fallback Tahap 2 (Garansi Penuh Anti 0-Bytes): Pure static crop + scale tanpa filter subtitle
    if not success:
        cmd_fb2 = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", in_path,
            "-vf", f"crop={crop_w}:{crop_h}:{safe_x}:{safe_y},{scale_filter_str}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "22",
            "-threads", "0",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            out_path,
        ]
        try:
            _run_ffmpeg_cmd(cmd_fb2, job_ctx=job_ctx)
            if _is_valid_output(out_path):
                success = True
                log_job_message("[clip/local] Sukses render fallback tahap 2 (pure static crop aman).", job_ctx=job_ctx)
            else:
                _cleanup_failed_output(out_path)
                raise RuntimeError("File hasil fallback tahap 2 kosong (0 bytes).")
        except Exception as e_fb2:
            _cleanup_failed_output(out_path)
            raise RuntimeError(f"Gagal merender klip setelah semua fallback static crop: {e_fb2}")

    t_mux = time.perf_counter() - t_mux_start

    log_job_message(
        f"[clip/local] Reframe timing: opencv_loop={t_cv:.2f}s, ffmpeg_mux={t_mux:.2f}s",
        job_ctx=job_ctx,
    )
    return out_path


_CLIPPER_WHISPER_MODEL = None


def _get_whisper_model():
    global _CLIPPER_WHISPER_MODEL
    if _CLIPPER_WHISPER_MODEL is None:
        try:
            import faster_whisper
            _CLIPPER_WHISPER_MODEL = faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")
        except Exception:
            try:
                import faster_whisper
                _CLIPPER_WHISPER_MODEL = faster_whisper.WhisperModel("tiny", device="cpu", compute_type="int8")
            except Exception:
                _CLIPPER_WHISPER_MODEL = False
    return _CLIPPER_WHISPER_MODEL if _CLIPPER_WHISPER_MODEL is not False else None


def _enrich_clip_with_whisper(
    clip_media_path: str,
    canonical_segments: Optional[List[Dict]] = None,
    clip_start: float = 0.0,
    clip_end: float = 0.0,
) -> Optional[List[Dict]]:
    """Transcribe a cut short clip locally to extract exact frame-accurate word timestamps."""
    if not clip_media_path or not os.path.exists(clip_media_path):
        return None
    model = _get_whisper_model()
    if not model:
        return None

    try:
        segs, info = model.transcribe(clip_media_path, word_timestamps=True)
        raw_words: List[Dict] = []
        for s in segs:
            for w in (getattr(s, "words", None) or []):
                w_str = (getattr(w, "word", "") or "").strip()
                if not w_str:
                    continue
                try:
                    w_st = round(float(w.start), 3)
                    w_et = round(float(w.end), 3)
                except (ValueError, TypeError):
                    continue
                if math.isfinite(w_st) and math.isfinite(w_et) and w_et > w_st:
                    raw_words.append({
                        "word": w_str,
                        "start": w_st,
                        "end": w_et,
                    })

        if not raw_words:
            return None

        # Align with canonical words from canonical_segments if available
        if canonical_segments:
            can_words: List[str] = []
            for c_seg in canonical_segments:
                if not isinstance(c_seg, dict):
                    continue
                try:
                    c_s = float(c_seg.get("start", 0.0))
                    c_e = float(c_seg.get("end", 0.0))
                except (ValueError, TypeError):
                    continue
                if c_e > clip_start and c_s < clip_end:
                    txt = str(c_seg.get("text", "")).strip()
                    if txt:
                        can_words.extend(txt.split())

            if can_words:
                sm = difflib.SequenceMatcher(
                    None,
                    [cw.lower() for cw in can_words],
                    [rw["word"].lower() for rw in raw_words],
                )
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "equal" or (tag == "replace" and (i2 - i1) >= (j2 - j1)):
                        for k in range(j2 - j1):
                            raw_words[j1 + k]["word"] = can_words[i1 + k]

        clip_dur = round(raw_words[-1]["end"], 3)
        return [{
            "start": 0.0,
            "end": max(clip_dur, 0.1),
            "text": " ".join(w["word"] for w in raw_words),
            "words": raw_words,
        }]
    except Exception:
        return None


def crop_clip_local(
    source_path: str,
    start_time: float,
    end_time: float,
    aspect_ratio: str,
    out_path: str,
    segments: Optional[List[Dict]] = None,
    burn_subtitles: bool = True,
    job_ctx: Optional[Any] = None,
    source_duration: Optional[float] = None,
    untrusted_spans: Optional[List[Dict]] = None,
    framing_mode: str = "podcast",
    subtitle_style: str = "karaoke",
    gaming_preset: str = "auto",
    gaming_custom_box: Optional[Dict] = None,
    font_family: Optional[str] = None,
    gaming_layout: Optional[str] = None,
    enable_sfx: bool = True,
    remove_silence: bool = False,
) -> str:
    """Cut + reframe one highlight + burn subtitles, returning local mp4 path."""
    t_start = time.perf_counter()
    cut_path = out_path + ".cut.mp4"
    ass_path = out_path + ".ass"
    vtt_path = out_path.rsplit(".", 1)[0] + ".vtt"

    eff_source_dur = source_duration
    if (eff_source_dur is None or eff_source_dur <= 0) and source_path and os.path.exists(source_path):
        eff_source_dur = _probe_media_duration(source_path)

    has_subs = False
    cues: Optional[List[Dict]] = None
    t_sub = 0.0
    t_cut = 0.0
    t_reframe = 0.0
    effective_burn = burn_subtitles and (subtitle_style or "karaoke").strip().lower() != "none"

    try:
        t_cut_start = time.perf_counter()
        _cut_subclip(source_path, start_time, end_time, cut_path, job_ctx=job_ctx)
        t_cut = time.perf_counter() - t_cut_start

        if remove_silence and os.path.exists(cut_path):
            from ..silence_cutter import trim_silence_from_video
            tight_cut_path = cut_path + ".tight.mp4"
            effective_cut, trimmed = trim_silence_from_video(
                cut_path, tight_cut_path, min_silence_duration=0.45, job_ctx=job_ctx
            )
            if trimmed and os.path.exists(effective_cut):
                try:
                    os.replace(effective_cut, cut_path)
                    eff_source_dur = _probe_media_duration(cut_path)
                except Exception:
                    pass

        if segments:
            t_sub_start = time.perf_counter()
            # Check if any segment intersecting the clip window already has word-level timestamps
            has_words_in_window = False
            for seg in segments:
                if not isinstance(seg, dict):
                    continue
                try:
                    s_st = float(seg.get("start", 0.0))
                    s_et = float(seg.get("end", 0.0))
                except (ValueError, TypeError):
                    continue
                if s_et > start_time and s_st < end_time:
                    w_list = seg.get("words")
                    if isinstance(w_list, list) and len(w_list) > 0:
                        has_words_in_window = True
                        break

            target_segments = segments
            target_st = start_time
            target_et = end_time
            target_dur = eff_source_dur

            # If transcript lacks word-level timestamps, enrich locally with Whisper on the cut clip
            if not has_words_in_window and os.path.exists(cut_path):
                enriched = _enrich_clip_with_whisper(
                    cut_path,
                    canonical_segments=segments,
                    clip_start=start_time,
                    clip_end=end_time,
                )
                if enriched:
                    target_segments = enriched
                    target_st = 0.0
                    target_et = max(0.1, end_time - start_time)
                    target_dur = target_et

            # Build validated cues ONCE as single source of truth for both ASS and VTT
            cues = build_validated_cues(
                segments=target_segments,
                clip_start=target_st,
                clip_end=target_et,
                source_duration=target_dur,
                untrusted_spans=untrusted_spans,
                target_chunk_size=4,
            )
            if cues:
                # Produce .vtt for browser preview tracks using validated cues
                create_vtt_subtitle_file(
                    segments=target_segments,
                    clip_start=target_st,
                    clip_end=target_et,
                    out_vtt_path=vtt_path,
                    cues=cues,
                    framing_mode=framing_mode,
                    gaming_preset=gaming_preset,
                    gaming_layout=gaming_layout,
                )
                if effective_burn:
                    if (framing_mode or "").strip().lower() in ("gaming", "dual", "split"):
                        res_w, res_h = (CANVAS_WIDTH, CANVAS_HEIGHT)
                    else:
                        target_ratio = _ratio(aspect_ratio)
                        res_w, res_h = (1080, 1920) if target_ratio < 0.6 else (1080, 1080)
                    has_subs = create_ass_subtitle_file(
                        segments=target_segments,
                        clip_start=target_st,
                        clip_end=target_et,
                        out_ass_path=ass_path,
                        width=res_w,
                        height=res_h,
                        cues=cues,
                        subtitle_style=subtitle_style,
                        framing_mode=framing_mode,
                        font_family=font_family,
                        gaming_preset=gaming_preset,
                        gaming_layout=gaming_layout,
                    )
            t_sub = time.perf_counter() - t_sub_start

        t_ref_start = time.perf_counter()
        _reframe_vertical(
            cut_path,
            out_path,
            aspect_ratio,
            ass_path=ass_path if has_subs else None,
            job_ctx=job_ctx,
            framing_mode=framing_mode,
            gaming_preset=gaming_preset,
            gaming_custom_box=gaming_custom_box,
            gaming_layout=gaming_layout,
        )
        t_reframe = time.perf_counter() - t_ref_start

        if enable_sfx and cues and os.path.exists(out_path):
            from ..sfx_manager import detect_sfx_events, apply_sfx_to_video
            sfx_events = detect_sfx_events(cues)
            if sfx_events:
                sfx_tmp_out = out_path + ".sfx.mp4"
                res_path = apply_sfx_to_video(
                    out_path, sfx_tmp_out, sfx_events, sfx_volume=0.35, job_ctx=job_ctx
                )
                if res_path == sfx_tmp_out and os.path.exists(sfx_tmp_out):
                    try:
                        os.replace(sfx_tmp_out, out_path)
                    except Exception:
                        pass
    finally:
        for tmp_file in [cut_path, ass_path]:
            if os.path.exists(tmp_file):
                for _ in range(5):
                    try:
                        os.remove(tmp_file)
                        break
                    except (PermissionError, OSError):
                        time.sleep(0.2)
    t_total = time.perf_counter() - t_start
    log_job_message(
        f"[clip/local] Stage timing: sub={t_sub:.2f}s, cut={t_cut:.2f}s, reframe={t_reframe:.2f}s, total={t_total:.2f}s",
        job_ctx=job_ctx,
    )
    return out_path


def crop_highlights_local(
    source_path: str,
    highlights: List[Dict],
    aspect_ratio: str = "9:16",
    out_dir: Optional[str] = None,
    transcript: Optional[Dict] = None,
    burn_subtitles: bool = True,
    job_ctx: Optional[Any] = None,
    framing_mode: str = "podcast",
    subtitle_style: str = "karaoke",
    gaming_preset: str = "auto",
    gaming_custom_box: Optional[Dict] = None,
    font_family: Optional[str] = None,
    gaming_layout: Optional[str] = None,
    enable_sfx: bool = True,
    remove_silence: bool = False,
) -> List[Dict]:
    """Crop every highlight, burn subtitles, and return list with clip_url."""
    if out_dir is None:
        out_dir = os.path.join(LOCAL_OUTPUT_DIR, f"job_{uuid.uuid4().hex[:8]}")
    os.makedirs(out_dir, exist_ok=True)

    # Extract segments and metadata from verified transcript only (remove unverified legacy srt fallback)
    segments: List[Dict] = []
    untrusted_spans: List[Dict] = []
    source_duration: Optional[float] = None
    if transcript and isinstance(transcript, dict):
        if "segments" in transcript and isinstance(transcript["segments"], list):
            segments = transcript["segments"]
        if "untrusted_spans" in transcript and isinstance(transcript["untrusted_spans"], list):
            untrusted_spans = transcript["untrusted_spans"]
        if "duration" in transcript and isinstance(transcript["duration"], (int, float)):
            source_duration = float(transcript["duration"])

    results: List[Dict] = []
    for i, h in enumerate(highlights, 1):
        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            try:
                job_ctx.check_cancellation_or_timeout()
            except (JobCancelledException, JobTimeoutException) as e:
                log_job_message(f"[clip/local] Pembatalan atau timeout sebelum klip #{i}: {e}", job_ctx=job_ctx)
                if results:
                    break
                raise

        out_path = os.path.join(out_dir, f"short_{i:02d}.mp4")
        vtt_path = os.path.join(out_dir, f"short_{i:02d}.vtt")
        log_job_message(f"[clip/local] {i}/{len(highlights)}: {h.get('title', '(untitled)')}", job_ctx=job_ctx)
        try:
            crop_clip_local(
                source_path=source_path,
                start_time=float(h["start_time"]),
                end_time=float(h["end_time"]),
                aspect_ratio=aspect_ratio,
                out_path=out_path,
                segments=segments,
                burn_subtitles=burn_subtitles,
                job_ctx=job_ctx,
                source_duration=source_duration,
                untrusted_spans=untrusted_spans,
                framing_mode=framing_mode,
                subtitle_style=subtitle_style,
                gaming_preset=gaming_preset,
                gaming_custom_box=gaming_custom_box,
                font_family=font_family,
                gaming_layout=gaming_layout,
                enable_sfx=enable_sfx,
                remove_silence=remove_silence,
            )
            vtt_url = vtt_path if os.path.exists(vtt_path) else None
            clip_record = {
                **h,
                "clip_url": out_path,
                "vtt_url": vtt_url,
                "filename": f"short_{i:02d}.mp4",
                "clip_index": i,
                "out_dir": out_dir,
                "aspect_ratio": aspect_ratio,
                "framing_mode": framing_mode,
                "subtitle_style": subtitle_style,
                "gaming_preset": gaming_preset,
                "gaming_layout": gaming_layout,
                "gaming_custom_box": gaming_custom_box,
            }

            results.append(clip_record)
            if job_ctx is not None and hasattr(job_ctx, "completed_shorts"):
                job_ctx.completed_shorts.append(clip_record)
        except (JobCancelledException, JobTimeoutException) as e:
            log_job_message(f"[clip/local] Klip #{i} dihentikan karena pembatalan/timeout: {e}", job_ctx=job_ctx)
            if results:
                break
            raise
        except Exception as e:
            # Check if this exception was caused by cancellation or timeout
            if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                if getattr(job_ctx, "cancel_event", None) and job_ctx.cancel_event.is_set():
                    log_job_message(f"[clip/local] Klip #{i} dihentikan karena pembatalan/timeout: {e}", job_ctx=job_ctx)
                    if results:
                        break
                    job_ctx.check_cancellation_or_timeout()

            log_job_message(f"[clip/local] {i} failed: {e}", job_ctx=job_ctx)
            results.append({
                **h,
                "clip_url": None,
                "filename": f"short_{i:02d}.mp4",
                "clip_index": i,
                "error": str(e),
                "out_dir": out_dir,
            })

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        if not results:
            job_ctx.check_cancellation_or_timeout()
    return results
