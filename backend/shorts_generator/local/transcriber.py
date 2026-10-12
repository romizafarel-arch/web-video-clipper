"""Local transcription via faster-whisper.

Reads a local media file and returns the same shape the highlight generator
expects: {duration, segments[start, end, text]}.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .. import config as cfg
from ..config import LOCAL_OUTPUT_DIR
from ..job_manager import log_job_message


def _probe_duration(media_path: str) -> float:
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


def _transcript_cache_paths(
    media_path: str,
    provider: str,
    model: str,
    language: Optional[str] = None,
) -> Tuple[Path, Path]:
    """Return (json_path, srt_path) uniquely identifying media source + transcribe settings."""
    cache_dir = Path(LOCAL_OUTPUT_DIR) / ".cache" / "transcripts"
    cache_dir.mkdir(parents=True, exist_ok=True)

    abs_path = str(Path(media_path).resolve())
    stat_res = Path(media_path).stat() if Path(media_path).exists() else None
    file_size = stat_res.st_size if stat_res else 0
    file_mtime_ns = getattr(stat_res, "st_mtime_ns", int(stat_res.st_mtime * 1e9)) if stat_res else 0

    key_components = [
        abs_path,
        str(file_size),
        str(file_mtime_ns),
        (provider or "gemini").strip().lower(),
        (model or "default").strip().lower(),
        (language or "auto").strip().lower(),
    ]
    cache_key = hashlib.sha256("|".join(key_components).encode("utf-8")).hexdigest()[:16]
    stem = Path(media_path).stem[:32]
    json_path = cache_dir / f"transcript_{stem}_{cache_key}.json"
    srt_path = cache_dir / f"transcript_{stem}_{cache_key}.srt"
    return json_path, srt_path


def _transcript_cache_path(media_path: str) -> Path:
    """Legacy helper: return the simple .srt cache path for backward compatibility."""
    cache_dir = Path(LOCAL_OUTPUT_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / (Path(media_path).stem + ".srt")


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _parse_srt_timestamp(value: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value!r}")
    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + (millis / 1000.0)


DURATION_TOLERANCE_SECONDS = 0.5


def _validate_transcript_contract_detailed(data: Any, max_duration: Optional[float] = None) -> Tuple[bool, Optional[str]]:
    """Validate that transcript adheres to the required semantic schema.

    - duration must be a finite float/int > 0
    - segments must be a non-empty list of dicts
    - each segment must have:
      - start: finite float/int >= 0, and <= duration + DURATION_TOLERANCE_SECONDS
      - end: finite float/int >= start, and <= duration + DURATION_TOLERANCE_SECONDS
      - text: str (non-null)
    - untrusted_spans (if present):
      - each span must have finite start and end, 0 <= start <= end <= duration + DURATION_TOLERANCE_SECONDS
      - no segment may cross any untrusted span
    """
    if not isinstance(data, dict):
        return False, f"Expected transcript to be a dict, got {type(data).__name__}"
    duration = data.get("duration")
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        return False, f"duration must be a finite positive number, got {duration!r}"
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return False, "segments must be a non-empty list"

    dur_limit = max_duration if (max_duration is not None and max_duration > 0) else duration
    max_allowed = dur_limit + DURATION_TOLERANCE_SECONDS

    for idx, s in enumerate(segments):
        if not isinstance(s, dict):
            return False, f"segment {idx} must be a dict, got {type(s).__name__}"
        start = s.get("start")
        end = s.get("end")
        text = s.get("text")
        if not isinstance(start, (int, float)) or not math.isfinite(start) or start < 0:
            return False, f"segment {idx} has invalid start: {start!r} (must be finite float >= 0)"
        if not isinstance(end, (int, float)) or not math.isfinite(end) or end < start:
            return False, f"segment {idx} has invalid end: {end!r} (must be finite float >= start {start!r})"
        if start > max_allowed:
            return False, f"segment {idx} start ({start}) exceeds media duration limit ({dur_limit:.2f}s + {DURATION_TOLERANCE_SECONDS}s)"
        if end > max_allowed:
            return False, f"segment {idx} end ({end}) exceeds media duration limit ({dur_limit:.2f}s + {DURATION_TOLERANCE_SECONDS}s)"
        if not isinstance(text, str):
            return False, f"segment {idx} has invalid text: expected str, got {type(text).__name__}"

    untrusted_spans = data.get("untrusted_spans")
    if untrusted_spans is not None:
        if not isinstance(untrusted_spans, list):
            return False, f"untrusted_spans must be a list, got {type(untrusted_spans).__name__}"
        for g_idx, g in enumerate(untrusted_spans):
            if not isinstance(g, dict):
                return False, f"untrusted_spans[{g_idx}] must be a dict"
            g_st = g.get("start")
            g_et = g.get("end")
            if not isinstance(g_st, (int, float)) or not math.isfinite(g_st) or g_st < 0:
                return False, f"untrusted_spans[{g_idx}] invalid start: {g_st!r}"
            if not isinstance(g_et, (int, float)) or not math.isfinite(g_et) or g_et < g_st:
                return False, f"untrusted_spans[{g_idx}] invalid end: {g_et!r}"
            if g_st > max_allowed:
                return False, f"untrusted_spans[{g_idx}] start ({g_st}) exceeds media duration limit ({dur_limit:.2f}s + {DURATION_TOLERANCE_SECONDS}s)"
            if g_et > max_allowed:
                return False, f"untrusted_spans[{g_idx}] end ({g_et}) exceeds media duration limit ({dur_limit:.2f}s + {DURATION_TOLERANCE_SECONDS}s)"
            for s_idx, s in enumerate(segments):
                s_st = s["start"]
                s_et = s["end"]
                if s_st < g_et - 0.05 and s_et > g_st + 0.05:
                    return False, f"segment {s_idx} [{s_st}, {s_et}] illegally crosses untrusted span [{g_st}, {g_et}]"

    return True, None


def _validate_transcript_contract(data: Any, max_duration: Optional[float] = None) -> bool:
    """Validate that transcript adheres to the required semantic schema."""
    return _validate_transcript_contract_detailed(data, max_duration=max_duration)[0]


def _write_transcript_cache(
    media_path: str,
    transcript: Dict,
    provider: str,
    model: str,
    language: Optional[str] = None,
) -> Tuple[Path, Path]:
    """Save transcript cache as JSON metadata and compatible .srt file with atomic staging."""
    is_valid, err_reason = _validate_transcript_contract_detailed(transcript)
    if not is_valid:
        raise ValueError(f"Invalid transcript contract: cannot cache semantically invalid transcript ({err_reason}).")

    json_path, srt_path = _transcript_cache_paths(media_path, provider, model, language)

    stat_res = Path(media_path).stat() if Path(media_path).exists() else None
    file_size = stat_res.st_size if stat_res else 0
    file_mtime_ns = getattr(stat_res, "st_mtime_ns", int(stat_res.st_mtime * 1e9)) if stat_res else 0
    file_mtime = stat_res.st_mtime if stat_res else 0.0

    probed_dur = _probe_duration(media_path)
    source_dur = probed_dur if probed_dur > 0 else float(transcript.get("duration", 0.0))

    meta = {
        "source_path": str(Path(media_path).resolve()),
        "source_size": file_size,
        "source_mtime_ns": file_mtime_ns,
        "source_mtime": file_mtime,
        "provider": (provider or "").strip().lower(),
        "model": (model or "").strip(),
        "language": (language or "auto").strip().lower(),
        "duration": source_dur,
        "segments": transcript.get("segments", []),
    }
    if "untrusted_spans" in transcript:
        meta["untrusted_spans"] = transcript["untrusted_spans"]
    if "recovery_audit" in transcript:
        meta["recovery_audit"] = transcript["recovery_audit"]
    if "policy_version" in transcript:
        meta["policy_version"] = transcript["policy_version"]

    # V3-T03: Re-validate final meta with source_dur upper bound BEFORE publishing
    is_meta_valid, meta_err = _validate_transcript_contract_detailed(meta, max_duration=source_dur)
    if not is_meta_valid:
        raise ValueError(f"Invalid final transcript metadata: cannot cache transcript exceeding duration ({meta_err}).")

    # Write accompanying .srt lines
    lines = []
    for idx, segment in enumerate(transcript.get("segments", []), start=1):
        start = _format_srt_timestamp(float(segment["start"]))
        end = _format_srt_timestamp(float(segment["end"]))
        text = str(segment.get("text", "")).strip().replace("\r", "").replace("\n", " ")
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")

    tmp_id = uuid.uuid4().hex[:8]
    tmp_json = json_path.with_name(f".tmp_{json_path.name}_{tmp_id}")
    tmp_srt = srt_path.with_name(f".tmp_{srt_path.name}_{tmp_id}")

    try:
        tmp_json.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_srt.write_text("\n".join(lines), encoding="utf-8")
        os.replace(str(tmp_json), str(json_path))
        os.replace(str(tmp_srt), str(srt_path))
    finally:
        if tmp_json.exists():
            try:
                tmp_json.unlink(missing_ok=True)
            except OSError:
                pass
        if tmp_srt.exists():
            try:
                tmp_srt.unlink(missing_ok=True)
            except OSError:
                pass

    return json_path, srt_path


def _load_transcript_cache(
    media_path: str,
    provider: str,
    model: str,
    language: Optional[str] = None,
) -> Optional[Dict]:
    """Load cached transcript if parameters and source file match, invalidating corrupted caches."""
    json_path, srt_path = _transcript_cache_paths(media_path, provider, model, language)
    if not json_path.exists():
        return None
    try:
        content = json_path.read_text(encoding="utf-8")
        if not content.strip():
            json_path.unlink(missing_ok=True)
            srt_path.unlink(missing_ok=True)
            return None
        data = json.loads(content)
        if not isinstance(data, dict):
            json_path.unlink(missing_ok=True)
            srt_path.unlink(missing_ok=True)
            return None

        if os.path.exists(media_path):
            stat_res = Path(media_path).stat()
            curr_size = stat_res.st_size
            curr_mtime_ns = getattr(stat_res, "st_mtime_ns", int(stat_res.st_mtime * 1e9))
            cached_ns = data.get("source_mtime_ns")
            if data.get("source_size") != curr_size or (cached_ns is not None and cached_ns != curr_mtime_ns):
                log_job_message(f"[transcribe/local] source file modified, invalidating cache: {json_path.name}")
                json_path.unlink(missing_ok=True)
                srt_path.unlink(missing_ok=True)
                return None

        # V3-T03: Enforce duration upper-bound on load
        probed_dur = _probe_duration(media_path) if (media_path and os.path.exists(media_path)) else 0.0
        eff_dur = probed_dur if probed_dur > 0 else float(data.get("duration", 0.0))
        is_contract_valid, err_reason = _validate_transcript_contract_detailed(data, max_duration=eff_dur if eff_dur > 0 else None)
        if not is_contract_valid:
            log_job_message(f"[transcribe/local] semantically invalid transcript cache invalidated: {json_path.name} ({err_reason})")
            json_path.unlink(missing_ok=True)
            srt_path.unlink(missing_ok=True)
            return None

        loaded = {"duration": float(data["duration"]), "segments": data["segments"]}
        if "untrusted_spans" in data:
            loaded["untrusted_spans"] = data["untrusted_spans"]
        if "recovery_audit" in data:
            loaded["recovery_audit"] = data["recovery_audit"]
        if "policy_version" in data:
            loaded["policy_version"] = data["policy_version"]
        return loaded
    except Exception as e:
        log_job_message(f"[transcribe/local] corrupt cache invalidated: {json_path.name} ({e})")
        try:
            json_path.unlink(missing_ok=True)
            srt_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None



def _write_srt_cache(media_path: str, transcript: Dict) -> Path:
    """Legacy helper writing root .srt file."""
    cache_path = _transcript_cache_path(media_path)
    lines = []
    for idx, segment in enumerate(transcript.get("segments", []), start=1):
        start = _format_srt_timestamp(float(segment["start"]))
        end = _format_srt_timestamp(float(segment["end"]))
        text = str(segment.get("text", "")).strip().replace("\r", "").replace("\n", " ")
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")

    cache_path.write_text("\n".join(lines), encoding="utf-8")
    return cache_path


def _load_srt_cache(cache_path: Path) -> Dict:
    content = cache_path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return {"duration": 0.0, "segments": []}

    segments = []
    for block in re.split(r"\n\s*\n", content):
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if "-->" not in lines[0] and len(lines) > 1 and "-->" in lines[1]:
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_raw, end_raw = [part.strip() for part in lines[0].split("-->", 1)]
        text = "\n".join(lines[1:]).strip()
        segments.append(
            {
                "start": _parse_srt_timestamp(start_raw),
                "end": _parse_srt_timestamp(end_raw),
                "text": text,
            }
        )

    duration = segments[-1]["end"] if segments else 0.0
    return {"duration": duration, "segments": segments}


def _resolve_device() -> str:
    device_pref = getattr(cfg, "LOCAL_WHISPER_DEVICE", "auto")
    if device_pref != "auto":
        return device_pref
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            # Test that CUDA actually works (catches missing cuBLAS/cuDNN libs)
            torch.zeros(1, device="cuda")
            return "cuda"
    except (ImportError, OSError, RuntimeError):
        pass
    return "cpu"


def transcribe_local(
    media_path: str,
    language: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    config: Optional[Dict] = None,
    force_refresh: bool = False,
    job_ctx: Optional[Any] = None,
) -> Dict:
    """Run transcription (Gemini or faster-whisper) on a local file, caching precisely by source + settings."""
    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    cfg_dict = config or {}
    effective_provider = (
        provider
        or cfg_dict.get("transcriber_provider")
        or getattr(cfg, "TRANSCRIBER_PROVIDER", "gemini")
    ).strip().lower()

    if effective_provider == "gemini":
        effective_model = (
            model
            or cfg_dict.get("gemini_transcriber_model")
            or getattr(cfg, "GEMINI_TRANSCRIBER_MODEL", "gemini-3.5-transcribe")
        ).strip()
    else:
        effective_model = (
            model
            or cfg_dict.get("whisper_model")
            or getattr(cfg, "LOCAL_WHISPER_MODEL", "base")
        ).strip()

    probed_dur = _probe_duration(media_path)

    if not force_refresh:
        cached = _load_transcript_cache(media_path, effective_provider, effective_model, language)
        if cached:
            if probed_dur > 0 and cached.get("duration", 0) <= 0:
                cached["duration"] = probed_dur
            log_job_message(
                f"[transcribe/local] reusing cached transcript ({effective_provider}/{effective_model}): "
                f"{len(cached['segments'])} segments, {cached['duration']:.0f}s of audio",
                job_ctx=job_ctx,
            )
            return cached

    if effective_provider == "gemini":
        from .gemini_transcriber import transcribe_with_gemini
        log_job_message(f"[transcribe/local] using Gemini API for transcription (model={effective_model})", job_ctx=job_ctx)
        gemini_key = cfg_dict.get("gemini_api_key")
        transcript = transcribe_with_gemini(media_path, language=language, model=effective_model, api_key=gemini_key, job_ctx=job_ctx)
        if probed_dur > 0:
            transcript["duration"] = probed_dur
        _write_transcript_cache(media_path, transcript, effective_provider, effective_model, language)
        # Also write legacy srt for backward compatibility
        _write_srt_cache(media_path, transcript)
        return transcript

    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper is required for --mode local when TRANSCRIBER_PROVIDER=whisper. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    device = _resolve_device()
    compute_type = "float16" if device == "cuda" else "int8"
    whisper_model_name = effective_model
    log_job_message(f"[transcribe/local] faster-whisper model={whisper_model_name} device={device}", job_ctx=job_ctx)

    from ..config import LOCAL_WHISPER_VAD_FILTER, LOCAL_WHISPER_VAD_PARAMETERS

    model_obj = WhisperModel(whisper_model_name, device=device, compute_type=compute_type)

    transcribe_kwargs = {
        "audio": media_path,
        "language": language,
        "beam_size": 5,
        "condition_on_previous_text": False,
        "word_timestamps": True,
    }
    if LOCAL_WHISPER_VAD_FILTER:
        transcribe_kwargs["vad_filter"] = True
        transcribe_kwargs["vad_parameters"] = LOCAL_WHISPER_VAD_PARAMETERS
    else:
        transcribe_kwargs["vad_filter"] = False

    segments_iter, info = model_obj.transcribe(**transcribe_kwargs)

    segments = []
    max_limit = probed_dur if probed_dur > 0 else None
    for s in segments_iter:
        if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
            job_ctx.check_cancellation_or_timeout()
        try:
            start_f = float(s.start)
            end_f = float(s.end)
        except (ValueError, TypeError):
            continue
        if not (math.isfinite(start_f) and math.isfinite(end_f)):
            continue
        if start_f < 0.0:
            start_f = 0.0
        if end_f <= start_f:
            continue
        if max_limit is not None:
            if start_f >= max_limit:
                continue
            if end_f > max_limit:
                end_f = max_limit
        text_str = (s.text or "").strip()
        if not text_str:
            continue

        seg_dict = {
            "start": round(start_f, 3),
            "end": round(end_f, 3),
            "text": text_str,
        }
        if hasattr(s, "words") and s.words:
            seg_dict["words"] = [
                {
                    "word": (w.word or "").strip(),
                    "start": round(float(w.start), 3),
                    "end": round(float(w.end), 3),
                }
                for w in s.words
                if getattr(w, "word", None) and math.isfinite(getattr(w, "start", 0)) and math.isfinite(getattr(w, "end", 0))
            ]
        segments.append(seg_dict)

    duration = probed_dur if probed_dur > 0 else (float(getattr(info, "duration", 0.0)) or (segments[-1]["end"] if segments else 0.0))
    log_job_message(f"[transcribe/local] {len(segments)} segments, {duration:.0f}s of audio", job_ctx=job_ctx)
    transcript = {"duration": duration, "segments": segments}
    _write_transcript_cache(media_path, transcript, effective_provider, effective_model, language)
    _write_srt_cache(media_path, transcript)
    return transcript
