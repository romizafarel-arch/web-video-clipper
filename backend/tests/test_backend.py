import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from shorts_generator.local.transcriber import (
    _transcript_cache_paths,
    _write_transcript_cache,
    _load_transcript_cache,
)
import web_app


class TestTranscriptCaching(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.fake_video = Path(self.tmp_dir.name) / "test_video.mp4"
        self.fake_video.write_bytes(b"dummy video content for hashing")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_cache_keys_vary_by_attributes(self):
        json1, srt1 = _transcript_cache_paths(
            str(self.fake_video), provider="whisper", model="base", language="id"
        )
        json2, srt2 = _transcript_cache_paths(
            str(self.fake_video), provider="whisper", model="large", language="id"
        )
        json3, srt3 = _transcript_cache_paths(
            str(self.fake_video), provider="whisper", model="base", language="en"
        )
        json4, srt4 = _transcript_cache_paths(
            str(self.fake_video), provider="gemini", model="base", language="id"
        )

        # All cache paths should differ when provider, model, or language differ
        self.assertNotEqual(json1, json2)
        self.assertNotEqual(json1, json3)
        self.assertNotEqual(json1, json4)

    def test_cache_write_and_read(self):
        sample_transcript = {
            "duration": 60.0,
            "language": "id",
            "text": "Halo dunia",
            "segments": [{"start": 0.0, "end": 2.0, "text": "Halo dunia"}],
        }
        _write_transcript_cache(
            str(self.fake_video),
            sample_transcript,
            provider="whisper",
            model="base",
            language="id",
        )

        # Reading with identical parameters should hit cache
        loaded = _load_transcript_cache(
            str(self.fake_video), provider="whisper", model="base", language="id"
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["duration"], 60.0)
        self.assertEqual(loaded["segments"][0]["text"], "Halo dunia")

        # Reading with different model or language should miss
        miss_model = _load_transcript_cache(
            str(self.fake_video), provider="whisper", model="small", language="id"
        )
        self.assertIsNone(miss_model)

        miss_lang = _load_transcript_cache(
            str(self.fake_video), provider="whisper", model="base", language="en"
        )
        self.assertIsNone(miss_lang)


class TestWebEndpointValidation(unittest.TestCase):
    def setUp(self):
        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    def test_generate_requires_url(self):
        resp = self.client.post("/api/generate", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("URL Video YouTube wajib diisi", resp.get_json()["error"])

    def test_generate_rejects_invalid_url_scheme(self):
        resp = self.client.post("/api/generate", json={"url": "javascript:alert(1)"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Format URL tidak valid", resp.get_json()["error"])

    def test_generate_validates_num_clips(self):
        # String not integer
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "num_clips": "invalid"})
        self.assertEqual(resp.status_code, 400)

        # < 1
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "num_clips": 0})
        self.assertEqual(resp.status_code, 400)

        # > 10
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "num_clips": 15})
        self.assertEqual(resp.status_code, 400)

    def test_generate_validates_aspect_ratio(self):
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "aspect_ratio": "21:9"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Rasio aspek", resp.get_json()["error"])

    def test_generate_validates_format(self):
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "format": "4k"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Resolusi", resp.get_json()["error"])

    def test_generate_validates_mode(self):
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "mode": "cloud"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Mode", resp.get_json()["error"])

    def test_generate_validates_llm_provider(self):
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "llm_provider": "anthropic"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("LLM provider", resp.get_json()["error"])

    def test_generate_validates_transcriber_provider(self):
        resp = self.client.post("/api/generate", json={"url": "https://youtu.be/xyz", "transcriber_provider": "deepgram"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Transcriber provider", resp.get_json()["error"])

    def test_output_file_security_allowlist(self):
        # Disallow non-media extensions
        resp = self.client.get("/output/.env")
        self.assertEqual(resp.status_code, 403)

        resp = self.client.get("/output/config.json")
        self.assertEqual(resp.status_code, 403)

    def test_index_renders_with_editor_and_advanced_settings(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        # Supports React SPA when built, or legacy Jinja template fallback
        self.assertTrue(
            '<div id="root">' in html or "editorModal" in html,
            "Expected React root element or editorModal template",
        )

    def test_edit_clip_validates_inputs(self):
        # Missing session folder
        resp = self.client.post("/api/edit-clip", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("session_folder", resp.get_json()["error"])

        # Non-existent session folder
        resp = self.client.post("/api/edit-clip", json={"session_folder": "non_existent_folder_xyz"})
        self.assertEqual(resp.status_code, 404)

        # Invalid timestamps (start >= end)
        resp = self.client.post(
            "/api/edit-clip",
            json={"session_folder": "dummy", "start_time": 20.0, "end_time": 10.0},
        )
        self.assertIn(resp.status_code, (400, 404))


class TestJobStatusTruthfulness(unittest.TestCase):
    @patch("web_app.generate_shorts")
    def test_job_fails_when_all_renders_fail(self, mock_generate):
        mock_generate.return_value = {
            "shorts": [
                {"clip_url": None, "error": "FFmpeg exit 1"},
                {"clip_url": None, "error": "FFmpeg exit 1"},
            ]
        }
        job_id = "test_fail"
        web_app.jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "stage": "queued",
            "progress": 0,
            "logs": [],
        }
        web_app.run_generation_job(job_id, {"url": "https://youtu.be/dummy", "num_clips": 2})

        self.assertEqual(web_app.jobs[job_id]["status"], "failed")
        self.assertIn("Render gagal total", web_app.jobs[job_id]["error"])

    @patch("web_app.generate_shorts")
    def test_job_partial_when_some_renders_fail(self, mock_generate):
        mock_generate.return_value = {
            "shorts": [
                {"clip_url": "https://example.com/clip1.mp4"},
                {"clip_url": None, "error": "FFmpeg exit 1"},
            ]
        }
        job_id = "test_partial"
        web_app.jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "stage": "queued",
            "progress": 0,
            "logs": [],
        }
        web_app.run_generation_job(job_id, {"url": "https://youtu.be/dummy", "num_clips": 2})

        self.assertEqual(web_app.jobs[job_id]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
