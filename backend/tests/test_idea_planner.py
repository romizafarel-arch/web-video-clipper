import json
import unittest

from shorts_generator.idea_planner import generate_directions, generate_plan


class TestIdeaPlanner(unittest.TestCase):
    def test_directions_return_three_distinct_fields(self):
        response = {
            "directions": [
                {"title": str(index), "summary": "Inti cerita", "hook": "Pembuka", "why": "Alasan"}
                for index in range(3)
            ]
        }
        prompts = []

        def llm(prompt):
            prompts.append(prompt)
            return json.dumps(response)

        result = generate_directions(llm, "Kopi untuk anak kos", "promosi", "santai", 30)
        self.assertEqual(len(result["directions"]), 3)
        self.assertIn("Kopi untuk anak kos", prompts[0])

    def test_plan_rejects_incomplete_scene_output(self):
        response = {
            "hooks": ["Satu", "Dua", "Tiga"],
            "scenes": [{"visual": "Meja", "spoken": "Pagi", "onscreen": "Pagi"}],
            "closing": "Selesai",
            "editing_note": "Potong cepat",
        }
        with self.assertRaisesRegex(ValueError, "adegan"):
            generate_plan(lambda _prompt: json.dumps(response), "Ide", "informasi", "santai", 30, {
                "title": "Arah", "summary": "Inti", "hook": "Pembuka", "why": "Alasan"
            })

    def test_plan_parses_json_code_fence(self):
        response = {
            "hooks": ["Satu", "Dua", "Tiga"],
            "scenes": [
                {"visual": f"Gambar {index}", "spoken": f"Ucapan {index}", "onscreen": f"Teks {index}"}
                for index in range(3)
            ],
            "closing": "Mulai sekarang",
            "editing_note": "Beri jeda setelah pembuka",
        }
        result = generate_plan(lambda _prompt: f"```json\n{json.dumps(response)}\n```", "Ide", "informasi", "santai", 30, {
            "title": "Arah", "summary": "Inti", "hook": "Pembuka", "why": "Alasan"
        })
        self.assertEqual(len(result["scenes"]), 3)
        self.assertEqual(result["closing"], "Mulai sekarang")

    def test_plan_fills_optional_text_from_spoken_line(self):
        response = {
            "hooks": ["Satu", "Dua", "Tiga"],
            "scenes": [
                {"visual": f"Gambar {index}", "spoken": f"Ucapan {index}", "onscreen": "" if index == 0 else f"Teks {index}"}
                for index in range(3)
            ],
        }
        result = generate_plan(lambda _prompt: json.dumps(response), "Ide", "informasi", "santai", 30, {
            "title": "Arah", "summary": "Inti", "hook": "Pembuka", "why": "Alasan"
        })
        self.assertEqual(result["scenes"][0]["onscreen"], "Ucapan 0")
        self.assertEqual(result["closing"], "Ucapan 2")
        self.assertTrue(result["editing_note"])


if __name__ == "__main__":
    unittest.main()
