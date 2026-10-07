const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const targetUrl = 'http://127.0.0.1:5173/';
const outputDir = path.resolve(__dirname, 'evidence-003-desktop-layout');

async function testInteractions() {
  const chromeProcess = spawn(chromePath, [
    '--headless=new',
    '--remote-debugging-port=9223',
    '--disable-gpu',
    '--no-sandbox',
    'about:blank'
  ]);

  let versionData = null;
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9223/json/version');
      if (res.ok) {
        versionData = await res.json();
        break;
      }
    } catch {
      await new Promise(r => setTimeout(r, 200));
    }
  }

  if (!versionData) {
    chromeProcess.kill();
    throw new Error('Chrome remote debug not ready');
  }

  const newTargetRes = await fetch('http://127.0.0.1:9223/json/new?' + encodeURIComponent(targetUrl), { method: 'PUT' });
  const target = await newTargetRes.json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);

  let idCounter = 1;
  const pending = new Map();

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(msg.error);
      else resolve(msg.result);
    }
  };

  const send = (method, params = {}) => {
    return new Promise((resolve, reject) => {
      const id = idCounter++;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  };

  await new Promise(r => ws.onopen = r);
  await send('Page.enable');
  await send('DOM.enable');
  await send('Runtime.enable');

  await send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });

  await new Promise(r => setTimeout(r, 2000));

  // Step 1: Open History Modal
  const openHistoryRes = await send('Runtime.evaluate', {
    expression: `(() => {
      const btn = document.querySelector('button[title*="Riwayat"]');
      if (btn) btn.click();
      return Boolean(btn);
    })()`,
    returnByValue: true,
  });

  await new Promise(r => setTimeout(r, 1200));

  // Step 2: Wait for history items and click "Studio" on first history clip
  let clickStudioRes = { success: false, count: 0 };
  for (let attempt = 0; attempt < 20; attempt++) {
    const checkRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const studioBtns = Array.from(document.querySelectorAll('button[title*="Player Studio"]'));
        if (studioBtns.length > 0) {
          studioBtns[0].click();
          return { success: true, count: studioBtns.length };
        }
        return { success: false, count: 0 };
      })()`,
      returnByValue: true,
    });
    if (checkRes.result.value.success) {
      clickStudioRes = checkRes.result.value;
      break;
    }
    await new Promise(r => setTimeout(r, 400));
  }

  await new Promise(r => setTimeout(r, 1000));

  // Step 3: Type custom text into live subtitle input
  const typeTextRes = await send('Runtime.evaluate', {
    expression: `(() => {
      const input = document.getElementById('live-subtitle-input');
      if (input) {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, '🔥 TEST SUBTITLE INTERAKTIF REAL-TIME 100%');
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      }
      return false;
    })()`,
    returnByValue: true,
  });

  await new Promise(r => setTimeout(r, 500));

  // Step 4: Verify text on overlay & capture screenshot
  const verifyRes = await send('Runtime.evaluate', {
    expression: `(() => {
      const overlay = document.querySelector('.tiktok-subtitle-stroke');
      const textContent = overlay ? overlay.textContent : '';
      const video = document.querySelector('section[aria-label="Studio Video Monitor"] video');
      return {
        hasVideo: Boolean(video),
        videoSrc: video ? video.src : '',
        overlayText: textContent,
      };
    })()`,
    returnByValue: true,
  });

  const shotRes = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(outputDir, 'desktop-studio-clip-loaded.png'), Buffer.from(shotRes.data, 'base64'));

  console.log(JSON.stringify({
    openHistory: openHistoryRes.result.value,
    clickStudio: clickStudioRes.result.value,
    typeText: typeTextRes.result.value,
    verify: verifyRes.result.value,
  }, null, 2));

  ws.close();
  chromeProcess.kill();
}

testInteractions().catch(e => {
  console.error(e);
  process.exit(1);
});
