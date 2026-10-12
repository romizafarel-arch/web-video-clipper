import hashlib
import json
import math
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import web_app
from shorts_generator.job_manager import (
    JobCancelledException,
    JobContext,
    JobStatus,
    JobTimeoutException,
    job_manager,
)
from shorts_generator.local.gemini_transcriber import (
    _parse_offset,
    _words_to_segments,
    _save_prevalidation_diagnostic,
    transcribe_with_gemini,
)
from shorts_generator.local.transcriber import (
    _validate_transcript_contract,
    _validate_transcript_contract_detailed,
    _write_transcript_cache,
    _transcript_cache_paths,
    transcribe_local,
)


class MockWordInfo:
    def __init__(self, word: str, start_offset: any, end_offset: any, speaker: str = ""):
        self.word = word
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.speaker_label = speaker


class TestV2TranscriptRegression(unittest.TestCase):
    """Regression test suite for Video 2 timestamp adapter and transcript contract."""

    def test_normal_pause_with_valid_timestamps(self):
        """A normal speech pause (>1.2s) should cleanly separate segments without leaking."""
        words = [
            MockWordInfo("Halo", "0.0s", "0.5s"),
            MockWordInfo("teman", "0.6s", "1.0s"),
            MockWordInfo("semua.", "1.1s", "1.5s"),
            # 2.5s pause here (4.0 - 1.5 = 2.5s > 1.2s)
            MockWordInfo("Nama", "4.0s", "4.4s"),
            MockWordInfo("saya", "4.5s", "4.8s"),
            MockWordInfo("Once.", "4.9s", "5.4s"),
        ]
        segs = _words_to_segments(words)
        self.assertEqual(len(segs), 2)

        # First segment should only contain words before the pause
        self.assertEqual(segs[0]["text"], "Halo teman semua.")
        self.assertEqual(segs[0]["start"], 0.0)
        self.assertEqual(segs[0]["end"], 1.5)
        self.assertLessEqual(segs[0]["start"], segs[0]["end"])

        # Second segment should begin with words after the pause
        self.assertEqual(segs[1]["text"], "Nama saya Once.")
        self.assertEqual(segs[1]["start"], 4.0)
        self.assertEqual(segs[1]["end"], 5.4)
        self.assertLessEqual(segs[1]["start"], segs[1]["end"])

    def test_missing_end_offset_raises_error(self):
        """Missing end_offset (None or empty string) must be rejected with targeted diagnostics."""
        words_none = [
            MockWordInfo("Halo", "0.0s", "0.5s"),
            MockWordInfo("kawan", "0.6s", None),
        ]
        with self.assertRaises(ValueError) as ctx_none:
            _words_to_segments(words_none)
        self.assertIn("Word 1 ('kawan') missing end_offset", str(ctx_none.exception))
        self.assertIn("raw value is None", str(ctx_none.exception))

        words_empty = [
            MockWordInfo("Halo", "0.0s", "0.5s"),
            MockWordInfo("kawan", "0.6s", "  "),
        ]
        with self.assertRaises(ValueError) as ctx_empty:
            _words_to_segments(words_empty)
        self.assertIn("Word 1 ('kawan') invalid end_offset", str(ctx_empty.exception))

    def test_missing_start_offset_raises_error(self):
        """Missing start_offset must be rejected with targeted diagnostics."""
        words = [
            MockWordInfo("Halo", None, "0.5s"),
        ]
        with self.assertRaises(ValueError) as ctx:
            _words_to_segments(words)
        self.assertIn("Word 0 ('Halo') missing start_offset", str(ctx.exception))

    def test_nan_infinity_negative_offsets_rejected(self):
        """NaN, Infinity, and negative values must be rejected."""
        # NaN
        with self.assertRaises(ValueError) as ctx_nan:
            _parse_offset("nan", "start_offset", 0, "test")
        self.assertIn("non-finite", str(ctx_nan.exception))

        # Infinity
        with self.assertRaises(ValueError) as ctx_inf:
            _parse_offset("inf", "end_offset", 0, "test")
        self.assertIn("non-finite", str(ctx_inf.exception))

        # Negative
        with self.assertRaises(ValueError) as ctx_neg:
            _parse_offset("-1.5s", "start_offset", 0, "test")
        self.assertIn("negative", str(ctx_neg.exception))

    def test_inverted_word_range_rejected(self):
        """A word with end_offset < start_offset must be rejected immediately."""
        words = [
            MockWordInfo("Halo", "2.0s", "1.0s"),
        ]
        with self.assertRaises(ValueError) as ctx:
            _words_to_segments(words)
        self.assertIn("has inverted time range", str(ctx.exception))
        self.assertIn("end_offset (1.0) < start_offset (2.0)", str(ctx.exception))

    def test_multi_speaker_overlapping_words_handled_cleanly(self):
        """In multi-speaker audio, when an overlapping word starts earlier than previous words,
        preceding words are flushed into a valid segment, and segments are chronologically sorted.
        """
        words = [
            MockWordInfo("Pertama", "5.0s", "5.5s"),
            MockWordInfo("Kedua", "4.0s", "4.5s"),  # Overlapping turn from other speaker
        ]
        segs = _words_to_segments(words)
        self.assertEqual(len(segs), 2)
        # Should be sorted chronologically by start
        self.assertEqual(segs[0]["text"], "Kedua")
        self.assertEqual(segs[0]["start"], 4.0)
        self.assertEqual(segs[0]["end"], 4.5)
        self.assertLessEqual(segs[0]["start"], segs[0]["end"])

        self.assertEqual(segs[1]["text"], "Pertama")
        self.assertEqual(segs[1]["start"], 5.0)
        self.assertEqual(segs[1]["end"], 5.5)
        self.assertLessEqual(segs[1]["start"], segs[1]["end"])

    def test_real_podcast_diagnostic_payload_validates_100_percent(self):
        """Verify the 1015-word real podcast diagnostic payload produces 100% valid contract."""
        diag_path = Path("output_val_v2/20260929_125137_val_v2_pod_verify_61097/diagnostic_transcript_pre_validation_val_v2_pod_verify_61097.json")
        if not diag_path.exists():
            self.skipTest("Diagnostic file not found")
        data = json.loads(diag_path.read_text(encoding="utf-8"))
        raw_words = [
            MockWordInfo(w.get("word"), w.get("start_offset"), w.get("end_offset"))
            for w in data.get("raw_words", [])
        ]
        self.assertEqual(len(raw_words), 1015)
        segs = _words_to_segments(raw_words)
        self.assertGreater(len(segs), 100)

        # Full contract check
        transcript_doc = {
            "duration": 484.0,
            "segments": segs,
            "language": "id",
        }
        ok, reason = _validate_transcript_contract_detailed(transcript_doc)
        self.assertTrue(ok, f"Contract validation failed: {reason}")
        self.assertIsNone(reason)
        self.assertTrue(_validate_transcript_contract(transcript_doc))

    def test_interval_coverage_with_longer_prior_end(self):
        """Segment bounds must cover the full interval (max end) even if earlier word ended later."""
        # Word 1 ends at 11.8s, Word 2 ends at 11.0s (e.g. overlap or short syllable)
        words = [
            MockWordInfo("Pertama", "10.0s", "11.8s"),
            MockWordInfo("dan", "10.5s", "10.8s"),
            MockWordInfo("kedua.", "10.9s", "11.0s"),
        ]
        segs = _words_to_segments(words)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["start"], 10.0)
        # End must be 11.8s (not 11.0s!), covering the full spoken interval
        self.assertEqual(segs[0]["end"], 11.8)
        self.assertLessEqual(segs[0]["start"], segs[0]["end"])

    def test_validate_transcript_contract_detailed(self):
        """_validate_transcript_contract_detailed must report precise field and index on errors."""
        valid_doc = {
            "duration": 10.0,
            "segments": [
                {"start": 0.0, "end": 4.5, "text": "Valid segment 1"},
                {"start": 4.5, "end": 9.8, "text": "Valid segment 2"},
            ]
        }
        ok, reason = _validate_transcript_contract_detailed(valid_doc)
        self.assertTrue(ok)
        self.assertIsNone(reason)
        self.assertTrue(_validate_transcript_contract(valid_doc))

        # Inverted segment
        invalid_doc = {
            "duration": 10.0,
            "segments": [
                {"start": 5.0, "end": 2.0, "text": "Inverted"},
            ]
        }
        ok, reason = _validate_transcript_contract_detailed(invalid_doc)
        self.assertFalse(ok)
        self.assertIn("segment 0 has invalid end", reason)
        self.assertIn("must be finite float >= start", reason)
        self.assertFalse(_validate_transcript_contract(invalid_doc))

    def test_cache_rejection_before_publication(self):
        """_write_transcript_cache must reject invalid transcript before writing to disk."""
        invalid_doc = {
            "duration": 10.0,
            "segments": [
                {"start": 8.0, "end": 4.0, "text": "Broken segment"},
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            _write_transcript_cache("mock_media.mp4", invalid_doc, "gemini", "gemini-3.5-transcribe", "id")
        self.assertIn("Invalid transcript contract", str(ctx.exception))
        self.assertIn("segment 0 has invalid end", str(ctx.exception))

    def test_save_prevalidation_diagnostic_artifact(self):
        """_save_prevalidation_diagnostic must save raw words & segments without credentials."""
        temp_dir = tempfile.mkdtemp()
        try:
            from shorts_generator import config as cfg
            orig_output = cfg.LOCAL_OUTPUT_DIR
            cfg.LOCAL_OUTPUT_DIR = temp_dir

            raw_words = [
                {"word": "Halo", "start_offset": "0.1s", "end_offset": "0.5s", "speaker": "A"},
                {"word": "Dunia", "start_offset": "0.6s", "end_offset": "1.0s", "speaker": "B"},
            ]
            segments = [
                {"start": 0.1, "end": 1.0, "text": "Halo Dunia"},
            ]
            mock_ctx = SimpleNamespace(
                job_id="test_diag_job",
                session_folder="test_session",
            )

            diag_p = _save_prevalidation_diagnostic(
                media_path=None,
                model_name="gemini-3.5-transcribe",
                language="id",
                raw_words=raw_words,
                segments=segments,
                job_ctx=mock_ctx,
            )

            self.assertIsNotNone(diag_p)
            self.assertTrue(diag_p.exists())

            content = json.loads(diag_p.read_text(encoding="utf-8"))
            self.assertEqual(content["job_id"], "test_diag_job")
            self.assertEqual(content["model"], "gemini-3.5-transcribe")
            self.assertEqual(content["raw_words_count"], 2)
            self.assertEqual(content["segments_count"], 1)
            # Ensure no credentials
            content_str = json.dumps(content)
            self.assertNotIn("api_key", content_str.lower())
            self.assertNotIn("secret", content_str.lower())
        finally:
            cfg.LOCAL_OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_short_word_range_not_extended_fictitiously(self):
        """Word with short duration (10.00s - 10.02s) must NOT be extended to 10.10s."""
        words = [
            MockWordInfo("Singkat", "10.00s", "10.02s"),
        ]
        segs = _words_to_segments(words)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["start"], 10.0)
        self.assertEqual(segs[0]["end"], 10.02)

    def test_zero_interval_word_policy(self):
        """Zero-interval word (10.0s - 10.0s) is accepted without fictitious extension and without dropping."""
        words = [
            MockWordInfo("Nol", "10.0s", "10.0s"),
        ]
        segs = _words_to_segments(words)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["start"], 10.0)
        self.assertEqual(segs[0]["end"], 10.0)
        self.assertEqual(segs[0]["text"], "Nol")

        # Must be valid under transcript contract (end >= start is satisfied: 10.0 >= 10.0)
        doc = {"duration": 15.0, "segments": segs, "language": "id"}
        ok, reason = _validate_transcript_contract_detailed(doc)
        self.assertTrue(ok, f"Zero interval segment failed contract: {reason}")

    def test_boolean_offset_rejected(self):
        """Boolean True/False must not be accepted as numeric offset."""
        with self.assertRaises(ValueError) as ctx_true:
            _parse_offset(True, "start_offset", 0, "test")
        self.assertIn("boolean type not allowed", str(ctx_true.exception))

        with self.assertRaises(ValueError) as ctx_false:
            _parse_offset(False, "end_offset", 0, "test")
        self.assertIn("boolean type not allowed", str(ctx_false.exception))

    def test_segment_86_sanitized_fixture(self):
        """Sanitized fixture for Segmen 86 runs cleanly from repo root without depending on output_val_v2."""
        fixture_path = Path("tests/fixtures/segment_86_sanitized.json")
        self.assertTrue(fixture_path.exists(), "Sanitized fixture tests/fixtures/segment_86_sanitized.json must exist")
        fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
        words = [
            MockWordInfo(w["word"], w["start_offset"], w["end_offset"])
            for w in fixture_data
        ]
        segs = _words_to_segments(words)
        self.assertGreater(len(segs), 1)
        for s in segs:
            self.assertLessEqual(s["start"], s["end"])
        doc = {"duration": 350.0, "segments": segs, "language": "id"}
        ok, reason = _validate_transcript_contract_detailed(doc)
        self.assertTrue(ok, f"Segment 86 fixture failed contract: {reason}")

    def test_streaming_hash_diagnostic_matches_direct_hash(self):
        """_save_prevalidation_diagnostic streaming SHA256 must match hashlib.sha256 exactly."""
        temp_dir = tempfile.mkdtemp()
        try:
            from shorts_generator import config as cfg
            orig_output = cfg.LOCAL_OUTPUT_DIR
            cfg.LOCAL_OUTPUT_DIR = temp_dir

            test_media = Path(temp_dir) / "dummy_video.mp4"
            test_content = b"TEST_VIDEO_BYTES_STREAMING_HASH_CHECK" * 1000
            test_media.write_bytes(test_content)
            expected_hash = hashlib.sha256(test_content).hexdigest()

            mock_ctx = SimpleNamespace(job_id="hash_test_job", session_folder="hash_session")
            diag_p = _save_prevalidation_diagnostic(
                media_path=str(test_media),
                model_name="gemini-3.5-transcribe",
                language="id",
                raw_words=[],
                segments=[],
                job_ctx=mock_ctx,
            )
            self.assertIsNotNone(diag_p)
            content = json.loads(diag_p.read_text(encoding="utf-8"))
            self.assertEqual(content["source_sha256"], expected_hash)
        finally:
            cfg.LOCAL_OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_diagnostic_hashing_cancellation_propagates_and_no_file_written(self):
        """JobCancelledException raised during diagnostic hashing must propagate and not write file."""
        temp_dir = tempfile.mkdtemp()
        try:
            from shorts_generator import config as cfg
            orig_output = cfg.LOCAL_OUTPUT_DIR
            cfg.LOCAL_OUTPUT_DIR = temp_dir

            test_media = Path(temp_dir) / "dummy_video.mp4"
            test_media.write_bytes(b"DATA" * 50000)

            mock_ctx = MagicMock()
            mock_ctx.job_id = "cancel_diag_job"
            mock_ctx.session_folder = "cancel_session"
            mock_ctx.check_cancellation_or_timeout.side_effect = JobCancelledException("Pekerjaan dibatalkan pengguna.")

            with self.assertRaises(JobCancelledException) as ctx:
                _save_prevalidation_diagnostic(
                    media_path=str(test_media),
                    model_name="gemini-3.5-transcribe",
                    language="id",
                    raw_words=[],
                    segments=[],
                    job_ctx=mock_ctx,
                )
            self.assertIn("Pekerjaan dibatalkan", str(ctx.exception))

            diag_file = Path(temp_dir) / "cancel_session" / f"diagnostic_transcript_pre_validation_{mock_ctx.job_id}.json"
            self.assertFalse(diag_file.exists(), "Diagnostic artifact must not be written if cancelled during hashing")
        finally:
            cfg.LOCAL_OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_diagnostic_hashing_timeout_propagates_and_no_file_written(self):
        """JobTimeoutException raised during diagnostic hashing must propagate and not write file."""
        temp_dir = tempfile.mkdtemp()
        try:
            from shorts_generator import config as cfg
            orig_output = cfg.LOCAL_OUTPUT_DIR
            cfg.LOCAL_OUTPUT_DIR = temp_dir

            test_media = Path(temp_dir) / "dummy_video.mp4"
            test_media.write_bytes(b"DATA" * 50000)

            mock_ctx = MagicMock()
            mock_ctx.job_id = "timeout_diag_job"
            mock_ctx.session_folder = "timeout_session"
            mock_ctx.check_cancellation_or_timeout.side_effect = JobTimeoutException("Batas waktu terlampaui.")

            with self.assertRaises(JobTimeoutException) as ctx:
                _save_prevalidation_diagnostic(
                    media_path=str(test_media),
                    model_name="gemini-3.5-transcribe",
                    language="id",
                    raw_words=[],
                    segments=[],
                    job_ctx=mock_ctx,
                )
            self.assertIn("Batas waktu terlampaui", str(ctx.exception))

            diag_file = Path(temp_dir) / "timeout_session" / f"diagnostic_transcript_pre_validation_{mock_ctx.job_id}.json"
            self.assertFalse(diag_file.exists(), "Diagnostic artifact must not be written if timed out during hashing")
        finally:
            cfg.LOCAL_OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("google.genai.Client")
    @patch("shorts_generator.local.gemini_transcriber._extract_audio_compressed")
    @patch("shorts_generator.local.gemini_transcriber._get_duration")
    def test_transcribe_with_gemini_cancellation_during_hashing_cleans_file_and_no_fallback(
        self, mock_get_dur, mock_extract, mock_client_cls
    ):
        """Cancellation during diagnostic hashing must propagate, clean remote file, and not fallback."""
        temp_dir = tempfile.mkdtemp()
        try:
            from shorts_generator import config as cfg
            orig_output = cfg.LOCAL_OUTPUT_DIR
            cfg.LOCAL_OUTPUT_DIR = temp_dir

            test_media = Path(temp_dir) / "test_video.mp4"
            test_media.write_bytes(b"VIDEO_PAYLOAD" * 10000)
            dummy_audio = Path(temp_dir) / "test_audio.mp3"
            dummy_audio.write_bytes(b"AUDIO_PAYLOAD")

            mock_get_dur.return_value = 10.0
            mock_extract.return_value = dummy_audio

            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            uploaded_file = MagicMock()
            uploaded_file.name = "files/test_cancel_clean_123"
            uploaded_file.state = "ACTIVE"
            mock_client.files.upload.return_value = uploaded_file

            mock_candidate = MagicMock()
            mock_part = MagicMock()
            mock_trans = MagicMock()
            mock_trans.words = [
                MockWordInfo("Halo", "0.0s", "1.0s"),
                MockWordInfo("sahabat.", "1.1s", "2.0s"),
            ]
            mock_part.audio_transcription = mock_trans
            mock_candidate.content = MagicMock(parts=[mock_part])
            mock_response = MagicMock(candidates=[mock_candidate], text="Halo sahabat.")

            in_hashing = [False]
            def on_generate(*args, **kwargs):
                in_hashing[0] = True
                return mock_response

            mock_client.models.generate_content.side_effect = on_generate

            mock_job_ctx = MagicMock()
            mock_job_ctx.job_id = "test_cancel_hash_job"
            mock_job_ctx.session_folder = "test_cancel_hash_session"
            def check_cancel_hook():
                if in_hashing[0]:
                    raise JobCancelledException("Pekerjaan dibatalkan saat hashing diagnostik.")
            mock_job_ctx.check_cancellation_or_timeout.side_effect = check_cancel_hook

            with self.assertRaises(JobCancelledException) as ctx:
                transcribe_with_gemini(
                    str(test_media),
                    language="id",
                    model="gemini-3.5-transcribe",
                    api_key="mock_key",
                    job_ctx=mock_job_ctx,
                )
            self.assertIn("Pekerjaan dibatalkan saat hashing diagnostik", str(ctx.exception))

            # Verify generate_content was called ONLY once (no fallback)
            self.assertEqual(mock_client.models.generate_content.call_count, 1)
            first_call_args = mock_client.models.generate_content.call_args[1]
            self.assertEqual(first_call_args.get("model"), "gemini-3.5-transcribe")

            # Verify File API cleanup was executed in finally
            mock_client.files.delete.assert_called_once_with(name="files/test_cancel_clean_123")

            # Verify diagnostic file was NOT written
            diag_file = Path(temp_dir) / "test_cancel_hash_session" / f"diagnostic_transcript_pre_validation_{mock_job_ctx.job_id}.json"
            self.assertFalse(diag_file.exists(), "Diagnostic artifact must not be written if cancelled during hashing")
        finally:
            cfg.LOCAL_OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("google.genai.Client")
    @patch("shorts_generator.local.gemini_transcriber._extract_audio_compressed")
    @patch("shorts_generator.local.gemini_transcriber._get_duration")
    def test_transcribe_with_gemini_timeout_during_hashing_cleans_file_and_no_fallback(
        self, mock_get_dur, mock_extract, mock_client_cls
    ):
        """Timeout during diagnostic hashing must propagate, clean remote file, and not fallback."""
        temp_dir = tempfile.mkdtemp()
        try:
            from shorts_generator import config as cfg
            orig_output = cfg.LOCAL_OUTPUT_DIR
            cfg.LOCAL_OUTPUT_DIR = temp_dir

            test_media = Path(temp_dir) / "test_video.mp4"
            test_media.write_bytes(b"VIDEO_PAYLOAD" * 10000)
            dummy_audio = Path(temp_dir) / "test_audio.mp3"
            dummy_audio.write_bytes(b"AUDIO_PAYLOAD")

            mock_get_dur.return_value = 10.0
            mock_extract.return_value = dummy_audio

            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            uploaded_file = MagicMock()
            uploaded_file.name = "files/test_timeout_clean_123"
            uploaded_file.state = "ACTIVE"
            mock_client.files.upload.return_value = uploaded_file

            mock_candidate = MagicMock()
            mock_part = MagicMock()
            mock_trans = MagicMock()
            mock_trans.words = [
                MockWordInfo("Halo", "0.0s", "1.0s"),
                MockWordInfo("sahabat.", "1.1s", "2.0s"),
            ]
            mock_part.audio_transcription = mock_trans
            mock_candidate.content = MagicMock(parts=[mock_part])
            mock_response = MagicMock(candidates=[mock_candidate], text="Halo sahabat.")

            in_hashing = [False]
            def on_generate(*args, **kwargs):
                in_hashing[0] = True
                return mock_response

            mock_client.models.generate_content.side_effect = on_generate

            mock_job_ctx = MagicMock()
            mock_job_ctx.job_id = "test_timeout_hash_job"
            mock_job_ctx.session_folder = "test_timeout_hash_session"
            def check_timeout_hook():
                if in_hashing[0]:
                    raise JobTimeoutException("Batas waktu terlampaui saat hashing diagnostik.")
            mock_job_ctx.check_cancellation_or_timeout.side_effect = check_timeout_hook

            with self.assertRaises(JobTimeoutException) as ctx:
                transcribe_with_gemini(
                    str(test_media),
                    language="id",
                    model="gemini-3.5-transcribe",
                    api_key="mock_key",
                    job_ctx=mock_job_ctx,
                )
            self.assertIn("Batas waktu terlampaui saat hashing diagnostik", str(ctx.exception))

            # Verify generate_content was called ONLY once (no fallback)
            self.assertEqual(mock_client.models.generate_content.call_count, 1)

            # Verify File API cleanup was executed in finally
            mock_client.files.delete.assert_called_once_with(name="files/test_timeout_clean_123")

            # Verify diagnostic file was NOT written
            diag_file = Path(temp_dir) / "test_timeout_hash_session" / f"diagnostic_transcript_pre_validation_{mock_job_ctx.job_id}.json"
            self.assertFalse(diag_file.exists(), "Diagnostic artifact must not be written if timed out during hashing")
        finally:
            cfg.LOCAL_OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("shorts_generator.local.gemini_transcriber.transcribe_with_gemini")
    def test_transcribe_local_cancellation_during_hashing_preserves_old_cache_and_no_new_cache(
        self, mock_transcribe_gemini
    ):
        """transcribe_local cancelled during transcription propagates exception and preserves existing cache."""
        temp_dir = tempfile.mkdtemp()
        try:
            from shorts_generator import config as cfg
            orig_output = cfg.LOCAL_OUTPUT_DIR
            cfg.LOCAL_OUTPUT_DIR = temp_dir

            test_media = Path(temp_dir) / "test_media.mp4"
            test_media.write_bytes(b"MEDIA_DATA" * 500)

            # Pre-populate an old valid cache
            old_transcript = {
                "duration": 10.0,
                "segments": [{"start": 0.0, "end": 2.0, "text": "Old cache segment."}],
            }
            json_path, srt_path = _transcript_cache_paths(str(test_media), "gemini", "gemini-3.5-transcribe", "id")
            _write_transcript_cache(str(test_media), old_transcript, "gemini", "gemini-3.5-transcribe", "id")
            old_json_content = json_path.read_text(encoding="utf-8")
            old_srt_content = srt_path.read_text(encoding="utf-8")

            mock_job_ctx = MagicMock()
            mock_transcribe_gemini.side_effect = JobCancelledException("Pekerjaan dibatalkan saat hashing.")

            with self.assertRaises(JobCancelledException):
                transcribe_local(
                    str(test_media),
                    language="id",
                    provider="gemini",
                    model="gemini-3.5-transcribe",
                    force_refresh=True,
                    config={"gemini_api_key": "mock_key"},
                    job_ctx=mock_job_ctx,
                )

            # Old cache must be preserved exactly
            self.assertTrue(json_path.exists())
            self.assertTrue(srt_path.exists())
            self.assertEqual(json_path.read_text(encoding="utf-8"), old_json_content)
            self.assertEqual(srt_path.read_text(encoding="utf-8"), old_srt_content)
        finally:
            cfg.LOCAL_OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_worker_lifecycle_cancellation_during_hashing_sets_canceled_status(self):
        """Worker executing job cancelled during transcription sets CANCELED status in memory and disk."""
        temp_dir = tempfile.mkdtemp(prefix="test_worker_cancel_")
        try:
            orig_output = web_app.OUTPUT_DIR
            web_app.OUTPUT_DIR = Path(temp_dir)

            with job_manager._admission_lock:
                job_manager._jobs.clear()
            web_app.jobs.clear()

            job_id = "test_cancel_worker_job"
            with job_manager._admission_lock:
                job_ctx = job_manager.admit_job(
                    job_id=job_id,
                    url="https://youtu.be/sample",
                    params={"url": "https://youtu.be/sample", "num_clips": 1},
                )
                web_app.jobs[job_id] = job_ctx.to_dict()

            with patch("web_app.generate_shorts", side_effect=JobCancelledException("Dibatalkan saat hashing")):
                web_app.run_generation_job(job_id, job_ctx.params)

            # In-memory status check
            mem_job = job_manager.get_job(job_id)
            self.assertEqual(mem_job.status, JobStatus.CANCELED)
            self.assertEqual(mem_job.stage, "canceled")

            # Disk metadata check
            meta_file = Path(temp_dir) / job_ctx.session_folder / f"job_{job_id}.json"
            self.assertTrue(meta_file.exists(), f"Metadata file {meta_file} must exist on disk")
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(meta_data.get("status"), JobStatus.CANCELED)
            self.assertEqual(meta_data.get("stage"), "canceled")
        finally:
            with job_manager._admission_lock:
                job_manager._jobs.clear()
            web_app.jobs.clear()
            web_app.OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_worker_lifecycle_timeout_during_hashing_sets_timeout_status(self):
        """Worker executing job timed out during transcription sets TIMEOUT status in memory and disk."""
        temp_dir = tempfile.mkdtemp(prefix="test_worker_timeout_")
        try:
            orig_output = web_app.OUTPUT_DIR
            web_app.OUTPUT_DIR = Path(temp_dir)

            with job_manager._admission_lock:
                job_manager._jobs.clear()
            web_app.jobs.clear()

            job_id = "test_timeout_worker_job"
            with job_manager._admission_lock:
                job_ctx = job_manager.admit_job(
                    job_id=job_id,
                    url="https://youtu.be/sample",
                    params={"url": "https://youtu.be/sample", "num_clips": 1},
                )
                web_app.jobs[job_id] = job_ctx.to_dict()

            with patch("web_app.generate_shorts", side_effect=JobTimeoutException("Batas waktu terlampaui saat hashing")):
                web_app.run_generation_job(job_id, job_ctx.params)

            # In-memory status check
            mem_job = job_manager.get_job(job_id)
            self.assertEqual(mem_job.status, JobStatus.TIMEOUT)
            self.assertEqual(mem_job.stage, "timeout")

            # Disk metadata check
            meta_file = Path(temp_dir) / job_ctx.session_folder / f"job_{job_id}.json"
            self.assertTrue(meta_file.exists(), f"Metadata file {meta_file} must exist on disk")
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(meta_data.get("status"), JobStatus.TIMEOUT)
            self.assertEqual(meta_data.get("stage"), "timeout")
        finally:
            with job_manager._admission_lock:
                job_manager._jobs.clear()
            web_app.jobs.clear()
            web_app.OUTPUT_DIR = orig_output
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
