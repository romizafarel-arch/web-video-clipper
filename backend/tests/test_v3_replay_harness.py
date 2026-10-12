"""Targeted Offline Tests for Video 3 Controlled Replay Harness (V3-R01, V3-R02, V3-R03).

Covers:
1. Ranking timeout -> finalization of status, error, metadata, and preservation.
2. Classification timeout -> exactly 1 dispatch, 0 ranking calls.
3. Classification invalid JSON -> exactly 1 dispatch, 0 ranking calls, fail-fast.
4. Classification valid other/medium -> accepted as valid, proceeds to ranking.
5. Clock initialization and budget cap (min(600, remaining - reserve)), dispatch rejection on 0 budget.
6. STT/upload blocked and 5th highlight request rejected.
7. Corrected manifest matches actual fixture sanitizer output.
"""
import copy
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import openai
import shorts_generator.highlights as hl
import shorts_generator.local.gemini_transcriber as gt
from shorts_generator.job_manager import JobContext, JobManager, JobStatus, JobTimeoutException
import scratch.run_controlled_replay_v3 as harness


class TestV3ReplayHarness(unittest.TestCase):
    """Test suite verifying V3-R01, V3-R02, and V3-R03 offline requirements."""

    def setUp(self):
        # Reset counters before each test
        for k in ("transcribe", "highlight"):
            for subk in ("attempted", "dispatched", "success", "failed", "blocked"):
                harness.api_counters[k][subk] = 0
        for k in ("upload", "polling", "delete", "delete_success", "delete_failed"):
            harness.api_counters["file_api"][k] = 0

    def tearDown(self):
        # Clean up active job in global manager
        from shorts_generator.job_manager import job_manager
        with job_manager._admission_lock:
            job_manager._active_job_id = None

    def test_01_ranking_timeout_finalizes_lifecycle_and_preservation(self):
        """V3-R01: Ranking timeout leads to terminal FAILED status, metadata written, preservation checked, and 0 subsequent dispatches."""
        call_count = 0

        def mock_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Classification succeeds
                return json.dumps({"content_type": "interview", "density": "medium"})
            else:
                # Chunk 1 ranking times out
                raise openai.APITimeoutError(request=None)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            job_id = "test_rank_timeout_job"

            meta = harness.execute_controlled_replay(
                override_llm_fn=mock_llm,
                override_session_dir=tmp_path,
                override_job_id=job_id,
                skip_guards_test=True,
            )

            # Assertions
            self.assertEqual(call_count, 2, "Expected exactly 2 LLM calls (1 classification + 1 ranking)")
            self.assertEqual(harness.api_counters["highlight"]["attempted"], 0)  # mock_llm called directly, or if via guarded
            self.assertIn("failed", str(meta["status"]).lower())
            self.assertIn("APITimeoutError", str(meta.get("error")))

            # Check that job metadata file was generated on disk
            meta_file = tmp_path / f"job_{job_id}.json"
            self.assertTrue(meta_file.exists(), "Final metadata file must exist on disk after timeout")

            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertIn("failed", str(meta_data["status"]).lower())
            self.assertTrue(meta_data["preservation"]["intact"])
            self.assertIsNotNone(meta_data["started_at"])
            self.assertIsNotNone(meta_data["ended_at"])

    def test_02_classification_timeout_fails_fast(self):
        """V3-R02: Classification timeout fails fast with exactly 1 dispatch and 0 ranking calls."""
        call_count = 0

        def mock_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            raise openai.APITimeoutError(request=None)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            job_id = "test_cls_timeout_job"

            meta = harness.execute_controlled_replay(
                override_llm_fn=mock_llm,
                override_session_dir=tmp_path,
                override_job_id=job_id,
                skip_guards_test=True,
            )

            self.assertEqual(call_count, 1, "Expected exactly 1 LLM call before aborting")
            self.assertIn("failed", str(meta["status"]).lower())
            self.assertIn("APITimeoutError", str(meta.get("error")))

            meta_file = tmp_path / f"job_{job_id}.json"
            self.assertTrue(meta_file.exists())
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertIn("failed", str(meta_data["status"]).lower())
            self.assertEqual(meta_data["highlight_summary"]["total_raw_candidates"], 0)

    def test_03_classification_invalid_json_fails_fast(self):
        """V3-R02: Non-JSON or broken classification response raises ClassificationContractError and halts before ranking."""
        call_count = 0

        def mock_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            return "I am an AI assistant and cannot determine the content type of this text."

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            job_id = "test_cls_invalid_json_job"

            meta = harness.execute_controlled_replay(
                override_llm_fn=mock_llm,
                override_session_dir=tmp_path,
                override_job_id=job_id,
                skip_guards_test=True,
            )

            self.assertEqual(call_count, 1, "Expected exactly 1 LLM call on invalid JSON classification")
            self.assertIn("failed", str(meta["status"]).lower())
            self.assertIn("ClassificationContractError", str(meta.get("error")))

            meta_file = tmp_path / f"job_{job_id}.json"
            self.assertTrue(meta_file.exists())
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertIn("failed", str(meta_data["status"]).lower())

    def test_03a_classification_non_string_fields_fails_fast(self):
        """V3-R02.a: Classification with non-string fields fails fast with exactly 1 dispatch and 0 ranking calls."""
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({"content_type": {"bad": "value"}, "density": True})
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        with patch.object(harness, "_orig_chat_create", return_value=mock_resp):
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                job_id = "test_cls_non_string_job"

                meta = harness.execute_controlled_replay(
                    override_session_dir=tmp_path,
                    override_job_id=job_id,
                    skip_guards_test=True,
                )

                # Exactly 1 dispatch measured by actual guard counter
                self.assertEqual(harness.api_counters["highlight"]["attempted"], 1, "Expected exactly 1 highlight attempted")
                self.assertEqual(harness.api_counters["highlight"]["dispatched"], 1, "Expected exactly 1 highlight dispatched")
                self.assertEqual(meta["highlight_summary"]["total_raw_candidates"], 0, "Zero ranking calls should be dispatched")
                self.assertEqual(len(meta.get("clips", [])), 0, "Zero render calls should be dispatched")

                # Memory status and disk status failed with ClassificationContractError
                self.assertIn("failed", str(meta["status"]).lower())
                self.assertIn("ClassificationContractError", str(meta.get("error")))
                self.assertIn("content_type", str(meta.get("error")))

                meta_file = tmp_path / f"job_{job_id}.json"
                self.assertTrue(meta_file.exists())
                meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
                self.assertIn("failed", str(meta_data["status"]).lower())
                self.assertIn("ClassificationContractError", str(meta_data.get("error")))
                self.assertTrue(meta_data["preservation"]["intact"])

                # Admission is released
                from shorts_generator.job_manager import job_manager
                self.assertIsNone(job_manager.get_active_job(), "Admission lock must be released")

    def test_03b_classification_invalid_category_density_fails_fast(self):
        """V3-R02.a: Classification with invalid enum values fails fast with exactly 1 dispatch and 0 ranking calls."""
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({"content_type": "invalid_category", "density": "extreme"})
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        with patch.object(harness, "_orig_chat_create", return_value=mock_resp):
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                job_id = "test_cls_invalid_enum_job"

                meta = harness.execute_controlled_replay(
                    override_session_dir=tmp_path,
                    override_job_id=job_id,
                    skip_guards_test=True,
                )

                # Exactly 1 dispatch measured by actual guard counter
                self.assertEqual(harness.api_counters["highlight"]["attempted"], 1, "Expected exactly 1 highlight attempted")
                self.assertEqual(harness.api_counters["highlight"]["dispatched"], 1, "Expected exactly 1 highlight dispatched")
                self.assertEqual(meta["highlight_summary"]["total_raw_candidates"], 0, "Zero ranking calls should be dispatched")
                self.assertEqual(len(meta.get("clips", [])), 0, "Zero render calls should be dispatched")

                # Memory status and disk status failed with ClassificationContractError
                self.assertIn("failed", str(meta["status"]).lower())
                self.assertIn("ClassificationContractError", str(meta.get("error")))
                self.assertIn("invalid_category", str(meta.get("error")))

                meta_file = tmp_path / f"job_{job_id}.json"
                self.assertTrue(meta_file.exists())
                meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
                self.assertIn("failed", str(meta_data["status"]).lower())
                self.assertIn("ClassificationContractError", str(meta_data.get("error")))
                self.assertTrue(meta_data["preservation"]["intact"])

                # Admission is released
                from shorts_generator.job_manager import job_manager
                self.assertIsNone(job_manager.get_active_job(), "Admission lock must be released")

    def test_03c_direct_classification_contract_validation(self):
        """V3-R02.a: Comprehensive contract validation on run_guarded_classification."""
        dummy_transcript = {"segments": [{"text": "Sample text for testing"}]}

        # 1. Non-dictionary root
        for bad_root in ["not json", "123", "[]", "null"]:
            with self.assertRaises(harness.ClassificationContractError):
                harness.run_guarded_classification(dummy_transcript, llm_fn=lambda _: bad_root)

        # 2. Missing fields
        with self.assertRaises(harness.ClassificationContractError):
            harness.run_guarded_classification(dummy_transcript, llm_fn=lambda _: json.dumps({"content_type": "podcast"}))
        with self.assertRaises(harness.ClassificationContractError):
            harness.run_guarded_classification(dummy_transcript, llm_fn=lambda _: json.dumps({"density": "medium"}))

        # 3. Non-string types for content_type or density
        bad_type_cases = [
            {"content_type": {"nested": "dict"}, "density": "medium"},
            {"content_type": ["list"], "density": "medium"},
            {"content_type": 123, "density": "medium"},
            {"content_type": True, "density": "medium"},
            {"content_type": None, "density": "medium"},
            {"content_type": "podcast", "density": {"nested": "dict"}},
            {"content_type": "podcast", "density": ["high"]},
            {"content_type": "podcast", "density": 99},
            {"content_type": "podcast", "density": False},
            {"content_type": "podcast", "density": None},
        ]
        for bad_case in bad_type_cases:
            with self.assertRaises(harness.ClassificationContractError):
                harness.run_guarded_classification(dummy_transcript, llm_fn=lambda _: json.dumps(bad_case))

        # 4. Invalid enum values
        bad_enum_cases = [
            {"content_type": "movie", "density": "medium"},
            {"content_type": "invalid_category", "density": "extreme"},
            {"content_type": "podcast", "density": "super_high"},
            {"content_type": "", "density": "low"},
            {"content_type": "interview", "density": ""},
        ]
        for bad_case in bad_enum_cases:
            with self.assertRaises(harness.ClassificationContractError):
                harness.run_guarded_classification(dummy_transcript, llm_fn=lambda _: json.dumps(bad_case))

        # 5. Valid cases across all allowed types and densities with case/whitespace normalization
        for c in harness.ALLOWED_CONTENT_TYPES:
            for d in harness.ALLOWED_DENSITIES:
                raw_json = json.dumps({"content_type": f"  {c.upper()} \n", "density": f" \t{d.title()} "})
                res = harness.run_guarded_classification(dummy_transcript, llm_fn=lambda _: raw_json)
                self.assertEqual(res["content_type"], c)
                self.assertEqual(res["density"], d)

    def test_04_classification_valid_other_medium_accepted(self):
        """V3-R02 & V3-R02.a: Valid JSON explicitly returning other/medium (with whitespace/casing) is accepted without error."""
        call_count = 0

        def mock_llm(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return json.dumps({"content_type": "  OTHER \n", "density": "  Medium  "})
            else:
                return json.dumps({
                    "highlights": [
                        {
                            "start_time": 10.0,
                            "end_time": 25.0,
                            "title": "Highlight 1",
                            "score": 85,
                            "hook_sentence": "Hook 1",
                            "virality_reason": "Reason 1",
                        }
                    ]
                })

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            job_id = "test_cls_other_medium_job"

            meta = harness.execute_controlled_replay(
                override_llm_fn=mock_llm,
                override_session_dir=tmp_path,
                override_job_id=job_id,
                skip_guards_test=True,
                skip_render=True,
            )

            # Call 1 was classification, then chunk 1, 2, 3 were processed
            self.assertGreaterEqual(call_count, 2, "Should proceed to ranking after valid other/medium classification")
            self.assertEqual(meta["highlight_summary"]["content_type"], "other")
            self.assertEqual(meta["highlight_summary"]["density"], "medium")

    def test_05_clock_initialization_and_budget_cap(self):
        """V3-R01: Clock is initialized, cap 600s is enforced, and zero remaining budget rejects dispatch."""
        test_jm = JobManager()
        ctx = test_jm.admit_job("clock_test_job", url="mock_url", params={}, timeout_seconds=1800.0)

        # Before started_at is set
        self.assertIsNone(ctx.started_at)
        b_default = harness._get_request_budget_sec(cap_seconds=600.0, reserve_seconds=60.0)
        self.assertEqual(b_default, 600.0)

        # Set started_at to now
        now = time.time()
        ctx.started_at = now

        # Case A: 100 seconds elapsed (remaining = 1700s, reserve = 60s -> effective = 1640s > 600s cap)
        with patch.object(harness, "_get_active_job_context", return_value=ctx):
            with patch("time.time", return_value=now + 100.0):
                budget = harness._get_request_budget_sec(cap_seconds=600.0, reserve_seconds=60.0)
                self.assertEqual(budget, 600.0, "Should be capped at 600.0s")

            # Case B: 1500 seconds elapsed (remaining = 300s, reserve = 60s -> effective = 240s < 600s cap)
            with patch("time.time", return_value=now + 1500.0):
                budget = harness._get_request_budget_sec(cap_seconds=600.0, reserve_seconds=60.0)
                self.assertAlmostEqual(budget, 240.0, places=1)

            # Case C: 1750 seconds elapsed (remaining = 50s <= 60s reserve -> effective <= 0)
            with patch("time.time", return_value=now + 1750.0):
                budget = harness._get_request_budget_sec(cap_seconds=600.0, reserve_seconds=60.0)
                self.assertEqual(budget, 0.0, "Budget should be 0.0 when within reserve")

                # Rejection before dispatch
                with self.assertRaises(JobTimeoutException):
                    harness._guarded_chat_create(MagicMock())

    def test_06_stt_and_upload_blocked_and_max_limit_enforced(self):
        """Proof of interceptor blocking guards and 5th highlight rejection."""
        from google import genai
        g_client = genai.Client(api_key="mock_key")

        # 1. STT blocked
        with self.assertRaises(RuntimeError) as cm_stt:
            g_client.models.generate_content(model="gemini-3.5-transcribe", contents="hi")
        self.assertIn("Semua panggilan inferensi Gemini", str(cm_stt.exception))

        # 2. File upload blocked
        with self.assertRaises(RuntimeError) as cm_up:
            g_client.files.upload(file="audio.mp3")
        self.assertIn("Semua panggilan upload Gemini File API DIBLOKIR", str(cm_up.exception))

        # 3. 5th highlight rejected
        harness.api_counters["highlight"]["dispatched"] = 4
        harness.api_counters["highlight"]["max"] = 4
        with self.assertRaises(RuntimeError) as cm_hl:
            harness._guarded_chat_create(MagicMock())
        self.assertIn("Batas inferensi highlight terlampaui", str(cm_hl.exception))

    def test_07_corrected_manifest_matches_actual_sanitizer(self):
        """V3-R03: Verify replay_audit_corrected.json accurately matches the fixture extraction."""
        manifest_p = ROOT_DIR / "output_val_v3/20260929_173758_val_v3_replay_78278/replay_audit_corrected.json"
        self.assertTrue(manifest_p.exists(), f"Corrected manifest must exist at {manifest_p}")

        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))

        # Re-run sanitizer on fixture raw_words
        fix_p = ROOT_DIR / "output_val_v3/20260929_160722_val_v3_long_72842/diagnostic_transcript_pre_validation_val_v3_long_72842.json"
        fix_data = json.loads(fix_p.read_text(encoding="utf-8"))
        raw_words = fix_data["raw_words"]

        sanitized, untrusted_spans, recovery_audit = gt._sanitize_and_recover_word_timestamps(
            raw_words, source_duration=2630.658322
        )
        recovered = [a for a in recovery_audit if a.get("action") == "local_bounded_recovery"]

        # Validate recovered words
        self.assertEqual(len(recovered), 3)
        self.assertEqual([r["index"] for r in recovered], [1228, 1229, 1230])
        self.assertEqual(recovered[0]["corrected"], [512.6, 513.267])
        self.assertEqual(recovered[1]["corrected"], [513.267, 513.933])
        self.assertEqual(recovered[2]["corrected"], [513.933, 514.6])

        # Validate untrusted spans word counts
        word_counts = [sp["word_count"] for sp in untrusted_spans]
        self.assertEqual(word_counts, [57, 6, 2, 48, 16])
        self.assertEqual(sum(word_counts), 129)

        # Validate manifest contents match
        m_rec = manifest["sanitization_audit_extracted"]["recovered_words"]
        self.assertEqual(len(m_rec), 3)
        self.assertEqual([r["raw_index"] for r in m_rec], [1228, 1229, 1230])

        m_spans = manifest["sanitization_audit_extracted"]["untrusted_spans"]
        self.assertEqual([sp["word_count"] for sp in m_spans], [57, 6, 2, 48, 16])

        proof = manifest["sanitization_audit_extracted"]["exclusion_ranges_proof"]
        self.assertTrue(proof["is_fully_covered"])
        self.assertEqual(proof["estimated_recovery_interval_actual"], [512.6, 514.6])
        self.assertEqual(proof["context_exclusion_range_applied"], [512.6, 515.2])


if __name__ == "__main__":
    unittest.main()
