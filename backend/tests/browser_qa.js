// tests/browser_qa.js - Automated Chrome CDP test for ShortsStudio Bagian A
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const PORT = process.argv[2] || 5055;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const TEMP_USER_DATA = path.join(process.cwd(), '.tmp_chrome_qa');

if (!fs.existsSync(TEMP_USER_DATA)) {
  fs.mkdirSync(TEMP_USER_DATA, { recursive: true });
}

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

class CDPClient {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.callbacks = new Map();

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.callbacks.has(msg.id)) {
        const { resolve, reject } = this.callbacks.get(msg.id);
        this.callbacks.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const msgId = ++this.id;
      this.callbacks.set(msgId, { resolve, reject });
      this.ws.send(JSON.stringify({ id: msgId, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error(`Eval error: ${res.exceptionDetails.text} (${expression})`);
    }
    return res.result?.value;
  }
}

async function runTest() {
  console.log('[QA] Starting Chrome in headless mode...');
  const chromeProc = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9222',
    `--user-data-dir=${TEMP_USER_DATA}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--mute-audio',
  ]);

  let cdp = null;

  try {
    // Wait for Chrome to listen on port 9222
    let versionData = null;
    for (let i = 0; i < 30; i++) {
      try {
        const res = await fetch('http://127.0.0.1:9222/json/version');
        if (res.ok) {
          versionData = await res.json();
          break;
        }
      } catch (e) {}
      await sleep(200);
    }

    if (!versionData) throw new Error('Chrome remote debugging did not respond.');

    console.log('[QA] Connecting to Chrome via CDP WebSocket...');
    const ws = new WebSocket(versionData.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    const browserCDP = new CDPClient(ws);
    const target = await browserCDP.send('Target.createTarget', { url: 'about:blank' });
    const targetWsUrl = `ws://127.0.0.1:9222/devtools/page/${target.targetId}`;

    const pageWs = new WebSocket(targetWsUrl);
    await new Promise((resolve, reject) => {
      pageWs.onopen = resolve;
      pageWs.onerror = reject;
    });
    cdp = new CDPClient(pageWs);

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('DOM.enable');

    // 1. Set Desktop Viewport 1280x800
    console.log('[QA] Setting desktop viewport 1280x800...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1280,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false,
    });

    console.log(`[QA] Navigating to ${BASE_URL}...`);
    await cdp.send('Page.navigate', { url: BASE_URL });
    await sleep(1500);

    // Verify title and page loaded
    const title = await cdp.eval('document.title');
    console.log(`[QA] Page title: "${title}"`);

    // 2. Open History Modal
    console.log('[QA] Opening History Modal...');
    await cdp.eval(`document.getElementById('historyBtn').click()`);
    await sleep(1000);

    const historyOpen = await cdp.eval(`!document.getElementById('historyModal').classList.contains('hidden')`);
    if (!historyOpen) throw new Error('History modal failed to open.');
    console.log('✅ History modal opened successfully.');

    // 3. Find card in History
    let cardFound = null;
    for (let retry = 0; retry < 20; retry++) {
      cardFound = await cdp.eval(`
        (() => {
          const item = document.querySelector('.history-item');
          if (!item) return null;
          return {
            title: item.querySelector('.history-title')?.textContent || '',
            meta: item.querySelector('.history-meta')?.textContent || '',
            hasEditBtn: !!item.querySelector('.btn-edit-clip-history'),
          };
        })()
      `);
      if (cardFound && cardFound.hasEditBtn) break;
      await sleep(400);
    }
    console.log('[QA] Found history card:', cardFound);
    if (!cardFound || !cardFound.hasEditBtn) throw new Error('History card or edit button not found.');

    // 4. Click Edit button
    console.log('[QA] Clicking Edit button on clip...');
    await cdp.eval(`document.querySelector('.btn-edit-clip-history').click()`);
    await sleep(1000);

    const editorOpen = await cdp.eval(`!document.getElementById('editorModal').classList.contains('hidden')`);
    if (!editorOpen) throw new Error('Editor modal failed to open.');
    console.log('✅ Editor modal opened successfully.');

    // 5. Verify Finding A-01: Timeline Preview Origin Stability in Clip Mode & Source Mode
    console.log('[QA] Testing A-01: Switching to Klip mode (#btnPreviewClip)...');
    await cdp.eval(`document.getElementById('btnPreviewClip').click()`);
    await sleep(500);

    const modeAfterSwitch = await cdp.eval(`document.getElementById('editorModeBadge').textContent`);
    console.log(`[QA] Badge after switching to Clip mode: "${modeAfterSwitch}"`);

    // In Clip Mode: set player to 12.4s
    await cdp.eval(`
      (() => {
        const p = document.getElementById('editorVideoPlayer');
        if (p) p.currentTime = 12.4;
        document.getElementById('btnSetInFromPlayer').click();
      })()
    `);
    const afterSetIn12_4 = await cdp.eval(`parseFloat(document.getElementById('editStartTime').value)`);
    console.log(`[QA] After Set In at t=12.4s in Clip mode: ${afterSetIn12_4}`);
    if (Math.abs(afterSetIn12_4 - 617.4) > 0.05) throw new Error(`Expected 617.4, got ${afterSetIn12_4}`);

    // Click Set In AGAIN on the same frame (test repeated click stability A-01)
    await cdp.eval(`document.getElementById('btnSetInFromPlayer').click()`);
    const afterSetInRepeat = await cdp.eval(`parseFloat(document.getElementById('editStartTime').value)`);
    console.log(`[QA] After repeated Set In at t=12.4s: ${afterSetInRepeat}`);
    if (afterSetInRepeat !== afterSetIn12_4) throw new Error(`Drift detected on repeated Set In! ${afterSetInRepeat} != ${afterSetIn12_4}`);
    console.log('✅ A-01 verified: Zero timeline drift on repeated Set In clicks in Clip mode.');

    // Manually edit In input field to 650.0, then click Set In with player at 12.4s
    await cdp.eval(`
      (() => {
        document.getElementById('editStartTime').value = '650.0';
        document.getElementById('btnSetInFromPlayer').click();
      })()
    `);
    const afterManualInSetIn = await cdp.eval(`parseFloat(document.getElementById('editStartTime').value)`);
    console.log(`[QA] After manual edit to 650.0 and Set In at 12.4s: ${afterManualInSetIn}`);
    if (Math.abs(afterManualInSetIn - 617.4) > 0.05) throw new Error(`Manual In edit corrupted clip origin! Got ${afterManualInSetIn}`);
    console.log('✅ A-01 verified: Manual In input does not alter clip preview origin.');

    // Test Source Mode: switch to source mode, seek to 625.0s, click Set In
    console.log('[QA] Testing A-01: Switching to Source mode (#btnPreviewSource)...');
    await cdp.eval(`document.getElementById('btnPreviewSource').click()`);
    await sleep(500);

    await cdp.eval(`
      (() => {
        const p = document.getElementById('editorVideoPlayer');
        if (p) p.currentTime = 625.0;
        document.getElementById('btnSetInFromPlayer').click();
      })()
    `);
    const afterSetInSourceMode = await cdp.eval(`parseFloat(document.getElementById('editStartTime').value)`);
    console.log(`[QA] After Set In at t=625.0s in Source mode: ${afterSetInSourceMode}`);
    if (Math.abs(afterSetInSourceMode - 625.0) > 0.05) throw new Error(`Expected 625.0 in source mode, got ${afterSetInSourceMode}`);
    console.log('✅ A-01 verified: Source mode accurately records absolute source timestamp.');

    // 6. Perform Revision 1: Save & Re-render (In=610.0, Out=635.0, Title="Short Real 600s Revisi 1")
    console.log('[QA] Performing Revision 1: Save & Re-render...');
    await cdp.eval(`
      (() => {
        document.getElementById('editStartTime').value = '610.0';
        document.getElementById('editEndTime').value = '635.0';
        document.getElementById('editClipTitle').value = 'Short Real 600s Revisi 1';
        document.getElementById('editClipHook').value = 'Hook Real 600s Revisi 1';
        document.getElementById('saveRenderEditorBtn').click();
      })()
    `);

    // Wait for save completion (editor modal closed)
    let save1Completed = false;
    for (let i = 0; i < 40; i++) {
      const isHidden = await cdp.eval(`document.getElementById('editorModal').classList.contains('hidden')`);
      if (isHidden) {
        save1Completed = true;
        break;
      }
      await sleep(500);
    }
    if (!save1Completed) throw new Error('Save Revision 1 timed out.');
    console.log('✅ Revision 1 saved successfully.');

    // Check updated card in DOM
    const cardRev1 = await cdp.eval(`
      (() => {
        const item = document.querySelector('.history-item');
        return {
          title: item.querySelector('.history-title')?.textContent || '',
          meta: item.querySelector('.history-meta')?.textContent || '',
          videoSrc: item.querySelector('.history-thumb video')?.src || '',
        };
      })()
    `);
    console.log('[QA] Card after Revision 1:', cardRev1);
    if (!cardRev1.title.includes('Short Real 600s Revisi 1')) throw new Error(`DOM card title not updated: ${cardRev1.title}`);
    if (!cardRev1.meta.includes('610.0s – 635.0s')) throw new Error(`DOM card meta timing not updated: ${cardRev1.meta}`);
    console.log('✅ DOM updated accurately after Revision 1.');

    // Screenshot 1: Desktop after Revision 1
    const ss1 = await cdp.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/screenshot_qa_rev1_desktop.png', Buffer.from(ss1.data, 'base64'));

    // 6b. Test dynamic click closure on "Tonton" / play button without refresh
    console.log('[QA] Testing dynamic closure on Tonton / play button without refresh...');
    await cdp.eval(`document.querySelector('.btn-play-clip').click()`);
    await sleep(600);
    const modalAfterPlay = await cdp.eval(`
      (() => {
        const modal = document.getElementById('videoModal');
        const title = document.getElementById('modalVideoTitle')?.textContent || '';
        const player = document.getElementById('modalVideoPlayer');
        const src = player?.querySelector('source')?.src || player?.src || '';
        const track = player?.querySelector('track')?.src || '';
        return {
          isOpen: !modal.classList.contains('hidden'),
          title,
          src,
          track,
        };
      })()
    `);
    console.log('[QA] Video Modal state after Tonton click:', modalAfterPlay);
    if (!modalAfterPlay.isOpen) throw new Error('Video modal did not open on Tonton click.');
    if (!modalAfterPlay.title.includes('Short Real 600s Revisi 1')) {
      throw new Error(`Video modal displayed stale title: "${modalAfterPlay.title}"`);
    }
    if (!modalAfterPlay.src.includes('?v=')) {
      throw new Error(`Video modal source missing revision cache-buster: "${modalAfterPlay.src}"`);
    }
    console.log('✅ Dynamic closure verified: Tonton opened latest revision video and title.');
    // Close video modal
    await cdp.eval(`document.getElementById('closeVideoModalBtn').click()`);
    await sleep(400);

    // 7. Verify Finding A-08: Reopening editor from same card WITHOUT refresh
    console.log('[QA] Testing A-08: Reopening editor from same card WITHOUT refresh...');
    await cdp.eval(`document.querySelector('.btn-edit-clip-history').click()`);
    await sleep(800);

    const reopenState = await cdp.eval(`
      (() => {
        return {
          inVal: parseFloat(document.getElementById('editStartTime').value),
          outVal: parseFloat(document.getElementById('editEndTime').value),
          titleVal: document.getElementById('editClipTitle').value,
          hookVal: document.getElementById('editClipHook').value,
        };
      })()
    `);
    console.log('[QA] Editor state on reopening:', reopenState);
    if (reopenState.titleVal !== 'Short Real 600s Revisi 1') throw new Error(`Expected reopened title 'Short Real 600s Revisi 1', got '${reopenState.titleVal}'`);
    if (reopenState.inVal !== 610.0) throw new Error(`Expected reopened In=610.0, got ${reopenState.inVal}`);
    if (reopenState.outVal !== 635.0) throw new Error(`Expected reopened Out=635.0, got ${reopenState.outVal}`);
    console.log('✅ A-08 verified: Reopening without refresh retains latest title and In/Out ranges.');

    // 8. Perform Revision 2: Save again with burn_subtitles=false (Test A-06 stale VTT elimination)
    console.log('[QA] Performing Revision 2: Save with subtitles disabled...');
    await cdp.eval(`
      (() => {
        document.getElementById('editStartTime').value = '612.0';
        document.getElementById('editEndTime').value = '638.0';
        document.getElementById('editClipTitle').value = 'Short Real 600s Revisi 2';
        document.getElementById('editBurnSubtitles').checked = false;
        document.getElementById('saveRenderEditorBtn').click();
      })()
    `);

    let save2Completed = false;
    for (let i = 0; i < 40; i++) {
      const isHidden = await cdp.eval(`document.getElementById('editorModal').classList.contains('hidden')`);
      if (isHidden) {
        save2Completed = true;
        break;
      }
      await sleep(500);
    }
    if (!save2Completed) throw new Error('Save Revision 2 timed out.');
    console.log('✅ Revision 2 saved successfully.');

    // 9. Reload page and verify persistence (Cycle 3)
    console.log('[QA] Reloading page to verify persistence...');
    await cdp.send('Page.reload');
    await sleep(1500);

    // Open History modal again
    await cdp.eval(`document.getElementById('historyBtn').click()`);
    await sleep(1000);

    let cardAfterReload = null;
    for (let retry = 0; retry < 20; retry++) {
      cardAfterReload = await cdp.eval(`
        (() => {
          const item = document.querySelector('.history-item');
          if (!item) return null;
          return {
            title: item.querySelector('.history-title')?.textContent || '',
            meta: item.querySelector('.history-meta')?.textContent || '',
            hasTrack: !!item.querySelector('track'),
          };
        })()
      `);
      if (cardAfterReload && cardAfterReload.title) break;
      await sleep(400);
    }
    console.log('[QA] Card after page reload:', cardAfterReload);
    if (!cardAfterReload) throw new Error('History card not found after page reload.');
    if (!cardAfterReload.title.includes('Short Real 600s Revisi 2')) throw new Error(`Reloaded card title incorrect: ${cardAfterReload.title}`);
    if (!cardAfterReload.meta.includes('612') || !cardAfterReload.meta.includes('638')) throw new Error(`Reloaded card meta timing incorrect: ${cardAfterReload.meta}`);
    if (cardAfterReload.hasTrack) throw new Error('Stale subtitle track should have been deleted (A-06)');
    console.log('✅ Persistence and stale VTT elimination verified after reload.');

    // Screenshot 2: Desktop after Revision 2
    const ss2 = await cdp.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/screenshot_qa_rev2_desktop.png', Buffer.from(ss2.data, 'base64'));

    // 10. Responsive Viewports: Mobile 390px and Mobile 320px
    console.log('[QA] Testing Mobile 390px viewport...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await sleep(500);
    const scroll390 = await cdp.eval(`document.documentElement.scrollWidth <= window.innerWidth`);
    if (!scroll390) throw new Error('Horizontal scroll detected on Mobile 390px');

    const bounds390 = await cdp.eval(`
      (() => {
        const interactive = Array.from(document.querySelectorAll('button, a.btn-download, a.btn-dl-clip, .btn-session-action'));
        const visible = interactive.filter(el => el.offsetParent !== null);
        const overflowing = visible.filter(el => {
          const r = el.getBoundingClientRect();
          return r.right > (window.innerWidth + 1.5) || r.left < -1.5;
        });
        return {
          totalVisible: visible.length,
          overflowingCount: overflowing.length,
          overflowingTags: overflowing.map(el => el.className + ' (' + el.textContent.trim() + ')'),
        };
      })()
    `);
    console.log('[QA] Mobile 390px button bounds check:', bounds390);
    if (bounds390.overflowingCount > 0) {
      throw new Error(`Buttons overflowing 390px viewport: ${bounds390.overflowingTags.join(', ')}`);
    }

    const ss390 = await cdp.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/screenshot_qa_mobile_390px.png', Buffer.from(ss390.data, 'base64'));
    console.log('✅ Mobile 390px: zero horizontal overflow & all buttons contained.');

    // 10b. Open Editor Modal on 390px and verify Batal / Simpan buttons are reachable via scroll
    console.log('[QA] Opening Editor Modal on 390px viewport to verify button containment and scrollability...');
    await cdp.eval(`document.querySelector('.btn-edit-clip-history').click()`);
    await sleep(800);
    const editorOpen390 = await cdp.eval(`!document.getElementById('editorModal').classList.contains('hidden')`);
    if (!editorOpen390) throw new Error('Editor modal failed to open on 390px');

    // Scroll down to the dialog footer
    await cdp.eval(`document.getElementById('saveRenderEditorBtn').scrollIntoView({ block: 'nearest' })`);
    await sleep(300);

    const editorBounds390 = await cdp.eval(`
      (() => {
        const cancelBtn = document.getElementById('cancelEditorBtn');
        const saveBtn = document.getElementById('saveRenderEditorBtn');
        const modal = document.querySelector('.dialog-editor');
        const mRect = modal.getBoundingClientRect();
        const cRect = cancelBtn.getBoundingClientRect();
        const sRect = saveBtn.getBoundingClientRect();
        return {
          modalWidth: mRect.width,
          cancel: { left: cRect.left, right: cRect.right, top: cRect.top, bottom: cRect.bottom },
          save: { left: sRect.left, right: sRect.right, top: sRect.top, bottom: sRect.bottom },
          cancelWithinBounds: cRect.left >= -1 && cRect.right <= window.innerWidth + 1,
          saveWithinBounds: sRect.left >= -1 && sRect.right <= window.innerWidth + 1,
          saveReachableInViewport: sRect.top >= 0 && sRect.bottom <= window.innerHeight + 10,
        };
      })()
    `);
    console.log('[QA] Mobile 390px editor buttons check:', editorBounds390);
    if (!editorBounds390.cancelWithinBounds) throw new Error('Cancel button overflows 390px viewport');
    if (!editorBounds390.saveWithinBounds) throw new Error('Save button overflows 390px viewport');
    if (!editorBounds390.saveReachableInViewport) throw new Error('Save button not reachable via scroll in 390px viewport');

    const ssEditor390 = await cdp.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/screenshot_qa_editor_390px.png', Buffer.from(ssEditor390.data, 'base64'));
    console.log('✅ Mobile 390px: Editor open, Batal/Simpan inside modal and reachable via scroll.');

    await cdp.eval(`document.getElementById('closeEditorBtn').click()`);
    await sleep(500);

    console.log('[QA] Testing Mobile 320px viewport...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 320,
      height: 568,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await sleep(500);
    const scroll320 = await cdp.eval(`document.documentElement.scrollWidth <= window.innerWidth`);
    if (!scroll320) throw new Error('Horizontal scroll detected on Mobile 320px');

    const bounds320 = await cdp.eval(`
      (() => {
        const interactive = Array.from(document.querySelectorAll('button, a.btn-download, a.btn-dl-clip, .btn-session-action'));
        const visible = interactive.filter(el => el.offsetParent !== null);
        const overflowing = visible.filter(el => {
          const r = el.getBoundingClientRect();
          return r.right > (window.innerWidth + 1.5) || r.left < -1.5;
        });
        return {
          totalVisible: visible.length,
          overflowingCount: overflowing.length,
          overflowingTags: overflowing.map(el => el.className + ' (' + el.textContent.trim() + ')'),
        };
      })()
    `);
    console.log('[QA] Mobile 320px button bounds check:', bounds320);
    if (bounds320.overflowingCount > 0) {
      throw new Error(`Buttons overflowing 320px viewport: ${bounds320.overflowingTags.join(', ')}`);
    }

    const ss320 = await cdp.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/screenshot_qa_mobile_320px.png', Buffer.from(ss320.data, 'base64'));
    console.log('✅ Mobile 320px: zero horizontal overflow & all buttons contained.');

    // 10c. Open Editor Modal on 320px and verify Batal / Simpan buttons are reachable via scroll
    console.log('[QA] Opening Editor Modal on 320px viewport to verify button containment and scrollability...');
    await cdp.eval(`document.querySelector('.btn-edit-clip-history').click()`);
    await sleep(800);
    const editorOpen320 = await cdp.eval(`!document.getElementById('editorModal').classList.contains('hidden')`);
    if (!editorOpen320) throw new Error('Editor modal failed to open on 320px');

    // Scroll down to the dialog footer
    await cdp.eval(`document.getElementById('saveRenderEditorBtn').scrollIntoView({ block: 'nearest' })`);
    await sleep(300);

    const editorBounds320 = await cdp.eval(`
      (() => {
        const cancelBtn = document.getElementById('cancelEditorBtn');
        const saveBtn = document.getElementById('saveRenderEditorBtn');
        const modal = document.querySelector('.dialog-editor');
        const mRect = modal.getBoundingClientRect();
        const cRect = cancelBtn.getBoundingClientRect();
        const sRect = saveBtn.getBoundingClientRect();
        return {
          modalWidth: mRect.width,
          cancel: { left: cRect.left, right: cRect.right, top: cRect.top, bottom: cRect.bottom },
          save: { left: sRect.left, right: sRect.right, top: sRect.top, bottom: sRect.bottom },
          cancelWithinBounds: cRect.left >= -1 && cRect.right <= window.innerWidth + 1,
          saveWithinBounds: sRect.left >= -1 && sRect.right <= window.innerWidth + 1,
          saveReachableInViewport: sRect.top >= 0 && sRect.bottom <= window.innerHeight + 10,
        };
      })()
    `);
    console.log('[QA] Mobile 320px editor buttons check:', editorBounds320);
    if (!editorBounds320.cancelWithinBounds) throw new Error('Cancel button overflows 320px viewport');
    if (!editorBounds320.saveWithinBounds) throw new Error('Save button overflows 320px viewport');
    if (!editorBounds320.saveReachableInViewport) throw new Error('Save button not reachable via scroll in 320px viewport');

    const ssEditor320 = await cdp.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync('docs/screenshot_qa_editor_320px.png', Buffer.from(ssEditor320.data, 'base64'));
    console.log('✅ Mobile 320px: Editor open, Batal/Simpan inside modal and reachable via scroll.');

    await cdp.eval(`document.getElementById('closeEditorBtn').click()`);
    await sleep(500);

    console.log('\n🎉 ALL QA CHECKS PASSED PERFECTLY! 🎉\n');
  } finally {
    if (chromeProc) {
      chromeProc.kill('SIGKILL');
    }
    try {
      fs.rmSync(TEMP_USER_DATA, { recursive: true, force: true });
    } catch (e) {}
  }
}

runTest().catch((err) => {
  console.error('[QA FAILED]', err);
  process.exit(1);
});
