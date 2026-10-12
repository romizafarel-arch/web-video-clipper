"""Runner Harness and Pre-flight Verification for Video 2 — Podcast (Two Speakers).

Enforces:
1. Strict output and cache isolation to output_val_v2/ before importing application modules.
2. Policy B/B with per-job inference guards:
   - OpenAI SDK max_retries = 0.
   - Maximum 2 highlight inferences (classification + ranking). Any 3rd attempt from application retry (e.g. on empty JSON) is blocked before reaching the network.
   - Maximum 1 Gemini transcription inference. Any fallback to multimodal models (gemini-3.5-flash) is blocked before dispatch.
   - Separate File API operation tracking (upload, delete) from model inferences.
3. Pre-flight binary and environment checks (Python, FFmpeg, FFprobe version checks must pass).
4. Monotonic timing and ISO timestamps with +07:00 offset.
5. In-process lifecycle and admission verification.
6. Full decode checks (-xerror) on resulting MP4/VTT files.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Force UTF-8 stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ==============================================================================
# 1. ENFORCE OUTPUT AND CACHE ISOLATION BEFORE IMPORTING APPLICATION MODULES
# ==============================================================================
VAL_OUTPUT_DIR = "output_val_v2"
os.environ["LOCAL_OUTPUT_DIR"] = VAL_OUTPUT_DIR

ROOT_DIR = Path(__file__).resolve().parent.parent
os.chdir(ROOT_DIR)
sys.path.insert(0, str(ROOT_DIR))

# ==============================================================================
# 2. PER-JOB INFERENCE COUNTERS AND GUARDS (POLICY B/B)
# ==============================================================================
api_counters = {
    "transcribe": {
        "attempted": 0,
        "dispatched": 0,
        "success": 0,
        "failed": 0,
        "blocked": 0,
        "max": 1,
    },
    "highlight": {
        "attempted": 0,
        "dispatched": 0,
        "success": 0,
        "failed": 0,
        "blocked": 0,
        "max": 2,
    },
    "file_api": {
        "upload": 0,
        "delete": 0,
        "polling": 0,
    },
}

# 2.1 OpenAI SDK max_retries = 0 and Highlight Call Limit Guard
import openai
from openai.resources.chat.completions import Completions

_orig_openai_init = openai.OpenAI.__init__
def _patched_openai_init(self, *args, **kwargs):
    kwargs["max_retries"] = 0
    _orig_openai_init(self, *args, **kwargs)
openai.OpenAI.__init__ = _patched_openai_init

_orig_chat_create = Completions.create
def _guarded_chat_create(self, *args, **kwargs):
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
        api_counters["highlight"]["success"] += 1
        return res
    except Exception:
        api_counters["highlight"]["failed"] += 1
        raise
Completions.create = _guarded_chat_create

# 2.2 Gemini Transcription Limit & Fallback Blocking Guard
from google.genai.models import Models
_orig_generate_content = Models.generate_content

def _guarded_generate_content(self, *args, **kwargs):
    model = str(kwargs.get("model") or (args[0] if args else "")).lower()
    contents = kwargs.get("contents") or (args[1] if len(args) > 1 else None)

    is_transcribe_prompt = False
    if contents and isinstance(contents, list) and len(contents) >= 2:
        for c in contents:
            if isinstance(c, str) and "You are a precise speech-to-text audio transcriber" in c:
                is_transcribe_prompt = True
                break

    if is_transcribe_prompt and "transcribe" not in model:
        api_counters["transcribe"]["blocked"] += 1
        raise RuntimeError(
            f"Transkripsi model fallback ({model}) diblokir oleh kebijakan harness Video 2 "
            "(Policy B/B: fail-fast pada gemini-3.5-transcribe, dilarang fallback ke model lain)."
        )

    if "transcribe" in model:
        api_counters["transcribe"]["attempted"] += 1
        if api_counters["transcribe"]["dispatched"] >= api_counters["transcribe"]["max"]:
            api_counters["transcribe"]["blocked"] += 1
            raise RuntimeError(
                f"Batas inferensi transkripsi terlampaui (maksimal {api_counters['transcribe']['max']}). "
                "Request diblokir sebelum mencapai jaringan."
            )
        api_counters["transcribe"]["dispatched"] += 1
        try:
            res = _orig_generate_content(self, *args, **kwargs)
            api_counters["transcribe"]["success"] += 1
            return res
        except Exception:
            api_counters["transcribe"]["failed"] += 1
            raise

    return _orig_generate_content(self, *args, **kwargs)
Models.generate_content = _guarded_generate_content

# 2.3 Gemini File API Tracking (Separate from Model Inference)
from google.genai.files import Files
_orig_files_upload = Files.upload
def _tracked_files_upload(self, *args, **kwargs):
    api_counters["file_api"]["upload"] += 1
    return _orig_files_upload(self, *args, **kwargs)
Files.upload = _tracked_files_upload

_orig_files_delete = Files.delete
def _tracked_files_delete(self, *args, **kwargs):
    api_counters["file_api"]["delete"] += 1
    return _orig_files_delete(self, *args, **kwargs)
Files.delete = _tracked_files_delete


# Import application modules AFTER setting os.environ["LOCAL_OUTPUT_DIR"] and installing harness guards
import shorts_generator.config as cfg
import shorts_generator.local.gemini_transcriber as gt
import shorts_generator.local.transcriber as tr
from shorts_generator.job_manager import JobContext, JobStatus, job_manager
from web_app import run_generation_job, jobs, OUTPUT_DIR, get_active_job

WIB = timezone(timedelta(hours=7))

def get_iso_now() -> str:
    return datetime.now(WIB).isoformat()

def get_package_version(pkg_name: str) -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version(pkg_name)
    except Exception:
        try:
            mod = __import__(pkg_name)
            return getattr(mod, "__version__", "unknown")
        except Exception:
            return "not_installed"

def run_preflight_check() -> dict:
    """Execute pre-flight check without making any paid API calls."""
    python_exe = sys.executable
    ffmpeg_exe = shutil.which("ffmpeg")
    ffprobe_exe = shutil.which("ffprobe")

    ffmpeg_ver = "unknown"
    ffmpeg_ok = False
    if ffmpeg_exe:
        try:
            r = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True)
            if r.returncode == 0:
                ffmpeg_ver = r.stdout.splitlines()[0] if r.stdout else "unknown"
                ffmpeg_ok = True
        except Exception:
            pass

    ffprobe_ver = "unknown"
    ffprobe_ok = False
    if ffprobe_exe:
        try:
            r = subprocess.run([ffprobe_exe, "-version"], capture_output=True, text=True)
            if r.returncode == 0:
                ffprobe_ver = r.stdout.splitlines()[0] if r.stdout else "unknown"
                ffprobe_ok = True
        except Exception:
            pass

    binding_results = {
        "cfg_LOCAL_OUTPUT_DIR": cfg.LOCAL_OUTPUT_DIR,
        "gt_LOCAL_OUTPUT_DIR": gt.LOCAL_OUTPUT_DIR,
        "tr_LOCAL_OUTPUT_DIR": tr.LOCAL_OUTPUT_DIR,
        "web_app_OUTPUT_DIR": str(OUTPUT_DIR),
        "target_output_dir": str(ROOT_DIR / VAL_OUTPUT_DIR),
        "cfg_matches": cfg.LOCAL_OUTPUT_DIR == VAL_OUTPUT_DIR,
        "gt_matches": gt.LOCAL_OUTPUT_DIR == VAL_OUTPUT_DIR,
        "tr_matches": tr.LOCAL_OUTPUT_DIR == VAL_OUTPUT_DIR,
        "web_app_matches": str(OUTPUT_DIR) == str(ROOT_DIR / VAL_OUTPUT_DIR),
    }

    test_audio_cache, _ = gt._get_audio_cache_path("isolation_test.mp4")
    test_tr_cache, _ = tr._transcript_cache_paths("isolation_test.mp4", "gemini", "gemini-3.5-transcribe", "id")

    audio_cache_dir = str(Path(test_audio_cache.parent).resolve())
    tr_cache_dir = str(Path(test_tr_cache.parent).resolve())
    expected_audio_cache = str((ROOT_DIR / VAL_OUTPUT_DIR / ".cache" / "audio").resolve())
    expected_tr_cache = str((ROOT_DIR / VAL_OUTPUT_DIR / ".cache" / "transcripts").resolve())

    cache_isolation_results = {
        "audio_cache_dir": audio_cache_dir,
        "expected_audio_cache_dir": expected_audio_cache,
        "audio_cache_isolated": audio_cache_dir.lower() == expected_audio_cache.lower(),
        "transcript_cache_dir": tr_cache_dir,
        "expected_transcript_cache_dir": expected_tr_cache,
        "transcript_cache_isolated": tr_cache_dir.lower() == expected_tr_cache.lower(),
    }

    v1_audio_cache = ROOT_DIR / "output_val_v1" / ".cache" / "audio"
    v1_tr_cache = ROOT_DIR / "output_val_v1" / ".cache" / "transcripts"
    v1_preservation = {
        "v1_audio_cache_exists": v1_audio_cache.exists(),
        "v1_audio_cache_files": len(list(v1_audio_cache.glob("*.*"))) if v1_audio_cache.exists() else 0,
        "v1_tr_cache_exists": v1_tr_cache.exists(),
        "v1_tr_cache_files": len(list(v1_tr_cache.glob("*.*"))) if v1_tr_cache.exists() else 0,
        "v1_preserved": v1_audio_cache.exists() and v1_tr_cache.exists(),
    }

    # Policy B/B Mock Checks
    test_client = openai.OpenAI(api_key="mock_key")
    openai_max_retries_zero = (getattr(test_client, "max_retries", -1) == 0)

    from google import genai
    g_mock_client = genai.Client(api_key="mock_key")
    gemini_fallback_blocked = False
    try:
        g_mock_client.models.generate_content(
            model="gemini-3.5-flash",
            contents=["mock_file", "You are a precise speech-to-text audio transcriber. Transcribe the entire audio..."]
        )
    except RuntimeError as re:
        if "diblokir oleh kebijakan harness Video 2" in str(re):
            gemini_fallback_blocked = True

    policy_bb_verification = {
        "policy": "B/B (Fail-fast, max_retries=0, 1 transcribe, max 2 highlights)",
        "openai_max_retries": getattr(test_client, "max_retries", -1),
        "openai_max_retries_zero_verified": openai_max_retries_zero,
        "gemini_fallback_blocked_verified": gemini_fallback_blocked,
        "highlight_inference_cap": 2,
        "transcribe_inference_cap": 1,
    }

    packages = {
        "google-genai": get_package_version("google-genai"),
        "openai": get_package_version("openai"),
        "opencv-python": get_package_version("cv2"),
        "faster-whisper": get_package_version("faster-whisper"),
        "flask": get_package_version("flask"),
        "pydantic": get_package_version("pydantic"),
    }

    is_passed = (
        ffmpeg_ok and
        ffprobe_ok and
        binding_results["cfg_matches"] and
        binding_results["gt_matches"] and
        binding_results["tr_matches"] and
        binding_results["web_app_matches"] and
        cache_isolation_results["audio_cache_isolated"] and
        cache_isolation_results["transcript_cache_isolated"] and
        v1_preservation["v1_preserved"] and
        openai_max_retries_zero and
        gemini_fallback_blocked
    )

    preflight_data = {
        "artifact_type": "Video_2_Preflight_Check",
        "verified_at": get_iso_now(),
        "working_directory": str(ROOT_DIR),
        "python_runtime": {
            "executable": python_exe,
            "version": sys.version,
            "packages": packages,
        },
        "media_binaries": {
            "ffmpeg_path": ffmpeg_exe,
            "ffmpeg_version": ffmpeg_ver,
            "ffmpeg_verified": ffmpeg_ok,
            "ffprobe_path": ffprobe_exe,
            "ffprobe_version": ffprobe_ver,
            "ffprobe_verified": ffprobe_ok,
        },
        "binding_verification": binding_results,
        "cache_isolation": cache_isolation_results,
        "video_1_preservation": v1_preservation,
        "policy_bb_verification": policy_bb_verification,
        "preflight_status": "PASSED" if is_passed else "FAILED",
    }

    out_file = ROOT_DIR / VAL_OUTPUT_DIR / "preflight_v2_check.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(preflight_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[Pre-flight] Pre-flight verification completed. Status: {preflight_data['preflight_status']}.")
    print(f"[Pre-flight] Report saved to: {out_file}")
    return preflight_data


def execute_video_2_validation(
    source_media_path: str,
    language: str = "id",
):
    """Execute single cold run of Video 2 after pre-flight confirmation."""
    preflight = run_preflight_check()
    if preflight["preflight_status"] != "PASSED":
        print("[FATAL] Pre-flight checks failed. Aborting execution before making any API calls!", file=sys.stderr)
        sys.exit(1)

    # Reset per-job counters
    for k in ("transcribe", "highlight"):
        for subk in ("attempted", "dispatched", "success", "failed", "blocked"):
            api_counters[k][subk] = 0
    for k in ("upload", "delete", "polling"):
        api_counters["file_api"][k] = 0

    print("==================================================")
    print("STARTING VIDEO 2 (PODCAST) COLD RUN")
    print(f"Start Timestamp: {get_iso_now()}")
    print(f"PID: {os.getpid()}")
    print(f"Source: {source_media_path}")
    print(f"Language: {language}")
    print(f"Policy: B/B (OpenAI max_retries=0, Highlight cap=2, Gemini no-fallback cap=1)")
    print("==================================================")

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

    job_id = f"val_v2_pod_verify_{int(time.time()) % 100000}"
    timestamp_str = datetime.now(WIB).strftime("%Y%m%d_%H%M%S")
    session_folder = f"{timestamp_str}_{job_id}"

    job_params = {
        "url": source_media_path,
        "session_folder": session_folder,
        "num_clips": 3,
        "aspect_ratio": "9:16",
        "format": "720",
        "language": language,
        "mode": "local",
        "config": config_payload,
    }

    t0_perf = time.perf_counter()
    start_iso = get_iso_now()
    logs_captured = []

    with job_manager._admission_lock:
        job_ctx = job_manager.admit_job(
            job_id=job_id,
            url=source_media_path,
            params=job_params,
            timeout_seconds=1800.0,
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
        print(f"[V2-Pod] [{now_ts}] (+{elapsed:6.2f}s) {msg}", flush=True)
        orig_emit(msg)
    job_ctx.emit_log = custom_emit

    thread = threading.Thread(
        target=run_generation_job,
        args=(job_id, job_params),
        daemon=True,
    )
    job_ctx.worker_thread = thread
    thread.start()
    thread.join()

    t1_perf = time.perf_counter()
    end_iso = get_iso_now()
    total_duration = t1_perf - t0_perf

    # Check lifecycle in the SAME process
    worker_thread_alive = thread.is_alive()
    in_memory_active_ctx = job_manager.get_active_job()
    in_memory_active_webapp = get_active_job()
    in_memory_status = jobs.get(job_id, {}).get("status")
    in_memory_stage = jobs.get(job_id, {}).get("stage")

    session_dir = OUTPUT_DIR / session_folder
    disk_meta_file = session_dir / f"job_{job_id}.json"
    disk_meta_data = {}
    if disk_meta_file.exists():
        try:
            disk_meta_data = json.loads(disk_meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            disk_meta_data = {"read_error": str(e)}

    print(f"\n==================================================")
    print(f"LIFECYCLE & ADMISSION VERIFICATION IN SAME PROCESS (PID {os.getpid()}):")
    print(f"  Worker thread alive: {worker_thread_alive}")
    print(f"  job_manager.get_active_job(): {in_memory_active_ctx}")
    print(f"  web_app.get_active_job(): {in_memory_active_webapp}")
    print(f"  In-memory status: {in_memory_status}, stage: {in_memory_stage}")
    print(f"  Disk metadata status: {disk_meta_data.get('status')}")
    print(f"  Disk metadata duration_seconds: {disk_meta_data.get('duration_seconds')}")
    print(f"  API Counters: {json.dumps(api_counters, indent=2)}")
    print(f"==================================================")

    # Physical verification on resulting MP4 & VTT
    clip_verifications = []
    result_shorts = disk_meta_data.get("result", {}).get("shorts", []) if isinstance(disk_meta_data.get("result"), dict) else []

    for i in range(1, 4):
        clip_p = session_dir / f"short_{i:02d}.mp4"
        vtt_p = session_dir / f"short_{i:02d}.vtt"
        c_info = {
            "clip_index": i,
            "path": str(clip_p),
            "exists": clip_p.exists(),
        }
        if clip_p.exists():
            c_info["size_bytes"] = clip_p.stat().st_size
            c_info["sha256"] = hashlib.sha256(clip_p.read_bytes()).hexdigest()

            # Probe media format
            cmd_probe = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(clip_p)]
            p_res = subprocess.run(cmd_probe, capture_output=True, text=True)
            if p_res.returncode == 0:
                p_data = json.loads(p_res.stdout)
                c_info["probed_duration"] = float(p_data.get("format", {}).get("duration", 0))
                for st in p_data.get("streams", []):
                    if st.get("codec_type") == "video":
                        c_info["video_codec"] = st.get("codec_name")
                        c_info["width"] = st.get("width")
                        c_info["height"] = st.get("height")
                        c_info["fps"] = st.get("r_frame_rate")
                        c_info["video_duration"] = float(st.get("duration", 0) or 0)
                    elif st.get("codec_type") == "audio":
                        c_info["audio_codec"] = st.get("codec_name")
                        c_info["sample_rate"] = st.get("sample_rate")
                        c_info["channels"] = st.get("channels")
                        c_info["audio_duration"] = float(st.get("duration", 0) or 0)

            # Full video and audio decode check using ffmpeg -xerror
            cmd_dec = ["ffmpeg", "-v", "error", "-xerror", "-i", str(clip_p), "-f", "null", "-"]
            dec_res = subprocess.run(cmd_dec, capture_output=True, text=True)
            c_info["full_decode_exit_code"] = dec_res.returncode
            c_info["full_decode_stderr"] = dec_res.stderr.strip()
            c_info["decode_success"] = (dec_res.returncode == 0 and not dec_res.stderr.strip())

            # VTT inspection
            c_info["vtt_exists"] = vtt_p.exists()
            if vtt_p.exists():
                c_info["vtt_size"] = vtt_p.stat().st_size
                c_info["vtt_sha256"] = hashlib.sha256(vtt_p.read_bytes()).hexdigest()
                vtt_lines = vtt_p.read_text(encoding="utf-8").splitlines()
                c_info["vtt_line_count"] = len(vtt_lines)
                c_info["vtt_header_valid"] = len(vtt_lines) > 0 and "WEBVTT" in vtt_lines[0]
                
                # Parse and validate cues
                cue_timestamps = []
                for line in vtt_lines:
                    if "-->" in line:
                        parts = line.split("-->")
                        if len(parts) == 2:
                            cue_timestamps.append((parts[0].strip(), parts[1].strip().split()[0]))
                
                c_info["vtt_cue_count"] = len(cue_timestamps)
                c_info["vtt_cues_ordered"] = True
                c_info["vtt_cues_within_duration"] = True
                
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
                probed_dur = c_info.get("probed_duration", 999999.0)
                for start_s, end_s in cue_timestamps:
                    s_sec = _vtt_to_sec(start_s)
                    e_sec = _vtt_to_sec(end_s)
                    if s_sec < prev_end - 0.05 or e_sec < s_sec:
                        c_info["vtt_cues_ordered"] = False
                    if e_sec > probed_dur + 0.5:
                        c_info["vtt_cues_within_duration"] = False
                    prev_end = e_sec

            # Match highlight metadata
            if i <= len(result_shorts):
                s = result_shorts[i - 1]
                c_info["expected_start"] = s.get("start_time")
                c_info["expected_end"] = s.get("end_time")
                c_info["expected_duration"] = round(float(s.get("end_time", 0)) - float(s.get("start_time", 0)), 2)
                c_info["duration_delta"] = round(c_info.get("probed_duration", 0) - c_info["expected_duration"], 3)
                c_info["duration_within_tolerance"] = abs(c_info["duration_delta"]) <= 0.5
                c_info["title"] = s.get("title")
                c_info["hook_sentence"] = s.get("hook_sentence")
                c_info["virality_reason"] = s.get("virality_reason")
                c_info["score"] = s.get("score")

        clip_verifications.append(c_info)

    summary_data = {
        "run_type": "Video_2_Podcast_Verification_Run_Reuse_Audio",
        "job_id": job_id,
        "session_folder": session_folder,
        "pid": os.getpid(),
        "start_iso": start_iso,
        "end_iso": end_iso,
        "total_duration_seconds": total_duration,
        "in_memory_status": in_memory_status,
        "in_memory_stage": in_memory_stage,
        "worker_thread_alive": worker_thread_alive,
        "in_memory_active_ctx": in_memory_active_ctx,
        "in_memory_active_webapp": in_memory_active_webapp,
        "disk_meta_status": disk_meta_data.get("status"),
        "disk_meta_stage": disk_meta_data.get("stage"),
        "disk_meta_duration_seconds": disk_meta_data.get("duration_seconds"),
        "error": disk_meta_data.get("error"),
        "api_counters": api_counters,
        "logs": logs_captured,
        "clips_verified": clip_verifications,
    }

    out_job_summary = ROOT_DIR / VAL_OUTPUT_DIR / f"validation_v2_summary_{job_id}.json"
    out_job_summary.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    out_summary = ROOT_DIR / VAL_OUTPUT_DIR / "validation_v2_verification_summary.json"
    out_summary.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n>>> Video 2 summary saved to: {out_job_summary} and {out_summary}")
    return summary_data

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "--preflight":
        source_arg = sys.argv[1]
        lang_arg = sys.argv[2] if len(sys.argv) > 2 else "id"
        execute_video_2_validation(source_arg, language=lang_arg)
    else:
        run_preflight_check()
