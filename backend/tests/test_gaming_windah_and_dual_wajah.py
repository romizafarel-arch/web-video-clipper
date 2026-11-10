import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from shorts_generator.local.clipper import (
    crop_clip_local,
    detect_facecam_candidate,
    _reframe_dual_split,
)
from shorts_generator.local.gaming_presets import (
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    FACECAM_2L_HEIGHT,
    GAMING_PRESETS,
    resolve_gaming_crop_boxes,
    build_gaming_filter_complex,
)
from web_app import app


class TestGamingWindahAndDualWajah(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.video_dual_path = os.path.join(cls.temp_dir.name, "synthetic_dual_1080p.mp4")

        # Create a 2.0-second 1920x1080 video with 2 speakers:
        # Speaker 1 (Blue) on Left [300..600, 300..700]
        # Speaker 2 (Red) on Right [1300..1600, 300..700]
        fps = 25.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(cls.video_dual_path, fourcc, fps, (1920, 1080))
        for _ in range(50):
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            frame[:, :] = (20, 20, 20)
            # Speaker 1 (Left): Blue shirt & simulated face
            cv2.rectangle(frame, (350, 400), (550, 800), (220, 50, 50), -1)  # Blue body (BGR)
            cv2.circle(frame, (450, 350), 90, (180, 160, 200), -1)           # Face
            cv2.putText(frame, "SPEAKER 1", (360, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

            # Speaker 2 (Right): Green/Red shirt & simulated face
            cv2.rectangle(frame, (1350, 400), (1550, 800), (50, 50, 220), -1)  # Red body (BGR)
            cv2.circle(frame, (1450, 350), 90, (180, 160, 200), -1)            # Face
            cv2.putText(frame, "SPEAKER 2", (1360, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

            writer.write(frame)
        writer.release()

        # Add silent AAC audio
        cls.dual_muxed_path = os.path.join(cls.temp_dir.name, "synthetic_dual_with_audio.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-v", "error",
            "-i", cls.video_dual_path,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            cls.dual_muxed_path,
        ], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_01_gaming_facecam_aspect_ratio_and_no_cutoff(self):
        """Verifies gaming facecam preset dimensions match 2.25:1 (900x400 in 1080p)."""
        top, mid, bot = resolve_gaming_crop_boxes("clean_2layer_bottom_right", 1920, 1080)
        bx, by, bw, bh = bot
        self.assertEqual(bw, 900)
        self.assertEqual(bh, 400)
        ratio = bw / float(bh)
        expected_ratio = CANVAS_WIDTH / float(FACECAM_2L_HEIGHT)  # 1080 / 480 = 2.25
        self.assertAlmostEqual(ratio, expected_ratio, delta=0.01)

        # Check filter complex preserves headroom
        fc = build_gaming_filter_complex(top, mid, bot, layout="cam_top")
        self.assertIn("max(0\\,(in_h-out_h)*0.15)", fc)

    def test_02_detect_facecam_candidate_aspect_ratio(self):
        """Verifies auto-detected facecam candidates adhere to 2.25:1 aspect ratio."""
        res = detect_facecam_candidate(self.dual_muxed_path)
        box = res["box"]
        # Convert normalized to 1080p pixel width & height
        px_w = box["w"] * 1920
        px_h = box["h"] * 1080
        ratio = px_w / float(px_h)
        self.assertAlmostEqual(ratio, 2.25, delta=0.2)

    def test_03_dual_wajah_split_render(self):
        """Verifies dual wajah rendering splits scene into 2 parts: top panel and bottom panel."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out_dual.mp4")
            rendered = crop_clip_local(
                source_path=self.dual_muxed_path,
                start_time=0.0,
                end_time=1.5,
                aspect_ratio="9:16",
                out_path=out_path,
                segments=[{"start": 0.0, "end": 1.2, "text": "DUAL SPEAKER PODCAST"}],
                burn_subtitles=True,
                framing_mode="dual",
            )
            self.assertTrue(os.path.exists(rendered))
            self.assertGreater(os.path.getsize(rendered), 5000)

            # Check dimensions (1080x1920)
            cap = cv2.VideoCapture(rendered)
            ret, frame = cap.read()
            cap.release()
            self.assertTrue(ret)
            self.assertEqual(frame.shape, (1920, 1080, 3))

            # Verify Top panel (y < 960) has Speaker 1 (Blue body)
            top_sample = frame[450, 390]
            # Verify Bottom panel (y >= 960) has Speaker 2 (Red body)
            bot_sample = frame[1400, 650]

            # In BGR: Speaker 1 has high blue channel (index 0)
            self.assertGreater(top_sample[0], top_sample[2], "Top panel should be Speaker 1 (Blue)")
            # Speaker 2 has high red channel (index 2)
            self.assertGreater(bot_sample[2], bot_sample[0], "Bottom panel should be Speaker 2 (Red)")

    def test_04_web_app_accepts_dual_framing_mode(self):
        """Verifies Flask backend accepts framing_mode='dual' in request payloads."""
        client = app.test_client()
        res = client.post("/api/generate", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "framing_mode": "dual",
        })
        # Should NOT return 400 framing error
        self.assertNotEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
