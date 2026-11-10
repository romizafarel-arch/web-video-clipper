"""Fast Silence & Dead-Air Cutter using Native FFmpeg silencedetect.

Trims conversational dead air (>0.45s) to maximize video velocity
and boost viewer retention rate without cloud API costs.
"""
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .job_manager import log_job_message


def _probe_duration(media_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        media_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        val = float(proc.stdout.strip())
        return val if math.isfinite(val) and val > 0 else 0.0
    except Exception:
        return 0.0


def detect_silences(
    media_path: str,
    noise_thresh_db: float = -35.0,
    min_duration: float = 0.45,
    job_ctx: Optional[Any] = None,
) -> List[Tuple[float, float]]:
    """Detect silence intervals (start, end) in seconds using ffmpeg silencedetect."""
    if not os.path.exists(media_path):
        return []

    cmd = [
        "ffmpeg", "-y", "-loglevel", "info",
        "-i", media_path,
        "-af", f"silencedetect=noise={noise_thresh_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        output = proc.stderr or ""
    except Exception as e:
        log_job_message(f"[silence] Warning: silencedetect failed ({e})", job_ctx=job_ctx)
        return []

    silences: List[Tuple[float, float]] = []
    current_start: Optional[float] = None

    start_pattern = re.compile(r"silence_start:\s*([0-9.]+)")
    end_pattern = re.compile(r"silence_end:\s*([0-9.]+)")

    for line in output.splitlines():
        sm = start_pattern.search(line)
        if sm:
            try:
                current_start = float(sm.group(1))
            except ValueError:
                current_start = None
            continue

        em = end_pattern.search(line)
        if em and current_start is not None:
            try:
                end_val = float(em.group(1))
                if end_val > current_start:
                    silences.append((current_start, end_val))
            except ValueError:
                pass
            current_start = None

    return silences


def compute_speech_intervals(
    total_duration: float,
    silences: List[Tuple[float, float]],
    padding: float = 0.06,
) -> List[Tuple[float, float]]:
    """Invert silence intervals into active speech intervals with slight buffer padding."""
    if not silences or total_duration <= 0:
        return [(0.0, total_duration)] if total_duration > 0 else []

    intervals: List[Tuple[float, float]] = []
    cur_pos = 0.0

    for s_start, s_end in silences:
        # Buffer boundaries so word endings aren't clipped
        speech_end = min(total_duration, s_start + padding)
        if speech_end > cur_pos + 0.1:
            intervals.append((cur_pos, speech_end))
        cur_pos = max(cur_pos, s_end - padding)

    if cur_pos < total_duration - 0.1:
        intervals.append((cur_pos, total_duration))

    # Merge overlapping or close intervals (< 0.12s gap)
    if not intervals:
        return [(0.0, total_duration)]

    merged: List[Tuple[float, float]] = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 0.12:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def trim_silence_from_video(
    in_video_path: str,
    out_video_path: str,
    noise_thresh_db: float = -35.0,
    min_silence_duration: float = 0.45,
    min_total_saved: float = 0.6,
    job_ctx: Optional[Any] = None,
) -> Tuple[str, bool]:
    """Strip pauses > min_silence_duration from video.
    
    Returns (effective_path, was_trimmed).
    """
    total_dur = _probe_duration(in_video_path)
    if total_dur <= 2.0:
        return in_video_path, False

    silences = detect_silences(
        in_video_path,
        noise_thresh_db=noise_thresh_db,
        min_duration=min_silence_duration,
        job_ctx=job_ctx,
    )

    if not silences:
        log_job_message("[silence] Audio sudah padat, tidak ada jeda hening terdeteksi.", job_ctx=job_ctx)
        return in_video_path, False

    total_silence_time = sum(max(0.0, end - start) for start, end in silences)
    if total_silence_time < min_total_saved:
        log_job_message(
            f"[silence] Total jeda hening kecil ({total_silence_time:.2f}s < {min_total_saved}s), skip pemotongan untuk menjaga ritme alami.",
            job_ctx=job_ctx,
        )
        return in_video_path, False

    speech_intervals = compute_speech_intervals(total_dur, silences)
    if len(speech_intervals) <= 1:
        return in_video_path, False

    log_job_message(
        f"[silence] Memangkas {len(silences)} jeda hening (menghemat {total_silence_time:.2f}s dari total {total_dur:.2f}s)",
        job_ctx=job_ctx,
    )

    # Build FFmpeg trim + concat filter graph
    filter_parts = []
    v_labels = []
    a_labels = []

    for idx, (st, et) in enumerate(speech_intervals):
        v_tag = f"v{idx}"
        a_tag = f"a{idx}"
        filter_parts.append(
            f"[0:v]trim=start={st:.3f}:end={et:.3f},setpts=PTS-STARTPTS[{v_tag}]"
        )
        filter_parts.append(
            f"[0:a]atrim=start={st:.3f}:end={et:.3f},asetpts=PTS-STARTPTS[{a_tag}]"
        )
        v_labels.append(f"[{v_tag}]")
        a_labels.append(f"[{a_tag}]")

    num_segs = len(speech_intervals)
    concat_inputs = "".join(v_labels[i] + a_labels[i] for i in range(num_segs))
    filter_parts.append(f"{concat_inputs}concat=n={num_segs}:v=1:a=1[vcat][acat]")

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", in_video_path,
        "-filter_complex", filter_complex,
        "-map", "[vcat]",
        "-map", "[acat]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "19",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_video_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        if os.path.exists(out_video_path) and os.path.getsize(out_video_path) > 1024:
            new_dur = _probe_duration(out_video_path)
            log_job_message(
                f"[silence] Sukses memadatkan video: durasi {total_dur:.2f}s -> {new_dur:.2f}s.",
                job_ctx=job_ctx,
            )
            return out_video_path, True
        else:
            log_job_message("[silence] Warning: Hasil trim 0 bytes, fallback ke video awal.", job_ctx=job_ctx)
            return in_video_path, False
    except Exception as e:
        log_job_message(f"[silence] Warning: Gagal memotong silence ({e}), fallback ke video awal.", job_ctx=job_ctx)
        return in_video_path, False
