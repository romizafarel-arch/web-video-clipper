"""Job lifecycle and execution state manager for ShortsStudio.

Manages job states, concurrency control (single active job policy),
cooperative cancellation, subprocess lifecycle termination (FFmpeg),
execution timeouts, and persistence recovery.
"""
import copy
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("shorts_generator.job_manager")


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    CANCELING = "canceling"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELED = "canceled"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"

    ACTIVE_STATUSES = {QUEUED, RUNNING, CANCELING}
    TERMINAL_STATUSES = {COMPLETED, PARTIAL, FAILED, CANCELED, TIMEOUT, INTERRUPTED}


class JobConflictError(Exception):
    """Raised when attempting to admit a new job while an active job is still running."""
    pass


class JobCancelledException(Exception):
    """Raised when a job execution detects a cancellation signal."""
    pass


class JobTimeoutException(Exception):
    """Raised when a job execution exceeds its configured timeout duration."""
    pass


def mask_sensitive_keys(data: Any) -> Any:
    """Recursively mask or strip API keys from config/metadata dictionaries."""
    if not isinstance(data, dict):
        return data
    cleaned = copy.deepcopy(data)
    sensitive_keys = {
        "gemini_api_key",
        "openai_api_key",
        "muapi_api_key",
        "reef_flow_api_key",
        "api_key",
        "password",
        "secret",
    }
    for k, v in list(cleaned.items()):
        if isinstance(v, dict):
            cleaned[k] = mask_sensitive_keys(v)
        elif any(s in k.lower() for s in sensitive_keys):
            if isinstance(v, str) and v:
                if len(v) <= 8:
                    cleaned[k] = "••••••••"
                else:
                    cleaned[k] = f"{v[:4]}••••••••{v[-4:]}"
            else:
                cleaned[k] = None
    return cleaned


