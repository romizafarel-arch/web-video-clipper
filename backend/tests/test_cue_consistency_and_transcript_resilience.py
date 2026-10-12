import math
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List

from shorts_generator.local.clipper import (
    _format_ass_time,
    _format_vtt_time,
    _parse_ass_time,
    _parse_vtt_time,
    build_validated_cues,
    create_ass_subtitle_file,
    create_vtt_subtitle_file,
    crop_clip_local,
)
from web_app import verify_rendered_video


def parse_ass_dialogues(ass_path: str) -> List[Dict]:
    """Parse dialogue lines from an ASS file into structured cue dictionaries."""
    cues = []
    with open(ass_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Dialogue:"):
                # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
                parts = line.strip().split(",", 9)
                if len(parts) >= 10:
                    start_s = _parse_ass_time(parts[1])
                    end_s = _parse_ass_time(parts[2])
                    raw_text = parts[9].strip()
                    clean_text = re.sub(r"\{[^}]*\}", "", raw_text).strip()
                    cues.append({"start": start_s, "end": end_s, "text": clean_text, "raw": raw_text})
    return cues


def parse_vtt_cues(vtt_path: str) -> List[Dict]:
    """Parse cues from a WebVTT file into structured cue dictionaries."""
    cues = []
    with open(vtt_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f]

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if "-->" in line:
            time_parts = line.split("-->")
            start_s = _parse_vtt_time(time_parts[0].strip())
            end_s = _parse_vtt_time(time_parts[1].strip().split()[0])
            idx += 1
            text_lines = []
            while idx < len(lines) and lines[idx]:
                text_lines.append(lines[idx])
                idx += 1
            text = " ".join(text_lines).strip()
            cues.append({"start": start_s, "end": end_s, "text": text})
        else:
            idx += 1
    return cues


class TestCueConsistencyAndTranscriptResilience(unittest.TestCase):
    """Regression suite for transcript timestamp resilience and ASS/VTT cue consistency."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_cues_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cue_parity_between_ass_and_vtt(self):
        """ASS and VTT cues must originate from a single source of truth with matching count, text, and timing."""
        segments = [
            {"start": 10.0, "end": 14.0, "text": "Halo kawan selamat datang kembali di podcast kami."},
            {"start": 14.5, "end": 18.0, "text": "Hari ini topik kita sangat menarik untuk dibahas bersama."},
            {"start": 18.5, "end": 21.0, "text": "Simak sampai tuntas ya."},
        ]
        clip_start = 10.0
        clip_end = 21.0

        cues = build_validated_cues(segments, clip_start=clip_start, clip_end=clip_end, source_duration=30.0)
        self.assertTrue(len(cues) >= 3)

        ass_file = os.path.join(self.temp_dir, "test_parity.ass")
        vtt_file = os.path.join(self.temp_dir, "test_parity.vtt")

        # Generate both formats using the shared validated cues
        ok_ass = create_ass_subtitle_file(segments, clip_start, clip_end, ass_file, cues=cues)
        ok_vtt = create_vtt_subtitle_file(segments, clip_start, clip_end, vtt_file, cues=cues)
        self.assertTrue(ok_ass)
        self.assertTrue(ok_vtt)

        ass_cues = parse_ass_dialogues(ass_file)
        vtt_cues = parse_vtt_cues(vtt_file)

        # 1. Exact cue count parity
        self.assertEqual(len(ass_cues), len(vtt_cues))
        self.assertEqual(len(ass_cues), len(cues))

        # 2. Strict text match and timing alignment (tolerance <= 0.01s for centisecond ASS vs ms VTT)
        for i, (a, v) in enumerate(zip(ass_cues, vtt_cues)):
            self.assertEqual(a["text"], v["text"], f"Cue {i} text mismatch: '{a['text']}' != '{v['text']}'")
            self.assertAlmostEqual(a["start"], v["start"], delta=0.015, msg=f"Cue {i} start mismatch")
            self.assertAlmostEqual(a["end"], v["end"], delta=0.015, msg=f"Cue {i} end mismatch")

    def test_conversational_overlap_preservation_video2(self):
        """Legitimate multi-speaker overlaps (Video 2 podcast case) must be preserved without dropping or overwriting."""
        segments = [
            {"start": 5.0, "end": 9.0, "text": "Ini poin paling krusial dalam pembahasan kita."},
            # Overlapping turn from Speaker 2
            {"start": 7.0, "end": 10.5, "text": "Betul sekali saya sangat sepakat."},
            # Next normal turn
            {"start": 11.0, "end": 14.0, "text": "Mari kita lanjutkan ke topik selanjutnya."},
        ]
        clip_start = 5.0
        clip_end = 15.0

        cues = build_validated_cues(segments, clip_start=clip_start, clip_end=clip_end, source_duration=20.0)

        # Ensure text from both Speaker 1 and Speaker 2 is present in the cues
        all_text = " ".join(c["text"] for c in cues)
        self.assertIn("KRUSIAL", all_text)
        self.assertIn("BETUL", all_text)
        self.assertIn("SEPAKAT", all_text)
        self.assertIn("LANJUTKAN", all_text)

        # Ensure cues remain chronologically sorted by start time
        for i in range(len(cues) - 1):
            self.assertLessEqual(cues[i]["start"], cues[i + 1]["start"])

    def test_inverted_and_nonfinite_timestamps_quarantined_video3(self):
        """Inverted (end < start), non-finite, and zero duration segments must be quarantined without shifting subsequent cues."""
        segments = [
            {"start": 2.0, "end": 4.0, "text": "Kalimat awal sebelum masalah."},
            # Inverted timestamp anomaly (Video 3 pattern)
            {"start": 6.5, "end": 3.2, "text": "Anomali terbalik harus dibuang."},
            # Non-finite timestamps
            {"start": float("nan"), "end": 7.0, "text": "Anomali nan harus dibuang."},
            {"start": 8.0, "end": float("inf"), "text": "Anomali inf harus dibuang."},
            # Zero-duration segment
            {"start": 9.0, "end": 9.0, "text": "Anomali zero duration harus dibuang."},
            # Negative start timestamp
            {"start": -3.0, "end": 2.0, "text": "Anomali negatif harus dibuang."},
            # Valid segment occurring later
            {"start": 12.0, "end": 15.0, "text": "Kalimat kedua setelah anomali."},
        ]
        clip_start = 0.0
        clip_end = 20.0

        cues = build_validated_cues(segments, clip_start=clip_start, clip_end=clip_end, source_duration=25.0)

        all_text = " ".join(c["text"] for c in cues)
        self.assertIn("KALIMAT AWAL", all_text)
        self.assertIn("KALIMAT KEDUA SETELAH ANOMALI", all_text)
        self.assertNotIn("TERBALIK", all_text)
        self.assertNotIn("NAN", all_text)
        self.assertNotIn("INF", all_text)
        self.assertNotIn("ZERO DURATION", all_text)
        self.assertNotIn("NEGATIF", all_text)

        # Verify that the subsequent cue did NOT shift or drift
        first_post_anomaly_cue = [c for c in cues if "KALIMAT KEDUA" in c["text"]][0]
        # Start relative to clip_start=0.0 should be exactly 12.0
        self.assertAlmostEqual(first_post_anomaly_cue["start"], 12.0, delta=0.01)

        # Verify no dummy/hallucinated text filled the silence between 4.0 and 12.0
        gap_cues = [c for c in cues if 4.1 <= c["start"] < 11.9]
        self.assertEqual(len(gap_cues), 0, "No artificial cues or dummy text should be generated for silence")

    def test_out_of_bounds_timestamps_quarantined(self):
        """Timestamps exceeding the source media duration must be rejected."""
        source_dur = 25.0
        segments = [
            {"start": 5.0, "end": 10.0, "text": "Segmen dalam durasi normal."},
            {"start": 20.0, "end": 24.5, "text": "Segmen menjelang akhir durasi."},
            {"start": 28.0, "end": 35.0, "text": "Segmen halusinasi melampaui durasi sumber."},
        ]
        clip_start = 0.0
        clip_end = 25.0

        cues = build_validated_cues(segments, clip_start=clip_start, clip_end=clip_end, source_duration=source_dur)
        all_text = " ".join(c["text"] for c in cues)

        self.assertIn("DURASI NORMAL", all_text)
        self.assertIn("MENJELANG AKHIR", all_text)
        self.assertNotIn("MELAMPAUI DURASI", all_text)

    def test_untrusted_spans_quarantine(self):
        """Segments falling within untrusted spans (e.g. repetition loops) must be quarantined."""
        segments = [
            {"start": 1.0, "end": 4.0, "text": "Bagian pembuka yang valid."},
            {"start": 5.0, "end": 9.0, "text": "Bagian halusinasi repetitif tidak terpercaya."},
            {"start": 11.0, "end": 14.0, "text": "Bagian penutup yang kembali valid."},
        ]
        untrusted_spans = [{"start": 4.8, "end": 9.5}]

        cues = build_validated_cues(
            segments,
            clip_start=0.0,
            clip_end=15.0,
            source_duration=20.0,
            untrusted_spans=untrusted_spans,
        )
        all_text = " ".join(c["text"] for c in cues)

        self.assertIn("BAGIAN PEMBUKA", all_text)
        self.assertNotIn("HALUSINASI REPETITIF", all_text)
        self.assertIn("BAGIAN PENUTUP", all_text)

        # Cues after untrusted span remain properly timed at 11.0
        closing_cue = [c for c in cues if "PENUTUP" in c["text"]][0]
        self.assertAlmostEqual(closing_cue["start"], 11.0, delta=0.01)

    def test_indonesian_english_code_switching_and_missing_stt_handling(self):
        """Mixed Indonesian-English speech must be preserved cleanly; omitted STT words must not be hallucinated."""
        mixed_segments = [
            {
                "start": 2.0,
                "end": 6.0,
                "text": "Kita harus scale up system architecture kita secara agile dan robust.",
            }
        ]
        cues = build_validated_cues(mixed_segments, clip_start=0.0, clip_end=8.0, source_duration=10.0)
        all_text = " ".join(c["text"] for c in cues)

        self.assertIn("SCALE UP", all_text)
        self.assertIn("SYSTEM ARCHITECTURE", all_text)
        self.assertIn("AGILE DAN ROBUST", all_text)

        # Simulate STT dropping words during code-switching (e.g. omitting English technical term)
        stt_dropped_segment = [
            {
                "start": 2.0,
                "end": 4.0,
                "text": "Kita harus secara agile.",
            }
        ]
        cues_dropped = build_validated_cues(stt_dropped_segment, clip_start=0.0, clip_end=8.0, source_duration=10.0)
        dropped_text = " ".join(c["text"] for c in cues_dropped)

        self.assertIn("AGILE", dropped_text)
        self.assertNotIn("SCALE UP", dropped_text)
        # Verify duration matches actual segment (2.0 to 4.0), not artificially inflated to 6.0
        self.assertAlmostEqual(cues_dropped[-1]["end"], 4.0, delta=0.05)

    def test_clipper_pipeline_integration_small_fixture(self):
        """End-to-end integration test rendering a tiny synthetic fixture without touching output_val_v*."""
        fixture_video = os.path.join(self.temp_dir, "synthetic_src.mp4")
        out_short = os.path.join(self.temp_dir, "short_01.mp4")
        expected_vtt = os.path.join(self.temp_dir, "short_01.vtt")

        # Create a 2.0s synthetic MP4 with color testsrc and 1kHz sine audio
        cmd_gen = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            fixture_video,
        ]
        res = subprocess.run(cmd_gen, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"FFmpeg fixture generation failed: {res.stderr}")

        segments = [
            {"start": 0.2, "end": 0.9, "text": "UJI INTEGRASI RUNTIME"},
            {"start": 1.0, "end": 1.8, "text": "KONSISTENSI CUE SUBTITLE"},
        ]

        # Call crop_clip_local with burn_subtitles=True
        res_path = crop_clip_local(
            source_path=fixture_video,
            start_time=0.0,
            end_time=2.0,
            aspect_ratio="9:16",
            out_path=out_short,
            segments=segments,
            burn_subtitles=True,
            source_duration=2.0,
        )

        self.assertTrue(os.path.exists(res_path))
        self.assertTrue(os.path.exists(expected_vtt))

        # Staging verification checks that media is valid, decodable, and correct duration
        verify_rendered_video(Path(res_path), expected_duration=2.0, min_duration=0.5)

        # Verify VTT cues match the input segments
        vtt_cues = parse_vtt_cues(expected_vtt)
        self.assertTrue(len(vtt_cues) >= 2)
        vtt_text = " ".join(c["text"] for c in vtt_cues)
        self.assertIn("UJI INTEGRASI", vtt_text)
        self.assertIn("KONSISTENSI CUE", vtt_text)

    def test_word_by_word_karaoke_ass_formatting(self):
        """ASS karaoke format must use \\kf tags, positive centiseconds, and exact duration sum."""
        segments = [
            {"start": 1.0, "end": 4.0, "text": "Halo kawan semua selamat datang."},
        ]
        ass_file = os.path.join(self.temp_dir, "test_karaoke.ass")
        cues = build_validated_cues(segments, clip_start=1.0, clip_end=4.0, source_duration=5.0)
        self.assertTrue(len(cues) > 0)
        self.assertTrue("words" in cues[0])

        ok = create_ass_subtitle_file(segments, 1.0, 4.0, ass_file, cues=cues, subtitle_style="karaoke")
        self.assertTrue(ok)

        ass_dialogues = parse_ass_dialogues(ass_file)
        self.assertEqual(len(ass_dialogues), len(cues))

        for cue, dial in zip(cues, ass_dialogues):
            raw = dial["raw"]
            self.assertIn(r"\kf", raw)
            # Find all \kf<duration> tags
            durations = [int(m) for m in re.findall(r"\\kf(\d+)", raw)]
            self.assertTrue(all(d > 0 for d in durations))
            expected_cue_cs = max(1, int(round((cue["end"] - cue["start"]) * 100)))
            self.assertEqual(sum(durations), expected_cue_cs, "Sum of word centiseconds must match cue duration")

    def test_word_by_word_kinetic_beat_formatting(self):
        """ASS kinetic beat format must use \\k discrete tags with positive centiseconds."""
        segments = [
            {"start": 0.0, "end": 2.5, "text": "Ini tes kinetic beat jump."},
        ]
        ass_file = os.path.join(self.temp_dir, "test_kinetic.ass")
        ok = create_ass_subtitle_file(segments, 0.0, 2.5, ass_file, subtitle_style="kinetic")
        self.assertTrue(ok)

        dialogues = parse_ass_dialogues(ass_file)
        self.assertTrue(len(dialogues) > 0)
        for d in dialogues:
            self.assertIn(r"\k", d["raw"])
            durations = [int(m) for m in re.findall(r"\\k(\d+)", d["raw"])]
            self.assertTrue(all(dur > 0 for dur in durations))

    def test_classic_and_none_subtitle_styles(self):
        """Classic style produces plain text without tags; 'none' creates no file."""
        segments = [{"start": 0.0, "end": 2.0, "text": "Teks statis tanpa efek."}]
        ass_classic = os.path.join(self.temp_dir, "test_classic.ass")
        ok_classic = create_ass_subtitle_file(segments, 0.0, 2.0, ass_classic, subtitle_style="classic")
        self.assertTrue(ok_classic)

        dialogues = parse_ass_dialogues(ass_classic)
        self.assertNotIn(r"\kf", dialogues[0]["raw"])
        self.assertNotIn(r"\k", dialogues[0]["raw"])
        self.assertEqual(dialogues[0]["text"], "TEKS STATIS TANPA EFEK.")

        ass_none = os.path.join(self.temp_dir, "test_none.ass")
        ok_none = create_ass_subtitle_file(segments, 0.0, 2.0, ass_none, subtitle_style="none")
        self.assertFalse(ok_none)
        self.assertFalse(os.path.exists(ass_none))

    def test_explicit_word_timestamps_preservation(self):
        """When segment provides explicit word timings, centisecond allocation uses them."""
        segments = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "SATU DUA",
                "words": [
                    {"word": "SATU", "start": 0.0, "end": 0.5},
                    {"word": "DUA", "start": 0.5, "end": 2.0},
                ],
            }
        ]
        cues = build_validated_cues(segments, clip_start=0.0, clip_end=2.0)
        self.assertEqual(len(cues), 1)
        words_info = cues[0]["words"]
        self.assertEqual(len(words_info), 2)
        # SATU was 0.5s (25% of 2s), DUA was 1.5s (75% of 2s)
        self.assertEqual(words_info[0]["duration_cs"], 50)
        self.assertEqual(words_info[1]["duration_cs"], 150)


if __name__ == "__main__":
    unittest.main()
