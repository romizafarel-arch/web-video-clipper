import {chromium} from 'file:///C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
const p=await browser.newPage({viewport:{width:1920,height:1080}});
await p.goto(new URL('./index.html?clean=1',import.meta.url).href);await p.waitForFunction(()=>window.OPENER?.ready);
async function snap(t,name){await p.evaluate(async t=>{window.OPENER.seek(t);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));},t);if(name){await p.screenshot({path:new URL('./output/'+name+'.png',import.meta.url).pathname.slice(1)});return p.evaluate(()=>Object.fromEntries([...document.querySelectorAll('#world *')].filter(e=>e.id).map(e=>[e.id,{style:e.getAttribute('style'),rect:JSON.stringify(e.getBoundingClientRect())}])));}}
await snap(19.98);const a=await snap(10.7,'seek-a');await snap(2);const b=await snap(10.7,'seek-b');
console.log(JSON.stringify(Object.keys(a).filter(k=>JSON.stringify(a[k])!==JSON.stringify(b[k])).map(k=>({id:k,a:a[k],b:b[k]})),null,2));
}finally{await browser.close();}
