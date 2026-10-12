"""Audio transcription using Google Gemini Multimodal API.

Extracts a compressed audio track using ffmpeg, uploads it to Gemini File API,
and requests a timestamped transcription in JSON format with segment start and end times.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import config as cfg
from ..config import LOCAL_OUTPUT_DIR, require_gemini_key
from ..job_manager import JobCancelledException, JobTimeoutException, log_job_message


def _get_duration(media_path: str) -> float:
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
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def _get_audio_cache_path(media_path: str) -> Tuple[Path, str]:
    """Compute high-precision, collision-free cache path for extracted compressed audio."""
    cache_dir = Path(LOCAL_OUTPUT_DIR) / ".cache" / "audio"
    cache_dir.mkdir(parents=True, exist_ok=True)

    resolved_path = str(Path(media_path).resolve())
    stat_res = Path(media_path).stat() if Path(media_path).exists() else None
    file_size = stat_res.st_size if stat_res else 0
    mtime_ns = getattr(stat_res, "st_mtime_ns", int(stat_res.st_mtime * 1e9)) if stat_res else 0
    extraction_params = "codec=libmp3lame|ar=16000|ac=1|b=64k"

    key_components = [
        resolved_path,
        str(file_size),
        str(mtime_ns),
        extraction_params,
    ]
    cache_key = hashlib.sha256("|".join(key_components).encode("utf-8")).hexdigest()[:16]
    stem = Path(media_path).stem[:32]
    audio_path = cache_dir / f"audio_{stem}_{cache_key}.mp3"
    return audio_path, cache_key


def _verify_audio_integrity(
    audio_path: str,
    expected_duration: Optional[float] = None,
    job_ctx: Optional[Any] = None,
) -> bool:
    """Verify that an audio file exists, has content, and decodes cleanly without payload truncation."""
    p = Path(audio_path)
    if not p.exists() or p.stat().st_size <= 128:
        return False
    header_dur = _get_duration(audio_path)
    if header_dur <= 0:
        return False

    target = expected_duration if (expected_duration and expected_duration > 0) else header_dur
    if target <= 0:
        return False

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        try:
            job_ctx.check_cancellation_or_timeout()
        except Exception:
            return False

    # Establish deadline: at least 10s or 2x target duration
    deadline_duration = max(10.0, float(target) * 2.0)
    deadline = time.time() + deadline_duration
    if job_ctx is not None and getattr(job_ctx, "started_at", None) and getattr(job_ctx, "timeout_seconds", None):
        job_remaining = (job_ctx.started_at + job_ctx.timeout_seconds) - time.time()
        if job_remaining > 0:
            deadline = min(deadline, time.time() + job_remaining)
        else:
            return False

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-v", "error",
        "-i", audio_path,
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-f", "s16le",
        "pipe:1",
    ]

    proc = None
    stop_watchdog = threading.Event()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if job_ctx is not None and hasattr(job_ctx, "register_subprocess"):
            job_ctx.register_subprocess(proc)

        def _watchdog_monitor():
            while not stop_watchdog.wait(timeout=0.05):
                should_abort = False
                if time.time() > deadline:
                    should_abort = True
                elif job_ctx is not None:
                    cancel_evt = getattr(job_ctx, "cancel_event", None)
                    if cancel_evt and cancel_evt.is_set():
                        should_abort = True
                    elif getattr(job_ctx, "started_at", None) and getattr(job_ctx, "timeout_seconds", None):
                        if (time.time() - job_ctx.started_at) > job_ctx.timeout_seconds:
                            should_abort = True
                if should_abort:
                    try:
                        if proc.poll() is None:
                            proc.terminate()
                            try:
                                proc.wait(timeout=0.2)
                            except Exception:
                                proc.kill()
                    except Exception:
                        pass
                    break

        watchdog_thread = threading.Thread(target=_watchdog_monitor, daemon=True)
        watchdog_thread.start()

        total_bytes = 0
        max_bytes = int((target + 300.0) * 16000 * 2)

        while True:
            if time.time() > deadline:
                return False
            if job_ctx is not None:
                cancel_evt = getattr(job_ctx, "cancel_event", None)
                if cancel_evt and cancel_evt.is_set():
                    return False
                if getattr(job_ctx, "started_at", None) and getattr(job_ctx, "timeout_seconds", None):
                    if (time.time() - job_ctx.started_at) > job_ctx.timeout_seconds:
                        return False

            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                return False

        try:
            ret = proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            return False

        if ret != 0:
            return False

        if time.time() > deadline:
            return False
        if job_ctx is not None and getattr(job_ctx, "cancel_event", None) and job_ctx.cancel_event.is_set():
            return False

        decoded_duration = total_bytes / (16000 * 2)
        if decoded_duration <= 0:
            return False
        target = expected_duration if (expected_duration and expected_duration > 0) else header_dur
        if abs(decoded_duration - target) > max(0.5, 0.05 * target):
            return False
        return True
    except Exception:
        return False
    finally:
        stop_watchdog.set()
        if proc is not None:
            if job_ctx is not None and hasattr(job_ctx, "unregister_subprocess"):
                try:
                    job_ctx.unregister_subprocess(proc)
                except Exception:
                    pass
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=0.5)
                    except Exception:
                        proc.kill()
                        proc.wait(timeout=0.5)
            except Exception:
                pass


def _extract_audio_compressed(media_path: str, job_ctx: Optional[Any] = None) -> Path:
    """Extract 16kHz mono MP3 audio to optimize upload size and speed with atomic publication."""
    audio_path, cache_key = _get_audio_cache_path(media_path)
    cache_dir = audio_path.parent
    stem = Path(media_path).stem[:32]

    # If audio already extracted, verify it is uncorrupted, un-truncated, and reusable
    if audio_path.exists():
        is_valid = False
        try:
            is_valid = _verify_audio_integrity(str(audio_path), job_ctx=job_ctx)
        except Exception:
            is_valid = False

        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            job_ctx.check_cancellation_or_timeout()

        if is_valid:
            log_job_message(f"[transcribe/gemini] reusing cached compressed audio: {audio_path.name}", job_ctx=job_ctx)
            return audio_path
        else:
            log_job_message(f"[transcribe/gemini] corrupted or truncated audio cache invalidated: {audio_path.name}", job_ctx=job_ctx)
            audio_path.unlink(missing_ok=True)

    tmp_id = uuid.uuid4().hex[:8]
    tmp_audio_path = cache_dir / f".tmp_audio_{stem}_{cache_key}_{tmp_id}.mp3"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", media_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        str(tmp_audio_path),
    ]
    log_job_message(f"[transcribe/gemini] extracting compressed audio: {audio_path.name}...", job_ctx=job_ctx)
    from .clipper import _run_ffmpeg_cmd
    try:
        _run_ffmpeg_cmd(cmd, job_ctx=job_ctx)

        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            job_ctx.check_cancellation_or_timeout()

        if not tmp_audio_path.exists():
            raise RuntimeError("Ekstraksi audio gagal atau menghasilkan berkas audio yang rusak.")

        verified = _verify_audio_integrity(str(tmp_audio_path), job_ctx=job_ctx)

        # Setelah verifier kembali, jalankan job_ctx.check_cancellation_or_timeout() sebelum error media generik dan sebelum publikasi cache
        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            job_ctx.check_cancellation_or_timeout()

        if not verified:
            raise RuntimeError("Ekstraksi audio gagal atau menghasilkan berkas audio yang rusak.")

        os.replace(str(tmp_audio_path), str(audio_path))
        return audio_path
    finally:
        if tmp_audio_path.exists():
            try:
                tmp_audio_path.unlink(missing_ok=True)
            except OSError:
                pass


def _parse_offset(val: Any, field_name: str, word_idx: int, word_text: str) -> float:
    """Parse and strictly validate a word offset (start_offset or end_offset).

    Differentiates missing values (None, empty string) from valid 0.0 offsets.
    Validates numeric, finite, non-negative values.
    Raises ValueError with precise diagnostic context upon violation.
    """
    if val is None:
        raise ValueError(
            f"[transcribe/gemini] Word {word_idx} ({word_text!r}) missing {field_name}: "
            f"raw value is None (offset missing from model output)."
        )
    if isinstance(val, bool):
        raise ValueError(
            f"[transcribe/gemini] Word {word_idx} ({word_text!r}) invalid {field_name}: "
            f"boolean type not allowed for numeric offset."
        )
    elif isinstance(val, (int, float)):
        num = float(val)
    elif isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            raise ValueError(
                f"[transcribe/gemini] Word {word_idx} ({word_text!r}) invalid {field_name}: "
                f"raw value is empty string."
            )
        if val_str.endswith("s"):
            val_str = val_str[:-1].strip()
        try:
            num = float(val_str)
        except ValueError:
            raise ValueError(
                f"[transcribe/gemini] Word {word_idx} ({word_text!r}) invalid {field_name}: "
                f"cannot parse raw value {val!r} as float."
            )
    else:
        raise ValueError(
            f"[transcribe/gemini] Word {word_idx} ({word_text!r}) invalid {field_name}: "
            f"unexpected type {type(val).__name__} for raw value {val!r}."
        )

    if not math.isfinite(num):
        raise ValueError(
            f"[transcribe/gemini] Word {word_idx} ({word_text!r}) invalid {field_name}: "
            f"value is non-finite ({num})."
        )
    if num < 0.0:
        raise ValueError(
            f"[transcribe/gemini] Word {word_idx} ({word_text!r}) invalid {field_name}: "
            f"value is negative ({num})."
        )
    return num


MAX_LOCAL_WINDOW_SECONDS = 5.0
MAX_LOCAL_WORDS = 6
MAX_PLAUSIBLE_SPEECH_RATE = 5.0
RESET_TIME_THRESHOLD = 5.0
MAX_TOLERABLE_GAP_FRACTION = 0.25
MAX_RAW_DEVIATION_FROM_WINDOW = 5.0
MAX_PLAUSIBLE_WORD_DURATION = 10.5
MAX_PLAUSIBLE_SPEAKER_OVERLAP = 5.0
SANITIZER_POLICY_VERSION = "gemini_recovery_v2_conservative"


def _calculate_union_span_duration(spans: List[Dict]) -> float:
    """Calculate the total duration of untrusted spans using union coverage (merging overlaps, no negative spans)."""
    if not spans:
        return 0.0
    intervals = []
    for s in spans:
        st = float(s.get("start", 0.0))
        et = float(s.get("end", 0.0))
        if et > st and math.isfinite(st) and math.isfinite(et):
            intervals.append((st, et))
    if not intervals:
        return 0.0
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for cur_st, cur_et in intervals[1:]:
        prev_st, prev_et = merged[-1]
        if cur_st <= prev_et:
            merged[-1] = (prev_st, max(prev_et, cur_et))
        else:
            merged.append((cur_st, cur_et))
    return sum(et - st for st, et in merged)


def _sanitize_and_recover_word_timestamps(
    words_list: List[Any],
    source_duration: Optional[float] = None,
    job_ctx: Optional[Any] = None,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Sanitize and conservatively recover word-level timestamps before segment formation.

    Enforces:
    1. Strict offset parsing via _parse_offset (rejects None, bool, empty, NaN, Inf, negative).
    2. Exact duplicate payload deduplication when consecutive words share word, speaker, and valid offsets.
    3. Detection of intrinsic defects: inverted ranges, out-of-bounds, corrupt tokens, suspicious durations,
       and neighbor-context end spikes.
    4. Detection of temporal reset blocks (backward jumps > RESET_TIME_THRESHOLD).
    5. Local bounded recovery: linear interpolation ONLY when 2 trusted word anchors exist, window <= 5s,
       count <= 6, plausible speech rate, and raw timestamps do not deviate beyond local window.
    6. Untrusted gap identification: records ambiguous blocks that cannot be safely recovered.
       Rejects overlapping anchors with explicit quality error.
    7. Overall quality check: evaluates union duration of untrusted spans against tolerance.

    Returns:
        (processed_words, untrusted_spans, audit_log)
    """
    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    if not words_list:
        return [], [], []

    source_dur = source_duration if (source_duration and source_duration > 0) else float("inf")

    # Pass 1: Parse offsets strictly on a fresh copy
    raw_parsed: List[Dict] = []
    for idx, w in enumerate(words_list):
        word_text = getattr(w, "word", "") if not isinstance(w, dict) else w.get("word", "")
        if not isinstance(word_text, str):
            word_text = str(word_text or "")

        start_raw = getattr(w, "start_offset", None) if not isinstance(w, dict) else w.get("start_offset")
        end_raw = getattr(w, "end_offset", None) if not isinstance(w, dict) else w.get("end_offset")
        speaker = getattr(w, "speaker", "") or getattr(w, "speaker_label", "") if not isinstance(w, dict) else (w.get("speaker") or w.get("speaker_label", ""))

        start_t = _parse_offset(start_raw, "start_offset", idx, word_text)
        end_t = _parse_offset(end_raw, "end_offset", idx, word_text)

        raw_parsed.append({
            "index": idx,
            "word": word_text,
            "raw_start": start_t,
            "raw_end": end_t,
            "start": start_t,
            "end": end_t,
            "speaker": str(speaker or ""),
            "estimated": False,
            "untrusted": False,
        })

    audit_log: List[Dict] = []

    # Pass 2: Deduplicate exact duplicate payload items with identical valid offsets and speaker
    deduped_words: List[Dict] = []
    for w in raw_parsed:
        if deduped_words:
            prev = deduped_words[-1]
            is_exact_dup = (
                w["word"] == prev["word"]
                and w["raw_start"] == prev["raw_start"]
                and w["raw_end"] == prev["raw_end"]
                and w["raw_end"] >= w["raw_start"]
                and w["speaker"] == prev["speaker"]
            )
            if is_exact_dup:
                audit_log.append({
                    "index": w["index"],
                    "word": w["word"],
                    "action": "exact_duplicate_payload_dropped",
                    "raw": [w["raw_start"], w["raw_end"]],
                    "reason": f"exact_duplicate_of_index_{prev['index']}_with_valid_range",
                })
                continue
        deduped_words.append(w)

    n = len(deduped_words)
    defective_flags = [False] * n
    defective_tags: List[Set[str]] = [set() for _ in range(n)]

    # Pass 3: Detect intrinsic defects, suspicious durations, and neighbor-context end spikes
    for i, w in enumerate(deduped_words):
        if w["raw_end"] < w["raw_start"]:
            defective_flags[i] = True
            defective_tags[i].add("inverted")
        if w["raw_start"] > source_dur or w["raw_end"] > source_dur:
            defective_flags[i] = True
            defective_tags[i].add("out_of_bounds")
        if "/?" in w["word"] or ("?" in w["word"] and len(w["word"]) <= 2 and not w["word"][0].isalnum()):
            defective_flags[i] = True
            defective_tags[i].add("corrupt_token")
        dur = w["raw_end"] - w["raw_start"]
        if dur > MAX_PLAUSIBLE_WORD_DURATION:
            defective_flags[i] = True
            defective_tags[i].add("suspicious_duration")
        if i < n - 1:
            next_w = deduped_words[i + 1]
            next_anchor_ref = max(next_w["raw_start"], next_w["raw_end"])
            if w["raw_end"] > next_anchor_ref + MAX_PLAUSIBLE_SPEAKER_OVERLAP:
                defective_flags[i] = True
                defective_tags[i].add("end_spike")

    # Pass 4: Detect temporal resets (backward jumps exceeding threshold)
    watermark = 0.0
    for i in range(n):
        if defective_flags[i]:
            continue
        w = deduped_words[i]
        if w["raw_start"] < watermark - RESET_TIME_THRESHOLD:
            defective_flags[i] = True
            defective_tags[i].add("temporal_reset")
        else:
            watermark = max(watermark, w["raw_start"])

    # Pass 5: Resolve sandwiched defects
    i = 0
    while i < n - 2:
        if defective_flags[i] and not defective_flags[i + 1] and defective_flags[i + 2]:
            defective_flags[i + 1] = True
            defective_tags[i + 1].add("sandwiched_in_anomaly_group")
        elif defective_flags[i] and not defective_flags[i + 1] and not defective_flags[i + 2] and i < n - 3 and defective_flags[i + 3]:
            if deduped_words[i + 2]["raw_start"] > deduped_words[i + 3]["raw_start"] or deduped_words[i + 1]["raw_end"] > deduped_words[i + 2]["raw_start"]:
                defective_flags[i + 1] = True
                defective_flags[i + 2] = True
                defective_flags[i + 3] = True
                defective_tags[i + 1].add("sandwiched_in_anomaly_group")
                defective_tags[i + 2].add("sandwiched_in_anomaly_group")
                defective_tags[i + 3].add("sandwiched_in_anomaly_group")
        i += 1

    # Pass 6: Group contiguous defectives into blocks
    blocks: List[List[int]] = []
    curr_block: List[int] = []
    for i in range(n):
        if defective_flags[i]:
            curr_block.append(i)
        else:
            if curr_block:
                blocks.append(curr_block)
                curr_block = []
    if curr_block:
        blocks.append(curr_block)

    untrusted_spans: List[Dict] = []

    # Pass 7: Recovery or Untrusted Gap Assignment per block
    for block_indices in blocks:
        start_idx = block_indices[0]
        end_idx = block_indices[-1]
        count = len(block_indices)

        left_anchor = None
        for k in range(start_idx - 1, -1, -1):
            if not defective_flags[k]:
                left_anchor = deduped_words[k]
                break

        right_anchor = None
        for k in range(end_idx + 1, n):
            if not defective_flags[k]:
                right_anchor = deduped_words[k]
                break

        eligible_local = False
        rejection_reasons: List[str] = []

        # V3-T01: Interpolation strictly requires two trusted word anchors
        if left_anchor is None:
            rejection_reasons.append("missing_left_anchor")
        if right_anchor is None:
            rejection_reasons.append("missing_right_anchor")

        if left_anchor and right_anchor:
            left_time = left_anchor["end"]
            right_time = right_anchor["start"]
            window_dur = right_time - left_time

            if window_dur < 0:
                rejection_reasons.append(f"negative_window({window_dur:.2f}s_anchors_overlap)")
            elif window_dur > MAX_LOCAL_WINDOW_SECONDS:
                rejection_reasons.append(f"window_too_large({window_dur:.2f}s > {MAX_LOCAL_WINDOW_SECONDS}s)")
        else:
            left_time = left_anchor["end"] if left_anchor else 0.0
            right_time = right_anchor["start"] if right_anchor else source_dur
            window_dur = right_time - left_time

        if count > MAX_LOCAL_WORDS:
            rejection_reasons.append(f"too_many_words({count} > {MAX_LOCAL_WORDS})")

        # V3-T01 & V3-T02: Inspect defect tags across all words in block
        block_tags = set().union(*(defective_tags[idx_b] for idx_b in block_indices))
        if "corrupt_token" in block_tags:
            rejection_reasons.append("has_corrupt_tokens")
        if "out_of_bounds" in block_tags:
            rejection_reasons.append("out_of_bounds_in_block")
        if "temporal_reset" in block_tags:
            rejection_reasons.append("temporal_reset_in_block")
        if "suspicious_duration" in block_tags or "end_spike" in block_tags:
            rejection_reasons.append("end_spike_or_suspicious_duration")

        # V3-T01: Check raw deviation from local window (forward and backward)
        for idx_b in block_indices:
            w_b = deduped_words[idx_b]
            rst = w_b["raw_start"]
            ret = w_b["raw_end"]
            if (
                rst < left_time - MAX_RAW_DEVIATION_FROM_WINDOW
                or ret < left_time - MAX_RAW_DEVIATION_FROM_WINDOW
                or rst > right_time + MAX_RAW_DEVIATION_FROM_WINDOW
                or ret > right_time + MAX_RAW_DEVIATION_FROM_WINDOW
            ):
                rejection_reasons.append(
                    f"raw_deviation_exceeds_window(raw=[{rst},{ret}],window=[{left_time:.1f},{right_time:.1f}])"
                )
                break

        if not rejection_reasons:
            speech_rate = count / max(window_dur, 0.1)
            if speech_rate > MAX_PLAUSIBLE_SPEECH_RATE:
                rejection_reasons.append(f"speech_rate_implausible({speech_rate:.1f} w/s > {MAX_PLAUSIBLE_SPEECH_RATE})")
            else:
                eligible_local = True

        if eligible_local:
            dt = window_dur / count
            for step, idx_b in enumerate(block_indices):
                w = deduped_words[idx_b]
                new_st = round(left_time + step * dt, 3)
                new_et = round(left_time + (step + 1) * dt, 3)
                audit_log.append({
                    "index": w["index"],
                    "word": w["word"],
                    "action": "local_bounded_recovery",
                    "raw": [w["raw_start"], w["raw_end"]],
                    "corrected": [new_st, new_et],
                    "reason": f"interpolated_in_window({left_time:.2f}s..{right_time:.2f}s)",
                })
                w["start"] = new_st
                w["end"] = new_et
                w["estimated"] = True
                defective_flags[idx_b] = False
        else:
            # V3-T04: Determine quarantine interval safely
            if left_anchor is not None and right_anchor is not None:
                if left_anchor["end"] > right_anchor["start"]:
                    # Overlapping anchors around defective block: cannot determine boundaries safely
                    raise ValueError(
                        f"[transcribe/gemini] Transcript quality error: conflicting overlapping anchors around defective block "
                        f"[{start_idx}..{end_idx}] (left_anchor end {left_anchor['end']}s > right_anchor start {right_anchor['start']}s). "
                        "Cannot safely determine quarantine boundaries."
                    )
                span_start = round(left_anchor["end"], 2)
                span_end = round(right_anchor["start"], 2)
            elif left_anchor is None and right_anchor is not None:
                span_start = 0.0
                span_end = round(right_anchor["start"], 2)
            elif left_anchor is not None and right_anchor is None:
                span_start = round(left_anchor["end"], 2)
                span_end = round(source_dur, 2)
            else:
                span_start = 0.0
                span_end = round(source_dur, 2)

            if span_end < span_start:
                raise ValueError(
                    f"[transcribe/gemini] Transcript quality error: invalid quarantine interval [{span_start}, {span_end}] "
                    f"for defective block [{start_idx}..{end_idx}]."
                )

            raw_text = " ".join(deduped_words[idx_b]["word"] for idx_b in block_indices)
            span_record = {
                "start": span_start,
                "end": span_end,
                "start_index": deduped_words[start_idx]["index"],
                "end_index": deduped_words[end_idx]["index"],
                "word_count": count,
                "raw_text": raw_text[:200] + ("..." if len(raw_text) > 200 else ""),
                "reasons": rejection_reasons,
            }
            untrusted_spans.append(span_record)
            for idx_b in block_indices:
                w = deduped_words[idx_b]
                w["untrusted"] = True
                audit_log.append({
                    "index": w["index"],
                    "word": w["word"],
                    "action": "marked_untrusted_gap",
                    "raw": [w["raw_start"], w["raw_end"]],
                    "reason": "; ".join(rejection_reasons),
                })

    # Pass 8: Quality check on total untrusted duration using union coverage (V3-T04)
    total_gap_dur = _calculate_union_span_duration(untrusted_spans)
    if source_duration and source_duration > 0:
        gap_fraction = total_gap_dur / source_duration
        if gap_fraction > MAX_TOLERABLE_GAP_FRACTION:
            raise ValueError(
                f"[transcribe/gemini] Transcript quality error: untrusted spans cover {total_gap_dur:.1f}s "
                f"({gap_fraction * 100:.1f}% of media duration), exceeding tolerance ({MAX_TOLERABLE_GAP_FRACTION * 100:.0f}%)."
            )

    return deduped_words, untrusted_spans, audit_log


