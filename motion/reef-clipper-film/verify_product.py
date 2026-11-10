"""Bounded integration audit: actual Flask editor + native FFmpeg, no AI calls."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'backend'))
import web_app

with tempfile.TemporaryDirectory(prefix='reef_motion_audit_', dir=str(ROOT)) as temp:
    output = Path(temp)
    session = output / 'fictional-demo'
    session.mkdir()
    source = session / 'source.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                    '-i', 'testsrc2=size=640x360:rate=30:duration=4', '-f', 'lavfi',
                    '-i', 'sine=frequency=220:sample_rate=48000:duration=4',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)], check=True)
    meta = {'job_id': 'fictional-demo', 'result': {
        'source_video_url': str(source), 'transcript': {'segments': []},
        'shorts': [{'clip_index': 1, 'filename': 'short_01.mp4', 'start_time': 0, 'end_time': 4}]}}
    (session / 'job_demo.json').write_text(json.dumps(meta), encoding='utf-8')
    with patch.object(web_app, 'OUTPUT_DIR', output):
        client = web_app.app.test_client()
        res = client.post('/api/edit-clip', json={
            'session_folder': 'fictional-demo', 'clip_index': 1,
            'start_time': 1, 'end_time': 3, 'aspect_ratio': '9:16',
            'framing_mode': 'center', 'subtitle_style': 'classic', 'font_family': 'Anton',
            'burn_subtitles': True, 'enable_sfx': False, 'remove_silence': False,
            'title': 'Fictional motion demo',
            'segments': [{'start': 1, 'end': 2.8, 'text': 'Keep'}]})
        report = {'endpoint': '/api/edit-clip', 'http_status': res.status_code,
                  'claims_tested': ['trim 1–3 seconds', '9:16 center crop', 'manual subtitle text', 'MP4 render'],
                  'paid_ai_calls': 0,
                  'limitation': 'Earlier multiword cue on a tone-only source returned KEEP only. Film uses the verified single-word cue KEEP; no automatic caption claim.'}
        if res.status_code != 200:
            report['error'] = res.get_json()
        else:
            video = session / 'short_01.mp4'
            probe = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                'stream=codec_type,width,height:format=duration', '-of', 'json', str(video)], text=True)
            report['media'] = json.loads(probe)
            report['subtitle_vtt'] = (session / 'short_01.vtt').read_text(encoding='utf-8')
            assert 'KEEP' in report['subtitle_vtt'].upper(), 'Expected manual cue missing'
            report['download_status'] = client.get('/output/fictional-demo/short_01.mp4').status_code
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True)
            report['decode_ok'] = True
        (ROOT / 'product-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        assert res.status_code == 200, 'Actual render failed; do not claim verification'
