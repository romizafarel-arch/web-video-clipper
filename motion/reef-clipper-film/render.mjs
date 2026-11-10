/** Bang Motion frame export adapted to installed Playwright; lossless PNG pipe to FFmpeg.
 * node render.mjs qc | preview | final
 * PLAYWRIGHT_MODULE may point to an existing playwright/index.mjs.
 * CHROME_PATH may override the installed Chrome path. No browser download needed.
 */
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
const root=path.dirname(fileURLToPath(import.meta.url));
const mode=process.argv[2]||'qc';
if(!['qc','preview','final'].includes(mode))throw Error('Use qc, preview, or final');
const installed=path.join(process.env.USERPROFILE||'', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');
const modulePath=process.env.PLAYWRIGHT_MODULE||(existsSync(installed)?pathToFileURL(installed).href:'playwright');
const {chromium}=await import(modulePath);
const out=path.join(root,'output');await mkdir(out,{recursive:true});
const width=mode==='preview'?960:1920,height=mode==='preview'?540:1080,fps=mode==='preview'?30:60;
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files','--disable-background-timer-throttling','--disable-renderer-backgrounding']});
let ffmpeg;
try{
 const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(pathToFileURL(path.join(root,'index.html')).href+'?clean=1');
 await page.waitForFunction(()=>window.OPENER?.ready,{timeout:30000});
 await page.evaluate(()=>document.fonts.ready);
 async function frame(t){
  await page.evaluate(async time=>{await window.OPENER.seekFrame(time);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));},t);
  return page.screenshot({type:'png',animations:'allow'});
 }
 if(mode==='qc'){
  const times=[0,.8,2.2,3.8,5.3,6.4,7.5,9.6,10.7,11.3,12.8,13.7,15.2,16.8,18.7,19.98];
  for(const t of times)await writeFile(path.join(out,`qc-${t.toFixed(2)}.png`),await frame(t));
  const states=()=>page.evaluate(()=>[...document.querySelectorAll('#world *')].filter(e=>e.id).map(e=>[e.id,e.getAttribute('style'),JSON.stringify(e.getBoundingClientRect())]));
  const first=await frame(10.7),stateA=await states();await frame(2);const second=await frame(10.7),stateB=await states();
  if(JSON.stringify(stateA)!==JSON.stringify(stateB))throw Error('Timeline state differs after reverse seek');
  const pixels=await page.evaluate(async ([a,b])=>{
   async function decode(s){const im=new Image();im.src='data:image/png;base64,'+s;await im.decode();const c=document.createElement('canvas');c.width=im.width;c.height=im.height;const ctx=c.getContext('2d');ctx.drawImage(im,0,0);return ctx.getImageData(0,0,c.width,c.height).data;}
   const x=await decode(a),y=await decode(b);let max=0,sum=0;for(let i=0;i<x.length;i++){const d=Math.abs(x[i]-y[i]);max=Math.max(max,d);sum+=d;}return {max_channel_difference:max,mean_channel_difference:sum/x.length};
  },[first.toString('base64'),second.toString('base64')]);
  // Chrome may vary one rounding bit on a few gradient pixels; geometry must be exact.
  if(pixels.max_channel_difference>1||pixels.mean_channel_difference>.0001)throw Error('Reverse seek pixel difference exceeds compositor rounding tolerance');
  const report={errors,deterministic_seek:true,identical_dom_state:true,pixels,frames:times,duration:await page.evaluate(()=>window.OPENER.tl.duration())};
  await writeFile(path.join(out,'qc-report.json'),JSON.stringify(report,null,2));
  if(errors.length)throw Error(errors.join('\n'));
  console.log(JSON.stringify(report));
 }else{
  const target=path.join(out,mode==='final'?'Reef-Clipper-1080p60.mp4':'Reef-Clipper-preview-30fps.mp4');
  ffmpeg=spawn('ffmpeg',['-y','-hide_banner','-loglevel','warning','-f','image2pipe','-framerate',String(fps),'-vcodec','png','-i','pipe:0','-i',path.join(root,'assets/soundtrack.wav'),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf',mode==='final'?'17':'23','-pix_fmt','yuv420p','-r',String(fps),'-c:a','aac','-b:a','256k','-t','20','-movflags','+faststart',target],{stdio:['pipe','ignore','pipe']});
  let encodingLog='';ffmpeg.stderr.on('data',b=>encodingLog+=b.toString());
  const completed=once(ffmpeg,'close');
  ffmpeg.stdin.on('error',()=>{});
  for(let i=0;i<20*fps;i++){
   const png=await frame(i/fps);
   if(!ffmpeg.stdin.write(png))await once(ffmpeg.stdin,'drain');
   if(i%(fps*2)===0)console.log(`${mode}: ${i}/${20*fps} frames`);
  }
  ffmpeg.stdin.end();const [code]=await completed;
  if(code!==0)throw Error(encodingLog);
  if(errors.length)throw Error(errors.join('\n'));
  console.log(`DONE: ${target}`);
 }
}finally{await browser.close();if(ffmpeg&&!ffmpeg.killed&&ffmpeg.exitCode===null)ffmpeg.kill();}
