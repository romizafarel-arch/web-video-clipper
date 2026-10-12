import io
import tempfile
import unittest
from pathlib import Path

import web_app
from shorts_generator.local.clipper import create_ass_subtitle_file
from shorts_generator.local.gaming_presets import build_gaming_filter_complex


class TestFontFamilySystem(unittest.TestCase):
    def setUp(self):
        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    def test_get_fonts_endpoint(self):
        resp = self.client.get("/api/fonts")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("fonts", data)
        fonts = data["fonts"]
        self.assertIsInstance(fonts, list)
        self.assertGreaterEqual(len(fonts), 9)

        font_families = [f["family"] for f in fonts]
        self.assertIn("Anton", font_families)
        self.assertIn("The Bold Font", font_families)
        self.assertIn("Montserrat Black", font_families)
        self.assertIn("Bebas Neue", font_families)
        self.assertIn("Poppins", font_families)
        self.assertIn("Bangers", font_families)
        self.assertIn("Inter", font_families)
        self.assertIn("Oswald", font_families)
        self.assertIn("Roboto", font_families)

    def test_get_font_file_endpoint(self):
        resp = self.client.get("/api/fonts/Anton-Regular.ttf")
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.data), 1000)
        resp.close()

    def test_get_font_file_path_traversal_blocked(self):
        resp = self.client.get("/api/fonts/../web_app.py")
        self.assertIn(resp.status_code, (403, 404))

    def test_upload_font_validation(self):
        # Missing file field
        resp = self.client.post("/api/fonts/upload", data={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("font_file", resp.get_json()["error"])

        # Invalid extension
        data = {
            "font_file": (io.BytesIO(b"fake binary"), "malicious.exe")
        }
        resp = self.client.post("/api/fonts/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("tidak didukung", resp.get_json()["error"])

    def test_create_ass_subtitle_file_custom_font(self):
        segments = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Testing Font Custom",
                "words": [
                    {"word": "Testing", "start": 0.0, "end": 0.8},
                    {"word": "Font", "start": 0.8, "end": 1.4},
                    {"word": "Custom", "start": 1.4, "end": 2.0},
                ],
            }
        ]
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tf:
            out_ass_path = tf.name

        try:
            res = create_ass_subtitle_file(
                segments=segments,
                clip_start=0.0,
                clip_end=2.0,
                out_ass_path=out_ass_path,
                width=1080,
                height=1920,
                subtitle_style="karaoke",
                font_family="The Bold Font",
            )
            self.assertTrue(res)
            self.assertTrue(Path(out_ass_path).exists())
            with open(out_ass_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("The Bold Font", content)
            self.assertIn("[V4+ Styles]", content)
            self.assertIn("Style: Default,The Bold Font", content)
        finally:
            if Path(out_ass_path).exists():
                Path(out_ass_path).unlink()

    def test_gaming_presets_include_fontsdir(self):
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as tf:
            tf.write(b"[Script Info]\n")
            real_ass = tf.name

        try:
            filter_str = build_gaming_filter_complex(
                top_crop=None,
                mid_crop=(0, 0, 1920, 1080),
                bot_crop=(0, 0, 1920, 1080),
                ass_path=real_ass,
            )
            self.assertIn("fontsdir=", filter_str)
            self.assertIn("ass=filename=", filter_str)
        finally:
            if Path(real_ass).exists():
                Path(real_ass).unlink()


if __name__ == "__main__":
    unittest.main()
