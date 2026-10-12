"""E2E Browser QA Test Runner for ShortsStudio React SPA."""
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


@app.route("/api/test/setup_job", methods=["POST"])
def test_setup_job():
    data = request.get_json(force=True) or {}
    job_id = data.get("job_id", "test_job_123")
    status = data.get("status", JobStatus.RUNNING)
    stage = data.get("stage", "analyzing")
    progress = data.get("progress", 50)
    logs = data.get("logs", ["[QA] Initializing test pipeline...\n"])
    error = data.get("error")
    cancel_reason = data.get("cancel_reason")
    result = data.get("result")
    url = data.get("url", "https://youtu.be/dQw4w9WgXcQ")
    params = data.get("params", {"num_clips": 3, "aspect_ratio": "9:16"})

    with job_manager._admission_lock:
        if job_id in job_manager._jobs:
            ctx = job_manager._jobs[job_id]
        else:
            ctx = JobContext(job_id=job_id, url=url, params=params)
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


@app.route("/api/test/create_sample_session", methods=["POST"])
def test_create_sample_session():
    """Create sample videos in OUTPUT_DIR to test HistoryModal and preview dialog."""
    session_id = "session_e2e_sample"
    session_dir = OUTPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy mp4 files
    for name, ar in [("clip_916.mp4", "9:16"), ("clip_11.mp4", "1:1"), ("clip_169.mp4", "16:9")]:
        fpath = session_dir / name
        if not fpath.exists():
            # Minimal MP4 header / bytes so it can be served
            fpath.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

    # Metadata job.json
    job_meta = {
        "job_id": "sample_history_job",
        "url": "https://youtu.be/dQw4w9WgXcQ",
        "title": "Sesi Tes Riwayat E2E",
        "status": "completed",
        "params": {"aspect_ratio": "9:16", "num_clips": 3},
        "aspect_ratio": "9:16",
        "result": {
            "video_title": "Video Contoh E2E",
            "shorts": [
                {
                    "clip_index": 1,
                    "filename": "clip_916.mp4",
                    "clip_url": str(session_dir / "clip_916.mp4"),
                    "web_url": f"/output/{session_id}/clip_916.mp4",
                    "title": "Klip Vertikal 9:16",
                    "aspect_ratio": "9:16",
                    "start_time": 0.0,
                    "end_time": 15.0,
                    "score": 95,
                    "hook_sentence": "Hook pembuka viral",
                },
                {
                    "clip_index": 2,
                    "filename": "clip_11.mp4",
                    "clip_url": str(session_dir / "clip_11.mp4"),
                    "web_url": f"/output/{session_id}/clip_11.mp4",
                    "title": "Klip Persegi 1:1",
                    "aspect_ratio": "1:1",
                    "start_time": 15.0,
                    "end_time": 30.0,
                    "score": 88,
                    "hook_sentence": "Hook kedua",
                },
                {
                    "clip_index": 3,
                    "filename": "clip_169.mp4",
                    "clip_url": str(session_dir / "clip_169.mp4"),
                    "web_url": f"/output/{session_id}/clip_169.mp4",
                    "title": "Klip Lanskap 16:9",
                    "aspect_ratio": "16:9",
                    "start_time": 30.0,
                    "end_time": 45.0,
                    "score": 91,
                    "hook_sentence": "Hook ketiga lanskap",
                },
            ],
        },
    }
    (session_dir / "job_sample_history.json").write_text(json.dumps(job_meta), encoding="utf-8")
    return jsonify({"success": True, "session_id": session_id})


def main():
    port = int(os.environ.get("TEST_PORT", 5088))
    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()
    print(f"[E2E-RUNNER] Flask backend running on port {port}...")
    time.sleep(1.5)

    # Run Node.js CDP test
    script_path = BASE_DIR / "tests" / "e2e_spa_browser_test.mjs"
    res = subprocess.run([sys.executable, "-c", "import sys; sys.exit(0)"])
    proc = subprocess.run(["node", str(script_path), str(port)], capture_output=False)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
