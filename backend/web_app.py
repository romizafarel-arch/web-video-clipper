"""Web Application Server for AI YouTube Shorts Generator.

Provides a modern web interface for generating, viewing, and managing YouTube Shorts.
"""
import io
import json
import math
import os
import re
import shutil
import struct
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from dotenv import dotenv_values, set_key
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

# Force stdout/stderr UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import shorts_generator.config as cfg
from shorts_generator import cleanup_source_video, generate_shorts, report_error_to_reef_flow
from shorts_generator.job_manager import (
    JobConflictError,
    JobCancelledException,
    JobContext,
    JobStatus,
    JobTimeoutException,
    job_manager,
    mask_sensitive_keys,
)
from shorts_generator.agnes import (
    AGNES_ASPECT_RATIOS,
    AGNES_SIZES,
    AGNES_VIDEO_MODELS,
    agnes_chat,
    generate_video_to_file,
)
from shorts_generator.idea_planner import generate_directions, generate_plan
from shorts_generator.local.llm import call_gemini_llm, call_local_llm, call_openai_llm

app = Flask(__name__, template_folder="templates", static_folder="static")

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
OUTPUT_DIR = BASE_DIR / cfg.LOCAL_OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR = BASE_DIR / "assets" / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_FONT_EXTENSIONS = {".ttf", ".otf"}

# Recover any jobs that were interrupted when the server stopped/restarted
try:
    _recovered = job_manager.recover_interrupted_jobs(OUTPUT_DIR)
    if _recovered > 0:
        print(f"[boot] Pulihkan {_recovered} status pekerjaan yang terputus saat aplikasi dihentikan.", flush=True)
except Exception:
    pass

# In-memory jobs store and execution lock
jobs: Dict[str, Dict[str, Any]] = {}
generation_lock = threading.Lock()


def get_active_job() -> Optional[Dict[str, Any]]:
    """Return the currently active job if any (queued, running, or canceling)."""
    active_ctx = job_manager.get_active_job()
    if active_ctx:
        d = active_ctx.to_dict()
        d["job_id"] = active_ctx.job_id
        jobs[active_ctx.job_id] = d
        return d
    for j_id, j in jobs.items():
        if j.get("status") in JobStatus.ACTIVE_STATUSES:
            if "job_id" not in j:
                j["job_id"] = j_id
            return j
    return None


ALLOWED_MEDIA_EXTENSIONS = {".mp4", ".vtt", ".srt", ".webm", ".jpg", ".jpeg", ".png", ".mov", ".mkv"}

# Per-clip and per-session lock management for safe concurrent editorial re-rendering
_clip_locks: Dict[str, threading.Lock] = {}
_clip_locks_guard = threading.Lock()

_session_locks: Dict[str, threading.Lock] = {}
_session_locks_guard = threading.Lock()


def get_clip_lock(session_folder: str, clip_index: int) -> threading.Lock:
    """Return or create a thread lock dedicated to a specific session clip."""
    lock_key = f"{session_folder}:{clip_index}"
    with _clip_locks_guard:
        if lock_key not in _clip_locks:
            _clip_locks[lock_key] = threading.Lock()
        return _clip_locks[lock_key]


def get_session_lock(session_folder: str) -> threading.Lock:
    """Return or create a thread lock dedicated to metadata commits for an entire session."""
    with _session_locks_guard:
        if session_folder not in _session_locks:
            _session_locks[session_folder] = threading.Lock()
        return _session_locks[session_folder]


class SessionGate:
    """Coordinates editorial operations and session deletion without race windows."""

    def __init__(self):
        self._lock = threading.RLock()
        self._active_editors: Dict[str, List[int]] = {}
        self._deleting_sessions: Set[str] = set()

    def register_editor_start(self, folder_name: str, clip_index: int) -> Tuple[bool, Optional[str]]:
        """Register that clip editing is starting. Returns False if session is currently being deleted."""
        with self._lock:
            if folder_name in self._deleting_sessions:
                return False, "Sesi sedang dalam proses penghapusan atau telah dihapus."
            if folder_name not in self._active_editors:
                self._active_editors[folder_name] = []
            self._active_editors[folder_name].append(clip_index)
            return True, None

    def unregister_editor_done(self, folder_name: str, clip_index: int) -> None:
        """Unregister clip editing upon completion or failure."""
        with self._lock:
            if folder_name in self._active_editors:
                try:
                    self._active_editors[folder_name].remove(clip_index)
                except ValueError:
                    pass
                if not self._active_editors[folder_name]:
                    del self._active_editors[folder_name]

    def acquire_deletion_gate(self, folder_name: str) -> Tuple[bool, Optional[str]]:
        """Atomically enter deletion state. Rejects if active editors are currently rendering."""
        with self._lock:
            if folder_name in self._deleting_sessions:
                return False, "Sesi sedang dalam proses penghapusan."
            if folder_name in self._active_editors and len(self._active_editors[folder_name]) > 0:
                clips = sorted(list(set(self._active_editors[folder_name])))
                clips_str = ", ".join(f"#{c}" for c in clips)
                return False, f"Sesi tidak dapat dihapus karena klip ({clips_str}) sedang dalam proses render."
            self._deleting_sessions.add(folder_name)
            return True, None

    def release_deletion_gate(self, folder_name: str) -> None:
        with self._lock:
            self._deleting_sessions.discard(folder_name)

    def purge_session(self, folder_name: str) -> None:
        with self._lock:
            self._active_editors.pop(folder_name, None)
            self._deleting_sessions.discard(folder_name)


session_gate = SessionGate()


def _persist_job_metadata(job_ctx: JobContext, extra: Optional[Dict[str, Any]] = None) -> None:
    """Atomically commit current job metadata to session folder under session lock."""
    session_folder = getattr(job_ctx, "session_folder", None)
    if not session_folder:
        return
    job_dir = OUTPUT_DIR / session_folder
    job_dir.mkdir(parents=True, exist_ok=True)
    with get_session_lock(session_folder):
        meta_path = job_dir / f"job_{job_ctx.job_id}.json"
        existing_data: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except Exception:
                pass

        params = getattr(job_ctx, "params", {}) or {}
        safe_config = mask_sensitive_keys(params.get("config") if isinstance(params, dict) else {})
        meta_data = {
            **existing_data,
            "job_id": job_ctx.job_id,
            "session_folder": session_folder,
            "status": job_ctx.status,
            "stage": job_ctx.stage,
            "created_at": datetime.fromtimestamp(job_ctx.created_at).isoformat() if job_ctx.created_at else None,
            "started_at": datetime.fromtimestamp(job_ctx.started_at).isoformat() if job_ctx.started_at else None,
            "ended_at": datetime.fromtimestamp(job_ctx.ended_at).isoformat() if job_ctx.ended_at else None,
            "duration_seconds": round((job_ctx.ended_at or time.time()) - (job_ctx.started_at or job_ctx.created_at), 2),
            "url": getattr(job_ctx, "url", "") or params.get("url", ""),
            "config": safe_config or existing_data.get("config"),
            "error": job_ctx.error,
            "cancel_reason": job_ctx.cancel_reason,
            "aspect_ratio": params.get("aspect_ratio", "9:16"),
            "result": job_ctx.result if job_ctx.result is not None else existing_data.get("result"),
        }
        if extra:
            meta_data.update(extra)

        tmp_meta = job_dir / f".tmp_job_{job_ctx.job_id}.json"
        with open(tmp_meta, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2, ensure_ascii=False)
        tmp_meta.replace(meta_path)


def probe_media_duration(source_path: str) -> Optional[float]:
    """Probe ground-truth media duration using OpenCV VideoCapture."""
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(str(source_path))
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            cap.release()
            if fps > 0 and frame_count > 0:
                dur = float(frame_count / fps)
                if math.isfinite(dur) and dur > 0:
                    return dur
    except Exception:
        pass
    return None


def verify_rendered_video(
    video_path: Path,
    expected_duration: Optional[float] = None,
    min_duration: float = 0.5,
) -> None:
    """Verify that a rendered staging video file is a valid, non-empty, decodable MP4 media file."""
    if not video_path.exists():
        raise RuntimeError("File hasil render tidak ditemukan.")
    size = video_path.stat().st_size
    if size < 1024:
        raise RuntimeError(f"Ukuran file hasil render terlalu kecil ({size} bytes).")

    try:
        import cv2  # type: ignore
    except ImportError as e:
        raise RuntimeError(f"Decoder OpenCV tidak tersedia untuk verifikasi media: {e}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("Hasil render tidak dapat dibuka sebagai video oleh decoder OpenCV.")

    try:
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0

        if w <= 0 or h <= 0:
            raise RuntimeError(f"Dimensi video tidak valid ({w}x{h}).")
        if fps <= 0 or frame_count <= 0:
            raise RuntimeError(f"FPS ({fps}) atau frame count ({frame_count}) tidak valid.")

        dur = frame_count / fps
        if dur < min_duration:
            raise RuntimeError(f"Durasi video ({dur:.2f}s) lebih pendek dari batas minimum {min_duration}s.")

        if expected_duration is not None and expected_duration > 0:
            # Frame-period and pipeline-measured tolerance: allows small rounding/muxing skews (<= 3 frames or 0.25s), strictly capped at 0.5s
            frame_period = 1.0 / fps if fps > 0 else 0.04
            allowed_tolerance = min(0.5, max(0.25, frame_period * 3.0))
            if abs(dur - expected_duration) > allowed_tolerance:
                raise RuntimeError(
                    f"Durasi fisik video hasil render ({dur:.2f}s) tidak sesuai dengan durasi rentang yang diminta ({expected_duration:.2f}s, toleransi ±{allowed_tolerance:.2f}s)."
                )

        # 1. Decode first frame
        ret, frame = cap.read()
        if not ret or frame is None:
            raise RuntimeError("Frame pertama video tidak dapat didecode.")

        # 2. Decode frame near the end to ensure the entire stream is intact
        if frame_count > 2:
            target_end_frame = max(0, int(frame_count) - 2)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_end_frame)
            ret_end, frame_end = cap.read()
            if not ret_end or frame_end is None:
                raise RuntimeError("Frame akhir video tidak dapat didecode (kemungkinan file terpotong/truncated).")
    finally:
        cap.release()


def resolve_session_source(session_folder: str) -> Tuple[Optional[str], Optional[dict], Optional[str]]:
    """Resolve the source video path and metadata for a given session folder.

    Returns (source_path, job_data, error_msg).
    Strictly isolates source resolution: never picks arbitrary files from root OUTPUT_DIR.
    """
    session_folder = str(session_folder or "").strip()
    if not session_folder or ".." in session_folder or "/" in session_folder or "\\" in session_folder:
        return None, None, "Folder sesi tidak valid."

    target_dir = (OUTPUT_DIR / session_folder).resolve()
    try:
        target_dir.relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return None, None, "Folder sesi tidak ditemukan atau akses ditolak."
    if not target_dir.exists() or target_dir == OUTPUT_DIR.resolve():
        return None, None, "Folder sesi tidak ditemukan atau akses ditolak."

    job_data = None
    source_path = None
    job_jsons = list(target_dir.glob("job_*.json"))
    if job_jsons:
        try:
            with open(job_jsons[0], "r", encoding="utf-8") as f:
                job_data = json.load(f)
        except Exception:
            pass

    if job_data:
        # 1. Check result.source_video_url (supports local files outside session folder)
        res_data = job_data.get("result") if isinstance(job_data.get("result"), dict) else {}
        src_url = res_data.get("source_video_url") or job_data.get("source_video_url")
        if src_url and isinstance(src_url, str):
            p = Path(src_url)
            if p.exists() and p.is_file():
                source_path = str(p.resolve())
        # 2. Check url field if it was a local file path
        if not source_path:
            url_field = job_data.get("url")
            if url_field and isinstance(url_field, str):
                p = Path(url_field)
                if p.exists() and p.is_file():
                    source_path = str(p.resolve())

    # 3. Check inside target_dir only (never look in root OUTPUT_DIR)
    if not source_path:
        candidates = list(target_dir.glob("source_*.*"))
        for c in candidates:
            if c.is_file() and c.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS:
                source_path = str(c.resolve())
                break

    if not source_path or not os.path.exists(source_path):
        return None, job_data, "File video sumber untuk sesi ini tidak ditemukan atau telah dipindahkan."

    return source_path, job_data, None


