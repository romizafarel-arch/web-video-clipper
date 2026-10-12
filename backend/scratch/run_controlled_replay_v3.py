"""Controlled Replay/Resume Runner for Video 3 — Long-Form Content (40–45 min).

Authorizes:
- EXACTLY ONE controlled replay session using stored STT response from fixture.
- Transcribe: 0 inferences (strictly blocked by guard).
- File API Upload: 0 uploads (strictly blocked by guard).
- Highlight: Maximum 4 APMix inferences (1 content classification + 3 chunk rankings).
- Fail-fast: max_retries = 0, MAX_HIGHLIGHT_API_ATTEMPTS = 1, no automatic retries or second runs.
- Rejection of highlight candidates crossing untrusted spans AND estimated recovery ranges.
- Full decode checks (-xerror) and physical duration verification on resulting clips.
- 100% preservation of 65 files in V1/V2, .env, source V3, and raw fixture.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set

# Force UTF-8 stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ==============================================================================
# 1. ENFORCE OUTPUT AND CACHE ISOLATION BEFORE IMPORTING APPLICATION MODULES
# ==============================================================================
VAL_OUTPUT_DIR = "output_val_v3"
os.environ["LOCAL_OUTPUT_DIR"] = VAL_OUTPUT_DIR

ROOT_DIR = Path(__file__).resolve().parent.parent
os.chdir(ROOT_DIR)
sys.path.insert(0, str(ROOT_DIR))

PLANNING_RESERVE_SECONDS = 60.0
WIB = timezone(timedelta(hours=7))

def get_iso_now() -> str:
    return datetime.now(WIB).isoformat()

# ==============================================================================
# 2. PER-JOB INFERENCE COUNTERS AND GUARDS (REPLAY POLICY: 0 STT, MAX 4 HL)
# ==============================================================================
api_counters = {
    "transcribe": {
        "attempted": 0,
        "dispatched": 0,
        "success": 0,
        "failed": 0,
        "blocked": 0,
        "max": 0,  # STRICTLY 0 FOR CONTROLLED REPLAY
    },
    "highlight": {
        "attempted": 0,
        "dispatched": 0,
        "success": 0,
        "failed": 0,
        "blocked": 0,
        "max": 4,  # MAX 4 FOR 3-CHUNK LONG VIDEO
    },
    "file_api": {
        "upload": 0,
        "polling": 0,
        "delete": 0,
        "delete_success": 0,
        "delete_failed": 0,
    },
}

def _get_active_job_context():
    try:
        from shorts_generator.job_manager import job_manager
        return job_manager.get_active_job()
    except Exception:
        return None

def _check_cancel_and_deadline(reserve_seconds: float = 0.0) -> None:
    from shorts_generator.job_manager import JobStatus, JobTimeoutException, JobCancelledException
    active_ctx = _get_active_job_context()
    if not active_ctx:
        return
    if active_ctx.cancel_event.is_set():
        if getattr(active_ctx, "is_timeout", False) or (active_ctx.cancel_reason and "Batas waktu" in active_ctx.cancel_reason):
            raise JobTimeoutException(active_ctx.cancel_reason or "Batas waktu pengerjaan terlampaui.")
        raise JobCancelledException(active_ctx.cancel_reason or "Pekerjaan dibatalkan oleh pengguna.")
    if active_ctx.started_at:
        elapsed = time.time() - active_ctx.started_at
        remaining = active_ctx.timeout_seconds - elapsed
        if remaining <= reserve_seconds:
            with active_ctx._lock:
                active_ctx.is_timeout = True
                active_ctx.status = JobStatus.CANCELING
                active_ctx.stage = "canceling"
                active_ctx.cancel_reason = f"Batas waktu job terlampaui (sisa {remaining:.1f}s <= cadangan {reserve_seconds:.1f}s)."
                active_ctx.cancel_event.set()
                active_ctx.terminate_all_subprocesses()
            raise JobTimeoutException(active_ctx.cancel_reason)

REQUEST_CAP_SECONDS = 600.0
DEFAULT_JOB_TIMEOUT_SECONDS = 1800.0

def _get_request_budget_sec(
    cap_seconds: float = REQUEST_CAP_SECONDS,
    reserve_seconds: float = PLANNING_RESERVE_SECONDS,
) -> float:
    active_ctx = _get_active_job_context()
    if not active_ctx or not active_ctx.started_at:
        return cap_seconds
    elapsed = time.time() - active_ctx.started_at
    remaining = active_ctx.timeout_seconds - elapsed
    effective_remaining = remaining - reserve_seconds
    if effective_remaining <= 0.0:
        return 0.0
    return min(cap_seconds, effective_remaining)

# 2.1 OpenAI SDK max_retries = 0 and Highlight Guard
import openai
from openai.resources.chat.completions import Completions

_orig_openai_init = openai.OpenAI.__init__
def _patched_openai_init(self, *args, **kwargs):
    kwargs["max_retries"] = 0
    _orig_openai_init(self, *args, **kwargs)
openai.OpenAI.__init__ = _patched_openai_init

_orig_chat_create = Completions.create
def _guarded_chat_create(self, *args, **kwargs):
    from shorts_generator.job_manager import JobCancelledException, JobTimeoutException
    _check_cancel_and_deadline(reserve_seconds=PLANNING_RESERVE_SECONDS)

    budget_sec = _get_request_budget_sec(cap_seconds=REQUEST_CAP_SECONDS, reserve_seconds=PLANNING_RESERVE_SECONDS)
    if budget_sec <= 0.0:
        active_ctx = _get_active_job_context()
        if active_ctx:
            with active_ctx._lock:
                active_ctx.is_timeout = True
                active_ctx.cancel_reason = "Batas waktu job 1.800s terlampaui atau tidak tersisa budget aman untuk dispatch request highlight."
                active_ctx.cancel_event.set()
        raise JobTimeoutException("Batas waktu job 1.800s terlampaui atau tidak tersisa budget aman untuk dispatch request highlight.")

    existing_timeout = kwargs.get("timeout")
    if existing_timeout is None:
        kwargs["timeout"] = float(budget_sec)
    else:
        try:
            kwargs["timeout"] = min(float(existing_timeout), float(budget_sec))
        except (ValueError, TypeError):
            kwargs["timeout"] = float(budget_sec)

    api_counters["highlight"]["attempted"] += 1
    if api_counters["highlight"]["dispatched"] >= api_counters["highlight"]["max"]:
        api_counters["highlight"]["blocked"] += 1
        raise RuntimeError(
            f"Batas inferensi highlight terlampaui (maksimal {api_counters['highlight']['max']}). "
            f"Request ke-{api_counters['highlight']['attempted']} diblokir sebelum mencapai jaringan."
        )
    api_counters["highlight"]["dispatched"] += 1

    try:
        res = _orig_chat_create(self, *args, **kwargs)
        _check_cancel_and_deadline(reserve_seconds=0.0)
        api_counters["highlight"]["success"] += 1
        return res
    except (JobCancelledException, JobTimeoutException):
        raise
    except Exception:
        _check_cancel_and_deadline(reserve_seconds=0.0)
        api_counters["highlight"]["failed"] += 1
        raise
Completions.create = _guarded_chat_create

# 2.2 Strict Prohibition on STT and File API Upload
from google.genai.models import Models
_orig_generate_content = Models.generate_content
def _blocked_generate_content(self, *args, **kwargs):
    model = str(kwargs.get("model") or (args[0] if args else "")).lower()
    api_counters["transcribe"]["attempted"] += 1
    api_counters["transcribe"]["blocked"] += 1
    raise RuntimeError(
        f"Semua panggilan inferensi Gemini ({model}) DIBLOKIR pada controlled replay Video 3. "
        "Replay wajib menggunakan respons STT tersimpan dari fixture."
    )
Models.generate_content = _blocked_generate_content

from google.genai.files import Files
_orig_files_upload = Files.upload
def _blocked_files_upload(self, *args, **kwargs):
    api_counters["file_api"]["upload"] += 1
    raise RuntimeError(
        "Semua panggilan upload Gemini File API DIBLOKIR pada controlled replay Video 3."
    )
Files.upload = _blocked_files_upload

# ==============================================================================
# 3. APPLICATION MODULE IMPORTS & AUDIT HOOKS
# ==============================================================================
import shorts_generator.config as cfg
import shorts_generator.local.gemini_transcriber as gt
import shorts_generator.local.transcriber as tr
import shorts_generator.highlights as hl
from shorts_generator.job_manager import JobContext, JobStatus, job_manager, JobTimeoutException, JobCancelledException
from web_app import run_generation_job, jobs, OUTPUT_DIR, get_active_job
from shorts_generator.local.clipper import crop_highlights_local

hl.MAX_HIGHLIGHT_API_ATTEMPTS = 1

# Hook call_highlight_api to record raw candidates per chunk
_orig_call_highlight_api = hl.call_highlight_api
def _audited_call_highlight_api(transcript_text, content_info, duration, num_clips, is_chunk=False, llm_fn=hl.call_muapi_llm, job_ctx=None, framing_mode="podcast", **kwargs):
    res = _orig_call_highlight_api(transcript_text, content_info, duration, num_clips, is_chunk=is_chunk, llm_fn=llm_fn, job_ctx=job_ctx, framing_mode=framing_mode, **kwargs)
    if is_chunk and job_ctx and getattr(job_ctx, "session_folder", None):
        try:
            session_p = OUTPUT_DIR / job_ctx.session_folder
            session_p.mkdir(parents=True, exist_ok=True)
            chunk_n = api_counters["highlight"]["dispatched"]
            raw_chunk_file = session_p / f"raw_candidates_chunk_req_{chunk_n}.json"
            raw_data = {
                "chunk_request_number": chunk_n,
                "recorded_at": get_iso_now(),
                "duration": duration,
                "content_info": content_info,
                "raw_validated_candidates": res.get("highlights", [])
            }
            raw_chunk_file.write_text(json.dumps(raw_data, indent=2, ensure_ascii=False), encoding="utf-8")
            job_ctx.emit_log(f"[audit] Disimpan {len(res.get('highlights', []))} kandidat chunk ke {raw_chunk_file.name}")
        except Exception as e:
            job_ctx.emit_log(f"[audit] Gagal menyimpan chunk candidates: {e}")
    return res
hl.call_highlight_api = _audited_call_highlight_api

class ClassificationContractError(ValueError):
    """Raised when classification response fails contract or parsing."""
    pass

ALLOWED_CONTENT_TYPES = {
    "podcast", "interview", "tutorial", "lecture",
    "commentary", "debate", "vlog", "other",
}
ALLOWED_DENSITIES = {"low", "medium", "high"}

def run_guarded_classification(transcript: Dict, llm_fn: Any, job_ctx: Optional[Any] = None) -> Dict[str, str]:
    """Execute classification with strict fail-fast enforcement (V3-R02 & V3-R02.a).
    
    Tegakkan fail-fast di tingkat harness ketika klasifikasi:
    - Mengalami exception/timeout.
    - Mengembalikan JSON invalid atau hasil yang tidak memenuhi kontrak klasifikasi.
    - Mengembalikan field non-string (dict, list, bool, number, null) atau kategori/density tidak sah.
    Helper produksi yang mengembalikan default other/medium tidak boleh menyamarkan kegagalan.
    Namun respons JSON valid yang memang menyatakan other/medium tetap diterima.
    """
    segments = transcript.get("segments", [])
    sample = " ".join(s.get("text", "") for s in segments[:25])[:3000]
    prompt = f"{hl.CONTENT_TYPE_PROMPT}\n\nTranscript sample:\n{sample}"

    if job_ctx:
        job_ctx.emit_log("[highlights] detecting content type and density with guarded fail-fast...")

    # Dispatch directly via llm_fn so upstream timeouts/network exceptions raise immediately
    raw = llm_fn(prompt)

    try:
        parsed = hl._parse_json_loose(raw)
    except Exception as parse_err:
        raise ClassificationContractError(
            f"Respons klasifikasi bukan JSON valid: {parse_err}. Raw output preview: {str(raw)[:200]!r}"
        )

    if not isinstance(parsed, dict):
        raise ClassificationContractError(
            f"Kontrak klasifikasi gagal: hasil parsing bukan dictionary (tipe: {type(parsed).__name__})"
        )

    if "content_type" not in parsed:
        raise ClassificationContractError(
            f"Kontrak klasifikasi gagal: field 'content_type' hilang. Parsed: {parsed}"
        )
    raw_c_type = parsed["content_type"]
    if not isinstance(raw_c_type, str) or isinstance(raw_c_type, bool):
        raise ClassificationContractError(
            f"Kontrak klasifikasi gagal: field 'content_type' harus bertipe string, "
            f"didapat {type(raw_c_type).__name__}: {raw_c_type!r}"
        )

    if "density" not in parsed:
        raise ClassificationContractError(
            f"Kontrak klasifikasi gagal: field 'density' hilang. Parsed: {parsed}"
        )
    raw_density = parsed["density"]
    if not isinstance(raw_density, str) or isinstance(raw_density, bool):
        raise ClassificationContractError(
            f"Kontrak klasifikasi gagal: field 'density' harus bertipe string, "
            f"didapat {type(raw_density).__name__}: {raw_density!r}"
        )

    c_type = raw_c_type.strip().lower()
    density = raw_density.strip().lower()

    if not c_type or c_type not in ALLOWED_CONTENT_TYPES:
        raise ClassificationContractError(
            f"Kontrak klasifikasi gagal: field 'content_type' bernilai tidak sah ({c_type!r}). "
            f"Harus salah satu dari: {sorted(ALLOWED_CONTENT_TYPES)}"
        )
    if not density or density not in ALLOWED_DENSITIES:
        raise ClassificationContractError(
            f"Kontrak klasifikasi gagal: field 'density' bernilai tidak sah ({density!r}). "
            f"Harus salah satu dari: {sorted(ALLOWED_DENSITIES)}"
        )

    result = {"content_type": c_type, "density": density}
    if job_ctx:
        job_ctx.emit_log(f"[highlights] detected valid: content_type={c_type} density={density}")
    return result

# ==============================================================================
# 4. PRESERVATION & MEDIA VERIFICATION HELPERS
# ==============================================================================
def compute_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def snapshot_preservation_manifest() -> Dict[str, str]:
    manifest = {}
    v1_files = sorted(list((ROOT_DIR / "output_val_v1").glob("**/*")))
    v2_files = sorted(list((ROOT_DIR / "output_val_v2").glob("**/*")))
    for f in v1_files + v2_files:
        if f.is_file():
            rel = str(f.relative_to(ROOT_DIR)).replace("\\", "/")
            manifest[rel] = compute_sha256(f)
    env_p = ROOT_DIR / ".env"
    if env_p.exists():
        manifest[".env"] = compute_sha256(env_p)
    src_v3 = ROOT_DIR / "output_val_v3" / "source_long_v3.mp4"
    if src_v3.exists():
        manifest["output_val_v3/source_long_v3.mp4"] = compute_sha256(src_v3)
    fix_v3 = ROOT_DIR / "output_val_v3" / "20260929_160722_val_v3_long_72842" / "diagnostic_transcript_pre_validation_val_v3_long_72842.json"
    if fix_v3.exists():
        manifest["output_val_v3/fixture_diagnostic.json"] = compute_sha256(fix_v3)
    return manifest

def verify_media_clip(clip_p: Path, vtt_p: Path, matched_record: Optional[Dict] = None) -> Dict[str, Any]:
    info = {
        "filename": clip_p.name,
        "path": str(clip_p),
        "exists": clip_p.exists(),
        "completion_record_found": (matched_record is not None),
    }
    if not clip_p.exists():
        return info

    info["size_bytes"] = clip_p.stat().st_size
    info["sha256"] = compute_sha256(clip_p)

    # ffprobe probe
    cmd_probe = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(clip_p)]
    p_res = subprocess.run(cmd_probe, capture_output=True, text=True)
    if p_res.returncode == 0:
        p_data = json.loads(p_res.stdout)
        info["probed_duration"] = float(p_data.get("format", {}).get("duration", 0))
        for st in p_data.get("streams", []):
            if st.get("codec_type") == "video":
                info["video_codec"] = st.get("codec_name")
                info["width"] = st.get("width")
                info["height"] = st.get("height")
                info["fps"] = st.get("r_frame_rate")
            elif st.get("codec_type") == "audio":
                info["audio_codec"] = st.get("codec_name")
                info["sample_rate"] = st.get("sample_rate")

    # ffmpeg -xerror full decode check
    cmd_dec = ["ffmpeg", "-v", "error", "-xerror", "-i", str(clip_p), "-f", "null", "-"]
    dec_res = subprocess.run(cmd_dec, capture_output=True, text=True)
    info["full_decode_exit_code"] = dec_res.returncode
    info["full_decode_stderr"] = dec_res.stderr.strip()
    info["decode_success"] = (dec_res.returncode == 0 and not dec_res.stderr.strip())

    # VTT verification
    info["vtt_exists"] = vtt_p.exists()
    if vtt_p.exists():
        info["vtt_size"] = vtt_p.stat().st_size
        info["vtt_sha256"] = compute_sha256(vtt_p)
        vtt_lines = vtt_p.read_text(encoding="utf-8").splitlines()
        info["vtt_line_count"] = len(vtt_lines)
        info["vtt_header_valid"] = len(vtt_lines) > 0 and "WEBVTT" in vtt_lines[0]

        cue_timestamps = []
        for line in vtt_lines:
            if "-->" in line:
                parts = line.split("-->")
                if len(parts) == 2:
                    cue_timestamps.append((parts[0].strip(), parts[1].strip().split()[0]))
        info["vtt_cue_count"] = len(cue_timestamps)
        info["vtt_cues_ordered"] = True
        info["vtt_cues_within_duration"] = True

        def _vtt_to_sec(ts_str):
            try:
                p = ts_str.split(":")
                if len(p) == 3:
                    return float(p[0]) * 3600 + float(p[1]) * 60 + float(p[2])
                elif len(p) == 2:
                    return float(p[0]) * 60 + float(p[1])
            except Exception:
                pass
            return 0.0

        prev_end = 0.0
        probed_dur = info.get("probed_duration", 999999.0)
        for start_s, end_s in cue_timestamps:
            s_sec = _vtt_to_sec(start_s)
            e_sec = _vtt_to_sec(end_s)
            if s_sec < prev_end - 0.05 or e_sec < s_sec:
                info["vtt_cues_ordered"] = False
            if e_sec > probed_dur + 0.5:
                info["vtt_cues_within_duration"] = False
            prev_end = e_sec

    # Matched record info
    if matched_record:
        info["expected_start"] = matched_record.get("start_time")
        info["expected_end"] = matched_record.get("end_time")
        if matched_record.get("end_time") is not None and matched_record.get("start_time") is not None:
            info["expected_duration"] = round(float(matched_record["end_time"]) - float(matched_record["start_time"]), 2)
            if "probed_duration" in info:
                info["duration_delta"] = round(info["probed_duration"] - info["expected_duration"], 3)
                info["duration_within_tolerance"] = abs(info["duration_delta"]) <= 0.5
        info["title"] = matched_record.get("title")
        info["hook_sentence"] = matched_record.get("hook_sentence")
        info["virality_reason"] = matched_record.get("virality_reason")
        info["score"] = matched_record.get("score")

    info["audiovisual_assessment"] = "Belum dinilai"
    return info

# ==============================================================================
# 5. OFFLINE VERIFICATION & REPLAY ORCHESTRATION
# ==============================================================================
def execute_controlled_replay(
    dry_run: bool = False,
    override_llm_fn: Optional[Any] = None,
    override_session_dir: Optional[Path] = None,
    override_job_id: Optional[str] = None,
    override_job_manager: Optional[Any] = None,
    skip_guards_test: bool = False,
    skip_render: bool = False,
):
    print("=" * 60)
    print("SHORTSSTUDIO: CONTROLLED REPLAY / RESUME VALIDASI VIDEO 3" + (" (DRY-RUN)" if dry_run else ""))
    print(f"Timestamp: {get_iso_now()}")
    print(f"PID: {os.getpid()}")
    print("=" * 60)

    # 1. Source and Fixture Verification
    source_p = ROOT_DIR / "output_val_v3" / "source_long_v3.mp4"
    fixture_p = ROOT_DIR / "output_val_v3" / "20260929_160722_val_v3_long_72842" / "diagnostic_transcript_pre_validation_val_v3_long_72842.json"

    expected_src_sha = "d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24"
    expected_fix_sha = "5c0342f33294bd7ae605a76f0e169560c7fe1acfcc7bdd21de3f428aabffade5"
    ref_dur = 2630.658322

    if not source_p.exists():
        print(f"[FATAL] Source media {source_p} does not exist!", file=sys.stderr)
        sys.exit(1)
    if not fixture_p.exists():
        print(f"[FATAL] Diagnostic fixture {fixture_p} does not exist!", file=sys.stderr)
        sys.exit(1)

    src_sha = compute_sha256(source_p)
    fix_sha = compute_sha256(fixture_p)
    probed_dur = tr._probe_duration(str(source_p))

    print(f"[Check] Source SHA-256:  {src_sha} (match={src_sha == expected_src_sha})")
    print(f"[Check] Fixture SHA-256: {fix_sha} (match={fix_sha == expected_fix_sha})")
    print(f"[Check] Probed duration: {probed_dur:.6f}s (ref={ref_dur:.6f}s, diff={abs(probed_dur - ref_dur):.6f}s)")

    if src_sha != expected_src_sha:
        print(f"[FATAL] Source SHA mismatch! Expected {expected_src_sha}, got {src_sha}", file=sys.stderr)
        sys.exit(1)
    if fix_sha != expected_fix_sha:
        print(f"[FATAL] Fixture SHA mismatch! Expected {expected_fix_sha}, got {fix_sha}", file=sys.stderr)
        sys.exit(1)
    if abs(probed_dur - ref_dur) > 0.01:
        print(f"[FATAL] Probed duration mismatch! Expected {ref_dur}, got {probed_dur}", file=sys.stderr)
        sys.exit(1)

    # 2. Snapshot Preservation Before Execution
    print("\n[Preservation] Capturing baseline SHA-256 snapshot for 65 V1/V2 files, .env, source, fixture...")
    manifest_before = snapshot_preservation_manifest()
    print(f"[Preservation] Captured {len(manifest_before)} files in pre-run snapshot.")

    # 3. Offline Sanitization & Contract Validation
    print("\n[Sanitizer] Executing production sanitizer on 5,851 raw words from fixture...")
    fixture_data = json.loads(fixture_p.read_text(encoding="utf-8"))
    raw_words = fixture_data.get("raw_words", [])
    if len(raw_words) != 5851:
        print(f"[FATAL] Unexpected word count in fixture: {len(raw_words)} != 5851", file=sys.stderr)
        sys.exit(1)

    sanitized_words, untrusted_spans, recovery_audit = gt._sanitize_and_recover_word_timestamps(
        raw_words, source_duration=probed_dur
    )
    segments = gt._words_to_segments(sanitized_words, untrusted_spans=untrusted_spans, source_duration=probed_dur)

    transcript = {
        "duration": probed_dur,
        "segments": segments,
        "untrusted_spans": untrusted_spans,
        "recovery_audit": recovery_audit,
        "policy_version": gt.SANITIZER_POLICY_VERSION,
    }

    is_valid, err_reason = tr._validate_transcript_contract_detailed(transcript, max_duration=probed_dur)
    if not is_valid:
        print(f"[FATAL] Sanitized transcript failed contract validation: {err_reason}", file=sys.stderr)
        sys.exit(1)

    recovered_words = [a for a in recovery_audit if a.get("action") == "local_bounded_recovery"]
    untrusted_words = [w for w in sanitized_words if w.get("untrusted")]
    total_gap_dur = gt._calculate_union_span_duration(untrusted_spans)

    print(f"[Sanitizer] Sanitization complete:")
    print(f"  Policy version: {transcript['policy_version']}")
    print(f"  Raw words: {len(raw_words)}")
    print(f"  Sanitized words: {len(sanitized_words)}")
    print(f"  Recovered words (estimated): {len(recovered_words)}")
    for r in recovered_words:
        print(f"    - Index {r['index']} '{r['word']}': {r['corrected'][0]:.3f}s..{r['corrected'][1]:.3f}s (raw: {r['raw']})")
    print(f"  Untrusted words: {len(untrusted_words)}")
    print(f"  Untrusted spans: {len(untrusted_spans)} (total {total_gap_dur:.2f}s, {total_gap_dur/probed_dur*100:.2f}% of media)")
    for idx_usp, sp in enumerate(untrusted_spans, 1):
        print(f"    - Span {idx_usp} [{sp['start']:.1f}s..{sp['end']:.1f}s]: {sp['word_count']} words")
    print(f"  Segments produced: {len(segments)}")
    print(f"  Contract valid: {is_valid}")

    # Dynamically verify and prove that exclusion cluster covers all recovered words
    min_est = min(r["corrected"][0] for r in recovered_words) if recovered_words else 512.6
    max_est = max(r["corrected"][1] for r in recovered_words) if recovered_words else 514.6
    est_cluster_start = min(512.6, min_est)
    est_cluster_end = max(515.2, max_est)
    estimated_cluster_spans = [
        {
            "start": est_cluster_start,
            "end": est_cluster_end,
            "reasons": [
                f"estimated_recovery_cluster(hyper_arousal_hyper_{min_est:.3f}..{max_est:.3f}_context_extended_to_{est_cluster_end:.1f})"
            ],
        }
    ]
    # Filter spans combines untrusted_spans AND estimated_cluster_spans
    exclusion_spans = untrusted_spans + estimated_cluster_spans
    print(f"[Filter] Total exclusion spans (5 untrusted + 1 estimated cluster): {len(exclusion_spans)}")
    for idx_sp, sp in enumerate(exclusion_spans, 1):
        print(f"  Exclusion {idx_sp}: [{sp['start']:.1f}s..{sp['end']:.1f}s] - {sp.get('reasons')}")

    # 4. Offline Proof of Blocking Guards
    if not skip_guards_test:
        print("\n[Guards] Testing that STT and upload guards are strictly active...")
        mock_client = openai.OpenAI(api_key="mock_key")
        if getattr(mock_client, "max_retries", -1) != 0:
            print(f"[FATAL] OpenAI max_retries is {getattr(mock_client, 'max_retries', -1)} != 0", file=sys.stderr)
            sys.exit(1)
        if hl.MAX_HIGHLIGHT_API_ATTEMPTS != 1:
            print(f"[FATAL] MAX_HIGHLIGHT_API_ATTEMPTS is {hl.MAX_HIGHLIGHT_API_ATTEMPTS} != 1", file=sys.stderr)
            sys.exit(1)

        from google import genai
        g_mock = genai.Client(api_key="mock_key")

        stt_blocked = False
        try:
            g_mock.models.generate_content(model="gemini-3.5-transcribe", contents="test")
        except RuntimeError as re_stt:
            if "Semua panggilan inferensi Gemini" in str(re_stt):
                stt_blocked = True
        if not stt_blocked:
            print("[FATAL] STT blocking guard failed to raise RuntimeError!", file=sys.stderr)
            sys.exit(1)
        print("  STT blocking guard: PASSED (attempted STT call was intercepted and blocked).")

        upload_blocked = False
        try:
            g_mock.files.upload(file="dummy.mp3")
        except RuntimeError as re_up:
            if "Semua panggilan upload Gemini File API DIBLOKIR" in str(re_up):
                upload_blocked = True
        if not upload_blocked:
            print("[FATAL] File upload blocking guard failed to raise RuntimeError!", file=sys.stderr)
            sys.exit(1)
        print("  File upload blocking guard: PASSED (attempted upload was intercepted and blocked).")

    # Reset counters
    for k in ("transcribe", "highlight"):
        for subk in ("attempted", "dispatched", "success", "failed", "blocked"):
            api_counters[k][subk] = 0
    for k in ("upload", "polling", "delete", "delete_success", "delete_failed"):
        api_counters["file_api"][k] = 0

    print("[Guards] Counters cleanly reset: transcribe attempted/dispatched = 0, file upload = 0.")

    if dry_run:
        print("\n" + "=" * 60)
        print("[DRY-RUN] Offline verification and proof of guards PASSED successfully.")
        print("[DRY-RUN] Ready for single controlled replay execution.")
        print("=" * 60)
        return {"status": "dry_run_passed"}

    # 5. Highlight & Render Execution
    print("\n" + "=" * 60)
    print("DISPATCHING HIGHLIGHT INFERENCES (APMix deepseek-v4-flash-free)")
    print("=" * 60)

    active_jm = override_job_manager or job_manager
    job_id = override_job_id or f"val_v3_replay_{int(time.time()) % 100000}"
    timestamp_str = datetime.now(WIB).strftime("%Y%m%d_%H%M%S")
    session_folder = f"{timestamp_str}_{job_id}"
    if override_session_dir:
        session_dir = Path(override_session_dir)
    else:
        session_dir = ROOT_DIR / VAL_OUTPUT_DIR / session_folder
    session_dir.mkdir(parents=True, exist_ok=True)

    config_payload = {
        "llm_provider": "openai",
        "transcriber_provider": "gemini",
        "gemini_model": "gemini-3.6-flash",
        "gemini_transcriber_model": "gemini-3.5-transcribe",
        "openai_model": "deepseek-v4-flash-free",
        "whisper_model": "base",
        "openai_base_url": "https://api.apmix.ai/v1",
        "gemini_api_key": cfg.GEMINI_API_KEY,
        "openai_api_key": cfg.OPENAI_API_KEY,
        "muapi_api_key": cfg.MUAPI_API_KEY,
    }

    job_params = {
        "url": str(source_p),
        "session_folder": session_folder,
        "num_clips": 3,
        "aspect_ratio": "9:16",
        "format": "720",
        "language": "id",
        "mode": "local",
        "config": config_payload,
    }

    t0_perf = time.perf_counter()
    start_iso = get_iso_now()
    logs_captured = []

    with active_jm._admission_lock:
        job_ctx = active_jm.admit_job(
            job_id=job_id,
            url=str(source_p),
            params=job_params,
            timeout_seconds=DEFAULT_JOB_TIMEOUT_SECONDS,
        )
        job_ctx.session_folder = session_folder
        jobs[job_id] = job_ctx.to_dict()

    orig_emit = job_ctx.emit_log
    def custom_emit(msg: str):
        elapsed = time.perf_counter() - t0_perf
        now_ts = datetime.now(WIB).strftime("%H:%M:%S.%f")[:-3]
        log_entry = {
            "time": now_ts,
            "iso": get_iso_now(),
            "elapsed": round(elapsed, 3),
            "message": msg
        }
        logs_captured.append(log_entry)
        print(f"[Replay-V3] [{now_ts}] (+{elapsed:6.2f}s) {msg}", flush=True)
        orig_emit(msg)
    job_ctx.emit_log = custom_emit

    # V3-R01: Clock initialization before first inference
    now_wall = time.time()
    job_ctx.started_at = now_wall
    job_ctx.transition_to(JobStatus.RUNNING, stage="highlighting", progress=30)
    jobs[job_id] = job_ctx.to_dict()

    all_raw_candidates: List[Dict] = []
    chunk_raw_records: List[Dict] = []
    clean_candidates: List[Dict] = []
    rejected_candidates: List[Dict] = []
    top_candidates: List[Dict] = []
    rendered_shorts: List[Dict] = []
    clip_verifications: List[Dict] = []
    content_info: Dict[str, str] = {}
    chunks: List[Dict] = []

    final_status = JobStatus.FAILED
    execution_err = None
    stage_for_final = "failed"

    try:
        # Step 5.1: Create LLM callable using runner configuration
        if override_llm_fn:
            llm_fn = override_llm_fn
        else:
            from shorts_generator.local.llm import create_llm_callable
            llm_fn = create_llm_callable(config=config_payload, job_ctx=job_ctx)

        # Step 5.2: Detect content type / density (Call 1) with fail-fast (V3-R02)
        content_info = run_guarded_classification(transcript, llm_fn=llm_fn, job_ctx=job_ctx)

        # Step 5.3: Chunk transcript (Video 3 is 2630s >= 1800s -> 3 chunks)
        chunks = hl.chunk_transcript(transcript)
        job_ctx.emit_log(f"[highlights] long video split into {len(chunks)} chunks")

        # Step 5.4: Process each chunk (Calls 2, 3, 4)
        for i, chunk in enumerate(chunks, 1):
            offset = float(chunk.get("_offset", 0.0))
            chunk_dur = chunk["duration"]
            job_ctx.emit_log(f"[highlights] requesting candidates for Chunk {i}/{len(chunks)} (offset {offset:.0f}s, dur {chunk_dur:.0f}s)...")
            text = hl.build_transcript_text(chunk)
            chunk_res = hl.call_highlight_api(
                text, content_info, chunk_dur, num_clips=3, is_chunk=True, llm_fn=llm_fn, job_ctx=job_ctx
            )
            chunk_candidates = chunk_res.get("highlights", [])
            job_ctx.emit_log(f"[highlights] Chunk {i} returned {len(chunk_candidates)} candidates.")

            for h in chunk_candidates:
                abs_start = round(float(h["start_time"]) + offset, 2)
                abs_end = round(float(h["end_time"]) + offset, 2)
                c_copy = dict(h)
                c_copy["chunk_index"] = i
                c_copy["rel_start"] = float(h["start_time"])
                c_copy["rel_end"] = float(h["end_time"])
                c_copy["start_time"] = abs_start
                c_copy["end_time"] = abs_end
                all_raw_candidates.append(c_copy)
                chunk_raw_records.append(c_copy)

        # Step 5.5: Save complete raw candidate manifest before deduplication
        raw_manifest_path = session_dir / "all_raw_candidates_before_dedupe.json"
        raw_manifest_path.write_text(json.dumps({
            "recorded_at": get_iso_now(),
            "total_raw_candidates": len(all_raw_candidates),
            "candidates": all_raw_candidates,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        job_ctx.emit_log(f"[audit] Disimpan {len(all_raw_candidates)} total kandidat mentah ke {raw_manifest_path.name}")

        # Step 5.6: Filter out untrusted spans AND estimated recovery cluster
        job_ctx.emit_log("[highlights] filtering candidates against untrusted spans and estimated ranges...")
        for h in all_raw_candidates:
            h_start = float(h["start_time"])
            h_end = float(h["end_time"])
            intersected = False
            intersect_reason = None
            for sp in exclusion_spans:
                s_start = float(sp["start"])
                s_end = float(sp["end"])
                if h_start < s_end - 0.05 and h_end > s_start + 0.05:
                    intersected = True
                    intersect_reason = f"intersects span [{s_start:.1f}s..{s_end:.1f}s] ({'; '.join(sp.get('reasons', []))})"
                    break
            if intersected:
                h_rej = dict(h)
                h_rej["rejection_reason"] = intersect_reason
                rejected_candidates.append(h_rej)
                job_ctx.emit_log(f"[highlights] candidate {h.get('title')!r} [{h_start:.1f}s..{h_end:.1f}s] REJECTED: {intersect_reason}")
            else:
                clean_candidates.append(h)

        # Save rejected candidates audit
        rejected_path = session_dir / "rejected_candidates_audit.json"
        rejected_path.write_text(json.dumps({
            "recorded_at": get_iso_now(),
            "total_rejected": len(rejected_candidates),
            "rejected_candidates": rejected_candidates,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        # Step 5.7: Deduplicate clean candidates
        job_ctx.emit_log(f"[highlights] deduplicating {len(clean_candidates)} safe candidates...")
        deduped = hl.dedupe_highlights(clean_candidates)
        top_candidates = sorted(deduped, key=lambda x: int(x.get("score", 0)), reverse=True)[:3]
        job_ctx.emit_log(f"[highlights] selected {len(top_candidates)} top highlights (target: 3).")

        for idx_top, top_c in enumerate(top_candidates, 1):
            job_ctx.emit_log(f"  Selected #{idx_top}: {top_c.get('title')!r} [{top_c['start_time']}s..{top_c['end_time']}s] (score: {top_c.get('score')})")

        # Step 5.8: Render clips if candidates exist
        if top_candidates and not dry_run and not skip_render:
            job_ctx.transition_to(JobStatus.RUNNING, stage="rendering", progress=60)
            jobs[job_id] = job_ctx.to_dict()

            job_ctx.pipeline_context = {
                "mode": "local",
                "source_video_url": str(source_p),
                "transcript": transcript,
                "highlights": top_candidates,
            }

            job_ctx.emit_log(f"[cropper] rendering {len(top_candidates)} shorts into {session_dir}...")
            rendered_shorts = crop_highlights_local(
                str(source_p),
                top_candidates,
                aspect_ratio="9:16",
                out_dir=str(session_dir),
                transcript=transcript,
                job_ctx=job_ctx,
            )

            # Verification of Resulting Clips
            from scratch.run_validation_v3 import build_shorts_lookup
            shorts_by_index, shorts_by_filename = build_shorts_lookup(rendered_shorts)
            for i in range(1, 4):
                target_fname = f"short_{i:02d}.mp4"
                clip_p = session_dir / target_fname
                vtt_p = session_dir / f"short_{i:02d}.vtt"
                matched_rec = shorts_by_index.get(i) or shorts_by_filename.get(target_fname.lower())
                v_info = verify_media_clip(clip_p, vtt_p, matched_rec)
                clip_verifications.append(v_info)

        successful_renders = [c for c in clip_verifications if c.get("exists") and c.get("decode_success")]
        if skip_render and top_candidates:
            final_status = JobStatus.COMPLETED
            stage_for_final = "completed"
        elif len(successful_renders) == len(top_candidates) and len(top_candidates) > 0:
            final_status = JobStatus.COMPLETED
            stage_for_final = "completed"
        elif successful_renders:
            final_status = JobStatus.PARTIAL
            stage_for_final = "partial"
        else:
            final_status = JobStatus.FAILED
            stage_for_final = "failed"
            execution_err = "No clips successfully rendered."

    except JobCancelledException as jce:
        execution_err = str(jce)
        job_ctx.error = execution_err
        job_ctx.cancel_reason = execution_err
        final_status = JobStatus.CANCELED
        stage_for_final = "canceled"
    except JobTimeoutException as jte:
        execution_err = str(jte)
        job_ctx.error = execution_err
        job_ctx.is_timeout = True
        final_status = JobStatus.TIMEOUT
        stage_for_final = "timed_out"
    except Exception as exc:
        execution_err = f"{type(exc).__name__}: {exc}"
        job_ctx.error = execution_err
        if getattr(job_ctx, "is_timeout", False) or (job_ctx.started_at and (time.time() - job_ctx.started_at >= job_ctx.timeout_seconds)):
            final_status = JobStatus.TIMEOUT
            stage_for_final = "timed_out"
        elif getattr(job_ctx, "cancel_event", None) and job_ctx.cancel_event.is_set():
            final_status = JobStatus.CANCELED
            stage_for_final = "canceled"
        else:
            final_status = JobStatus.FAILED
            stage_for_final = "failed"
    finally:
        # V3-R01: Guaranteed lifecycle finalization and preservation check on success or failure!
        t1_perf = time.perf_counter()
        total_wall_clock = t1_perf - t0_perf
        end_iso = get_iso_now()
        job_ctx.ended_at = time.time()

        job_ctx.transition_to(
            final_status,
            stage=stage_for_final,
            progress=100 if final_status == JobStatus.COMPLETED else job_ctx.progress
        )
        if execution_err:
            job_ctx.error = execution_err
            job_ctx.emit_log(f"[FINAL] Job terminated with status {final_status}: {execution_err}")
        jobs[job_id] = job_ctx.to_dict()

        # 7. Snapshot Preservation After Execution
        print("\n[Preservation] Verifying SHA-256 post-run preservation...")
        manifest_after = snapshot_preservation_manifest()
        preservation_diffs = []
        for k, v in manifest_before.items():
            if k not in manifest_after:
                preservation_diffs.append(f"DELETED: {k}")
            elif manifest_after[k] != v:
                preservation_diffs.append(f"MODIFIED: {k} (was {v[:8]}, now {manifest_after[k][:8]})")
        for k in manifest_after:
            if k not in manifest_before:
                preservation_diffs.append(f"NEW FILE IN PROTECTED PATH: {k}")

        preservation_intact = (len(preservation_diffs) == 0)
        print(f"[Preservation] Preserved files intact: {preservation_intact}")
        if not preservation_intact:
            for diff in preservation_diffs:
                print(f"  [Preservation Error] {diff}", file=sys.stderr)

        # 8. Record Final Job Metadata on Disk
        successful_renders = [c for c in clip_verifications if c.get("exists") and c.get("decode_success")]
        disk_meta = {
            "job_id": job_id,
            "session_folder": session_folder,
            "status": str(final_status),
            "stage": stage_for_final,
            "error": execution_err,
            "run_type": "controlled_replay_v3",
            "created_at": start_iso,
            "started_at": datetime.fromtimestamp(job_ctx.started_at, WIB).isoformat() if job_ctx.started_at else None,
            "ended_at": end_iso,
            "wall_clock_seconds": round(total_wall_clock, 2),
            "timeout_seconds": job_ctx.timeout_seconds,
            "source_media": {
                "path": str(source_p),
                "sha256": src_sha,
                "probed_duration": probed_dur,
            },
            "fixture_provenance": {
                "origin_job": "val_v3_long_72842",
                "path": str(fixture_p),
                "sha256": fix_sha,
                "policy_version": gt.SANITIZER_POLICY_VERSION,
            },
            "api_counters": api_counters,
            "sanitization_summary": {
                "raw_words": len(raw_words),
                "sanitized_words": len(sanitized_words),
                "recovered_words_count": len(recovered_words),
                "recovered_words": recovered_words,
                "untrusted_words_count": len(untrusted_words),
                "untrusted_spans_count": len(untrusted_spans),
                "untrusted_spans": untrusted_spans,
                "total_untrusted_gap_seconds": round(total_gap_dur, 2),
                "gap_fraction_percent": round(total_gap_dur / probed_dur * 100, 3),
                "segments_count": len(segments),
                "contract_valid": is_valid,
            },
            "highlight_summary": {
                "content_type": content_info.get("content_type"),
                "density": content_info.get("density"),
                "chunks_count": len(chunks),
                "total_raw_candidates": len(all_raw_candidates),
                "rejected_candidates_count": len(rejected_candidates),
                "clean_candidates_count": len(clean_candidates),
                "deduped_candidates_count": len(top_candidates),
                "top_selected_count": len(top_candidates),
            },
            "clips": clip_verifications,
            "preservation": {
                "v1_v2_files_count": len(manifest_before) - 3,
                "intact": preservation_intact,
                "diffs": preservation_diffs,
            },
            "logs": logs_captured,
        }

        meta_file = session_dir / f"job_{job_id}.json"
        meta_file.write_text(json.dumps(disk_meta, indent=2, ensure_ascii=False), encoding="utf-8")

        if override_session_dir is None:
            global_summary_file = ROOT_DIR / VAL_OUTPUT_DIR / "validation_v3_replay_summary.json"
            global_summary_file.write_text(json.dumps(disk_meta, indent=2, ensure_ascii=False), encoding="utf-8")

        print("\n" + "=" * 60)
        print("CONTROLLED REPLAY COMPLETED / TERMINATED")
        print(f"Final Status: {final_status}")
        print(f"Clips Rendered: {len(successful_renders)} / {len(top_candidates)}")
        print(f"API Counters: Transcribe={api_counters['transcribe']['dispatched']}, Upload={api_counters['file_api']['upload']}, Highlight={api_counters['highlight']['dispatched']}")
        print(f"Session Dir: {session_dir}")
        print(f"Metadata: {meta_file}")
        print("=" * 60)

    return disk_meta

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv or "--offline-check" in sys.argv
    execute_controlled_replay(dry_run=is_dry)

