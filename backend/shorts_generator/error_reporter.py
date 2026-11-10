"""Automated Error Ingestion Reporter for Reef Flow.

Integrates automatic issue tracking with Reef Flow Webhook Ingestion API.
Ensures zero-crash, non-blocking execution via background worker threads.
"""
import json
import logging
import os
import re
import threading
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("shorts_generator.error_reporter")


def scrub_sensitive_keys(text: str) -> str:
    """Mask known API keys and sensitive tokens from error messages and tracebacks."""
    if not text:
        return ""
    patterns = [
        r"(rf_live_[a-zA-Z0-9_\-]{16,})",
        r"(AQ\.[a-zA-Z0-9_\-]{20,})",
        r"(apx_live_[a-zA-Z0-9_\-]{16,})",
        r"(sk-[a-zA-Z0-9_\-]{20,})",
    ]
    cleaned = str(text)
    for p in patterns:
        cleaned = re.sub(p, "[REDACTED_API_KEY]", cleaned)
    return cleaned


def _send_payload_sync(
    webhook_url: str,
    api_key: str,
    title: str,
    description: Optional[str] = None,
    priority: str = "URGENT",
    status: str = "TODO",
    timeout: float = 5.0,
) -> bool:
    """Send POST request to Reef Flow Webhook Ingestion API synchronously."""
    try:
        # Title must be max 120 chars, single-line
        safe_title = str(title or "Unknown Error").strip().replace("\r", " ").replace("\n", " ")
        if len(safe_title) > 120:
            safe_title = safe_title[:117] + "..."
        if not safe_title:
            safe_title = "Unknown Error"

        safe_desc = scrub_sensitive_keys(str(description or ""))

        payload = {
            "title": safe_title,
            "description": safe_desc,
            "priority": str(priority or "URGENT").upper(),
            "status": str(status or "TODO").upper(),
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "User-Agent": "ReefClipper/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        logger.debug(f"[ReefFlow] Reporting failed: {e}")
        return False


def report_error_to_reef_flow(
    title: str,
    description: Optional[str] = None,
    priority: str = "URGENT",
    status: str = "TODO",
    async_mode: bool = True,
) -> None:
    """Report an error to Reef Flow Webhook Ingestion API.

    Guaranteed non-blocking and safe: Wrapped in internal try/catch so failure
    never interrupts the main Reef Clipper execution pipeline.
    """
    try:
        webhook_url = os.getenv("REEF_FLOW_WEBHOOK_URL", "").strip()
        api_key = os.getenv("REEF_FLOW_API_KEY", "").strip()

        if not webhook_url or not api_key:
            return

        if async_mode:
            thread = threading.Thread(
                target=_send_payload_sync,
                args=(webhook_url, api_key, title, description, priority, status),
                daemon=True,
            )
            thread.start()
        else:
            _send_payload_sync(webhook_url, api_key, title, description, priority, status)
    except Exception as e:
        # Ultimate defensive fallback: never allow reporting errors to bubble up
        logger.debug(f"[ReefFlow] Unexpected reporter wrapper error: {e}")


# Exact alias matching user prompt
reportErrorToReefFlow = report_error_to_reef_flow