def _collect_and_verify_completed_shorts(
    job_ctx: JobContext,
    session_folder: Optional[str],
    job_dir: Optional[Path],
    pipeline_result: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Retrieve only truly completed and verified video clips with complete metadata (B-04)."""
    valid_shorts: List[Dict[str, Any]] = []
    seen_filenames: Set[str] = set()

    # 1. Candidate completed shorts strictly from job_ctx.completed_shorts or pipeline_result["shorts"]
    candidates: List[Dict[str, Any]] = []
    if hasattr(job_ctx, "completed_shorts") and job_ctx.completed_shorts:
        for cs in job_ctx.completed_shorts:
            if cs not in candidates:
                candidates.append(cs)
    if pipeline_result and isinstance(pipeline_result, dict):
        for ps in (pipeline_result.get("shorts", []) or []):
            if ps not in candidates:
                candidates.append(ps)

    # Highlights map for fallback metadata verification
    pipe_ctx = getattr(job_ctx, "pipeline_context", {}) or {}
    highlights_list = pipe_ctx.get("highlights", [])
    highlights_map: Dict[int, Dict[str, Any]] = {}
    for i, h in enumerate(highlights_list, 1):
        highlights_map[i] = h

    # Check candidates
    for c in candidates:
        clip_path = c.get("clip_url")
        if not clip_path:
            continue
        p = Path(clip_path)
        if not p.is_file():
            continue
        # Skip temporary, cut, silent or hidden files
        if ".cut." in p.name or ".silent." in p.name or p.name.startswith((".", "_")):
            continue

        item = dict(c)
        fname = p.name
        if fname in seen_filenames:
            continue

        m = re.match(r"^short_(\d+)\.mp4$", fname)
        c_idx = item.get("clip_index") or (int(m.group(1)) if m else 1)
        item["clip_index"] = c_idx

        # Trustworthy start_time and end_time
        h_match = highlights_map.get(c_idx, {})
        start_time = float(item.get("start_time") if item.get("start_time") is not None else h_match.get("start_time", 0.0))
        end_time = float(item.get("end_time") if item.get("end_time") is not None else h_match.get("end_time", 0.0))
        expected_dur = max(0.0, end_time - start_time) if end_time > start_time else None

        try:
            # Physical verification with Bagian A duration tolerance
            verify_rendered_video(p, expected_duration=expected_dur)
        except Exception:
            # Corrupted, truncated, or duration mismatch -> reject!
            continue

        seen_filenames.add(fname)
        item["filename"] = fname
        item["start_time"] = start_time
        item["end_time"] = end_time

        if session_folder:
            item["folder_name"] = session_folder
            item["web_url"] = f"/output/{session_folder}/{fname}"
            vtt_p = p.with_suffix(".vtt")
            if vtt_p.exists():
                item["vtt_url"] = f"/output/{session_folder}/{vtt_p.name}"
            elif "vtt_url" not in item:
                item["vtt_url"] = None

        if "title" not in item or not item["title"]:
            item["title"] = h_match.get("title") or f"Short #{c_idx}"
        if "hook_sentence" not in item:
            item["hook_sentence"] = h_match.get("hook_sentence") or ""

        valid_shorts.append(item)

    return sorted(valid_shorts, key=lambda s: int(s.get("clip_index", 0)))


def run_generation_job(job_id: str, params: Dict[str, Any]):
    """Background worker to run shorts generation with config isolation and strict completion validation."""
    with generation_lock:
        job_ctx = job_manager.get_job(job_id)
        if not job_ctx:
            job_ctx = JobContext(job_id=job_id, url=params.get("url", ""), params=params)
            job_manager._jobs[job_id] = job_ctx

        job_ctx.worker_thread = threading.current_thread()

        session_folder = params.get("session_folder") or job_ctx.session_folder
        if not session_folder:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_folder = f"{timestamp_str}_{job_id}"
        job_ctx.session_folder = session_folder
        job_dir = OUTPUT_DIR / session_folder

        result = None
        valid_shorts = []
        failed_shorts = []

        try:
            job_dir.mkdir(parents=True, exist_ok=True)

            # Check if job was cancelled while queued
            if job_ctx.status == JobStatus.CANCELED:
                jobs[job_id] = job_ctx.to_dict()
                try:
                    _persist_job_metadata(job_ctx)
                except Exception:
                    pass
                return

            job_ctx.transition_to(JobStatus.RUNNING, stage="downloading", progress=10)
            job_ctx.started_at = time.time()
            jobs[job_id] = job_ctx.to_dict()
            _persist_job_metadata(job_ctx)

            result = generate_shorts(
                youtube_url=params["url"],
                num_clips=params.get("num_clips", 3),
                aspect_ratio=params.get("aspect_ratio", "9:16"),
                download_format=params.get("format", "720"),
                language=params.get("language") or None,
                mode=params.get("mode", "local"),
                out_dir=str(job_dir),
                config=params.get("config"),
                job_ctx=job_ctx,
                framing_mode=params.get("framing_mode", "podcast"),
                subtitle_style=params.get("subtitle_style", "karaoke"),
                gaming_preset=params.get("gaming_preset", "discord_top_cam_bottom_right"),
                gaming_custom_box=params.get("gaming_custom_box"),
                gaming_layout=params.get("gaming_layout"),
                auto_delete_source_video=params.get("auto_delete_source_video"),
                font_family=params.get("font_family"),
                cookies_path=params.get("cookies_path"),
                enable_sfx=bool(params.get("enable_sfx", True)),
                remove_silence=bool(params.get("remove_silence", False)),
            )

            # Normalize clip paths to web-accessible URLs
            target_aspect_ratio = params.get("aspect_ratio", "9:16")
            target_font_family = params.get("font_family")
            shorts = result.get("shorts", []) if isinstance(result, dict) else []
            for short in shorts:
                short.setdefault("aspect_ratio", target_aspect_ratio)
                if target_font_family:
                    short.setdefault("font_family", target_font_family)
                clip_path = short.get("clip_url")
                if clip_path and not str(clip_path).startswith("http"):
                    filename = Path(clip_path).name
                    short["web_url"] = f"/output/{session_folder}/{filename}"
                    short["filename"] = filename
                    short["folder_name"] = session_folder
                    vtt_name = Path(clip_path).stem + ".vtt"
                    if (job_dir / vtt_name).exists():
                        short["vtt_url"] = f"/output/{session_folder}/{vtt_name}"
                    valid_shorts.append(short)
                elif clip_path and str(clip_path).startswith("http"):
                    short["web_url"] = clip_path
                    valid_shorts.append(short)
                else:
                    failed_shorts.append(short)

            stats = {
                "total": len(shorts),
                "success": len(valid_shorts),
                "failed": len(failed_shorts),
            }
            if isinstance(result, dict):
                result["stats"] = stats
                result["aspect_ratio"] = target_aspect_ratio

            # Determine job outcome status truthfully (B-04)
            if not shorts or len(shorts) == 0:
                err_text = "Tidak ada klip video yang berhasil dibuat oleh AI."
                job_ctx.transition_to(JobStatus.FAILED, stage="failed", progress=100, error=err_text, result=result)
                report_error_to_reef_flow(
                    title=f"[Worker Gagal] AI tidak menghasilkan klip (Job {job_id})",
                    description=f"Job ID: {job_id}\nURL: {params.get('url')}\nError: {err_text}",
                    priority="HIGH",
                )
            elif len(valid_shorts) == 0:
                errors = [s.get("error") for s in failed_shorts if s.get("error")]
                error_msg = "; ".join(errors[:2]) if errors else "Semua proses pemotongan klip video gagal."
                err_text = f"Render gagal total: {error_msg}"
                job_ctx.transition_to(JobStatus.FAILED, stage="failed", progress=100, error=err_text, result=result)
                report_error_to_reef_flow(
                    title=f"[Worker Gagal] Render gagal total (Job {job_id})",
                    description=f"Job ID: {job_id}\nURL: {params.get('url')}\nDetail: {err_text}",
                    priority="URGENT",
                )
            elif len(failed_shorts) > 0:
                job_ctx.transition_to(JobStatus.PARTIAL, stage="partial", progress=100, error="Sebagian klip gagal dirender.", result=result)
            else:
                job_ctx.transition_to(JobStatus.COMPLETED, stage="completed", progress=100, result=result)

        except JobCancelledException as e:
            cancel_msg = str(e)
            job_ctx.emit_log(f"[INFO] Eksekusi dihentikan: {cancel_msg}")
            valid_shorts = _collect_and_verify_completed_shorts(
                job_ctx=job_ctx,
                session_folder=session_folder,
                job_dir=job_dir,
                pipeline_result=result,
            )
            if len(valid_shorts) > 0:
                total_expected = max(len(valid_shorts), params.get("num_clips", 0) or 0)
                res = {
                    "shorts": valid_shorts,
                    "stats": {
                        "total": total_expected,
                        "success": len(valid_shorts),
                        "failed": max(0, total_expected - len(valid_shorts)),
                    },
                }
                ctx_pipe = getattr(job_ctx, "pipeline_context", {}) or {}
                for k, v in ctx_pipe.items():
                    if k not in res:
                        res[k] = v
                job_ctx.transition_to(
                    JobStatus.PARTIAL,
                    stage="partial",
                    progress=100,
                    error=f"Sebagian klip selesai sebelum pembatalan: {cancel_msg}",
                    result=res,
                )
            else:
                res = {
                    "shorts": [],
                    "stats": {
                        "total": params.get("num_clips", 0) or 0,
                        "success": 0,
                        "failed": 0,
                    },
                }
                job_ctx.transition_to(
                    JobStatus.CANCELED,
                    stage="canceled",
                    progress=100,
                    error=cancel_msg,
                    result=res,
                )

        except JobTimeoutException as e:
            timeout_msg = str(e)
            job_ctx.emit_log(f"[ERROR] Batas waktu terlampaui: {timeout_msg}")
            valid_shorts = _collect_and_verify_completed_shorts(
                job_ctx=job_ctx,
                session_folder=session_folder,
                job_dir=job_dir,
                pipeline_result=result,
            )
            if len(valid_shorts) > 0:
                total_expected = max(len(valid_shorts), params.get("num_clips", 0) or 0)
                res = {
                    "shorts": valid_shorts,
                    "stats": {
                        "total": total_expected,
                        "success": len(valid_shorts),
                        "failed": max(0, total_expected - len(valid_shorts)),
                    },
                }
                ctx_pipe = getattr(job_ctx, "pipeline_context", {}) or {}
                for k, v in ctx_pipe.items():
                    if k not in res:
                        res[k] = v
                job_ctx.transition_to(
                    JobStatus.PARTIAL,
                    stage="partial",
                    progress=100,
                    error=f"Sebagian klip selesai sebelum batas waktu: {timeout_msg}",
                    result=res,
                )
            else:
                res = {
                    "shorts": [],
                    "stats": {
                        "total": params.get("num_clips", 0) or 0,
                        "success": 0,
                        "failed": 0,
                    },
                }
                job_ctx.transition_to(
                    JobStatus.TIMEOUT,
                    stage="timeout",
                    progress=100,
                    error=timeout_msg,
                    result=res,
                )

        except Exception as e:
            job_ctx.transition_to(
                JobStatus.FAILED,
                stage="failed",
                progress=100,
                error=str(e),
                result=result,
            )
            job_ctx.emit_log(f"[ERROR] Generation failed: {e}")
            import traceback
            report_error_to_reef_flow(
                title=f"[Worker Error] Job {job_id}: {str(e)[:80]}",
                description=f"Job ID: {job_id}\nURL: {params.get('url')}\nError: {e}\n\nStack Trace:\n{traceback.format_exc()}",
                priority="URGENT",
            )

        finally:
            # Purge temporary cookies file to prevent credential leaks
            cookies_p = params.get("cookies_path")
            if cookies_p:
                try:
                    cp = Path(cookies_p)
                    if cp.exists():
                        cp.unlink()
                except Exception:
                    pass

            if session_folder:
                try:
                    _persist_job_metadata(job_ctx)
                except Exception as e:
                    job_ctx.emit_log(f"[warning] Failed to save job metadata: {e}")

            jobs[job_id] = job_ctx.to_dict()


_monorepo_frontend = BASE_DIR.parent / "frontend" / "dist"
FRONTEND_DIST = _monorepo_frontend if _monorepo_frontend.exists() else (BASE_DIR / "frontend" / "dist")


@app.route("/")
def index():
    """Render main web app dashboard (React SPA if built, fallback to classic)."""
    if (FRONTEND_DIST / "index.html").exists():
        return send_from_directory(str(FRONTEND_DIST), "index.html")
    return render_template("index.html")


@app.route("/classic")
def classic_index():
    """Render classic legacy vanilla dashboard."""
    return render_template("index.html")


@app.route("/assets/<path:filename>")
def serve_frontend_assets(filename: str):
    """Serve built frontend assets (JS/CSS/images)."""
    if (FRONTEND_DIST / "assets").exists():
        return send_from_directory(str(FRONTEND_DIST / "assets"), filename)
    root_assets = Path(__file__).resolve().parent / "assets"
    if (root_assets / filename).exists():
        return send_from_directory(str(root_assets), filename)
    return jsonify({"error": "Asset not found"}), 404


def extract_font_name_from_ttf(file_path: Path) -> Tuple[str, str]:
    """Extract (family_name, full_name) from TTF/OTF 'name' table using pure standard library struct."""
    family = ""
    full = ""
    try:
        with open(file_path, "rb") as f:
            data = f.read(1024 * 1024)
        if len(data) >= 12:
            num_tables = struct.unpack(">H", data[4:6])[0]
            name_offset = 0
            for i in range(num_tables):
                tag = data[12 + i * 16 : 16 + i * 16]
                if tag == b"name":
                    name_offset = struct.unpack(">I", data[12 + i * 16 + 8 : 12 + i * 16 + 12])[0]
                    break
            if name_offset and name_offset < len(data):
                count, string_offset = struct.unpack(">HH", data[name_offset + 2 : name_offset + 6])
                storage = name_offset + string_offset
                for i in range(count):
                    rec = data[name_offset + 6 + i * 12 : name_offset + 6 + (i + 1) * 12]
                    plat, enc, lang, name_id, length, off = struct.unpack(">HHHHHH", rec)
                    if name_id in (1, 4):
                        raw = data[storage + off : storage + off + length]
                        try:
                            if plat == 3 or (plat == 0 and enc != 0):
                                val = raw.decode("utf-16-be").strip()
                            else:
                                val = raw.decode("latin1").strip()
                            if name_id == 1 and not family:
                                family = val
                            elif name_id == 4 and not full:
                                full = val
                        except Exception:
                            pass
    except Exception:
        pass
    if not family:
        stem = file_path.stem.replace("-", " ").replace("_", " ")
        family = stem
    if not full:
        full = family
    return family, full


@app.route("/api/fonts", methods=["GET"])
def api_list_fonts():
    """List available local bundled and uploaded fonts."""
    fonts = []
    if FONTS_DIR.exists():
        for font_file in sorted(FONTS_DIR.iterdir()):
            if font_file.is_file() and font_file.suffix.lower() in ALLOWED_FONT_EXTENSIONS:
                fam, full = extract_font_name_from_ttf(font_file)
                is_custom = font_file.stem.startswith("custom_")
                fonts.append({
                    "name": full or fam,
                    "family": fam,
                    "filename": font_file.name,
                    "url": f"/api/fonts/{font_file.name}",
                    "is_custom": is_custom,
                })
    return jsonify({"fonts": fonts})


@app.route("/api/fonts/<path:filename>", methods=["GET"])
def api_serve_font(filename: str):
    """Serve font file from FONTS_DIR with appropriate MIME type."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_FONT_EXTENSIONS:
        return jsonify({"error": "Format font tidak diizinkan."}), 403
    mimetype = "font/ttf" if ext == ".ttf" else "font/otf"
    return send_from_directory(str(FONTS_DIR), filename, mimetype=mimetype)


@app.route("/api/fonts/upload", methods=["POST"])
def api_upload_font():
    """Upload custom TTF or OTF font file directly to backend assets/fonts."""
    if "font_file" not in request.files:
        return jsonify({"error": "File font wajib diunggah (field: 'font_file')."}), 400

    uploaded = request.files["font_file"]
    if not uploaded.filename:
        return jsonify({"error": "Nama file font kosong."}), 400

    original_filename = secure_filename(uploaded.filename)
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_FONT_EXTENSIONS:
        return jsonify({"error": f"Ekstensi '{ext}' tidak didukung. Harap unggah file .ttf atau .otf."}), 400

    clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(original_filename).stem)[:40] or "custom_font"
    unique_filename = f"custom_{clean_stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest_path = FONTS_DIR / unique_filename

    try:
        uploaded.save(str(dest_path))
        if dest_path.stat().st_size > 25 * 1024 * 1024:
            dest_path.unlink()
            return jsonify({"error": "Ukuran file font melebihi batas 25MB."}), 400

        fam, full = extract_font_name_from_ttf(dest_path)
        return jsonify({
            "success": True,
            "font_name": full or fam,
            "family": fam,
            "filename": unique_filename,
            "url": f"/api/fonts/{unique_filename}",
            "message": f"Font '{full or fam}' berhasil diunggah dan dibundle ke backend.",
        })
    except Exception as e:
        if dest_path.exists():
            try:
                dest_path.unlink()
            except Exception:
                pass
        return jsonify({"error": f"Gagal menyimpan file font: {e}"}), 500




