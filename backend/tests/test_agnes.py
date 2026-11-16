import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import web_app
from shorts_generator.agnes import (
    AgnesAPIError,
    agnes_chat,
    build_video_prompt,
    download_video,
    fetch_video_status,
    normalize_base_url,
    submit_video,
)
from web_app import app


class TestAgnesClient(unittest.TestCase):
    def test_normalize_base_url_strips_v1(self):
        self.assertEqual(normalize_base_url("https://apihub.agnes-ai.com/v1/"), "https://apihub.agnes-ai.com")
        self.assertEqual(normalize_base_url("https://apihub.agnes-ai.com"), "https://apihub.agnes-ai.com")

    def test_submit_video_enforces_flash_720p_and_duration_bounds(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"video_id": "vid_123"}
        with patch("shorts_generator.agnes.requests.post", return_value=mock_resp) as post_mock:
            vid = submit_video(
                prompt="Kopi susu hangat di meja kayu",
                model="agnes-video-2.5-flash",
                duration=20,
                aspect_ratio="9:16",
                size="1080P",
                api_key="agnes-secret-key",
            )
        self.assertEqual(vid, "vid_123")
        sent_url = post_mock.call_args[0][0]
        sent_json = post_mock.call_args[1]["json"]
        self.assertEqual(sent_url, "https://apihub.agnes-ai.com/v1/videos")
        self.assertEqual(sent_json["mode"], "text")
        self.assertEqual(sent_json["seconds"], "12")
        self.assertEqual(sent_json["size"], "720P")
        self.assertEqual(sent_json["aspect_ratio"], "9:16")

    def test_fetch_video_status_extracts_completed_url(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"status": "completed", "url": "https://cdn.example.com/out.mp4"}
        with patch("shorts_generator.agnes.requests.get", return_value=mock_resp) as get_mock:
            info = fetch_video_status("vid_123", model_name="agnes-video-2.5-flash", api_key="agnes-key")
        self.assertEqual(info["status"], "completed")
        self.assertEqual(info["url"], "https://cdn.example.com/out.mp4")
        self.assertEqual(get_mock.call_args[1]["params"], {"video_id": "vid_123", "model_name": "agnes-video-2.5-flash"})

    def test_download_video_omits_auth_header(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.iter_content.return_value = [b"fake-mp4-bytes"]
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "short_1.mp4"
            with patch("shorts_generator.agnes.requests.get", return_value=mock_resp) as get_mock:
                out = download_video("https://cdn.example.com/out.mp4", dest)
            self.assertTrue(out.exists())
            self.assertEqual(out.read_bytes(), b"fake-mp4-bytes")
            self.assertNotIn("headers", get_mock.call_args[1])

    def test_agnes_chat_parses_content(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"choices": [{"message": {"content": '{"directions": []}'}}]}
        with patch("shorts_generator.agnes.requests.post", return_value=mock_resp):
            reply = agnes_chat("test prompt", api_key="agnes-key")
        self.assertEqual(reply, '{"directions": []}')

    def test_submit_video_raises_on_401(self):
        mock_resp = MagicMock(status_code=401, text="Unauthorized")
        mock_resp.json.return_value = {"error": {"message": "Invalid key"}}
        with patch("shorts_generator.agnes.requests.post", return_value=mock_resp):
            with self.assertRaises(AgnesAPIError):
                submit_video("test", api_key="bad-key")

    def test_build_video_prompt_combines_plan(self):
        prompt = build_video_prompt(
            idea="Kopi susu anak kos",
            direction={"summary": "Pagi hari hemat di kos"},
            hook="Cuma modal lima ribu",
            plan={"scenes": [{"visual": "Tuang kopi ke gelas es"}, {"visual": "Aduk perlahan"}]},
        )
        self.assertIn("Kopi susu anak kos", prompt)
        self.assertIn("Tuang kopi ke gelas es", prompt)


class TestAgnesRoutes(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_generate_video_requires_agnes_key(self):
        with patch.object(web_app.cfg, "AGNES_API_KEY", ""):
            resp = self.client.post("/api/ideas/generate-video", json={"prompt": "Video kopi"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("AGNES_API_KEY", resp.get_json()["error"])

    def test_generate_video_validates_duration_and_model(self):
        with patch.object(web_app.cfg, "AGNES_API_KEY", "agnes-test-key"):
            resp_dur = self.client.post("/api/ideas/generate-video", json={"prompt": "Video kopi", "duration": 2})
            self.assertEqual(resp_dur.status_code, 400)
            resp_model = self.client.post("/api/ideas/generate-video", json={"prompt": "Video kopi", "model": "bad-model"})
            self.assertEqual(resp_model.status_code, 400)

    def test_idea_llm_call_falls_back_to_agnes_when_gemini_missing(self):
        with (
            patch.object(web_app.cfg, "LLM_PROVIDER", "gemini"),
            patch.object(web_app.cfg, "GEMINI_API_KEY", ""),
            patch.object(web_app.cfg, "AGNES_API_KEY", "agnes-test-key"),
        ):
            llm_fn, notice = web_app._idea_llm_call()
        self.assertIs(llm_fn, web_app.agnes_chat)
        self.assertIn("Agnes AI", notice)

    def test_generate_video_starts_and_completes_job(self):
        with (
            patch.object(web_app.cfg, "AGNES_API_KEY", "agnes-test-key"),
            patch("web_app.get_active_job", return_value=None),
            patch("web_app.generate_video_to_file") as gen_mock,
            patch("web_app.threading.Thread") as thread_cls,
        ):
            def write_fake_video(*_args, **kwargs):
                dest = kwargs["dest_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b"mp4data")
                return {"video_id": "vid_99", "model": "agnes-video-2.5-flash", "remote_url": "https://cdn/v.mp4", "file_path": str(dest)}

            gen_mock.side_effect = write_fake_video
            captured = {}

            def capture_thread(target=None, args=(), daemon=True):
                captured["target"] = target
                captured["args"] = args
                m = MagicMock()
                return m

            thread_cls.side_effect = capture_thread
            resp = self.client.post(
                "/api/ideas/generate-video",
                json={"prompt": "Kopi susu cinematic", "duration": 6, "aspect_ratio": "9:16", "model": "agnes-video-2.5-flash"},
            )
            self.assertEqual(resp.status_code, 200)
            job_id = resp.get_json()["job_id"]

            # Run worker synchronously for deterministic assertion
            captured["target"](*captured["args"])
            job_resp = self.client.get(f"/api/jobs/{job_id}")
            self.assertEqual(job_resp.status_code, 200)
            job_data = job_resp.get_json()
            self.assertEqual(job_data["status"], "completed")
            shorts = job_data["result"]["shorts"]
            self.assertEqual(len(shorts), 1)
            self.assertTrue(shorts[0]["web_url"].endswith("/short_1.mp4"))

            # Cleanup test session folder
            session_folder = job_data["result"]["session_folder"]
            self.client.delete(f"/api/history/session/{session_folder}")


if __name__ == "__main__":
    unittest.main()
