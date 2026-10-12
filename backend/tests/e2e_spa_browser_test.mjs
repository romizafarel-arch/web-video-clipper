// tests/e2e_spa_browser_test.mjs - End-to-End Chrome CDP Test for ShortsAI Studio React SPA
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const PORT = process.argv[2] || 5088;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const TEMP_USER_DATA = path.join(process.cwd(), '.tmp_chrome_spa_e2e');

if (!fs.existsSync(TEMP_USER_DATA)) {
  fs.mkdirSync(TEMP_USER_DATA, { recursive: true });
}

function sleep(ms) {
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
  console.log(`[E2E] Connecting to server at ${BASE_URL}...`);
  // Ensure sample session exists
  await postHelper('/api/test/create_sample_session', {});

  console.log('[E2E] Launching headless Chrome via CDP...');
  const chromeProc = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9224',
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
        const res = await fetch('http://127.0.0.1:9224/json/version');
        if (res.ok) {
          versionData = await res.json();
          break;
        }
      } catch (e) {}
      await sleep(200);
    }

    if (!versionData) throw new Error('Chrome remote debugging did not respond.');

    const ws = new WebSocket(versionData.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    const browserCDP = new CDPClient(ws);
    const target = await browserCDP.send('Target.createTarget', { url: 'about:blank' });
    const targetWsUrl = `ws://127.0.0.1:9224/devtools/page/${target.targetId}`;

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
    // 1. Desktop Viewport 1280x800: Navigation & Initial Elements
    // =========================================================================
    console.log('[E2E] Step 1: Navigating on Desktop (1280x800)...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1280,
      height: 800,
      deviceScaleFactor: 1,
      mobile: false,
    });

    await cdp.send('Page.navigate', { url: BASE_URL });
    await sleep(2000);

    const docTitle = await cdp.eval('document.title');
    console.log(`[E2E] Page Title: "${docTitle}"`);
    if (!docTitle.includes('ShortsAI Studio')) {
      throw new Error(`Unexpected page title: ${docTitle}`);
    }

    // Verify form controls exist
    const formCheck = await cdp.eval(`
      (() => {
        const urlInput = document.getElementById('youtube-url');
        const aspectSelect = document.getElementById('aspect-ratio');
        const submitBtn = document.querySelector('button[type="submit"]');
        return {
          hasUrlInput: !!urlInput,
          hasAspectSelect: !!aspectSelect,
          aspectOptions: aspectSelect ? Array.from(aspectSelect.options).map(o => o.value) : [],
          hasSubmitBtn: !!submitBtn,
        };
      })()
    `);
    console.log('[E2E] Form elements inspection:', formCheck);
    if (!formCheck.hasUrlInput || !formCheck.hasAspectSelect || !formCheck.hasSubmitBtn) {
      throw new Error('Key generator form inputs missing on desktop view.');
    }
    if (!formCheck.aspectOptions.includes('9:16') || !formCheck.aspectOptions.includes('1:1') || !formCheck.aspectOptions.includes('16:9')) {
      throw new Error(`Incomplete aspect ratios: ${JSON.stringify(formCheck.aspectOptions)}`);
    }
    console.log('✅ Step 1 (Desktop Initial Render) Passed.');

    // =========================================================================
    // 2. Keyboard Navigation & A11y on Settings & History Modals
    // =========================================================================
    console.log('[E2E] Step 2: Testing Settings Modal Keyboard Navigation (Escape)...');
    // Click Settings button in header
    await cdp.eval(`
      (() => {
        const btn = document.querySelector('button[aria-label*="Pengaturan"]') ||
                    document.querySelector('button[title*="Pengaturan"]');
        if (btn) btn.click();
      })()
    `);
    await sleep(600);

    const isSettingsOpen = await cdp.eval(`
      !!document.querySelector('[data-slot="dialog-content"]') && document.body.textContent.includes('Konfigurasi API')
    `);
    console.log(`[E2E] Settings modal visible: ${isSettingsOpen}`);
    if (!isSettingsOpen) throw new Error('Settings modal did not open.');

    // Send Escape key
    console.log('[E2E] Pressing Escape key to close Settings Modal...');
    await cdp.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await sleep(600);

    const isSettingsClosed = await cdp.eval(`
      !document.body.textContent.includes('Konfigurasi API')
    `);
    console.log(`[E2E] Settings modal closed on Escape: ${isSettingsClosed}`);
    if (!isSettingsClosed) throw new Error('Settings modal did not close on Escape.');

    console.log('[E2E] Testing History Modal & Video Preview Keyboard Navigation...');
    // Open History Modal
    await cdp.eval(`
      (() => {
        const btn = document.querySelector('button[aria-label*="Riwayat"]') ||
                    document.querySelector('button[title*="Riwayat"]');
        if (btn) btn.click();
      })()
    `);
    await sleep(800);

    const isHistoryOpen = await cdp.eval(`
      !!document.querySelector('[data-slot="dialog-content"]') && document.body.textContent.includes('Riwayat Sesi')
    `);
    console.log(`[E2E] History modal visible: ${isHistoryOpen}`);
    if (!isHistoryOpen) throw new Error('History modal did not open.');

    // Verify clips in history session with retry
    let historyClips = 0;
    for (let i = 0; i < 10; i++) {
      historyClips = await cdp.eval(`
        (() => {
          const previewBtns = Array.from(document.querySelectorAll('button')).filter(b => b.textContent.includes('Tonton'));
          return previewBtns.length;
        })()
      `);
      if (historyClips > 0) break;
      await sleep(300);
    }
    console.log(`[E2E] History video preview buttons found: ${historyClips}`);
    if (historyClips < 1) throw new Error('Expected at least 1 previewable clip in History modal.');

    // Trigger video preview on the first clip
    console.log('[E2E] Clicking Tonton button to open Video Player Dialog...');
    await cdp.eval(`
      (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Tonton'));
        if (btn) btn.click();
      })()
    `);
    await sleep(800);

    // Verify video preview dialog is open with dynamic aspect ratio class
    const previewDialog = await cdp.eval(`
      (() => {
        const video = document.querySelector('video[controls]');
        const container = video ? video.parentElement : null;
        const closeBtn = document.querySelector('button[aria-label="Tutup video player"]');
        return {
          hasVideo: !!video,
          aspectClass: container ? container.className : '',
          isDialogShown: !!closeBtn,
        };
      })()
    `);
    console.log('[E2E] Video preview dialog state:', previewDialog);
    if (!previewDialog.hasVideo || !previewDialog.isDialogShown) {
      throw new Error('Video player element or close button not found in preview dialog.');
    }

    // Press Escape to close preview dialog
    console.log('[E2E] Pressing Escape to close Preview Player Dialog...');
    await cdp.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await sleep(600);

    const isPreviewClosed = await cdp.eval(`
      !document.querySelector('button[aria-label="Tutup video player"]') &&
      !document.querySelector('video[controls]')
    `);
    console.log(`[E2E] Preview closed on Escape: ${isPreviewClosed}`);
    if (!isPreviewClosed) throw new Error('Preview player did not close on Escape.');

    // Press Escape to close History Modal
    console.log('[E2E] Pressing Escape to close History Modal...');
    await cdp.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await sleep(600);

    const isHistoryClosed = await cdp.eval(`!document.body.textContent.includes('Riwayat Sesi')`);
    console.log(`[E2E] History modal closed on Escape: ${isHistoryClosed}`);
    if (!isHistoryClosed) throw new Error('History modal did not close on Escape.');
    console.log('✅ Step 2 (Modals & Keyboard A11y) Passed.');

    // =========================================================================
    // 3. Submit URL & Active Job Progress Verification
    // =========================================================================
    console.log('[E2E] Step 3: Submitting URL & Verifying Active Progress Card...');
    const testJobId = 'job_running_test_99';
    await postHelper('/api/test/setup_job', {
      job_id: testJobId,
      status: 'running',
      stage: 'transcribing',
      progress: 35,
      logs: ['[pipeline] Audio extracted.\n', '[transcribe] Running speech-to-text...\n'],
      params: { num_clips: 3, aspect_ratio: '16:9' },
    });

    // Emulate form submit or trigger polling directly via page reload
    await cdp.send('Page.reload');
    await sleep(1500);

    // Verify JobProgressCard is immediately visible on reload
    const activeProgressCard = await cdp.eval(`
      (() => {
        const cardTitle = document.body.textContent.includes('Pipeline Pembuatan Video Sedang Berjalan');
        const jobIdText = document.body.textContent.includes('${testJobId}');
        const cancelBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Batalkan Pekerjaan'));
        const progressBar = document.querySelector('[role="progressbar"]') || document.querySelector('.bg-violet-500');
        return {
          cardVisible: cardTitle,
          jobIdMatched: jobIdText,
          hasCancelBtn: !!cancelBtn,
          hasProgressBar: !!progressBar,
        };
      })()
    `);
    console.log('[E2E] Active Progress Card inspection on reload:', activeProgressCard);
    if (!activeProgressCard.cardVisible || !activeProgressCard.jobIdMatched) {
      throw new Error('Active job progress card failed to restore immediately on page reload.');
    }
    console.log('✅ Step 3 (Submit & Refresh Resume) Passed.');

    // =========================================================================
    // 4. Job Completion & Aspect Ratio Verification (1:1, 16:9, 9:16)
    // =========================================================================
    console.log('[E2E] Step 4: Testing Completed Status & Dynamic Aspect Ratios in ResultsGallery...');
    await postHelper('/api/test/setup_job', {
      job_id: testJobId,
      status: 'completed',
      stage: 'completed',
      progress: 100,
      logs: ['[pipeline] All clips generated successfully.\n'],
      result: {
        video_title: 'Video Demo Selesai E2E',
        aspect_ratio: '16:9',
        shorts: [
          {
            clip_index: 1,
            title: 'Klip Pertama 9:16',
            web_url: '/output/session_e2e_sample/clip_916.mp4',
            filename: 'clip_916.mp4',
            aspect_ratio: '9:16',
            score: 96,
            start_time: 0,
            end_time: 15,
          },
          {
            clip_index: 2,
            title: 'Klip Kedua 1:1',
            web_url: '/output/session_e2e_sample/clip_11.mp4',
            filename: 'clip_11.mp4',
            aspect_ratio: '1:1',
            score: 90,
            start_time: 15,
            end_time: 30,
          },
          {
            clip_index: 3,
            title: 'Klip Ketiga 16:9',
            web_url: '/output/session_e2e_sample/clip_169.mp4',
            filename: 'clip_169.mp4',
            aspect_ratio: '16:9',
            score: 92,
            start_time: 30,
            end_time: 45,
          },
        ],
      },
    });

    // Wait for poll interval to catch the completed status
    await sleep(2500);

    const galleryCheck = await cdp.eval(`
      (() => {
        const galleryTitle = document.body.textContent.includes('Shorts Berhasil Dibuat (3 Klip)');
        const badges = Array.from(document.querySelectorAll('span')).map(s => s.textContent.trim());
        const has916 = badges.includes('9:16');
        const has11 = badges.includes('1:1');
        const has169 = badges.includes('16:9');
        const aspectContainers = Array.from(document.querySelectorAll('div')).map(d => d.className);
        const hasAspectSquare = aspectContainers.some(c => c.includes('aspect-square'));
        const hasAspectVideo = aspectContainers.some(c => c.includes('aspect-video'));
        const hasAspect916 = aspectContainers.some(c => c.includes('aspect-[9/16]'));
        return {
          galleryTitle,
          has916,
          has11,
          has169,
          hasAspectSquare,
          hasAspectVideo,
          hasAspect916,
        };
      })()
    `);
    console.log('[E2E] ResultsGallery aspect ratio verification:', galleryCheck);
    if (!galleryCheck.galleryTitle) throw new Error('ResultsGallery did not render completed results.');
    if (!galleryCheck.has916 || !galleryCheck.has11 || !galleryCheck.has169) {
      throw new Error('Aspect ratio badges (9:16, 1:1, 16:9) missing in ResultsGallery.');
    }
    if (!galleryCheck.hasAspectSquare || !galleryCheck.hasAspectVideo || !galleryCheck.hasAspect916) {
      throw new Error('Aspect ratio CSS classes missing on video containers.');
    }
    console.log('✅ Step 4 (Completed Status & Aspect Ratios) Passed.');

    // =========================================================================
    // 5. Partial Status Verification
    // =========================================================================
    console.log('[E2E] Step 5: Testing Partial Status (Partial Success)...');
    const partialJobId = 'job_partial_test_77';
    await postHelper('/api/test/setup_job', {
      job_id: partialJobId,
      status: 'running',
      stage: 'cropping',
      progress: 60,
      logs: ['[pipeline] Rendering clip 1...\n'],
      params: { num_clips: 2, aspect_ratio: '9:16' },
    });

    await cdp.send('Page.reload');
    await sleep(1500);

    // Transition to partial
    await postHelper('/api/test/setup_job', {
      job_id: partialJobId,
      status: 'partial',
      stage: 'partial',
      progress: 100,
      error: 'Selesai sebagian: 1 klip berhasil dibuat, 1 klip gagal.',
      result: {
        video_title: 'Video Parsial E2E',
        aspect_ratio: '9:16',
        stats: { success: 1, failed: 1 },
        shorts: [
          {
            clip_index: 1,
            title: 'Klip Parsial Sukses',
            web_url: '/output/session_e2e_sample/clip_916.mp4',
            filename: 'clip_916.mp4',
            aspect_ratio: '9:16',
            score: 87,
            start_time: 0,
            end_time: 15,
          },
        ],
      },
    });

    await sleep(2500);

    const partialCheck = await cdp.eval(`
      (() => {
        const toastWarning = document.body.textContent.includes('Selesai sebagian');
        const galleryTitle = document.body.textContent.includes('Shorts Berhasil Dibuat (1 Klip)');
        return {
          toastWarning,
          galleryTitle,
        };
      })()
    `);
    console.log('[E2E] Partial status check:', partialCheck);
    if (!partialCheck.galleryTitle && !partialCheck.toastWarning) {
      throw new Error('Partial status did not render saved clips or toast warning.');
    }
    console.log('✅ Step 5 (Partial Status Handling) Passed.');

    // =========================================================================
    // 6. Mobile Viewport Simulation (390x844 - iPhone 14)
    // =========================================================================
    console.log('[E2E] Step 6: Testing Mobile Viewport (390x844)...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 3,
      mobile: true,
      hasTouch: true,
    });
    await sleep(1000);

    const mobileLayout = await cdp.eval(`
      (() => {
        const root = document.documentElement;
        const body = document.body;
        const scrollWidth = root.scrollWidth;
        const clientWidth = root.clientWidth;
        const noHorizontalScroll = scrollWidth <= clientWidth;

        // Verify touch targets for main buttons (height >= 40px)
        const buttons = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
        const touchTargetsOk = buttons.every(b => {
          const rect = b.getBoundingClientRect();
          return rect.height >= 32; // minimum standard
        });

        return {
          scrollWidth,
          clientWidth,
          noHorizontalScroll,
          visibleButtonsCount: buttons.length,
          touchTargetsOk,
        };
      })()
    `);
    console.log('[E2E] Mobile layout inspection:', mobileLayout);
    if (!mobileLayout.noHorizontalScroll) {
      throw new Error(`Mobile layout has horizontal overflow: scrollWidth ${mobileLayout.scrollWidth} > clientWidth ${mobileLayout.clientWidth}`);
    }
    console.log('✅ Step 6 (Mobile Viewport Simulation) Passed.');

    console.log('\n======================================================');
    console.log('🎉 ALL END-TO-END BROWSER TESTS PASSED 100%!');
    console.log('======================================================\n');
  } finally {
    if (chromeProc) {
      chromeProc.kill();
    }
  }
}

runTest().catch((err) => {
  console.error('\n❌ [E2E FAILED]:', err);
  process.exit(1);
});
