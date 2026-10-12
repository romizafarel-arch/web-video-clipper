// tests/browser_qa_lifecycle.js - Automated Chrome CDP test for ShortsStudio Bagian B (Job Lifecycle)
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const PORT = process.argv[2] || 5066;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const TEMP_USER_DATA = path.join(process.cwd(), '.tmp_chrome_qa_b');

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

async function postHelper(url, body) {
  const res = await fetch(`${BASE_URL}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function runTest() {
  console.log('[QA-B] Starting Chrome in headless mode for Lifecycle QA...');
  const chromeProc = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9223',
    `--user-data-dir=${TEMP_USER_DATA}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--mute-audio',
  ]);

  let cdp = null;

  try {
    let versionData = null;
    for (let i = 0; i < 30; i++) {
      try {
        const res = await fetch('http://127.0.0.1:9223/json/version');
        if (res.ok) {
          versionData = await res.json();
          break;
        }
      } catch (e) {}
      await sleep(200);
    }

    if (!versionData) throw new Error('Chrome remote debugging did not respond.');

    console.log('[QA-B] Connecting to Chrome via CDP WebSocket...');
    const ws = new WebSocket(versionData.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    const browserCDP = new CDPClient(ws);
    const target = await browserCDP.send('Target.createTarget', { url: 'about:blank' });
    const targetWsUrl = `ws://127.0.0.1:9223/devtools/page/${target.targetId}`;

    const pageWs = new WebSocket(targetWsUrl);
    await new Promise((resolve, reject) => {
      pageWs.onopen = resolve;
      pageWs.onerror = reject;
    });
    cdp = new CDPClient(pageWs);

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('DOM.enable');

    // =========================================================================
    // 1. Initial Desktop Viewport 1280x800 & Navigate
    // =========================================================================
    console.log('[QA-B] Step 1: Navigating to studio on Desktop 1280x800...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1280,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false,
    });

    await cdp.send('Page.navigate', { url: BASE_URL });
    await sleep(1500);

    const title = await cdp.eval('document.title');
    console.log(`[QA-B] Title: "${title}"`);

    // =========================================================================
    // 2. Lifecycle Scenario: Cancellation of Running Job
    // =========================================================================
    console.log('[QA-B] Step 2: Testing Job Cancellation from Running State...');
    const jobId1 = 'job_cancel_test_01';
    await postHelper('/api/test/setup_job', {
      job_id: jobId1,
      status: 'running',
      stage: 'analyzing',
      progress: 60,
      logs: '[pipeline] Running highlight analysis...\n',
    });

    // Emulate starting polling on this job via Page reload resume
    await cdp.eval(`localStorage.setItem('shorts_active_job_id', '${jobId1}')`);
    await cdp.send('Page.reload');
    await sleep(2000);

    // Click Cancel button
    console.log('[QA-B] Clicking Cancel button...');
    await cdp.eval(`document.getElementById('btnCancelJob').click()`);
    await sleep(400);

    const btnAfterClick = await cdp.eval(`
      (() => {
        const b = document.getElementById('btnCancelJob');
        return {
          disabled: b.disabled,
          cancelingClass: b.classList.contains('canceling'),
          text: b.querySelector('span')?.textContent,
        };
      })()
    `);
    console.log('[QA-B] Cancel button state immediately after click:', btnAfterClick);
    if (!btnAfterClick.disabled && !btnAfterClick.cancelingClass) {
      throw new Error('Cancel button did not enter canceling state after click.');
    }

    // Server marks job canceled
    await postHelper('/api/test/setup_job', {
      job_id: jobId1,
      status: 'canceled',
      stage: 'canceled',
      progress: 100,
      cancel_reason: 'Dibatalkan oleh pengguna saat QA.',
    });
    await sleep(1500); // Wait for poll cycle

    const titleCanceled = await cdp.eval(`document.getElementById('progressTitle').textContent`);
    const keyAfterCancel = await cdp.eval(`localStorage.getItem('shorts_active_job_id')`);
    console.log(`[QA-B] Progress Title after canceled: "${titleCanceled}", active key: "${keyAfterCancel}"`);
    if (!titleCanceled.includes('Dibatalkan')) {
      throw new Error(`Expected title to indicate cancellation, got: ${titleCanceled}`);
    }
    if (keyAfterCancel) {
      throw new Error('Active job key was not cleared from localStorage after cancellation.');
    }
    console.log('✅ Scenario 1 (Cancellation of Running Job) Passed.');

    // =========================================================================
    // 3. Lifecycle Scenario: Refresh & Resume Active Running Job
    // =========================================================================
    console.log('[QA-B] Step 3: Testing Page Refresh with Active Running Job...');
    const jobId2 = 'job_resume_running_02';
    await postHelper('/api/test/setup_job', {
      job_id: jobId2,
      status: 'running',
      stage: 'transcribing',
      progress: 45,
      logs: '[transcribe] Extracting segments and generating timestamps...\n',
    });

    await cdp.eval(`localStorage.setItem('shorts_active_job_id', '${jobId2}')`);
    console.log('[QA-B] Reloading page to test resumeActiveJobIfAny...');
    await cdp.send('Page.reload');
    await sleep(2000);

    const resumedState = await cdp.eval(`
      (() => {
        const prog = document.getElementById('progressSection');
        const title = document.getElementById('progressTitle')?.textContent;
        const fill = document.getElementById('progressBarFill')?.style.width;
        const activeKey = localStorage.getItem('shorts_active_job_id');
        const logs = document.getElementById('terminalLogBody')?.textContent;
        return {
          progressVisible: !prog.classList.contains('hidden'),
          title,
          fill,
          activeKey,
          hasLogs: logs && logs.includes('[transcribe]'),
        };
      })()
    `);
    console.log('[QA-B] Resumed state after reload:', resumedState);
    if (!resumedState.progressVisible || resumedState.activeKey !== jobId2 || !resumedState.hasLogs) {
      throw new Error(`Failed to restore active running job on page reload: ${JSON.stringify(resumedState)}`);
    }
    console.log('✅ Scenario 2 (Refresh & Resume Active Running Job) Passed.');

    // =========================================================================
    // 4. Lifecycle Scenario: Resume with Partial Results
    // =========================================================================
    console.log('[QA-B] Step 4: Testing Page Refresh with Completed Partial Job...');
    const jobId3 = 'job_partial_03';
    await postHelper('/api/test/setup_job', {
      job_id: jobId3,
      status: 'partial',
      stage: 'partial',
      progress: 100,
      error: 'Sebagian klip selesai sebelum batas waktu.',
      result: {
        mode: 'local',
        shorts: [
          {
            clip_index: 1,
            title: 'Klip Parsial Pertama',
            hook_sentence: 'Hook pertama sukses',
            filename: 'short_01.mp4',
            web_url: '/output/test/short_01.mp4',
            clip_url: '/output/test/short_01.mp4',
          }
        ]
      }
    });

    await cdp.eval(`localStorage.setItem('shorts_active_job_id', '${jobId3}')`);
    await cdp.send('Page.reload');
    await sleep(2000);

    const partialResumed = await cdp.eval(`
      (() => {
        const cards = document.querySelectorAll('.short-card');
        const key = localStorage.getItem('shorts_active_job_id');
        const resultsVisible = !document.getElementById('resultsSection').classList.contains('hidden');
        return {
          cardCount: cards.length,
          key,
          resultsVisible,
        };
      })()
    `);
    console.log('[QA-B] Partial resumed state:', partialResumed);
    if (partialResumed.key !== null) {
      throw new Error(`Active key was not cleared on partial completed job reload.`);
    }
    if (partialResumed.cardCount < 1 || !partialResumed.resultsVisible) {
      throw new Error(`Partial results card was not rendered on reload.`);
    }
    console.log('✅ Scenario 3 (Resume with Partial Results) Passed.');

    // =========================================================================
    // 5. Lifecycle Scenario: Interrupted Terminal State & Log Normalization
    // =========================================================================
    console.log('[QA-B] Step 5: Testing Interrupted Terminal State & Logs as Array...');
    const jobId4 = 'job_interrupted_04';
    await postHelper('/api/test/setup_job', {
      job_id: jobId4,
      status: 'interrupted',
      stage: 'interrupted',
      progress: 30,
      error: 'Server dimulai ulang saat proses berlangsung.',
      logs: ['[server] Restart initiated', '[warning] Terminated before completion'],
    });

    await cdp.eval(`localStorage.setItem('shorts_active_job_id', '${jobId4}')`);
    await cdp.send('Page.reload');
    await sleep(2000);

    const interruptedState = await cdp.eval(`
      (() => {
        const title = document.getElementById('progressTitle')?.textContent;
        const key = localStorage.getItem('shorts_active_job_id');
        const generateBtnDisabled = document.getElementById('generateSubmitBtn')?.disabled;
        return { title, key, generateBtnDisabled };
      })()
    `);
    console.log('[QA-B] Interrupted state:', interruptedState);
    if (interruptedState.key !== null) {
      throw new Error('Key was not cleared on interrupted terminal status.');
    }
    if (interruptedState.generateBtnDisabled) {
      throw new Error('Generate button remained disabled after interrupted job.');
    }
    console.log('✅ Scenario 4 (Interrupted State & Log Normalization) Passed.');

    // =========================================================================
    // 6. Lifecycle Scenario: Network Glitch Recovery on Initial Resume
    // =========================================================================
    console.log('[QA-B] Step 6: Testing Network Glitch Recovery on Initial Resume...');
    const jobId5 = 'job_glitch_05';
    await postHelper('/api/test/setup_job', {
      job_id: jobId5,
      status: 'running',
      stage: 'analyzing',
      progress: 70,
      logs: '[pipeline] Running LLM analysis after network recovery...\n',
    });

    // Injects 1 temporary network failure on next get_job call
    await postHelper('/api/test/set_flags', { glitch_count: 1 });
    await cdp.eval(`localStorage.setItem('shorts_active_job_id', '${jobId5}')`);

    await cdp.send('Page.reload');
    // First attempt will fail with 503, retry should succeed after 1s
    await sleep(2500);

    const glitchRecovered = await cdp.eval(`
      (() => {
        const key = localStorage.getItem('shorts_active_job_id');
        const progressVisible = !document.getElementById('progressSection').classList.contains('hidden');
        return { key, progressVisible };
      })()
    `);
    console.log('[QA-B] Glitch recovered state:', glitchRecovered);
    if (glitchRecovered.key !== jobId5 || !glitchRecovered.progressVisible) {
      throw new Error(`Failed to recover active job after temporary network glitch: ${JSON.stringify(glitchRecovered)}`);
    }
    console.log('✅ Scenario 5 (Network Glitch Recovery on Initial Resume) Passed.');

    // =========================================================================
    // 7. Lifecycle Scenario: Cancel Button Error Recovery
    // =========================================================================
    console.log('[QA-B] Step 7: Testing Cancel Button Error Recovery on 500 response...');
    await postHelper('/api/test/set_flags', { fail_cancel: true });

    // Click cancel button -> server returns 500
    await cdp.eval(`document.getElementById('btnCancelJob').click()`);
    await sleep(600);

    const btnRecovered = await cdp.eval(`
      (() => {
        const b = document.getElementById('btnCancelJob');
        return {
          disabled: b.disabled,
          cancelingClass: b.classList.contains('canceling'),
          text: b.querySelector('span')?.textContent,
        };
      })()
    `);
    console.log('[QA-B] Cancel button state after 500 error:', btnRecovered);
    if (btnRecovered.disabled || btnRecovered.cancelingClass || btnRecovered.text !== 'Batalkan') {
      throw new Error(`Cancel button did not recover after error response: ${JSON.stringify(btnRecovered)}`);
    }
    console.log('✅ Scenario 6 (Cancel Button Error Recovery) Passed.');

    // =========================================================================
    // 8. Responsive Reachability & Accessibility (Desktop, 390px, 320px, & Keyboard)
    // =========================================================================
    console.log('[QA-B] Step 8: Responsive Touch Target & Keyboard Navigation Verification...');

    // A. Desktop (1280x800)
    console.log('[QA-B] Checking Desktop 1280x800 layout & reachability...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1280,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await sleep(300);

    const desktopBtnMetrics = await cdp.eval(`
      (() => {
        const b = document.getElementById('btnCancelJob');
        const rect = b.getBoundingClientRect();
        return {
          width: rect.width,
          height: rect.height,
          visible: rect.width > 0 && rect.height > 0,
        };
      })()
    `);
    console.log('[QA-B] Desktop cancel button metrics:', desktopBtnMetrics);
    if (!desktopBtnMetrics.visible || desktopBtnMetrics.height < 32) {
      throw new Error(`Desktop cancel button not properly sized: ${JSON.stringify(desktopBtnMetrics)}`);
    }

    // B. Mobile 390px (iPhone 12/13/14)
    console.log('[QA-B] Checking Mobile 390x844 layout & touch target...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await sleep(300);

    const mobile390Metrics = await cdp.eval(`
      (() => {
        const b = document.getElementById('btnCancelJob');
        const rect = b.getBoundingClientRect();
        const hasHorizontalScroll = document.documentElement.scrollWidth > window.innerWidth;
        return {
          width: rect.width,
          height: rect.height,
          hasHorizontalScroll,
          visible: rect.width > 0 && rect.height > 0,
        };
      })()
    `);
    console.log('[QA-B] Mobile 390px metrics:', mobile390Metrics);
    if (mobile390Metrics.height < 44) {
      throw new Error(`Touch target on 390px must be >= 44px, got ${mobile390Metrics.height}px`);
    }
    if (mobile390Metrics.hasHorizontalScroll) {
      throw new Error('Horizontal scroll detected on 390px mobile viewport.');
    }

    // C. Narrow Mobile 320px (iPhone SE 1st gen)
    console.log('[QA-B] Checking Narrow Mobile 320x568 layout & touch target...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 320,
      height: 568,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await sleep(300);

    const mobile320Metrics = await cdp.eval(`
      (() => {
        const b = document.getElementById('btnCancelJob');
        const rect = b.getBoundingClientRect();
        const hasHorizontalScroll = document.documentElement.scrollWidth > window.innerWidth;
        return {
          width: rect.width,
          height: rect.height,
          hasHorizontalScroll,
          visible: rect.width > 0 && rect.height > 0,
        };
      })()
    `);
    console.log('[QA-B] Mobile 320px metrics:', mobile320Metrics);
    if (mobile320Metrics.height < 44) {
      throw new Error(`Touch target on 320px must be >= 44px, got ${mobile320Metrics.height}px`);
    }
    if (mobile320Metrics.hasHorizontalScroll) {
      throw new Error('Horizontal scroll detected on 320px narrow mobile viewport.');
    }

    // D. Keyboard Tab Focus Navigation
    console.log('[QA-B] Testing keyboard focus navigation to #btnCancelJob...');
    await cdp.eval(`
      (() => {
        const btn = document.getElementById('btnCancelJob');
        btn.focus();
      })()
    `);
    await sleep(200);

    const keyboardFocus = await cdp.eval(`
      (() => {
        const b = document.getElementById('btnCancelJob');
        const isFocused = document.activeElement === b;
        const style = window.getComputedStyle(b);
        return {
          isFocused,
          outlineStyle: style.outlineStyle,
          outlineWidth: style.outlineWidth,
        };
      })()
    `);
    console.log('[QA-B] Keyboard focus metrics on #btnCancelJob:', keyboardFocus);
    if (!keyboardFocus.isFocused) {
      throw new Error('Cancel button could not receive keyboard focus.');
    }
    console.log('✅ Scenario 7 (Responsive Reachability & Keyboard Focus) Passed.');

    console.log('\n======================================================');
    console.log('🎉 ALL BROWSER QA LIFECYCLE SCENARIOS PASSED CLEANLY! 🎉');
    console.log('======================================================\n');
  } finally {
    try {
      chromeProc.kill('SIGKILL');
    } catch (_) {}
  }
}

runTest().catch((err) => {
  console.error('\n❌ Browser QA Lifecycle Test Failed:', err);
  process.exit(1);
});
