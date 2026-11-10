"""Prepare portable HTML and source ZIP without intermediate QC screenshots."""
import base64
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
html=(ROOT/'index.html').read_text(encoding='utf-8')
js=(ROOT/'assets'/'gsap.min.js').read_text(encoding='utf-8')
html=html.replace('<script src="assets/gsap.min.js"></script>', '<script>'+js+'</script>')
for name,mime in [('Sora.ttf','font/ttf'),('WorkSans.ttf','font/ttf'),('Anton.ttf','font/ttf'),('logo.svg','image/svg+xml'),('soundtrack.wav','audio/wav')]:
    data=base64.b64encode((ROOT/'assets'/name).read_bytes()).decode('ascii')
    html=html.replace('assets/'+name,'data:'+mime+';base64,'+data)
standalone=OUT/'Reef-Clipper.html'
standalone.write_text(html,encoding='utf-8')
if '--html-only' in sys.argv:
    print(standalone)
    raise SystemExit(0)

video=OUT/'Reef-Clipper-1080p60.mp4'
if not video.is_file():
    raise SystemExit('Final MP4 missing: package not published')
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries','stream=codec_type,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,duration:format=duration,size','-of','json',str(video)],text=True))
v=next(s for s in probe['streams'] if s['codec_type']=='video')
assert (v['width'],v['height'],v['r_frame_rate'],v['nb_read_frames'])==(1920,1080,'60/1','1200'),v
assert abs(float(probe['format']['duration'])-20)<.05
decoded=subprocess.run(['ffmpeg','-hide_banner','-v','info','-i',str(video),
                        '-vf','blackdetect=d=0.01:pix_th=0.02:pic_th=0.99',
                        '-f','null','-'],capture_output=True,text=True,check=True)
assert 'black_start:' not in decoded.stderr, 'Unexpected blank interval in master'
probe['checks']={'decoded_all_frames':True,'blank_intervals':0,'expected_frames':1200,'duration_seconds':20}
(OUT/'delivery-verification.json').write_text(json.dumps(probe,indent=2),encoding='utf-8')
# Refresh the lightweight preview from the approved master after the targeted fixes.
# This is a cheap transcode, not a second browser frame render.
subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-vf','scale=960:540,fps=30',
                '-c:v','libx264','-crf','23','-preset','fast','-c:a','aac','-b:a','192k',
                '-movflags','+faststart',str(OUT/'Reef-Clipper-preview-30fps.mp4')],check=True)
with zipfile.ZipFile(OUT/'Reef-Clipper-motion-project.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in ['index.html','render.mjs','make_audio.py','verify_product.py','package_film.py','README.md','product-verification.json']:
        z.write(ROOT/name,'Reef-Clipper/'+name)
    for file in (ROOT/'assets').iterdir():
        if file.is_file():z.write(file,'Reef-Clipper/assets/'+file.name)
    for name in ['Reef-Clipper-1080p60.mp4','Reef-Clipper-preview-30fps.mp4','delivery-verification.json','qc-report.json','html-verification.json']:
        z.write(OUT/name,'Reef-Clipper/output/'+name)
for name in ['Reef-Clipper-1080p60.mp4','Reef-Clipper.html','Reef-Clipper-motion-project.zip']:
    f=OUT/name;print(f'{f} — {f.stat().st_size} bytes')