def _words_to_segments(
    words_list: List[Any],
    untrusted_spans: Optional[List[Dict]] = None,
    source_duration: Optional[float] = None,
) -> List[Dict]:
    """Convert a list of WordInfo objects or sanitized word dicts into valid transcript segments.

    Enforces:
    - Non-null, finite, non-negative start and end offsets via _parse_offset.
    - end_offset >= start_offset for every word.
    - Untrusted gap protection: any untrusted gap forces an immediate segment flush and boundaries
      are strictly separated without silent concatenation across gaps.
    - Clean handling of multi-speaker overlapping dialogue: if a word's start timestamp
      jumps backwards relative to current segment start, or follows a speech pause (>1.2s),
      the preceding words are cleanly flushed into a completed segment before starting the new turn.
    - Segment boundaries cover the full interval of valid words within it:
      start = min(w['start']), end = max(w['end']).
    - At the end, segments are sorted chronologically by start time to guarantee monotonic order.
    - No silent word dropping or fictitious durations.
    """
    segs: List[Dict] = []
    if not words_list:
        return segs

    parsed_words: List[Dict] = []
    for idx, w in enumerate(words_list):
        if isinstance(w, dict) and "start" in w and "end" in w:
            word_text = str(w.get("word") or "")
            start_t = float(w["start"])
            end_t = float(w["end"])
            untrusted = bool(w.get("untrusted", False))
            estimated = bool(w.get("estimated", False))
        else:
            word_text = getattr(w, "word", "") if not isinstance(w, dict) else w.get("word", "")
            if not isinstance(word_text, str):
                word_text = str(word_text or "")

            start_raw = getattr(w, "start_offset", None) if not isinstance(w, dict) else w.get("start_offset")
            end_raw = getattr(w, "end_offset", None) if not isinstance(w, dict) else w.get("end_offset")

            start_t = _parse_offset(start_raw, "start_offset", idx, word_text)
            end_t = _parse_offset(end_raw, "end_offset", idx, word_text)
            untrusted = False
            estimated = False

        if not untrusted and end_t < start_t:
            raise ValueError(
                f"[transcribe/gemini] Word {idx} ({word_text!r}) has inverted time range: "
                f"end_offset ({end_t}) < start_offset ({start_t})."
            )

        parsed_words.append({
            "word": word_text,
            "start": start_t,
            "end": end_t,
            "untrusted": untrusted,
            "estimated": estimated,
        })

    curr_seg_words: List[Dict] = []

    def _emit_segment(words_chunk: List[Dict]):
        if not words_chunk:
            return
        seg_start = min(cw["start"] for cw in words_chunk)
        seg_end = max(cw["end"] for cw in words_chunk)
        text = " ".join(cw["word"] for cw in words_chunk).strip()
        if not text:
            return
        segs.append({
            "start": round(seg_start, 2),
            "end": round(seg_end, 2),
            "text": text,
            "words": [
                {
                    "word": cw["word"],
                    "start": round(cw["start"], 3),
                    "end": round(cw["end"], 3),
                }
                for cw in words_chunk
            ],
        })

    for pw in parsed_words:
        if pw.get("untrusted"):
            # Boundary of an untrusted gap: flush previous words immediately
            if curr_seg_words:
                _emit_segment(curr_seg_words)
                curr_seg_words = []
            continue

        if curr_seg_words:
            seg_start = min(cw["start"] for cw in curr_seg_words)
            last_word_end = curr_seg_words[-1]["end"]
            pause_gap = (pw["start"] - last_word_end) > 1.2 if (pw["start"] >= last_word_end) else False
            backward_jump = pw["start"] < seg_start

            if backward_jump or pause_gap:
                _emit_segment(curr_seg_words)
                curr_seg_words = []

        curr_seg_words.append(pw)

        word_text = pw["word"]
        is_sentence_end = any(word_text.endswith(p) for p in (".", "?", "!", "\n"))
        seg_span = max(cw["end"] for cw in curr_seg_words) - min(cw["start"] for cw in curr_seg_words)

        if (is_sentence_end and len(curr_seg_words) >= 3) or len(curr_seg_words) >= 12 or seg_span >= 6.0:
            _emit_segment(curr_seg_words)
            curr_seg_words = []

    if curr_seg_words:
        _emit_segment(curr_seg_words)

    segs.sort(key=lambda s: s["start"])

    # Strict contract validation on final segments
    max_allowed = source_duration if (source_duration and source_duration > 0) else float("inf")
    for idx, s in enumerate(segs):
        st = s["start"]
        et = s["end"]
        if st < 0 or et < st or et > max_allowed + 0.5:
            raise ValueError(f"[transcribe/gemini] Segment {idx} violates time bounds: [{st}, {et}], max={max_allowed}")
        for g in (untrusted_spans or []):
            if st < g["end"] - 0.05 and et > g["start"] + 0.05:
                raise ValueError(
                    f"[transcribe/gemini] Segment {idx} [{st}, {et}] illegally crosses untrusted span [{g['start']}, {g['end']}]"
                )

    return segs


