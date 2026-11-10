import {chromium} from 'file:///C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
 const p=await browser.newPage({viewport:{width:960,height:540}}),errors=[],network=[];
 p.on('pageerror',e=>errors.push(e.message));
 await p.route(/^https?:/,route=>{network.push(route.request().url());return route.abort();});
 await p.goto(new URL('./output/Reef-Clipper.html?debug=1',import.meta.url).href);
 await p.waitForFunction(()=>window.OPENER?.ready);
 await p.locator('#play').click();
 await p.waitForFunction(()=>window.OPENER.tl.time()>.1);
 await p.keyboard.press('Space');
 const result=await p.evaluate(()=>({ready:window.OPENER.ready,duration:window.OPENER.DURATION,fonts:document.fonts.status,audio_seconds:document.querySelector('audio').duration,paused:window.OPENER.tl.paused(),frame_visible:document.querySelector('#frame').getBoundingClientRect().width>0}));
 if(errors.length||network.length||!result.paused||result.audio_seconds!==20)throw Error(JSON.stringify({errors,network,result}));
 await writeFile(new URL('./output/html-verification.json',import.meta.url),JSON.stringify({errors,external_requests:network,...result},null,2));
 console.log(JSON.stringify(result));
}finally{await browser.close();}
