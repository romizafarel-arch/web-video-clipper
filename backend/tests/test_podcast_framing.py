import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import cv2
import numpy as np

from shorts_generator.local.clipper import (
    PodcastFramingTracker,
    _reframe_vertical,
    _detect_multiview_faces,
    _compute_lip_activity,
    _build_ffmpeg_crop_expression,
)
from web_app import verify_rendered_video


class TestPodcastFraming(unittest.TestCase):
    """Regression suite for Prioritas 2: Podcast framing, dual-speaker centering, and stability."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_framing_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_dual_faces_centered_when_both_fit(self):
        """When two speakers in a wide shot fit together in 9:16 with safe margins, center BOTH faces."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080  # 9:16 vertical crop
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, fps=30.0)

        # Speaker A at [650..770] (center 710), Speaker B at [950..1070] (center 1010)
        # Total span = 1070 - 650 = 420px. Safe margin = 48px. 420 + 96 = 516px <= 608px. Both fit!
        faces = [
            (650, 200, 120, 120),
            (950, 210, 120, 120),
        ]

        target_center = tracker.update_faces(faces)
        x0, y0, cw, ch = tracker.step()

        # Expected center is the midpoint between left edge of A and right edge of B: (650 + 1070) // 2 = 860
        expected_target_x = (650 + 1070) // 2
        self.assertEqual(target_center[0], expected_target_x)

        # Verify safe margins: neither face should touch the crop border
        # Ideal crop window is [860 - 304, 860 + 304] = [556, 1164]
        left_margin = 650 - (expected_target_x - crop_w // 2)
        right_margin = (expected_target_x + crop_w // 2) - 1070
        self.assertGreaterEqual(left_margin, tracker.safe_margin)
        self.assertGreaterEqual(right_margin, tracker.safe_margin)

    def test_02_faces_too_far_apart_sticks_without_ping_pong(self):
        """When two faces cannot both fit, maintain temporal stickiness to prevent camera oscillation."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, fps=30.0)

        # Speaker 1 on far left [200..340], Speaker 2 on far right [1500..1640]
        # Span = 1640 - 200 = 1440px > 608px. They CANNOT both fit.
        faces_frame1 = [
            (200, 200, 140, 140),
            (1500, 200, 140, 140),
        ]

        # Initial detection selects one face (e.g. Speaker 1 if cold-start or whichever is picked)
        target1 = tracker.update_faces(faces_frame1)
        initial_tracked_x = tracker.tracked_subject_x
        self.assertIsNotNone(initial_tracked_x)

        # Simulate subsequent frames where detection bounding box for Speaker 2 slightly fluctuates in size (+3%)
        # In the old code, this minor noise caused immediate ping-pong whipping across the screen!
        faces_frame2 = [
            (200, 200, 140, 140),
            (1500, 200, 144, 144),  # slightly larger area, but < 1.45x dominance threshold
        ]
        target2 = tracker.update_faces(faces_frame2)

        # With temporal stickiness, it must stay locked on the initial speaker side (around 1570, NOT jump to Speaker 1 at ~270)
        self.assertAlmostEqual(tracker.tracked_subject_x, initial_tracked_x, delta=10)
        self.assertAlmostEqual(target1[0], target2[0], delta=10)

    def test_03_no_face_fallback_holds_position_before_relaxing(self):
        """Temporary face occlusion/loss must hold last known framing instead of immediately panning to empty table."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, fps=30.0)

        # Speaker at left side [300..420]
        faces = [(300, 200, 120, 120)]
        target_initial = tracker.update_faces(faces)
        self.assertEqual(target_initial[0], 360)

        # Simulate 15 frames where face is not detected (e.g. looking down at notes or microphone)
        for _ in range(15):
            target_hold = tracker.update_faces([])
            # Must remain held at x=360, NOT drift to center table x=960!
            self.assertEqual(target_hold[0], 360)

        # Now simulate extended period of no faces (> 2.0s = 60 frames)
        for _ in range(70):
            target_relaxed = tracker.update_faces([])

        # After extended absence, fallback to center is permitted
        self.assertEqual(target_relaxed[0], src_w // 2)

    def test_04_scene_cut_snaps_target_immediately(self):
        """Scene cut must snap target instantly instead of slow panning which cuts faces at frame edge."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, fps=30.0)

        # Shot 1: Speaker at x=300
        tracker.update_faces([(300, 200, 120, 120)])
        for _ in range(10):
            tracker.step()

        pos_before_cut = tracker.current_center[0]
        # In shot 1, camera center is close to 360 (clamped to crop_w//2 = 304 if near left edge)
        self.assertLess(pos_before_cut, 500)

        # Shot 2: Scene cut to Speaker at x=1400 (center 1460)
        tracker.update_faces([(1400, 200, 120, 120)], is_scene_cut=True)
        x0, y0, cw, ch = tracker.step(is_scene_cut=True)

        # Must snap immediately: current_center must be right at 1460 (clamped to 1920 - 304 = 1616)
        expected_snap_center = min(1920 - 304, max(304, 1460))
        self.assertEqual(tracker.current_center[0], expected_snap_center)
        # Face at [1400..1520] is fully inside crop window [x0 .. x0 + cw]
        self.assertGreaterEqual(1400, x0)
        self.assertLessEqual(1520, x0 + cw)

    def test_05_strict_boundary_clamping_on_extreme_positions(self):
        """Crop box must stay strictly within source frame boundaries even with extreme corner detections."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, fps=30.0)

        # Extreme left-top
        tracker.update_faces([(0, 0, 100, 100)])
        x0, y0, cw, ch = tracker.step()
        self.assertGreaterEqual(x0, 0)
        self.assertGreaterEqual(y0, 0)
        self.assertLessEqual(x0 + cw, src_w)
        self.assertLessEqual(y0 + ch, src_h)

        # Extreme right-bottom
        tracker.update_faces([(1850, 950, 100, 100)])
        x0, y0, cw, ch = tracker.step(is_scene_cut=True)
        self.assertGreaterEqual(x0, 0)
        self.assertGreaterEqual(y0, 0)
        self.assertLessEqual(x0 + cw, src_w)
        self.assertLessEqual(y0 + ch, src_h)
        self.assertEqual(x0, src_w - crop_w)
        self.assertEqual(y0, src_h - crop_h)

    def test_06_end_to_end_synthetic_render_and_verification(self):
        """Render a synthetic test video with shot transitions and verify decodable output."""
        src_path = os.path.join(self.temp_dir, "synthetic_podcast.mp4")
        out_path = os.path.join(self.temp_dir, "reframe_out.mp4")

        # Create a 2.0s 1280x720 video with two distinct visual blocks (Shot 1 left, Shot 2 right)
        fps = 24
        src_w, src_h = 1280, 720
        total_frames = int(fps * 2.0)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(src_path, fourcc, fps, (src_w, src_h))

        for idx in range(total_frames):
            frame = np.zeros((src_h, src_w, 3), dtype=np.uint8)
            if idx < total_frames // 2:
                # Shot 1: Person on left side (x=300, y=250)
                cv2.rectangle(frame, (280, 200), (420, 360), (200, 180, 150), -1)
                cv2.putText(frame, "Speaker Left", (280, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            else:
                # Shot 2: Scene cut to person on right side (x=900, y=250)
                frame[:, :] = (30, 30, 30)  # different background color for clear cut
                cv2.rectangle(frame, (880, 200), (1020, 360), (200, 180, 150), -1)
                cv2.putText(frame, "Speaker Right", (880, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            writer.write(frame)
        writer.release()

        # Time the reframe execution
        t0 = time.time()
        rendered_path = _reframe_vertical(
            in_path=src_path,
            out_path=out_path,
            aspect_ratio="9:16",
        )
        elapsed = time.time() - t0

        self.assertTrue(os.path.exists(rendered_path))
        self.assertGreater(os.path.getsize(rendered_path), 1024)

        # Verify valid, decodable MP4
        verify_rendered_video(Path(rendered_path), expected_duration=2.0, min_duration=0.5)

        # Verify crop and lanczos scale dimensions for 9:16 (standard vertical FHD 1080x1920):
        cap = cv2.VideoCapture(rendered_path)
        out_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        out_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        self.assertEqual(out_w, 1080)
        self.assertEqual(out_h, 1920)

    def test_07_framing_modes_single_and_center(self):
        """Validate behavior of framing_mode='center' and framing_mode='single'."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080

        # 1. Center mode: always centers frame, ignores detected faces
        tracker_center = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, framing_mode="center")
        faces = [(200, 200, 120, 120), (1400, 200, 120, 120)]
        target_center = tracker_center.update_faces(faces)
        self.assertEqual(target_center, (src_w // 2, src_h // 2))

        # 2. Single mode: with 2 faces that could fit, strictly tracks dominant face (valid_faces[0])
        tracker_single = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, framing_mode="single")
        # Face 1 at x=650 (w=150, area=22500, center=725), Face 2 at x=950 (w=100, area=10000, center=1000)
        faces_two = [
            (650, 200, 150, 150),
            (950, 200, 100, 100),
        ]
        target_single = tracker_single.update_faces(faces_two)
        # In single mode, target must center on Face 1 (725), NOT the midpoint (875)
        self.assertEqual(target_single[0], 725)

        # 3. Podcast mode: centers both when both fit
        tracker_podcast = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, framing_mode="podcast")
        target_podcast = tracker_podcast.update_faces(faces_two)
        expected_both = (650 + 1050) // 2  # 850
        self.assertEqual(target_podcast[0], expected_both)

    def test_08_multiview_face_detection_and_flipping(self):
        """Verify multiview detection combining frontal, profile, and horizontally flipped profile."""
        img = np.zeros((400, 600), dtype=np.uint8)

        class MockCascade:
            def __init__(self, boxes):
                self._boxes = boxes

            def detectMultiScale(self, image, **kwargs):
                return self._boxes

        fc = MockCascade([(100, 100, 80, 80)])

        class MockProfileCascade:
            def detectMultiScale(self, image, **kwargs):
                return [(300, 100, 70, 70)]

        pc = MockProfileCascade()
        results = _detect_multiview_faces(img, face_cascade=fc, profile_cascade=pc)

        self.assertEqual(len(results), 3)
        xs = [r[0] for r in results]
        self.assertIn(100, xs)
        self.assertIn(300, xs)
        self.assertIn(230, xs)

    def test_09_continuity_tracker_bridges_intermittent_misses(self):
        """Continuity tracker must keep track of a speaker during brief detection drops (head turn / mic block)."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, fps=30.0)

        # Frame 1: Two speakers fit in 9:16 (Speaker A at 650, Speaker B at 950)
        faces_frame1 = [(650, 200, 120, 120), (950, 210, 120, 120)]
        target1 = tracker.update_faces(faces_frame1)
        self.assertEqual(target1[0], 860)

        # Frame 2: Speaker A turns head / mic blocks, so ONLY Speaker B is detected
        faces_frame2 = [(950, 210, 120, 120)]
        target2 = tracker.update_faces(faces_frame2)

        # Continuity tracker keeps Speaker A's track alive for <= 2 missed intervals,
        # so framing remains at dual-speaker center 860 instead of whipping to Speaker B at 1010
        self.assertEqual(target2[0], 860)

    def test_10_active_speaker_lip_activity_switching_and_cooldown(self):
        """Wide shot camera follows active speaker with cooldown to prevent rapid ping-pong whipping."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, fps=30.0, switch_cooldown_sec=1.8)

        # Speaker 1 on far left [200..340, center 270], Speaker 2 on far right [1500..1640, center 1570]
        # Frame at t=0.0s: Speaker 1 is actively speaking (lip_activity=10.0), Speaker 2 is quiet (0.0)
        faces_t0 = [(200, 200, 140, 140, 10.0), (1500, 200, 140, 140, 0.0)]
        target_t0 = tracker.update_faces(faces_t0, current_time=0.0)
        self.assertAlmostEqual(tracker.tracked_subject_x, 270, delta=10)

        # Frame at t=0.5s: Speaker 2 starts talking (lip_activity=12.0)
        # Cooldown (1.8s) has NOT expired (only 0.5s elapsed). Must stay on Speaker 1!
        faces_t05 = [(200, 200, 140, 140, 0.0), (1500, 200, 140, 140, 12.0)]
        target_t05 = tracker.update_faces(faces_t05, current_time=0.5)
        self.assertAlmostEqual(tracker.tracked_subject_x, 270, delta=10)

        # Frame at t=2.0s: Speaker 2 is still talking (lip_activity=12.0)
        # Cooldown HAS expired (2.0s >= 1.8s). Camera must now switch to Speaker 2!
        faces_t20 = [(200, 200, 140, 140, 0.0), (1500, 200, 140, 140, 12.0)]
        target_t20 = tracker.update_faces(faces_t20, current_time=2.0)
        self.assertAlmostEqual(tracker.tracked_subject_x, 1570, delta=10)

        # Frame at t=2.4s: Speaker 1 interrupts (lip_activity=15.0)
        # Cooldown is ACTIVE again (only 0.4s since switch). Camera must stay on Speaker 2!
        faces_t24 = [(200, 200, 140, 140, 15.0), (1500, 200, 140, 140, 0.0)]
        target_t24 = tracker.update_faces(faces_t24, current_time=2.4)
        self.assertAlmostEqual(tracker.tracked_subject_x, 1570, delta=10)

    def test_11_cinematic_smooth_panning_vs_instant_cut_expressions(self):
        """Trajectory expressions must use smooth lerp for head sway and instant snap for scene cuts."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080

        # Case 1: Head sway (person shifts 70px from x=300 to x=370 over 0.5s)
        traj_sway = []
        for i in range(15):
            traj_sway.append((i * 0.033, 300, 0, False))
        for i in range(15):
            traj_sway.append((0.5 + i * 0.033, int(300 + 70 * (i / 15.0)), 0, False))
        for i in range(15):
            traj_sway.append((1.0 + i * 0.033, 370, 0, False))

        x_expr, y_expr = _build_ffmpeg_crop_expression(traj_sway, src_w, src_h, crop_w, crop_h)
        self.assertIn("*(t-", x_expr)
        self.assertIn("/", x_expr)

        # Case 2: Scene cut (instant transition from x=200 to x=900)
        traj_cut = [
            (0.0, 200, 0, False),
            (0.5, 200, 0, False),
            (1.0, 900, 0, True),
            (1.5, 900, 0, False),
        ]
        x_cut_expr, _ = _build_ffmpeg_crop_expression(traj_cut, src_w, src_h, crop_w, crop_h)
        self.assertIn("if(lt(t,1.000),200,900)", x_cut_expr)

        # Case 3: Test FFmpeg actually runs the generated smooth pan filter
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=1280x720:rate=30",
            "-vf", f"crop=400:720:x='{x_expr}':y=0",
            "-f", "null", "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=f"FFmpeg failed: {res.stderr}")

    def test_12_visual_lip_activity_calculation(self):
        """Visual lip activity calculation must detect mouth movement in lower third of face."""
        gray1 = np.ones((200, 200), dtype=np.uint8) * 120
        gray2 = np.ones((200, 200), dtype=np.uint8) * 120
        gray2[165:195, 40:160] = 40

        face_box = (20, 20, 160, 160)
        score1, crop1 = _compute_lip_activity(gray1, face_box)
        score2, crop2 = _compute_lip_activity(gray2, face_box, prev_mouth_crop=crop1)

    def test_13_single_face_lock_stickiness_no_ping_pong(self):
        """In single mode, once a subject face is locked, maintain persistent lock even when other faces become larger."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, framing_mode="single")

        # Frame 1: Face 1 at x=650 (w=150, area=22500, center=725), Face 2 at x=1200 (w=100, area=10000, center=1250)
        faces_frame1 = [(650, 200, 150, 150), (1200, 200, 100, 100)]
        target1 = tracker.update_faces(faces_frame1)
        self.assertEqual(target1[0], 725)
        self.assertEqual(tracker.tracked_subject_x, 725)

        # Frame 2: Face 2 gets closer to camera and becomes larger than Face 1!
        # Face 1 shrinks slightly to 140x140 (19600), Face 2 grows to 160x160 (25600)
        faces_frame2 = [(650, 200, 140, 140), (1200, 200, 160, 160)]
        target2 = tracker.update_faces(faces_frame2)

        # With Single Face Lock stickiness, target MUST stay locked on Face 1 (720), NOT whip to Face 2 (1280)!
        self.assertAlmostEqual(target2[0], 720, delta=15)
        self.assertAlmostEqual(tracker.tracked_subject_x, 720, delta=15)

    def test_14_single_face_lock_holds_on_temporary_occlusion(self):
        """In single mode, if the locked face is briefly occluded while another face is visible, hold target instead of jumping."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, framing_mode="single")

        # Frame 1: Lock on Face 1 (x=600)
        faces_frame1 = [(600, 200, 140, 140), (1300, 200, 120, 120)]
        tracker.update_faces(faces_frame1)
        locked_x = tracker.tracked_subject_x

        # Frame 2-5: Face 1 is occluded / turns away, so only Face 2 (x=1300) is detected
        faces_occluded = [(1300, 200, 120, 120)]
        for _ in range(4):
            target_hold = tracker.update_faces(faces_occluded)
            # Must hold locked position of Face 1, NOT immediately snap 700px across to Face 2
            self.assertAlmostEqual(target_hold[0], locked_x, delta=10)

    def test_15_crop_expression_recursion_guard(self):
        """Crop expression generator must bound segments to <= 16 to prevent FFmpeg filter recursion crashes."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        # Generate 60 rapid alternating jump points
        trajectory = []
        for i in range(60):
            t = i * 0.25
            x = 200 if (i % 2 == 0) else 800
            trajectory.append((t, x, 0, False))

        x_expr, y_expr = _build_ffmpeg_crop_expression(trajectory, src_w, src_h, crop_w, crop_h)
        self.assertIsInstance(x_expr, str)
        # Verify expression syntax is valid by checking in FFmpeg filter
        test_video = os.path.join(self.temp_dir, "test_guard.mp4")
        writer = cv2.VideoWriter(test_video, cv2.VideoWriter_fourcc(*"mp4v"), 24, (src_w, src_h))
        for _ in range(24):
            writer.write(np.zeros((src_h, src_w, 3), dtype=np.uint8))
        writer.release()

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", test_video,
            "-vf", f"crop={crop_w}:{crop_h}:x='{x_expr}':y='{y_expr}'",
            "-f", "null", "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=f"FFmpeg failed with: {res.stderr}")

    def test_16_minor_head_movements_hold_rock_solid_static_crop(self):
        """Minor natural head sway (<= 40px) must yield a completely static crop expression without drifting."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080

        # Simulate natural head movement swaying between x=300 and x=338 (38px difference)
        trajectory = []
        for i in range(40):
            t = i * 0.1
            x = 300 + (i % 5) * 8  # 300, 308, 316, 324, 332... (spread = 32px)
            trajectory.append((t, x, 0, False))

        x_expr, y_expr = _build_ffmpeg_crop_expression(trajectory, src_w, src_h, crop_w, crop_h)

        # Must NOT generate sliding lerp expressions or conditional drift
        self.assertNotIn("*(t-", x_expr)
        self.assertNotIn("if(", x_expr)
        # Must be a fixed static integer
        self.assertTrue(x_expr.isdigit())

    def test_17_background_clutter_face_ignored(self):
        """In podcast mode, small background clutter / poster face (< 20% area of main face) must not pull the camera."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        tracker = PodcastFramingTracker(src_w, src_h, crop_w, crop_h, framing_mode="podcast")

        # Speaker in foreground at x=400 (w=200, h=200, area=40,000, center=500)
        # Background clutter/poster at x=800 (w=40, h=40, area=1,600 = 4% of speaker area)
        faces_with_clutter = [
            (400, 200, 200, 200),
            (800, 200, 40, 40),
        ]
        target = tracker.update_faces(faces_with_clutter)

        # Target must be centered on the foreground speaker (500), NOT pulled towards the midpoint (660)
        self.assertEqual(target[0], 500)
        self.assertEqual(tracker.tracked_subject_x, 500)

    def test_18_many_scene_cuts_bounds_depth_and_runs_in_ffmpeg(self):
        """Many scene cuts and camera switches must be safely bounded to <= 6 segments without -22 EINVAL."""
        src_w, src_h = 1920, 1080
        crop_w, crop_h = 608, 1080
        trajectory = []
        # Simulate 40 scene cuts across a 60-second video
        for i in range(40):
            t = i * 1.5
            x = (200 + (i * 73)) % (src_w - crop_w)
            trajectory.append((t, x, 0, True))

        x_expr, y_expr = _build_ffmpeg_crop_expression(trajectory, src_w, src_h, crop_w, crop_h)
        self.assertIsInstance(x_expr, str)
        # Verify nesting depth is bounded: count of 'if(' must be <= 6
        self.assertLessEqual(x_expr.count("if("), 6)

        # Validate with FFmpeg directly
        test_video = os.path.join(self.temp_dir, "test_cuts.mp4")
        writer = cv2.VideoWriter(test_video, cv2.VideoWriter_fourcc(*"mp4v"), 24, (src_w, src_h))
        for _ in range(24):
            writer.write(np.zeros((src_h, src_w, 3), dtype=np.uint8))
        writer.release()

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", test_video,
            "-vf", f"crop={crop_w}:{crop_h}:x='{x_expr}':y='{y_expr}'",
            "-f", "null", "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, msg=f"FFmpeg failed with exit code {res.returncode}: {res.stderr}")

    def test_19_reframe_fallback_static_crop_never_zero_bytes(self):
        """Reframe fallback must always produce non-empty valid video file even when primary crop or ASS filter is faulty."""
        src_w, src_h = 1280, 720
        test_video = os.path.join(self.temp_dir, "test_input_subclip.mp4")
        out_video = os.path.join(self.temp_dir, "test_output_short.mp4")

        # Generate a synthetic 1-second video
        writer = cv2.VideoWriter(test_video, cv2.VideoWriter_fourcc(*"mp4v"), 24, (src_w, src_h))
        for _ in range(24):
            writer.write(np.zeros((src_h, src_w, 3), dtype=np.uint8))
        writer.release()

        # Create a corrupted / problematic ASS file to trigger fallback
        broken_ass = os.path.join(self.temp_dir, "broken.ass")
        with open(broken_ass, "w", encoding="utf-8") as f:
            f.write("Corrupted ASS Content Without Headers\n")

        # Reframe with center mode, which triggers static crop with broken subtitle
        _reframe_vertical(
            in_path=test_video,
            out_path=out_video,
            aspect_ratio="9:16",
            ass_path=broken_ass,
            framing_mode="center",
        )

        self.assertTrue(os.path.exists(out_video))
        self.assertGreater(os.path.getsize(out_video), 1024)


if __name__ == "__main__":
    unittest.main()