def _save_prevalidation_diagnostic(
    media_path: str,
    model_name: str,
    language: Optional[str],
    raw_words: List[Any],
    segments: List[Dict],
    job_ctx: Optional[Any] = None,
    error: Optional[str] = None,
    untrusted_spans: Optional[List[Dict]] = None,
    recovery_audit: Optional[List[Dict]] = None,
) -> Optional[Path]:
    """Save raw WordInfo and pre-validation transcript segments as a separate diagnostic artifact.

    Contains: job_id, session_folder, model, language, source path and hash,
    raw words payload, pre-validation segments, untrusted_spans, recovery_audit,
    and error status (if any).
    NEVER saves credentials.
    """
    try:
        session_folder = getattr(job_ctx, "session_folder", None)
        job_id = getattr(job_ctx, "job_id", None) or "unknown_job"

        target_dir = Path(LOCAL_OUTPUT_DIR)
        if session_folder:
            target_dir = target_dir / session_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        diag_file = target_dir / f"diagnostic_transcript_pre_validation_{job_id}.json"

        source_hash = None
        if media_path and os.path.exists(media_path):
            try:
                h = hashlib.sha256()
                with open(media_path, "rb") as f:
                    while chunk := f.read(65536):
                        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                            job_ctx.check_cancellation_or_timeout()
                        h.update(chunk)
                source_hash = h.hexdigest()
            except (JobCancelledException, JobTimeoutException):
                raise
            except Exception:
                pass

        serialized_words = []
        for w in (raw_words or []):
            if isinstance(w, dict):
                serialized_words.append({
                    "word": str(w.get("word", "")),
                    "start_offset": str(w.get("start_offset", "")),
                    "end_offset": str(w.get("end_offset", "")),
                    "speaker": str(w.get("speaker", "") or w.get("speaker_label", "")),
                })
            else:
                serialized_words.append({
                    "word": str(getattr(w, "word", "")),
                    "start_offset": str(getattr(w, "start_offset", "")),
                    "end_offset": str(getattr(w, "end_offset", "")),
                    "speaker": str(getattr(w, "speaker", "") or getattr(w, "speaker_label", "")),
                })

        diag_data = {
            "artifact_type": "diagnostic_transcript_pre_validation",
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S+07:00", time.localtime()),
            "job_id": job_id,
            "session_folder": session_folder,
            "model": model_name,
            "language": language or "auto",
            "source_path": str(Path(media_path).resolve()) if media_path else None,
            "source_sha256": source_hash,
            "raw_words_count": len(serialized_words),
            "raw_words": serialized_words,
            "segments_count": len(segments or []),
            "segments": segments or [],
            "status": "error" if error else "pre_validation_ready",
            "validation_error": error,
        }
        if untrusted_spans is not None:
            diag_data["untrusted_spans"] = untrusted_spans
        if recovery_audit is not None:
            diag_data["recovery_audit"] = recovery_audit

        diag_file.write_text(json.dumps(diag_data, indent=2, ensure_ascii=False), encoding="utf-8")
        log_job_message(f"[transcribe/gemini] saved pre-validation diagnostic artifact: {diag_file.name}", job_ctx=job_ctx)
        return diag_file
    except (JobCancelledException, JobTimeoutException):
        raise
    except Exception as e:
        log_job_message(f"[transcribe/gemini] warning: failed to save pre-validation diagnostic: {e}", job_ctx=job_ctx)
        return None


