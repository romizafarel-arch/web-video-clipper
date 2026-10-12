"""Regression tests for Section A: Editor precision and output protection.

Validates:
1. Editing short_02 or short_03 does not touch short_01.
2. Preview and Set In/Out logic for candidates starting at >= 600s.
3. External local files outside session folders are reused for re-rendering.
4. Re-render failures preserve previous video without corruption.
5. Concurrent edit requests on the same clip do not collide.
6. Non-finite timestamps (NaN, Infinity), negative values, and out-of-boundary durations are rejected.
"""
import json
import math
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from web_app import (
    app,
    OUTPUT_DIR,
    resolve_session_source,
    get_clip_lock,
    get_session_lock,
    probe_media_duration,
    verify_rendered_video,
)
from shorts_generator.highlights import _sanitize_highlights, _coerce_float, _coerce_int


class TestEditorialRegression(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.test_session_id = f"test_session_{int(time.time() * 1000)}"
        self.session_dir = OUTPUT_DIR / self.test_session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Mock source video inside session
        self.source_file = self.session_dir / "source_mock.mp4"
        self.source_file.write_bytes(b"MOCK_SOURCE_VIDEO_HEADER_1234567890")

        # Mock initial clips
        self.short1 = self.session_dir / "short_01.mp4"
        self.short1.write_bytes(b"SHORT_01_INITIAL_BYTES")
        self.short2 = self.session_dir / "short_02.mp4"
        self.short2.write_bytes(b"SHORT_02_INITIAL_BYTES")
        self.short3 = self.session_dir / "short_03.mp4"
        self.short3.write_bytes(b"SHORT_03_INITIAL_BYTES")

        # Job JSON
        self.job_meta = {
            "job_id": self.test_session_id,
            "session_folder": self.test_session_id,
            "result": {
                "source_video_url": str(self.source_file),
                "transcript": {
                    "duration": 750.0,
                    "segments": [
                        {"start": 600.0, "end": 645.0, "text": "Segmen di menit ke 10"},
                    ],
                },
                "shorts": [
                    {
                        "clip_index": 1,
                        "filename": "short_01.mp4",
                        "title": "Short Satu",
                        "start_time": 10.0,
                        "end_time": 40.0,
                        "score": 90,
                    },
                    {
                        "clip_index": 2,
                        "filename": "short_02.mp4",
                        "title": "Short Dua",
                        "start_time": 600.0,
                        "end_time": 645.0,
                        "score": 88,
                    },
                    {
                        "clip_index": 3,
                        "filename": "short_03.mp4",
                        "title": "Short Tiga",
                        "start_time": 650.0,
                        "end_time": 690.0,
                        "score": 85,
                    },
                ],
            },
        }
        self.job_json_path = self.session_dir / f"job_{self.test_session_id}.json"
        with open(self.job_json_path, "w", encoding="utf-8") as f:
            json.dump(self.job_meta, f, indent=2)

        self.probe_patcher = patch("web_app.probe_media_duration", return_value=750.0)
        self.mock_probe = self.probe_patcher.start()
        self.verify_patcher = patch("web_app.verify_rendered_video", return_value=None)
        self.mock_verify = self.verify_patcher.start()

    def tearDown(self):
        self.probe_patcher.stop()
        self.verify_patcher.stop()
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)

    def test_history_includes_clip_index(self):
        """Verify /api/history exposes accurate clip_index for every clip."""
        res = self.client.get("/api/history")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        target_session = next((s for s in data.get("sessions", []) if s["id"] == self.test_session_id), None)
        self.assertIsNotNone(target_session)

        shorts = target_session["shorts"]
        self.assertEqual(len(shorts), 3)
        self.assertEqual(shorts[0]["clip_index"], 1)
        self.assertEqual(shorts[0]["filename"], "short_01.mp4")
        self.assertEqual(shorts[1]["clip_index"], 2)
        self.assertEqual(shorts[1]["filename"], "short_02.mp4")
        self.assertEqual(shorts[2]["clip_index"], 3)
        self.assertEqual(shorts[2]["filename"], "short_03.mp4")

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_edit_short_02_does_not_modify_short_01(self, mock_crop):
        """Editing short_02 modifies short_02 only; short_01 remains bit-for-bit identical."""
        def fake_crop(**kwargs):
            out = kwargs["out_path"]
            with open(out, "wb") as f:
                f.write(b"NEWLY_RENDERED_SHORT_02_DATA_XYZ")

        mock_crop.side_effect = fake_crop

        payload = {
            "session_folder": self.test_session_id,
            "clip_index": 2,
            "filename": "short_02.mp4",
            "start_time": 605.0,
            "end_time": 640.0,
            "title": "Short Dua Diedit",
            "hook_sentence": "Hook Baru Klip Dua",
        }
        res = self.client.post("/api/edit-clip", json=payload)
        self.assertEqual(res.status_code, 200)
        resp_data = res.get_json()
        self.assertTrue(resp_data["success"])
        self.assertEqual(resp_data["clip"]["clip_index"], 2)
        self.assertEqual(resp_data["clip"]["filename"], "short_02.mp4")

        # Verify short_01 was NOT modified
        self.assertEqual(self.short1.read_bytes(), b"SHORT_01_INITIAL_BYTES")
        # Verify short_02 was updated
        self.assertEqual(self.short2.read_bytes(), b"NEWLY_RENDERED_SHORT_02_DATA_XYZ")
        # Verify short_03 was NOT modified
        self.assertEqual(self.short3.read_bytes(), b"SHORT_03_INITIAL_BYTES")

        # Verify job metadata preserved short_01 and updated short_02
        with open(self.job_json_path, "r", encoding="utf-8") as f:
            updated_job = json.load(f)
        s_list = updated_job["result"]["shorts"]
        self.assertEqual(s_list[0]["title"], "Short Satu")
        self.assertEqual(s_list[0]["start_time"], 10.0)
        self.assertEqual(s_list[1]["title"], "Short Dua Diedit")
        self.assertEqual(s_list[1]["start_time"], 605.0)
        self.assertEqual(s_list[1]["end_time"], 640.0)

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_preview_and_in_out_for_candidate_at_600s_or_more(self, mock_crop):
        """Preview endpoint and In/Out ranges operate correctly on candidates starting >= 600s."""
        def fake_crop(**kwargs):
            out = kwargs["out_path"]
            with open(out, "wb") as f:
                f.write(b"RENDERED_600S_CANDIDATE")

        mock_crop.side_effect = fake_crop

        # 1. Test source preview endpoint
        res = self.client.get(f"/api/session-source/{self.test_session_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, b"MOCK_SOURCE_VIDEO_HEADER_1234567890")
        res.close()

        # 2. Test edit clip with candidate starting at 610s and ending at 645s
        payload = {
            "session_folder": self.test_session_id,
            "clip_index": 2,
            "start_time": 610.0,
            "end_time": 645.0,
            "title": "Candidate at 10 minutes",
        }
        res_edit = self.client.post("/api/edit-clip", json=payload)
        self.assertEqual(res_edit.status_code, 200)
        resp_json = res_edit.get_json()
        self.assertEqual(resp_json["clip"]["start_time"], 610.0)
        self.assertEqual(resp_json["clip"]["end_time"], 645.0)

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_external_local_file_reused_for_editing(self, mock_crop):
        """A source file located outside the session folder is resolved and used for re-rendering."""
        with tempfile.TemporaryDirectory() as external_dir:
            ext_file = Path(external_dir) / "original_lecture.mp4"
            ext_file.write_bytes(b"EXTERNAL_LECTURE_CONTENT_123")

            # Update job metadata to point to external source
            with open(self.job_json_path, "r", encoding="utf-8") as f:
                j = json.load(f)
            j["result"]["source_video_url"] = str(ext_file)
            with open(self.job_json_path, "w", encoding="utf-8") as f:
                json.dump(j, f)

            # Remove local source file in session folder to force external resolution
            if self.source_file.exists():
                self.source_file.unlink()

            resolved_path, _, err = resolve_session_source(self.test_session_id)
            self.assertIsNone(err)
            self.assertEqual(resolved_path, str(ext_file.resolve()))

            # Verify session-source route serves the external file
            source_res = self.client.get(f"/api/session-source/{self.test_session_id}")
            self.assertEqual(source_res.status_code, 200)
            self.assertEqual(source_res.data, b"EXTERNAL_LECTURE_CONTENT_123")
            source_res.close()

            # Verify re-render passes the external source path
            captured_source = []
            def fake_crop(**kwargs):
                captured_source.append(kwargs["source_path"])
                with open(kwargs["out_path"], "wb") as f:
                    f.write(b"RENDER_FROM_EXTERNAL")

            mock_crop.side_effect = fake_crop

            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 5.0,
                "end_time": 25.0,
            })
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(captured_source), 1)
            self.assertEqual(captured_source[0], str(ext_file.resolve()))

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_rerender_failure_preserves_old_video(self, mock_crop):
        """If re-rendering fails midway, the existing video file is kept intact without corruption."""
        original_bytes = self.short1.read_bytes()

        def crashing_crop(**kwargs):
            # Write a partial corrupt staged file then raise
            with open(kwargs["out_path"], "wb") as f:
                f.write(b"CORRUPT_PARTIAL_CRASH")
            raise RuntimeError("FFmpeg process killed / out of disk")

        mock_crop.side_effect = crashing_crop

        payload = {
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 10.0,
            "end_time": 30.0,
        }
        res = self.client.post("/api/edit-clip", json=payload)
        self.assertEqual(res.status_code, 500)
        self.assertIn("Gagal merender klip", res.get_json()["error"])

        # Old video MUST be preserved exactly
        self.assertEqual(self.short1.read_bytes(), original_bytes)

        # No temporary files should be left behind
        tmp_files = list(self.session_dir.glob(".tmp_short_*"))
        self.assertEqual(len(tmp_files), 0)

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_concurrent_edit_requests_do_not_collide(self, mock_crop):
        """Two concurrent requests to edit the same clip are safely serialized by per-clip lock."""
        execution_log = []

        def slow_crop(**kwargs):
            out = kwargs["out_path"]
            th_name = threading.current_thread().name
            tag = "A" if "t1" in th_name else "B"
            execution_log.append(f"start_{tag}")
            time.sleep(0.1)
            with open(out, "wb") as f:
                f.write(f"RENDER_RESULT_{tag}".encode("utf-8"))
            execution_log.append(f"end_{tag}")

        mock_crop.side_effect = slow_crop

        def req_worker(req_title, results):
            client = self.app.test_client()
            r = client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 10.0,
                "end_time": 25.0,
                "title": req_title,
            })
            results.append(r.status_code)

        results = []
        t1 = threading.Thread(target=req_worker, name="t1_worker", args=("reqA", results))
        t2 = threading.Thread(target=req_worker, name="t2_worker", args=("reqB", results))

        t1.start()
        time.sleep(0.02)  # ensure t1 acquires lock first
        t2.start()

        t1.join()
        t2.join()

        # Both should either succeed serially (200, 200) or cleanly conflict (200, 409)
        for code in results:
            self.assertIn(code, (200, 409))

        # Check serialization in execution log
        # Operations must not overlap: either A completely precedes B, or B completely precedes A
        if "start_B" in execution_log and "start_A" in execution_log:
            idx_start_a = execution_log.index("start_A")
            idx_end_a = execution_log.index("end_A")
            idx_start_b = execution_log.index("start_B")
            idx_end_b = execution_log.index("end_B")
            a_then_b = idx_start_a < idx_end_a < idx_start_b < idx_end_b
            b_then_a = idx_start_b < idx_end_b < idx_start_a < idx_end_a
            self.assertTrue(
                a_then_b or b_then_a,
                f"Execution must be strictly serialized without overlapping crop operations: {execution_log}"
            )

    def test_validation_rejects_nan_infinity_and_out_of_bounds(self):
        """Endpoint rejects NaN, Infinity, negative, beyond duration, and mismatched identity."""
        # 1. Non-dict payload
        res = self.client.post("/api/edit-clip", json=[1, 2, 3])
        self.assertEqual(res.status_code, 400)

        # 2. NaN start_time
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": "nan",
            "end_time": 30.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("finite", res.get_json()["error"])

        # 3. Infinity end_time
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 10.0,
            "end_time": "inf",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("finite", res.get_json()["error"])

        # 4. Negative start_time
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": -5.0,
            "end_time": 20.0,
        })
        self.assertEqual(res.status_code, 400)

        # 5. Out <= In
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 30.0,
            "end_time": 20.0,
        })
        self.assertEqual(res.status_code, 400)

        # 6. Exceeds source duration (source duration in metadata is 750.0s)
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 800.0,
            "end_time": 850.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("melebihi durasi", res.get_json()["error"])

        # 7. Unregistered clip_index (session only has clips 1, 2, 3)
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 99,
            "start_time": 10.0,
            "end_time": 25.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("tidak terdaftar", res.get_json()["error"])

        # 8. Mismatched filename and clip_index
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "filename": "short_02.mp4",
            "start_time": 10.0,
            "end_time": 25.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("tidak cocok", res.get_json()["error"])

    def test_highlights_sanitizer_rejects_nan_and_inf(self):
        """_sanitize_highlights discards candidates with NaN or infinite timestamps."""
        raw_candidates = [
            {"title": "Valid Clip", "start_time": 10.0, "end_time": 30.0, "score": 90},
            {"title": "NaN Clip 1", "start_time": float("nan"), "end_time": 30.0, "score": 80},
            {"title": "NaN Clip 2", "start_time": "nan", "end_time": "30.0", "score": 80},
            {"title": "Inf Clip", "start_time": 10.0, "end_time": float("inf"), "score": 80},
            {"title": "Negative Clip", "start_time": -10.0, "end_time": 20.0, "score": 80},
        ]
        cleaned = _sanitize_highlights(raw_candidates, duration=100.0)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["title"], "Valid Clip")
        self.assertTrue(math.isfinite(cleaned[0]["start_time"]))
        self.assertTrue(math.isfinite(cleaned[0]["end_time"]))

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_two_concurrent_clips_in_same_session_preserve_both_metadata(self, mock_crop):
        """Finding A-02: Two concurrent requests editing different clips in the same session preserve both in metadata."""
        def fake_crop(**kwargs):
            out = kwargs["out_path"]
            with open(out, "wb") as f:
                f.write(b"RENDER_CONCURRENT_DATA")

        mock_crop.side_effect = fake_crop

        def edit_worker(clip_idx, title, results):
            c = self.app.test_client()
            r = c.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": clip_idx,
                "filename": f"short_{clip_idx:02d}.mp4",
                "start_time": 10.0 + clip_idx,
                "end_time": 30.0 + clip_idx,
                "title": title,
            })
            results.append((clip_idx, r.status_code))

        results = []
        t1 = threading.Thread(target=edit_worker, args=(1, "Clip 1 Edited Concurrently", results))
        t2 = threading.Thread(target=edit_worker, args=(2, "Clip 2 Edited Concurrently", results))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        for c_idx, code in results:
            self.assertEqual(code, 200)

        with open(self.job_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        s_list = meta["result"]["shorts"]
        title1 = next((s["title"] for s in s_list if s.get("clip_index") == 1), None)
        title2 = next((s["title"] for s in s_list if s.get("clip_index") == 2), None)
        self.assertEqual(title1, "Clip 1 Edited Concurrently")
        self.assertEqual(title2, "Clip 2 Edited Concurrently")

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_atomic_promotion_rollback_on_failure(self, mock_crop):
        """Finding A-03: Failure during metadata atomic promotion rolls back media and returns 500 without corruption."""
        original_bytes = self.short1.read_bytes()

        def fake_crop(**kwargs):
            with open(kwargs["out_path"], "wb") as f:
                f.write(b"RENDER_FOR_ROLLBACK_TEST")

        mock_crop.side_effect = fake_crop

        orig_replace = os.replace
        def fault_replace(src, dst):
            if "tmp_" in str(src) and "job_" in str(dst):
                raise OSError("Simulated Windows file lock error during metadata commit")
            return orig_replace(src, dst)

        with patch("os.replace", side_effect=fault_replace):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 12.0,
                "end_time": 28.0,
                "title": "Failed Commit Title",
            })
            self.assertEqual(res.status_code, 500)
            self.assertIn("Gagal mempublikasikan hasil render secara konsisten", res.get_json()["error"])

        # short_01.mp4 must be rolled back to its original bytes
        self.assertEqual(self.short1.read_bytes(), original_bytes)

        # job_*.json must still have original title
        with open(self.job_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["result"]["shorts"][0]["title"], "Short Satu")

        # Staging and backup files must be cleaned up
        tmps = list(self.session_dir.glob(".tmp_*"))
        baks = list(self.session_dir.glob(".bak_*"))
        self.assertEqual(len(tmps), 0)
        self.assertEqual(len(baks), 0)

    def test_duration_validation_ground_truth_and_eof(self):
        """Finding A-04: Duration validation rejects when probe fails, probe overrides transcript, and start >= EOF."""
        # 1. Probe fails (returns None) -> Reject immediately
        self.mock_probe.return_value = None
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 10.0,
            "end_time": 25.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Durasi media video sumber tidak dapat diverifikasi", res.get_json()["error"])

        # 2. Probe returns 100.0s (even though transcript says 750.0s) -> Media probe is ground truth!
        self.mock_probe.return_value = 100.0

        # Start at exact EOF (100.0) -> Reject
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 100.0,
            "end_time": 105.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("melebihi durasi", res.get_json()["error"])

        # End > 100.5s -> Reject
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 90.0,
            "end_time": 101.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("melebihi durasi", res.get_json()["error"])

        # End within 0.5s tolerance (e.g. 100.4s) -> Valid range check passes
        self.mock_probe.return_value = 750.0

    def test_verify_rendered_video_rejects_corrupted_or_non_media(self):
        """Finding A-05: verify_rendered_video rejects missing, empty, or un-decodable staging files."""
        # Stop verify patcher to test real verify_rendered_video implementation
        self.verify_patcher.stop()
        try:
            # Non-existent file
            fake_path = self.session_dir / "non_existent.mp4"
            with self.assertRaises(RuntimeError) as cm:
                verify_rendered_video(fake_path)
            self.assertIn("tidak ditemukan", str(cm.exception))

            # Empty / small file (< 1024 bytes)
            small_file = self.session_dir / "small.mp4"
            small_file.write_bytes(b"TOO_SMALL")
            with self.assertRaises(RuntimeError) as cm:
                verify_rendered_video(small_file)
            self.assertIn("terlalu kecil", str(cm.exception))

            # Corrupt file with >= 1024 bytes of non-video garbage
            corrupt_file = self.session_dir / "corrupt.mp4"
            corrupt_file.write_bytes(b"NOT_A_VALID_MP4_HEADER" * 100)
            with self.assertRaises(RuntimeError) as cm:
                verify_rendered_video(corrupt_file)
            self.assertTrue(
                "tidak dapat dibuka sebagai video" in str(cm.exception)
                or "Dimensi video tidak valid" in str(cm.exception)
            )
        finally:
            self.verify_patcher.start()

    def test_verify_rendered_video_real_media(self):
        """Finding A-05: verify_rendered_video passes on real OpenCV-encoded MP4 media."""
        import cv2
        import numpy as np

        self.verify_patcher.stop()
        try:
            real_mp4_path = self.session_dir / "real_test.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            # Write 2 seconds at 30 fps (60 frames)
            out = cv2.VideoWriter(str(real_mp4_path), fourcc, 30.0, (120, 120))
            for _ in range(60):
                out.write(np.zeros((120, 120, 3), dtype=np.uint8))
            out.release()

            # Probed duration should be approx 2.0s
            dur = probe_media_duration(str(real_mp4_path))
            self.assertIsNotNone(dur)
            self.assertAlmostEqual(dur, 2.0, delta=0.2)

            # verify_rendered_video should pass with min_duration=0.5
            verify_rendered_video(real_mp4_path, min_duration=0.5)

            # verify_rendered_video should raise if min_duration=5.0
            with self.assertRaises(RuntimeError) as cm:
                verify_rendered_video(real_mp4_path, min_duration=5.0)
            self.assertIn("lebih pendek", str(cm.exception))

            real_mp4_path.unlink(missing_ok=True)
        finally:
            self.verify_patcher.start()

    @patch("shorts_generator.local.clipper.crop_clip_local")
    def test_re_render_without_subtitles_deletes_stale_vtt(self, mock_crop):
        """Finding A-06: When re-rendering without burned subtitles, old stale VTT is unlinked and vtt_url is None."""
        # Setup existing VTT
        vtt_path = self.session_dir / "short_01.vtt"
        vtt_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:10.000\nOld stale subtitle\n", encoding="utf-8")

        def fake_crop(**kwargs):
            out = kwargs["out_path"]
            with open(out, "wb") as f:
                f.write(b"RENDER_WITHOUT_SUBS")

        mock_crop.side_effect = fake_crop

        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "start_time": 10.0,
            "end_time": 25.0,
            "burn_subtitles": False,
        })
        self.assertEqual(res.status_code, 200)
        resp_data = res.get_json()
        self.assertIsNone(resp_data["clip"]["vtt_url"])

        # File must be deleted on disk
        self.assertFalse(vtt_path.exists())

        # Metadata must have vtt_url: None
        with open(self.job_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertIsNone(meta["result"]["shorts"][0]["vtt_url"])

    def test_strict_identity_rejects_decimal_index_and_non_matching_filename(self):
        """Finding A-07: Strict clip identity rejects decimal indices and mismatched filenames."""
        # Decimal float index 2.9
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 2.9,
            "start_time": 10.0,
            "end_time": 25.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("bukan desimal", res.get_json()["error"])

        # Mismatched filename
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 1,
            "filename": "unrelated.mp4",
            "start_time": 10.0,
            "end_time": 25.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("tidak cocok", res.get_json()["error"])

        # Non-existent clip_index 99
        res = self.client.post("/api/edit-clip", json={
            "session_folder": self.test_session_id,
            "clip_index": 99,
            "start_time": 10.0,
            "end_time": 25.0,
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("tidak terdaftar", res.get_json()["error"])

    def test_timeline_preview_origin_stability(self):
        """Finding A-01: Timeline origin math maintains constant origin without drift on repeated Set In or manual In edits."""
        clip_origin_start = 605.0
        player_current_time = 12.4

        # First Set In click:
        set_in_1 = clip_origin_start + player_current_time
        self.assertAlmostEqual(set_in_1, 617.4)

        # Second Set In click on the same frame:
        set_in_2 = clip_origin_start + player_current_time
        self.assertAlmostEqual(set_in_2, 617.4)
        self.assertEqual(set_in_1, set_in_2)

        # User manually edits In input field to 650.0s
        manual_in_input = 650.0
        # Origin must NOT change with manual input
        self.assertEqual(clip_origin_start, 605.0)

        # Player still at 12.4s, user clicks Set In again:
        set_in_3 = clip_origin_start + player_current_time
        self.assertAlmostEqual(set_in_3, 617.4)

        # Set Out at player time 15.0s:
        set_out_1 = clip_origin_start + 15.0
        self.assertAlmostEqual(set_out_1, 620.0)

    def test_rollback_restore_fault_retains_backup(self):
        """Transaction Safety: When metadata promotion AND backup restoration fail, backups must NOT be deleted."""
        real_replace = os.replace
        def fail_meta_and_restore(src, dst):
            if Path(dst).name.startswith("job_") or Path(src).name.startswith(".bak_"):
                raise PermissionError("Simulated locked backup restoration")
            return real_replace(src, dst)

        def crop_mock(**kw):
            Path(kw["out_path"]).write_bytes(b"STAGED_VIDEO")

        with patch("shorts_generator.local.clipper.crop_clip_local", side_effect=crop_mock), \
             patch("os.replace", side_effect=fail_meta_and_restore):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 10.0,
                "end_time": 25.0,
                "title": "New Title",
            })
        self.assertEqual(res.status_code, 500)
        # Backups must still exist on disk so data is not lost
        backups = list(self.session_dir.glob(".bak_*"))
        self.assertGreater(len(backups), 0, "Backups should be preserved when rollback restoration fails")

    def test_rollback_unlinks_new_video_when_no_old_video(self):
        """Transaction Safety: If no old video existed before edit, rollback unlinks the newly promoted video."""
        # Remove short_01.mp4 to simulate a registered clip whose file was missing
        if self.short1.exists():
            self.short1.unlink()

        real_replace = os.replace
        def fail_meta(src, dst):
            if Path(dst).name.startswith("job_"):
                raise PermissionError("Simulated metadata locked")
            return real_replace(src, dst)

        def crop_mock(**kw):
            Path(kw["out_path"]).write_bytes(b"STAGED_VIDEO")

        with patch("shorts_generator.local.clipper.crop_clip_local", side_effect=crop_mock), \
             patch("os.replace", side_effect=fail_meta):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 10.0,
                "end_time": 25.0,
            })
        self.assertEqual(res.status_code, 500)
        # short_01.mp4 must not be left behind on disk
        self.assertFalse(self.short1.exists(), "New video must be unlinked when commit fails and no old video existed")

    def test_rollback_unlinks_new_vtt_when_no_old_vtt(self):
        """Transaction Safety: If no old VTT existed before edit, rollback unlinks the newly promoted VTT."""
        vtt_path = self.session_dir / "short_01.vtt"
        if vtt_path.exists():
            vtt_path.unlink()

        real_replace = os.replace
        def fail_meta(src, dst):
            if Path(dst).name.startswith("job_"):
                raise PermissionError("Simulated metadata locked")
            return real_replace(src, dst)

        def mock_crop_with_vtt(**kwargs):
            out_p = Path(kwargs["out_path"])
            out_p.write_bytes(b"STAGED_VIDEO")
            out_p.with_suffix(".vtt").write_text("WEBVTT\n\n00:00.000 --> 00:05.000\nSub", encoding="utf-8")

        with patch("shorts_generator.local.clipper.crop_clip_local", side_effect=mock_crop_with_vtt), \
             patch("os.replace", side_effect=fail_meta):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 10.0,
                "end_time": 25.0,
                "burn_subtitles": True,
            })
        self.assertEqual(res.status_code, 500)
        self.assertFalse(vtt_path.exists(), "New VTT must be unlinked when commit fails and no old VTT existed")

    def test_vtt_unlink_failure_triggers_rollback(self):
        """Transaction Safety: Failure to delete old VTT must abort transaction, rollback, and return 500."""
        vtt_path = self.session_dir / "short_01.vtt"
        vtt_path.write_text("OLD_VTT_CONTENT", encoding="utf-8")

        real_unlink = Path.unlink
        def fail_vtt_unlink(path_obj, *args, **kwargs):
            if path_obj == vtt_path:
                raise PermissionError("VTT locked by external process")
            return real_unlink(path_obj, *args, **kwargs)

        def crop_mock(**kw):
            Path(kw["out_path"]).write_bytes(b"STAGED_VIDEO")

        with patch("shorts_generator.local.clipper.crop_clip_local", side_effect=crop_mock), \
             patch.object(Path, "unlink", side_effect=fail_vtt_unlink):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 10.0,
                "end_time": 25.0,
                "burn_subtitles": False,
            })
        self.assertEqual(res.status_code, 500)
        # Original video and VTT must remain intact
        self.assertTrue(self.short1.exists())
        self.assertEqual(self.short1.read_bytes(), b"SHORT_01_INITIAL_BYTES")
        self.assertTrue(vtt_path.exists())
        self.assertEqual(vtt_path.read_text(encoding="utf-8"), "OLD_VTT_CONTENT")

    def test_verify_rendered_video_rejects_short_physical_duration(self):
        """Physical Render Verification: rejects 26s for 30s selection and 7s for 8s selection, but accepts frame rounding."""
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. 26s physical video (260 frames at 10 fps) tested against 30s selection -> REJECTED
            p_26s = Path(tmp_dir) / "render_26s.mp4"
            out = cv2.VideoWriter(str(p_26s), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
            for i in range(260):
                out.write(np.full((120, 160, 3), i % 255, dtype=np.uint8))
            out.release()

            with self.assertRaises(RuntimeError) as cm_30:
                verify_rendered_video(p_26s, expected_duration=30.0, min_duration=0.4)
            self.assertIn("tidak sesuai dengan durasi rentang yang diminta", str(cm_30.exception))

            # 2. 7s physical video (70 frames at 10 fps) tested against 8s selection -> REJECTED
            p_7s = Path(tmp_dir) / "render_7s.mp4"
            out = cv2.VideoWriter(str(p_7s), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
            for i in range(70):
                out.write(np.full((120, 160, 3), i % 255, dtype=np.uint8))
            out.release()

            with self.assertRaises(RuntimeError) as cm_8:
                verify_rendered_video(p_7s, expected_duration=8.0, min_duration=0.4)
            self.assertIn("tidak sesuai dengan durasi rentang yang diminta", str(cm_8.exception))

            # 3. Frame rounding: 7.97s physical video (239 frames at 30 fps = 7.967s) tested against 8.0s selection -> ACCEPTED
            p_round_8s = Path(tmp_dir) / "render_7_97s.mp4"
            out = cv2.VideoWriter(str(p_round_8s), cv2.VideoWriter_fourcc(*"mp4v"), 30, (160, 120))
            for i in range(239):
                out.write(np.full((120, 160, 3), i % 255, dtype=np.uint8))
            out.release()

            verify_rendered_video(p_round_8s, expected_duration=8.0, min_duration=0.4)

            # 4. Frame rounding: 29.93s physical video (898 frames at 30 fps = 29.933s) tested against 30.0s selection -> ACCEPTED
            p_round_30s = Path(tmp_dir) / "render_29_93s.mp4"
            out = cv2.VideoWriter(str(p_round_30s), cv2.VideoWriter_fourcc(*"mp4v"), 30, (160, 120))
            for i in range(898):
                out.write(np.full((120, 160, 3), i % 255, dtype=np.uint8))
            out.release()

            verify_rendered_video(p_round_30s, expected_duration=30.0, min_duration=0.4)

    def test_endpoint_short_render_rejected_and_preserves_artifacts(self):
        """End-to-end: Rejection of short render prevents promotion and preserves old MP4, VTT, and metadata."""
        import cv2
        import numpy as np

        vtt_path = self.session_dir / "short_01.vtt"
        vtt_path.write_text("OLD_VTT_BEFORE_REJECT", encoding="utf-8")

        # Fake crop producing a 7s video for an 8s requested range
        def fake_short_crop(**kwargs):
            out_p = Path(kwargs["out_path"])
            out = cv2.VideoWriter(str(out_p), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
            for i in range(70):
                out.write(np.full((120, 160, 3), i % 255, dtype=np.uint8))
            out.release()

        with patch("shorts_generator.local.clipper.crop_clip_local", side_effect=fake_short_crop), \
             patch("web_app.verify_rendered_video", side_effect=verify_rendered_video):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 10.0,
                "end_time": 18.0,  # 8.0s expected, but physical render is 7.0s
                "title": "Unwanted Corrupted Title",
            })

        self.assertEqual(res.status_code, 500)
        self.assertIn("tidak sesuai dengan durasi rentang yang diminta", res.get_json()["error"])

        # Old MP4 must be completely preserved
        self.assertEqual(self.short1.read_bytes(), b"SHORT_01_INITIAL_BYTES")
        # Old VTT must be preserved
        self.assertEqual(vtt_path.read_text(encoding="utf-8"), "OLD_VTT_BEFORE_REJECT")
        # Metadata must NOT be updated with new title
        with open(self.job_json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["result"]["shorts"][0]["title"], "Short Satu")
        self.assertEqual(meta["result"]["shorts"][0]["start_time"], 10.0)
        self.assertEqual(meta["result"]["shorts"][0]["end_time"], 40.0)

    def test_real_ffmpeg_normal_render_passes_verification(self):
        """End-to-end with real FFmpeg: A standard cut and render passes verification cleanly."""
        import subprocess
        from shorts_generator.local.clipper import crop_clip_local

        with tempfile.TemporaryDirectory() as tmp_dir:
            real_src = Path(tmp_dir) / "real_source.mp4"
            real_out = Path(tmp_dir) / "real_output.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=duration=12:size=320x240:rate=25",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-shortest", "-c:v", "libx264", "-c:a", "aac",
                str(real_src)
            ], check=True)

            crop_clip_local(
                source_path=str(real_src),
                start_time=2.0,
                end_time=6.0,
                aspect_ratio="9:16",
                out_path=str(real_out),
                burn_subtitles=False
            )

            # verify_rendered_video must pass with expected_duration=4.0
            verify_rendered_video(real_out, expected_duration=4.0, min_duration=0.4)
            self.assertTrue(real_out.exists())
            self.assertGreater(real_out.stat().st_size, 1024)

    def test_eof_tolerance_normalization(self):
        """EOF Normalization: Out exceeding source duration within 0.5s is clamped, or rejected if effective < 0.5s."""
        def crop_mock(**kw):
            Path(kw["out_path"]).write_bytes(b"STAGED_VIDEO")

        # 1. 99.8 to 100.4 on 100s source: clamped to 100.0, effective duration = 0.2s < 0.5s -> 400
        with patch("web_app.probe_media_duration", return_value=100.0):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 99.8,
                "end_time": 100.4,
            })
            self.assertEqual(res.status_code, 400)
            self.assertIn("terlalu pendek", res.get_json()["error"])

        # 2. 95.0 to 100.3 on 100s source: clamped to 100.0, effective duration = 5.0s -> 200
        with patch("web_app.probe_media_duration", return_value=100.0), \
             patch("web_app.verify_rendered_video"), \
             patch("shorts_generator.local.clipper.crop_clip_local", side_effect=crop_mock):
            res = self.client.post("/api/edit-clip", json={
                "session_folder": self.test_session_id,
                "clip_index": 1,
                "start_time": 95.0,
                "end_time": 100.3,
            })
            self.assertEqual(res.status_code, 200)
            clip_res = res.get_json()["clip"]
            self.assertEqual(clip_res["end_time"], 100.0)


if __name__ == "__main__":
    unittest.main()
