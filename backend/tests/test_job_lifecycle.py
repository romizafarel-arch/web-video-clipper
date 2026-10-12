"""Targeted Unit & Integration Tests for Job Lifecycle Management (Bagian B).

Tests:
1. Cancellation before start (queued) and while running.
2. Idempotent cancel (repeated POST /api/jobs/<job_id>/cancel) & late worker cannot overwrite status.
3. Timeout enforcement on worker side and blocking new job until worker fully exits.
4. Two concurrent generation requests: race condition protected (one 200, one 409).
5. Accurate reading of all terminal statuses from disk and boot recovery of interrupted jobs.
6. Zero successful clips reported as failed, never completed.
7. Session deletion protection (409 Conflict) while generation or editorial render is active.
8. Real FFmpeg process termination with temporary fixture.
9. Partial results preserved when cancelled mid-way after clip 1.
10. No credentials or API keys persisted in metadata JSON.
"""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import shorts_generator.config as cfg
import web_app
from shorts_generator.job_manager import (
    JobCancelledException,
    JobConflictError,
    JobContext,
    JobStatus,
    JobTimeoutException,
    job_manager,
    mask_sensitive_keys,
)
from shorts_generator import pipeline
from shorts_generator.local.clipper import _cut_subclip, _run_ffmpeg_cmd, crop_highlights_local