def _transcribe_chunks_gemini(
    client: Any,
    audio_file_path: Path,
    total_duration: float,
    model_name: str,
    language: Optional[str] = None,
    job_ctx: Optional[Any] = None,
    chunk_seconds: float = 1500.0,
) -> List[Dict]:
    """Transcribe long audio in bounded chunks to avoid Gemini model input token limits."""
    from google.genai import types
    from .clipper import _run_ffmpeg_cmd

    num_chunks = int(math.ceil(total_duration / chunk_seconds))
    log_job_message(
        f"[transcribe/gemini] audio duration {total_duration:.0f}s ({total_duration/3600:.1f}h) exceeds single-pass limit. "
        f"Processing in {num_chunks} chunks of ~{chunk_seconds/60:.0f}m...",
        job_ctx=job_ctx,
    )
    all_words: List[Dict] = []

    for chunk_idx in range(num_chunks):
        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            job_ctx.check_cancellation_or_timeout()

        c_start = chunk_idx * chunk_seconds
        c_dur = min(chunk_seconds, total_duration - c_start)
        if c_dur <= 0.1:
            continue

        tmp_id = uuid.uuid4().hex[:8]
        tmp_chunk = audio_file_path.parent / f".tmp_chunk_{chunk_idx}_{tmp_id}.mp3"
        slice_cmd = [
            "ffmpeg", "-y",
            "-ss", f"{c_start:.3f}",
            "-t", f"{c_dur:.3f}",
            "-i", str(audio_file_path),
            "-acodec", "copy",
            str(tmp_chunk),
        ]
        _run_ffmpeg_cmd(slice_cmd, job_ctx=job_ctx)

        if not tmp_chunk.exists() or tmp_chunk.stat().st_size == 0:
            log_job_message(f"[transcribe/gemini] warning: empty chunk slice at {c_start:.0f}s, skipping", job_ctx=job_ctx)
            continue

        up_chunk = None
        try:
            log_job_message(
                f"[transcribe/gemini] transcribing chunk {chunk_idx + 1}/{num_chunks} "
                f"({c_start/60:.1f}m - {(c_start + c_dur)/60:.1f}m)...",
                job_ctx=job_ctx,
            )
            up_chunk = client.files.upload(file=str(tmp_chunk))

            p_start = time.time()
            while getattr(up_chunk, "state", None) and str(up_chunk.state).upper() == "PROCESSING":
                if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                    job_ctx.check_cancellation_or_timeout()
                if time.time() - p_start > 180.0:
                    raise TimeoutError(f"Gemini chunk {chunk_idx + 1} processing timed out after 180s.")
                time.sleep(1.0)
                up_chunk = client.files.get(name=up_chunk.name)

            transcribe_config_args = {"word_timestamp": True}
            if language:
                transcribe_config_args["language_codes"] = [language]

            resp = None
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                        job_ctx.check_cancellation_or_timeout()
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=[up_chunk],
                        config=types.GenerateContentConfig(
                            audio_transcription_config=types.AudioTranscriptionConfig(
                                **transcribe_config_args
                            )
                        ),
                    )
                    break
                except Exception as req_err:
                    if attempt == max_retries - 1:
                        raise
                    err_str = str(req_err)
                    delay = 5.0 * (attempt + 1)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                        m = re.search(r"retry in ([\d\.]+)s", err_str, re.IGNORECASE)
                        if not m:
                            m = re.search(r"'retryDelay':\s*'(\d+)s'", err_str)
                        if m:
                            try:
                                delay = float(m.group(1)) + 2.0
                            except ValueError:
                                delay = 62.0
                        else:
                            delay = 62.0
                    log_job_message(
                        f"[transcribe/gemini] chunk {chunk_idx + 1} quota/rate-limit (attempt {attempt + 1}/{max_retries}): "
                        f"waiting {delay:.1f}s before retry...",
                        job_ctx=job_ctx,
                    )
                    sleep_start = time.time()
                    while time.time() - sleep_start < delay:
                        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                            job_ctx.check_cancellation_or_timeout()
                        time.sleep(1.0)

            cands = getattr(resp, "candidates", []) or []
            if cands:
                p_cand = cands[0]
                c_content = getattr(p_cand, "content", None)
                parts = getattr(c_content, "parts", []) or []
                chunk_words_count = 0
                for part in parts:
                    trans = getattr(part, "audio_transcription", None)
                    if trans:
                        for pw in getattr(trans, "words", []) or []:
                            w_text = str(getattr(pw, "word", "") or "")
                            s_raw = getattr(pw, "start_offset", None)
                            e_raw = getattr(pw, "end_offset", None)
                            st = _parse_offset(s_raw, "start_offset", len(all_words), w_text)
                            et = _parse_offset(e_raw, "end_offset", len(all_words), w_text)
                            spk = getattr(pw, "speaker", "") or getattr(pw, "speaker_label", "")
                            all_words.append({
                                "word": w_text,
                                "start_offset": f"{st + c_start:.3f}s",
                                "end_offset": f"{et + c_start:.3f}s",
                                "speaker": str(spk or ""),
                            })
                            chunk_words_count += 1
                log_job_message(f"[transcribe/gemini] chunk {chunk_idx + 1}/{num_chunks} complete ({chunk_words_count} words).", job_ctx=job_ctx)
        finally:
            if up_chunk is not None:
                try:
                    client.files.delete(name=up_chunk.name)
                except Exception:
                    pass
            if tmp_chunk.exists():
                try:
                    tmp_chunk.unlink(missing_ok=True)
                except OSError:
                    pass

    return all_words


