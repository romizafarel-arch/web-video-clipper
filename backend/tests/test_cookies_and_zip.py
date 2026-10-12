import io
import json
import os
import shutil
import tempfile
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from web_app import app, OUTPUT_DIR
from shorts_generator.local.downloader import download_youtube_local


class TestCookiesAndZipFeatures(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.test_session_name = "test_bundle_session_1234"
        self.session_dir = OUTPUT_DIR / self.test_session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Create sample clips and vtt
        (self.session_dir / "short_1.mp4").write_bytes(b"dummy video data 1")
        (self.session_dir / "short_2.mp4").write_bytes(b"dummy video data 2")
        (self.session_dir / "short_1.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:05.000\nHello", encoding="utf-8")
        # Source video should NOT be included in zip
        (self.session_dir / "source_raw.mp4").write_bytes(b"raw master video")

    def tearDown(self):
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)

    def test_session_zip_success(self):
        """Test GET /api/sessions/<folder>/zip packages clips and excludes raw source."""
        resp = self.client.get(f"/api/sessions/{self.test_session_name}/zip")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/zip", resp.headers.get("Content-Type", ""))
        self.assertIn(f"{self.test_session_name}_clips.zip", resp.headers.get("Content-Disposition", ""))

        # Verify ZIP archive contents
        zip_buf = io.BytesIO(resp.data)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            names = set(zf.namelist())
            self.assertIn("short_1.mp4", names)
            self.assertIn("short_2.mp4", names)
            self.assertIn("short_1.vtt", names)
            self.assertNotIn("source_raw.mp4", names)

        # Ensure response close cleans up
        resp.close()

    def test_session_zip_not_found(self):
        """Test GET /api/sessions/<folder>/zip returns 404 for nonexistent sessions."""
        resp = self.client.get("/api/sessions/non_existent_folder_abc/zip")
        self.assertEqual(resp.status_code, 404)

    def test_session_zip_path_traversal_blocked(self):
        """Test directory traversal attempts in session zip are rejected."""
        resp = self.client.get("/api/sessions/..%2F..%2Fetc/zip")
        self.assertIn(resp.status_code, (400, 404))

    @patch("web_app.run_generation_job")
    def test_generate_endpoint_with_cookies_file(self, mock_run_job):
        """Test POST /api/generate accepts multipart cookies_file and stores cookies_path."""
        payload_data = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "mode": "local",
            "num_clips": 2,
            "aspect_ratio": "9:16",
        }
        cookies_bytes = io.BytesIO(b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1799999999\tLOGIN_INFO\tabc")

        resp = self.client.post(
            "/api/generate",
            data={
                "data": json.dumps(payload_data),
                "cookies_file": (cookies_bytes, "cookies.txt"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("job_id", data)

        # Inspect arguments passed to worker thread
        mock_run_job.assert_called_once()
        args = mock_run_job.call_args[0]
        job_params = args[1]
        self.assertIn("cookies_path", job_params)
        self.assertTrue(job_params["cookies_path"])
        self.assertTrue(os.path.exists(job_params["cookies_path"]))
        self.assertTrue(job_params["cookies_path"].endswith(".txt"))

        # Clean up created cookies file and session folder
        if os.path.exists(job_params["cookies_path"]):
            os.unlink(job_params["cookies_path"])
        sess_dir = OUTPUT_DIR / job_params["session_folder"]
        if sess_dir.exists():
            shutil.rmtree(sess_dir, ignore_errors=True)

    @patch("shorts_generator.local.downloader._import_ytdlp")
    def test_downloader_uses_cookiefile(self, mock_import):
        """Test download_youtube_local passes cookiefile to yt_dlp when cookies_path exists."""
        mock_ydl_cls = MagicMock()
        mock_import.return_value = MagicMock(YoutubeDL=mock_ydl_cls)
        mock_instance = mock_ydl_cls.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {"id": "test123"}
        mock_instance.prepare_filename.return_value = str(self.session_dir / "source_test123_720p.mp4")

        # Create actual dummy cookies file
        cookie_file = self.session_dir / "my_cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File", encoding="utf-8")

        download_youtube_local(
            video_url="https://www.youtube.com/watch?v=test123",
            fmt="720",
            out_dir=str(self.session_dir),
            cookies_path=str(cookie_file),
        )

        mock_ydl_cls.assert_called_once()
        opts = mock_ydl_cls.call_args[0][0]
        self.assertIn("cookiefile", opts)
        self.assertEqual(opts["cookiefile"], str(cookie_file))


if __name__ == "__main__":
    unittest.main()
