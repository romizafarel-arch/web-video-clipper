"""Automated End-to-End Browser QA Runner for ShortsStudio Bagian A."""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from web_app import app, OUTPUT_DIR
from shorts_generator.local.clipper import crop_clip_local


def setup_real_test_session() -> Path:
    session_id = "session_e2e_real_qa"
    session_dir = OUTPUT_DIR / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
    session_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ensure test_source_700s.mp4 exists
    root_source = Path("test_source_700s.mp4").resolve()
    if not root_source.exists() or root_source.stat().st_size < 10000:
        print("[SETUP] Generating 700s test video with ffmpeg...")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=700:size=160x120:rate=5",
            "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", "700",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(root_source),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    session_source = session_dir / "source_700s.mp4"
    shutil.copy2(str(root_source), str(session_source))

    # 2. Render initial short_01.mp4 at 605s..640s
    short1_path = session_dir / "short_01.mp4"
    print("[SETUP] Pre-rendering initial short_01.mp4 (605s..640s)...")
    crop_clip_local(
        source_path=str(session_source),
        start_time=605.0,
        end_time=640.0,
        aspect_ratio="9:16",
        out_path=str(short1_path),
        burn_subtitles=False,
    )

    # 3. Create initial VTT
    vtt_path = session_dir / "short_01.vtt"
    vtt_path.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:10.000\nInitial Subtitle At 10 Minutes\n",
        encoding="utf-8",
    )

    # 4. Create Job JSON
    job_meta = {
        "job_id": session_id,
        "session_folder": session_id,
        "created_at": "2026-09-28T16:00:00",
        "result": {
            "source_video_url": str(session_source),
            "transcript": {
                "duration": 700.0,
                "segments": [
                    {"start": 605.0, "end": 640.0, "text": "Segmen video pada menit ke-10"},
                ],
            },
            "shorts": [
                {
                    "clip_index": 1,
                    "filename": "short_01.mp4",
                    "title": "Short Asli 600s",
                    "hook_sentence": "Hook awal 600s",
                    "start_time": 605.0,
                    "end_time": 640.0,
                    "score": 92,
                    "clip_url": str(short1_path),
                    "web_url": f"/output/{session_id}/short_01.mp4",
                    "vtt_url": f"/output/{session_id}/short_01.vtt",
                }
            ],
        },
    }
    with open(session_dir / f"job_{session_id}.json", "w", encoding="utf-8") as f:
        json.dump(job_meta, f, indent=2)

    return session_dir


def main():
    session_dir = setup_real_test_session()
    port = 5055

    # Run Flask in background thread
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()
    time.sleep(1.0)
    print(f"[RUNNER] Flask test server running on http://127.0.0.1:{port}")

    try:
        # Run node tests/browser_qa.js
        print("[RUNNER] Launching Node.js CDP browser QA runner...")
        res = subprocess.run(["node", "tests/browser_qa.js", str(port)], check=False)
        if res.returncode != 0:
            print(f"[RUNNER FAILED] Node runner exited with code {res.returncode}")
            sys.exit(res.returncode)
        else:
            print("[RUNNER SUCCESS] All browser QA tests passed!")
    finally:
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
        root_source = Path("test_source_700s.mp4")
        if root_source.exists():
            root_source.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