def transcribe_with_gemini(
    media_path: str,
    language: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    job_ctx: Optional[Any] = None,
) -> Dict:
    """Transcribe audio using Google Gemini API.

    Returns dict shape:
        {"duration": float, "segments": [{"start": float, "end": float, "text": str}]}
    """
    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise RuntimeError(
            "google-genai is required for Gemini transcription. Install with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    gemini_key = api_key or require_gemini_key()
    client = genai.Client(api_key=gemini_key)

    total_duration = _get_duration(media_path)
    audio_file_path = _extract_audio_compressed(media_path, job_ctx=job_ctx)

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    model_name = (model or getattr(cfg, "GEMINI_TRANSCRIBER_MODEL", None) or "gemini-3.5-transcribe").strip()
    if model_name.startswith("models/"):
        model_name = model_name[7:]

    uploaded_file = None
    use_chunking = (total_duration > 1800.0) and ("transcribe" in model_name.lower())

    if not use_chunking:
        log_job_message(f"[transcribe/gemini] uploading audio ({audio_file_path.stat().st_size / (1024 * 1024):.2f} MB)...", job_ctx=job_ctx)
        uploaded_file = client.files.upload(file=str(audio_file_path))
        log_job_message(f"[transcribe/gemini] uploaded file id: {uploaded_file.name}", job_ctx=job_ctx)

    try:
        if uploaded_file is not None:
            # Check file state if processing is required with finite timeout and cancellation checkpoints
            poll_start = time.time()
            max_poll_seconds = 180.0
            while getattr(uploaded_file, "state", None) and str(uploaded_file.state).upper() == "PROCESSING":
                if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                    job_ctx.check_cancellation_or_timeout()
                if time.time() - poll_start > max_poll_seconds:
                    raise TimeoutError("Gemini file processing timed out after 180s.")
                time.sleep(1.0)
                uploaded_file = client.files.get(name=uploaded_file.name)

        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            job_ctx.check_cancellation_or_timeout()

        log_job_message(f"[transcribe/gemini] transcribing with model {model_name}...", job_ctx=job_ctx)

        segments: List[Dict] = []
        full_text = ""
        words: List[Any] = []

        # Path A: Specialized Gemini Speech-to-Text model (gemini-3.5-transcribe)
        if "transcribe" in model_name.lower():
            try:
                if use_chunking:
                    words = _transcribe_chunks_gemini(
                        client=client,
                        audio_file_path=audio_file_path,
                        total_duration=total_duration,
                        model_name=model_name,
                        language=language,
                        job_ctx=job_ctx,
                    )
                else:
                    transcribe_config_args = {"word_timestamp": True}
                    if language:
                        transcribe_config_args["language_codes"] = [language]

                    response = client.models.generate_content(
                        model=model_name,
                        contents=[uploaded_file],
                        config=types.GenerateContentConfig(
                            audio_transcription_config=types.AudioTranscriptionConfig(
                                **transcribe_config_args
                            )
                        ),
                    )

                    candidates = getattr(response, "candidates", []) or []
                    if not candidates:
                        raise ValueError(f"[transcribe/gemini] model {model_name} returned 0 candidates")

                    if len(candidates) > 1:
                        log_job_message(
                            f"[transcribe/gemini] note: response contains {len(candidates)} alternative candidates; "
                            "transcribing primary candidate (index 0) only.",
                            job_ctx=job_ctx,
                        )

                    primary_candidate = candidates[0]
                    content = getattr(primary_candidate, "content", None)
                    parts = getattr(content, "parts", []) or []

                    for part in parts:
                        trans = getattr(part, "audio_transcription", None)
                        if trans:
                            part_words = getattr(trans, "words", []) or []
                            words.extend(part_words)

                if words:
                    untrusted_spans = []
                    recovery_audit = []
                    try:
                        sanitized_words, untrusted_spans, recovery_audit = _sanitize_and_recover_word_timestamps(
                            words_list=words,
                            source_duration=total_duration if total_duration > 0 else None,
                        )
                        segments = _words_to_segments(
                            sanitized_words,
                            untrusted_spans=untrusted_spans,
                            source_duration=total_duration if total_duration > 0 else None,
                        )
                    except (JobCancelledException, JobTimeoutException):
                        raise
                    except Exception as parse_err:
                        _save_prevalidation_diagnostic(
                            media_path=media_path,
                            model_name=model_name,
                            language=language,
                            raw_words=words,
                            segments=[],
                            job_ctx=job_ctx,
                            error=str(parse_err),
                            untrusted_spans=untrusted_spans,
                            recovery_audit=recovery_audit,
                        )
                        raise

                    full_text = " ".join([str(w.get("word", "") if isinstance(w, dict) else getattr(w, "word", "")) for w in words])
                    n_rec = sum(1 for a in recovery_audit if a.get("action") == "local_bounded_recovery")
                    log_job_message(
                        f"[transcribe/gemini] extracted {len(segments)} segments ({len(words)} words) with {model_name} "
                        f"(recovered: {n_rec}, untrusted spans: {len(untrusted_spans)})",
                        job_ctx=job_ctx,
                    )
                    _save_prevalidation_diagnostic(
                        media_path=media_path,
                        model_name=model_name,
                        language=language,
                        raw_words=words,
                        segments=segments,
                        job_ctx=job_ctx,
                        untrusted_spans=untrusted_spans,
                        recovery_audit=recovery_audit,
                    )
            except (JobCancelledException, JobTimeoutException):
                raise
            except Exception as e:
                log_job_message(f"[transcribe/gemini] {model_name} failed ({e}), falling back to gemini-3.5-flash...", job_ctx=job_ctx)

        # Path B: Multimodal Gemini LLM prompt (supports user-selected multimodal model)
        if not segments:
            if uploaded_file is None:
                log_job_message(f"[transcribe/gemini] uploading audio ({audio_file_path.stat().st_size / (1024 * 1024):.2f} MB)...", job_ctx=job_ctx)
                uploaded_file = client.files.upload(file=str(audio_file_path))
                poll_start = time.time()
                max_poll_seconds = 180.0
                while getattr(uploaded_file, "state", None) and str(uploaded_file.state).upper() == "PROCESSING":
                    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                        job_ctx.check_cancellation_or_timeout()
                    if time.time() - poll_start > max_poll_seconds:
                        raise TimeoutError("Gemini file processing timed out after 180s.")
                    time.sleep(1.0)
                    uploaded_file = client.files.get(name=uploaded_file.name)

            # If user specified a non-transcribe model (e.g. gemini-2.5-flash), respect their choice
            if model_name and "transcribe" not in model_name.lower():
                target_mm_model = model_name
            else:
                target_mm_model = (getattr(cfg, "GEMINI_MODEL", None) or "gemini-3.5-flash").strip()

            if target_mm_model.startswith("models/"):
                target_mm_model = target_mm_model[7:]
            log_job_message(f"[transcribe/gemini] querying {target_mm_model} with structured JSON prompt...", job_ctx=job_ctx)
            lang_instruction = f" The audio language is {language}." if language else ""
            prompt = (
                "You are a precise speech-to-text audio transcriber."
                f"{lang_instruction}\n"
                "Transcribe the entire audio file from beginning to end with accurate timestamps in seconds.\n"
                "Break the transcription into natural sentence or phrase segments (each between 2 to 10 seconds).\n"
                "Return ONLY a JSON array of segment objects adhering strictly to this schema:\n"
                "[\n"
                "  {\n"
                "    \"start\": 0.0,\n"
                "    \"end\": 4.2,\n"
                "    \"text\": \"Spoken sentence here\"\n"
                "  }\n"
                "]\n"
                "Important requirements:\n"
                "- 'start' and 'end' must be numbers (seconds as float).\n"
                "- 'text' must be the exact transcribed words.\n"
                "- Do not omit any spoken parts.\n"
                "- Return strictly valid JSON."
            )

            response = client.models.generate_content(
                model=target_mm_model,
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            response_text = (response.text or "").strip()
            if not response_text:
                raise RuntimeError("Gemini returned empty response for transcription.")

            # Clean markdown wrappers if any
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            data = json.loads(response_text)
            if isinstance(data, dict):
                for key in ("segments", "transcription", "result", "items"):
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break

            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    t = str(item.get("text", "")).strip()
                    if not t:
                        continue
                    try:
                        s_val = float(item.get("start", 0.0))
                        e_val = float(item.get("end", s_val + 1.0))
                    except (ValueError, TypeError):
                        continue
                    segments.append({
                        "start": max(0.0, s_val),
                        "end": max(s_val, e_val),
                        "text": t,
                    })

        if not segments:
            raise RuntimeError("Gemini produced no valid transcription segments.")

        # Save diagnostic if segments came from Path B (words list empty)
        if not words and segments:
            _save_prevalidation_diagnostic(
                media_path=media_path,
                model_name=target_mm_model if 'target_mm_model' in locals() else model_name,
                language=language,
                raw_words=[],
                segments=segments,
                job_ctx=job_ctx,
            )

        # Sort segments chronologically
        segments.sort(key=lambda s: s["start"])

        computed_duration = total_duration if total_duration > 0 else (segments[-1]["end"] if segments else 0.0)

        log_job_message(f"[transcribe/gemini] transcription complete: {len(segments)} segments, ~{computed_duration:.1f}s", job_ctx=job_ctx)
        return {
            "duration": computed_duration,
            "segments": segments,
            "untrusted_spans": untrusted_spans if 'untrusted_spans' in locals() else [],
            "recovery_audit": recovery_audit if 'recovery_audit' in locals() else [],
            "policy_version": SANITIZER_POLICY_VERSION if ('recovery_audit' in locals() and recovery_audit) else None,
        }

    finally:
        # Delete the uploaded file from Gemini File API to keep storage clean
        if uploaded_file is not None:
            try:
                log_job_message(f"[transcribe/gemini] cleaning up uploaded file: {uploaded_file.name}", job_ctx=job_ctx)
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
