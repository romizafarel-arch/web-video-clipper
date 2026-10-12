"""
Tests for Official OpenAI-Compatible Controlled Replay Harness (Video 3)
========================================================================
Offline verification with mocked SDK transport and blocked network:
  - Configuration resolution (DeepSeek / OpenAI)
  - Parameter propagation (base_url, model, max_retries=0, timeout cap 600s)
  - Shared job budget 1800s decrement and deadline check
  - 0 STT and 0 upload blocking guards
  - 5th highlight request blocking guard
  - Fail-fast on classification failure
  - Fail-fast on ranking failure (e.g. HTTP 503 simulation)
  - Metadata enrichment for official provider
  - O-01: Strict endpoint validation and credential isolation (no generic fallback)
  - O-02: Deprecated model rejection and thinking parameter injection
  - O-03: Dynamic context binding under override_job_manager with deadline cutoff (< 60s reserve)
"""

import sys
import os
import json
import time
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scratch.run_controlled_replay_v3 as v3_harness
import scratch.run_controlled_replay_v3_official as official_harness
from shorts_generator.job_manager import JobManager, JobContext, JobStatus, JobTimeoutException


class TestV3OfficialHarness(unittest.TestCase):
    def setUp(self):
        # Reset counters
        for k in ("transcribe", "highlight"):
            for subk in ("attempted", "dispatched", "success", "failed", "blocked"):
                v3_harness.api_counters[k][subk] = 0
        for k in ("upload", "polling", "delete", "delete_success", "delete_failed"):
            v3_harness.api_counters["file_api"][k] = 0

    def test_01_config_resolution(self):
        """Verify default and overridden configuration resolution for official providers (O-01, O-02)."""
        # DeepSeek defaults: deepseek-flash with thinking disabled
        ds_cfg = official_harness.resolve_official_config("deepseek")
        self.assertEqual(ds_cfg["provider"], "deepseek")
        self.assertEqual(ds_cfg["base_url"], "https://api.deepseek.com")
        self.assertEqual(ds_cfg["model"], "deepseek-flash")
        self.assertEqual(ds_cfg["env_key"], "DEEPSEEK_API_KEY")
        self.assertEqual(ds_cfg["thinking_mode"], "disabled")

        # OpenAI defaults: gpt-4o-mini
        oa_cfg = official_harness.resolve_official_config("openai")
        self.assertEqual(oa_cfg["provider"], "openai")
        self.assertEqual(oa_cfg["base_url"], "https://api.openai.com/v1")
        self.assertEqual(oa_cfg["model"], "gpt-4o-mini")
        self.assertEqual(oa_cfg["env_key"], "OPENAI_OFFICIAL_API_KEY")
        self.assertIsNone(oa_cfg["thinking_mode"])

        # Custom overrides (valid model)
        custom_cfg = official_harness.resolve_official_config(
            provider="deepseek",
            model="deepseek-flash",
            base_url="https://api.deepseek.com",
            api_key="sk-custom-secret",
            thinking_mode="enabled",
        )
        self.assertEqual(custom_cfg["model"], "deepseek-flash")
        self.assertEqual(custom_cfg["base_url"], "https://api.deepseek.com")
        self.assertEqual(custom_cfg["api_key"], "sk-custom-secret")
        self.assertEqual(custom_cfg["thinking_mode"], "enabled")

        # Rejection of deprecated models (O-02)
        with self.assertRaises(ValueError) as ctx_chat:
            official_harness.resolve_official_config(provider="deepseek", model="deepseek-chat")
        self.assertIn("telah dihentikan", str(ctx_chat.exception))

        with self.assertRaises(ValueError) as ctx_reasoner:
            official_harness.resolve_official_config(provider="deepseek", model="deepseek-reasoner")
        self.assertIn("telah dihentikan", str(ctx_reasoner.exception))

        # Invalid provider
        with self.assertRaises(ValueError):
            official_harness.resolve_official_config("unsupported_provider")

    def test_02_llm_callable_and_guards(self):
        """Verify official LLM callable instantiates client with max_retries=0 and extra_body thinking parameter (O-02)."""
        cfg = {
            "provider": "deepseek",
            "name": "DeepSeek API Resmi",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-flash",
            "api_key": "sk-mock-key-12345",
            "thinking_mode": "disabled",
        }
        callable_fn = official_harness.create_official_llm_callable(cfg)

        import openai
        test_client = openai.OpenAI(api_key="sk-test", base_url="https://api.deepseek.com")
        self.assertEqual(getattr(test_client, "max_retries", -1), 0)
        self.assertEqual(str(test_client.base_url).rstrip("/"), "https://api.deepseek.com")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"content_type": "interview", "density": "medium"}'))]

        with patch("openai.resources.chat.completions.Completions.create", return_value=mock_response) as mock_create:
            res = callable_fn("Dummy prompt for classification")
            self.assertIn("interview", res)
            self.assertEqual(mock_create.call_count, 1)
            call_kwargs = mock_create.call_args[1]
            self.assertEqual(call_kwargs.get("model"), "deepseek-flash")
            self.assertEqual(call_kwargs.get("extra_body"), {"thinking": {"type": "disabled"}})

    def test_03_timeout_cap_and_shared_budget_decrement(self):
        """Verify request timeout is capped at min(600.0, remaining_job_budget - 60.0)."""
        test_jm = JobManager()
        job_ctx = test_jm.admit_job(
            job_id="test_budget_decrement_job",
            url="dummy.mp4",
            params={},
            timeout_seconds=1800.0,
        )
        now = time.time()
        job_ctx.started_at = now
        job_ctx.transition_to(JobStatus.RUNNING)

        with patch("scratch.run_controlled_replay_v3._get_active_job_context", return_value=job_ctx):
            # Case 1: Fresh job (elapsed = 0s) -> remaining = 1800, effective = 1740 -> cap is 600.0
            budget1 = v3_harness._get_request_budget_sec(cap_seconds=600.0, reserve_seconds=60.0)
            self.assertEqual(budget1, 600.0)

            # Case 2: Elapsed 1500s -> remaining = 300, effective = 240s -> cap is 240.0 (< 600.0)
            job_ctx.started_at = now - 1500.0
            budget2 = v3_harness._get_request_budget_sec(cap_seconds=600.0, reserve_seconds=60.0)
            self.assertAlmostEqual(budget2, 240.0, delta=1.0)

            # Case 3: Elapsed 1760s -> remaining = 40, effective <= 0s -> budget is 0.0
            job_ctx.started_at = now - 1760.0
            budget3 = v3_harness._get_request_budget_sec(cap_seconds=600.0, reserve_seconds=60.0)
            self.assertEqual(budget3, 0.0)

        job_ctx.transition_to(JobStatus.FAILED)

    def test_04_stt_and_file_upload_blocked(self):
        """Verify strict prohibition on Gemini STT and Google File API upload."""
        from google.genai.models import Models
        from google.genai.files import Files

        # STT call must raise RuntimeError and increment blocked counter
        with self.assertRaises(RuntimeError) as ctx_stt:
            Models.generate_content(MagicMock(), model="gemini-3.5-transcribe", contents="audio")
        self.assertIn("Semua panggilan inferensi Gemini", str(ctx_stt.exception))
        self.assertEqual(v3_harness.api_counters["transcribe"]["blocked"], 1)

        # File API upload must raise RuntimeError and increment upload counter
        with self.assertRaises(RuntimeError) as ctx_up:
            Files.upload(MagicMock(), file="sample.mp3")
        self.assertIn("Semua panggilan upload Gemini File API DIBLOKIR", str(ctx_up.exception))
        self.assertEqual(v3_harness.api_counters["file_api"]["upload"], 1)

    def test_05_fifth_highlight_request_blocked(self):
        """Verify 5th highlight inference is blocked before reaching network."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"highlights": []}'))]

        test_jm = JobManager()
        job_ctx = test_jm.admit_job("test_guard_max_job", "dummy.mp4", {}, timeout_seconds=1800.0)
        job_ctx.started_at = time.time()
        job_ctx.transition_to(JobStatus.RUNNING)

        from openai.resources.chat.completions import Completions

        with patch("scratch.run_controlled_replay_v3._get_active_job_context", return_value=job_ctx), \
             patch("scratch.run_controlled_replay_v3._orig_chat_create", return_value=mock_response):
            
            # 4 requests should succeed
            for i in range(4):
                Completions.create(MagicMock(), model="deepseek-flash", messages=[{"role": "user", "content": f"msg {i}"}])
            self.assertEqual(v3_harness.api_counters["highlight"]["dispatched"], 4)

            # 5th request must be blocked
            with self.assertRaises(RuntimeError) as ctx_max:
                Completions.create(MagicMock(), model="deepseek-flash", messages=[{"role": "user", "content": "msg 5"}])
            self.assertIn("Batas inferensi highlight terlampaui", str(ctx_max.exception))
            self.assertEqual(v3_harness.api_counters["highlight"]["blocked"], 1)
            self.assertEqual(v3_harness.api_counters["highlight"]["dispatched"], 4)

        job_ctx.transition_to(JobStatus.FAILED)

    def test_06_mocked_classification_failure(self):
        """Verify fail-fast when classification returns invalid contract."""
        test_jm = JobManager()
        tmp_session_dir = ROOT_DIR / "output_val_v3" / "test_session_official_cls_fail"
        tmp_session_dir.mkdir(parents=True, exist_ok=True)

        mock_choice = MagicMock()
        mock_choice.message.content = "Not valid JSON at all"
        mock_resp = MagicMock(choices=[mock_choice])

        try:
            with patch.object(v3_harness, "_orig_chat_create", return_value=mock_resp):
                res = official_harness.execute_official_replay(
                    provider="deepseek",
                    api_key="sk-mock-key",
                    skip_guards_test=True,
                    override_job_id="test_official_cls_fail_job",
                    override_session_dir=tmp_session_dir,
                    override_job_manager=test_jm,
                )

            meta_file = tmp_session_dir / "job_test_official_cls_fail_job.json"
            self.assertTrue(meta_file.exists())
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "failed")
            self.assertIn("ClassificationContractError", meta["error"])
            # Exactly 1 dispatch for classification, 0 for chunk ranking
            self.assertEqual(meta["api_counters"]["highlight"]["dispatched"], 1)
        finally:
            if tmp_session_dir.exists():
                shutil.rmtree(tmp_session_dir, ignore_errors=True)

    def test_07_mocked_ranking_503_failure(self):
        """Verify fail-fast when ranking encounters simulated HTTP 503."""
        test_jm = JobManager()
        tmp_session_dir = ROOT_DIR / "output_val_v3" / "test_session_official_503_fail"
        tmp_session_dir.mkdir(parents=True, exist_ok=True)

        import openai

        call_count = 0
        def fake_chat_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_choice = MagicMock()
                mock_choice.message.content = '{"content_type": "interview", "density": "medium"}'
                return MagicMock(choices=[mock_choice])
            err_resp = MagicMock(status_code=503, headers={})
            raise openai.InternalServerError(
                message="Error code: 503 - {'error': {'message': 'The model is temporarily unavailable.', 'code': 'upstream_unavailable'}}",
                response=err_resp,
                body={'error': {'message': 'The model is temporarily unavailable.', 'code': 'upstream_unavailable'}}
            )

        try:
            with patch.object(v3_harness, "_orig_chat_create", side_effect=fake_chat_create):
                res = official_harness.execute_official_replay(
                    provider="deepseek",
                    api_key="sk-mock-key",
                    skip_guards_test=True,
                    override_job_id="test_official_503_job",
                    override_session_dir=tmp_session_dir,
                    override_job_manager=test_jm,
                )

            self.assertEqual(res["status"], "failed")
            self.assertIn("InternalServerError", res["error"])
            self.assertIn("503", res["error"])
            # Exactly 2 highlight calls attempted/dispatched: 1 classification, 1 chunk 1 ranking
            self.assertEqual(res["api_counters"]["highlight"]["dispatched"], 2)
            self.assertEqual(res["api_counters"]["highlight"]["success"], 1)
            self.assertEqual(res["api_counters"]["highlight"]["failed"], 1)
        finally:
            if tmp_session_dir.exists():
                shutil.rmtree(tmp_session_dir, ignore_errors=True)

    def test_08_mocked_success_metadata_enrichment(self):
        """Verify successful run records official provider metadata without mentioning APMix."""
        test_jm = JobManager()
        tmp_session_dir = ROOT_DIR / "output_val_v3" / "test_session_official_success"
        tmp_session_dir.mkdir(parents=True, exist_ok=True)

        call_count = 0
        def fake_success_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_choice = MagicMock()
            if call_count == 1:
                mock_choice.message.content = '{"content_type": "interview", "density": "medium"}'
            else:
                mock_choice.message.content = json.dumps({
                    "highlights": [
                        {
                            "start_time": 10.0,
                            "end_time": 25.0,
                            "title": f"Highlight {call_count}",
                            "hook_sentence": "Hook text",
                            "virality_reason": "Reason",
                            "score": 85,
                        }
                    ]
                })
            return MagicMock(choices=[mock_choice])

        try:
            with patch.object(v3_harness, "_orig_chat_create", side_effect=fake_success_create):
                res = official_harness.execute_official_replay(
                    provider="deepseek",
                    api_key="sk-mock-key",
                    skip_guards_test=True,
                    skip_render=True,
                    override_job_id="test_official_success_job",
                    override_session_dir=tmp_session_dir,
                    override_job_manager=test_jm,
                )

            self.assertEqual(res["status"], "completed")
            self.assertEqual(res["run_type"], "controlled_replay_v3_official")
            self.assertEqual(res["official_provider"]["provider"], "deepseek")
            self.assertEqual(res["official_provider"]["endpoint"], "https://api.deepseek.com")
            self.assertEqual(res["official_provider"]["model"], "deepseek-flash")
            self.assertEqual(res["official_provider"]["thinking_mode"], "disabled")
            self.assertEqual(res["highlight_summary"]["top_selected_count"], 3)
        finally:
            if tmp_session_dir.exists():
                shutil.rmtree(tmp_session_dir, ignore_errors=True)

    def test_09_official_endpoint_and_credential_isolation(self):
        """Verify strict endpoint validation and credential isolation without generic fallback (O-01)."""
        # 1. Valid endpoints
        self.assertEqual(
            official_harness.validate_official_endpoint("deepseek", "https://api.deepseek.com"),
            "https://api.deepseek.com",
        )
        self.assertEqual(
            official_harness.validate_official_endpoint("openai", "https://api.openai.com/v1"),
            "https://api.openai.com/v1",
        )

        # 2. Reject HTTP (non-HTTPS)
        with self.assertRaises(ValueError) as ctx_http:
            official_harness.validate_official_endpoint("deepseek", "http://example.invalid/v1")
        self.assertIn("HTTPS", str(ctx_http.exception))

        # 3. Reject APMix endpoint
        with self.assertRaises(ValueError) as ctx_apmix:
            official_harness.validate_official_endpoint("deepseek", "https://api.apmix.ai/v1")
        self.assertIn("APMix dilarang", str(ctx_apmix.exception))

        # 4. Reject unofficial / arbitrary hosts
        with self.assertRaises(ValueError) as ctx_host:
            official_harness.validate_official_endpoint("openai", "https://example.invalid/v1")
        self.assertIn("tidak sah", str(ctx_host.exception))

        # 5. Reject cross-provider endpoints
        with self.assertRaises(ValueError) as ctx_cross1:
            official_harness.validate_official_endpoint("openai", "https://api.deepseek.com/v1")
        self.assertIn("tidak sah atau non-kanonikal", str(ctx_cross1.exception))

        with self.assertRaises(ValueError) as ctx_cross2:
            official_harness.validate_official_endpoint("deepseek", "https://api.openai.com/v1")
        self.assertIn("tidak sah atau non-kanonikal", str(ctx_cross2.exception))

        # 5.b Reject userinfo, port, query string, and non-canonical path (O-01.a)
        with self.assertRaises(ValueError) as ctx_userinfo:
            official_harness.validate_official_endpoint("openai", "https://review-user:dummy-secret@api.openai.com/v1")
        self.assertIn("userinfo", str(ctx_userinfo.exception).lower())

        with self.assertRaises(ValueError) as ctx_port:
            official_harness.validate_official_endpoint("openai", "https://api.openai.com:8443/v1")
        self.assertIn("port", str(ctx_port.exception).lower())

        with self.assertRaises(ValueError) as ctx_query:
            official_harness.validate_official_endpoint("openai", "https://api.openai.com/v1?token=dummy-secret")
        self.assertIn("query string", str(ctx_query.exception).lower())

        with self.assertRaises(ValueError) as ctx_path:
            official_harness.validate_official_endpoint("openai", "https://api.openai.com/unrelated-path")
        self.assertIn("tidak sah atau non-kanonikal", str(ctx_path.exception))

        # 6. Credential isolation: ensure generic OPENAI_API_KEY is NEVER used as fallback
        env_backup = dict(os.environ)
        try:
            os.environ["OPENAI_API_KEY"] = "sk-generic-apmix-key"
            os.environ.pop("OPENAI_OFFICIAL_API_KEY", None)
            os.environ.pop("DEEPSEEK_API_KEY", None)

            # OpenAI config resolution must NOT pick up OPENAI_API_KEY
            oa_cfg = official_harness.resolve_official_config("openai")
            self.assertIsNone(oa_cfg["api_key"])

            # DeepSeek config resolution must NOT pick up OPENAI_API_KEY
            ds_cfg = official_harness.resolve_official_config("deepseek")
            self.assertIsNone(ds_cfg["api_key"])

            # Calling execute_official_replay without key must raise RuntimeError before dispatch
            with self.assertRaises(RuntimeError) as ctx_exec:
                official_harness.execute_official_replay(provider="openai", dry_run=False)
            self.assertIn("belum disetel di lingkungan lokal", str(ctx_exec.exception))
            self.assertIn("Kunci generik OPENAI_API_KEY tidak digunakan", str(ctx_exec.exception))

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_10_deepseek_model_and_thinking_payload(self):
        """Verify deepseek-flash uses thinking=disabled extra_body in chat completions (O-02)."""
        cfg = official_harness.resolve_official_config(
            provider="deepseek",
            api_key="sk-test-key",
        )
        self.assertEqual(cfg["model"], "deepseek-flash")
        self.assertEqual(cfg["thinking_mode"], "disabled")

        callable_fn = official_harness.create_official_llm_callable(cfg)

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]

        with patch("openai.resources.chat.completions.Completions.create", return_value=mock_resp) as mock_create:
            res = callable_fn("Hello DeepSeek Flash")
            self.assertEqual(mock_create.call_count, 1)
            kwargs = mock_create.call_args[1]
            self.assertEqual(kwargs.get("model"), "deepseek-flash")
            self.assertEqual(kwargs.get("extra_body"), {"thinking": {"type": "disabled"}})
            # Temperature is passed
            self.assertEqual(kwargs.get("temperature"), 0.7)

    def test_11_override_job_manager_budget_binding_and_timeout(self):
        """Verify override_job_manager binds deadline checking and aborts if remaining <= 60s reserve (O-03)."""
        # Create a JobManager subclass that admits a job with remaining time <= 60s reserve
        class ExpiringJobManager(JobManager):
            def admit_job(self, *args, **kwargs):
                ctx = super().admit_job(*args, **kwargs)
                # Set timeout so remaining is strictly <= 60.0s reserve (e.g. 30.0s)
                ctx.timeout_seconds = 30.0
                return ctx

        test_jm = ExpiringJobManager()
        tmp_session_dir = ROOT_DIR / "output_val_v3" / "test_session_official_timeout_guard"
        tmp_session_dir.mkdir(parents=True, exist_ok=True)

        # Mock the underlying dispatch function to prove it is NEVER reached (0 dispatches)
        with patch.object(v3_harness, "_orig_chat_create") as mock_orig_chat:
            res = official_harness.execute_official_replay(
                provider="deepseek",
                api_key="sk-mock-key",
                skip_guards_test=True,
                override_job_id="test_official_timeout_job",
                override_session_dir=tmp_session_dir,
                override_job_manager=test_jm,
            )

            # 1. 0 dispatches reached the underlying chat create
            self.assertEqual(mock_orig_chat.call_count, 0)

        try:
            # 2. Final job status is TIMEOUT / timed_out
            self.assertEqual(res["status"], str(JobStatus.TIMEOUT))
            self.assertEqual(res["stage"], "timed_out")
            self.assertIn("Batas waktu job terlampaui", res["error"])

            # 3. Counters: 0 highlight calls dispatched
            self.assertEqual(res["api_counters"]["highlight"]["dispatched"], 0)
            self.assertEqual(res["api_counters"]["highlight"]["attempted"], 0)

            # 4. Final metadata written on disk
            meta_file = tmp_session_dir / "job_test_official_timeout_job.json"
            self.assertTrue(meta_file.exists())
            saved_meta = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(saved_meta["status"], str(JobStatus.TIMEOUT))
            self.assertEqual(saved_meta["stage"], "timed_out")

            # 5. Admission in test_jm is cleanly released (terminal status)
            self.assertIsNone(test_jm.get_active_job())

        finally:
            if tmp_session_dir.exists():
                shutil.rmtree(tmp_session_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
