const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const targetUrl = 'http://127.0.0.1:5173/';
const outputDir = path.resolve(__dirname, 'evidence-003-desktop-layout');
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

async function run() {
  const chromeProcess = spawn(chromePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--disable-gpu',
    '--no-sandbox',
    '--hide-scrollbars',
    'about:blank'
  ]);

  let versionData = null;
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9222/json/version');
      if (res.ok) {
        versionData = await res.json();
        break;
      }
    } catch {
      await new Promise(r => setTimeout(r, 200));
    }
  }

  if (!versionData) {
    console.error('Could not connect to Chrome DevTools port');
    chromeProcess.kill();
    process.exit(1);
  }

  const newTargetRes = await fetch('http://127.0.0.1:9222/json/new?' + encodeURIComponent(targetUrl), { method: 'PUT' });
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

  await new Promise(r => setTimeout(r, 2000));

  const viewports = [
    { name: 'desktop-1440', width: 1440, height: 900 },
    { name: 'laptop-1024', width: 1024, height: 768 },
    { name: 'tablet-768', width: 768, height: 1024 },
    { name: 'mobile-390', width: 390, height: 844 },
    { name: 'mobile-320', width: 320, height: 568 },
  ];

  const results = [];

  for (const vp of viewports) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: vp.width,
      height: vp.height,
      deviceScaleFactor: 1,
      mobile: vp.width < 768,
    });

    await new Promise(r => setTimeout(r, 800));

    const evalRes = await send('Runtime.evaluate', {
      expression: `(() => {
        const docEl = document.documentElement;
        const body = document.body;
        const innerWidth = window.innerWidth;
        const scrollWidth = Math.max(docEl.scrollWidth, body.scrollWidth);
        const hasHorizontalOverflow = scrollWidth > innerWidth;
        const overflowDelta = scrollWidth - innerWidth;

        const studioPlayer = document.querySelector('section[aria-label="Studio Video Monitor"]');
        const studioRect = studioPlayer ? studioPlayer.getBoundingClientRect() : null;

        const mainGrid = document.querySelector('main > div');
        const gridClasses = mainGrid ? mainGrid.className : '';

        const interactiveElements = Array.from(document.querySelectorAll('button, a, input, select'));
        const smallTargets = interactiveElements
          .filter(el => {
            const r = el.getBoundingClientRect();
            return (r.width > 0 && r.height > 0) && (r.width < 43.5 || r.height < 43.5);
          })
          .map(el => ({
            tag: el.tagName,
            text: (el.textContent || el.title || el.getAttribute('aria-label') || '').trim().slice(0, 30),
            width: Math.round(el.getBoundingClientRect().width),
            height: Math.round(el.getBoundingClientRect().height),
          }));

        return {
          innerWidth,
          scrollWidth,
          hasHorizontalOverflow,
          overflowDelta,
          hasStudioPlayer: Boolean(studioPlayer),
          studioWidth: studioRect ? Math.round(studioRect.width) : 0,
          smallTargetsCount: smallTargets.length,
          smallTargets: smallTargets.slice(0, 5),
        };
      })()`,
      returnByValue: true,
    });

    const info = evalRes.result.value;

    const shotRes = await send('Page.captureScreenshot', { format: 'png' });
    const imgBuffer = Buffer.from(shotRes.data, 'base64');
    const imgPath = path.join(outputDir, `${vp.name}.png`);
    fs.writeFileSync(imgPath, imgBuffer);

    results.push({
      ...vp,
      ...info,
      screenshot: `${vp.name}.png`
    });
  }

  console.log(JSON.stringify(results, null, 2));

  ws.close();
  chromeProcess.kill();
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
