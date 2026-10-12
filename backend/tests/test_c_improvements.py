"""Regression tests for Bagian C: Cache accuracy, log isolation, and input validation."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import shorts_generator.config as cfg
import web_app
from shorts_generator.job_manager import JobContext, JobStatus, job_manager
from shorts_generator.local.clipper import crop_highlights_local
from shorts_generator.local.gemini_transcriber import _extract_audio_compressed, _get_audio_cache_path
from shorts_generator.local.transcriber import (
    _load_transcript_cache,
    _probe_duration,
    _transcript_cache_paths,
    _write_transcript_cache,
    transcribe_local,
)


def _create_sine_mp4(out_path: str, duration: int = 2, freq: int = 440) -> None:
    """Generate a real valid MP4 fixture with audio using FFmpeg."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=10",
        "-c:v", "libx264", "-c:a", "aac",
        out_path,
    ]
    subprocess.run(cmd, check=True)


class TestBagianCImprovements(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="shorts_test_c_"))
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._orig_output_dir = cfg.LOCAL_OUTPUT_DIR
        self._orig_web_output = web_app.OUTPUT_DIR
        cfg.LOCAL_OUTPUT_DIR = str(self.output_dir)
        web_app.OUTPUT_DIR = self.output_dir

        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

        with job_manager._admission_lock:
            job_manager._jobs.clear()
        web_app.jobs.clear()

    def tearDown(self):
        cfg.LOCAL_OUTPUT_DIR = self._orig_output_dir
        web_app.OUTPUT_DIR = self._orig_web_output
        with job_manager._admission_lock:
            job_manager._jobs.clear()
        web_app.jobs.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ==========================================
    # 1. Audio and Transcript Cache Accuracy
    # ==========================================

    def test_audio_cache_different_paths_same_basename_have_distinct_identities(self):
        """Two different video files with identical basename video.mp4 have distinct audio caches."""
        dir_a = self.temp_dir / "folder_a"
        dir_b = self.temp_dir / "folder_b"
        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        video_a = str(dir_a / "video.mp4")
        video_b = str(dir_b / "video.mp4")

        # Generate real media with different audio tones
        _create_sine_mp4(video_a, duration=2, freq=440)
        _create_sine_mp4(video_b, duration=3, freq=880)

        path_a, key_a = _get_audio_cache_path(video_a)
        path_b, key_b = _get_audio_cache_path(video_b)

        self.assertNotEqual(key_a, key_b, "Identical basenames in different folders must produce different cache keys")
        self.assertNotEqual(path_a, path_b, "Audio cache files must not collide")

        # Extract both
        cached_a = _extract_audio_compressed(video_a)
        cached_b = _extract_audio_compressed(video_b)

        self.assertTrue(cached_a.exists())
        self.assertTrue(cached_b.exists())
        self.assertNotEqual(cached_a, cached_b)
        self.assertGreater(cached_a.stat().st_size, 500)
        self.assertGreater(cached_b.stat().st_size, 500)

    def test_audio_cache_corrupted_file_detected_and_regenerated(self):
        """Corrupted/0-byte audio cache file is detected, unlinked, and treated as a cache miss."""
        dir_c = self.temp_dir / "folder_c"
        dir_c.mkdir(parents=True, exist_ok=True)
        video_c = str(dir_c / "corrupt_test.mp4")
        _create_sine_mp4(video_c, duration=2, freq=440)

        audio_path, _ = _get_audio_cache_path(video_c)
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        # Create a corrupt 0-byte cache file
        audio_path.write_bytes(b"")

        self.assertTrue(audio_path.exists())
        self.assertEqual(audio_path.stat().st_size, 0)

        # Extraction should detect corruption, purge, and re-extract cleanly
        fresh_audio = _extract_audio_compressed(video_c)
        self.assertTrue(fresh_audio.exists())
        self.assertGreater(fresh_audio.stat().st_size, 500)

    def test_transcript_cache_identity_and_duration_preservation(self):
        """Transcript cache preserves source duration without clamping to segments[-1]['end']."""
        dummy_media = str(self.temp_dir / "dur_test.mp4")
        _create_sine_mp4(dummy_media, duration=4, freq=440)

        json_p, srt_p = _transcript_cache_paths(dummy_media, "gemini", "model-x", "en")
        self.assertIn("transcript_dur_test_", json_p.name)

        # Mock transcript where segments end at 2.5s but source media is 4.0s
        transcript_data = {
            "duration": 4.0,
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "Hello world"},
                {"start": 1.5, "end": 2.5, "text": "Ending early"},
            ],
        }
        _write_transcript_cache(dummy_media, transcript_data, "gemini", "model-x", "en")

        self.assertTrue(json_p.exists())
        loaded = _load_transcript_cache(dummy_media, "gemini", "model-x", "en")
        self.assertIsNotNone(loaded)
        # Duration must remain the true source duration (4.0s), NOT 2.5s
        self.assertAlmostEqual(loaded["duration"], 4.0, places=1)

    def test_transcript_cache_corrupted_json_handled_cleanly(self):
        """Corrupted transcript JSON cache is purged and returns None without throwing."""
        dummy_media = str(self.temp_dir / "corrupt_json.mp4")
        _create_sine_mp4(dummy_media, duration=2, freq=440)

        json_p, srt_p = _transcript_cache_paths(dummy_media, "gemini", "model-x", "en")
        json_p.parent.mkdir(parents=True, exist_ok=True)
        json_p.write_text("{invalid_json: true", encoding="utf-8")

        loaded = _load_transcript_cache(dummy_media, "gemini", "model-x", "en")
        self.assertIsNone(loaded)
        self.assertFalse(json_p.exists(), "Corrupt cache file should have been unlinked")

    def test_clipper_does_not_use_unverified_legacy_srt_fallback(self):
        """Clipper ignores naked basename .srt files if transcript is not provided."""
        source_media = str(self.temp_dir / "unverified.mp4")
        _create_sine_mp4(source_media, duration=2, freq=440)

        # Place a legacy unverified .srt in LOCAL_OUTPUT_DIR
        legacy_srt = Path(cfg.LOCAL_OUTPUT_DIR) / "unverified.srt"
        legacy_srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nFake unverified subtitle\n",
            encoding="utf-8",
        )

        with patch("shorts_generator.local.clipper.crop_clip_local") as mock_crop:
            crop_highlights_local(
                source_path=source_media,
                highlights=[{"start_time": 0.0, "end_time": 1.5, "title": "Test"}],
                out_dir=str(self.temp_dir / "out_clip"),
                transcript=None,  # No verified transcript
            )
            # mock_crop must have been called with empty segments, NOT the fake .srt!
            call_kwargs = mock_crop.call_args.kwargs
            self.assertEqual(call_kwargs.get("segments"), [])

    # ==========================================
    # 2. Job Log Isolation
    # ==========================================

    def test_job_log_isolation_prints_from_other_threads_do_not_leak(self):
        """Prints from concurrent threads do not leak into active job logs or alter stage/progress."""
        job_ctx = job_manager.admit_job("isolation_job", "https://example.invalid", {})
        job_ctx.transition_to(JobStatus.RUNNING, stage="downloading", progress=20)

        def noisy_thread():
            # These prints simulating other threads or endpoints should NOT appear in job_ctx.logs
            print("[download] downloading random file for other user...", flush=True)
            print("[transcribe] whisper processing background task...", flush=True)
            print("cropping ffmpeg other video...", flush=True)

        t = threading.Thread(target=noisy_thread)
        t.start()
        t.join()

        # Check job_ctx logs
        self.assertEqual(len(job_ctx.logs), 0, "No external prints should leak into job_ctx.logs")
        self.assertEqual(job_ctx.stage, "downloading")
        self.assertEqual(job_ctx.progress, 20)

        # Now emit log directly through job_ctx
        job_ctx.emit_log("[transcribe] audio transcription started")
        self.assertEqual(len(job_ctx.logs), 1)
        self.assertIn("[transcribe]", job_ctx.logs[0])
        self.assertEqual(job_ctx.stage, "transcribing")
        self.assertEqual(job_ctx.progress, 45)

    # ==========================================
    # 3. Backend Input Validation
    # ==========================================

    def test_api_generate_rejects_non_dict_payloads(self):
        """POST /api/generate rejects non-dict JSON payloads (lists, ints, strings) with 400."""
        for invalid_payload in (["url", "num_clips"], 12345, "string_payload"):
            resp = self.client.post("/api/generate", json=invalid_payload)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Payload harus berupa objek JSON yang valid", resp.get_json()["error"])

    def test_api_generate_strictly_validates_num_clips(self):
        """POST /api/generate strictly validates num_clips: rejects bool, float, strings, and out-of-bounds."""
        valid_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        # Boolean True is subclass of int in Python; must be rejected!
        resp_bool = self.client.post("/api/generate", json={"url": valid_url, "num_clips": True})
        self.assertEqual(resp_bool.status_code, 400)
        self.assertIn("tidak valid. Harus berupa angka bulat", resp_bool.get_json()["error"])

        resp_bool_f = self.client.post("/api/generate", json={"url": valid_url, "num_clips": False})
        self.assertEqual(resp_bool_f.status_code, 400)

        # Float
        resp_float = self.client.post("/api/generate", json={"url": valid_url, "num_clips": 3.5})
        self.assertEqual(resp_float.status_code, 400)

        # Out of bounds
        resp_zero = self.client.post("/api/generate", json={"url": valid_url, "num_clips": 0})
        self.assertEqual(resp_zero.status_code, 400)

        resp_over = self.client.post("/api/generate", json={"url": valid_url, "num_clips": 11})
        self.assertEqual(resp_over.status_code, 400)

    def test_api_generate_strictly_validates_types(self):
        """POST /api/generate validates strings for URL, mode, language, and providers."""
        # Non-string URL
        resp = self.client.post("/api/generate", json={"url": 12345})
        self.assertEqual(resp.status_code, 400)

        # Invalid mode
        valid_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        resp = self.client.post("/api/generate", json={"url": valid_url, "mode": "magic"})
        self.assertEqual(resp.status_code, 400)

        # Non-string language
        resp = self.client.post("/api/generate", json={"url": valid_url, "language": 999})
        self.assertEqual(resp.status_code, 400)

        # Invalid transcriber_provider
        resp = self.client.post("/api/generate", json={"url": valid_url, "transcriber_provider": "vosk"})
        self.assertEqual(resp.status_code, 400)

    def test_api_config_pre_validation_protects_env(self):
        """POST /api/config pre-validates all updates before writing to .env."""
        orig_llm = cfg.LLM_PROVIDER
        resp = self.client.post("/api/config", json={"LLM_PROVIDER": "unsupported_ai"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("tidak valid", resp.get_json()["error"])
        self.assertEqual(cfg.LLM_PROVIDER, orig_llm, "Config must not mutate on validation error")

        # Non-dict config payload
        resp_list = self.client.post("/api/config", json=["not", "a", "dict"])
        self.assertEqual(resp_list.status_code, 400)

        # Non-string value for config key
        resp_int = self.client.post("/api/config", json={"GEMINI_API_KEY": 12345})
        self.assertEqual(resp_int.status_code, 400)

    def test_api_models_test_validates_payload(self):
        """POST /api/models/test validates JSON object, provider, and model name."""
        resp = self.client.post("/api/models/test", json="invalid")
        self.assertEqual(resp.status_code, 400)

        resp = self.client.post("/api/models/test", json={"provider": "gemini", "model": ""})
        self.assertEqual(resp.status_code, 400)

        resp = self.client.post("/api/models/test", json={"provider": 123, "model": "gemini-3.5-flash"})
        self.assertEqual(resp.status_code, 400)

    def test_open_folder_validates_payload(self):
        """POST /api/open-folder validates JSON object and folder string."""
        resp = self.client.post("/api/open-folder", json=["not_a_dict"])
        self.assertEqual(resp.status_code, 400)

        resp = self.client.post("/api/open-folder", json={"folder": 123})
        self.assertEqual(resp.status_code, 400)

    # ==========================================
    # 4. Residues C-01 to C-04 Regressions
    # ==========================================

    def test_c01_truncated_mp3_audio_cache_detected_and_regenerated(self):
        """C-01: A truncated MP3 with a valid header duration must not become a cache hit."""
        from shorts_generator.local.gemini_transcriber import _verify_audio_integrity
        source_video = str(self.temp_dir / "c01_source.mp4")
        _create_sine_mp4(source_video, duration=4, freq=440)

        # 1. First extraction succeeds and creates valid cache
        cached = _extract_audio_compressed(source_video)
        self.assertTrue(cached.exists())
        full_bytes = cached.read_bytes()
        self.assertGreater(len(full_bytes), 1000)
        self.assertTrue(_verify_audio_integrity(str(cached)))

        # 2. Corrupt/truncate the audio file by cutting bytes in half
        cached.write_bytes(full_bytes[: len(full_bytes) // 2])
        truncated_size = cached.stat().st_size
        self.assertFalse(_verify_audio_integrity(str(cached)), "Truncated MP3 must fail integrity verification")

        # 3. Next extraction must detect truncation, invalidate corrupt cache, and re-extract
        reused = _extract_audio_compressed(source_video)
        self.assertEqual(reused, cached)
        self.assertGreater(cached.stat().st_size, truncated_size, "Cache must be re-extracted with full payload")
        self.assertTrue(_verify_audio_integrity(str(cached)))

    def test_c02_transcript_cache_semantic_contract_validation(self):
        """C-02: Corrupted or non-finite transcript cache must be rejected, unlinked, and treated as a miss."""
        source_video = str(self.temp_dir / "c02_source.mp4")
        _create_sine_mp4(source_video, duration=3, freq=440)

        valid_transcript = {
            "duration": 3.0,
            "segments": [{"start": 0.0, "end": 2.0, "text": "Valid speech"}],
        }
        json_path, srt_path = _write_transcript_cache(source_video, valid_transcript, "gemini", "test-model", "en")
        self.assertTrue(json_path.exists())
        template = json.loads(json_path.read_text(encoding="utf-8"))

        # Test invalid schemas: NaN duration, Inf duration, invalid segments, empty dict segment, NaN timestamp
        invalid_cases = [
            ("nan_duration", float("nan"), valid_transcript["segments"]),
            ("inf_duration", float("inf"), valid_transcript["segments"]),
            ("invalid_segment_type", 3.0, ["not_a_dict"]),
            ("empty_segment_dict", 3.0, [{}]),
            ("nan_segment_start", 3.0, [{"start": float("nan"), "end": 2.0, "text": "Invalid"}]),
            ("reversed_timestamps", 3.0, [{"start": 2.5, "end": 1.0, "text": "Reversed"}]),
        ]

        for case_name, dur, segs in invalid_cases:
            data = dict(template, duration=dur, segments=segs)
            json_path.write_text(json.dumps(data), encoding="utf-8")

            loaded = _load_transcript_cache(source_video, "gemini", "test-model", "en")
            self.assertIsNone(loaded, f"Corrupted cache '{case_name}' must return None (cache miss)")
            self.assertFalse(json_path.exists(), f"Corrupted cache '{case_name}' must be unlinked from disk")

        # Also verify that _write_transcript_cache rejects writing invalid contracts
        with self.assertRaises(ValueError):
            _write_transcript_cache(source_video, {"duration": float("nan"), "segments": []}, "gemini", "m", "en")

    def test_c03_highlight_and_llm_logs_propagated_to_job_ctx(self):
        """C-03: Real highlight code logs into job_ctx, transitions stage to analyzing, and avoids global leaks."""
        import io
        import contextlib
        from shorts_generator.pipeline import _run_local
        from shorts_generator.job_manager import JobContext, JobStatus

        source_video = str(self.temp_dir / "c03_source.mp4")
        _create_sine_mp4(source_video, duration=4, freq=440)

        job_ctx = JobContext("c03_test", "https://example.com/c03", {})
        job_ctx.transition_to(JobStatus.RUNNING, stage="transcribing", progress=45)

        valid_transcript = {
            "duration": 4.0,
            "segments": [{"start": 0.0, "end": 2.0, "text": "Hello world"}],
        }

        stages_recorded = []
        def fake_llm(prompt):
            stages_recorded.append((job_ctx.stage, job_ctx.progress, any("[highlights]" in m for m in job_ctx.logs)))
            if "content_type" in prompt:
                return json.dumps({"content_type": "podcast", "density": "high"})
            return json.dumps({"highlights": [{"start_time": 0.0, "end_time": 3.0, "score": 90, "title": "Highlight"}]})

        captured_stdout = io.StringIO()
        with patch("shorts_generator.local.downloader.download_youtube_local", return_value=source_video), \
             patch("shorts_generator.local.transcriber.transcribe_local", return_value=valid_transcript), \
             patch("shorts_generator.local.llm.create_llm_callable", return_value=fake_llm), \
             patch("shorts_generator.local.clipper.crop_highlights_local", return_value=[]), \
             contextlib.redirect_stdout(captured_stdout):
            _run_local("c03_fixture", 1, "9:16", "720", "en", out_dir=str(self.output_dir / "c03"), job_ctx=job_ctx)

        # 1. Job logs must contain highlights messages
        self.assertTrue(any("[highlights]" in m for m in job_ctx.logs), "job_ctx.logs must contain [highlights] messages")
        # 2. During LLM calls, job must be in analyzing stage with progress >= 70
        self.assertTrue(len(stages_recorded) >= 1)
        for stage, prog, has_hl_log in stages_recorded:
            self.assertEqual(stage, "analyzing")
            self.assertGreaterEqual(prog, 70)
            self.assertTrue(has_hl_log)

    def test_c04_backend_request_validation_consistency(self):
        """C-04: open-folder rejects malformed JSON and null; generate rejects invalid URLs and passes normalized language."""
        # 1. POST /api/open-folder with malformed JSON '{' or 'null' must return 400 with 0 launches
        for bad_body in ("{", "null"):
            with patch("os.startfile") as mock_launch:
                resp = self.client.post("/api/open-folder", data=bad_body, content_type="application/json")
                self.assertEqual(resp.status_code, 400)
                mock_launch.assert_not_called()

        # Valid empty dict {} opens output dir
        with patch("os.startfile") as mock_launch:
            resp_empty = self.client.post("/api/open-folder", json={})
            self.assertEqual(resp_empty.status_code, 200)
            self.assertEqual(mock_launch.call_count, 1)

        # 2. POST /api/generate with malformed URL must return 400 with 0 workers
        with patch("web_app.run_generation_job") as mock_worker:
            resp_url = self.client.post("/api/generate", json={"url": "https://[broken"})
            self.assertEqual(resp_url.status_code, 400)
            self.assertIn("Format URL tidak valid", resp_url.get_json()["error"])
            mock_worker.assert_not_called()

        # 3. POST /api/generate with language " en " must forward stripped "en" to job_ctx params
        with patch("web_app.run_generation_job"):
            resp_lang = self.client.post("/api/generate", json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "language": " en ",
            })
            self.assertEqual(resp_lang.status_code, 200)
            job_id = resp_lang.get_json()["job_id"]
            admitted_job = job_manager.get_job(job_id)
            self.assertIsNotNone(admitted_job)
            self.assertEqual(admitted_job.params.get("language"), "en", "Language must be passed as normalized 'en'")

    def test_c01_failed_verifier_rejects_and_publishes_no_cache(self):
        """C-01: Verifier returning False must raise RuntimeError, purge staging, and publish 0 files."""
        source = self.temp_dir / "failed_verifier_source.mp4"
        source.write_bytes(b"fixture source")

        def creates_invalid_staging(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"RIFF" + b"\0" * 200)

        with patch("shorts_generator.local.clipper._run_ffmpeg_cmd", side_effect=creates_invalid_staging) as extractor, \
             patch("shorts_generator.local.gemini_transcriber._verify_audio_integrity", return_value=False) as verifier:
            with self.assertRaises(RuntimeError):
                _extract_audio_compressed(str(source))
            self.assertEqual(extractor.call_count, 1)
            self.assertEqual(verifier.call_count, 1)

        cache_path, _ = _get_audio_cache_path(str(source))
        self.assertFalse(cache_path.exists(), "Final cache file must NOT be published when verifier fails")

    def test_c01_missing_staging_cleanly_raises_without_mock_bypasses(self):
        """C-01: Missing staging after extraction must unconditionally raise RuntimeError without synthetic fallbacks."""
        source = self.temp_dir / "missing_staging_source.mp4"
        source.write_bytes(b"fixture source")

        with patch("shorts_generator.local.clipper._run_ffmpeg_cmd") as mock_extract:
            with self.assertRaises(RuntimeError) as cm:
                _extract_audio_compressed(str(source))
            self.assertIn("Ekstraksi audio gagal", str(cm.exception))

        cache_path, _ = _get_audio_cache_path(str(source))
        self.assertFalse(cache_path.exists(), "Final cache file must NOT be published when staging is missing")

    def test_c01_decoder_handles_stderr_backpressure_and_cleans_up(self):
        """C-01: Decoder child writing 1MB to stderr before PCM does not hang or deadlock."""
        from shorts_generator.local.gemini_transcriber import _verify_audio_integrity
        sample = self.temp_dir / "pipe_fixture.mp3"
        sample.write_bytes(b"fixture header" + b"\0" * 200)

        real_popen = subprocess.Popen
        procs = []
        code = "import sys; sys.stderr.buffer.write(b'x'*1048576); sys.stderr.buffer.flush(); sys.stdout.buffer.write(b'\\0'*64000); sys.stdout.buffer.flush()"

        def noisy_decoder(cmd, **kwargs):
            proc = real_popen([sys.executable, "-B", "-c", code], **kwargs)
            procs.append(proc)
            return proc

        with patch("shorts_generator.local.gemini_transcriber._get_duration", return_value=2.0), \
             patch("shorts_generator.local.gemini_transcriber.subprocess.Popen", side_effect=noisy_decoder):
            t0 = time.time()
            res = _verify_audio_integrity(str(sample), expected_duration=2.0)
            elapsed = time.time() - t0

        self.assertTrue(res, "Decoder with 64000 bytes PCM (2.0s) should verify as True")
        self.assertLess(elapsed, 2.0, "Decoder must finish within 2 seconds without hanging on stderr")
        time.sleep(0.05)
        self.assertTrue(all(p.poll() is not None for p in procs), "All decoder child processes must be cleaned up")

    def test_c01_decoder_cancels_and_terminates_stuck_subprocess(self):
        """C-01: Stuck decoder is promptly terminated on job cancellation without orphan processes."""
        from shorts_generator.local.gemini_transcriber import _verify_audio_integrity
        sample = self.temp_dir / "stuck_fixture.mp3"
        sample.write_bytes(b"fixture header" + b"\0" * 200)

        real_popen = subprocess.Popen
        procs = []
        code = "import time; time.sleep(60)"

        def stuck_decoder(cmd, **kwargs):
            proc = real_popen([sys.executable, "-B", "-c", code], **kwargs)
            procs.append(proc)
            return proc

        job_ctx = JobContext("stuck_decoder_job", "https://example.com/test", {})
        job_ctx.started_at = time.time()

        def cancel_later():
            time.sleep(0.1)
            job_ctx.request_cancel(reason="Test cancel stuck decoder")

        t = threading.Thread(target=cancel_later, daemon=True)
        t.start()

        with patch("shorts_generator.local.gemini_transcriber._get_duration", return_value=5.0), \
             patch("shorts_generator.local.gemini_transcriber.subprocess.Popen", side_effect=stuck_decoder):
            t0 = time.time()
            res = _verify_audio_integrity(str(sample), expected_duration=5.0, job_ctx=job_ctx)
            elapsed = time.time() - t0

        self.assertFalse(res, "Cancelled stuck decoder must return False")
        self.assertLess(elapsed, 2.0, "Cancellation must abort stuck decoder within 2 seconds")
        time.sleep(0.05)
        self.assertTrue(all(p.poll() is not None for p in procs), "Subprocess must not be left running")

    def test_c01_worker_cancel_during_staging_verification(self):
        """C-01: Worker records CANCELED status on cancel during staging verification without orphan processes or files."""
        src = self.temp_dir / "worker_cancel_test.mp4"
        src.write_bytes(b"dummy video content" * 100)

        jid = "test_cancel_worker_staging"
        ctx = job_manager.admit_job(
            jid,
            "http://example.com/test",
            {"url": str(src), "num_clips": 1, "mode": "local", "transcriber_provider": "gemini"},
        )
        web_app.jobs[jid] = ctx.to_dict()

        procs_cancel = []
        real_popen = subprocess.Popen

        def slow_decoder(cmd, **kw):
            p = real_popen([sys.executable, "-B", "-c", "import time; time.sleep(10)"], **kw)
            procs_cancel.append(p)
            return p

        def cancel_after_start():
            time.sleep(0.1)
            ctx.request_cancel(reason="Dibatalkan saat verifikasi audio staging")

        t_cancel = threading.Thread(target=cancel_after_start, daemon=True)
        t_cancel.start()

        with patch("shorts_generator.local.downloader.download_youtube_local", return_value=str(src)), \
             patch("shorts_generator.local.gemini_transcriber._get_duration", return_value=4.0), \
             patch("shorts_generator.local.gemini_transcriber.subprocess.Popen", side_effect=slow_decoder), \
             patch("shorts_generator.local.clipper._run_ffmpeg_cmd", side_effect=lambda cmd, **kw: Path(cmd[-1]).write_bytes(b"staging audio")):
            web_app.run_generation_job(jid, ctx.params)

        time.sleep(0.05)
        # Memory status
        self.assertEqual(ctx.status, JobStatus.CANCELED)
        self.assertEqual(web_app.jobs[jid].get("status"), "canceled")

        # Disk status
        meta_p = self.output_dir / ctx.session_folder / f"job_{jid}.json"
        self.assertTrue(meta_p.exists(), f"Job metadata {meta_p} must exist on disk")
        meta_data = json.loads(meta_p.read_text(encoding="utf-8"))
        self.assertEqual(meta_data.get("status"), "canceled")

        # Subprocess registry and termination
        self.assertEqual(len(ctx._subprocesses), 0, "Subprocess registry must be empty")
        self.assertTrue(all(p.poll() is not None for p in procs_cancel), "Decoder subprocess must be terminated")

        # Cache and staging absence
        audio_cache, _ = _get_audio_cache_path(str(src))
        self.assertFalse(audio_cache.exists(), "Audio cache must not be published on cancellation")
        staging_files = list(audio_cache.parent.glob(".tmp_audio_*"))
        self.assertEqual(len(staging_files), 0, "No staging files must remain after cancellation")

    def test_c01_worker_timeout_during_staging_verification(self):
        """C-01: Worker records TIMEOUT status on timeout during staging verification without orphan processes or files."""
        src = self.temp_dir / "worker_timeout_test.mp4"
        src.write_bytes(b"dummy video content" * 100)

        jid = "test_timeout_worker_staging"
        ctx = job_manager.admit_job(
            jid,
            "http://example.com/test",
            {"url": str(src), "num_clips": 1, "mode": "local", "transcriber_provider": "gemini"},
            timeout_seconds=0.2,
        )
        web_app.jobs[jid] = ctx.to_dict()

        procs_to = []
        real_popen = subprocess.Popen

        def slow_decoder(cmd, **kw):
            p = real_popen([sys.executable, "-B", "-c", "import time; time.sleep(10)"], **kw)
            procs_to.append(p)
            return p

        with patch("shorts_generator.local.downloader.download_youtube_local", return_value=str(src)), \
             patch("shorts_generator.local.gemini_transcriber._get_duration", return_value=4.0), \
             patch("shorts_generator.local.gemini_transcriber.subprocess.Popen", side_effect=slow_decoder), \
             patch("shorts_generator.local.clipper._run_ffmpeg_cmd", side_effect=lambda cmd, **kw: Path(cmd[-1]).write_bytes(b"staging audio")):
            web_app.run_generation_job(jid, ctx.params)

        time.sleep(0.05)
        # Memory status
        self.assertEqual(ctx.status, JobStatus.TIMEOUT)
        self.assertEqual(web_app.jobs[jid].get("status"), "timeout")

        # Disk status
        meta_p = self.output_dir / ctx.session_folder / f"job_{jid}.json"
        self.assertTrue(meta_p.exists(), f"Job metadata {meta_p} must exist on disk")
        meta_data = json.loads(meta_p.read_text(encoding="utf-8"))
        self.assertEqual(meta_data.get("status"), "timeout")

        # Subprocess registry and termination
        self.assertEqual(len(ctx._subprocesses), 0, "Subprocess registry must be empty")
        self.assertTrue(all(p.poll() is not None for p in procs_to), "Decoder subprocess must be terminated")

        # Cache and staging absence
        audio_cache, _ = _get_audio_cache_path(str(src))
        self.assertFalse(audio_cache.exists(), "Audio cache must not be published on timeout")
        staging_files = list(audio_cache.parent.glob(".tmp_audio_*"))
        self.assertEqual(len(staging_files), 0, "No staging files must remain after timeout")


if __name__ == "__main__":
    unittest.main()

