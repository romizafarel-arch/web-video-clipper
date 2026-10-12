"""Unit and integration tests for AUTO_DELETE_SOURCE_VIDEO auto-cleanup feature."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import shorts_generator.config as cfg
from shorts_generator.pipeline import cleanup_source_video, generate_shorts
import web_app


class TestAutoDeleteSourceConfig(unittest.TestCase):
    def test_default_config_is_true(self):
        """AUTO_DELETE_SOURCE_VIDEO should default to True."""
        self.assertTrue(getattr(cfg, "AUTO_DELETE_SOURCE_VIDEO", None))

    def test_env_parsing(self):
        """Should parse truthy and falsy strings correctly."""
        for val, expected in [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("", False),
        ]:
            with patch.dict(os.environ, {"AUTO_DELETE_SOURCE_VIDEO": val}):
                parsed = os.getenv("AUTO_DELETE_SOURCE_VIDEO", "true").strip().lower() in ("true", "1", "yes")
                self.assertEqual(parsed, expected)


class TestCleanupSourceVideo(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_cleanup_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_safely_deletes_source_files_only(self):
        """Deletes source_* files, strictly keeping short_*, *.vtt, and job_*.json."""
        # Create various files in test_dir
        source_mp4 = Path(self.test_dir) / "source_abc123_720p.mp4"
        source_mkv = Path(self.test_dir) / "source_xyz_1080p.mkv"
        source_part = Path(self.test_dir) / "source_temp.mp4.part"
        short_01 = Path(self.test_dir) / "short_01.mp4"
        short_02 = Path(self.test_dir) / "short_02.mp4"
        sub_01 = Path(self.test_dir) / "short_01.vtt"
        job_meta = Path(self.test_dir) / "job_abcdef12.json"
        custom_user_file = Path(self.test_dir) / "my_custom_video.mp4"

        for p in (source_mp4, source_mkv, source_part, short_01, short_02, sub_01, job_meta, custom_user_file):
            p.write_bytes(b"dummy data 12345")

        deleted = cleanup_source_video(source_path=str(source_mp4), out_dir=self.test_dir)

        # Source files should be deleted
        self.assertFalse(source_mp4.exists())
        self.assertFalse(source_mkv.exists())
        self.assertFalse(source_part.exists())
        self.assertIn(str(source_mp4.resolve()), [str(Path(d).resolve()) for d in deleted])

        # Protected files MUST still exist!
        self.assertTrue(short_01.exists())
        self.assertTrue(short_02.exists())
        self.assertTrue(sub_01.exists())
        self.assertTrue(job_meta.exists())
        self.assertTrue(custom_user_file.exists())

    def test_does_not_delete_user_file_outside_source_pattern(self):
        """If source_path is a personal user file (does not start with source_), do not delete it."""
        user_file = Path(self.test_dir) / "personal_recording.mp4"
        user_file.write_bytes(b"valuable user content")

        deleted = cleanup_source_video(source_path=str(user_file), out_dir=self.test_dir)
        self.assertEqual(deleted, [])
        self.assertTrue(user_file.exists())

    def test_handles_nonexistent_gracefully(self):
        """Gracefully handle missing files without exceptions."""
        nonexistent = str(Path(self.test_dir) / "source_ghost.mp4")
        deleted = cleanup_source_video(source_path=nonexistent, out_dir=self.test_dir)
        self.assertEqual(deleted, [])


class TestPipelineAutoDelete(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_pipe_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("shorts_generator.local.downloader.download_youtube_local")
    @patch("shorts_generator.local.transcriber.transcribe_local")
    @patch("shorts_generator.pipeline.get_highlights")
    @patch("shorts_generator.local.clipper.crop_highlights_local")
    def test_pipeline_deletes_source_when_active_and_success(
        self, mock_crop, mock_highlights, mock_transcribe, mock_download
    ):
        """When auto_delete_source_video=True and rendering succeeds, source file is deleted."""
        source_file = Path(self.test_dir) / "source_vid123_720p.mp4"
        source_file.write_bytes(b"dummy source video")
        short_file = Path(self.test_dir) / "short_01.mp4"
        short_file.write_bytes(b"dummy short clip")

        mock_download.return_value = str(source_file)
        mock_transcribe.return_value = {"segments": [{"start": 0, "end": 10, "text": "hello"}]}
        mock_highlights.return_value = {
            "highlights": [{"score": 90, "start_time": 0, "end_time": 10, "title": "Highlight"}]
        }
        mock_crop.return_value = [{"clip_url": str(short_file), "score": 90}]

        res = generate_shorts(
            youtube_url="https://www.youtube.com/watch?v=vid123",
            mode="local",
            out_dir=self.test_dir,
            auto_delete_source_video=True,
        )

        self.assertTrue(res.get("source_deleted"))
        self.assertFalse(source_file.exists())
        self.assertTrue(short_file.exists())

    @patch("shorts_generator.local.downloader.download_youtube_local")
    @patch("shorts_generator.local.transcriber.transcribe_local")
    @patch("shorts_generator.pipeline.get_highlights")
    @patch("shorts_generator.local.clipper.crop_highlights_local")
    def test_pipeline_keeps_source_when_disabled(
        self, mock_crop, mock_highlights, mock_transcribe, mock_download
    ):
        """When auto_delete_source_video=False, source file is preserved."""
        source_file = Path(self.test_dir) / "source_vid123_720p.mp4"
        source_file.write_bytes(b"dummy source video")
        short_file = Path(self.test_dir) / "short_01.mp4"
        short_file.write_bytes(b"dummy short clip")

        mock_download.return_value = str(source_file)
        mock_transcribe.return_value = {"segments": [{"start": 0, "end": 10, "text": "hello"}]}
        mock_highlights.return_value = {
            "highlights": [{"score": 90, "start_time": 0, "end_time": 10, "title": "Highlight"}]
        }
        mock_crop.return_value = [{"clip_url": str(short_file), "score": 90}]

        res = generate_shorts(
            youtube_url="https://www.youtube.com/watch?v=vid123",
            mode="local",
            out_dir=self.test_dir,
            auto_delete_source_video=False,
        )

        self.assertFalse(res.get("source_deleted"))
        self.assertTrue(source_file.exists())
        self.assertTrue(short_file.exists())

    @patch("shorts_generator.local.downloader.download_youtube_local")
    @patch("shorts_generator.local.transcriber.transcribe_local")
    @patch("shorts_generator.pipeline.get_highlights")
    @patch("shorts_generator.local.clipper.crop_highlights_local")
    def test_pipeline_preserves_source_on_render_failure(
        self, mock_crop, mock_highlights, mock_transcribe, mock_download
    ):
        """When render crashes/fails, source video must NOT be deleted prematurely."""
        source_file = Path(self.test_dir) / "source_vid123_720p.mp4"
        source_file.write_bytes(b"dummy source video")

        mock_download.return_value = str(source_file)
        mock_transcribe.return_value = {"segments": [{"start": 0, "end": 10, "text": "hello"}]}
        mock_highlights.return_value = {
            "highlights": [{"score": 90, "start_time": 0, "end_time": 10, "title": "Highlight"}]
        }
        mock_crop.side_effect = RuntimeError("FFmpeg crashed during cropping")

        with self.assertRaises(RuntimeError):
            generate_shorts(
                youtube_url="https://www.youtube.com/watch?v=vid123",
                mode="local",
                out_dir=self.test_dir,
                auto_delete_source_video=True,
            )

        # Source file MUST be preserved!
        self.assertTrue(source_file.exists())


class TestWebAppApiAutoDelete(unittest.TestCase):
    def setUp(self):
        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    def test_get_config_includes_auto_delete(self):
        """GET /api/config should report auto_delete_source_video."""
        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("auto_delete_source_video", data)
        self.assertIsInstance(data["auto_delete_source_video"], bool)

    def test_post_config_updates_auto_delete(self):
        """POST /api/config should accept and update AUTO_DELETE_SOURCE_VIDEO."""
        with patch("web_app.set_key"):
            res = self.client.post("/api/config", json={"AUTO_DELETE_SOURCE_VIDEO": False})
            self.assertEqual(res.status_code, 200)
            self.assertFalse(cfg.AUTO_DELETE_SOURCE_VIDEO)

            res = self.client.post("/api/config", json={"AUTO_DELETE_SOURCE_VIDEO": "true"})
            self.assertEqual(res.status_code, 200)
            self.assertTrue(cfg.AUTO_DELETE_SOURCE_VIDEO)

    @patch("web_app.threading.Thread")
    def test_api_generate_passes_auto_delete_flag(self, mock_thread):
        """POST /api/generate should read auto_delete_source_video and pass to worker."""
        # Ensure no active jobs block testing
        web_app.job_manager._jobs.clear()

        res = self.client.post(
            "/api/generate",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "auto_delete_source_video": False,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        job_id = data["job_id"]

        job = web_app.job_manager.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertFalse(job.params.get("auto_delete_source_video"))


if __name__ == "__main__":
    unittest.main()
