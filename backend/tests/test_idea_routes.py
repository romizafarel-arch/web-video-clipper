import json
import unittest
from unittest.mock import patch

import web_app
from web_app import app


class TestIdeaRoutes(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_directions_endpoint_returns_three_directions(self):
        response_body = {"directions": [
            {"title": str(index), "summary": "Inti", "hook": "Pembuka", "why": "Alasan"}
            for index in range(3)
        ]}
        with patch("web_app._idea_llm_call", return_value=(lambda _prompt: json.dumps(response_body), None)):
            response = self.client.post("/api/ideas/directions", json={"idea": "Kopi", "goal": "promosi", "tone": "santai", "duration": 30})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["directions"]), 3)

    def test_plan_endpoint_requires_selected_direction(self):
        response = self.client.post("/api/ideas/plan", json={"idea": "Kopi", "goal": "informasi", "tone": "santai", "duration": 30})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Pilih salah satu", response.get_json()["error"])

    def test_plan_endpoint_returns_scene_guide(self):
        response_body = {
            "hooks": ["Pembuka 1", "Pembuka 2", "Pembuka 3"],
            "scenes": [
                {"visual": f"Gambar {index}", "spoken": f"Ucapan {index}", "onscreen": f"Teks {index}"}
                for index in range(3)
            ],
            "closing": "Penutup",
            "editing_note": "Catatan",
        }
        payload = {
            "idea": "Kopi",
            "goal": "informasi",
            "tone": "santai",
            "duration": 30,
            "direction": {"title": "Arah", "summary": "Inti", "hook": "Pembuka", "why": "Alasan"},
        }
        with patch("web_app._idea_llm_call", return_value=(lambda _prompt: json.dumps(response_body), None)):
            response = self.client.post("/api/ideas/plan", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["scenes"]), 3)

    def test_missing_ai_key_has_actionable_status(self):
        with patch("web_app._idea_llm_call", side_effect=RuntimeError("GEMINI_API_KEY is not set")):
            response = self.client.post("/api/ideas/directions", json={"idea": "Kopi"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Pengaturan", response.get_json()["error"])

    def test_unavailable_openai_model_uses_available_model_for_idea_only(self):
        with (
            patch.object(web_app.cfg, "LLM_PROVIDER", "openai"),
            patch.object(web_app.cfg, "OPENAI_MODEL", "old-model"),
            patch("web_app.get_openai_models", return_value={"success": True, "models": [{"id": "hy4-free"}]}),
            patch("web_app.call_openai_llm", return_value="ok") as call,
        ):
            llm_call, notice = web_app._idea_llm_call()
            self.assertEqual(llm_call("prompt"), "ok")
            call.assert_called_once_with("prompt", model="hy4-free")
            self.assertIn("hy4-free", notice)
            self.assertEqual(web_app.cfg.OPENAI_MODEL, "old-model")

    def test_directions_endpoint_passes_llm_provider_and_model_override(self):
        response_body = {"directions": [
            {"title": str(index), "summary": "Inti", "hook": "Pembuka", "why": "Alasan"}
            for index in range(3)
        ]}
        with patch("web_app._idea_llm_call", return_value=(lambda _prompt: json.dumps(response_body), None)) as mock_llm:
            response = self.client.post(
                "/api/ideas/directions",
                json={
                    "idea": "Kopi",
                    "goal": "promosi",
                    "tone": "santai",
                    "duration": 30,
                    "llm_provider": "agnes",
                    "llm_model": "agnes-3.0-flash",
                },
            )
        self.assertEqual(response.status_code, 200)
        mock_llm.assert_called_once_with("agnes", "agnes-3.0-flash")

    def test_models_endpoint_supports_agnes_provider(self):
        fake_agnes = {
            "success": True,
            "provider": "agnes",
            "models": [{"id": "agnes-2.5-flash", "name": "agnes-2.5-flash"}],
            "video_models": [{"id": "agnes-video-2.5-flash", "name": "agnes-video-2.5-flash"}],
            "raw_count": 2,
        }
        with patch("web_app.get_agnes_models", return_value=fake_agnes):
            response = self.client.get("/api/models?provider=agnes")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["provider"], "agnes")
        self.assertEqual(body["models"][0]["id"], "agnes-2.5-flash")
        self.assertEqual(body["video_models"][0]["id"], "agnes-video-2.5-flash")

    def test_models_endpoint_supports_muapi_provider(self):
        fake_muapi = {
            "success": True,
            "provider": "muapi",
            "models": [{"id": "veo3.1-fast-text-to-video", "name": "veo3.1-fast-text-to-video ($0.60)"}],
            "video_models": [{"id": "veo3.1-fast-text-to-video", "name": "veo3.1-fast-text-to-video ($0.60)"}],
            "raw_count": 1,
        }
        with patch("web_app.get_muapi_video_models", return_value=fake_muapi):
            response = self.client.get("/api/models?provider=muapi")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["provider"], "muapi")
        self.assertEqual(body["video_models"][0]["id"], "veo3.1-fast-text-to-video")

    def test_generate_video_accepts_muapi_provider(self):
        fake_muapi = {
            "success": True,
            "video_models": [{
                "id": "veo3.1-fast-text-to-video",
                "endpoint_url": "veo3.1-fast-text-to-video",
                "input_fields": ["prompt", "aspect_ratio", "duration", "resolution"],
            }],
        }
        fake_schema = {
            "endpoint_url": "veo3.1-fast-text-to-video",
            "input_fields": ["prompt", "aspect_ratio", "duration", "resolution"],
            "aspect_ratio": {"enum": ["16:9", "9:16"], "default": "16:9"},
            "duration": {"enum": [8], "default": 8},
            "resolution": {"enum": ["720p", "1080p"], "default": "720p"},
        }
        with (
            patch.object(web_app.cfg, "MUAPI_API_KEY", "muapi-test-key"),
            patch("web_app.get_muapi_video_models", return_value=fake_muapi),
            patch("web_app.get_muapi_model_schema", return_value=fake_schema),
            patch("web_app.get_active_job", return_value=None),
            patch.object(web_app.job_manager, "get_active_job", return_value=None),
            patch("web_app.threading.Thread") as thread_cls,
        ):
            resp = self.client.post(
                "/api/ideas/generate-video",
                json={
                    "provider": "muapi",
                    "prompt": "Kopi susu hangat pagi hari",
                    "model": "veo3.1-fast-text-to-video",
                    "aspect_ratio": "9:16",
                    "duration": 8,
                    "resolution": "720p",
                },
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["status"], "started")
        thread_cls.assert_called_once()
        job_id = body["job_id"]
        job_ctx = web_app.job_manager.get_job(job_id)
        try:
            self.assertIsNotNone(job_ctx)
            self.assertEqual(job_ctx.url, "muapi://veo3.1-fast-text-to-video")
            self.assertEqual(job_ctx.params["payload_options"], {
                "aspect_ratio": "9:16",
                "duration": 8,
                "resolution": "720p",
            })
        finally:
            if job_ctx and job_ctx.session_folder:
                self.client.delete(f"/api/history/session/{job_ctx.session_folder}")
            web_app.job_manager._jobs.pop(job_id, None)
            web_app.jobs.pop(job_id, None)

    def test_generate_video_returns_409_on_job_conflict(self):
        with (
            patch.object(web_app.cfg, "AGNES_API_KEY", "agnes-test-key"),
            patch("web_app.get_active_job", return_value=None),
            patch.object(web_app.job_manager, "admit_job", side_effect=web_app.JobConflictError("Sudah ada job aktif")),
        ):
            resp = self.client.post(
                "/api/ideas/generate-video",
                json={
                    "provider": "agnes",
                    "prompt": "Kopi susu hangat pagi hari",
                    "model": "agnes-video-2.5-flash",
                    "aspect_ratio": "9:16",
                    "duration": 6,
                    "size": "720P",
                },
            )
        self.assertEqual(resp.status_code, 409)
        self.assertIn("job aktif", resp.get_json()["error"].lower())


if __name__ == "__main__":
    unittest.main()