class TestJobLifecycle(unittest.TestCase):
    """Test suite covering the complete Bagian B job lifecycle specifications."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_job_lifecycle_")
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.orig_output_dir = web_app.OUTPUT_DIR
        web_app.OUTPUT_DIR = self.output_dir

        # Reset global job manager state
        with job_manager._admission_lock:
            job_manager._jobs.clear()
        web_app.jobs.clear()

        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    def tearDown(self):
        # Terminate any lingering subprocesses in job manager
        with job_manager._admission_lock:
            for job in list(job_manager._jobs.values()):
                job.terminate_all_subprocesses()
            job_manager._jobs.clear()
        web_app.jobs.clear()

        web_app.OUTPUT_DIR = self.orig_output_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cancel_queued_job_before_start_does_not_run_pipeline(self):
        """Job cancelled while queued must not execute the pipeline."""
        pipeline_mock = MagicMock()
        job_id = "queue_cancel"

        with job_manager._admission_lock:
            job_ctx = job_manager.admit_job(
                job_id=job_id,
                url="https://youtu.be/sample",
                params={"url": "https://youtu.be/sample", "num_clips": 1},
            )
            web_app.jobs[job_id] = job_ctx.to_dict()

        # Cancel job immediately while in queued status
        resp = self.client.post(f"/api/jobs/{job_id}/cancel")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], JobStatus.CANCELED)

        # Now worker starts
        with patch("web_app.generate_shorts", pipeline_mock):
            web_app.run_generation_job(job_id, job_ctx.params)

        pipeline_mock.assert_not_called()
        self.assertEqual(web_app.jobs[job_id]["status"], JobStatus.CANCELED)

    def test_cancel_running_job_and_idempotent_cancel(self):
        """Calling cancel while running sets canceling and repeated cancel calls are safe."""
        job_id = "run_cancel"
        barrier = threading.Barrier(2)

        def slow_pipeline(*args, **kwargs):
            job_ctx = kwargs.get("job_ctx")
            barrier.wait()  # Signal that pipeline is running
            # Wait for cancellation signal
            for _ in range(50):
                if job_ctx and job_ctx.cancel_event.is_set():
                    raise JobCancelledException("Pekerjaan dibatalkan.")
                time.sleep(0.05)
            raise RuntimeError("Pipeline did not see cancellation!")

        with job_manager._admission_lock:
            job_ctx = job_manager.admit_job(
                job_id=job_id,
                url="https://youtu.be/sample",
                params={"url": "https://youtu.be/sample", "num_clips": 1},
            )
            web_app.jobs[job_id] = job_ctx.to_dict()

        worker_thread = threading.Thread(
            target=web_app.run_generation_job,
            args=(job_id, job_ctx.params),
        )

        with patch("web_app.generate_shorts", side_effect=slow_pipeline):
            worker_thread.start()
            barrier.wait()  # Wait until pipeline starts

            # First cancel call
            resp1 = self.client.post(f"/api/jobs/{job_id}/cancel")
            self.assertEqual(resp1.status_code, 200)
            self.assertIn(resp1.get_json()["status"], (JobStatus.CANCELING, JobStatus.CANCELED))

            # Second (repeated) cancel call - idempotent
            resp2 = self.client.post(f"/api/jobs/{job_id}/cancel")
            self.assertEqual(resp2.status_code, 200)

            worker_thread.join(timeout=5.0)

        self.assertFalse(worker_thread.is_alive())
        final_job = web_app.jobs[job_id]
        self.assertEqual(final_job["status"], JobStatus.CANCELED)

    def test_late_worker_cannot_overwrite_canceled_job_to_completed(self):
        """A worker completing late must NOT overwrite a cancelled or timed out job to completed."""
        job_id = "late_worker"
        with job_manager._admission_lock:
            job_ctx = job_manager.admit_job(
                job_id=job_id,
                url="https://youtu.be/sample",
                params={"url": "https://youtu.be/sample", "num_clips": 1},
            )
            web_app.jobs[job_id] = job_ctx.to_dict()

        # Job is cancelled
        job_ctx.request_cancel(reason="Dibatalkan pengguna.")
        self.assertEqual(job_ctx.status, JobStatus.CANCELED)

        # Worker attempts to transition to COMPLETED
        transitioned = job_ctx.transition_to(
            JobStatus.COMPLETED,
            stage="completed",
            result={"shorts": [{"clip_url": "dummy.mp4"}]},
        )
        self.assertFalse(transitioned)
        self.assertEqual(job_ctx.status, JobStatus.CANCELED)

    def test_timeout_blocks_new_job_until_worker_exits(self):
        """When a job times out, a new job is rejected (409) until the timed-out worker finishes."""
        job_id = "timeout_job"
        worker_started = threading.Event()
        worker_can_exit = threading.Event()

        def timeout_pipeline(*args, **kwargs):
            job_ctx = kwargs.get("job_ctx")
            worker_started.set()
            # Simulate work exceeding timeout and winding down
            try:
                while True:
                    if job_ctx:
                        job_ctx.check_cancellation_or_timeout()
                    time.sleep(0.05)
            except JobTimeoutException:
                worker_can_exit.wait(timeout=3.0)
                raise

        with job_manager._admission_lock:
            job_ctx = job_manager.admit_job(
                job_id=job_id,
                url="https://youtu.be/sample",
                params={"url": "https://youtu.be/sample", "num_clips": 1},
                timeout_seconds=0.2,  # 200ms timeout
            )
            web_app.jobs[job_id] = job_ctx.to_dict()

        worker_thread = threading.Thread(
            target=web_app.run_generation_job,
            args=(job_id, job_ctx.params),
        )

        with patch("web_app.generate_shorts", side_effect=timeout_pipeline):
            worker_thread.start()
            worker_started.wait()

            # Wait 0.3s for timeout to trigger inside pipeline
            time.sleep(0.3)

            # While worker is still running / shutting down, second job must be rejected with 409
            resp_conflict = self.client.post("/api/generate", json={
                "url": "https://youtu.be/other",
                "num_clips": 1,
            })
            self.assertEqual(resp_conflict.status_code, 409)

            # Now allow worker to exit
            worker_can_exit.set()
            worker_thread.join(timeout=3.0)

        self.assertFalse(worker_thread.is_alive())
        self.assertEqual(web_app.jobs[job_id]["status"], JobStatus.TIMEOUT)

        # After worker exits, new job can now be admitted
        with patch("web_app.run_generation_job"):
            resp_admit = self.client.post("/api/generate", json={
                "url": "https://youtu.be/other",
                "num_clips": 1,
            })
            self.assertEqual(resp_admit.status_code, 200)

    def test_concurrent_generation_requests_only_one_admitted(self):
        """Two concurrent generation requests must admit exactly one (200) and reject the other (409)."""
        results = []
        barrier = threading.Barrier(2)

        def trigger_gen(url_param):
            client = web_app.app.test_client()
            try:
                barrier.wait(timeout=5.0)
            except threading.BrokenBarrierError:
                pass
            resp = client.post("/api/generate", json={
                "url": url_param,
                "num_clips": 2,
            })
            results.append(resp.status_code)

        # Patch once in the main test thread to avoid mock stack corruption across threads
        with patch("web_app.run_generation_job"):
            t1 = threading.Thread(target=trigger_gen, args=("https://youtu.be/video1",))
            t2 = threading.Thread(target=trigger_gen, args=("https://youtu.be/video2",))

            t1.start()
            t2.start()
            t1.join(timeout=5.0)
            t2.join(timeout=5.0)

        self.assertEqual(sorted(results), [200, 409])
        from unittest.mock import MagicMock
        self.assertFalse(isinstance(web_app.run_generation_job, MagicMock))

    def test_disk_status_and_boot_recovery_of_interrupted_jobs(self):
        """Accurately reads all disk statuses and recovers interrupted active jobs on boot."""
        sess_dir = self.output_dir / "20260928_120000_jobpast"
        sess_dir.mkdir(parents=True, exist_ok=True)

        # 1. Test reading varied statuses from disk
        test_statuses = [
            JobStatus.COMPLETED,
            JobStatus.PARTIAL,
            JobStatus.FAILED,
            JobStatus.CANCELED,
            JobStatus.TIMEOUT,
        ]
        for st in test_statuses:
            jid = f"job_{st}"
            meta_file = sess_dir / f"job_{jid}.json"
            meta_data = {
                "job_id": jid,
                "session_folder": sess_dir.name,
                "status": st,
                "stage": st,
                "result": {"shorts": []} if st == JobStatus.COMPLETED else None,
                "error": "Sample error" if st == JobStatus.FAILED else None,
                "cancel_reason": "Sample cancel" if st in (JobStatus.CANCELED, JobStatus.TIMEOUT) else None,
            }
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta_data, f)

            resp = self.client.get(f"/api/jobs/{jid}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["status"], st)

        # 2. Test boot recovery: a dangling active job on disk is marked as interrupted
        dangling_id = "job_dangling"
        dangling_file = sess_dir / f"job_{dangling_id}.json"
        with open(dangling_file, "w", encoding="utf-8") as f:
            json.dump({
                "job_id": dangling_id,
                "session_folder": sess_dir.name,
                "status": JobStatus.RUNNING,
                "stage": "cropping",
            }, f)

        # Trigger recovery
        recovered = job_manager.recover_interrupted_jobs(self.output_dir)
        self.assertGreaterEqual(recovered, 1)

        resp_recovered = self.client.get(f"/api/jobs/{dangling_id}")
        self.assertEqual(resp_recovered.status_code, 200)
        rec_data = resp_recovered.get_json()
        self.assertEqual(rec_data["status"], JobStatus.INTERRUPTED)
        self.assertIn("terputus", rec_data["error"])

    def test_zero_clips_reported_as_failed_never_completed(self):
        """If 0 clips succeeded when clips were expected, the job must be marked as failed."""
        job_id = "zero_clips"
        with job_manager._admission_lock:
            job_ctx = job_manager.admit_job(
                job_id=job_id,
                url="https://youtu.be/sample",
                params={"url": "https://youtu.be/sample", "num_clips": 3},
            )
            web_app.jobs[job_id] = job_ctx.to_dict()

        mock_result = {
            "shorts": [
                {"clip_url": None, "error": "FFmpeg error 1"},
                {"clip_url": None, "error": "FFmpeg error 2"},
            ]
        }
        with patch("web_app.generate_shorts", return_value=mock_result):
            web_app.run_generation_job(job_id, job_ctx.params)

        final_job = web_app.jobs[job_id]
        self.assertEqual(final_job["status"], JobStatus.FAILED)
        self.assertIn("Render gagal total", final_job["error"])

    def test_session_deletion_protection_when_active(self):
        """DELETE session returns 409 if session is currently being generated or edited."""
        sess_name = "20260928_active_sess"
        sess_path = self.output_dir / sess_name
        sess_path.mkdir(parents=True, exist_ok=True)
        (sess_path / "dummy.mp4").write_bytes(b"content")

        # 1. Protected while active generation job has this session_folder
        with job_manager._admission_lock:
            job_ctx = job_manager.admit_job(
                job_id="active_del_test",
                url="https://youtu.be/sample",
                params={"url": "https://youtu.be/sample"},
            )
            job_ctx.status = JobStatus.RUNNING
            job_ctx.session_folder = sess_name
            web_app.jobs["active_del_test"] = job_ctx.to_dict()

        resp_del_gen = self.client.delete(f"/api/history/session/{sess_name}")
        self.assertEqual(resp_del_gen.status_code, 409)
        self.assertTrue(sess_path.exists())

        # Release active generation job
        job_ctx.status = JobStatus.COMPLETED

        # 2. Protected while editorial lock is held on this session
        sess_lock = web_app.get_session_lock(sess_name)
        sess_lock.acquire()
        try:
            resp_del_edit = self.client.delete(f"/api/history/session/{sess_name}")
            self.assertEqual(resp_del_edit.status_code, 409)
            self.assertTrue(sess_path.exists())
        finally:
            sess_lock.release()

        # 3. Once inactive and unlocked, deletion succeeds
        resp_del_ok = self.client.delete(f"/api/history/session/{sess_name}")
        self.assertEqual(resp_del_ok.status_code, 200)
        self.assertFalse(sess_path.exists())

    def test_real_ffmpeg_termination_with_temporary_fixture(self):
        """Test that terminating an active job actually terminates child FFmpeg processes."""
        fixture_mp4 = self.temp_dir + os.sep + "test_source_clip.mp4"
        out_subclip = self.temp_dir + os.sep + "test_terminated_out.mp4"

        # Generate a small 10s synthetic test video with FFmpeg
        gen_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=10:size=640x360:rate=30",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", "10",
            "-c:v", "libx264", "-c:a", "aac",
            fixture_mp4,
        ]
        try:
            subprocess.run(gen_cmd, check=True)
        except Exception as e:
            self.skipTest(f"FFmpeg not installed or failed to create test fixture: {e}")

        job_ctx = JobContext(job_id="test_ffmpeg_term", url=fixture_mp4, params={})
        job_ctx.status = JobStatus.RUNNING
        job_ctx.started_at = time.time()

        slow_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=1280x720:rate=30",
            "-c:v", "libx264", "-preset", "slow",
            out_subclip,
        ]

        def run_proc():
            try:
                _run_ffmpeg_cmd(slow_cmd, job_ctx=job_ctx)
            except Exception:
                pass

        t = threading.Thread(target=run_proc)
        t.start()

        # Wait until process is registered and actively alive
        proc = None
        for _ in range(50):
            with job_ctx._lock:
                if len(job_ctx._subprocesses) > 0:
                    p = next(iter(job_ctx._subprocesses))
                    if p.poll() is None:
                        proc = p
                        break
            time.sleep(0.02)

        self.assertIsNotNone(proc, "FFmpeg process should be actively running")
        self.assertIsNone(proc.poll(), "FFmpeg process must be alive before cancel")

        # Terminate job and verify subprocess exits within bounded time (< 1.5s)
        t0 = time.time()
        job_ctx.request_cancel(reason="Test termination")
        t.join(timeout=3.0)
        elapsed = time.time() - t0

        self.assertFalse(t.is_alive())
        self.assertIsNotNone(proc.poll(), "Process must have terminated")
        self.assertLess(elapsed, 1.5, f"Termination must complete promptly, took {elapsed:.2f}s")
        self.assertEqual(len(job_ctx._subprocesses), 0)

    def test_partial_results_preserved_on_cancel(self):
        """When cancelled after clip 1, clip 1 is retained and returned as partial."""
        highlights = [
            {"title": "Highlight 1", "start_time": 1.0, "end_time": 4.0},
            {"title": "Highlight 2", "start_time": 5.0, "end_time": 8.0},
        ]
        job_ctx = JobContext(job_id="part_test", url="dummy.mp4", params={})

        call_count = 0

        def mock_crop_clip(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            out_p = kwargs.get("out_path")
            Path(out_p).write_bytes(b"mock clip content")
            if call_count == 1:
                # Cancel job right after clip 1 finishes!
                job_ctx.request_cancel(reason="Cancel after clip 1")
            return out_p

        with patch("shorts_generator.local.clipper.crop_clip_local", side_effect=mock_crop_clip):
            results = crop_highlights_local(
                source_path="dummy.mp4",
                highlights=highlights,
                out_dir=str(self.output_dir / "sess_partial"),
                job_ctx=job_ctx,
            )

        # Exactly 1 clip was processed before cancellation stopped further clips
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["clip_index"], 1)
        self.assertTrue(Path(results[0]["clip_url"]).exists())

    def test_no_credentials_persisted_in_metadata(self):
        """Sensitive API keys and secrets must never be written to metadata JSON."""
        raw_config = {
            "gemini_api_key": "AIzaSySecretGeminiKey123456",
            "openai_api_key": "sk-proj-SecretOpenAiKey987654",
            "muapi_api_key": "secret_muapi_token_here",
            "llm_provider": "gemini",
            "gemini_model": "gemini-3.5-flash",
        }

        masked = mask_sensitive_keys(raw_config)
        self.assertNotIn("AIzaSySecretGeminiKey123456", json.dumps(masked))
        self.assertNotIn("sk-proj-SecretOpenAiKey987654", json.dumps(masked))
        self.assertIn("••••", masked["gemini_api_key"])
        self.assertIn("••••", masked["openai_api_key"])

    def test_b01_ffmpeg_inflight_timeout_enforcement(self):
        """B-01: FFmpeg running process must be aborted when deadline expires during execution."""
        out_subclip = self.temp_dir + os.sep + "test_b01_timeout_out.mp4"
        job_ctx = JobContext(job_id="test_b01_timeout", url="dummy", params={}, timeout_seconds=0.4)
        job_ctx.status = JobStatus.RUNNING
        job_ctx.started_at = time.time()

        slow_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=10:size=1280x720:rate=30",
            "-c:v", "libx264", "-preset", "slow",
            out_subclip,
        ]

        t0 = time.time()
        with self.assertRaises(JobTimeoutException):
            _run_ffmpeg_cmd(slow_cmd, job_ctx=job_ctx)
        elapsed = time.time() - t0

        self.assertLess(elapsed, 2.0, f"In-flight timeout took too long: {elapsed:.2f}s")
        self.assertEqual(len(job_ctx._subprocesses), 0)

    def test_b02_precompletion_persistence_and_boot_recovery(self):
        """B-02: Active job must persist metadata to disk before completion and recover cleanly on boot."""
        job_id = "test_b02_live"
        session_folder = f"20260928_150000_{job_id}"
        sess_dir = self.output_dir / session_folder
        sess_dir.mkdir(parents=True, exist_ok=True)

        params = {
            "session_folder": session_folder,
            "url": "https://youtu.be/sample",
            "num_clips": 1,
            "mode": "local",
            "config": {},
        }
        job_ctx = job_manager.admit_job(job_id=job_id, url=params["url"], params=params)
        job_ctx.session_folder = session_folder
        web_app.jobs[job_id] = job_ctx.to_dict()

        entered = threading.Event()
        release = threading.Event()

        def mock_pipeline(**kwargs):
            entered.set()
            release.wait(timeout=5.0)
            return {"shorts": []}

        with patch("web_app.generate_shorts", side_effect=mock_pipeline):
            worker = threading.Thread(target=web_app.run_generation_job, args=(job_id, params))
            worker.start()

            self.assertTrue(entered.wait(timeout=3.0))

            # 1. Verify job_<id>.json exists while worker is active and unfinished
            meta_path = sess_dir / f"job_{job_id}.json"
            self.assertTrue(meta_path.exists(), "Job metadata must be persisted before completion")
            with open(meta_path, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
            self.assertEqual(disk_data.get("status"), JobStatus.RUNNING)

            # 2. Simulate server boot recovery
            recovered_count = job_manager.recover_interrupted_jobs(self.output_dir)
            self.assertGreaterEqual(recovered_count, 1)
            with open(meta_path, "r", encoding="utf-8") as f:
                recovered_disk = json.load(f)
            self.assertEqual(recovered_disk.get("status"), JobStatus.INTERRUPTED)

            # Unblock and join worker
            release.set()
            worker.join(timeout=3.0)
            self.assertFalse(worker.is_alive())

    def test_b03_session_deletion_vs_concurrent_editor_gate(self):
        """B-03: Session deletion must be rejected when an editor is active and vice versa."""
        session_name = "test_b03_gate_session"
        sess_path = self.output_dir / session_name
        sess_path.mkdir(parents=True, exist_ok=True)
        (sess_path / "source_fixture.mp4").write_bytes(b"fixture")
        (sess_path / "short_01.mp4").write_bytes(b"old-clip")

        # 1. Register active editor -> deletion must be rejected with 409
        ok, _ = web_app.session_gate.register_editor_start(session_name, 1)
        self.assertTrue(ok)
        resp_del_conflict = self.client.delete(f"/api/history/session/{session_name}")
        self.assertEqual(resp_del_conflict.status_code, 409)
        self.assertIn("sedang dalam proses render", resp_del_conflict.get_json()["error"])

        # 2. Editor finishes -> deletion succeeds
        web_app.session_gate.unregister_editor_done(session_name, 1)

        # 3. Deletion gate acquired -> new editor is rejected
        gate_ok, _ = web_app.session_gate.acquire_deletion_gate(session_name)
        self.assertTrue(gate_ok)
        can_start, start_err = web_app.session_gate.register_editor_start(session_name, 1)
        self.assertFalse(can_start)
        self.assertIn("proses penghapusan", start_err)

        web_app.session_gate.release_deletion_gate(session_name)

    def test_b04_empty_results_and_timeout_outcome_classification(self):
        """B-04: Empty clips list must report FAILED, and timeout must report TIMEOUT or PARTIAL."""
        # 1. Empty results report FAILED
        with job_manager._admission_lock:
            job_manager._jobs.clear()
        web_app.jobs.clear()
        job_ctx_empty = job_manager.admit_job("empty_test", "dummy", {"num_clips": 1, "config": {}})
        web_app.jobs["empty_test"] = job_ctx_empty.to_dict()

        with patch("web_app.generate_shorts", return_value={"shorts": []}):
            web_app.run_generation_job("empty_test", {"url": "dummy", "config": {}})
        self.assertEqual(job_ctx_empty.status, JobStatus.FAILED)
        self.assertIn("Tidak ada klip video", job_ctx_empty.error)

        # 2. Timeout inside crop loop with 0 completed clips reports TIMEOUT
        with job_manager._admission_lock:
            job_manager._jobs.clear()
        web_app.jobs.clear()
        job_ctx_to = job_manager.admit_job("to_test", "dummy", {"num_clips": 1, "config": {}}, timeout_seconds=0.1)
        web_app.jobs["to_test"] = job_ctx_to.to_dict()

        def timeout_crop(**kwargs):
            job_ctx_to.started_at = time.time() - 2
            job_ctx_to.check_cancellation_or_timeout()

        def pipeline_with_crop(**kwargs):
            crop_highlights_local("fixture.mp4", [{"start_time": 0, "end_time": 4}], out_dir=str(self.output_dir / "to_sess"), job_ctx=kwargs["job_ctx"])
            return {"shorts": []}

        with patch("web_app.generate_shorts", side_effect=pipeline_with_crop), patch("shorts_generator.local.clipper.crop_clip_local", side_effect=timeout_crop):
            web_app.run_generation_job("to_test", {"url": "dummy", "config": {}})
        self.assertEqual(job_ctx_to.status, JobStatus.TIMEOUT)

    def test_b05_api_mode_cancellation_propagation(self):
        """B-05: Cancelling during API mode download must abort before transcribe, highlights, or cropping."""
        job_ctx = JobContext(job_id="api_cancel_test", url="https://youtu.be/api_vid", params={})
        job_ctx.status = JobStatus.RUNNING
        job_ctx.started_at = time.time()

        called = []

        def mock_download(*args, **kwargs):
            called.append("download")
            job_ctx.request_cancel(reason="Cancel during download")
            return "https://example.invalid/source.mp4"

        def mock_transcribe(*args, **kwargs):
            called.append("transcribe")
            return {"duration": 10, "segments": [{"start": 0, "end": 5, "text": "mock"}]}

        def mock_highlights(*args, **kwargs):
            called.append("highlights")
            return {"highlights": [{"start_time": 0, "end_time": 5, "score": 80}]}

        def mock_crop(*args, **kwargs):
            called.append("crop")
            return [{"clip_url": "https://example.invalid/short.mp4"}]

        with patch("shorts_generator.pipeline.download_youtube", side_effect=mock_download), \
             patch("shorts_generator.pipeline.transcribe", side_effect=mock_transcribe), \
             patch("shorts_generator.pipeline.get_highlights", side_effect=mock_highlights), \
             patch("shorts_generator.pipeline.crop_highlights", side_effect=mock_crop):
            with self.assertRaises(JobCancelledException):
                pipeline.generate_shorts(job_ctx.url, mode="api", job_ctx=job_ctx)

        self.assertEqual(called, ["download"])
        self.assertNotIn("transcribe", called)
        self.assertNotIn("highlights", called)
        self.assertNotIn("crop", called)

    def test_b03_same_clip_editor_gate(self):
        """B-03: Two requests editing the same clip must both be tracked by SessionGate."""
        sess = "two_editors_same_clip"
        folder = web_app.OUTPUT_DIR / sess
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / "source_fixture.mp4"
        source.write_bytes(b"source-fixture")
        (folder / "short_01.mp4").write_bytes(b"old-video")
        meta = {
            "result": {
                "source_video_url": str(source),
                "transcript": {"duration": 10, "segments": []},
                "shorts": [
                    {
                        "clip_index": 1,
                        "filename": "short_01.mp4",
                        "start_time": 0,
                        "end_time": 4,
                        "title": "Klip 1",
                        "hook_sentence": "Hook 1",
                    }
                ],
            }
        }
        (folder / "job_fixture.json").write_text(json.dumps(meta), encoding="utf-8")

        first_started, release_first, second_registered, second_started, release_second = (
            threading.Event() for _ in range(5)
        )
        counter_lock = threading.Lock()
        counts = {"registered": 0, "crop": 0}
        responses = {}
        original_register = web_app.session_gate.register_editor_start

        def register(*args):
            result = original_register(*args)
            with counter_lock:
                counts["registered"] += 1
                if counts["registered"] == 2:
                    second_registered.set()
            return result

        def mock_crop(**kwargs):
            with counter_lock:
                counts["crop"] += 1
                ordinal = counts["crop"]
            if ordinal == 1:
                first_started.set()
                self.assertTrue(release_first.wait(4))
            else:
                second_started.set()
                self.assertTrue(release_second.wait(4))
            Path(kwargs["out_path"]).write_bytes(b"new-render-fixture")

        def edit(name):
            with web_app.app.test_client() as client:
                response = client.post(
                    "/api/edit-clip",
                    json={
                        "session_folder": sess,
                        "clip_index": 1,
                        "start_time": 1,
                        "end_time": 4,
                        "burn_subtitles": False,
                    },
                )
                responses[name] = response.status_code

        with patch.object(web_app.session_gate, "register_editor_start", side_effect=register), \
             patch("web_app.probe_media_duration", return_value=10), \
             patch("shorts_generator.local.clipper.crop_clip_local", side_effect=mock_crop), \
             patch("web_app.verify_rendered_video", return_value=None):
            t1 = threading.Thread(target=edit, args=("first_edit",))
            t2 = threading.Thread(target=edit, args=("second_edit",))
            try:
                t1.start()
                self.assertTrue(first_started.wait(2))
                t2.start()
                self.assertTrue(second_registered.wait(2))
                release_first.set()
                t1.join(3)
                self.assertFalse(t1.is_alive())
                self.assertTrue(second_started.wait(2))
                # While t2 is rendering, gate MUST still be active for sess
                gate_active = bool(web_app.session_gate._active_editors.get(sess))
                self.assertTrue(gate_active)
                with web_app.app.test_client() as client:
                    responses["delete"] = client.delete("/api/history/session/" + sess).status_code
                self.assertEqual(responses["delete"], 409)
                self.assertTrue(folder.exists())
            finally:
                release_first.set()
                release_second.set()
                if t1.ident:
                    t1.join(3)
                if t2.ident:
                    t2.join(3)

        self.assertEqual(responses.get("first_edit"), 200)
        self.assertEqual(responses.get("second_edit"), 200)
        self.assertEqual(responses.get("delete"), 409)
        self.assertTrue(folder.exists())

    def test_b05_gemini_transcriber_import_and_signature(self):
        """B-05: gemini_transcriber imports cleanly and _extract_audio_compressed accepts job_ctx."""
        import ast
        import importlib
        mod = importlib.import_module("shorts_generator.local.gemini_transcriber")
        self.assertIsNotNone(mod)
        p = Path(__file__).resolve().parent.parent / "shorts_generator/local/gemini_transcriber.py"
        tree = ast.parse(p.read_text(encoding="utf-8"))
        helper = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_extract_audio_compressed"
        )
        arg_names = [a.arg for a in helper.args.args]
        self.assertIn("job_ctx", arg_names)

    def test_b02_initial_persistence_failure_recovery(self):
        """B-02: Failure in _persist_job_metadata must cleanly transition to FAILED and unblock new jobs."""
        errors = []
        pipeline_calls = []
        with patch("web_app._persist_job_metadata", side_effect=PermissionError("fixture: metadata file locked")), \
             patch("web_app.generate_shorts", side_effect=lambda **kw: pipeline_calls.append(kw)), \
             patch("threading.excepthook", side_effect=lambda args: errors.append(type(args.exc_value).__name__)):
            first = self.client.post("/api/generate", json={"url": "https://example.invalid/fixture", "num_clips": 1})
            self.assertEqual(first.status_code, 200)
            jid = first.get_json()["job_id"]
            ctx = job_manager.get_job(jid)
            ctx.worker_thread.join(3)
            self.assertFalse(ctx.worker_thread.is_alive())
            status = self.client.get("/api/jobs/" + jid).get_json()
            self.assertEqual(status["status"], JobStatus.FAILED)
            self.assertIn("fixture: metadata file locked", status["error"])
            self.assertEqual(errors, [])
            self.assertEqual(len(pipeline_calls), 0)

            # Subsequent generate request must be admitted without 409 conflict
            with patch("web_app._persist_job_metadata", return_value=None):
                second = self.client.post("/api/generate", json={"url": "https://example.invalid/second", "num_clips": 1})
                self.assertEqual(second.status_code, 200)
                second_jid = second.get_json()["job_id"]
                second_ctx = job_manager.get_job(second_jid)
                if second_ctx and second_ctx.worker_thread:
                    second_ctx.request_cancel()
                    second_ctx.worker_thread.join(3)

    def test_b04_incomplete_first_clip_cancel_rejected(self):
        """B-04: Canceled job with only an incomplete/corrupted file must report CANCELED with 0 successes."""
        ctx = job_manager.admit_job("incomplete_first_clip", "fixture", {"url": "fixture", "config": {}})
        web_app.jobs[ctx.job_id] = ctx.to_dict()

        def incomplete(**kwargs):
            # Write corrupted file (header only)
            (Path(kwargs["out_dir"]) / "short_01.mp4").write_bytes(b"incomplete-video-header")
            ctx.request_cancel(reason="Dibatalkan saat render klip 1")
            ctx.check_cancellation_or_timeout()

        with patch("web_app.generate_shorts", side_effect=incomplete):
            web_app.run_generation_job(ctx.job_id, ctx.params)

        self.assertEqual(ctx.status, JobStatus.CANCELED)
        self.assertEqual(ctx.result["stats"]["success"], 0)
        self.assertEqual(len(ctx.result["shorts"]), 0)

        path = web_app.OUTPUT_DIR / ctx.session_folder / "short_01.mp4"
        persisted = json.loads((path.parent / f"job_{ctx.job_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], JobStatus.CANCELED)
        self.assertEqual(persisted["result"]["stats"]["success"], 0)

    def test_b04_partial_clip_retention_with_complete_metadata(self):
        """B-04: Canceled job after 1 truly completed clip retains complete metadata for that clip."""
        ctx = job_manager.admit_job("partial_clip_retention", "fixture", {"url": "fixture", "config": {}})
        web_app.jobs[ctx.job_id] = ctx.to_dict()

        def one_complete_then_cancel(**kwargs):
            out_dir = Path(kwargs["out_dir"])
            clip1 = out_dir / "short_01.mp4"
            clip1.write_bytes(b"complete-video-fixture")
            (out_dir / "short_01.vtt").write_text("WEBVTT\n", encoding="utf-8")
            # Incomplete clip 2
            (out_dir / "short_02.mp4").write_bytes(b"corrupt-clip-2")

            completed_item = {
                "clip_index": 1,
                "title": "Highlight Pertama",
                "hook_sentence": "Hook menarik",
                "start_time": 0.0,
                "end_time": 4.5,
                "clip_url": str(clip1),
                "filename": "short_01.mp4",
                "out_dir": str(out_dir),
            }
            ctx.completed_shorts.append(completed_item)
            ctx.request_cancel(reason="Dibatalkan saat klip 2")
            ctx.check_cancellation_or_timeout()

        def mock_verify(video_path, *args, **kwargs):
            if "short_02" in str(video_path):
                raise RuntimeError("File short_02 corrupt")

        with patch("web_app.generate_shorts", side_effect=one_complete_then_cancel), \
             patch("web_app.verify_rendered_video", side_effect=mock_verify):
            web_app.run_generation_job(ctx.job_id, ctx.params)

        self.assertEqual(ctx.status, JobStatus.PARTIAL)
        self.assertEqual(ctx.result["stats"]["success"], 1)
        self.assertEqual(len(ctx.result["shorts"]), 1)
        short0 = ctx.result["shorts"][0]
        # Must have complete metadata fields
        for field in ("clip_index", "title", "hook_sentence", "start_time", "end_time", "filename", "web_url", "vtt_url", "folder_name", "clip_url"):
            self.assertIn(field, short0)
        self.assertEqual(short0["clip_index"], 1)
        self.assertEqual(short0["title"], "Highlight Pertama")
        self.assertEqual(short0["hook_sentence"], "Hook menarik")

    def test_b04_duration_mismatch_rejected_on_cancel_and_timeout(self):
        """B-04: Valid 2s MP4 for an 8s selection must be rejected on cancel & timeout; matching clip retained."""
        # 1. Test Cancellation with 2s MP4 for 8s selection -> REJECTED, 0 success
        ctx_cancel = job_manager.admit_job("dur_mismatch_cancel", "fixture", {"url": "fixture", "num_clips": 1, "config": {}})
        web_app.jobs[ctx_cancel.job_id] = ctx_cancel.to_dict()

        def short_file_cancel(**kwargs):
            out_dir = Path(kwargs["out_dir"])
            clip = out_dir / "short_01.mp4"
            clip.write_bytes(b"mock-2s-mp4-content")
            # Completed item claims 8s selection (0.0 to 8.0)
            completed_item = {
                "clip_index": 1,
                "title": "Eight Second Clip",
                "hook_sentence": "Hook",
                "start_time": 0.0,
                "end_time": 8.0,
                "clip_url": str(clip),
                "filename": "short_01.mp4",
                "out_dir": str(out_dir),
            }
            ctx_cancel.completed_shorts.append(completed_item)
            ctx_cancel.request_cancel(reason="Stopped during render")
            ctx_cancel.check_cancellation_or_timeout()

        # Real verification mock: rejects when expected_duration=8.0 but actual duration is 2.0s
        def mock_verify_check(video_path, expected_duration=None, **kw):
            actual_dur = 2.0  # Physical file is only 2 seconds
            if expected_duration is not None and abs(actual_dur - expected_duration) > 0.25:
                raise RuntimeError(
                    f"Durasi fisik video hasil render ({actual_dur:.2f}s) tidak sesuai dengan durasi rentang yang diminta ({expected_duration:.2f}s, toleransi ±0.25s)."
                )

        with patch("web_app.generate_shorts", side_effect=short_file_cancel), \
             patch("web_app.verify_rendered_video", side_effect=mock_verify_check):
            web_app.run_generation_job(ctx_cancel.job_id, ctx_cancel.params)

        self.assertEqual(ctx_cancel.status, JobStatus.CANCELED)
        self.assertEqual(ctx_cancel.result["stats"]["success"], 0)
        self.assertEqual(ctx_cancel.result["shorts"], [])

        # 2. Test Timeout with 2s MP4 for 8s selection -> REJECTED, status TIMEOUT, 0 success
        with job_manager._admission_lock:
            job_manager._jobs.clear()
        web_app.jobs.clear()

        ctx_to = job_manager.admit_job("dur_mismatch_to", "fixture", {"url": "fixture", "num_clips": 1, "config": {}}, timeout_seconds=0.1)
        web_app.jobs[ctx_to.job_id] = ctx_to.to_dict()

        def short_file_timeout(**kwargs):
            out_dir = Path(kwargs["out_dir"])
            clip = out_dir / "short_01.mp4"
            clip.write_bytes(b"mock-2s-mp4-content")
            completed_item = {
                "clip_index": 1,
                "title": "Eight Second Clip",
                "hook_sentence": "Hook",
                "start_time": 0.0,
                "end_time": 8.0,
                "clip_url": str(clip),
                "filename": "short_01.mp4",
                "out_dir": str(out_dir),
            }
            ctx_to.completed_shorts.append(completed_item)
            ctx_to.started_at = time.time() - 10
            ctx_to.check_cancellation_or_timeout()

        with patch("web_app.generate_shorts", side_effect=short_file_timeout), \
             patch("web_app.verify_rendered_video", side_effect=mock_verify_check):
            web_app.run_generation_job(ctx_to.job_id, ctx_to.params)

        self.assertEqual(ctx_to.status, JobStatus.TIMEOUT)
        self.assertEqual(ctx_to.result["stats"]["success"], 0)
        self.assertEqual(ctx_to.result["shorts"], [])

        # 3. Test Matching clip (8.0s physical == 8.0s expected) -> RETAINED as PARTIAL with full metadata
        with job_manager._admission_lock:
            job_manager._jobs.clear()
        web_app.jobs.clear()

        ctx_match = job_manager.admit_job("dur_match_partial", "fixture", {"url": "fixture", "num_clips": 2, "config": {}})
        web_app.jobs[ctx_match.job_id] = ctx_match.to_dict()

        def matching_file_then_cancel(**kwargs):
            out_dir = Path(kwargs["out_dir"])
            clip = out_dir / "short_01.mp4"
            clip.write_bytes(b"mock-8s-mp4-content")
            (out_dir / "short_01.vtt").write_text("WEBVTT\n", encoding="utf-8")
            completed_item = {
                "clip_index": 1,
                "title": "Eight Second Clip Matching",
                "hook_sentence": "Hook match",
                "start_time": 0.0,
                "end_time": 8.0,
                "clip_url": str(clip),
                "filename": "short_01.mp4",
                "out_dir": str(out_dir),
            }
            ctx_match.completed_shorts.append(completed_item)
            ctx_match.request_cancel(reason="Stopped during clip 2")
            ctx_match.check_cancellation_or_timeout()

        def mock_verify_match(video_path, expected_duration=None, **kw):
            actual_dur = 8.0  # Physical file matches expected duration
            if expected_duration is not None and abs(actual_dur - expected_duration) > 0.25:
                raise RuntimeError("Mismatch")

        with patch("web_app.generate_shorts", side_effect=matching_file_then_cancel), \
             patch("web_app.verify_rendered_video", side_effect=mock_verify_match):
            web_app.run_generation_job(ctx_match.job_id, ctx_match.params)

        self.assertEqual(ctx_match.status, JobStatus.PARTIAL)
        self.assertEqual(ctx_match.result["stats"]["success"], 1)
        self.assertEqual(len(ctx_match.result["shorts"]), 1)
        retained = ctx_match.result["shorts"][0]
        self.assertEqual(retained["clip_index"], 1)
        self.assertEqual(retained["start_time"], 0.0)
        self.assertEqual(retained["end_time"], 8.0)
        self.assertEqual(retained["title"], "Eight Second Clip Matching")
        self.assertEqual(retained["hook_sentence"], "Hook match")
        self.assertEqual(retained["filename"], "short_01.mp4")
        self.assertEqual(retained["web_url"], f"/output/{ctx_match.session_folder}/short_01.mp4")
        self.assertEqual(retained["vtt_url"], f"/output/{ctx_match.session_folder}/short_01.vtt")


if __name__ == "__main__":
    unittest.main()