@app.route("/output/<path:filename>")
def serve_output(filename: str):
    """Serve output video files with support for Range requests and extension allowlist."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        return jsonify({"error": "Akses berkas tidak diizinkan"}), 403
    return send_from_directory(str(OUTPUT_DIR), filename, conditional=True)


@app.route("/api/session-source/<path:folder_name>")
def serve_session_source(folder_name: str):
    """Serve the verified source video for a specific session with Range support."""
    folder_name = folder_name.strip()
    if not folder_name:
        return jsonify({"error": "Nama folder sesi tidak boleh kosong."}), 400

    source_path, job_data, error_msg = resolve_session_source(folder_name)
    if error_msg:
        return jsonify({"error": error_msg}), 404

    ext = Path(source_path).suffix.lower()
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        return jsonify({"error": "Format berkas sumber tidak diizinkan."}), 403

    from flask import send_file
    return send_file(source_path, conditional=True)


def validate_and_sanitize_gaming_box(custom_box: Any) -> Optional[Dict[str, Any]]:
    """Validate and sanitize gaming bounding box coordinates (normalized 0.0-1.0 or pixel).
    
    Accepts keys:
    - 'facecam' or 'bottom': streamer webcam bounding box
    - 'gameplay' or 'mid': gameplay action zone bounding box
    - 'top': optional squad/discord cam strip
    
    Returns clean dictionary with standard keys or None if invalid.
    """
    if not isinstance(custom_box, dict) or not custom_box:
        return None

    def sanitize_sub(sub: Any) -> Optional[Dict[str, float]]:
        if not isinstance(sub, dict):
            return None
        try:
            x = float(sub.get("x", 0))
            y = float(sub.get("y", 0))
            w = float(sub.get("w", 0))
            h = float(sub.get("h", 0))
        except (ValueError, TypeError):
            return None

        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(w) and math.isfinite(h)):
            return None
        if w <= 0 or h <= 0 or x < 0 or y < 0:
            return None

        # Check if normalized 0.0..1.0
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0:
            x_c = max(0.0, min(0.98, x))
            y_c = max(0.0, min(0.98, y))
            w_c = max(0.02, min(1.0 - x_c, w))
            h_c = max(0.02, min(1.0 - y_c, h))
            return {"x": round(x_c, 4), "y": round(y_c, 4), "w": round(w_c, 4), "h": round(h_c, 4)}
        else:
            # Pixel values
            x_c = max(0.0, x)
            y_c = max(0.0, y)
            w_c = max(2.0, w)
            h_c = max(2.0, h)
            return {"x": round(x_c, 1), "y": round(y_c, 1), "w": round(w_c, 1), "h": round(h_c, 1)}

    clean_box: Dict[str, Any] = {}

    # Facecam / bottom
    bot_raw = custom_box.get("facecam") or custom_box.get("bottom")
    if bot_raw:
        sanitized_bot = sanitize_sub(bot_raw)
        if sanitized_bot:
            clean_box["bottom"] = sanitized_bot
            clean_box["facecam"] = sanitized_bot

    # Gameplay / mid
    mid_raw = custom_box.get("gameplay") or custom_box.get("mid")
    if mid_raw:
        sanitized_mid = sanitize_sub(mid_raw)
        if sanitized_mid:
            clean_box["mid"] = sanitized_mid
            clean_box["gameplay"] = sanitized_mid

    # Top strip (Discord / squad cam)
    top_raw = custom_box.get("top")
    if top_raw:
        sanitized_top = sanitize_sub(top_raw)
        if sanitized_top:
            clean_box["top"] = sanitized_top

    if not clean_box:
        return None

    return clean_box


@app.route("/api/detect-facecam", methods=["GET"])
def detect_facecam_api():
    """Analyze source video corners to automatically suggest facecam bounding box."""
    session_folder = request.args.get("session_folder", "").strip()
    if not session_folder:
        return jsonify({"error": "Parameter session_folder harus diisi."}), 400

    source_path, job_data, error_msg = resolve_session_source(session_folder)
    if error_msg or not source_path or not os.path.exists(source_path):
        return jsonify({"error": error_msg or "Video sumber tidak ditemukan untuk sesi ini."}), 404

    clip_start = 0.0
    clip_end = None
    clip_idx_str = request.args.get("clip_index")
    if clip_idx_str and clip_idx_str.isdigit():
        target_idx = int(clip_idx_str)
        if job_data:
            res_val = job_data.get("result")
            result_dict = res_val if isinstance(res_val, dict) else {}
            shorts_list = result_dict.get("shorts", [])
            for s in shorts_list:
                if isinstance(s, dict) and s.get("clip_index") == target_idx:
                    clip_start = float(s.get("start_time", 0.0))
                    clip_end = float(s.get("end_time", clip_start + 30.0))
                    break

    try:
        from shorts_generator.local.clipper import detect_facecam_candidate
        result = detect_facecam_candidate(
            video_path=source_path,
            clip_start=clip_start,
            clip_end=clip_end,
            num_samples=5,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "detected": False,
            "confidence": "low",
            "confidence_score": 0.0,
            "corner": "bottom_right",
            "box": {"x": 0.74, "y": 0.63, "w": 0.26, "h": 0.37},
            "message": f"Deteksi otomatis gagal ({e}). Silakan gunakan preset atau atur kotak secara manual.",
        })


@app.route("/api/config", methods=["GET"])
def get_config():
    """Return sanitized current configuration."""
    def mask_key(k: str) -> str:
        if not k:
            return ""
        if len(k) <= 8:
            return "••••••••"
        return f"{k[:4]}••••••••{k[-4:]}"

    return jsonify({
        "mode_default": "local",
        "llm_provider": cfg.LLM_PROVIDER,
        "transcriber_provider": cfg.TRANSCRIBER_PROVIDER,
        "gemini_model": cfg.GEMINI_MODEL,
        "gemini_transcriber_model": getattr(cfg, "GEMINI_TRANSCRIBER_MODEL", "gemini-3.5-transcribe"),
        "openai_model": cfg.OPENAI_MODEL,
        "openai_base_url": cfg.OPENAI_BASE_URL or "",
        "whisper_model": cfg.LOCAL_WHISPER_MODEL,
        "job_timeout_seconds": getattr(cfg, "JOB_TIMEOUT_SECONDS", 1800.0),
        "auto_delete_source_video": getattr(cfg, "AUTO_DELETE_SOURCE_VIDEO", True),
        "has_gemini_key": bool(cfg.GEMINI_API_KEY and cfg.GEMINI_API_KEY != "your_gemini_key_here"),
        "has_openai_key": bool(cfg.OPENAI_API_KEY and cfg.OPENAI_API_KEY != "your_openai_key_here" and cfg.OPENAI_API_KEY != "your_apmix_or_openai_key_here"),
        "has_muapi_key": bool(cfg.MUAPI_API_KEY and cfg.MUAPI_API_KEY != "your_muapi_key_here"),
        "has_agnes_key": bool(cfg.AGNES_API_KEY and cfg.AGNES_API_KEY != "your_agnes_key_here"),
        "agnes_base_url": getattr(cfg, "AGNES_BASE_URL", "https://apihub.agnes-ai.com"),
        "agnes_video_model": getattr(cfg, "AGNES_VIDEO_MODEL", "agnes-video-2.5-flash"),
        "gemini_key_masked": mask_key(cfg.GEMINI_API_KEY),
        "openai_key_masked": mask_key(cfg.OPENAI_API_KEY),
        "muapi_key_masked": mask_key(cfg.MUAPI_API_KEY),
        "agnes_key_masked": mask_key(cfg.AGNES_API_KEY),
    })


# --- Dynamic Model Loading & Testing ---

_models_cache: Dict[str, Any] = {}


def get_gemini_models(force_refresh: bool = False) -> Dict[str, Any]:
    global _models_cache
    if not force_refresh and "gemini" in _models_cache:
        return _models_cache["gemini"]

    key = cfg.GEMINI_API_KEY
    if not key or key == "your_gemini_key_here":
        return {
            "success": False,
            "error": "GEMINI_API_KEY belum disetel. Silakan isi API key di menu Pengaturan.",
            "models": [
                {"id": "gemini-3.5-flash", "name": "gemini-3.5-flash (Default Cepat)", "recommended": True},
                {"id": "gemini-2.5-flash", "name": "gemini-2.5-flash (Stabil)", "recommended": True},
                {"id": "gemini-2.5-pro", "name": "gemini-2.5-pro (Kreativitas Tinggi)", "recommended": False},
                {"id": "gemini-flash-latest", "name": "gemini-flash-latest", "recommended": False},
            ],
            "transcribe_models": [
                {"id": "gemini-3.5-transcribe", "name": "gemini-3.5-transcribe (Audio to Text)", "recommended": True},
                {"id": "gemini-2.5-flash", "name": "gemini-2.5-flash", "recommended": False},
            ],
            "raw_count": 0,
        }

    try:
        from google import genai
        client = genai.Client(api_key=key)
        raw_list = client.models.list()

        all_models = []
        highlight_models = []
        transcribe_models = []

        seen_highlights = set()
        seen_transcribers = set()

        for m in raw_list:
            raw_name = getattr(m, "name", "") or ""
            model_id = raw_name.replace("models/", "")
            display_name = getattr(m, "display_name", "") or model_id
            all_models.append(model_id)

            lower = model_id.lower()
            # Highlights
            if any(k in lower for k in ["flash", "pro", "gemini-3", "gemini-2"]) and not any(k in lower for k in ["tts", "embedding", "image", "vision", "robotics"]):
                if model_id not in seen_highlights:
                    seen_highlights.add(model_id)
                    highlight_models.append({
                        "id": model_id,
                        "name": f"{model_id} ({display_name})" if display_name and display_name != model_id else model_id,
                        "recommended": model_id in ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"],
                    })

            # Transcribers
            if "transcribe" in lower or any(k in lower for k in ["flash", "pro"]):
                if model_id not in seen_transcribers:
                    seen_transcribers.add(model_id)
                    transcribe_models.append({
                        "id": model_id,
                        "name": f"{model_id} ({display_name})" if display_name and display_name != model_id else model_id,
                        "recommended": "transcribe" in lower,
                    })

        preset_transcribers = ["gemini-3.5-transcribe", "gemini-2.5-flash", "gemini-1.5-flash"]
        for pt in preset_transcribers:
            if pt not in seen_transcribers:
                transcribe_models.insert(0, {
                    "id": pt,
                    "name": f"{pt} (Audio Speech-to-Text)" if "transcribe" in pt else pt,
                    "recommended": "transcribe" in pt,
                })
                seen_transcribers.add(pt)

        highlight_models.sort(key=lambda x: (not x.get("recommended", False), x["id"]))
        transcribe_models.sort(key=lambda x: (not x.get("recommended", False), x["id"]))

        result = {
            "success": True,
            "provider": "gemini",
            "models": highlight_models,
            "transcribe_models": transcribe_models,
            "raw_count": len(all_models),
        }
        _models_cache["gemini"] = result
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "models": [
                {"id": "gemini-3.5-flash", "name": "gemini-3.5-flash (Default)", "recommended": True},
                {"id": "gemini-2.5-flash", "name": "gemini-2.5-flash", "recommended": True},
                {"id": "gemini-2.5-pro", "name": "gemini-2.5-pro", "recommended": False},
            ],
            "transcribe_models": [
                {"id": "gemini-3.5-transcribe", "name": "gemini-3.5-transcribe", "recommended": True},
                {"id": "gemini-2.5-flash", "name": "gemini-2.5-flash", "recommended": False},
            ],
            "raw_count": 0,
        }


def get_openai_models(force_refresh: bool = False) -> Dict[str, Any]:
    global _models_cache
    if not force_refresh and "openai" in _models_cache:
        return _models_cache["openai"]

    key = cfg.OPENAI_API_KEY
    if not key or key in ["your_openai_key_here", "your_apmix_or_openai_key_here"]:
        return {
            "success": False,
            "error": "OPENAI_API_KEY belum disetel. Silakan isi API key di menu Pengaturan.",
            "models": [
                {"id": "gpt-4o-mini", "name": "gpt-4o-mini (Default)", "recommended": True},
                {"id": "gpt-4o", "name": "gpt-4o", "recommended": True},
            ],
            "raw_count": 0,
        }

    try:
        from openai import OpenAI
        kwargs = {"api_key": key}
        if cfg.OPENAI_BASE_URL:
            kwargs["base_url"] = cfg.OPENAI_BASE_URL
        client = OpenAI(**kwargs)
        resp = client.models.list()

        models = []
        for m in getattr(resp, "data", []):
            model_id = getattr(m, "id", "") or str(m)
            models.append({
                "id": model_id,
                "name": model_id,
                "recommended": any(k in model_id.lower() for k in ["gpt-4", "flash", "chat", "claude", "deepseek"]),
            })

        models.sort(key=lambda x: (not x.get("recommended", False), x["id"]))
        result = {
            "success": True,
            "provider": "openai",
            "models": models,
            "raw_count": len(models),
        }
        _models_cache["openai"] = result
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "models": [
                {"id": "gpt-4o-mini", "name": "gpt-4o-mini", "recommended": True},
                {"id": "gpt-4o", "name": "gpt-4o", "recommended": True},
            ],
            "raw_count": 0,
        }


def get_whisper_models() -> Dict[str, Any]:
    whisper_models = [
        {"id": "base", "name": "base (~74M) • Seimbang & Cepat (Rekomendasi Default)", "recommended": True},
        {"id": "tiny", "name": "tiny (~39M) • Paling Cepat & Sangat Ringan", "recommended": False},
        {"id": "small", "name": "small (~244M) • Akurasi Tinggi", "recommended": False},
        {"id": "medium", "name": "medium (~769M) • Multilingual Expert", "recommended": False},
        {"id": "large-v3-turbo", "name": "large-v3-turbo (~809M) • Cepat & Presisi Maksimal", "recommended": True},
        {"id": "large-v3", "name": "large-v3 (~1550M) • Kualitas Tertinggi", "recommended": False},
    ]
    return {
        "success": True,
        "provider": "whisper",
        "models": whisper_models,
        "raw_count": len(whisper_models),
    }


@app.route("/api/models", methods=["GET"])
def api_get_models():
    """Retrieve available models from API for Gemini, OpenAI, or Whisper."""
    provider = request.args.get("provider", "").strip().lower()
    refresh = request.args.get("refresh", "false").strip().lower() == "true"

    if provider == "gemini":
        return jsonify(get_gemini_models(force_refresh=refresh))
    elif provider == "openai":
        return jsonify(get_openai_models(force_refresh=refresh))
    elif provider == "whisper":
        return jsonify(get_whisper_models())
    else:
        # Return all
        return jsonify({
            "gemini": get_gemini_models(force_refresh=refresh),
            "openai": get_openai_models(force_refresh=refresh),
            "whisper": get_whisper_models(),
            "active": {
                "llm_provider": cfg.LLM_PROVIDER,
                "gemini_model": cfg.GEMINI_MODEL,
                "openai_model": cfg.OPENAI_MODEL,
                "transcriber_provider": cfg.TRANSCRIBER_PROVIDER,
                "gemini_transcriber_model": getattr(cfg, "GEMINI_TRANSCRIBER_MODEL", "gemini-3.5-transcribe"),
                "whisper_model": cfg.LOCAL_WHISPER_MODEL,
            },
        })


@app.route("/api/models/test", methods=["POST"])
def api_test_model():
    """Test ping a model to verify connection, credentials, and response latency."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Payload harus berupa objek JSON yang valid"}), 400

    raw_provider = data.get("provider", "gemini")
    if not isinstance(raw_provider, str):
        return jsonify({"success": False, "error": "Provider harus berupa teks"}), 400
    provider = raw_provider.strip().lower()

    raw_model = data.get("model")
    if not isinstance(raw_model, str) or not raw_model.strip():
        return jsonify({"success": False, "error": "Nama model wajib diisi"}), 400
    model_name = raw_model.strip()

    t0 = time.time()
    try:
        if provider == "gemini":
            from google import genai
            key = cfg.require_gemini_key()
            client = genai.Client(api_key=key)
            norm_model = model_name[7:] if model_name.startswith("models/") else model_name
            resp = client.models.generate_content(
                model=norm_model,
                contents="Ping. Reply with: OK",
                config={"max_output_tokens": 10, "temperature": 0.1},
            )
            elapsed_ms = int((time.time() - t0) * 1000)
            text = (resp.text or "").strip()
            return jsonify({
                "success": True,
                "provider": "gemini",
                "model": norm_model,
                "latency_ms": elapsed_ms,
                "reply": text,
                "message": f"Model {norm_model} online! Latensi: {elapsed_ms}ms",
            })

        elif provider == "openai":
            from openai import OpenAI
            key = cfg.require_openai_key()
            kwargs = {"api_key": key}
            if cfg.OPENAI_BASE_URL:
                kwargs["base_url"] = cfg.OPENAI_BASE_URL
            client = OpenAI(**kwargs)
            resp = client.chat.completions.create(
                model=model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "Ping. Reply with: OK"}],
            )
            elapsed_ms = int((time.time() - t0) * 1000)
            text = (resp.choices[0].message.content or "").strip()
            return jsonify({
                "success": True,
                "provider": "openai",
                "model": model_name,
                "latency_ms": elapsed_ms,
                "reply": text,
                "message": f"Model {model_name} online! Latensi: {elapsed_ms}ms",
            })

        elif provider == "whisper":
            valid_whisper_models = {
                "tiny", "tiny.en", "base", "base.en", "small", "small.en",
                "medium", "medium.en", "large", "large-v1", "large-v2", "large-v3",
                "large-v3-turbo", "turbo",
            }
            norm_name = model_name.strip().lower()
            is_valid_name = norm_name in valid_whisper_models or os.path.isdir(model_name)
            if not is_valid_name:
                return jsonify({
                    "success": False,
                    "provider": "whisper",
                    "model": model_name,
                    "latency_ms": 0,
                    "error": f"Model '{model_name}' bukan nama model Faster-Whisper yang valid (contoh: base, small, large-v3-turbo).",
                }), 200

            try:
                import faster_whisper  # type: ignore
            except ImportError:
                return jsonify({
                    "success": False,
                    "provider": "whisper",
                    "model": model_name,
                    "latency_ms": 0,
                    "error": "Paket faster-whisper belum terpasang di sistem. Jalankan: pip install -r requirements-local.txt",
                }), 200

            return jsonify({
                "success": True,
                "provider": "whisper",
                "model": model_name,
                "latency_ms": 0,
                "message": f"Model Faster-Whisper '{model_name}' valid & pustaka terpasang!",
            })
        else:
            return jsonify({"success": False, "error": f"Provider '{provider}' tidak dikenal"}), 400
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return jsonify({
            "success": False,
            "provider": provider,
            "model": model_name,
            "latency_ms": elapsed_ms,
            "error": str(e),
        }), 200


