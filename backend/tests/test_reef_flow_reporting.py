"""Unit tests for Reef Flow Webhook Error Reporting."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from shorts_generator.error_reporter import (
    _send_payload_sync,
    reportErrorToReefFlow,
    report_error_to_reef_flow,
    scrub_sensitive_keys,
)
from web_app import app


class TestReefFlowErrorReporting(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        os.environ["REEF_FLOW_WEBHOOK_URL"] = "http://localhost:3000/api/v1/projects/RC/issues"
        os.environ["REEF_FLOW_API_KEY"] = "rf_live_testkey12345678901234567890"

    def test_scrub_sensitive_keys(self):
        text = "Failed with key rf_live_dummy_test_key_000000000000000000000000 and sk-12345678901234567890"
        scrubbed = scrub_sensitive_keys(text)
        self.assertNotIn("rf_live_dummy_test_key_000000000000000000000000", scrubbed)
        self.assertNotIn("sk-12345678901234567890", scrubbed)
        self.assertIn("[REDACTED_API_KEY]", scrubbed)

    @patch("urllib.request.urlopen")
    def test_send_payload_sync_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        title = "Very long title " + ("x" * 150)
        desc = "Traceback detail"
        ok = _send_payload_sync(
            webhook_url="http://localhost:3000/api/v1/projects/RC/issues",
            api_key="rf_live_testkey",
            title=title,
            description=desc,
            priority="URGENT",
            status="TODO",
        )
        self.assertTrue(ok)
        self.assertTrue(mock_urlopen.called)

        # Inspect request
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.headers.get("X-api-key"), "rf_live_testkey")
        self.assertEqual(req.headers.get("Content-type"), "application/json")

        payload = json.loads(req.data.decode("utf-8"))
        self.assertLessEqual(len(payload["title"]), 120)
        self.assertTrue(payload["title"].endswith("..."))
        self.assertEqual(payload["priority"], "URGENT")
        self.assertEqual(payload["status"], "TODO")

    @patch("urllib.request.urlopen")
    def test_send_payload_sync_failure_is_safe(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("Connection refused")
        # Should not raise exception
        ok = _send_payload_sync(
            webhook_url="http://localhost:3000/api/v1/projects/RC/issues",
            api_key="rf_live_testkey",
            title="Test Error",
            description="Details",
        )
        self.assertFalse(ok)

    @patch("threading.Thread")
    def test_report_error_async_starts_thread(self, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        report_error_to_reef_flow(
            title="Async Error",
            description="Detail",
            priority="HIGH",
        )

        self.assertTrue(mock_thread_cls.called)
        self.assertTrue(mock_thread.start.called)
        _, kwargs = mock_thread_cls.call_args
        self.assertTrue(kwargs.get("daemon"))

    def test_alias_equality(self):
        self.assertEqual(report_error_to_reef_flow, reportErrorToReefFlow)

    @patch("shorts_generator.error_reporter._send_payload_sync")
    def test_api_report_error_endpoint(self, mock_send):
        mock_send.return_value = True

        res = self.app.post(
            "/api/report-error",
            json={
                "title": "Client side exception",
                "description": "Button click failed",
                "priority": "HIGH",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "reported")


if __name__ == "__main__":
    unittest.main()