class JobContext:
    """Thread-safe context tracking execution, cancellation, and subprocesses for a single job."""

    def __init__(
        self,
        job_id: str,
        url: str,
        params: Dict[str, Any],
        timeout_seconds: float = 1800.0,
    ):
        self.job_id = job_id
        self.url = url
        self.params = params
        self.timeout_seconds = max(0.1, float(timeout_seconds))

        self.status = JobStatus.QUEUED
        self.stage = "queued"
        self.progress = 0
        self.logs: List[str] = []
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.cancel_reason: Optional[str] = None

        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.session_folder: Optional[str] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.is_timeout: bool = False

        self.completed_shorts: List[Dict[str, Any]] = []
        self.pipeline_context: Dict[str, Any] = {}

        self.cancel_event = threading.Event()
        self._lock = threading.RLock()
        self._subprocesses: Set[subprocess.Popen] = set()

    def register_subprocess(self, proc: subprocess.Popen) -> None:
        """Register an active child subprocess (e.g. FFmpeg) with this job."""
        with self._lock:
            self._subprocesses.add(proc)
            if self.cancel_event.is_set():
                self._terminate_single_process(proc)

    def unregister_subprocess(self, proc: subprocess.Popen) -> None:
        """Unregister a finished subprocess."""
        with self._lock:
            self._subprocesses.discard(proc)

    def _terminate_single_process(self, proc: subprocess.Popen) -> None:
        """Gracefully terminate a child process, escalating to kill if necessary."""
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=2.0)
        except Exception as e:
            logger.warning(f"Error terminating subprocess: {e}")

    def terminate_all_subprocesses(self) -> None:
        """Terminate all currently running child processes associated with this job."""
        with self._lock:
            procs = list(self._subprocesses)
        for proc in procs:
            self._terminate_single_process(proc)

    def request_cancel(self, reason: str = "Dibatalkan oleh pengguna.") -> Dict[str, Any]:
        """Request cancellation of this job. Idempotent and thread-safe."""
        with self._lock:
            if self.status in JobStatus.TERMINAL_STATUSES:
                return {
                    "job_id": self.job_id,
                    "status": self.status,
                    "message": "Pekerjaan sudah selesai atau sudah berada dalam status akhir.",
                    "already_terminal": True,
                }

            self.cancel_reason = reason
            self.cancel_event.set()
            self.terminate_all_subprocesses()

            if self.status == JobStatus.QUEUED:
                self.status = JobStatus.CANCELED
                self.stage = "canceled"
                self.ended_at = time.time()
                self.logs.append(f"\n[INFO] {reason} (sebelum pipeline berjalan)\n")
                return {
                    "job_id": self.job_id,
                    "status": self.status,
                    "message": "Pekerjaan dibatalkan sebelum memulai eksekusi.",
                    "already_terminal": True,
                }

            if self.status == JobStatus.RUNNING:
                self.status = JobStatus.CANCELING
                self.stage = "canceling"
                self.logs.append(f"\n[INFO] Permintaan pembatalan diterima: {reason}. Menghentikan proses...\n")
                return {
                    "job_id": self.job_id,
                    "status": self.status,
                    "message": "Sedang menghentikan pekerjaan...",
                    "already_terminal": False,
                }

            # If already CANCELING:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "message": "Sedang dalam proses penghentian.",
                "already_terminal": False,
            }

    def check_cancellation_or_timeout(self) -> None:
        """Cooperative checkpoint to be called between pipeline stages and clips."""
        if self.started_at:
            elapsed = time.time() - self.started_at
            if elapsed > self.timeout_seconds:
                with self._lock:
                    self.is_timeout = True
                    if self.status in JobStatus.ACTIVE_STATUSES:
                        self.status = JobStatus.CANCELING
                        self.stage = "canceling"
                        self.cancel_reason = (
                            f"Batas waktu pengerjaan terlampaui ({self.timeout_seconds:.1f} detik)."
                        )
                        self.cancel_event.set()
                        self.terminate_all_subprocesses()
                raise JobTimeoutException(self.cancel_reason)

        if self.cancel_event.is_set():
            if getattr(self, "is_timeout", False) or (self.cancel_reason and "Batas waktu" in self.cancel_reason):
                raise JobTimeoutException(self.cancel_reason or "Batas waktu pengerjaan terlampaui.")
            raise JobCancelledException(self.cancel_reason or "Pekerjaan dibatalkan oleh pengguna.")

    def transition_to(
        self,
        new_status: str,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Safely transition job status enforcing terminal immutability."""
        with self._lock:
            # If already in a terminal state, DO NOT allow overwriting!
            if self.status in JobStatus.TERMINAL_STATUSES:
                logger.warning(
                    f"Job {self.job_id} already in terminal state '{self.status}', ignoring transition to '{new_status}'"
                )
                return False

            # If currently CANCELING, late completion MUST NOT mark job as completed!
            if self.status == JobStatus.CANCELING and new_status == JobStatus.COMPLETED:
                valid_count = 0
                if result and isinstance(result, dict):
                    valid_count = sum(1 for s in result.get("shorts", []) if s.get("clip_url"))
                if valid_count > 0:
                    new_status = JobStatus.PARTIAL
                    stage = "partial"
                else:
                    is_to = getattr(self, "is_timeout", False) or (self.cancel_reason and "Batas waktu" in self.cancel_reason)
                    new_status = JobStatus.TIMEOUT if is_to else JobStatus.CANCELED
                    stage = "timeout" if is_to else "canceled"

            self.status = new_status
            if stage is not None:
                self.stage = stage
            if progress is not None:
                self.progress = progress
            if error is not None:
                self.error = error
            if result is not None:
                self.result = result

            if new_status in JobStatus.TERMINAL_STATUSES:
                self.ended_at = time.time()
                # Ensure all child processes are killed and unregistered
                self.terminate_all_subprocesses()

            return True

    def emit_log(self, message: str) -> None:
        """Thread-safe append to job logs, update stage/progress, and mirror to process stdout."""
        if not message:
            return
        formatted = message if message.endswith("\n") else message + "\n"
        with self._lock:
            self.logs.append(formatted)
            if self.status not in JobStatus.TERMINAL_STATUSES:
                lower = message.lower()
                if "[download" in lower or "yt-dlp" in lower or "downloading" in lower:
                    self.stage = "downloading"
                    self.progress = max(self.progress, 20)
                elif "[transcribe" in lower or "whisper" in lower or "gemini_audio" in lower:
                    self.stage = "transcribing"
                    self.progress = max(self.progress, 45)
                elif "[highlights" in lower or "llm" in lower or "candidates" in lower:
                    self.stage = "analyzing"
                    self.progress = max(self.progress, 70)
                elif "[clip" in lower or "cropping" in lower or "ffmpeg" in lower:
                    self.stage = "cropping"
                    self.progress = max(self.progress, 85)
        try:
            out = sys.__stdout__ if sys.__stdout__ is not None else sys.stdout
            out.write(formatted)
            out.flush()
        except Exception:
            pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert job state to serializable dictionary for JSON API responses."""
        with self._lock:
            raw_logs = "".join(self.logs)
            now = time.time()
            elapsed = int((self.ended_at or now) - (self.started_at or self.created_at))
            return {
                "job_id": self.job_id,
                "url": self.url,
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "logs": raw_logs,
                "result": self.result,
                "error": self.error,
                "cancel_reason": self.cancel_reason,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "elapsed_seconds": max(0, elapsed),
                "session_folder": self.session_folder,
            }


class JobManager:
    """Central registry and admission controller for ShortsStudio jobs."""

    def __init__(self, timeout_seconds: float = 1800.0):
        self.default_timeout = timeout_seconds
        self._jobs: Dict[str, JobContext] = {}
        self._admission_lock = threading.RLock()

    def admit_job(
        self,
        job_id: str,
        url: str,
        params: Dict[str, Any],
        timeout_seconds: Optional[float] = None,
    ) -> JobContext:
        """Atomically admit a new generation job, strictly rejecting if another job is active."""
        with self._admission_lock:
            active = self.get_active_job()
            if active:
                raise JobConflictError(
                    f"Sedang ada proses generasi yang aktif (Job ID: {active.job_id}, Status: {active.status}). "
                    "Harap tunggu hingga selesai atau batalkan pekerjaan tersebut."
                )

            timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout
            ctx = JobContext(job_id=job_id, url=url, params=params, timeout_seconds=timeout)
            self._jobs[job_id] = ctx
            return ctx

    def get_active_job(self) -> Optional[JobContext]:
        """Return the currently active job (queued, running, canceling, or worker still alive) if any."""
        with self._admission_lock:
            for job in self._jobs.values():
                if job.status in JobStatus.ACTIVE_STATUSES:
                    return job
                if job.worker_thread and job.worker_thread.is_alive() and job.worker_thread != threading.current_thread():
                    return job
            return None

    def get_job(self, job_id: str) -> Optional[JobContext]:
        """Return job by ID from memory."""
        with self._admission_lock:
            return self._jobs.get(job_id)

    def request_cancel(self, job_id: str, reason: str = "Dibatalkan oleh pengguna.") -> Dict[str, Any]:
        """Idempotently request cancellation of a job by ID."""
        with self._admission_lock:
            job = self._jobs.get(job_id)
            if not job:
                return {"error": "Pekerjaan tidak ditemukan.", "not_found": True}
            return job.request_cancel(reason=reason)

    def recover_interrupted_jobs(self, output_dir: Path) -> int:
        """Scan session folders and mark any dangling active jobs as interrupted upon boot."""
        if not output_dir.exists():
            return 0

        recovered_count = 0
        job_files = list(output_dir.glob("**/job_*.json"))
        for jf in job_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                status = data.get("status")
                # If disk status was active when server stopped/crashed:
                if status in JobStatus.ACTIVE_STATUSES or (status is None and not data.get("result")):
                    data["status"] = JobStatus.INTERRUPTED
                    data["stage"] = "interrupted"
                    data["error"] = "Pekerjaan terputus saat aplikasi dihentikan atau dimuat ulang."
                    data["ended_at"] = datetime.now().isoformat()

                    tmp_file = jf.with_suffix(".tmp_recover")
                    with open(tmp_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    tmp_file.replace(jf)
                    recovered_count += 1
            except Exception as e:
                logger.warning(f"Could not recover metadata file {jf}: {e}")

        return recovered_count


# Global singleton instance
job_manager = JobManager()


def log_job_message(message: str, job_ctx: Optional[Any] = None) -> None:
    """Helper to log via job_ctx if present, falling back to process stdout."""
    if job_ctx is not None and hasattr(job_ctx, "emit_log"):
        job_ctx.emit_log(message)
    else:
        try:
            out = sys.__stdout__ if sys.__stdout__ is not None else sys.stdout
            out.write(message if message.endswith("\n") else message + "\n")
            out.flush()
        except Exception:
            print(message, flush=True)

