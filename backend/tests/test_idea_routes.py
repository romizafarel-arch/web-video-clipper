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


if __name__ == "__main__":
    unittest.main()
