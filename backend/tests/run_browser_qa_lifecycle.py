"""Automated End-to-End Browser QA Runner for ShortsStudio Bagian B (Job Lifecycle)."""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from flask import jsonify, request

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import web_app
from web_app import app, job_manager, jobs, OUTPUT_DIR
from shorts_generator.job_manager import JobContext, JobStatus


# Additional test control hooks
_fail_cancel_flag = False
_glitch_job_count = 0


@app.route("/api/test/setup_job", methods=["POST"])
def test_setup_job():
    global _fail_cancel_flag, _glitch_job_count
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id", "test_qa_job")
    status = data.get("status", JobStatus.RUNNING)
    stage = data.get("stage", "analyzing")
    progress = data.get("progress", 50)
    logs = data.get("logs", "[QA] Running test job step...\n")
    error = data.get("error")
    cancel_reason = data.get("cancel_reason")
    result = data.get("result")

    with job_manager._admission_lock:
        if job_id in job_manager._jobs:
            ctx = job_manager._jobs[job_id]
        else:
            ctx = JobContext(job_id=job_id, url="https://youtu.be/sample", params={"num_clips": 1})
            job_manager._jobs[job_id] = ctx

        ctx.status = status
        ctx.stage = stage
        ctx.progress = progress
        ctx.error = error
        ctx.cancel_reason = cancel_reason
        ctx.result = result
        if isinstance(logs, list):
            ctx.logs = logs
        else:
            ctx.logs = [logs]

        jobs[job_id] = ctx.to_dict()

    return jsonify({"success": True, "job_id": job_id})


@app.route("/api/test/set_flags", methods=["POST"])
def test_set_flags():
    global _fail_cancel_flag, _glitch_job_count
    data = request.get_json(force=True) or {}
    _fail_cancel_flag = bool(data.get("fail_cancel", False))
    _glitch_job_count = int(data.get("glitch_count", 0))
    return jsonify({"success": True, "fail_cancel": _fail_cancel_flag, "glitch_count": _glitch_job_count})


# Wrap get_job and cancel_job to handle test flags
_orig_get_job = app.view_functions.get("get_job")
_orig_cancel_job = app.view_functions.get("api_cancel_job")


def _wrapped_get_job(job_id: str):
    global _glitch_job_count
    if _glitch_job_count > 0:
        _glitch_job_count -= 1
        return jsonify({"error": "Simulated temporary network fault"}), 503
    return _orig_get_job(job_id)


def _wrapped_cancel_job(job_id: str):
    global _fail_cancel_flag
    if _fail_cancel_flag:
        _fail_cancel_flag = False
        return jsonify({"error": "Simulated cancel server failure"}), 500
    return _orig_cancel_job(job_id)


app.view_functions["get_job"] = _wrapped_get_job
app.view_functions["api_cancel_job"] = _wrapped_cancel_job


def main():
    port = 5066

    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()
    time.sleep(1.0)
    print(f"[RUNNER B] Flask test server running on http://127.0.0.1:{port}")

    try:
        print("[RUNNER B] Launching Node.js CDP Lifecycle QA runner...")
        res = subprocess.run(["node", "tests/browser_qa_lifecycle.js", str(port)], check=False)
        if res.returncode != 0:
            print(f"[RUNNER B FAILED] Node runner exited with code {res.returncode}")
            sys.exit(res.returncode)
        else:
            print("[RUNNER B SUCCESS] All Bagian B browser lifecycle QA tests passed!")
    finally:
        pass


if __name__ == "__main__":
    main()
