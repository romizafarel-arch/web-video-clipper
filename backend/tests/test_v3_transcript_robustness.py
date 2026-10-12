import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from shorts_generator.local.gemini_transcriber import (
    _parse_offset,
    _words_to_segments,
    _sanitize_and_recover_word_timestamps,
    _calculate_union_span_duration,
    SANITIZER_POLICY_VERSION,
)
from shorts_generator.local.transcriber import (
    _validate_transcript_contract_detailed,
    _write_transcript_cache,
    _load_transcript_cache,
    _probe_duration,
    _transcript_cache_paths,
)
from shorts_generator.highlights import (
    chunk_transcript,
    get_highlights,
    _filter_untrusted_highlights,
)


class WordInfoMock:
    def __init__(self, word: str, start_offset: str, end_offset: str):
        self.word = word
        self.start_offset = start_offset
        self.end_offset = end_offset


class TestV3TranscriptRobustness(unittest.TestCase):
    def test_01_valid_data_preserved_unchanged(self):
        """Clean valid words should remain untouched with 0 recoveries and 0 untrusted spans."""
        words = [
            {"word": "Halo", "start_offset": "1.0s", "end_offset": "1.5s"},
            {"word": "dunia", "start_offset": "1.5s", "end_offset": "2.0s"},
            {"word": "selamat", "start_offset": "2.2s", "end_offset": "2.8s"},
            {"word": "pagi", "start_offset": "2.8s", "end_offset": "3.5s"},
        ]
        sanitized, untrusted_spans, audit_log = _sanitize_and_recover_word_timestamps(
            words, source_duration=10.0
        )
        self.assertEqual(len(untrusted_spans), 0)
        self.assertEqual(len(audit_log), 0)
        self.assertEqual(len(sanitized), 4)
        for w, orig in zip(sanitized, words):
            self.assertEqual(w["word"], orig["word"])
            self.assertFalse(w.get("estimated", False))
            self.assertFalse(w.get("untrusted", False))

        segs = _words_to_segments(sanitized, untrusted_spans=untrusted_spans, source_duration=10.0)
        self.assertTrue(len(segs) > 0)
        self.assertAlmostEqual(segs[0]["start"], 1.0)
        self.assertAlmostEqual(segs[-1]["end"], 3.5)

    def test_02_rejection_of_invalid_types_and_numbers(self):
        """Type errors (bool, NaN, Inf, negative) must raise ValueError and never be coerced to 0."""
        # Boolean
        with self.assertRaises(ValueError) as ctx:
            _parse_offset(True, "start_offset", 0, "test")
        self.assertIn("boolean", str(ctx.exception))

        # NaN
        with self.assertRaises(ValueError) as ctx:
            _parse_offset(float("nan"), "start_offset", 0, "test")
        self.assertIn("finite", str(ctx.exception))

        # Infinity
        with self.assertRaises(ValueError) as ctx:
            _parse_offset(float("inf"), "end_offset", 0, "test")
        self.assertIn("finite", str(ctx.exception))

        # Negative
        with self.assertRaises(ValueError) as ctx:
            _parse_offset("-1.5s", "start_offset", 0, "test")
        self.assertIn("negative", str(ctx.exception))

    def test_03_local_bounded_recovery_interpolated_and_flagged(self):
        """Small local jitter / inverted pair between stable anchors is interpolated and flagged estimated."""
        # 4 words inside window [10.0, 12.0] (dur = 2.0s, count = 2 bad words, rate = 1.0 w/s <= 5.0)
        words = [
            {"word": "anchor1", "start_offset": "9.0s", "end_offset": "10.0s"},
            {"word": "wordA", "start_offset": "11.5s", "end_offset": "10.5s"},  # inverted
            {"word": "wordB", "start_offset": "11.9s", "end_offset": "10.9s"},  # inverted
            {"word": "anchor2", "start_offset": "12.0s", "end_offset": "13.0s"},
        ]
        sanitized, untrusted_spans, audit = _sanitize_and_recover_word_timestamps(
            words, source_duration=20.0
        )
        self.assertEqual(len(untrusted_spans), 0)
        # wordA and wordB should be recovered
        recovered = [w for w in sanitized if w.get("estimated")]
        self.assertEqual(len(recovered), 2)
        for w in recovered:
            self.assertTrue(w["start"] < w["end"])
            self.assertGreaterEqual(w["start"], 10.0)
            self.assertLessEqual(w["end"], 12.0)

        # Segments contract valid
        segs = _words_to_segments(sanitized, untrusted_spans=untrusted_spans, source_duration=20.0)
        self.assertTrue(len(segs) > 0)
        for s in segs:
            self.assertLessEqual(s["start"], s["end"])

    def test_04_out_of_bounds_and_massive_resets_marked_untrusted_spans(self):
        """Out of bounds endpoints (> duration) and massive temporal jumps become untrusted spans."""
        words = [
            {"word": "awal", "start_offset": "10.0s", "end_offset": "11.0s"},
            {"word": "rusak_oob", "start_offset": "11.2s", "end_offset": "9999.0s"},
            {"word": "rusak_reset", "start_offset": "1.0s", "end_offset": "2.0s"},
            {"word": "normal", "start_offset": "15.0s", "end_offset": "16.0s"},
        ]
        sanitized, untrusted_spans, audit = _sanitize_and_recover_word_timestamps(
            words, source_duration=100.0
        )
        self.assertEqual(len(untrusted_spans), 1)
        span = untrusted_spans[0]
        self.assertAlmostEqual(span["start"], 11.0)
        self.assertAlmostEqual(span["end"], 15.0)
        self.assertEqual(span["word_count"], 2)

        # Segments exclude the untrusted words and do NOT bridge across the gap
        segs = _words_to_segments(sanitized, untrusted_spans=untrusted_spans, source_duration=100.0)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["text"], "awal")
        self.assertEqual(segs[1]["text"], "normal")
        # Ensure no segment crosses [11.0, 15.0]
        for s in segs:
            self.assertFalse(s["start"] < 15.0 and s["end"] > 11.0)

    def test_05_valid_dialogue_overlap_preserved(self):
        """Legitimate overlapping speech between speakers is preserved without flattening start times."""
        # Test A: valid overlap preserved without flattening start time (never max(prev_end, start))
        words_overlap = [
            {"word": "pembicara_satu", "start_offset": "10.0s", "end_offset": "13.0s"},
            {"word": "pembicara_dua", "start_offset": "12.0s", "end_offset": "14.0s"},
        ]
        sanitized_ov, untrusted_ov, _ = _sanitize_and_recover_word_timestamps(
            words_overlap, source_duration=30.0
        )
        self.assertEqual(len(untrusted_ov), 0)
        self.assertFalse(sanitized_ov[0].get("estimated"))
        self.assertFalse(sanitized_ov[1].get("estimated"))
        self.assertAlmostEqual(sanitized_ov[0]["end"], 13.0)
        self.assertAlmostEqual(sanitized_ov[1]["start"], 12.0)  # preserved start, not flattened to 13.0!

        # Test B: backward jump speaker turn cleanly flushes into separate segments
        words_turn = [
            {"word": "pembicara_satu.", "start_offset": "10.0s", "end_offset": "13.0s"},
            {"word": "pembicara_dua.", "start_offset": "9.5s", "end_offset": "12.0s"},
        ]
        sanitized_turn, untrusted_turn, _ = _sanitize_and_recover_word_timestamps(
            words_turn, source_duration=30.0
        )
        segs = _words_to_segments(sanitized_turn, untrusted_spans=untrusted_turn, source_duration=30.0)
        self.assertEqual(len(segs), 2)
        self.assertAlmostEqual(segs[0]["start"], 9.5)
        self.assertAlmostEqual(segs[1]["start"], 10.0)

    def test_06_exact_duplicate_payload_vs_natural_repetition(self):
        """Exact identical payload duplicates are deduplicated, while natural speech repetitions are preserved."""
        # Exact duplicate identical payload
        words_exact_dup = [
            {"word": "halo", "start_offset": "1.0s", "end_offset": "1.5s"},
            {"word": "halo", "start_offset": "1.0s", "end_offset": "1.5s"},  # duplicate
            {"word": "teman", "start_offset": "1.6s", "end_offset": "2.0s"},
        ]
        sanitized, untrusted_spans, audit = _sanitize_and_recover_word_timestamps(
            words_exact_dup, source_duration=10.0
        )
        self.assertEqual(len(sanitized), 2)
        dup_audits = [a for a in audit if a["action"] == "exact_duplicate_payload_dropped"]
        self.assertEqual(len(dup_audits), 1)

        # Natural repetition with progressing timestamps
        words_natural_rep = [
            {"word": "tidak", "start_offset": "1.0s", "end_offset": "1.4s"},
            {"word": "tidak", "start_offset": "1.5s", "end_offset": "1.9s"},
            {"word": "tidak", "start_offset": "2.0s", "end_offset": "2.4s"},
        ]
        sanitized_rep, _, audit_rep = _sanitize_and_recover_word_timestamps(
            words_natural_rep, source_duration=10.0
        )
        self.assertEqual(len(sanitized_rep), 3)
        self.assertEqual(len(audit_rep), 0)

    def test_07_highlight_filtering_of_untrusted_spans(self):
        """Highlight candidates that intersect untrusted spans are strictly discarded."""
        untrusted_spans = [{"start": 100.0, "end": 120.0, "reasons": ["massive_reset"]}]
        highlights = [
            {"title": "Valid Clip A", "start_time": 50.0, "end_time": 90.0, "score": 90},
            {"title": "Corrupt Clip B", "start_time": 95.0, "end_time": 115.0, "score": 95},  # overlaps untrusted
            {"title": "Valid Clip C", "start_time": 130.0, "end_time": 180.0, "score": 85},
        ]
        filtered = _filter_untrusted_highlights(highlights, untrusted_spans)
        self.assertEqual(len(filtered), 2)
        titles = [h["title"] for h in filtered]
        self.assertIn("Valid Clip A", titles)
        self.assertIn("Valid Clip C", titles)
        self.assertNotIn("Corrupt Clip B", titles)

    def test_08_chunk_transcript_propagates_untrusted_spans(self):
        """chunk_transcript must propagate relative untrusted spans to each chunk."""
        transcript = {
            "duration": 2500.0,
            "segments": [
                {"start": 10.0, "end": 20.0, "text": "chunk 1 text"},
                {"start": 1300.0, "end": 1310.0, "text": "chunk 2 text"},
            ],
            "untrusted_spans": [
                {"start": 50.0, "end": 70.0, "word_count": 5},
                {"start": 1350.0, "end": 1380.0, "word_count": 10},
            ],
        }
        chunks = chunk_transcript(transcript)
        self.assertGreater(len(chunks), 1)
        # Chunk 1 (starts at 0s) should include untrusted span at [50, 70]
        c1_spans = chunks[0].get("untrusted_spans", [])
        self.assertTrue(any(s["start"] == 50.0 and s["end"] == 70.0 for s in c1_spans))

        # Chunk 2 (starts around 1140s) should include relative untrusted span for [1350, 1380]
        offset2 = chunks[1]["_offset"]
        c2_spans = chunks[1].get("untrusted_spans", [])
        self.assertTrue(any(s["start"] == 1350.0 - offset2 for s in c2_spans))

    def test_09_cache_serialization_and_validation(self):
        """Cache write and load must serialize untrusted_spans, recovery_audit, and policy_version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_media = Path(tmpdir) / "test_video.mp4"
            dummy_media.write_bytes(b"dummy_video_content")

            transcript = {
                "duration": 60.0,
                "segments": [
                    {"start": 0.0, "end": 10.0, "text": "Halo dunia"},
                    {"start": 20.0, "end": 30.0, "text": "Segmen kedua"},
                ],
                "untrusted_spans": [
                    {"start": 12.0, "end": 18.0, "reasons": ["temporal_reset"]}
                ],
                "recovery_audit": [
                    {"action": "local_bounded_recovery", "word": "dunia", "corrected": [5.0, 6.0]}
                ],
                "policy_version": SANITIZER_POLICY_VERSION,
            }

            # Valid contract test
            is_valid, err = _validate_transcript_contract_detailed(transcript)
            self.assertTrue(is_valid, err)

            # Test write
            from shorts_generator.local import transcriber
            old_output_dir = transcriber.LOCAL_OUTPUT_DIR
            try:
                transcriber.LOCAL_OUTPUT_DIR = tmpdir
                json_p, srt_p = _write_transcript_cache(
                    str(dummy_media), transcript, provider="gemini", model="gemini-3.5-transcribe"
                )
                self.assertTrue(json_p.exists())
                self.assertTrue(srt_p.exists())

                loaded = _load_transcript_cache(
                    str(dummy_media), provider="gemini", model="gemini-3.5-transcribe"
                )
                self.assertIsNotNone(loaded)
                self.assertEqual(len(loaded["untrusted_spans"]), 1)
                self.assertEqual(len(loaded["recovery_audit"]), 1)
                self.assertEqual(loaded["policy_version"], SANITIZER_POLICY_VERSION)

                # Corrupt contract rejection test: segment crossing untrusted span
                bad_transcript = {
                    "duration": 60.0,
                    "segments": [
                        {"start": 10.0, "end": 15.0, "text": "bad segment crossing span"}
                    ],
                    "untrusted_spans": [{"start": 12.0, "end": 18.0}],
                }
                bad_valid, bad_err = _validate_transcript_contract_detailed(bad_transcript)
                self.assertFalse(bad_valid)
                self.assertIn("illegally crosses untrusted span", bad_err)
            finally:
                transcriber.LOCAL_OUTPUT_DIR = old_output_dir

    def test_10_offline_diagnostic_fixture_full_replay(self):
        """Full offline replay of the 5,851-word fixture from Video 3 cold run."""
        fixture_path = Path("output_val_v3/20260929_160722_val_v3_long_72842/diagnostic_transcript_pre_validation_val_v3_long_72842.json")
        if not fixture_path.exists():
            self.skipTest(f"Fixture {fixture_path} not found")

        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        raw_words = data.get("raw_words", [])
        self.assertEqual(len(raw_words), 5851)
        source_dur = 2630.658322

        sanitized, untrusted_spans, audit = _sanitize_and_recover_word_timestamps(
            raw_words, source_duration=source_dur
        )

        # 1. Exact local bounded cluster recovered (3 words total: hyper arousal hyper in block [1228..1230])
        recovered_words = [a for a in audit if a["action"] == "local_bounded_recovery"]
        self.assertEqual(len(recovered_words), 3)

        # 2. Exactly 5 untrusted spans (including OOB 3030.2s block [4660..4661])
        self.assertEqual(len(untrusted_spans), 5)
        total_untrusted_dur = sum(s["end"] - s["start"] for s in untrusted_spans)
        self.assertAlmostEqual(total_untrusted_dur, 34.1, delta=1.0)
        self.assertLess(total_untrusted_dur / source_dur, 0.05)

        # 3. Exactly 129 words marked untrusted
        untrusted_word_count = sum(s["word_count"] for s in untrusted_spans)
        self.assertEqual(untrusted_word_count, 129)

        # 4. Generate segments
        segments = _words_to_segments(sanitized, untrusted_spans=untrusted_spans, source_duration=source_dur)
        self.assertEqual(len(segments), 713)

        # 5. Contract validation on the resulting transcript
        final_transcript = {
            "duration": source_dur,
            "segments": segments,
            "untrusted_spans": untrusted_spans,
            "recovery_audit": audit,
            "policy_version": SANITIZER_POLICY_VERSION,
        }
        is_valid, err_reason = _validate_transcript_contract_detailed(final_transcript)
        self.assertTrue(is_valid, f"Contract validation failed: {err_reason}")

        # 6. Verify highlight filtering with simulated candidates
        simulated_highlights = [
            {"title": "Valid Intro", "start_time": 60.0, "end_time": 120.0, "score": 90},
            {"title": "Across OOB Reset", "start_time": 1115.0, "end_time": 1135.0, "score": 95},  # overlaps untrusted span 1
            {"title": "Valid Mid", "start_time": 1500.0, "end_time": 1560.0, "score": 88},
        ]
        clean_hl = _filter_untrusted_highlights(simulated_highlights, untrusted_spans)
        self.assertEqual(len(clean_hl), 2)
        self.assertEqual(clean_hl[0]["title"], "Valid Intro")
        self.assertEqual(clean_hl[1]["title"], "Valid Mid")

    def test_11_v3_t01_strict_recovery_eligibility_and_bounds(self):
        """V3-T01: Tighten recovery eligibility.
        - Words with inverted and out-of-bounds must be recognized as OOB and disqualified from recovery.
        - Two trusted word anchors are required for interpolation (0 and EOF cannot substitute).
        - Raw deviation exceeding local window (+-5s) disqualifies recovery.
        """
        # Probe 1: Source 10s; anchor 0-1s & 2-3s; raw word 9999-1.5s (both inverted & OOB)
        words_p1 = [
            {"word": "anchor1", "start_offset": "0.0s", "end_offset": "1.0s"},
            {"word": "corrupt_oob_inv", "start_offset": "9999.0s", "end_offset": "1.5s"},
            {"word": "anchor2", "start_offset": "2.0s", "end_offset": "3.0s"},
        ]
        sanitized_1, untrusted_1, audit_1 = _sanitize_and_recover_word_timestamps(
            words_p1, source_duration=10.0
        )
        self.assertEqual(len(untrusted_1), 1)
        self.assertEqual(untrusted_1[0]["start"], 1.0)
        self.assertEqual(untrusted_1[0]["end"], 2.0)
        self.assertFalse(any(w.get("estimated") for w in sanitized_1))
        self.assertTrue(sanitized_1[1].get("untrusted"))

        # Probe 2: Source 100s; anchor 0-1s & 2-3s; raw word 90-1.5s (within source dur, but raw deviation 90s >> window)
        words_p2 = [
            {"word": "anchor1", "start_offset": "0.0s", "end_offset": "1.0s"},
            {"word": "corrupt_jump_inv", "start_offset": "90.0s", "end_offset": "1.5s"},
            {"word": "anchor2", "start_offset": "2.0s", "end_offset": "3.0s"},
        ]
        sanitized_2, untrusted_2, audit_2 = _sanitize_and_recover_word_timestamps(
            words_p2, source_duration=100.0
        )
        self.assertEqual(len(untrusted_2), 1)
        self.assertEqual(untrusted_2[0]["start"], 1.0)
        self.assertEqual(untrusted_2[0]["end"], 2.0)
        self.assertFalse(any(w.get("estimated") for w in sanitized_2))
        self.assertTrue(sanitized_2[1].get("untrusted"))

        # Probe 3: No left anchor; raw 90-1.5s followed by word 2-3s (time 0 cannot be used as word anchor)
        words_p3 = [
            {"word": "corrupt_head", "start_offset": "90.0s", "end_offset": "1.5s"},
            {"word": "anchor_r", "start_offset": "2.0s", "end_offset": "3.0s"},
        ]
        sanitized_3, untrusted_3, audit_3 = _sanitize_and_recover_word_timestamps(
            words_p3, source_duration=20.0
        )
        self.assertEqual(len(untrusted_3), 1)
        self.assertEqual(untrusted_3[0]["start"], 0.0)
        self.assertEqual(untrusted_3[0]["end"], 2.0)
        self.assertFalse(any(w.get("estimated") for w in sanitized_3))
        self.assertTrue(sanitized_3[0].get("untrusted"))

        # Probe 4: No right anchor; word 18-19s followed by inverted word 19.7-19.3s on 20s media (EOF cannot be word anchor)
        words_p4 = [
            {"word": "anchor_l", "start_offset": "18.0s", "end_offset": "19.0s"},
            {"word": "corrupt_tail", "start_offset": "19.7s", "end_offset": "19.3s"},
        ]
        sanitized_4, untrusted_4, audit_4 = _sanitize_and_recover_word_timestamps(
            words_p4, source_duration=20.0
        )
        self.assertEqual(len(untrusted_4), 1)
        self.assertEqual(untrusted_4[0]["start"], 19.0)
        self.assertEqual(untrusted_4[0]["end"], 20.0)
        self.assertFalse(any(w.get("estimated") for w in sanitized_4))
        self.assertTrue(sanitized_4[1].get("untrusted"))

    def test_12_v3_t02_end_spike_and_suspicious_duration_quarantined(self):
        """V3-T02: Detect non-inverted end spikes and suspicious durations in neighbor context.
        - Spikes must not be used as anchors or merged into huge segments.
        - Legitimate multi-speaker overlaps must be preserved.
        """
        # Reviewer probe: Source 100s, left=10-11s, spike=11.1-99s, right=12-13s
        words_spike = [
            {"word": "left", "start_offset": "10.0s", "end_offset": "11.0s"},
            {"word": "spike", "start_offset": "11.1s", "end_offset": "99.0s"},
            {"word": "right", "start_offset": "12.0s", "end_offset": "13.0s"},
        ]
        sanitized, untrusted_spans, audit = _sanitize_and_recover_word_timestamps(
            words_spike, source_duration=100.0
        )
        self.assertEqual(len(untrusted_spans), 1)
        self.assertEqual(untrusted_spans[0]["start"], 11.0)
        self.assertEqual(untrusted_spans[0]["end"], 12.0)
        self.assertTrue(sanitized[1].get("untrusted"))

        segs = _words_to_segments(sanitized, untrusted_spans=untrusted_spans, source_duration=100.0)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["text"], "left")
        self.assertAlmostEqual(segs[0]["start"], 10.0)
        self.assertAlmostEqual(segs[0]["end"], 11.0)
        self.assertEqual(segs[1]["text"], "right")
        self.assertAlmostEqual(segs[1]["start"], 12.0)
        self.assertAlmostEqual(segs[1]["end"], 13.0)
        # Verify no segment contains 99s or bridges across 11-12s
        for s in segs:
            self.assertLessEqual(s["end"], 13.0)

        # Suspicious single-word duration (dur = 15s > 10.5s)
        words_long = [
            {"word": "norm1", "start_offset": "5.0s", "end_offset": "6.0s"},
            {"word": "long_stretched", "start_offset": "6.1s", "end_offset": "21.1s"},  # dur = 15s
            {"word": "norm2", "start_offset": "22.0s", "end_offset": "23.0s"},
        ]
        san_long, un_long, _ = _sanitize_and_recover_word_timestamps(words_long, source_duration=100.0)
        self.assertEqual(len(un_long), 1)
        self.assertTrue(san_long[1].get("untrusted"))

    def test_13_v3_t03_cache_duration_upper_bound_enforcement(self):
        """V3-T03: Enforce media duration limits on transcript cache contracts.
        - Final metadata re-validated before publishing; rejects segment exceeding duration.
        - Invalid cache file on disk unlinked on load; returns None.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            from shorts_generator.local import transcriber
            old_output_dir = transcriber.LOCAL_OUTPUT_DIR
            try:
                transcriber.LOCAL_OUTPUT_DIR = tmpdir
                dummy_video = Path(tmpdir) / "video_10s.mp4"
                dummy_video.write_bytes(b"dummy")
                cached_json, cached_srt = _transcript_cache_paths(
                    str(dummy_video), provider="gemini", model="gemini-3.5-transcribe"
                )

                # 1. Reject publishing invalid transcript exceeding duration (10s source, segment ends at 90s)
                invalid_transcript = {
                    "duration": 10.0,
                    "segments": [
                        {"start": 0.0, "end": 1.0, "text": "start"},
                        {"start": 9.0, "end": 90.0, "text": "overshoot"},
                    ],
                }
                with unittest.mock.patch("shorts_generator.local.transcriber._probe_duration", return_value=10.0):
                    with self.assertRaises(ValueError) as ctx:
                        _write_transcript_cache(
                            str(dummy_video), invalid_transcript, provider="gemini", model="gemini-3.5-transcribe"
                        )
                    self.assertIn("exceeds media duration limit", str(ctx.exception))

                    # Verify no cache files were published
                    self.assertFalse(cached_json.exists())
                    self.assertFalse(cached_srt.exists())

                # 2. Reject and unlink invalid cache file on load
                cached_json.write_text(json.dumps({
                    "version": 1,
                    "format": "transcribe_json",
                    "duration": 10.0,
                    "segments": [{"start": 9.0, "end": 90.0, "text": "overshoot"}],
                }), encoding="utf-8")
                cached_srt.write_text("1\n00:00:09,000 --> 00:01:30,000\novershoot\n", encoding="utf-8")

                with unittest.mock.patch("shorts_generator.local.transcriber._probe_duration", return_value=10.0):
                    loaded = _load_transcript_cache(str(dummy_video), provider="gemini", model="gemini-3.5-transcribe")
                    self.assertIsNone(loaded)
                    self.assertFalse(cached_json.exists())
                    self.assertFalse(cached_srt.exists())

                # 3. Valid cache within duration (9.8s <= 10.0s + 0.5s) roundtrips cleanly
                valid_transcript = {
                    "duration": 10.0,
                    "segments": [{"start": 0.0, "end": 9.8, "text": "valid content"}],
                }
                with unittest.mock.patch("shorts_generator.local.transcriber._probe_duration", return_value=10.0):
                    jp, sp = _write_transcript_cache(
                        str(dummy_video), valid_transcript, provider="gemini", model="gemini-3.5-transcribe"
                    )
                    self.assertTrue(jp.exists())
                    loaded_valid = _load_transcript_cache(str(dummy_video), provider="gemini", model="gemini-3.5-transcribe")
                    self.assertIsNotNone(loaded_valid)
                    self.assertEqual(len(loaded_valid["segments"]), 1)
            finally:
                transcriber.LOCAL_OUTPUT_DIR = old_output_dir

    def test_14_v3_t04_anchor_overlap_and_union_gap_coverage(self):
        """V3-T04: Fix quarantine interval contract during anchor overlap and union coverage.
        - Overlapping anchors around defective block raise explicit quality ValueError.
        - Union gap coverage handles overlapping, disjoint, and nested spans correctly without negative durations.
        """
        # Overlapping anchors around corrupt token: left 10-20s, token 15-15.1s, right 16-21s
        # left_end (20s) > right_start (16s) -> cannot determine safe quarantine boundaries
        words_overlap_anchors = [
            {"word": "anchor_left", "start_offset": "10.0s", "end_offset": "20.0s"},
            {"word": "/?corrupt?", "start_offset": "15.0s", "end_offset": "15.1s"},
            {"word": "anchor_right", "start_offset": "16.0s", "end_offset": "21.0s"},
        ]
        with self.assertRaises(ValueError) as ctx:
            _sanitize_and_recover_word_timestamps(words_overlap_anchors, source_duration=30.0)
        self.assertIn("conflicting overlapping anchors", str(ctx.exception))

        # Union duration helper verification
        # 1. Disjoint
        self.assertAlmostEqual(_calculate_union_span_duration([{"start": 10.0, "end": 20.0}, {"start": 30.0, "end": 40.0}]), 20.0)
        # 2. Overlapping (10-25 and 20-35 -> union 10-35 = 25s, NOT 30s)
        self.assertAlmostEqual(_calculate_union_span_duration([{"start": 10.0, "end": 25.0}, {"start": 20.0, "end": 35.0}]), 25.0)
        # 3. Contained (10-30 and 15-20 -> union 10-30 = 20s)
        self.assertAlmostEqual(_calculate_union_span_duration([{"start": 10.0, "end": 30.0}, {"start": 15.0, "end": 20.0}]), 20.0)
        # 4. Inverted/degenerate (ignored, no negative duration)
        self.assertAlmostEqual(_calculate_union_span_duration([{"start": 30.0, "end": 20.0}]), 0.0)
        # 5. Empty
        self.assertAlmostEqual(_calculate_union_span_duration([]), 0.0)


if __name__ == "__main__":
    unittest.main()
