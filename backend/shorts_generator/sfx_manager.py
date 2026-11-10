"""Auto Sound Design & SFX Layering Engine for Viral Shorts.

Injects subtle, high-impact sound effects (whoosh, pop, ding) synchronized
with subtitle emphasis words and scene transitions via FFmpeg amix.
"""
import math
import os
import re
import subprocess
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .job_manager import log_job_message

SFX_DIR = Path(__file__).resolve().parent.parent / "assets" / "sfx"


def ensure_default_sfx() -> Dict[str, str]:
    """Ensure standard procedural SFX exist in backend/assets/sfx/."""
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    sr = 44100
    results = {}

    sfx_files = {
        "pop.wav": _generate_pop,
        "whoosh.wav": _generate_whoosh,
        "ding.wav": _generate_ding,
    }

    for fname, generator_fn in sfx_files.items():
        fpath = SFX_DIR / fname
        if not fpath.exists() or fpath.stat().st_size < 100:
            audio_arr = generator_fn(sr)
            _save_wav(str(fpath), audio_arr, sr)
        results[fname.replace(".wav", "")] = str(fpath.resolve())

    return results


def _save_wav(path: str, arr: np.ndarray, sample_rate: int = 44100) -> None:
    arr_clipped = np.clip(arr, -1.0, 1.0)
    int_data = (arr_clipped * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_data.tobytes())


def _generate_pop(sr: int) -> np.ndarray:
    """Punchy subtle UI pop / bubble click (70ms)."""
    dur = 0.07
    t = np.linspace(0, dur, int(sr * dur), False)
    freq = 850.0 * np.exp(-t * 35.0) + 120.0
    phase = 2.0 * np.pi * np.cumsum(freq) / sr
    env = np.exp(-t * 40.0)
    return (np.sin(phase) * env * 0.7).astype(np.float32)


def _generate_whoosh(sr: int) -> np.ndarray:
    """Smooth transitional noise whoosh (200ms)."""
    dur = 0.20
    t = np.linspace(0, dur, int(sr * dur), False)
    noise = np.random.uniform(-1.0, 1.0, len(t)).astype(np.float32)
    # Bell-shaped envelope peaking at t = 0.09s
    env = np.exp(-((t - 0.09) ** 2) / (2.0 * (0.045 ** 2)))
    # Frequency sweep 350Hz -> 1400Hz -> 400Hz
    sweep_phase = 2.0 * np.pi * (350.0 + 800.0 * np.sin(np.pi * t / dur)) * t
    sweep = np.sin(sweep_phase)
    signal = (0.65 * noise + 0.35 * sweep) * env * 0.45
    return signal.astype(np.float32)


def _generate_ding(sr: int) -> np.ndarray:
    """Crisp harmonic bell chime for stats/numbers (350ms)."""
    dur = 0.35
    t = np.linspace(0, dur, int(sr * dur), False)
    env = np.exp(-t * 11.0)
    f1, f2 = 1760.0, 3520.0
    signal = (0.75 * np.sin(2.0 * np.pi * f1 * t) + 0.25 * np.sin(2.0 * np.pi * f2 * t)) * env * 0.5
    return signal.astype(np.float32)


EMPHASIS_KEYWORDS = {
    "rahasia", "bahaya", "gila", "wow", "penting", "kunci", "fakta",
    "money", "secret", "never", "always", "stop", "biggest", "crazy",
    "hack", "trik", "tips", "rugi", "untung", "sukses", "gagal",
}


def detect_sfx_events(
    cues: List[Dict[str, Any]],
    min_gap: float = 2.8,
) -> List[Dict[str, Any]]:
    """Determine high-impact SFX moments from subtitle cues."""
    events: List[Dict[str, Any]] = []
    last_time = -10.0

    sfx_paths = ensure_default_sfx()

    for idx, cue in enumerate(cues):
        start_ts = float(cue.get("start", 0.0))
        text = str(cue.get("text", "")).strip()
        words = cue.get("words", [])

        if start_ts - last_time < min_gap:
            continue

        sfx_type = None

        # 1. Number, percentage, or currency -> Ding
        if re.search(r"\b\d+([.,]\d+)?\b|%|\$|rp|ribu|juta|miliar", text, re.IGNORECASE):
            sfx_type = "ding"

        # 2. Strong emphasis word or ALL CAPS exclamation -> Pop
        elif any(w.lower() in EMPHASIS_KEYWORDS for w in re.findall(r"\w+", text)) or "!" in text:
            sfx_type = "pop"

        # 3. First cue or major transition after gap -> Whoosh
        elif idx == 0 or (start_ts - last_time >= min_gap * 1.5):
            sfx_type = "whoosh"

        if sfx_type and sfx_type in sfx_paths:
            events.append({
                "timestamp": round(start_ts, 2),
                "type": sfx_type,
                "file": sfx_paths[sfx_type],
                "text": text[:25],
            })
            last_time = start_ts

    return events


def apply_sfx_to_video(
    in_video_path: str,
    out_video_path: str,
    sfx_events: List[Dict[str, Any]],
    sfx_volume: float = 0.35,
    job_ctx: Optional[Any] = None,
) -> str:
    """Mix SFX into video audio using FFmpeg adelay + amix without re-encoding video stream."""
    if not sfx_events or not os.path.exists(in_video_path):
        return in_video_path

    # Cap maximum SFX events per clip to avoid audio clutter (max 8)
    events = sfx_events[:8]

    log_job_message(
        f"[sfx] Layering {len(events)} sound effects onto audio timeline ({', '.join(e['type'] for e in events)})",
        job_ctx=job_ctx,
    )

    inputs = ["-i", in_video_path]
    for ev in events:
        inputs.extend(["-i", ev["file"]])

    # Build filter_complex with adelay and volume
    filter_parts = []
    mix_inputs = ["[0:a]"]

    for i, ev in enumerate(events, start=1):
        delay_ms = max(0, int(round(ev["timestamp"] * 1000)))
        pad_tag = f"sfx{i}"
        filter_parts.append(
            f"[{i}:a]volume={sfx_volume:.2f},adelay={delay_ms}|{delay_ms}[{pad_tag}]"
        )
        mix_inputs.append(f"[{pad_tag}]")

    num_inputs = len(mix_inputs)
    amix_str = f"{''.join(mix_inputs)}amix=inputs={num_inputs}:duration=first:dropout_transition=0[aout]"
    filter_parts.append(amix_str)

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_video_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        if os.path.exists(out_video_path) and os.path.getsize(out_video_path) > 1024:
            log_job_message("[sfx] Sound design successfully applied.", job_ctx=job_ctx)
            return out_video_path
        else:
            log_job_message("[sfx] Warning: SFX render returned 0 bytes, fallback to original audio.", job_ctx=job_ctx)
            return in_video_path
    except Exception as e:
        log_job_message(f"[sfx] Warning: Could not mix SFX ({e}), fallback to original audio.", job_ctx=job_ctx)
        return in_video_path
