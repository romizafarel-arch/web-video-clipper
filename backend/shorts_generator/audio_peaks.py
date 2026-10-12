"""Audio Peak & Energy Scanner for Screams and Laughter Detection.

Scans audio tracks via FFmpeg PCM extraction and RMS windowing to detect
sudden volume spikes (screams, jumpscares, bursts of chaotic laughter)
and boost viral highlight scoring.
"""
import math
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .job_manager import log_job_message


def scan_audio_energy(
    media_path: str,
    window_seconds: float = 0.5,
    sample_rate: int = 16000,
    job_ctx: Optional[Any] = None,
) -> List[Tuple[float, float]]:
    """Extract audio energy series [(timestamp_seconds, rms_db)] using fast FFmpeg PCM streaming."""
    if not media_path or not os.path.exists(media_path):
        return []

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", media_path,
        "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-f", "f32le", "pipe:1",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
        raw_bytes = proc.stdout
        if not raw_bytes:
            return []

        audio = np.frombuffer(raw_bytes, dtype=np.float32)
        if len(audio) == 0:
            return []

        win_size = max(128, int(sample_rate * window_seconds))
        n_windows = len(audio) // win_size
        if n_windows == 0:
            return []

        # Reshape to 2D matrix for vectorized RMS computation
        audio_truncated = audio[:n_windows * win_size].reshape((n_windows, win_size))
        rms_values = np.sqrt(np.mean(audio_truncated ** 2, axis=1))

        # Vectorized dB calculation with floor at -96 dB
        rms_clipped = np.maximum(rms_values, 1.58e-5)
        rms_db_arr = 20.0 * np.log10(rms_clipped)

        series: List[Tuple[float, float]] = []
        for idx, val_db in enumerate(rms_db_arr):
            ts = round(idx * window_seconds, 2)
            series.append((ts, round(float(val_db), 2)))

        return series
    except Exception as e:
        log_job_message(f"[audio_peaks] Warning: Could not scan audio energy ({e})", job_ctx=job_ctx)
        return []


def compute_baseline_db(energy_series: List[Tuple[float, float]]) -> float:
    """Compute baseline conversational dB level (median of active windows)."""
    if not energy_series:
        return -45.0

    # Filter out near-silence (below -70 dB)
    active_levels = [db for _, db in energy_series if db > -70.0]
    if not active_levels:
        return -50.0

    return float(np.median(active_levels))


def boost_highlights_with_audio_peaks(
    highlights: List[Dict[str, Any]],
    energy_series: List[Tuple[float, float]],
    max_boost: int = 20,
    job_ctx: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Score booster: evaluate audio energy peaks (screams / chaos laughter) for each highlight."""
    if not highlights or not energy_series:
        return highlights

    baseline_db = compute_baseline_db(energy_series)
    # Peak threshold: at least 6.0 dB above conversational baseline
    peak_threshold = baseline_db + 6.0

    boosted: List[Dict[str, Any]] = []
    for h in highlights:
        h_st = float(h.get("start_time", 0.0))
        h_et = float(h.get("end_time", 0.0))

        # Windows intersecting this highlight
        clip_windows = [db for ts, db in energy_series if h_st <= ts <= h_et]
        if not clip_windows:
            boosted.append(h)
            continue

        max_clip_db = max(clip_windows)
        spikes = [db for db in clip_windows if db >= peak_threshold]
        spike_count = len(spikes)

        boost = 0
        elevation = max_clip_db - baseline_db
        if spike_count > 0 or elevation >= 5.0:
            elevation_score = (max(0.0, elevation) / 15.0) * (max_boost * 0.7)
            frequency_score = min(spike_count, 6) * 1.5
            boost = int(round(min(float(max_boost), elevation_score + frequency_score)))

        orig_score = int(h.get("score", 0))
        new_score = min(100, orig_score + boost)

        updated_h = dict(h)
        updated_h["score"] = new_score
        updated_h["audio_peak_db"] = round(max_clip_db, 1)
        updated_h["peak_spikes"] = spike_count
        updated_h["audio_boost"] = boost

        if boost > 0:
            log_job_message(
                f"[audio_peaks] Highlight '{h.get('title')}' [{h_st:.1f}s..{h_et:.1f}s]: "
                f"Peak {max_clip_db:.1f}dB ({spike_count} spikes, baseline {baseline_db:.1f}dB) -> +{boost} pts (score: {orig_score}->{new_score})",
                job_ctx=job_ctx,
            )

        boosted.append(updated_h)

    # Re-sort descending by boosted score
    boosted.sort(key=lambda x: int(x.get("score", 0)), reverse=True)
    return boosted