@app.route("/api/config", methods=["POST"])
def update_config():
    """Update settings and persist to .env."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Payload konfigurasi harus berupa objek JSON yang valid."}), 400

    allowed_keys = [
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_TRANSCRIBER_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "LLM_PROVIDER",
        "TRANSCRIBER_PROVIDER",
        "LOCAL_WHISPER_MODEL",
        "MUAPI_API_KEY",
        "AGNES_API_KEY",
        "AGNES_BASE_URL",
        "AGNES_VIDEO_MODEL",
        "JOB_TIMEOUT_SECONDS",
        "AUTO_DELETE_SOURCE_VIDEO",
    ]

    # Pre-validate all configuration updates before writing .env or mutating in-memory config
    for k, v in data.items():
        if k in allowed_keys:
            if k == "AUTO_DELETE_SOURCE_VIDEO":
                if not isinstance(v, (bool, str, int)):
                    return jsonify({"error": f"Nilai untuk pengaturan '{k}' harus berupa boolean atau teks."}), 400
            elif k == "JOB_TIMEOUT_SECONDS":
                if v is not None and not isinstance(v, (int, float, str)):
                    return jsonify({"error": f"Nilai untuk pengaturan '{k}' harus berupa angka."}), 400
            elif v is not None and not isinstance(v, str):
                return jsonify({"error": f"Nilai untuk pengaturan '{k}' harus berupa teks."}), 400
            if k == "LLM_PROVIDER" and v is not None:
                norm_llm = str(v).strip().lower()
                if norm_llm not in ("gemini", "openai"):
                    return jsonify({"error": f"LLM provider '{norm_llm}' tidak valid. Pilihan: gemini, openai."}), 400
            if k == "TRANSCRIBER_PROVIDER" and v is not None:
                norm_tp = str(v).strip().lower()
                if norm_tp not in ("gemini", "whisper"):
                    return jsonify({"error": f"Transcriber provider '{norm_tp}' tidak valid. Pilihan: gemini, whisper."}), 400

    for k in allowed_keys:
        if k in data and data[k] is not None:
            if k == "AUTO_DELETE_SOURCE_VIDEO":
                raw_v = data[k]
                if isinstance(raw_v, bool):
                    val = "true" if raw_v else "false"
                else:
                    val = "true" if str(raw_v).strip().lower() in ("true", "1", "yes") else "false"
                set_key(str(ENV_PATH), k, val)
                os.environ[k] = val
                cfg.AUTO_DELETE_SOURCE_VIDEO = (val == "true")
                continue

            val = str(data[k]).strip()
            # If masked value sent back unchanged, skip
            if "••••" in val:
                continue
            set_key(str(ENV_PATH), k, val)
            os.environ[k] = val

            # Dynamically update cfg variables in memory
            if hasattr(cfg, k):
                if k == "JOB_TIMEOUT_SECONDS":
                    try:
                        setattr(cfg, k, float(val))
                    except ValueError:
                        pass
                else:
                    setattr(cfg, k, val)

    # Re-normalize special config attributes
    cfg.LLM_PROVIDER = os.getenv("LLM_PROVIDER", getattr(cfg, "LLM_PROVIDER", "gemini")).strip().lower()
    cfg.TRANSCRIBER_PROVIDER = os.getenv("TRANSCRIBER_PROVIDER", getattr(cfg, "TRANSCRIBER_PROVIDER", "gemini")).strip().lower()
    cfg.GEMINI_MODEL = os.getenv("GEMINI_MODEL", getattr(cfg, "GEMINI_MODEL", "gemini-3.5-flash")).strip()
    cfg.GEMINI_TRANSCRIBER_MODEL = os.getenv("GEMINI_TRANSCRIBER_MODEL", getattr(cfg, "GEMINI_TRANSCRIBER_MODEL", "gemini-3.5-transcribe")).strip()
    cfg.OPENAI_MODEL = os.getenv("OPENAI_MODEL", getattr(cfg, "OPENAI_MODEL", "gpt-4o-mini")).strip()
    cfg.LOCAL_WHISPER_MODEL = os.getenv("LOCAL_WHISPER_MODEL", getattr(cfg, "LOCAL_WHISPER_MODEL", "base")).strip()
    cfg.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
    cfg.AGNES_BASE_URL = (os.getenv("AGNES_BASE_URL", getattr(cfg, "AGNES_BASE_URL", "https://apihub.agnes-ai.com")) or "https://apihub.agnes-ai.com").strip().rstrip("/")
    cfg.AGNES_VIDEO_MODEL = (os.getenv("AGNES_VIDEO_MODEL", getattr(cfg, "AGNES_VIDEO_MODEL", "agnes-video-2.5-flash")) or "agnes-video-2.5-flash").strip()
    try:
        cfg.JOB_TIMEOUT_SECONDS = float(os.getenv("JOB_TIMEOUT_SECONDS", getattr(cfg, "JOB_TIMEOUT_SECONDS", 7200.0)))
    except (ValueError, TypeError):
        cfg.JOB_TIMEOUT_SECONDS = 7200.0
    cfg.AUTO_DELETE_SOURCE_VIDEO = os.getenv("AUTO_DELETE_SOURCE_VIDEO", "true").strip().lower() in ("true", "1", "yes")

    # Clear cache so fresh models can load
    _models_cache.clear()

    return jsonify({"success": True, "message": "Pengaturan & pilihan model berhasil disimpan!"})


def _idea_request_data():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Isi permintaan tidak terbaca."}), 400)

    idea = data.get("idea")
    goal = data.get("goal", "informasi")
    tone = data.get("tone", "santai")
    duration = data.get("duration", 30)
    if not isinstance(idea, str) or not idea.strip() or len(idea.strip()) > 1000:
        return None, (jsonify({"error": "Tulis ide maksimal 1.000 karakter."}), 400)
    if goal not in ("hiburan", "informasi", "promosi"):
        return None, (jsonify({"error": "Pilih tujuan video yang tersedia."}), 400)
    if tone not in ("santai", "lucu", "serius", "meyakinkan"):
        return None, (jsonify({"error": "Pilih gaya bicara yang tersedia."}), 400)
    if duration not in (15, 30, 45):
        return None, (jsonify({"error": "Durasi harus 15, 30, atau 45 detik."}), 400)
    return {"idea": idea.strip(), "goal": goal, "tone": tone, "duration": duration}, None


def _has_usable_key(value: Optional[str], *placeholders: str) -> bool:
    cleaned = (value or "").strip()
    return bool(cleaned and cleaned not in placeholders)


def _idea_llm_call():
    """Use configured model when available; fall back across Gemini/Agnes/OpenAI on runtime errors."""
    provider = str(cfg.LLM_PROVIDER or "gemini").strip().lower()
    has_gemini = _has_usable_key(cfg.GEMINI_API_KEY, "your_gemini_key_here")
    has_openai = _has_usable_key(cfg.OPENAI_API_KEY, "your_openai_key_here", "your_apmix_or_openai_key_here")
    has_agnes = _has_usable_key(getattr(cfg, "AGNES_API_KEY", ""), "your_agnes_key_here")

    primary_fn = call_local_llm
    notice: Optional[str] = None

    if provider != "openai":
        if not has_gemini and has_agnes:
            return agnes_chat, "Gemini belum disetel; menyusun ide memakai Agnes AI."
    else:
        if not has_openai and has_agnes:
            return agnes_chat, "OpenAI belum disetel; menyusun ide memakai Agnes AI."
        model_response = get_openai_models()
        if model_response.get("success") is True:
            available = model_response.get("models", [])
            model_ids = [item.get("id") for item in available if isinstance(item, dict) and item.get("id")]
            configured_model = str(cfg.OPENAI_MODEL or "").strip()
            if model_ids and configured_model not in model_ids:
                fallback_model = model_ids[0]
                notice = f"Model {configured_model or 'aktif'} tidak tersedia; untuk ide ini dipakai {fallback_model}."
                app.logger.warning(notice)
                primary_fn = lambda prompt, _m=fallback_model: call_openai_llm(prompt, model=_m)

    fallbacks = []
    if provider == "openai":
        if has_gemini:
            fallbacks.append(("gemini", call_gemini_llm))
        if has_agnes:
            fallbacks.append(("agnes", agnes_chat))
    else:
        if has_agnes:
            fallbacks.append(("agnes", agnes_chat))
        if has_openai:
            fallbacks.append(("openai", call_openai_llm))

    if not fallbacks:
        return primary_fn, notice

    def runner(prompt: str) -> str:
        try:
            return primary_fn(prompt)
        except Exception as exc:
            last_err = exc
            app.logger.warning("Idea LLM primary (%s) failed: %s. Mencoba fallback...", provider, exc)
            for name, fn in fallbacks:
                try:
                    return fn(prompt)
                except Exception as fb_exc:
                    last_err = fb_exc
                    app.logger.warning("Idea LLM fallback (%s) failed: %s", name, fb_exc)
            raise last_err

    return runner, notice


def _idea_error_response(exc: Exception, task: str):
    detail = str(exc).lower()
    if "api_key" in detail and ("not set" in detail or "belum disetel" in detail):
        return jsonify({"error": "Sambungkan AI dulu lewat Pengaturan sebelum membuat panduan."}), 503
    if "model_not_found" in detail or "unknown model" in detail:
        return jsonify({"error": "Model AI yang dipilih tidak tersedia. Buka Pengaturan dan pilih model yang tersedia."}), 502
    if "connection error" in detail or "connecterror" in detail:
        return jsonify({"error": "Tidak bisa terhubung ke layanan AI. Periksa koneksi atau alamat AI di Pengaturan."}), 502
    app.logger.exception("Idea %s generation failed", task)
    label = "Arah cerita" if task == "direction" else "Panduan video"
    return jsonify({"error": f"{label} belum berhasil dibuat. Coba lagi sebentar."}), 502


@app.route("/api/ideas/directions", methods=["POST"])
def api_idea_directions():
    data, error = _idea_request_data()
    if error:
        return error
    try:
        llm_call, notice = _idea_llm_call()
        result = generate_directions(llm_call, **data)
        if notice:
            result["notice"] = notice
        return jsonify(result)
    except Exception as exc:
        return _idea_error_response(exc, "direction")


@app.route("/api/ideas/plan", methods=["POST"])
def api_idea_plan():
    data, error = _idea_request_data()
    if error:
        return error
    direction = request.get_json(silent=True).get("direction")
    if not isinstance(direction, dict) or any(
        not isinstance(direction.get(key), str) or not direction[key].strip()
        for key in ("title", "summary", "hook", "why")
    ):
        return jsonify({"error": "Pilih salah satu arah cerita terlebih dahulu."}), 400
    try:
        llm_call, notice = _idea_llm_call()
        result = generate_plan(llm_call, direction=direction, **data)
        if notice:
            result["notice"] = notice
        return jsonify(result)
    except Exception as exc:
        return _idea_error_response(exc, "plan")


def run_agnes_idea_job(job_id: str, params: Dict[str, Any]) -> None:
    """Background worker to generate a video from an idea using Agnes AI."""
    with generation_lock:
        job_ctx = job_manager.get_job(job_id)
        if not job_ctx:
            job_ctx = JobContext(job_id=job_id, url=params.get("url", "idea://agnes"), params=params)
            job_manager._jobs[job_id] = job_ctx

        job_ctx.worker_thread = threading.current_thread()
        session_folder = params.get("session_folder") or job_ctx.session_folder
        if not session_folder:
            session_folder = f"idea_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_id}"
        job_ctx.session_folder = session_folder
        job_dir = OUTPUT_DIR / session_folder
        result: Optional[Dict[str, Any]] = None

        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            if job_ctx.status == JobStatus.CANCELED:
                jobs[job_id] = job_ctx.to_dict()
                _persist_job_metadata(job_ctx)
                return

            job_ctx.transition_to(JobStatus.RUNNING, stage="submitting", progress=10)
            job_ctx.started_at = time.time()
            job_ctx.emit_log("[agnes] Mengirim prompt ide ke Agnes AI...")
            jobs[job_id] = job_ctx.to_dict()
            _persist_job_metadata(job_ctx)

            filename = "short_1.mp4"
            dest_path = job_dir / filename

            def on_status(status_name: str, pct: Optional[int], message: str) -> None:
                job_ctx.emit_log(f"[agnes] {message}")
                normalized = (status_name or "").strip().lower()
                if normalized == "submitting":
                    next_stage = "submitting"
                elif normalized == "downloading":
                    next_stage = "downloading"
                else:
                    next_stage = "rendering"
                if pct is not None:
                    mapped = max(10, min(95, int(pct)))
                    job_ctx.transition_to(JobStatus.RUNNING, stage=next_stage, progress=mapped)
                else:
                    job_ctx.transition_to(JobStatus.RUNNING, stage=next_stage)
                jobs[job_id] = job_ctx.to_dict()

            gen_info = generate_video_to_file(
                prompt=params["prompt"],
                dest_path=dest_path,
                model=params.get("model"),
                duration=params.get("duration", 6),
                aspect_ratio=params.get("aspect_ratio", "9:16"),
                size=params.get("size", "720P"),
                api_key=params.get("api_key"),
                base_url=params.get("base_url"),
                check_cancel=job_ctx.check_cancellation_or_timeout,
                on_status=on_status,
            )

            title = (params.get("title") or "Video Ide Agnes AI").strip()[:120]
            aspect_ratio = params.get("aspect_ratio", "9:16")
            duration = float(params.get("duration", 6))
            short_entry = {
                "title": title,
                "hook_sentence": params.get("hook") or params["prompt"][:140],
                "score": 95,
                "clip_index": 1,
                "filename": filename,
                "folder_name": session_folder,
                "web_url": f"/output/{session_folder}/{filename}",
                "clip_url": str(dest_path),
                "aspect_ratio": aspect_ratio,
                "start_time": 0,
                "end_time": duration,
                "summary": params["prompt"],
                "agnes_video_id": gen_info.get("video_id"),
                "agnes_model": gen_info.get("model"),
            }
            result = {
                "session_folder": session_folder,
                "video_title": title,
                "aspect_ratio": aspect_ratio,
                "shorts": [short_entry],
                "stats": {"total": 1, "success": 1, "failed": 0},
            }
            job_ctx.emit_log(f"[agnes] Video selesai disimpan: {filename}")
            job_ctx.transition_to(JobStatus.COMPLETED, stage="completed", progress=100, result=result)

        except JobCancelledException as exc:
            job_ctx.emit_log(f"[INFO] Generasi video Agnes AI dibatalkan: {exc}")
            job_ctx.transition_to(
                JobStatus.CANCELED,
                stage="canceled",
                progress=100,
                error=str(exc),
                result={"shorts": [], "stats": {"total": 1, "success": 0, "failed": 0}},
            )
        except JobTimeoutException as exc:
            job_ctx.emit_log(f"[ERROR] Batas waktu Agnes AI terlampaui: {exc}")
            job_ctx.transition_to(
                JobStatus.TIMEOUT,
                stage="timeout",
                progress=100,
                error=str(exc),
                result={"shorts": [], "stats": {"total": 1, "success": 0, "failed": 0}},
            )
        except Exception as exc:
            job_ctx.emit_log(f"[ERROR] Agnes AI gagal: {exc}")
            job_ctx.transition_to(JobStatus.FAILED, stage="failed", progress=100, error=str(exc), result=result)
        finally:
            if session_folder:
                try:
                    _persist_job_metadata(job_ctx)
                except Exception:
                    pass
            jobs[job_id] = job_ctx.to_dict()


@app.route("/api/ideas/generate-video", methods=["POST"])
def api_idea_generate_video():
    """Generate a video from an idea prompt via Agnes AI in a background job."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Payload harus berupa objek JSON yang valid."}), 400

    if not _has_usable_key(getattr(cfg, "AGNES_API_KEY", ""), "your_agnes_key_here"):
        return jsonify({"error": "Sambungkan AGNES_API_KEY dulu lewat Pengaturan sebelum membuat video."}), 503

    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.strip()) > 2000:
        return jsonify({"error": "Prompt video wajib diisi (maksimal 2.000 karakter)."}), 400

    model = str(data.get("model") or getattr(cfg, "AGNES_VIDEO_MODEL", "agnes-video-2.5-flash")).strip()
    if model not in AGNES_VIDEO_MODELS:
        return jsonify({"error": f"Model Agnes tidak valid. Pilihan: {', '.join(AGNES_VIDEO_MODELS)}"}), 400

    aspect_ratio = str(data.get("aspect_ratio") or "9:16").strip()
    if aspect_ratio not in AGNES_ASPECT_RATIOS:
        return jsonify({"error": f"Rasio aspek tidak valid. Pilihan: {', '.join(AGNES_ASPECT_RATIOS)}"}), 400

    raw_duration = data.get("duration", 6)
    try:
        duration = int(raw_duration)
    except (TypeError, ValueError):
        return jsonify({"error": "Durasi video Agnes AI harus berupa angka 4 sampai 12 detik."}), 400
    if not 4 <= duration <= 12:
        return jsonify({"error": "Durasi video Agnes AI harus antara 4 sampai 12 detik."}), 400

    size = str(data.get("size") or "720P").strip().upper()
    if size not in AGNES_SIZES:
        return jsonify({"error": f"Resolusi tidak valid. Pilihan: {', '.join(AGNES_SIZES)}"}), 400

    title = str(data.get("title") or data.get("idea") or "Video Ide Agnes AI").strip()
    hook = str(data.get("hook") or "").strip()

    with job_manager._admission_lock:
        active_job = get_active_job()
        if active_job:
            return jsonify({
                "error": f"Sedang ada proses generasi yang aktif (Job ID: {active_job['job_id']}). Harap tunggu hingga selesai atau batalkan pekerjaan tersebut."
            }), 409

        job_id = str(uuid.uuid4())[:8]
        session_folder = f"idea_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_id}"
        (OUTPUT_DIR / session_folder).mkdir(parents=True, exist_ok=True)

        job_params = {
            "session_folder": session_folder,
            "prompt": prompt.strip(),
            "title": title,
            "hook": hook,
            "model": model,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "size": size,
            "api_key": cfg.AGNES_API_KEY,
            "base_url": getattr(cfg, "AGNES_BASE_URL", "https://apihub.agnes-ai.com"),
            "config": {
                "agnes_api_key": cfg.AGNES_API_KEY,
                "agnes_base_url": getattr(cfg, "AGNES_BASE_URL", "https://apihub.agnes-ai.com"),
                "agnes_video_model": model,
            },
        }
        job_ctx = job_manager.admit_job(
            job_id=job_id,
            url=f"agnes://{model}",
            params=job_params,
            timeout_seconds=getattr(cfg, "JOB_TIMEOUT_SECONDS", 1800.0),
        )
        job_ctx.session_folder = session_folder
        jobs[job_id] = job_ctx.to_dict()
        try:
            _persist_job_metadata(job_ctx)
        except Exception:
            pass

    thread = threading.Thread(target=run_agnes_idea_job, args=(job_id, job_params), daemon=True)
    job_ctx.worker_thread = thread
    thread.start()

    return jsonify({"job_id": job_id, "status": "started"})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Trigger shorts generation in the background with strict input validation and config snapshotting."""
    cookies_file = None
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Payload harus berupa objek JSON yang valid."}), 400
    else:
        # Support multipart/form-data
        if "data" in request.form:
            try:
                data = json.loads(request.form.get("data", "{}"))
            except Exception:
                return jsonify({"error": "Payload form-data 'data' bukan JSON yang valid."}), 400
        else:
            data = request.form.to_dict()
            if "num_clips" in data:
                try:
                    data["num_clips"] = int(data["num_clips"])
                except (ValueError, TypeError):
                    pass
        if "cookies_file" in request.files:
            cookies_file = request.files["cookies_file"]

    raw_url = data.get("url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        return jsonify({"error": "URL Video YouTube wajib diisi berupa teks."}), 400
    url = raw_url.strip()

    try:
        parsed = urlparse(url)
    except ValueError:
        return jsonify({"error": "Format URL tidak valid. Masukkan URL YouTube (https://...) atau file lokal yang valid."}), 400

    is_http = parsed.scheme in ("http", "https")
    is_file = parsed.scheme == "file"
    is_local_file = os.path.isfile(url)
    if not (is_http or is_file or is_local_file):
        return jsonify({"error": "Format URL tidak valid. Masukkan URL YouTube (https://...) atau file lokal yang valid."}), 400

    if "num_clips" in data:
        raw_num_clips = data["num_clips"]
        if isinstance(raw_num_clips, bool) or not isinstance(raw_num_clips, int):
            return jsonify({"error": f"Target jumlah klip '{raw_num_clips}' tidak valid. Harus berupa angka bulat."}), 400
        if raw_num_clips < 1 or raw_num_clips > 10:
            return jsonify({"error": "Target jumlah klip harus berupa angka bulat antara 1 dan 10."}), 400
        num_clips = raw_num_clips
    else:
        num_clips = 3

    raw_ar = data.get("aspect_ratio", "9:16")
    if not isinstance(raw_ar, str):
        return jsonify({"error": "Rasio aspek harus berupa teks."}), 400
    aspect_ratio = raw_ar.strip()
    if aspect_ratio not in ("9:16", "1:1", "16:9"):
        return jsonify({"error": f"Rasio aspek '{aspect_ratio}' tidak didukung. Pilihan: 9:16, 1:1, 16:9."}), 400

    raw_framing = data.get("framing_mode", "podcast")
    if not isinstance(raw_framing, str):
        return jsonify({"error": "Mode framing harus berupa teks."}), 400
    framing_mode = raw_framing.strip().lower()
    if framing_mode not in ("podcast", "single", "center", "gaming", "dual"):
        framing_mode = "podcast"

    raw_preset = data.get("gaming_preset", "auto")
    valid_presets = (
        "auto", "auto_detect", "clean_2layer", "clean_2layer_cam_top", "clean_2layer_cam_bottom",
        "clean_2layer_bottom_right", "clean_2layer_bottom_left",
        "clean_2layer_top_right", "clean_2layer_top_left", "discord_top_cam_bottom_right",
        "discord_left_cam_top_right", "custom"
    )
    if not isinstance(raw_preset, str) or raw_preset.strip().lower() not in valid_presets:
        gaming_preset = "auto"
    else:
        gaming_preset = raw_preset.strip().lower()

    raw_layout = data.get("gaming_layout")
    gaming_layout = str(raw_layout).strip().lower() if raw_layout in ("cam_top", "cam_bottom") else None

    gaming_custom_box = validate_and_sanitize_gaming_box(data.get("gaming_custom_box"))

    raw_sub = data.get("subtitle_style", "karaoke")
    if not isinstance(raw_sub, str):
        return jsonify({"error": "Gaya subtitle harus berupa teks."}), 400
    subtitle_style = raw_sub.strip().lower()
    valid_sub_styles = (
        "karaoke", "kinetic", "classic", "none",
        "hormozi", "tiktok_punch", "devon_bold", "vox_box", "ali_abdaal",
        "aesthetic", "mrbeast", "karaoke_bounce", "cyber_neon", "retro_synth",
        "luxury_gold", "gaming_rage", "clean_bottom_bar", "comic_pow",
        "nas_daily", "netflix_sub", "matrix_hacker", "dan_koe", "fire_flame", "pastel_vlog",
        "hormozi_emerald", "hormozi_fire", "vox_cinema", "ali_cyan", "aesthetic_warm", "mrbeast_yellow",
    )
    if subtitle_style not in valid_sub_styles:
        subtitle_style = "karaoke"

    raw_font = data.get("font_family")
    font_family = str(raw_font).strip() if (raw_font and isinstance(raw_font, str)) else None

    raw_fmt = data.get("format", "720")
    if not isinstance(raw_fmt, str):
        return jsonify({"error": "Resolusi harus berupa teks."}), 400
    fmt = raw_fmt.strip()
    if fmt not in ("360", "480", "720", "1080"):
        return jsonify({"error": f"Resolusi '{fmt}' tidak valid. Pilihan: 360, 480, 720, 1080."}), 400

    raw_mode = data.get("mode", "local")
    if not isinstance(raw_mode, str):
        return jsonify({"error": "Mode harus berupa teks."}), 400
    mode = raw_mode.strip().lower()
    if mode not in ("local", "api"):
        return jsonify({"error": f"Mode '{mode}' tidak valid. Pilihan: local, api."}), 400

    if mode == "api" and framing_mode == "gaming":
        return jsonify({"error": "Mode Cloud API (MuAPI) belum mendukung layout Gaming Facecam. Silakan gunakan Local Engine untuk fitur ini."}), 400

    raw_llm = data.get("llm_provider")
    if raw_llm is not None and not isinstance(raw_llm, str):
        return jsonify({"error": "LLM provider harus berupa teks."}), 400
    llm_provider = str(raw_llm or cfg.LLM_PROVIDER or "gemini").strip().lower()
    if llm_provider not in ("gemini", "openai"):
        return jsonify({"error": f"LLM provider '{llm_provider}' tidak didukung. Pilihan: gemini, openai."}), 400

    raw_trans = data.get("transcriber_provider")
    if raw_trans is not None and not isinstance(raw_trans, str):
        return jsonify({"error": "Transcriber provider harus berupa teks."}), 400
    transcriber_provider = str(raw_trans or cfg.TRANSCRIBER_PROVIDER or "gemini").strip().lower()
    if transcriber_provider not in ("gemini", "whisper"):
        return jsonify({"error": f"Transcriber provider '{transcriber_provider}' tidak didukung. Pilihan: gemini, whisper."}), 400

    language = data.get("language")
    if language is not None:
        if not isinstance(language, str):
            return jsonify({"error": "Bahasa harus berupa teks (string)."}), 400
        language = language.strip() or None

    for m_key in ("gemini_model", "gemini_transcriber_model", "openai_model", "whisper_model"):
        if m_key in data and data[m_key] is not None and not isinstance(data[m_key], str):
            return jsonify({"error": f"Nilai '{m_key}' harus berupa teks."}), 400

    raw_auto_del = data.get("auto_delete_source_video")
    if raw_auto_del is None:
        auto_delete_source_video = getattr(cfg, "AUTO_DELETE_SOURCE_VIDEO", True)
    elif isinstance(raw_auto_del, bool):
        auto_delete_source_video = raw_auto_del
    elif isinstance(raw_auto_del, str):
        auto_delete_source_video = raw_auto_del.strip().lower() in ("true", "1", "yes")
    else:
        auto_delete_source_video = bool(raw_auto_del)

    # Ensure single active generation job protected from concurrent race conditions
    with job_manager._admission_lock:
        active_job = get_active_job()
        if active_job:
            return jsonify({
                "error": f"Sedang ada proses generasi yang aktif (Job ID: {active_job['job_id']}). Harap tunggu hingga selesai atau batalkan pekerjaan tersebut."
            }), 409

        config_snapshot = {
            "llm_provider": llm_provider,
            "transcriber_provider": transcriber_provider,
            "gemini_model": (data.get("gemini_model") or cfg.GEMINI_MODEL or "gemini-3.5-flash").strip(),
            "gemini_transcriber_model": (data.get("gemini_transcriber_model") or getattr(cfg, "GEMINI_TRANSCRIBER_MODEL", "gemini-3.5-transcribe")).strip(),
            "openai_model": (data.get("openai_model") or cfg.OPENAI_MODEL or "gpt-4o-mini").strip(),
            "whisper_model": (data.get("whisper_model") or cfg.LOCAL_WHISPER_MODEL or "base").strip(),
            "openai_base_url": cfg.OPENAI_BASE_URL,
            "gemini_api_key": cfg.GEMINI_API_KEY,
            "openai_api_key": cfg.OPENAI_API_KEY,
            "muapi_api_key": cfg.MUAPI_API_KEY,
            "auto_delete_source_video": auto_delete_source_video,
        }

        job_id = str(uuid.uuid4())[:8]
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_folder = f"{timestamp_str}_{job_id}"
        job_dir = OUTPUT_DIR / session_folder
        job_dir.mkdir(parents=True, exist_ok=True)

        cookies_temp_path = None
        if cookies_file and getattr(cookies_file, "filename", None):
            c_path = job_dir / f"cookies_{job_id}.txt"
            cookies_file.save(str(c_path))
            cookies_temp_path = str(c_path)
        elif data.get("cookies_content"):
            c_path = job_dir / f"cookies_{job_id}.txt"
            with open(c_path, "w", encoding="utf-8") as cf:
                cf.write(str(data["cookies_content"]))
            cookies_temp_path = str(c_path)

        job_params = {
            "session_folder": session_folder,
            "num_clips": num_clips,
            "aspect_ratio": aspect_ratio,
            "framing_mode": framing_mode,
            "subtitle_style": subtitle_style,
            "font_family": font_family,
            "gaming_preset": gaming_preset,
            "gaming_layout": gaming_layout,
            "gaming_custom_box": gaming_custom_box,
            "format": fmt,
            "language": language,
            "mode": mode,
            "config": config_snapshot,
            "auto_delete_source_video": auto_delete_source_video,
            "cookies_path": cookies_temp_path,
            "enable_sfx": bool(data.get("enable_sfx", True)),
            "remove_silence": bool(data.get("remove_silence", False)),
        }
        job_ctx = job_manager.admit_job(
            job_id=job_id,
            url=url,
            params=job_params,
            timeout_seconds=getattr(cfg, "JOB_TIMEOUT_SECONDS", 1800.0),
        )
        job_ctx.session_folder = session_folder
        jobs[job_id] = job_ctx.to_dict()
        try:
            _persist_job_metadata(job_ctx)
        except Exception:
            pass

    thread = threading.Thread(
        target=run_generation_job,
        args=(job_id, {"url": url, **job_params}),
        daemon=True,
    )
    job_ctx.worker_thread = thread
    thread.start()

    return jsonify({"job_id": job_id, "status": "started"})


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def api_cancel_job(job_id: str):
    """Cancel an active or queued generation job idempotently."""
    result = job_manager.request_cancel(job_id)
    if result.get("not_found"):
        return jsonify({"error": "Pekerjaan tidak ditemukan."}), 404

    job_ctx = job_manager.get_job(job_id)
    if job_ctx:
        jobs[job_id] = job_ctx.to_dict()
        try:
            _persist_job_metadata(job_ctx)
        except Exception:
            pass

    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": result.get("status"),
        "message": result.get("message"),
        "already_terminal": result.get("already_terminal", False),
    }), 200


@app.route("/api/jobs/active", methods=["GET"])
def get_current_active_job():
    """Retrieve the currently active job if any (queued, running, or canceling)."""
    active = get_active_job()
    if active:
        data = dict(active)
        data["active"] = True
        return jsonify(data)
    return jsonify({"active": False, "status": "none"}), 200


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    """Retrieve job status, progress, logs, and results."""
    job_ctx = job_manager.get_job(job_id)
    if job_ctx:
        d = job_ctx.to_dict()
        jobs[job_id] = d
        return jsonify(d)

    job = jobs.get(job_id)
    if job:
        raw_logs = "".join(job.get("logs", []))
        return jsonify({
            "job_id": job["job_id"],
            "url": job.get("url"),
            "status": job.get("status", "running"),
            "stage": job.get("stage", "running"),
            "progress": job.get("progress", 0),
            "logs": raw_logs,
            "result": job.get("result"),
            "error": job.get("error"),
            "cancel_reason": job.get("cancel_reason"),
            "elapsed_seconds": int(time.time() - job.get("created_at", time.time())),
            "session_folder": job.get("session_folder"),
        })

    # Check if saved metadata exists on disk
    meta_candidates = list(OUTPUT_DIR.glob(f"**/job_{job_id}.json"))
    if meta_candidates:
        try:
            with open(meta_candidates[0], "r", encoding="utf-8") as f:
                data = json.load(f)
                disk_status = data.get("status") or "completed"
                disk_stage = data.get("stage") or disk_status
                raw_disk_logs = data.get("logs")
                if isinstance(raw_disk_logs, list):
                    formatted_logs = "\n".join(raw_disk_logs)
                elif isinstance(raw_disk_logs, str) and raw_disk_logs:
                    formatted_logs = raw_disk_logs
                else:
                    formatted_logs = "Memuat status dari sesi sebelumnya."

                return jsonify({
                    "job_id": job_id,
                    "status": disk_status,
                    "stage": disk_stage,
                    "progress": 100 if disk_status in (JobStatus.COMPLETED, JobStatus.PARTIAL, JobStatus.FAILED) else 0,
                    "logs": formatted_logs,
                    "result": data.get("result"),
                    "error": data.get("error"),
                    "cancel_reason": data.get("cancel_reason"),
                    "created_at": data.get("created_at"),
                    "ended_at": data.get("ended_at"),
                    "duration_seconds": data.get("duration_seconds", 0),
                    "session_folder": data.get("session_folder"),
                })
        except Exception:
            pass
    return jsonify({"error": "Job not found"}), 404


@app.route("/api/history", methods=["GET"])
def get_history():
    """List all available generated shorts grouped by generation sessions."""
    sessions: List[Dict[str, Any]] = []
    flat_items: List[Dict[str, Any]] = []
    seen_files = set()

    # 1. Scan for session subdirectories in OUTPUT_DIR
    subdirs = [p for p in OUTPUT_DIR.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))]
    for sdir in sorted(subdirs, key=os.path.getmtime, reverse=True):
        folder_name = sdir.name
        job_json_files = list(sdir.glob("job_*.json"))
        session_meta: Dict[str, Any] = {}
        if job_json_files:
            try:
                with open(job_json_files[0], "r", encoding="utf-8") as f:
                    session_meta = json.load(f)
            except Exception:
                pass

        session_shorts: List[Dict[str, Any]] = []
        res_data = session_meta.get("result")
        result = res_data if isinstance(res_data, dict) else {}
        session_ar = (
            session_meta.get("aspect_ratio")
            or (session_meta.get("params", {}).get("aspect_ratio") if isinstance(session_meta.get("params"), dict) else None)
            or (result.get("aspect_ratio") if isinstance(result, dict) else None)
            or "9:16"
        )
        known_shorts = result.get("shorts", [])

        # Add shorts listed in job JSON
        for idx, s in enumerate(known_shorts, 1):
            fn = s.get("filename")
            if not fn and s.get("clip_url"):
                fn = Path(s["clip_url"]).name
            if fn:
                fp = sdir / fn
                if fp.exists():
                    seen_files.add(str(fp.resolve()))
                    vtt_name = fp.stem + ".vtt"
                    has_vtt_file = (sdir / vtt_name).exists()
                    # Honor committed metadata: if metadata explicitly set vtt_url to None, do not resurrect old VTT!
                    if "vtt_url" in s:
                        has_vtt = bool(s.get("vtt_url") and has_vtt_file)
                    else:
                        has_vtt = has_vtt_file

                    c_idx = s.get("clip_index")
                    if c_idx is None or not isinstance(c_idx, int) or isinstance(c_idx, bool):
                        m = re.search(r"short_(\d+)", fn)
                        c_idx = int(m.group(1)) if m else idx

                    rev_id = s.get("rev_id")
                    rev_query = f"?v={rev_id}" if rev_id else ""
                    item = {
                        "title": s.get("title") or fn,
                        "hook_sentence": s.get("hook_sentence") or "",
                        "score": s.get("score") or 0,
                        "web_url": f"/output/{folder_name}/{fn}{rev_query}",
                        "vtt_url": f"/output/{folder_name}/{vtt_name}{rev_query}" if has_vtt else None,
                        "filename": fn,
                        "clip_index": c_idx,
                        "folder_name": folder_name,
                        "rev_id": rev_id,
                        "aspect_ratio": s.get("aspect_ratio") or session_ar,
                        "size_bytes": fp.stat().st_size,
                        "created_at": datetime.fromtimestamp(fp.stat().st_mtime).strftime("%d %b %Y, %H:%M"),
                        "start_time": s.get("start_time"),
                        "end_time": s.get("end_time"),
                    }
                    session_shorts.append(item)
                    flat_items.append(item)

        # Check for any extra/orphan mp4 in this session folder
        for mp4 in sorted(sdir.glob("*.mp4"), key=os.path.getmtime):
            if ".cut." in mp4.name or mp4.name.startswith("source_") or mp4.name.startswith(".tmp_") or mp4.name.startswith(".bak_"):
                continue
            if str(mp4.resolve()) not in seen_files:
                seen_files.add(str(mp4.resolve()))
                fn = mp4.name
                vtt_name = mp4.stem + ".vtt"
                has_vtt = (sdir / vtt_name).exists()
                m = re.search(r"short_(\d+)", fn)
                c_idx = int(m.group(1)) if m else (len(session_shorts) + 1)
                item = {
                    "title": fn.replace(".mp4", "").replace("_", " ").title(),
                    "hook_sentence": "Klip video",
                    "score": 85,
                    "web_url": f"/output/{folder_name}/{fn}",
                    "vtt_url": f"/output/{folder_name}/{vtt_name}" if has_vtt else None,
                    "filename": fn,
                    "clip_index": c_idx,
                    "folder_name": folder_name,
                    "aspect_ratio": session_ar,
                    "size_bytes": mp4.stat().st_size,
                    "created_at": datetime.fromtimestamp(mp4.stat().st_mtime).strftime("%d %b %Y, %H:%M"),
                    "start_time": None,
                    "end_time": None,
                }
                session_shorts.append(item)
                flat_items.append(item)

        if session_shorts:
            session_url = session_meta.get("url", "")
            first_title = session_shorts[0].get("title", "")
            created_dt = session_meta.get("created_at")
            if created_dt:
                try:
                    display_time = datetime.fromisoformat(created_dt).strftime("%d %b %Y, %H:%M")
                except Exception:
                    display_time = datetime.fromtimestamp(sdir.stat().st_mtime).strftime("%d %b %Y, %H:%M")
            else:
                display_time = datetime.fromtimestamp(sdir.stat().st_mtime).strftime("%d %b %Y, %H:%M")

            sessions.append({
                "id": folder_name,
                "folder_name": folder_name,
                "job_id": session_meta.get("job_id"),
                "url": session_url,
                "title": first_title or f"Sesi {folder_name}",
                "created_at": display_time,
                "aspect_ratio": session_ar,
                "total_shorts": len(session_shorts),
                "total_size_bytes": sum(s["size_bytes"] for s in session_shorts),
                "shorts": session_shorts,
                "is_legacy": False,
            })

    # 2. Check legacy items in root OUTPUT_DIR
    legacy_jobs = list(OUTPUT_DIR.glob("job_*.json"))
    legacy_shorts: List[Dict[str, Any]] = []
    for p in sorted(legacy_jobs, key=os.path.getmtime, reverse=True):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                res_data = data.get("result")
                result = res_data if isinstance(res_data, dict) else {}
                for idx, short in enumerate(result.get("shorts", []), 1):
                    fn = short.get("filename")
                    if fn:
                        fp = OUTPUT_DIR / fn
                        if fp.exists() and str(fp.resolve()) not in seen_files:
                            seen_files.add(str(fp.resolve()))
                            vtt_name = fp.stem + ".vtt"
                            has_vtt = (OUTPUT_DIR / vtt_name).exists()
                            c_idx = short.get("clip_index")
                            if c_idx is None or not isinstance(c_idx, int) or isinstance(c_idx, bool):
                                m = re.search(r"short_(\d+)", fn)
                                c_idx = int(m.group(1)) if m else idx
                            item = {
                                "title": short.get("title") or fn,
                                "hook_sentence": short.get("hook_sentence") or "",
                                "score": short.get("score") or 0,
                                "web_url": f"/output/{fn}",
                                "vtt_url": f"/output/{vtt_name}" if has_vtt else None,
                                "filename": fn,
                                "clip_index": c_idx,
                                "folder_name": "",
                                "size_bytes": fp.stat().st_size,
                                "created_at": datetime.fromtimestamp(fp.stat().st_mtime).strftime("%d %b %Y, %H:%M"),
                                "start_time": short.get("start_time"),
                                "end_time": short.get("end_time"),
                            }
                            legacy_shorts.append(item)
                            flat_items.append(item)
        except Exception:
            continue

    # Extra root mp4s
    for mp4 in sorted(OUTPUT_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True):
        if ".cut." in mp4.name or mp4.name.startswith("source_") or mp4.name.startswith(".tmp_"):
            continue
        if str(mp4.resolve()) not in seen_files:
            seen_files.add(str(mp4.resolve()))
            fn = mp4.name
            vtt_name = mp4.stem + ".vtt"
            m = re.search(r"short_(\d+)", fn)
            c_idx = int(m.group(1)) if m else (len(legacy_shorts) + 1)
            item = {
                "title": fn.replace(".mp4", "").replace("_", " ").title(),
                "hook_sentence": "Klip video",
                "score": None,
                "web_url": f"/output/{fn}",
                "vtt_url": f"/output/{vtt_name}" if has_vtt else None,
                "filename": fn,
                "clip_index": c_idx,
                "folder_name": "",
                "size_bytes": mp4.stat().st_size,
                "created_at": datetime.fromtimestamp(mp4.stat().st_mtime).strftime("%d %b %Y, %H:%M"),
                "start_time": None,
                "end_time": None,
            }
            legacy_shorts.append(item)
            flat_items.append(item)

    if legacy_shorts:
        sessions.append({
            "id": "legacy_root",
            "folder_name": "",
            "job_id": None,
            "url": "",
            "title": "Sesi Sebelumnya (Legacy)",
            "created_at": legacy_shorts[0]["created_at"],
            "total_shorts": len(legacy_shorts),
            "total_size_bytes": sum(s["size_bytes"] for s in legacy_shorts),
            "shorts": legacy_shorts,
            "is_legacy": True,
        })

    return jsonify({
        "sessions": sessions,
        "history": flat_items,
        "total_videos": len(flat_items),
    })


@app.route("/api/open-folder", methods=["POST"])
def open_folder():
    """Open a session folder in the system file manager."""
    try:
        data = request.get_json(force=False, silent=False)
    except Exception:
        return jsonify({"error": "Payload harus berupa objek JSON yang valid."}), 400

    raw_body = request.get_data(cache=True).strip()
    if data is None and not raw_body:
        data = {}
    elif not isinstance(data, dict):
        return jsonify({"error": "Payload harus berupa objek JSON yang valid."}), 400

    raw_folder = data.get("folder", "")
    if not isinstance(raw_folder, str):
        return jsonify({"error": "Nama folder harus berupa teks."}), 400
    folder_name = raw_folder.strip()

    target_dir = OUTPUT_DIR
    if folder_name:
        target_dir = (OUTPUT_DIR / folder_name).resolve()
        if not str(target_dir).startswith(str(OUTPUT_DIR.resolve())):
            return jsonify({"error": "Akses ditolak"}), 403

    if not target_dir.exists():
        return jsonify({"error": "Folder tidak ditemukan"}), 404

    try:
        if sys.platform == "win32":
            os.startfile(str(target_dir))
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", str(target_dir)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(target_dir)])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": f"Gagal membuka folder: {e}"}), 500


@app.route("/api/history/session/<path:folder_name>", methods=["DELETE"])
def delete_session(folder_name: str):
    """Delete a session folder with concurrency and active-job protections."""
    folder_name = folder_name.strip()
    if not folder_name:
        return jsonify({"error": "Nama folder tidak boleh kosong"}), 400

    target_dir = (OUTPUT_DIR / folder_name).resolve()
    # Security: must be strictly inside OUTPUT_DIR, cannot be OUTPUT_DIR itself
    if not str(target_dir).startswith(str(OUTPUT_DIR.resolve())) or target_dir == OUTPUT_DIR.resolve():
        return jsonify({"error": "Akses ditolak"}), 403

    if not target_dir.exists():
        return jsonify({"error": "Folder tidak ditemukan"}), 404

    # 1. Check if an active generation job is currently targeting this session
    active_job = job_manager.get_active_job()
    if active_job and getattr(active_job, "session_folder", None) == folder_name:
        return jsonify({
            "error": "Sesi tidak dapat dihapus karena proses generasi sedang berjalan pada sesi ini."
        }), 409

    # 2. Acquire session gate for deletion (atomically blocks new editors from starting)
    gate_ok, gate_err = session_gate.acquire_deletion_gate(folder_name)
    if not gate_ok:
        return jsonify({"error": gate_err}), 409

    # 3. Check and hold session lock during deletion
    session_lock = get_session_lock(folder_name)
    if not session_lock.acquire(blocking=False):
        session_gate.release_deletion_gate(folder_name)
        return jsonify({
            "error": "Sesi tidak dapat dihapus karena sedang dalam proses edit atau render editorial."
        }), 409

    try:
        import shutil
        if target_dir.is_dir():
            shutil.rmtree(target_dir)
        else:
            target_dir.unlink()

        session_gate.purge_session(folder_name)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": f"Gagal menghapus sesi: {e}"}), 500
    finally:
        session_lock.release()
        session_gate.release_deletion_gate(folder_name)


@app.route("/api/sessions/<path:folder_name>/zip", methods=["GET"])
def download_session_zip(folder_name: str):
    """Bundle and stream all rendered video clips and subtitles for a session as a ZIP archive."""
    import zipfile
    import tempfile
    from flask import send_file

    folder_name = folder_name.strip()
    if not folder_name or ".." in folder_name or "/" in folder_name or "\\" in folder_name:
        return jsonify({"error": "Nama folder sesi tidak valid."}), 400

    target_dir = (OUTPUT_DIR / folder_name).resolve()
    try:
        target_dir.relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Folder sesi tidak ditemukan atau akses ditolak."}), 404

    if not target_dir.exists() or not target_dir.is_dir() or target_dir == OUTPUT_DIR.resolve():
        return jsonify({"error": "Folder sesi tidak ditemukan."}), 404

    clip_files = []
    # 1. First collect from job metadata if present to ensure proper clip ordering
    job_jsons = list(target_dir.glob("job_*.json"))
    if job_jsons:
        try:
            with open(job_jsons[0], "r", encoding="utf-8") as f:
                meta = json.load(f)
            shorts = meta.get("result", {}).get("shorts", [])
            for s in shorts:
                fn = s.get("filename") or (Path(s["clip_url"]).name if s.get("clip_url") else None)
                if fn:
                    p = target_dir / fn
                    if p.exists() and p not in clip_files:
                        clip_files.append(p)
                    # Include corresponding VTT subtitle if present
                    vtt_p = target_dir / (p.stem + ".vtt")
                    if vtt_p.exists() and vtt_p not in clip_files:
                        clip_files.append(vtt_p)
        except Exception:
            pass

    # 2. Also scan any rendered mp4 clips in the directory not starting with source_
    for p in sorted(target_dir.glob("*.mp4")):
        if not p.name.startswith("source_") and not p.name.startswith(".") and p not in clip_files:
            clip_files.append(p)
            vtt_p = target_dir / (p.stem + ".vtt")
            if vtt_p.exists() and vtt_p not in clip_files:
                clip_files.append(vtt_p)

    if not clip_files:
        return jsonify({"error": "Tidak ada klip video yang ditemukan dalam sesi ini."}), 404

    # Build ZIP using ZIP_STORED (fastest I/O, no recompression of already compressed MP4 video)
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = Path(temp_zip.name)
    temp_zip.close()

    try:
        with zipfile.ZipFile(temp_zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            for file_path in clip_files:
                zf.write(file_path, arcname=file_path.name)

        download_name = f"{folder_name}_clips.zip"
        resp = send_file(
            str(temp_zip_path),
            mimetype="application/zip",
            as_attachment=True,
            download_name=download_name,
        )

        def cleanup_temp_zip():
            try:
                if temp_zip_path.exists():
                    temp_zip_path.unlink()
            except Exception:
                pass

        resp.call_on_close(cleanup_temp_zip)
        return resp
    except Exception as e:
        if temp_zip_path.exists():
            try:
                temp_zip_path.unlink()
            except Exception:
                pass
        return jsonify({"error": f"Gagal membuat arsip ZIP: {str(e)}"}), 500


@app.route("/api/edit-clip", methods=["POST"])
def api_edit_clip():
    """Re-cut and re-frame a specific clip with custom in/out timestamps, caption, and framing."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Payload harus berupa objek JSON yang valid."}), 400

    session_folder = str(data.get("session_folder") or "").strip()
    if not session_folder or ".." in session_folder or "/" in session_folder or "\\" in session_folder:
        return jsonify({"error": "session_folder wajib disertakan dan tidak boleh mengandung path traversal."}), 400

    target_dir = (OUTPUT_DIR / session_folder).resolve()
    try:
        target_dir.relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Folder sesi tidak ditemukan atau akses ditolak."}), 404
    if not target_dir.exists() or target_dir == OUTPUT_DIR.resolve():
        return jsonify({"error": "Folder sesi tidak ditemukan atau akses ditolak."}), 404

    # 1. Validate timestamps (finite, not bool, valid range)
    raw_start = data.get("start_time")
    raw_end = data.get("end_time")
    if raw_start is None or raw_end is None:
        return jsonify({"error": "start_time dan end_time wajib disertakan."}), 400
    if isinstance(raw_start, bool) or isinstance(raw_end, bool):
        return jsonify({"error": "start_time dan end_time tidak boleh berupa boolean."}), 400

    try:
        start_time = float(raw_start)
        end_time = float(raw_end)
    except (TypeError, ValueError):
        return jsonify({"error": "Detik in/out harus berupa angka."}), 400

    if not (math.isfinite(start_time) and math.isfinite(end_time)):
        return jsonify({"error": "Detik in/out harus berupa bilangan finite (bukan NaN atau Infinity)."}), 400

    if start_time < 0:
        return jsonify({"error": "start_time tidak boleh kurang dari 0."}), 400

    if end_time <= start_time:
        return jsonify({"error": "Timestamp in/out tidak valid (end_time harus lebih besar dari start_time)."}), 400

    if (end_time - start_time) < 0.5:
        return jsonify({"error": "Durasi rentang klip terlalu pendek (minimal 0.5 detik)."}), 400

    # 2. Validate clip_index strictly (Finding A-07)
    raw_idx = data.get("clip_index")
    if raw_idx is None or isinstance(raw_idx, bool):
        return jsonify({"error": "clip_index wajib disertakan dan tidak boleh berupa boolean."}), 400

    if isinstance(raw_idx, float):
        if not raw_idx.is_integer():
            return jsonify({"error": f"clip_index harus berupa bilangan bulat, bukan desimal ({raw_idx})."}), 400
        clip_index = int(raw_idx)
    elif isinstance(raw_idx, str):
        raw_idx_str = raw_idx.strip()
        if not raw_idx_str.isdigit():
            return jsonify({"error": f"clip_index harus berupa bilangan bulat positif ('{raw_idx}')."}), 400
        clip_index = int(raw_idx_str)
    elif isinstance(raw_idx, int):
        clip_index = raw_idx
    else:
        return jsonify({"error": "clip_index harus berupa bilangan bulat."}), 400

    if clip_index < 1:
        return jsonify({"error": "clip_index harus berupa bilangan bulat positif."}), 400

    expected_filename = f"short_{clip_index:02d}.mp4"
    existing_file = target_dir / expected_filename

    # Exact match for filename if provided (Finding A-07)
    req_filename = data.get("filename")
    if req_filename is not None:
        if not isinstance(req_filename, str) or req_filename.strip() != expected_filename:
            return jsonify({"error": f"Nama file klip tidak valid atau tidak cocok dengan clip_index: '{req_filename}' != '{expected_filename}'."}), 400

    # 3. Resolve session source and metadata
    source_path, job_data, error_msg = resolve_session_source(session_folder)
    if error_msg:
        return jsonify({"error": error_msg}), 404

    # 4. Registry and existing file validation (Finding A-07: no arbitrary new clips allowed)
    res_val = job_data.get("result") if job_data else None
    result_dict = res_val if isinstance(res_val, dict) else {}
    session_shorts = result_dict.get("shorts", [])
    valid_indices = set()
    for idx, s in enumerate(session_shorts, 1):
        s_idx = s.get("clip_index")
        if s_idx is not None and isinstance(s_idx, int) and not isinstance(s_idx, bool):
            valid_indices.add(s_idx)
        else:
            valid_indices.add(idx)

    is_registered = bool(session_shorts and (clip_index in valid_indices))
    is_existing_file = existing_file.is_file()

    if not is_registered and not is_existing_file:
        return jsonify({"error": f"Klip #{clip_index} ({expected_filename}) tidak terdaftar dalam sesi ini dan file tidak ada di disk."}), 400

    # 5. Determine ground-truth media duration using probe_media_duration (Finding A-04)
    source_duration = probe_media_duration(source_path)
    if source_duration is None or source_duration <= 0:
        return jsonify({"error": "Durasi media video sumber tidak dapat diverifikasi secara valid. Pemotongan dibatalkan."}), 400

    if start_time >= source_duration:
        return jsonify({"error": f"start_time ({start_time:.1f}s) melebihi durasi video sumber ({source_duration:.1f}s)."}), 400

    if end_time > source_duration + 0.5:
        return jsonify({"error": f"end_time ({end_time:.1f}s) melebihi durasi video sumber ({source_duration:.1f}s)."}), 400

    effective_end_time = min(end_time, source_duration)
    effective_duration = effective_end_time - start_time
    if effective_duration < 0.5:
        return jsonify({"error": "Durasi rentang klip efektif terlalu pendek (minimal 0.5 detik)."}), 400

    aspect_ratio = str(data.get("aspect_ratio") or "9:16").strip()
    if aspect_ratio not in ("9:16", "1:1", "16:9"):
        aspect_ratio = "9:16"

    raw_framing = data.get("framing_mode", "podcast")
    if not isinstance(raw_framing, str) or raw_framing.strip().lower() not in ("podcast", "single", "center", "gaming", "dual"):
        framing_mode = "podcast"
    else:
        framing_mode = raw_framing.strip().lower()

    raw_preset = data.get("gaming_preset", "auto")
    valid_presets = (
        "auto", "auto_detect", "clean_2layer", "clean_2layer_cam_top", "clean_2layer_cam_bottom",
        "clean_2layer_bottom_right", "clean_2layer_bottom_left",
        "clean_2layer_top_right", "clean_2layer_top_left", "discord_top_cam_bottom_right",
        "discord_left_cam_top_right", "custom"
    )
    if not isinstance(raw_preset, str) or raw_preset.strip().lower() not in valid_presets:
        gaming_preset = "auto"
    else:
        gaming_preset = raw_preset.strip().lower()

    raw_layout = data.get("gaming_layout")
    gaming_layout = str(raw_layout).strip().lower() if raw_layout in ("cam_top", "cam_bottom") else None

    gaming_custom_box = validate_and_sanitize_gaming_box(data.get("gaming_custom_box"))

    raw_sub = data.get("subtitle_style", "karaoke")
    valid_sub_styles = (
        "karaoke", "kinetic", "classic", "none",
        "hormozi", "tiktok_punch", "devon_bold", "vox_box", "ali_abdaal",
        "aesthetic", "mrbeast", "karaoke_bounce", "cyber_neon", "retro_synth",
        "luxury_gold", "gaming_rage", "clean_bottom_bar", "comic_pow",
        "nas_daily", "netflix_sub", "matrix_hacker", "dan_koe", "fire_flame", "pastel_vlog",
        "hormozi_emerald", "hormozi_fire", "vox_cinema", "ali_cyan", "aesthetic_warm", "mrbeast_yellow",
    )
    if not isinstance(raw_sub, str) or raw_sub.strip().lower() not in valid_sub_styles:
        subtitle_style = "karaoke"
    else:
        subtitle_style = raw_sub.strip().lower()

    raw_font = data.get("font_family")
    font_family = str(raw_font).strip() if (raw_font and isinstance(raw_font, str)) else None

    burn_subtitles_flag = bool(data.get("burn_subtitles", True))
    if not burn_subtitles_flag:
        subtitle_style = "none"

    title = str(data.get("title") or "Klip Hasil Edit").strip()
    hook_sentence = str(data.get("hook_sentence") or "").strip()

    # Register with session gate to prevent concurrent session deletion
    allowed, err_msg = session_gate.register_editor_start(session_folder, clip_index)
    if not allowed:
        return jsonify({"error": err_msg or "Sesi sedang dalam proses penghapusan."}), 409

    # Per-clip locking for render execution
    clip_lock = get_clip_lock(session_folder, clip_index)
    acquired = clip_lock.acquire(timeout=30.0)
    if not acquired:
        session_gate.unregister_editor_done(session_folder, clip_index)
        return jsonify({"error": f"Klip #{clip_index} sedang diproses oleh permintaan lain. Silakan coba kembali."}), 409

    rev_id = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    staged_out_filename = f".tmp_short_{clip_index:02d}_{rev_id}.mp4"
    staged_out_path = target_dir / staged_out_filename
    staged_vtt_path = target_dir / f".tmp_short_{clip_index:02d}_{rev_id}.vtt"
    final_filename = expected_filename
    final_out_path = target_dir / final_filename
    final_vtt_path = target_dir / f"short_{clip_index:02d}.vtt"

    backup_out_path = target_dir / f".bak_short_{clip_index:02d}_{rev_id}.mp4"
    backup_vtt_path = target_dir / f".bak_short_{clip_index:02d}_{rev_id}.vtt"

    preserve_backups = False

    try:
        # Load segments and untrusted_spans from session job JSON if available
        segments = []
        untrusted_spans = []
        if job_data:
            res_val = job_data.get("result")
            result_dict = res_val if isinstance(res_val, dict) else {}
            transcript_data = result_dict.get("transcript")
            if not isinstance(transcript_data, dict):
                transcript_data = {}
            segments = transcript_data.get("segments", [])
            untrusted_spans = transcript_data.get("untrusted_spans", [])

        # Override segments if custom subtitles/segments provided in request
        custom_segments = data.get("segments")
        if custom_segments is None:
            custom_segments = data.get("subtitles")
        if isinstance(custom_segments, list) and len(custom_segments) > 0:
            parsed_custom = []
            for seg in custom_segments:
                if isinstance(seg, dict) and "start" in seg and "end" in seg and "text" in seg:
                    try:
                        s_st = float(seg["start"])
                        s_et = float(seg["end"])
                        s_tx = str(seg["text"]).strip()
                        if s_et > s_st and s_tx:
                            # Auto-adjust if timestamps were sent relative to clip start
                            if s_et <= (effective_duration + 1.0) and start_time > 0 and s_st < start_time:
                                s_st += start_time
                                s_et += start_time
                            parsed_custom.append({
                                "start": s_st,
                                "end": s_et,
                                "text": s_tx,
                                "words": seg.get("words", []) if isinstance(seg.get("words"), list) else []
                            })
                    except (ValueError, TypeError):
                        continue
            if parsed_custom:
                segments = parsed_custom


        from shorts_generator.local.clipper import crop_clip_local
        crop_clip_local(
            source_path=source_path,
            start_time=start_time,
            end_time=effective_end_time,
            aspect_ratio=aspect_ratio,
            out_path=str(staged_out_path),
            segments=segments,
            burn_subtitles=burn_subtitles_flag,
            source_duration=source_duration,
            untrusted_spans=untrusted_spans,
            framing_mode=framing_mode,
            subtitle_style=subtitle_style,
            font_family=font_family,
            gaming_preset=gaming_preset,
            gaming_custom_box=gaming_custom_box,
            gaming_layout=gaming_layout,
            enable_sfx=bool(data.get("enable_sfx", True)),
            remove_silence=bool(data.get("remove_silence", False)),
        )

        # 5. Staging Verification (Finding A-05): Check decodable media and duration match
        verify_rendered_video(staged_out_path, expected_duration=effective_duration, min_duration=0.4)

        has_new_vtt = staged_vtt_path.exists() and staged_vtt_path.stat().st_size > 0

        # Backup existing artifacts before promotion for transactional consistency (Finding A-03)
        has_old_out = final_out_path.exists()
        has_old_vtt = final_vtt_path.exists()
        if has_old_out:
            shutil.copy2(str(final_out_path), str(backup_out_path))
        if has_old_vtt:
            shutil.copy2(str(final_vtt_path), str(backup_vtt_path))

        # 2. Acquire session lock to read-modify-write metadata without lost updates (Finding A-02)
        session_lock = get_session_lock(session_folder)
        with session_lock:
            # Re-read the latest job JSON fresh inside the session lock
            job_jsons = list(target_dir.glob("job_*.json"))
            job_file = job_jsons[0] if job_jsons else None
            tmp_meta = None

            updated_clip = {
                "title": title,
                "hook_sentence": hook_sentence,
                "start_time": start_time,
                "end_time": effective_end_time,
                "score": data.get("score"),
                "aspect_ratio": aspect_ratio,
                "framing_mode": framing_mode,
                "subtitle_style": subtitle_style,
                "font_family": font_family,
                "gaming_preset": gaming_preset,
                "gaming_layout": gaming_layout,
                "gaming_custom_box": gaming_custom_box,
                "clip_url": str(final_out_path),
                "web_url": f"/output/{session_folder}/{final_filename}?v={rev_id}",
                "vtt_url": f"/output/{session_folder}/short_{clip_index:02d}.vtt?v={rev_id}" if has_new_vtt else None,
                "filename": final_filename,
                "clip_index": clip_index,
                "folder_name": session_folder,
                "rev_id": rev_id,
                "burn_subtitles": burn_subtitles_flag and subtitle_style != "none",
            }

            if job_file:
                with open(job_file, "r", encoding="utf-8") as f:
                    jdata = json.load(f)
                res_val = jdata.get("result")
                result_dict = res_val if isinstance(res_val, dict) else {}
                shorts_list = result_dict.get("shorts", [])
                found = False
                for idx, s in enumerate(shorts_list):
                    s_idx = s.get("clip_index")
                    if s_idx is None:
                        s_idx = idx + 1
                    if s.get("filename") == final_filename or s_idx == clip_index:
                        shorts_list[idx] = {**s, **updated_clip}
                        found = True
                        break
                if not found:
                    shorts_list.append(updated_clip)
                jdata.setdefault("result", {})["shorts"] = shorts_list

                tmp_meta = job_file.with_name(f"{job_file.name}.tmp_{rev_id}")
                with open(tmp_meta, "w", encoding="utf-8") as f:
                    json.dump(jdata, f, indent=2)

            # Atomic promotion: replace video, replace/delete vtt, replace metadata
            promoted_video = False
            promoted_vtt = False
            unlinked_old_vtt = False

            try:
                os.replace(str(staged_out_path), str(final_out_path))
                promoted_video = True

                if has_new_vtt:
                    os.replace(str(staged_vtt_path), str(final_vtt_path))
                    promoted_vtt = True
                else:
                    # Finding A-06: if new revision has no subtitles, remove old stale VTT
                    # Note: Any failure to delete old VTT must abort transaction and rollback
                    if final_vtt_path.exists():
                        final_vtt_path.unlink()
                        unlinked_old_vtt = True

                if job_file and tmp_meta:
                    os.replace(str(tmp_meta), str(job_file))

            except Exception as commit_err:
                # Rollback on any failure during promotion (Finding A-03)
                restore_errors = []

                if promoted_video:
                    if has_old_out:
                        if backup_out_path.exists():
                            try:
                                os.replace(str(backup_out_path), str(final_out_path))
                            except Exception as r_err:
                                restore_errors.append(f"Gagal restore video lama: {r_err}")
                        else:
                            restore_errors.append("Backup video lama tidak ditemukan untuk restore.")
                    else:
                        # No old video existed initially: remove the promoted video!
                        try:
                            if final_out_path.exists():
                                final_out_path.unlink()
                        except Exception as r_err:
                            restore_errors.append(f"Gagal menghapus video baru yang belum terkomit: {r_err}")

                if promoted_vtt:
                    if has_old_vtt:
                        if backup_vtt_path.exists():
                            try:
                                os.replace(str(backup_vtt_path), str(final_vtt_path))
                            except Exception as r_err:
                                restore_errors.append(f"Gagal restore VTT lama: {r_err}")
                        else:
                            restore_errors.append("Backup VTT lama tidak ditemukan untuk restore.")
                    else:
                        # No old VTT existed initially: remove the promoted VTT!
                        try:
                            if final_vtt_path.exists():
                                final_vtt_path.unlink()
                        except Exception as r_err:
                            restore_errors.append(f"Gagal menghapus VTT baru yang belum terkomit: {r_err}")
                elif unlinked_old_vtt:
                    # Old VTT was unlinked, but metadata commit failed: restore old VTT!
                    if has_old_vtt:
                        if backup_vtt_path.exists():
                            try:
                                os.replace(str(backup_vtt_path), str(final_vtt_path))
                            except Exception as r_err:
                                restore_errors.append(f"Gagal restore VTT lama setelah unlinking: {r_err}")
                        else:
                            restore_errors.append("Backup VTT lama tidak ditemukan untuk restore setelah unlinking.")

                if tmp_meta and tmp_meta.exists():
                    try:
                        tmp_meta.unlink()
                    except Exception:
                        pass

                if restore_errors:
                    preserve_backups = True
                    raise RuntimeError(f"Gagal commit dan rollback mengalami error ({'; '.join(restore_errors)}). Backup dipertahankan untuk pemulihan: {commit_err}")

                # Rollback succeeded cleanly, any unused backups can be removed
                if backup_out_path.exists():
                    try:
                        backup_out_path.unlink()
                    except Exception:
                        pass
                if backup_vtt_path.exists():
                    try:
                        backup_vtt_path.unlink()
                    except Exception:
                        pass

                raise RuntimeError(f"Gagal mempublikasikan hasil render secara konsisten (rollback berhasil): {commit_err}")

        # Promotion completed successfully: clean up backup files
        if backup_out_path.exists():
            try:
                backup_out_path.unlink()
            except Exception:
                pass
        if backup_vtt_path.exists():
            try:
                backup_vtt_path.unlink()
            except Exception:
                pass

        return jsonify({"success": True, "clip": updated_clip})

    except Exception as e:
        import traceback
        report_error_to_reef_flow(
            title=f"[Editor Error] Gagal merender klip #{clip_index}",
            description=f"Folder: {session_folder}\nClip Index: {clip_index}\nError: {e}\n\nStack Trace:\n{traceback.format_exc()}",
            priority="HIGH",
        )
        # Cleanup temporary files on failure
        if staged_out_path.exists():
            try:
                staged_out_path.unlink()
            except Exception:
                pass
        if staged_vtt_path.exists():
            try:
                staged_vtt_path.unlink()
            except Exception:
                pass
        if not preserve_backups:
            if backup_out_path.exists():
                try:
                    backup_out_path.unlink()
                except Exception:
                    pass
            if backup_vtt_path.exists():
                try:
                    backup_vtt_path.unlink()
                except Exception:
                    pass
        return jsonify({"error": f"Gagal merender klip: {e}"}), 500

    finally:
        try:
            clip_lock.release()
        finally:
            session_gate.unregister_editor_done(session_folder, clip_index)


