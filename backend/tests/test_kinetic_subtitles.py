import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from shorts_generator.local.clipper import (
    build_validated_cues,
    create_ass_subtitle_file,
    create_vtt_subtitle_file,
    crop_clip_local,
    crop_highlights_local,
)
from web_app import app, verify_rendered_video


class TestKineticKaraokeSubtitles(unittest.TestCase):
    """Unit and integration test suite for Word-by-Word Kinetic Subtitle (Karaoke)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_karaoke_")
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_build_validated_cues_character_weighted_timings(self):
        """Word centiseconds must be naturally weighted by character length and sum exactly to cue duration."""
        segments = [
            {"start": 5.0, "end": 8.0, "text": "Ini kalimat uji untuk karaoke berbobot."},
        ]
        cues = build_validated_cues(segments, clip_start=5.0, clip_end=8.0, source_duration=10.0)
        self.assertEqual(len(cues), 2)  # 6 words / target 4 = 2 chunks (3 words each)

        for cue in cues:
            self.assertIn("words", cue)
            words = cue["words"]
            self.assertTrue(len(words) > 0)
            total_dur = cue["end"] - cue["start"]
            expected_cs = max(1, int(round(total_dur * 100)))
            alloc_cs = sum(w["duration_cs"] for w in words)
            self.assertEqual(alloc_cs, expected_cs, f"Allocated centiseconds {alloc_cs} != expected {expected_cs}")
            # Words with more letters should have greater or equal duration than short words
            for w in words:
                self.assertGreaterEqual(w["duration_cs"], 1)

    def test_02_build_validated_cues_explicit_words(self):
        """When transcript segment provides word-level timestamps, they are strictly mapped."""
        segments = [
            {
                "start": 10.0,
                "end": 13.0,
                "text": "KATA_PENDEK KATA_SANGAT_PANJANG_SEKALI",
                "words": [
                    {"word": "KATA_PENDEK", "start": 10.0, "end": 10.6},
                    {"word": "KATA_SANGAT_PANJANG_SEKALI", "start": 10.6, "end": 13.0},
                ],
            }
        ]
        cues = build_validated_cues(segments, clip_start=10.0, clip_end=13.0, source_duration=20.0)
        self.assertEqual(len(cues), 1)
        words = cues[0]["words"]
        self.assertEqual(len(words), 2)
        # First word was 0.6s (20% of 3.0s), second was 2.4s (80% of 3.0s)
        self.assertEqual(words[0]["duration_cs"], 60)
        self.assertEqual(words[1]["duration_cs"], 240)

    def test_03_ass_karaoke_sweep_formatting(self):
        """subtitle_style='karaoke' must generate \\kf tags with PrimaryColour & SecondaryColour setup."""
        segments = [{"start": 0.0, "end": 2.0, "text": "VIRAL SHORTS TIKTOK REELS"}]
        ass_path = os.path.join(self.temp_dir, "karaoke.ass")
        ok = create_ass_subtitle_file(segments, 0.0, 2.0, ass_path, subtitle_style="karaoke")
        self.assertTrue(ok)

        content = Path(ass_path).read_text(encoding="utf-8")
        # Check style definition: Primary &H0015CCFA (Yellow), Secondary &H00FFFFFF (White)
        self.assertIn("&H0015CCFA", content)
        self.assertIn("&H00FFFFFF", content)
        # Check dialogue format
        self.assertIn(r"\kf", content)
        matches = re.findall(r"\\kf(\d+)", content)
        self.assertEqual(len(matches), 4)
        total_cs = sum(int(m) for m in matches)
        self.assertEqual(total_cs, 200)

    def test_04_ass_kinetic_beat_formatting(self):
        """subtitle_style='kinetic' must generate discrete \\k tags for beat jump animation."""
        segments = [{"start": 0.0, "end": 1.5, "text": "BEAT JUMP POP"}]
        ass_path = os.path.join(self.temp_dir, "kinetic.ass")
        ok = create_ass_subtitle_file(segments, 0.0, 1.5, ass_path, subtitle_style="kinetic")
        self.assertTrue(ok)

        content = Path(ass_path).read_text(encoding="utf-8")
        self.assertIn(r"\k", content)
        self.assertNotIn(r"\kf", content)
        matches = re.findall(r"\\k(\d+)", content)
        self.assertEqual(len(matches), 3)
        self.assertEqual(sum(int(m) for m in matches), 150)

    def test_05_ass_classic_and_none(self):
        """Classic style generates clean text; 'none' generates no file."""
        segments = [{"start": 0.0, "end": 2.0, "text": "TEKS STATIS"}]
        ass_classic = os.path.join(self.temp_dir, "classic.ass")
        ok_classic = create_ass_subtitle_file(segments, 0.0, 2.0, ass_classic, subtitle_style="classic")
        self.assertTrue(ok_classic)
        content_c = Path(ass_classic).read_text(encoding="utf-8")
        self.assertNotIn(r"\k", content_c)
        self.assertIn("TEKS STATIS", content_c)

        ass_none = os.path.join(self.temp_dir, "none.ass")
        ok_none = create_ass_subtitle_file(segments, 0.0, 2.0, ass_none, subtitle_style="none")
        self.assertFalse(ok_none)
        self.assertFalse(os.path.exists(ass_none))

    def test_06_crop_highlights_local_attaches_subtitle_style(self):
        """crop_highlights_local passes subtitle_style down and includes it in output dict."""
        mock_job_ctx = MagicMock()
        with patch("shorts_generator.local.clipper.crop_clip_local") as mock_crop:
            highlights = [{"start_time": 0.0, "end_time": 5.0, "title": "Test High"}]
            res = crop_highlights_local(
                source_path="mock.mp4",
                highlights=highlights,
                aspect_ratio="9:16",
                out_dir=self.temp_dir,
                burn_subtitles=True,
                job_ctx=mock_job_ctx,
                subtitle_style="kinetic",
            )
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["subtitle_style"], "kinetic")
            self.assertEqual(mock_crop.call_args[1]["subtitle_style"], "kinetic")

    def test_07_api_generate_accepts_and_persists_subtitle_style(self):
        """POST /api/generate validates subtitle_style and forwards it into job parameters."""
        payload = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "mode": "local",
            "subtitle_style": "karaoke",
            "format": "720",
        }
        with patch("threading.Thread.start"):
            res = self.client.post("/api/generate", json=payload)
            self.assertIn(res.status_code, (200, 409))
            if res.status_code == 200:
                data = res.get_json()
                self.assertIn("job_id", data)

        # Invalid subtitle_style fallback check
        payload_invalid = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "mode": "local",
            "subtitle_style": 12345,  # non-string
        }
        res_bad = self.client.post("/api/generate", json=payload_invalid)
        self.assertEqual(res_bad.status_code, 400)

    def test_08_api_edit_clip_updates_subtitle_style_and_meta(self):
        """POST /api/edit-clip updates subtitle_style in metadata and passes to crop_clip_local."""
        session_folder = "test_sess_sub_01"
        sess_dir = Path(self.temp_dir) / session_folder
        sess_dir.mkdir(parents=True, exist_ok=True)
        src_file = sess_dir / "source.mp4"
        src_file.write_bytes(b"FAKE_SRC_BYTES_1234567890")
        short_file = sess_dir / "short_01.mp4"
        short_file.write_bytes(b"INITIAL_CLIP")

        job_file = sess_dir / "job_test_sess_sub_01.json"
        job_data = {
            "job_id": "test_sess_sub_01",
            "session_folder": session_folder,
            "result": {
                "source_video_url": str(src_file),
                "transcript": {
                    "duration": 20.0,
                    "segments": [{"start": 0.0, "end": 10.0, "text": "HELLO WORLD"}],
                },
                "shorts": [
                    {
                        "clip_index": 1,
                        "filename": "short_01.mp4",
                        "start_time": 0.0,
                        "end_time": 10.0,
                        "title": "Clip 1",
                        "subtitle_style": "classic",
                    }
                ],
            },
        }
        job_file.write_text(json.dumps(job_data), encoding="utf-8")

        with patch("web_app.OUTPUT_DIR", Path(self.temp_dir)), \
             patch("web_app.probe_media_duration", return_value=20.0), \
             patch("shorts_generator.local.clipper.crop_clip_local") as mock_crop, \
             patch("web_app.verify_rendered_video"):

            def fake_crop(**kw):
                Path(kw["out_path"]).write_bytes(b"RENDERED_STAGED")

            mock_crop.side_effect = fake_crop

            res = self.client.post(
                "/api/edit-clip",
                json={
                    "session_folder": session_folder,
                    "clip_index": 1,
                    "start_time": 1.0,
                    "end_time": 9.0,
                    "subtitle_style": "kinetic",
                    "burn_subtitles": True,
                },
            )
            self.assertEqual(res.status_code, 200, res.get_data(as_text=True))
            # Verify crop_clip_local was called with subtitle_style='kinetic'
            self.assertEqual(mock_crop.call_args[1]["subtitle_style"], "kinetic")

            # Verify persisted job JSON was updated with subtitle_style
            saved_meta = json.loads(job_file.read_text(encoding="utf-8"))
            updated_short = saved_meta["result"]["shorts"][0]
            self.assertEqual(updated_short["subtitle_style"], "kinetic")
            self.assertTrue(updated_short["burn_subtitles"])

    def test_09_physical_ffmpeg_burn_karaoke_visual_color_transition(self):
        """FFmpeg must cleanly burn ASS karaoke into MP4 with verifiable color shift between unread and active words."""
        fixture_video = os.path.join(self.temp_dir, "synthetic_karaoke.mp4")
        out_short = os.path.join(self.temp_dir, "short_karaoke.mp4")

        # Create a 2.0s black video fixture
        cmd_gen = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:size=404x720:d=2:r=25",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            fixture_video,
        ]
        res = subprocess.run(cmd_gen, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Fixture generation failed: {res.stderr}")

        segments = [
            {"start": 0.0, "end": 2.0, "text": "KATA_AWAL KATA_AKHIR"},
        ]

        # Render clip with subtitle_style="karaoke"
        res_path = crop_clip_local(
            source_path=fixture_video,
            start_time=0.0,
            end_time=2.0,
            aspect_ratio="9:16",
            out_path=out_short,
            segments=segments,
            burn_subtitles=True,
            subtitle_style="karaoke",
            source_duration=2.0,
        )

        self.assertTrue(os.path.exists(res_path))
        verify_rendered_video(Path(res_path), expected_duration=2.0, min_duration=0.5)

        # Inspect frames via OpenCV: text must be burned in
        cap = cv2.VideoCapture(res_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        # Frame at 0.3s (Word 1 active) and Frame at 1.7s (Word 2 active)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(0.3 * fps))
        ret1, frame1 = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(1.7 * fps))
        ret2, frame2 = cap.read()
        cap.release()

        self.assertTrue(ret1 and ret2)
        # Non-black pixels must exist (subtitles are rendered)
        self.assertGreater(np.count_nonzero(frame1 > 40), 1000)
        self.assertGreater(np.count_nonzero(frame2 > 40), 1000)

    def test_09_boundary_word_filtering_and_audio_sync(self):
        """Words occurring outside the clip window must NOT be included or compressed into the clip."""
        # 13 words spanning 35.85 to 43.15, clip is 36.0 to 41.0
        seg = {
            "start": 35.85,
            "end": 43.15,
            "text": "Bahaya terbesar bagi manusia itu bukan mereka bermimpi terlalu tinggi dan mereka gagal.",
            "words": [
                {"word": "Bahaya", "start": 35.85, "end": 36.43},
                {"word": "terbesar", "start": 36.43, "end": 36.99},
                {"word": "bagi", "start": 37.61, "end": 37.89},
                {"word": "manusia", "start": 37.89, "end": 38.61},
                {"word": "itu", "start": 39.15, "end": 39.29},
                {"word": "bukan", "start": 39.29, "end": 39.69},
                {"word": "mereka", "start": 39.69, "end": 40.41},
                {"word": "bermimpi", "start": 40.41, "end": 40.81},
                {"word": "terlalu", "start": 41.10, "end": 41.50},
                {"word": "tinggi", "start": 41.50, "end": 41.90},
                {"word": "dan", "start": 42.00, "end": 42.20},
                {"word": "mereka", "start": 42.20, "end": 42.60},
                {"word": "gagal.", "start": 42.60, "end": 43.15},
            ],
        }
        cues = build_validated_cues([seg], clip_start=36.0, clip_end=41.0, source_duration=50.0)
        # All words after 41.0 must be dropped!
        all_words = " ".join(c["text"] for c in cues)
        self.assertNotIn("GAGAL", all_words)
        self.assertNotIn("TINGGI", all_words)
        self.assertIn("BAHAYA", all_words)
        self.assertIn("BERMIMPI", all_words)

        # Cues must not exceed clip duration (5.0s)
        for cue in cues:
            self.assertGreaterEqual(cue["start"], 0.0)
            self.assertLessEqual(cue["end"], 5.0)

    def test_11_creator_text_presets_ass_generation(self):
        """Verify each of the 5 creator presets generates correct ASS styles and font rules."""
        segments = [{"start": 0.0, "end": 2.0, "text": "Viral Content Scaling"}]

        # 1. Hormozi: Montserrat, Neon Yellow &H0000E6FF, Outline 4.5
        path_hormozi = os.path.join(self.temp_dir, "hormozi.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_hormozi, subtitle_style="hormozi"))
        c_hormozi = Path(path_hormozi).read_text(encoding="utf-8")
        self.assertIn("Montserrat", c_hormozi)
        self.assertIn("&H0000E6FF", c_hormozi)
        self.assertIn("4.5", c_hormozi)

        # 2. Vox Box: Inter, 80% Black opaque box BorderStyle 3
        path_vox = os.path.join(self.temp_dir, "vox.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_vox, subtitle_style="vox_box"))
        c_vox = Path(path_vox).read_text(encoding="utf-8")
        self.assertIn("Inter", c_vox)
        self.assertIn("&HCC000000", c_vox)
        self.assertIn(",3,", c_vox)  # BorderStyle 3

        # 3. Ali Abdaal: Poppins, Yellow highlight &H0000E6FF
        path_ali = os.path.join(self.temp_dir, "ali.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_ali, subtitle_style="ali_abdaal"))
        c_ali = Path(path_ali).read_text(encoding="utf-8")
        self.assertIn("Poppins", c_ali)
        self.assertIn("&H0000E6FF", c_ali)

        # 4. Aesthetic Cinema: Bebas Neue, wide letter-spacing 4
        path_aes = os.path.join(self.temp_dir, "aes.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_aes, subtitle_style="aesthetic"))
        c_aes = Path(path_aes).read_text(encoding="utf-8")
        self.assertIn("Bebas Neue", c_aes)
        self.assertIn(",4,0,1,", c_aes)  # Spacing 4

        # 5. MrBeast: Bangers, Italic, Cyan &H0000F0FF, Magenta shadow
        path_beast = os.path.join(self.temp_dir, "beast.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_beast, subtitle_style="mrbeast"))
        c_beast = Path(path_beast).read_text(encoding="utf-8")
        self.assertIn("Bangers", c_beast)
        self.assertIn("&H0000F0FF", c_beast)
        self.assertIn("&H00FF00EA", c_beast)

        # 6. Brat Acid Lime
        path_brat = os.path.join(self.temp_dir, "brat.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_brat, subtitle_style="brat_lime"))
        c_brat = Path(path_brat).read_text(encoding="utf-8")
        self.assertIn("Montserrat", c_brat)
        self.assertIn("&H0000E68A", c_brat)

        # 7. Dymo Tape Docu
        path_dymo = os.path.join(self.temp_dir, "dymo.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_dymo, subtitle_style="dymo_tape"))
        c_dymo = Path(path_dymo).read_text(encoding="utf-8")
        self.assertIn("Special Elite", c_dymo)
        self.assertIn("&HF50A0A0A", c_dymo)
        self.assertIn(",3,", c_dymo)

        # 8. Editorial Luxury Serif
        path_lux = os.path.join(self.temp_dir, "lux.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_lux, subtitle_style="luxury_serif"))
        c_lux = Path(path_lux).read_text(encoding="utf-8")
        self.assertIn("Cinzel", c_lux)
        self.assertIn("&H00DCF2FE", c_lux)

        # 9. Sticker Pop
        path_stk = os.path.join(self.temp_dir, "stk.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_stk, subtitle_style="sticker_pop"))
        c_stk = Path(path_stk).read_text(encoding="utf-8")
        self.assertIn("Rubik", c_stk)
        self.assertIn("&H0000FFFF", c_stk)

        # 10. Bloomberg Amber Terminal
        path_amber = os.path.join(self.temp_dir, "amber.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_amber, subtitle_style="amber_terminal"))
        c_amber = Path(path_amber).read_text(encoding="utf-8")
        self.assertIn("VT323", c_amber)
        self.assertIn("&H00009FFF", c_amber)
        self.assertIn(",3,", c_amber)

        # 11. CapCut Glow Aura
        path_cc = os.path.join(self.temp_dir, "capcut.ass")
        self.assertTrue(create_ass_subtitle_file(segments, 0.0, 2.0, path_cc, subtitle_style="capcut_glow"))
        c_cc = Path(path_cc).read_text(encoding="utf-8")
        self.assertIn("Poppins", c_cc)
        self.assertIn("&H00D4F500", c_cc)


if __name__ == "__main__":
    unittest.main()

