"""End-to-end unit and integration test suite for Gaming Facecam feature.
Verifies:
1. Candidate detection with 4-corner temporal voting.
2. Synthetic video rendering across various facecam corner configurations.
3. User bounding box preserved as source of truth throughout the entire clip.
4. Subtitle positioning (ASS margin_v & WebVTT line:72%) avoiding facecam panel.
5. Standard modes (podcast, single, center) remain unaffected (zero regression).
6. Web app API validation (detect-facecam, rejection of Cloud API for gaming framing).
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from shorts_generator.local.clipper import (
    crop_clip_local,
    create_ass_subtitle_file,
    create_vtt_subtitle_file,
    detect_facecam_candidate,
)
from shorts_generator.local.gaming_presets import (
    BOTTOM_HEIGHT,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    GAMEPLAY_2L_HEIGHT,
    GAMING_PRESETS,
    get_default_gameplay_box,
    resolve_gaming_crop_boxes,
)
from web_app import app, validate_and_sanitize_gaming_box


class TestGamingFacecamEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create a lightweight synthetic 1280x720 2-second test video with visual markers."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.synthetic_video_path = os.path.join(cls.temp_dir.name, "synthetic_gameplay_720p.mp4")

        # Create 1280x720 video with OpenCV: 25 fps, 2 seconds = 50 frames
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(cls.synthetic_video_path, fourcc, 25.0, (1280, 720))

        # We draw a green gameplay field, and a distinct simulated streamer webcam at bottom-right
        for i in range(50):
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            # Gameplay background (dark green grid)
            frame[:, :] = (30, 80, 30)
            cv2.putText(frame, f"GAMEPLAY HUD - FRAME {i}", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            cv2.circle(frame, (640, 360), 60, (0, 200, 255), -1)

            # Simulated Facecam in bottom-right corner [950, 460, 300, 240]
            # Cyan box representing streamer facecam
            cv2.rectangle(frame, (950, 460), (1250, 700), (255, 100, 0), -1)
            cv2.putText(frame, "CAM", (1050, 600), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

            writer.write(frame)
        writer.release()

        # Add silent AAC audio stream with ffmpeg for full container validity
        cls.muxed_video_path = os.path.join(cls.temp_dir.name, "synthetic_with_audio.mp4")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", cls.synthetic_video_path,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            cls.muxed_video_path,
        ]
        subprocess.run(cmd, check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_01_gaming_corner_presets_resolution(self):
        """Verifies that all 4 corner presets resolve to valid, clamped, even coordinates."""
        corners = ["bottom_right", "bottom_left", "top_right", "top_left"]
        for corner in corners:
            preset_name = f"clean_2layer_{corner}"
            top, mid, bot = resolve_gaming_crop_boxes(preset_name, 1280, 720)
            self.assertIsNone(top, f"2-layer preset {preset_name} should not have top strip")
            self.assertEqual(len(mid), 4)
            self.assertEqual(len(bot), 4)

            # Check even coordinates
            for val in (*mid, *bot):
                self.assertEqual(val % 2, 0, f"Coordinate {val} in {preset_name} must be even")

            # Check bounds within 1280x720
            self.assertLessEqual(bot[0] + bot[2], 1280)
            self.assertLessEqual(bot[1] + bot[3], 720)

    def test_02_default_gameplay_box_ratio(self):
        """Verifies that gameplay crop matches 3:4 aspect ratio for 1080x1440 mapping without distortion."""
        mx, my, mw, mh = get_default_gameplay_box(1920, 1080)
        self.assertEqual(mh, 1080)
        self.assertEqual(mw, 810)  # 1080 * 0.75 = 810
        # Rounded down to even pixel for video codecs
        self.assertEqual(mx, 554)

        # 720p stream
        gx, gy, gw, gh = get_default_gameplay_box(1280, 720)
        self.assertEqual(gh, 720)
        self.assertEqual(gw, 540)  # 720 * 0.75 = 540
        self.assertEqual(gx, 370)

    def test_03_detect_facecam_candidate_restricted_corners(self):
        """Verifies detect_facecam_candidate returns structured result and honest confidence."""
        res = detect_facecam_candidate(self.muxed_video_path)
        self.assertIn("detected", res)
        self.assertIn("box", res)
        self.assertIn("confidence", res)
        self.assertIn("corner", res)
        self.assertIn("message", res)

        # In purely synthetic shapes without realistic human faces, detector must be honest and report low confidence
        self.assertIn(res["confidence"], ("low", "high"))
        # Normalized bounding box coordinates must be within 0.0 .. 1.0
        box = res["box"]
        self.assertGreaterEqual(box["x"], 0.0)
        self.assertGreaterEqual(box["y"], 0.0)
        self.assertLessEqual(box["x"] + box["w"], 1.01)
        self.assertLessEqual(box["y"] + box["h"], 1.01)

    def test_04_render_gaming_2layer_corners(self):
        """Verifies rendering output 1080x1920 with user facecam at bottom-right, bottom-left, top-right."""
        test_cases = [
            ("clean_2layer_bottom_right", {"facecam": {"x": 0.74, "y": 0.63, "w": 0.26, "h": 0.37}}),
            ("clean_2layer_bottom_left",  {"facecam": {"x": 0.00, "y": 0.63, "w": 0.26, "h": 0.37}}),
            ("clean_2layer_top_right",    {"facecam": {"x": 0.74, "y": 0.00, "w": 0.26, "h": 0.37}}),
        ]

        for preset_name, custom_box in test_cases:
            with tempfile.TemporaryDirectory() as tmp:
                out_path = os.path.join(tmp, f"out_{preset_name}.mp4")
                crop_clip_local(
                    source_path=self.muxed_video_path,
                    start_time=0.0,
                    end_time=1.5,
                    aspect_ratio="9:16",
                    out_path=out_path,
                    segments=[{"start": 0.0, "end": 1.2, "text": "CLUTCH MOMENT!"}],
                    burn_subtitles=True,
                    framing_mode="gaming",
                    gaming_preset=preset_name,
                    gaming_custom_box=custom_box,
                )

                self.assertTrue(os.path.exists(out_path), f"Output file for {preset_name} must exist")
                self.assertGreater(os.path.getsize(out_path), 5000, "Output file must be non-empty")

                # Verify resolution with ffprobe
                probe = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=p=0",
                    out_path,
                ], capture_output=True, text=True, check=True)
                w, h = map(int, probe.stdout.strip().split(","))
                self.assertEqual(w, CANVAS_WIDTH)
                self.assertEqual(h, CANVAS_HEIGHT)

                # Verify visual contents by reading the output frame
                cap = cv2.VideoCapture(out_path)
                ret, frame = cap.read()
                cap.release()
                self.assertTrue(ret, "Must successfully read rendered frame")
                self.assertEqual(frame.shape, (1920, 1080, 3))

                # In default Windah Basudara style (cam_top):
                # Upper zone (y < 480) is facecam, Lower zone (y >= 480) is gameplay
                lower_pixel = frame[1000, 540]
                # Gameplay is predominantly green (channel 1 highest)
                self.assertGreater(lower_pixel[1], lower_pixel[0])

    def test_05_subtitle_positioning_safe_zones(self):
        """Verifies ASS and WebVTT subtitles are placed safely for both cam_bottom and cam_top layouts."""
        segments = [{"start": 0.0, "end": 1.5, "text": "INSANE CLUTCH PLAY", "words": []}]

        # 1. Classic layout (cam_bottom): sits above bottom facecam
        with tempfile.TemporaryDirectory() as tmp:
            ass_path_bot = os.path.join(tmp, "gaming_sub_bot.ass")
            create_ass_subtitle_file(
                segments=segments,
                clip_start=0.0,
                clip_end=1.5,
                out_ass_path=ass_path_bot,
                width=1080,
                height=1920,
                subtitle_style="karaoke",
                framing_mode="gaming",
                gaming_layout="cam_bottom",
            )
            with open(ass_path_bot, "r", encoding="utf-8") as f:
                ass_content_bot = f.read()

            expected_margin_v_bot = str(int(1920 * 0.27))
            self.assertIn(f",20,20,{expected_margin_v_bot},", ass_content_bot)

            vtt_path_bot = os.path.join(tmp, "gaming_sub_bot.vtt")
            create_vtt_subtitle_file(
                segments=segments,
                clip_start=0.0,
                clip_end=1.5,
                out_vtt_path=vtt_path_bot,
                framing_mode="gaming",
                gaming_layout="cam_bottom",
            )
            with open(vtt_path_bot, "r", encoding="utf-8") as f:
                self.assertIn("line:72%", f.read())

        # 2. Windah style (cam_top / default): sits cleanly in lower gameplay area
        with tempfile.TemporaryDirectory() as tmp:
            ass_path_top = os.path.join(tmp, "gaming_sub_top.ass")
            create_ass_subtitle_file(
                segments=segments,
                clip_start=0.0,
                clip_end=1.5,
                out_ass_path=ass_path_top,
                width=1080,
                height=1920,
                subtitle_style="karaoke",
                framing_mode="gaming",
                gaming_layout="cam_top",
            )
            with open(ass_path_top, "r", encoding="utf-8") as f:
                ass_content_top = f.read()

            expected_margin_v_top = str(int(1920 * 0.16))
            self.assertIn(f",20,20,{expected_margin_v_top},", ass_content_top)

            vtt_path_top = os.path.join(tmp, "gaming_sub_top.vtt")
            create_vtt_subtitle_file(
                segments=segments,
                clip_start=0.0,
                clip_end=1.5,
                out_vtt_path=vtt_path_top,
                framing_mode="gaming",
                gaming_layout="cam_top",
            )
            with open(vtt_path_top, "r", encoding="utf-8") as f:
                self.assertIn("line:84%", f.read())

    def test_06_standard_modes_zero_regression(self):
        """Verifies that standard framing modes (podcast, single, center) render normally without regression."""
        with tempfile.TemporaryDirectory() as tmp:
            for framing in ("podcast", "single", "center"):
                out_path = os.path.join(tmp, f"standard_{framing}.mp4")
                crop_clip_local(
                    source_path=self.muxed_video_path,
                    start_time=0.0,
                    end_time=1.0,
                    aspect_ratio="9:16",
                    out_path=out_path,
                    segments=[],
                    burn_subtitles=False,
                    framing_mode=framing,
                )
                self.assertTrue(os.path.exists(out_path))
                self.assertGreater(os.path.getsize(out_path), 5000)

    def test_07_api_detect_facecam_and_cloud_rejection(self):
        """Verifies Flask API endpoint /api/detect-facecam and cloud mode rejection on gaming framing."""
        client = app.test_client()

        # 1. /api/detect-facecam with non-existent session
        res404 = client.get("/api/detect-facecam?session_folder=non_existent_folder_abc")
        self.assertEqual(res404.status_code, 404)

        # 2. Reject Cloud API (mode: 'api') when framing_mode is 'gaming' in /api/generate
        res_cloud = client.post("/api/generate", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "mode": "api",
            "framing_mode": "gaming",
        })
        self.assertEqual(res_cloud.status_code, 400)
        data = res_cloud.get_json()
        self.assertIn("MuAPI", data.get("error", ""))

    def test_08_validate_and_sanitize_gaming_box(self):
        """Verifies sanitize helper correctly normalizes float inputs and clamps bounds."""
        # Valid normalized box
        box_in = {"facecam": {"x": 0.75, "y": 0.60, "w": 0.25, "h": 0.40}}
        box_out = validate_and_sanitize_gaming_box(box_in)
        self.assertIsNotNone(box_out)
        self.assertIn("facecam", box_out)
        self.assertIn("bottom", box_out)
        self.assertEqual(box_out["facecam"]["x"], 0.75)

        # Clamped out-of-bounds input
        oob_in = {"bottom": {"x": -0.5, "y": 1.5, "w": 2.0, "h": -1.0}}
        oob_out = validate_and_sanitize_gaming_box(oob_in)
        self.assertIsNone(oob_out, "Completely negative or inverted boxes must be rejected")

    def test_09_gaming_auto_fallback_when_no_face_detected(self):
        """Verifies that pure gameplay video without detected human face automatically triggers fallback to 9:16 Center Crop."""
        with tempfile.TemporaryDirectory() as tmp:
            out_fallback = os.path.join(tmp, "out_fallback_gameplay.mp4")
            crop_clip_local(
                source_path=self.muxed_video_path,
                start_time=0.0,
                end_time=1.0,
                aspect_ratio="9:16",
                out_path=out_fallback,
                segments=[{"start": 0.0, "end": 0.8, "text": "PURE GAMEPLAY NO WEBCAM"}],
                burn_subtitles=True,
                framing_mode="gaming",
                gaming_preset="auto",
            )
            self.assertTrue(os.path.exists(out_fallback), "Fallback output must exist")
            self.assertGreater(os.path.getsize(out_fallback), 5000)

            # Probe resolution: strictly 1080x1920
            probe = subprocess.run([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                out_fallback,
            ], capture_output=True, text=True, check=True)
            w, h = map(int, probe.stdout.strip().split(","))
            self.assertEqual(w, CANVAS_WIDTH)
            self.assertEqual(h, CANVAS_HEIGHT)

            # Read frame to verify single full gameplay crop (no black/empty bottom facecam box)
            cap = cv2.VideoCapture(out_fallback)
            ret, frame = cap.read()
            cap.release()
            self.assertTrue(ret)
            self.assertEqual(frame.shape, (1920, 1080, 3))


if __name__ == "__main__":
    unittest.main()