@app.route("/api/report-error", methods=["POST"])
def api_report_error():
    """Client error reporting proxy to Reef Flow (avoids exposing API keys in frontend)."""
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "Client Error").strip()
    description = str(data.get("description") or "").strip()
    priority = str(data.get("priority") or "HIGH").strip().upper()
    status = str(data.get("status") or "TODO").strip().upper()
    report_error_to_reef_flow(title=title, description=description, priority=priority, status=status)
    return jsonify({"status": "reported"}), 200


@app.errorhandler(500)
def internal_server_error_handler(e):
    import traceback
    report_error_to_reef_flow(
        title=f"[Unhandled 500] {request.method} {request.path}",
        description=f"Path: {request.path}\nMethod: {request.method}\nError: {e}\n\nStack Trace:\n{traceback.format_exc()}",
        priority="URGENT",
    )
    return jsonify({"error": "Terjadi kesalahan internal server."}), 500


@app.errorhandler(Exception)
def unhandled_exception_handler(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        if e.code and e.code < 500:
            return e
    import traceback
    report_error_to_reef_flow(
        title=f"[Unhandled Exception] {request.method} {request.path}: {str(e)[:60]}",
        description=f"Path: {request.path}\nMethod: {request.method}\nError: {e}\n\nStack Trace:\n{traceback.format_exc()}",
        priority="URGENT",
    )
    return jsonify({"error": f"Internal server error: {e}"}), 500


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    print(f"\n=======================================================")
    print(f"🚀 AI YouTube Shorts Generator Web UI is starting!")
    print(f"👉 Open in browser: http://{host}:{port}")
    print(f"=======================================================\n")
    app.run(host=host, port=port, debug=False, threaded=True)
