"""Unit and integration tests for Gaming Party Stream Clipper feature."""
import json
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from shorts_generator.audio_peaks import (
    boost_highlights_with_audio_peaks,
    compute_baseline_db,
    scan_audio_energy,
)
from shorts_generator.highlights import (
    GAMING_HIGHLIGHT_SYSTEM_PROMPT,
    GAMING_VIRALITY_CRITERIA,
    call_highlight_api,
    get_highlights,
)
from shorts_generator.local.clipper import (
    crop_clip_local,
    crop_highlights_local,
    validate_facecam_area,
)
from shorts_generator.local.gaming_presets import (
    BOTTOM_HEIGHT,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    GAMEPLAY_2L_HEIGHT,
    GAMING_PRESETS,
    build_gameplay_fallback_filter_complex,
    build_gaming_filter_complex,
    resolve_gaming_crop_boxes,
)


class TestGamingStreamClipper(unittest.TestCase):
    """Test suite verifying gaming party stream layout, filter graph, audio peaks, and viral prompts."""

    def test_01_gaming_presets_and_coordinate_resolution(self):
        """Verifies presets, boundary clamping, and proportional resolution scaling."""
        # 1. Standard 1080p stream resolution
        top, mid, bot = resolve_gaming_crop_boxes("discord_top_cam_bottom_right", 1920, 1080)
        self.assertEqual(len(top), 4)
        self.assertEqual(len(mid), 4)
        self.assertEqual(len(bot), 4)
        # Dimensions must be strictly even
        for box in (top, mid, bot):
            self.assertEqual(box[2] % 2, 0, f"Width {box[2]} must be even")
            self.assertEqual(box[3] % 2, 0, f"Height {box[3]} must be even")
            self.assertGreaterEqual(box[0], 0)
            self.assertGreaterEqual(box[1], 0)
            self.assertLessEqual(box[0] + box[2], 1920)
            self.assertLessEqual(box[1] + box[3], 1080)

        # 2. Scaled 720p stream resolution (1280x720)
        top_720, mid_720, bot_720 = resolve_gaming_crop_boxes("discord_top_cam_bottom_right", 1280, 720)
        self.assertLessEqual(top_720[0] + top_720[2], 1280)
        self.assertLessEqual(top_720[1] + top_720[3], 720)
        self.assertLessEqual(bot_720[0] + bot_720[2], 1280)
        self.assertLessEqual(bot_720[1] + bot_720[3], 720)

        # 3. Discord left cam preset
        top_left, mid_left, bot_left = resolve_gaming_crop_boxes("discord_left_cam_top_right", 1920, 1080)
        self.assertEqual(top_left[0], 0)
        self.assertGreater(bot_left[0], 1000)  # Webcam on the right side

        # 4. Custom bounding box with normalized floats
        custom_spec = {
            "top": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.20},
            "mid": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.80},
            "bottom": {"x": 0.7, "y": 0.6, "w": 0.3, "h": 0.40},
        }
        c_top, c_mid, c_bot = resolve_gaming_crop_boxes("custom", 1920, 1080, custom_box=custom_spec)
        self.assertEqual(c_top[0], 0)
        self.assertEqual(c_top[1], 0)
        self.assertEqual(c_top[2], 1920)
        self.assertLessEqual(c_bot[0] + c_bot[2], 1920)

    def test_02_filter_complex_generation(self):
        """Verifies single-pass FFmpeg filter_complex syntax and 3-layer vstack layout."""
        top = (0, 0, 1920, 260)
        mid = (260, 60, 1400, 960)
        bot = (1420, 680, 500, 400)

        filter_str = build_gaming_filter_complex(top, mid, bot, ass_path=None)
        self.assertIn("[0:v]split=3[raw_top][raw_mid][raw_bot]", filter_str)
        self.assertIn(f"scale={CANVAS_WIDTH}:340:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:340[v_top]", filter_str)
        self.assertIn(f"scale={CANVAS_WIDTH}:1100:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:1100[v_mid]", filter_str)
        self.assertIn(f"scale={CANVAS_WIDTH}:480:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:480[v_bot]", filter_str)
        self.assertIn("[v_top][v_mid][v_bot]vstack=inputs=3[v_stacked]", filter_str)
        self.assertIn("[v_stacked]null[v_out]", filter_str)

        # With ASS subtitle path
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
            f.write(b"[Script Info]\n")
            sub_file = f.name
        try:
            filter_sub = build_gaming_filter_complex(top, mid, bot, ass_path=sub_file)
            self.assertIn("ass=filename=", filter_sub)
            self.assertIn("[v_out]", filter_sub)
        finally:
            if os.path.exists(sub_file):
                os.remove(sub_file)

    def test_03_audio_peak_scanner_and_score_boosting(self):
        """Verifies PCM RMS audio energy windowing and highlight score boosting."""
        sample_audio = Path("scratch/audio_inspection/short02_09s_to_19s.wav")
        if not sample_audio.exists():
            self.skipTest(f"Sample audio {sample_audio} not found")

        series = scan_audio_energy(str(sample_audio), window_seconds=0.5)
        self.assertGreater(len(series), 10)
        ts, db = series[0]
        self.assertEqual(ts, 0.0)
        self.assertTrue(math.isfinite(db))

        baseline = compute_baseline_db(series)
        self.assertLess(baseline, 0.0)

        # Window with known high energy peak around 9.5s..11.0s (measured at ~ -19.5 dB vs baseline -27.9 dB)
        candidates = [
            {"title": "Quiet Part", "start_time": 1.0, "end_time": 3.0, "score": 60},
            {"title": "Chaos Scream", "start_time": 9.5, "end_time": 11.0, "score": 70},
        ]
        boosted = boost_highlights_with_audio_peaks(candidates, series, max_boost=20)
        scream_clip = next(c for c in boosted if c["title"] == "Chaos Scream")
        self.assertGreater(scream_clip["score"], 70)
        self.assertGreater(scream_clip["audio_boost"], 0)
        self.assertIn("audio_peak_db", scream_clip)

    def test_04_gaming_prompts_and_virality_switch(self):
        """Verifies that framing_mode='gaming' triggers gaming prompt and sweet spot rules."""
        recorded_prompts = []

        def mock_llm(prompt: str) -> str:
            recorded_prompts.append(prompt)
            return json.dumps({
                "highlights": [
                    {
                        "title": "Insane Jumpscare Scream",
                        "start_time": 10.0,
                        "end_time": 35.0,
                        "score": 95,
                        "hook_sentence": "NO WAY WHAT WAS THAT?!",
                        "virality_reason": "Ear-splitting hilarious scream during horror game glitch",
                    }
                ]
            })

        sample_transcript = {
            "segments": [
                {"start": 10.0, "end": 20.0, "text": "Bro watch out behind you!"},
                {"start": 20.1, "end": 35.0, "text": "AHHHHHHH NOOOO HAHAHA!"},
            ],
            "duration": 50.0,
        }

        # 1. Normal mode (podcast)
        get_highlights(sample_transcript, num_clips=1, llm_fn=mock_llm, framing_mode="podcast")
        self.assertGreaterEqual(len(recorded_prompts), 2)
        self.assertIn("45-90 seconds", recorded_prompts[-1])

        # 2. Gaming mode
        recorded_prompts.clear()
        res_gaming = get_highlights(sample_transcript, num_clips=1, llm_fn=mock_llm, framing_mode="gaming")
        self.assertGreaterEqual(len(recorded_prompts), 2)
        # Gaming prompt must include 20-60s sweet spot and screams/discord banter signals
        self.assertIn("20-60 seconds", recorded_prompts[-1])
        self.assertIn("SCREAMS & JUMPSCARES", recorded_prompts[-1])
        self.assertIn("ROASTING & DISCORD BANTER", recorded_prompts[-1])
        self.assertEqual(len(res_gaming["highlights"]), 1)
        self.assertEqual(res_gaming["highlights"][0]["title"], "Insane Jumpscare Scream")

    def test_05_gaming_reframe_render_integration(self):
        """Tests end-to-end rendering of a 3-layer gaming stream short."""
        source_video = Path("output/20260928_134842_d631438d/source_NoDG4oewwjg_720p.mp4")
        if not source_video.exists():
            self.skipTest(f"Test video {source_video} not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "test_gaming_short.mp4")
            crop_clip_local(
                source_path=str(source_video),
                start_time=0.0,
                end_time=3.0,
                aspect_ratio="9:16",
                out_path=out_file,
                segments=[
                    {"start": 0.2, "end": 2.5, "text": "LET'S GO CLUTCH THIS ROUND!", "words": [
                        {"word": "LET'S", "start": 0.2, "end": 0.7},
                        {"word": "GO", "start": 0.8, "end": 1.2},
                        {"word": "CLUTCH", "start": 1.3, "end": 2.0},
                        {"word": "THIS!", "start": 2.1, "end": 2.5},
                    ]}
                ],
                burn_subtitles=True,
                framing_mode="gaming",
                gaming_preset="discord_top_cam_bottom_right",
            )

            self.assertTrue(os.path.exists(out_file), "Rendered gaming short must exist")

            # Probe output video resolution: strictly 1080x1920
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name",
                "-of", "csv=p=0",
                out_file,
            ]
            res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            parts = res.stdout.strip().split(",")
            codec, width, height = parts[0], int(parts[1]), int(parts[2])
            self.assertEqual(codec, "h264")
            self.assertEqual(width, CANVAS_WIDTH)
            self.assertEqual(height, CANVAS_HEIGHT)

    def test_06_web_app_gaming_endpoints(self):
        """Verifies web_app endpoints correctly accept and store gaming framing parameters."""
        from web_app import app
        client = app.test_client()

        # Test generate validation with gaming mode and custom preset
        resp = client.post("/api/generate", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "framing_mode": "gaming",
            "gaming_preset": "discord_left_cam_top_right",
            "gaming_custom_box": {
                "top": {"x": 0, "y": 0, "w": 500, "h": 200},
                "mid": {"x": 200, "y": 50, "w": 1400, "h": 900},
                "bottom": {"x": 1400, "y": 0, "w": 500, "h": 350},
            },
        })
        # If job admitted or already active (409), parameters are accepted
        self.assertIn(resp.status_code, (200, 409))
        if resp.status_code == 200:
            data = resp.get_json()
            job_id = data["job_id"]
            from shorts_generator.job_manager import job_manager
            ctx = job_manager.get_job(job_id)
            self.assertIsNotNone(ctx)
            self.assertEqual(ctx.params["framing_mode"], "gaming")
            self.assertEqual(ctx.params["gaming_preset"], "discord_left_cam_top_right")
            self.assertIsNotNone(ctx.params["gaming_custom_box"])
            job_manager.request_cancel(job_id)
            if hasattr(job_manager, "_jobs"):
                job_manager._jobs.pop(job_id, None)
            from web_app import jobs
            jobs.pop(job_id, None)

    def test_07_clean_2layer_preset_and_filter_complex(self):
        """Verifies clean 2-layer gaming layout: Facecam Atas (480p) + Gameplay Bawah (1440p) (Windah style) default, and classic cam_bottom."""
        top, mid, bot = resolve_gaming_crop_boxes("clean_2layer", 1920, 1080)
        self.assertIsNone(top, "2-layer layout must omit top strip")
        self.assertEqual(len(mid), 4)
        self.assertEqual(len(bot), 4)

        # 1. Default layout: Facecam Atas + Gameplay Bawah (Windah Basudara style)
        filter_str = build_gaming_filter_complex(None, mid, bot, ass_path=None)
        self.assertIn("[0:v]split=2[raw_mid][raw_bot]", filter_str)
        self.assertIn(f"scale={CANVAS_WIDTH}:{GAMEPLAY_2L_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{GAMEPLAY_2L_HEIGHT}[v_mid]", filter_str)
        self.assertIn(f"scale={CANVAS_WIDTH}:{BOTTOM_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{BOTTOM_HEIGHT}[v_bot]", filter_str)
        self.assertIn("[v_bot][v_mid]vstack=inputs=2[v_stacked]", filter_str)
        self.assertIn("[v_stacked]null[v_out]", filter_str)

        # 2. Classic layout: Gameplay Atas + Facecam Bawah (cam_bottom)
        filter_str_bot = build_gaming_filter_complex(None, mid, bot, ass_path=None, layout="cam_bottom")
        self.assertIn("[v_mid][v_bot]vstack=inputs=2[v_stacked]", filter_str_bot)

    def test_08_gameplay_fallback_filter_complex(self):
        """Verifies Full Gameplay 9:16 Center Crop fallback filter complex."""
        fallback_filter = build_gameplay_fallback_filter_complex(1920, 1080, ass_path=None)
        self.assertIn("scale=1080:1920[v_gameplay]", fallback_filter)
        self.assertIn("[v_gameplay]null[v_out]", fallback_filter)

        # With ASS subtitles
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
            f.write(b"[Script Info]\n")
            sub_file = f.name
        try:
            filter_sub = build_gameplay_fallback_filter_complex(1920, 1080, ass_path=sub_file)
            self.assertIn("ass=filename=", filter_sub)
            self.assertIn("[v_out]", filter_sub)
        finally:
            if os.path.exists(sub_file):
                os.remove(sub_file)

    def test_09_smart_face_validation(self):
        """Verifies OpenCV Haar Cascade facecam validation behavior (detects face vs detects no face)."""
        source_video = Path("output/20260928_134842_d631438d/source_NoDG4oewwjg_720p.mp4")
        if not source_video.exists():
            self.skipTest(f"Test video {source_video} not found")

        # 1. Area where person's face actually is (around center-top [550, 70, 200, 200] in 720p video)
        has_face_roi = (550, 70, 200, 200)
        self.assertTrue(validate_facecam_area(str(source_video), has_face_roi))

        # 2. Area with empty background / corner (no face [1000, 500, 200, 200])
        no_face_roi = (1000, 500, 200, 200)
        self.assertFalse(validate_facecam_area(str(source_video), no_face_roi))


if __name__ == "__main__":
    unittest.main()

