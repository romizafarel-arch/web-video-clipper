/**
 * AI YouTube Shorts Generator — Frontend Client Script
 */

let titleFlasher = null;

function requestNotifPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    try {
      Notification.requestPermission().catch(() => {});
    } catch (_) {}
  }
}

function playNotificationSound() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, now); // D5
    osc.frequency.setValueAtTime(880, now + 0.15); // A5

    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.55);
  } catch (_) {}
}

function flashTabTitle(alertText) {
  if (!document.hidden) return;
  const originalTitle = document.title;
  let toggle = false;
  clearInterval(titleFlasher);
  titleFlasher = setInterval(() => {
    if (!document.hidden) {
      clearInterval(titleFlasher);
      document.title = originalTitle;
      return;
    }
    document.title = toggle ? alertText : originalTitle;
    toggle = !toggle;
  }, 900);
}

function sendBrowserNotif(title, body) {
  // 1. Suara notif (tetap terdengar walau lagi di tab lain / minimize)
  playNotificationSound();

  // 2. Judul tab berkedip saat berada di tab lain
  flashTabTitle('🔔 (SELESAI) Reef Clipper');

  // 3. Notifikasi sistem OS (jika izin sudah diberikan)
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      const notif = new Notification(title, { body });
      notif.onclick = () => {
        window.focus();
        notif.close();
      };
    } catch (_) {}
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const generateForm = document.getElementById('generateForm');
  const videoUrlInput = document.getElementById('videoUrlInput');
  const pasteBtn = document.getElementById('pasteBtn');
  const clipCountControl = document.getElementById('clipCountControl');
  const numClipsInput = document.getElementById('numClipsInput');
  const modeSelect = document.getElementById('modeSelect');
  const aspectRatioSelect = document.getElementById('aspectRatioSelect');
  const framingModeSelect = document.getElementById('framingModeSelect');
  const gamingPresetCell = document.getElementById('gamingPresetCell');
  const gamingPresetSelect = document.getElementById('gamingPresetSelect');
  const gamingCustomBoxCell = document.getElementById('gamingCustomBoxCell');
  const gamingCustomTop = document.getElementById('gamingCustomTop');
  const gamingCustomMid = document.getElementById('gamingCustomMid');
  const gamingCustomBot = document.getElementById('gamingCustomBot');
  const subtitleStyleSelect = document.getElementById('subtitleStyleSelect');
  const formatSelect = document.getElementById('formatSelect');
  const llmProviderSelect = document.getElementById('llmProviderSelect');
  const transcriberSelect = document.getElementById('transcriberSelect');
  const generateSubmitBtn = document.getElementById('generateSubmitBtn');

  // Model Controls (LLM & Transcriber)
  const btnLoadLlmModels = document.getElementById('btnLoadLlmModels');
  const llmModelSelect = document.getElementById('llmModelSelect');
  const btnTestLlmModel = document.getElementById('btnTestLlmModel');
  const customLlmBox = document.getElementById('customLlmBox');
  const customLlmInput = document.getElementById('customLlmInput');
  const llmModelStatus = document.getElementById('llmModelStatus');

  const btnLoadTransModels = document.getElementById('btnLoadTransModels');
  const transModelSelect = document.getElementById('transModelSelect');
  const btnTestTransModel = document.getElementById('btnTestTransModel');
  const customTransBox = document.getElementById('customTransBox');
  const customTransInput = document.getElementById('customTransInput');
  const transModelStatus = document.getElementById('transModelStatus');

  // Status & Nav
  const apiStatusBadge = document.getElementById('apiStatusBadge');
  const statusLabel = document.getElementById('statusLabel');
  const historyBtn = document.getElementById('historyBtn');
  const historyCountBadge = document.getElementById('historyCountBadge');
  const settingsBtn = document.getElementById('settingsBtn');

  // Progress Section
  const progressSection = document.getElementById('progressSection');
  const progressTitle = document.getElementById('progressTitle');
  const progressSubtitle = document.getElementById('progressSubtitle');
  const progressTimer = document.getElementById('progressTimer');
  const btnCancelJob = document.getElementById('btnCancelJob');
  const progressBarFill = document.getElementById('progressBarFill');
  const terminalLogBody = document.getElementById('terminalLogBody');
  const terminalToggleBtn = document.getElementById('terminalToggleBtn');

  // View Switcher & Animation Container
  const tabAnimationView = document.getElementById('tabAnimationView');
  const tabTerminalView = document.getElementById('tabTerminalView');
  const logAlertBadge = document.getElementById('logAlertBadge');
  const animationStatusText = document.getElementById('animationStatusText');
  const animationViewContainer = document.getElementById('animationViewContainer');
  const terminalViewContainer = document.getElementById('terminalViewContainer');

  const animScenes = {
    download: document.getElementById('sceneDownload'),
    transcribe: document.getElementById('sceneTranscribe'),
    analyze: document.getElementById('sceneAnalyze'),
    crop: document.getElementById('sceneCrop'),
    completed: document.getElementById('sceneCompleted'),
  };

  // Stepper Elements
  const stepNodes = {
    download: document.getElementById('stepDownload'),
    transcribe: document.getElementById('stepTranscribe'),
    analyze: document.getElementById('stepAnalyze'),
    crop: document.getElementById('stepCrop'),
  };
  const stepLines = {
    line1: document.getElementById('line1'),
    line2: document.getElementById('line2'),
    line3: document.getElementById('line3'),
  };

  // Results Section
  const resultsSection = document.getElementById('resultsSection');
  const resultsMeta = document.getElementById('resultsMeta');
  const shortsGrid = document.getElementById('shortsGrid');
  const newGenerationBtn = document.getElementById('newGenerationBtn');

  // Modals
  const settingsModal = document.getElementById('settingsModal');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
  const settingsForm = document.getElementById('settingsForm');
  const geminiApiKeyInput = document.getElementById('geminiApiKeyInput');
  const geminiTransModelInput = document.getElementById('geminiTransModelInput');
  const geminiModelInput = document.getElementById('geminiModelInput');
  const openaiApiKeyInput = document.getElementById('openaiApiKeyInput');
  const openaiBaseUrlInput = document.getElementById('openaiBaseUrlInput');
  const muapiKeyInput = document.getElementById('muapiKeyInput');
  const autoDeleteSourceInput = document.getElementById('autoDeleteSourceInput');
  const autoDeleteSourceGenInput = document.getElementById('autoDeleteSourceGenInput');

  const historyModal = document.getElementById('historyModal');
  const closeHistoryBtn = document.getElementById('closeHistoryBtn');
  const historyListContainer = document.getElementById('historyListContainer');

  const videoModal = document.getElementById('videoModal');
  const closeVideoModalBtn = document.getElementById('closeVideoModalBtn');
  const modalVideoPlayer = document.getElementById('modalVideoPlayer');
  const modalVideoTitle = document.getElementById('modalVideoTitle');

  const editorModal = document.getElementById('editorModal');
  const closeEditorBtn = document.getElementById('closeEditorBtn');
  const cancelEditorBtn = document.getElementById('cancelEditorBtn');
  const editorForm = document.getElementById('editorForm');
  const editSessionFolder = document.getElementById('editSessionFolder');
  const editClipIndex = document.getElementById('editClipIndex');
  const editScore = document.getElementById('editScore');
  const editClipTitle = document.getElementById('editClipTitle');
  const editClipHook = document.getElementById('editClipHook');
  const editStartTime = document.getElementById('editStartTime');
  const editEndTime = document.getElementById('editEndTime');
  const editAspectRatio = document.getElementById('editAspectRatio');
  const editFramingMode = document.getElementById('editFramingMode');
  const editGamingPresetRow = document.getElementById('editGamingPresetRow');
  const editGamingPreset = document.getElementById('editGamingPreset');
  const editGamingCustomRow = document.getElementById('editGamingCustomRow');
  const editGamingCustomTop = document.getElementById('editGamingCustomTop');
  const editGamingCustomMid = document.getElementById('editGamingCustomMid');
  const editGamingCustomBot = document.getElementById('editGamingCustomBot');
  const editGamingBoxJson = document.getElementById('editGamingBoxJson');
  const cloudGamingNotice = document.getElementById('cloudGamingNotice');
  const btnPreviewGaming = document.getElementById('btnPreviewGaming');
  const editorVideoWrapper = document.getElementById('editorVideoWrapper');
  const facecamOverlay = document.getElementById('facecamOverlay');
  const facecamBoundingBox = document.getElementById('facecamBoundingBox');
  const facecamCoordsDisplay = document.getElementById('facecamCoordsDisplay');
  const gamingFacecamToolbar = document.getElementById('gamingFacecamToolbar');
  const gamingPreviewCanvas = document.getElementById('gamingPreviewCanvas');
  const btnAutoDetectFacecam = document.getElementById('btnAutoDetectFacecam');
  const facecamDetectStatus = document.getElementById('facecamDetectStatus');
  const editSubtitleStyle = document.getElementById('editSubtitleStyle');
  const editBurnSubtitles = document.getElementById('editBurnSubtitles');
  const saveRenderEditorBtn = document.getElementById('saveRenderEditorBtn');
  const editorStatusMessage = document.getElementById('editorStatusMessage');
  const editorVideoPlayer = document.getElementById('editorVideoPlayer');
  const editorTimeDisplay = document.getElementById('editorTimeDisplay');
  const btnSetInFromPlayer = document.getElementById('btnSetInFromPlayer');
  const btnSetOutFromPlayer = document.getElementById('btnSetOutFromPlayer');

  // State
  let currentJobId = null;
  let pollInterval = null;
  let timerInterval = null;
  let timerSeconds = 0;
  let activeConfig = {};

  // 1. Initial Config & Status Check
  async function loadConfig() {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      activeConfig = data;

      // Update Form defaults
      if (data.llm_provider) llmProviderSelect.value = data.llm_provider;
      if (data.transcriber_provider) transcriberSelect.value = data.transcriber_provider;

      geminiApiKeyInput.value = data.gemini_key_masked || '';
      if (data.gemini_transcriber_model && geminiTransModelInput) {
        geminiTransModelInput.value = data.gemini_transcriber_model;
      }
      if (data.gemini_model && geminiModelInput) {
        geminiModelInput.value = data.gemini_model;
      }
      openaiApiKeyInput.value = data.openai_key_masked || '';
      openaiBaseUrlInput.value = data.openai_base_url || '';
      muapiKeyInput.value = data.muapi_key_masked || '';

      if (data.auto_delete_source_video !== undefined) {
        const isAutoDel = !!data.auto_delete_source_video;
        if (autoDeleteSourceInput) autoDeleteSourceInput.checked = isAutoDel;
        if (autoDeleteSourceGenInput) autoDeleteSourceGenInput.checked = isAutoDel;
      }

      // Header status indicator
      if (data.has_gemini_key || data.has_openai_key || data.has_muapi_key) {
        apiStatusBadge.classList.add('ready');
        const providers = [];
        if (data.has_gemini_key) providers.push('Gemini');
        if (data.has_openai_key) providers.push('OpenAI/APMIX');
        if (data.has_muapi_key) providers.push('MuAPI');
        statusLabel.textContent = `Siap (${providers.join(', ')})`;
      } else {
        apiStatusBadge.classList.remove('ready');
        statusLabel.textContent = 'Kunci API Belum Diatur';
      }

      // Populate dynamic model lists
      await Promise.all([loadLlmModels(false), loadTranscriberModels(false)]);
    } catch (err) {
      console.error('Failed to load config:', err);
      statusLabel.textContent = 'Offline';
    }
  }

  // Model Management & Dynamic Loading
  function setModelStatus(element, text, type = 'green') {
    if (!element) return;
    const dot = element.querySelector('.status-dot');
    const msg = element.querySelector('.status-msg');
    if (dot) dot.className = `status-dot ${type}`;
    if (msg) msg.textContent = text;
  }

  async function loadLlmModels(forceRefresh = false) {
    if (!llmModelSelect) return;
    const provider = llmProviderSelect ? llmProviderSelect.value : 'gemini';

    if (btnLoadLlmModels) {
      btnLoadLlmModels.classList.add('loading');
      const icon = btnLoadLlmModels.querySelector('.spin-icon-target');
      if (icon) icon.classList.add('spinning');
    }
    setModelStatus(llmModelStatus, `Memuat daftar model ${provider}...`, 'yellow');

    try {
      const res = await fetch(`/api/models?provider=${encodeURIComponent(provider)}&refresh=${forceRefresh}`);
      const data = await res.json();
      const models = data.models || [];
      const currentSelected = llmModelSelect.value;

      llmModelSelect.innerHTML = '';
      if (models.length > 0) {
        models.forEach((m) => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = m.name + (m.recommended ? ' ★' : '');
          llmModelSelect.appendChild(opt);
        });
      } else {
        const opt = document.createElement('option');
        opt.value = provider === 'gemini' ? 'gemini-3.5-flash' : 'gpt-4o-mini';
        opt.textContent = opt.value;
        llmModelSelect.appendChild(opt);
      }

      const customOpt = document.createElement('option');
      customOpt.value = '__custom__';
      customOpt.textContent = '✏️ Tulis Model Custom...';
      llmModelSelect.appendChild(customOpt);

      const targetPref = provider === 'gemini'
        ? (activeConfig.gemini_model || 'gemini-3.5-flash')
        : (activeConfig.openai_model || 'gpt-4o-mini');

      if (Array.from(llmModelSelect.options).some(o => o.value === targetPref)) {
        llmModelSelect.value = targetPref;
      } else if (currentSelected && Array.from(llmModelSelect.options).some(o => o.value === currentSelected)) {
        llmModelSelect.value = currentSelected;
      } else if (llmModelSelect.options.length > 0) {
        llmModelSelect.selectedIndex = 0;
      }

      if (customLlmBox) {
        customLlmBox.classList.toggle('hidden', llmModelSelect.value !== '__custom__');
      }
      const activeName = llmModelSelect.value === '__custom__' ? (customLlmInput.value || 'Custom') : llmModelSelect.value;
      setModelStatus(llmModelStatus, `Model aktif: ${activeName}`, 'green');

      if (forceRefresh) {
        showToast(`Daftar model ${provider.toUpperCase()} berhasil dimuat (${data.raw_count || models.length} model)`, 'success');
      }
    } catch (e) {
      console.error('Failed to load LLM models:', e);
      setModelStatus(llmModelStatus, `Gagal memuat model: ${e.message}`, 'red');
    } finally {
      if (btnLoadLlmModels) {
        btnLoadLlmModels.classList.remove('loading');
        const icon = btnLoadLlmModels.querySelector('.spin-icon-target');
        if (icon) icon.classList.remove('spinning');
      }
    }
  }

  async function loadTranscriberModels(forceRefresh = false) {
    if (!transModelSelect) return;
    const provider = transcriberSelect ? transcriberSelect.value : 'gemini';

    if (btnLoadTransModels) {
      btnLoadTransModels.classList.add('loading');
      const icon = btnLoadTransModels.querySelector('.spin-icon-target');
      if (icon) icon.classList.add('spinning');
    }
    setModelStatus(transModelStatus, `Memuat model audio ${provider}...`, 'yellow');

    try {
      const res = await fetch(`/api/models?provider=${encodeURIComponent(provider)}&refresh=${forceRefresh}`);
      const data = await res.json();
      const models = provider === 'gemini' ? (data.transcribe_models || data.models || []) : (data.models || []);
      const currentSelected = transModelSelect.value;

      transModelSelect.innerHTML = '';
      if (models.length > 0) {
        models.forEach((m) => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = m.name + (m.recommended ? ' ★' : '');
          transModelSelect.appendChild(opt);
        });
      } else {
        const opt = document.createElement('option');
        opt.value = provider === 'gemini' ? 'gemini-3.5-transcribe' : 'base';
        opt.textContent = opt.value;
        transModelSelect.appendChild(opt);
      }

      const customOpt = document.createElement('option');
      customOpt.value = '__custom__';
      customOpt.textContent = '✏️ Tulis Model Custom...';
      transModelSelect.appendChild(customOpt);

      const targetPref = provider === 'gemini'
        ? (activeConfig.gemini_transcriber_model || 'gemini-3.5-transcribe')
        : (activeConfig.whisper_model || 'base');

      if (Array.from(transModelSelect.options).some(o => o.value === targetPref)) {
        transModelSelect.value = targetPref;
      } else if (currentSelected && Array.from(transModelSelect.options).some(o => o.value === currentSelected)) {
        transModelSelect.value = currentSelected;
      } else if (transModelSelect.options.length > 0) {
        transModelSelect.selectedIndex = 0;
      }

      if (customTransBox) {
        customTransBox.classList.toggle('hidden', transModelSelect.value !== '__custom__');
      }
      const activeName = transModelSelect.value === '__custom__' ? (customTransInput.value || 'Custom') : transModelSelect.value;
      setModelStatus(transModelStatus, `Model aktif: ${activeName}`, 'green');

      if (forceRefresh) {
        showToast(`Model transkripsi ${provider.toUpperCase()} berhasil dimuat (${data.raw_count || models.length} model)`, 'success');
      }
    } catch (e) {
      console.error('Failed to load Transcriber models:', e);
      setModelStatus(transModelStatus, `Gagal memuat model: ${e.message}`, 'red');
    } finally {
      if (btnLoadTransModels) {
        btnLoadTransModels.classList.remove('loading');
        const icon = btnLoadTransModels.querySelector('.spin-icon-target');
        if (icon) icon.classList.remove('spinning');
      }
    }
  }

  // Model Control Event Listeners
  if (llmProviderSelect) {
    llmProviderSelect.addEventListener('change', () => loadLlmModels(false));
  }
  if (transcriberSelect) {
    transcriberSelect.addEventListener('change', () => loadTranscriberModels(false));
  }

  if (llmModelSelect) {
    llmModelSelect.addEventListener('change', () => {
      const isCustom = llmModelSelect.value === '__custom__';
      if (customLlmBox) customLlmBox.classList.toggle('hidden', !isCustom);
      if (isCustom && customLlmInput) {
        customLlmInput.focus();
        setModelStatus(llmModelStatus, 'Model custom dipilih (silakan ketik ID)', 'yellow');
      } else {
        setModelStatus(llmModelStatus, `Model aktif: ${llmModelSelect.value}`, 'green');
      }
    });
  }

  if (customLlmInput) {
    customLlmInput.addEventListener('input', () => {
      if (llmModelSelect && llmModelSelect.value === '__custom__') {
        const val = customLlmInput.value.trim();
        setModelStatus(llmModelStatus, val ? `Model custom: ${val}` : 'Ketikkan ID model...', val ? 'green' : 'yellow');
      }
    });
  }

  if (transModelSelect) {
    transModelSelect.addEventListener('change', () => {
      const isCustom = transModelSelect.value === '__custom__';
      if (customTransBox) customTransBox.classList.toggle('hidden', !isCustom);
      if (isCustom && customTransInput) {
        customTransInput.focus();
        setModelStatus(transModelStatus, 'Model custom dipilih (silakan ketik ID)', 'yellow');
      } else {
        setModelStatus(transModelStatus, `Model aktif: ${transModelSelect.value}`, 'green');
      }
    });
  }

  if (customTransInput) {
    customTransInput.addEventListener('input', () => {
      if (transModelSelect && transModelSelect.value === '__custom__') {
        const val = customTransInput.value.trim();
        setModelStatus(transModelStatus, val ? `Model custom: ${val}` : 'Ketikkan ID model...', val ? 'green' : 'yellow');
      }
    });
  }

  if (btnLoadLlmModels) {
    btnLoadLlmModels.addEventListener('click', () => loadLlmModels(true));
  }
  if (btnLoadTransModels) {
    btnLoadTransModels.addEventListener('click', () => loadTranscriberModels(true));
  }

  if (btnTestLlmModel) {
    btnTestLlmModel.addEventListener('click', async () => {
      const provider = llmProviderSelect ? llmProviderSelect.value : 'gemini';
      let model = llmModelSelect ? llmModelSelect.value : '';
      if (model === '__custom__' && customLlmInput) {
        model = customLlmInput.value.trim();
      }
      if (!model) {
        showToast('Pilih atau ketik model yang ingin diuji!', 'error');
        return;
      }

      btnTestLlmModel.classList.add('testing');
      const textSpan = btnTestLlmModel.querySelector('span');
      if (textSpan) textSpan.textContent = 'Menguji...';
      setModelStatus(llmModelStatus, `Menguji koneksi ke ${model}...`, 'yellow');

      try {
        const res = await fetch('/api/models/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider, model }),
        });
        const data = await res.json();
        if (data.success) {
          setModelStatus(llmModelStatus, `Online (${data.latency_ms}ms) • ${data.model}`, 'green');
          showToast(data.message, 'success');
        } else {
          setModelStatus(llmModelStatus, `Gagal: ${data.error || 'Tidak ada respons'}`, 'red');
          showToast(`Gagal uji model: ${data.error}`, 'error');
        }
      } catch (err) {
        setModelStatus(llmModelStatus, `Error: ${err.message}`, 'red');
        showToast(`Koneksi error: ${err.message}`, 'error');
      } finally {
        btnTestLlmModel.classList.remove('testing');
        if (textSpan) textSpan.textContent = 'Tes';
      }
    });
  }

  if (btnTestTransModel) {
    btnTestTransModel.addEventListener('click', async () => {
      const provider = transcriberSelect ? transcriberSelect.value : 'gemini';
      let model = transModelSelect ? transModelSelect.value : '';
      if (model === '__custom__' && customTransInput) {
        model = customTransInput.value.trim();
      }
      if (!model) {
        showToast('Pilih atau ketik model transkripsi yang ingin diuji!', 'error');
        return;
      }

      btnTestTransModel.classList.add('testing');
      const textSpan = btnTestTransModel.querySelector('span');
      if (textSpan) textSpan.textContent = 'Menguji...';
      setModelStatus(transModelStatus, `Menguji model audio ${model}...`, 'yellow');

      try {
        const res = await fetch('/api/models/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider, model }),
        });
        const data = await res.json();
        if (data.success) {
          setModelStatus(transModelStatus, `Siap (${data.latency_ms}ms) • ${data.model}`, 'green');
          showToast(data.message, 'success');
        } else {
          setModelStatus(transModelStatus, `Gagal: ${data.error || 'Error'}`, 'red');
          showToast(`Gagal uji audio: ${data.error}`, 'error');
        }
      } catch (err) {
        setModelStatus(transModelStatus, `Error: ${err.message}`, 'red');
        showToast(`Error: ${err.message}`, 'error');
      } finally {
        btnTestTransModel.classList.remove('testing');
        if (textSpan) textSpan.textContent = 'Tes';
      }
    });
  }

  // 2. Fetch History Count
  async function updateHistoryCount() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      const count = data.total_videos !== undefined ? data.total_videos : (data.history || []).length;
      historyCountBadge.textContent = count;
    } catch (e) {
      console.warn('History fetch error', e);
    }
  }

  // 3. Segmented Control for Clip Count
  clipCountControl.addEventListener('click', (e) => {
    const btn = e.target.closest('.segment-btn');
    if (!btn) return;
    clipCountControl.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    numClipsInput.value = btn.dataset.value;
    const countLabel = document.getElementById('clipCountLabel');
    if (countLabel) countLabel.textContent = `${btn.dataset.value} Klip`;
  });

  // 4. Paste Button Helper
  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text && (text.includes('youtube.com') || text.includes('youtu.be') || text.startsWith('http'))) {
        videoUrlInput.value = text.trim();
        showToast('Link YouTube berhasil ditempel!', 'success');
      } else if (text) {
        videoUrlInput.value = text.trim();
      }
    } catch (err) {
      videoUrlInput.focus();
    }
  });

  // Helper: parse custom bounding box string "x,y,w,h"
  function parseBox(str) {
    if (!str || typeof str !== 'string') return null;
    const parts = str.split(',').map(s => parseFloat(s.trim()));
    if (parts.length === 4 && parts.every(n => !isNaN(n))) {
      return { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
    }
    return null;
  }

  // ==========================================
  // Gaming Facecam Interactive Bounding Box & 9:16 Preview Engine
  // ==========================================
  const CORNER_PRESETS = {
    bottom_right: { x: 0.74, y: 0.63, w: 0.26, h: 0.37 },
    bottom_left:  { x: 0.00, y: 0.63, w: 0.26, h: 0.37 },
    top_right:    { x: 0.74, y: 0.00, w: 0.26, h: 0.37 },
    top_left:     { x: 0.00, y: 0.00, w: 0.26, h: 0.37 },
  };

  let currentFacecamNormBox = { ...CORNER_PRESETS.bottom_right };
  let isFacecamDragActive = false;
  let dragMode = null; // 'move', 'resize', or 'draw'
  let activeResizeHandle = null;
  let pointerStartPos = { x: 0, y: 0 };
  let boxStartNorm = { ...currentFacecamNormBox };

  // Calculate actual rendered video dimensions inside contain-fit wrapper
  function getVideoRenderRect() {
    if (!editorVideoWrapper) return { left: 0, top: 0, width: 280, height: 420 };
    const wrapperRect = editorVideoWrapper.getBoundingClientRect();
    if (!editorVideoPlayer || !editorVideoPlayer.videoWidth || !editorVideoPlayer.videoHeight) {
      return { left: 0, top: 0, width: wrapperRect.width, height: wrapperRect.height };
    }
    const vW = editorVideoPlayer.videoWidth;
    const vH = editorVideoPlayer.videoHeight;
    const scale = Math.min(wrapperRect.width / vW, wrapperRect.height / vH);
    const renderW = vW * scale;
    const renderH = vH * scale;
    const renderLeft = (wrapperRect.width - renderW) / 2;
    const renderTop = (wrapperRect.height - renderH) / 2;
    return { left: renderLeft, top: renderTop, width: renderW, height: renderH };
  }

  function roundTo(val, dec = 3) {
    const factor = Math.pow(10, dec);
    return Math.round(val * factor) / factor;
  }

  function renderFacecamOverlayBox() {
    if (!facecamBoundingBox || !editorVideoWrapper) return;
    const vr = getVideoRenderRect();
    const pxX = vr.left + (currentFacecamNormBox.x * vr.width);
    const pxY = vr.top + (currentFacecamNormBox.y * vr.height);
    const pxW = Math.max(16, currentFacecamNormBox.w * vr.width);
    const pxH = Math.max(16, currentFacecamNormBox.h * vr.height);

    facecamBoundingBox.style.left = `${Math.round(pxX)}px`;
    facecamBoundingBox.style.top = `${Math.round(pxY)}px`;
    facecamBoundingBox.style.width = `${Math.round(pxW)}px`;
    facecamBoundingBox.style.height = `${Math.round(pxH)}px`;

    const pctX = Math.round(currentFacecamNormBox.x * 100);
    const pctY = Math.round(currentFacecamNormBox.y * 100);
    const pctW = Math.round(currentFacecamNormBox.w * 100);
    const pctH = Math.round(currentFacecamNormBox.h * 100);

    if (facecamCoordsDisplay) {
      facecamCoordsDisplay.textContent = `X: ${pctX}% | Y: ${pctY}% | W: ${pctW}% | H: ${pctH}%`;
    }

    if (editGamingCustomBot) {
      editGamingCustomBot.value = `${currentFacecamNormBox.x},${currentFacecamNormBox.y},${currentFacecamNormBox.w},${currentFacecamNormBox.h}`;
    }
    if (editGamingBoxJson) {
      editGamingBoxJson.value = JSON.stringify(currentFacecamNormBox);
    }

    if (editorPlaybackMode === 'gaming_preview') {
      drawGamingPreviewCanvas();
    }
  }

  // Draw 9:16 vertical canvas preview (Action Gameplay 1440p top + Facecam 480p bottom)
  function drawGamingPreviewCanvas() {
    if (!gamingPreviewCanvas || !editorVideoPlayer) return;
    const ctx = gamingPreviewCanvas.getContext('2d');
    if (!ctx) return;

    const cW = gamingPreviewCanvas.width || 270;
    const cH = gamingPreviewCanvas.height || 480;

    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, cW, cH);

    const vW = editorVideoPlayer.videoWidth || 1920;
    const vH = editorVideoPlayer.videoHeight || 1080;

    // 1. Gameplay zone: Top 75% of vertical canvas (1080x1440 aspect)
    const targetRatio = 1080.0 / 1440.0; // 0.75
    let gameCropW = Math.min(vW, Math.round(vH * targetRatio));
    let gameCropH = vH;
    let gameCropX = Math.max(0, Math.round((vW - gameCropW) / 2));
    let gameCropY = 0;

    const gameTargetH = Math.round(cH * 0.75);
    try {
      if (editorVideoPlayer.readyState >= 2) {
        ctx.drawImage(editorVideoPlayer, gameCropX, gameCropY, gameCropW, gameCropH, 0, 0, cW, gameTargetH);
      } else {
        ctx.fillStyle = '#161b22';
        ctx.fillRect(0, 0, cW, gameTargetH);
        ctx.fillStyle = '#8b949e';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Memuat Frame Gameplay...', cW / 2, gameTargetH / 2);
      }
    } catch (_) {}

    // 2. Cyan accent divider between gameplay and facecam
    ctx.fillStyle = '#00f2fe';
    ctx.fillRect(0, gameTargetH - 2, cW, 3);

    // 3. Facecam zone: Bottom 25% of vertical canvas (1080x480 aspect)
    const camTargetH = cH - gameTargetH;
    const fcX = Math.round(currentFacecamNormBox.x * vW);
    const fcY = Math.round(currentFacecamNormBox.y * vH);
    const fcW = Math.round(currentFacecamNormBox.w * vW);
    const fcH = Math.round(currentFacecamNormBox.h * vH);

    try {
      if (editorVideoPlayer.readyState >= 2 && fcW > 0 && fcH > 0) {
        ctx.drawImage(editorVideoPlayer, fcX, fcY, fcW, fcH, 0, gameTargetH + 1, cW, camTargetH - 1);
      } else {
        ctx.fillStyle = '#21262d';
        ctx.fillRect(0, gameTargetH + 1, cW, camTargetH - 1);
        ctx.fillStyle = '#8b949e';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Area Facecam', cW / 2, gameTargetH + camTargetH / 2);
      }
    } catch (_) {}

    // 4. Subtitle preview tag (cleanly above facecam panel, around y = 70%)
    const captionText = editClipHook ? (editClipHook.value.trim() || editClipTitle.value.trim()) : '';
    if (captionText && editSubtitleStyle && editSubtitleStyle.value !== 'none') {
      ctx.save();
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillStyle = '#15ccfa';
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 3;
      const displaySnippet = captionText.length > 28 ? captionText.slice(0, 26) + '...' : captionText;
      const capY = Math.round(cH * 0.70);
      ctx.strokeText(displaySnippet, cW / 2, capY);
      ctx.fillText(displaySnippet, cW / 2, capY);
      ctx.restore();
    }
  }

  // Mouse & Pointer events for dragging, resizing, and drawing bounding box
  function setupFacecamOverlayInteractions() {
    if (!facecamOverlay || !facecamBoundingBox) return;

    facecamOverlay.addEventListener('pointerdown', (e) => {
      const isGaming = editFramingMode && editFramingMode.value === 'gaming';
      if (!isGaming || editorPlaybackMode !== 'source') return;

      const vr = getVideoRenderRect();
      if (vr.width <= 0 || vr.height <= 0) return;

      const overlayRect = editorVideoWrapper.getBoundingClientRect();
      const clickX = e.clientX - overlayRect.left;
      const clickY = e.clientY - overlayRect.top;

      pointerStartPos = { x: e.clientX, y: e.clientY };
      boxStartNorm = { ...currentFacecamNormBox };

      const handle = e.target.closest('.facecam-handle');
      if (handle) {
        // Resizing via handle
        isFacecamDragActive = true;
        dragMode = 'resize';
        activeResizeHandle = handle.dataset.handle;
        e.preventDefault();
        e.stopPropagation();
        facecamOverlay.setPointerCapture(e.pointerId);
        return;
      }

      const box = e.target.closest('.facecam-box');
      if (box) {
        // Drag moving the box
        isFacecamDragActive = true;
        dragMode = 'move';
        e.preventDefault();
        e.stopPropagation();
        facecamOverlay.setPointerCapture(e.pointerId);
        return;
      }

      // Clicking empty area -> start drawing new box
      if (clickX >= vr.left && clickX <= vr.left + vr.width &&
          clickY >= vr.top && clickY <= vr.top + vr.height) {
        isFacecamDragActive = true;
        dragMode = 'draw';
        const startNormX = Math.max(0, Math.min(0.98, (clickX - vr.left) / vr.width));
        const startNormY = Math.max(0, Math.min(0.98, (clickY - vr.top) / vr.height));
        currentFacecamNormBox = { x: roundTo(startNormX, 3), y: roundTo(startNormY, 3), w: 0.05, h: 0.05 };
        boxStartNorm = { ...currentFacecamNormBox };
        renderFacecamOverlayBox();
        facecamOverlay.setPointerCapture(e.pointerId);
        e.preventDefault();
      }
    });

    facecamOverlay.addEventListener('pointermove', (e) => {
      if (!isFacecamDragActive) return;
      const vr = getVideoRenderRect();
      if (vr.width <= 0 || vr.height <= 0) return;

      const deltaX = (e.clientX - pointerStartPos.x) / vr.width;
      const deltaY = (e.clientY - pointerStartPos.y) / vr.height;

      if (dragMode === 'move') {
        let nx = boxStartNorm.x + deltaX;
        let ny = boxStartNorm.y + deltaY;
        nx = Math.max(0.0, Math.min(1.0 - boxStartNorm.w, nx));
        ny = Math.max(0.0, Math.min(1.0 - boxStartNorm.h, ny));
        currentFacecamNormBox.x = roundTo(nx, 3);
        currentFacecamNormBox.y = roundTo(ny, 3);
      } else if (dragMode === 'resize') {
        let { x, y, w, h } = boxStartNorm;
        if (activeResizeHandle === 'se') {
          w = Math.max(0.06, Math.min(1.0 - x, w + deltaX));
          h = Math.max(0.06, Math.min(1.0 - y, h + deltaY));
        } else if (activeResizeHandle === 'sw') {
          const maxLeft = x + w - 0.06;
          const newX = Math.max(0.0, Math.min(maxLeft, x + deltaX));
          w = (x + w) - newX;
          x = newX;
          h = Math.max(0.06, Math.min(1.0 - y, h + deltaY));
        } else if (activeResizeHandle === 'ne') {
          const maxTop = y + h - 0.06;
          const newY = Math.max(0.0, Math.min(maxTop, y + deltaY));
          h = (y + h) - newY;
          y = newY;
          w = Math.max(0.06, Math.min(1.0 - x, w + deltaX));
        } else if (activeResizeHandle === 'nw') {
          const maxLeft = x + w - 0.06;
          const maxTop = y + h - 0.06;
          const newX = Math.max(0.0, Math.min(maxLeft, x + deltaX));
          const newY = Math.max(0.0, Math.min(maxTop, y + deltaY));
          w = (x + w) - newX;
          h = (y + h) - newY;
          x = newX;
          y = newY;
        }
        currentFacecamNormBox = {
          x: roundTo(x, 3),
          y: roundTo(y, 3),
          w: roundTo(w, 3),
          h: roundTo(h, 3),
        };
      } else if (dragMode === 'draw') {
        const startX = boxStartNorm.x;
        const startY = boxStartNorm.y;
        const curX = Math.max(0.0, Math.min(1.0, startX + deltaX));
        const curY = Math.max(0.0, Math.min(1.0, startY + deltaY));
        const left = Math.min(startX, curX);
        const top = Math.min(startY, curY);
        const width = Math.max(0.06, Math.abs(curX - startX));
        const height = Math.max(0.06, Math.abs(curY - startY));
        currentFacecamNormBox = {
          x: roundTo(left, 3),
          y: roundTo(top, 3),
          w: roundTo(width, 3),
          h: roundTo(height, 3),
        };
      }

      if (editGamingPreset) editGamingPreset.value = 'custom';
      renderFacecamOverlayBox();
    });

    const endDrag = (e) => {
      if (!isFacecamDragActive) return;
      isFacecamDragActive = false;
      dragMode = null;
      activeResizeHandle = null;
      try {
        if (e && e.pointerId && facecamOverlay.hasPointerCapture(e.pointerId)) {
          facecamOverlay.releasePointerCapture(e.pointerId);
        }
      } catch (_) {}
      renderFacecamOverlayBox();
    };

    facecamOverlay.addEventListener('pointerup', endDrag);
    facecamOverlay.addEventListener('pointercancel', endDrag);
  }

  // Hook corner buttons & auto detect
  document.querySelectorAll('.btn-corner-preset[data-corner]').forEach(btn => {
    btn.addEventListener('click', () => {
      const corner = btn.dataset.corner;
      if (CORNER_PRESETS[corner]) {
        currentFacecamNormBox = { ...CORNER_PRESETS[corner] };
        if (editGamingPreset) {
          const matched = `clean_2layer_${corner}`;
          if (Array.from(editGamingPreset.options).some(o => o.value === matched)) {
            editGamingPreset.value = matched;
          } else {
            editGamingPreset.value = 'custom';
          }
        }
        renderFacecamOverlayBox();
        if (facecamDetectStatus) {
          facecamDetectStatus.className = 'facecam-detect-status hidden';
          facecamDetectStatus.textContent = '';
        }
      }
    });
  });

  if (btnAutoDetectFacecam) {
    btnAutoDetectFacecam.addEventListener('click', async () => {
      const sessionFolder = editSessionFolder.value.trim();
      const clipIdx = editClipIndex.value.trim();
      if (!sessionFolder) return;

      btnAutoDetectFacecam.disabled = true;
      btnAutoDetectFacecam.textContent = '⏳ Menganalisis...';
      if (facecamDetectStatus) {
        facecamDetectStatus.className = 'facecam-detect-status status-low';
        facecamDetectStatus.textContent = 'Sedang menganalisis wajah di 4 sudut video sumber...';
        facecamDetectStatus.classList.remove('hidden');
      }

      try {
        const url = `/api/detect-facecam?session_folder=${encodeURIComponent(sessionFolder)}&clip_index=${encodeURIComponent(clipIdx)}`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.box) {
          currentFacecamNormBox = { ...data.box };
          renderFacecamOverlayBox();
        }
        if (facecamDetectStatus) {
          facecamDetectStatus.classList.remove('hidden');
          if (data.detected && data.confidence === 'high') {
            facecamDetectStatus.className = 'facecam-detect-status status-high';
            facecamDetectStatus.textContent = `✅ ${data.message}`;
          } else {
            facecamDetectStatus.className = 'facecam-detect-status status-low';
            facecamDetectStatus.textContent = `⚠️ ${data.message}`;
          }
        }
      } catch (err) {
        if (facecamDetectStatus) {
          facecamDetectStatus.className = 'facecam-detect-status status-low';
          facecamDetectStatus.textContent = `⚠️ Deteksi gagal (${err.message}). Menyarankan preset standar.`;
        }
      } finally {
        btnAutoDetectFacecam.disabled = false;
        btnAutoDetectFacecam.textContent = '🤖 Deteksi Wajah';
      }
    });
  }

  // Handle Cloud API vs Local mode limitations on Gaming layout
  function updateCloudModeRestrictions() {
    const isCloud = modeSelect && modeSelect.value === 'api';
    if (cloudGamingNotice) {
      cloudGamingNotice.classList.toggle('hidden', !isCloud);
    }
    if (framingModeSelect) {
      const gamingOption = framingModeSelect.querySelector('option[value="gaming"]');
      if (gamingOption) {
        gamingOption.disabled = isCloud;
        if (isCloud && framingModeSelect.value === 'gaming') {
          framingModeSelect.value = 'podcast';
          showToast('Mode Cloud API (MuAPI) belum mendukung layout Gaming. Framing dialihkan ke Podcast.', 'warning');
          updateGamingVisibility();
        }
      }
    }
  }
  if (modeSelect) {
    modeSelect.addEventListener('change', () => {
      updateCloudModeRestrictions();
      updateGamingVisibility();
    });
  }

  // Gaming layout preset visibility toggles
  function updateGamingVisibility() {
    const isGaming = framingModeSelect && framingModeSelect.value === 'gaming';
    if (gamingPresetCell) gamingPresetCell.style.display = isGaming ? 'block' : 'none';
    const isCustom = isGaming && gamingPresetSelect && gamingPresetSelect.value === 'custom';
    if (gamingCustomBoxCell) gamingCustomBoxCell.style.display = isCustom ? 'block' : 'none';
  }
  if (framingModeSelect) {
    framingModeSelect.addEventListener('change', updateGamingVisibility);
  }
  if (gamingPresetSelect) {
    gamingPresetSelect.addEventListener('change', updateGamingVisibility);
  }

  function updateEditGamingVisibility() {
    const isGaming = editFramingMode && editFramingMode.value === 'gaming';
    if (editGamingPresetRow) editGamingPresetRow.style.display = isGaming ? 'block' : 'none';
    const isCustom = isGaming && editGamingPreset && editGamingPreset.value === 'custom';
    if (editGamingCustomRow) editGamingCustomRow.style.display = isCustom ? 'block' : 'none';

    if (gamingFacecamToolbar) {
      gamingFacecamToolbar.classList.toggle('hidden', !isGaming);
    }
    if (btnPreviewGaming) {
      btnPreviewGaming.style.display = isGaming ? 'inline-flex' : 'none';
    }

    if (!isGaming && editorPlaybackMode === 'gaming_preview') {
      switchEditorPreviewMode('source');
    }

    if (isGaming && editorPlaybackMode === 'source') {
      if (facecamOverlay) facecamOverlay.classList.remove('hidden');
      renderFacecamOverlayBox();
    } else {
      if (facecamOverlay) facecamOverlay.classList.add('hidden');
    }
  }
  if (editFramingMode) {
    editFramingMode.addEventListener('change', updateEditGamingVisibility);
  }
  if (editGamingPreset) {
    editGamingPreset.addEventListener('change', () => {
      updateEditGamingVisibility();
      if (editGamingPreset.value.startsWith('clean_2layer_')) {
        const corner = editGamingPreset.value.replace('clean_2layer_', '');
        if (CORNER_PRESETS[corner]) {
          currentFacecamNormBox = { ...CORNER_PRESETS[corner] };
          renderFacecamOverlayBox();
        }
      }
    });
  }

  setupFacecamOverlayInteractions();
  window.addEventListener('resize', () => {
    if (editFramingMode && editFramingMode.value === 'gaming' && editorPlaybackMode === 'source') {
      renderFacecamOverlayBox();
    }
  });

  // 5. Timer Helper
  function startTimer(initialSeconds = 0) {
    stopTimer();
    timerSeconds = Math.max(0, parseInt(initialSeconds, 10) || 0);
    const m = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
    const s = String(timerSeconds % 60).padStart(2, '0');
    progressTimer.textContent = `${m}:${s}`;
    timerInterval = setInterval(() => {
      timerSeconds++;
      const mins = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
      const secs = String(timerSeconds % 60).padStart(2, '0');
      progressTimer.textContent = `${mins}:${secs}`;
    }, 1000);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  // 6. View Switcher & Animation Scene Helpers
  let activeProgressView = 'animation';
  function setActiveProgressView(viewName) {
    activeProgressView = viewName;
    try {
      localStorage.setItem('shorts_progress_view', viewName);
    } catch (_) {}

    if (viewName === 'animation') {
      if (tabAnimationView) {
        tabAnimationView.classList.add('active');
        tabAnimationView.setAttribute('aria-selected', 'true');
      }
      if (tabTerminalView) {
        tabTerminalView.classList.remove('active');
        tabTerminalView.setAttribute('aria-selected', 'false');
      }
      if (animationViewContainer) animationViewContainer.classList.remove('hidden');
      if (terminalViewContainer) terminalViewContainer.classList.add('hidden');
    } else {
      if (tabTerminalView) {
        tabTerminalView.classList.add('active');
        tabTerminalView.setAttribute('aria-selected', 'true');
      }
      if (tabAnimationView) {
        tabAnimationView.classList.remove('active');
        tabAnimationView.setAttribute('aria-selected', 'false');
      }
      if (animationViewContainer) animationViewContainer.classList.add('hidden');
      if (terminalViewContainer) terminalViewContainer.classList.remove('hidden');
      // Hide alert badge once user inspects the terminal logs
      if (logAlertBadge) logAlertBadge.classList.add('hidden');
    }
  }

  if (tabAnimationView) {
    tabAnimationView.addEventListener('click', () => setActiveProgressView('animation'));
  }
  if (tabTerminalView) {
    tabTerminalView.addEventListener('click', () => setActiveProgressView('terminal'));
  }

  // Restore saved view preference
  try {
    const savedView = localStorage.getItem('shorts_progress_view');
    if (savedView === 'terminal') {
      setActiveProgressView('terminal');
    } else {
      setActiveProgressView('animation');
    }
  } catch (_) {
    setActiveProgressView('animation');
  }

  function updateAnimationScene(stage) {
    Object.values(animScenes).forEach(scene => {
      if (scene) scene.classList.remove('active');
    });

    if (stage === 'downloading' && animScenes.download) {
      animScenes.download.classList.add('active');
      if (animationStatusText) animationStatusText.textContent = 'Mengunduh video...';
    } else if (stage === 'transcribing' && animScenes.transcribe) {
      animScenes.transcribe.classList.add('active');
      if (animationStatusText) animationStatusText.textContent = 'Transkripsi audio...';
    } else if (stage === 'analyzing' && animScenes.analyze) {
      animScenes.analyze.classList.add('active');
      if (animationStatusText) animationStatusText.textContent = 'Analisis hook AI...';
    } else if (stage === 'cropping' && animScenes.crop) {
      animScenes.crop.classList.add('active');
      if (animationStatusText) animationStatusText.textContent = 'Smart crop 9:16...';
    } else if (stage === 'completed' && animScenes.completed) {
      animScenes.completed.classList.add('active');
      if (animationStatusText) animationStatusText.textContent = 'Selesai diproses!';
    }
  }

  // 7. Update Stepper UI & Sync Animation
  function updateStepper(stage, progress) {
    progressBarFill.style.width = `${progress}%`;
    updateAnimationScene(stage);

    // Reset all
    Object.values(stepNodes).forEach(node => {
      node.classList.remove('active', 'completed');
    });
    Object.values(stepLines).forEach(line => {
      line.classList.remove('active', 'completed');
    });

    if (stage === 'downloading') {
      stepNodes.download.classList.add('active');
      progressTitle.textContent = 'Mengunduh & Memeriksa Video...';
      progressSubtitle.textContent = 'Mengambil konten video YouTube dan mengekstrak audio.';
    } else if (stage === 'transcribing') {
      stepNodes.download.classList.add('completed');
      stepLines.line1.classList.add('completed');
      stepNodes.transcribe.classList.add('active');
      progressTitle.textContent = 'Mentranskripsi Audio ke Teks...';
      progressSubtitle.textContent = 'Menghasilkan timestamp transkrip presisi dengan AI.';
    } else if (stage === 'analyzing') {
      stepNodes.download.classList.add('completed');
      stepLines.line1.classList.add('completed');
      stepNodes.transcribe.classList.add('completed');
      stepLines.line2.classList.add('completed');
      stepNodes.analyze.classList.add('active');
      progressTitle.textContent = 'Menganalisis Momen Viral Terbaik...';
      progressSubtitle.textContent = 'LLM mendeteksi hook, poin emosional, & menghitung skor virality.';
    } else if (stage === 'cropping') {
      stepNodes.download.classList.add('completed');
      stepLines.line1.classList.add('completed');
      stepNodes.transcribe.classList.add('completed');
      stepLines.line2.classList.add('completed');
      stepNodes.analyze.classList.add('completed');
      stepLines.line3.classList.add('completed');
      stepNodes.crop.classList.add('active');
      progressTitle.textContent = 'Memotong & Reframing Vertikal 9:16...';
      progressSubtitle.textContent = 'OpenCV melacak wajah dan FFmpeg merender klip final.';
    } else if (stage === 'completed') {
      Object.values(stepNodes).forEach(node => node.classList.add('completed'));
      Object.values(stepLines).forEach(line => line.classList.add('completed'));
      progressTitle.textContent = 'Pembuatan Shorts Selesai!';
      progressSubtitle.textContent = 'Semua klip vertikal siap ditonton dan diunduh.';
    }
  }

  // Reset title flasher when tab becomes visible
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && titleFlasher) {
      clearInterval(titleFlasher);
      titleFlasher = null;
      document.title = 'Reef Clipper | Pembuat Klip Video';
    }
  });

  // 7. Form Submission Handler
  generateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    requestNotifPermission();
    const url = videoUrlInput.value.trim();

    if (!url) {
      showToast('Masukkan URL YouTube terlebih dahulu!', 'error');
      return;
    }

    // Verify key status if in local mode
    const mode = modeSelect.value;
    if (mode === 'local') {
      const selectedLLM = llmProviderSelect.value;
      if (selectedLLM === 'gemini' && !activeConfig.has_gemini_key) {
        showToast('Kunci Gemini API belum diatur! Buka menu Pengaturan (ikon gir).', 'error');
        openSettingsModal();
        return;
      }
      if (selectedLLM === 'openai' && !activeConfig.has_openai_key) {
        showToast('Kunci OpenAI / APMIX API belum diatur! Buka menu Pengaturan (ikon gir).', 'error');
        openSettingsModal();
        return;
      }
    }

    // Disable button & prepare UI
    generateSubmitBtn.disabled = true;
    generateSubmitBtn.querySelector('.btn-text').textContent = 'Memproses Pipeline...';

    // Show Progress section, hide results
    resultsSection.classList.add('hidden');
    progressSection.classList.remove('hidden');
    progressSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    terminalLogBody.innerHTML = '<div class="log-line info">[ShortsAI] Mengirim permintaan ke server backend...</div>';
    if (logAlertBadge) logAlertBadge.classList.add('hidden');
    startTimer();
    updateStepper('downloading', 15);

    try {
      const selectedLlm = (llmModelSelect && llmModelSelect.value === '__custom__')
        ? (customLlmInput ? customLlmInput.value.trim() : '')
        : (llmModelSelect ? llmModelSelect.value : '');

      const selectedTrans = (transModelSelect && transModelSelect.value === '__custom__')
        ? (customTransInput ? customTransInput.value.trim() : '')
        : (transModelSelect ? transModelSelect.value : '');

      const payload = {
        url: url,
        mode: mode,
        num_clips: parseInt(numClipsInput.value, 10),
        aspect_ratio: aspectRatioSelect.value,
        framing_mode: framingModeSelect ? framingModeSelect.value : 'podcast',
        subtitle_style: subtitleStyleSelect ? subtitleStyleSelect.value : 'karaoke',
        format: formatSelect.value,
        llm_provider: llmProviderSelect.value,
        transcriber_provider: transcriberSelect.value,
        auto_delete_source_video: autoDeleteSourceGenInput ? autoDeleteSourceGenInput.checked : true,
      };

      if (framingModeSelect && framingModeSelect.value === 'gaming') {
        payload.gaming_preset = gamingPresetSelect ? gamingPresetSelect.value : 'clean_2layer';
        if (gamingPresetSelect && gamingPresetSelect.value === 'custom') {
          payload.gaming_custom_box = {
            top: parseBox(gamingCustomTop ? gamingCustomTop.value : ''),
            mid: parseBox(gamingCustomMid ? gamingCustomMid.value : ''),
            bottom: parseBox(gamingCustomBot ? gamingCustomBot.value : ''),
          };
        }
      }

      if (llmProviderSelect.value === 'gemini') {
        payload.gemini_model = selectedLlm || (geminiModelInput ? geminiModelInput.value.trim() : 'gemini-3.5-flash');
      } else if (llmProviderSelect.value === 'openai') {
        payload.openai_model = selectedLlm || 'gpt-4o-mini';
      }

      if (transcriberSelect.value === 'gemini') {
        payload.gemini_transcriber_model = selectedTrans || (geminiTransModelInput ? geminiTransModelInput.value.trim() : 'gemini-3.5-transcribe');
      } else if (transcriberSelect.value === 'whisper') {
        payload.whisper_model = selectedTrans || 'base';
      }

      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || 'Gagal memulai proses pembuat klip.');
      }

      currentJobId = data.job_id;
      try {
        localStorage.setItem('shorts_active_job_id', currentJobId);
      } catch (_) {}

      if (btnCancelJob) {
        btnCancelJob.disabled = false;
        btnCancelJob.classList.remove('canceling');
        const span = btnCancelJob.querySelector('span');
        if (span) span.textContent = 'Batalkan';
      }

      startPolling(currentJobId);
    } catch (err) {
      stopTimer();
      generateSubmitBtn.disabled = false;
      generateSubmitBtn.querySelector('.btn-text').textContent = 'Generate Viral Shorts Sekarang';
      showToast(err.message, 'error');
      progressTitle.textContent = 'Terjadi Kesalahan!';
      progressSubtitle.textContent = err.message;
    }
  });

  // 8. Cancel Job Button Handler
  if (btnCancelJob) {
    btnCancelJob.addEventListener('click', async () => {
      if (!currentJobId) return;
      btnCancelJob.disabled = true;
      btnCancelJob.classList.add('canceling');
      const span = btnCancelJob.querySelector('span');
      if (span) span.textContent = 'Membatalkan...';
      progressSubtitle.textContent = 'Menghentikan proses pipeline...';

      try {
        const res = await fetch(`/api/jobs/${currentJobId}/cancel`, { method: 'POST' });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.error) {
          showToast(data.error || 'Gagal membatalkan pekerjaan.', 'error');
          btnCancelJob.disabled = false;
          btnCancelJob.classList.remove('canceling');
          if (span) span.textContent = 'Batalkan';
          return;
        }
        if (data.message) {
          showToast(data.message, 'info');
        }
      } catch (err) {
        console.error('Cancel request error:', err);
        showToast('Gagal mengirim sinyal pembatalan.', 'error');
        btnCancelJob.disabled = false;
        btnCancelJob.classList.remove('canceling');
        if (span) span.textContent = 'Batalkan';
      }
    });
  }

  // 9. Polling Job Status with Network Fault Tolerance & Full State Handling
  function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);
    let consecutiveNetworkErrors = 0;

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);

        if (res.status === 404) {
          // Job not found on server (purged or invalid reference)
          clearInterval(pollInterval);
          pollInterval = null;
          stopTimer();
          showToast('Pekerjaan aktif sebelumnya tidak ditemukan di server.', 'info');
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          currentJobId = null;
          generateSubmitBtn.disabled = false;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Generate Viral Shorts Sekarang';
          if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.classList.remove('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Batalkan';
          }
          progressTitle.textContent = 'Pekerjaan Tidak Ditemukan';
          progressSubtitle.textContent = 'Referensi pekerjaan sudah tidak ada di server.';
          return;
        }

        if (!res.ok) {
          consecutiveNetworkErrors++;
          if (consecutiveNetworkErrors >= 5) {
            progressSubtitle.textContent = 'Koneksi jaringan terganggu. Mencoba menghubungkan kembali...';
          }
          return;
        }

        consecutiveNetworkErrors = 0;
        const job = await res.json();

        // Update Terminal Logs (Safely handle both string and legacy array formats)
        if (job.logs !== undefined && job.logs !== null) {
          const safeLogs = typeof job.logs === 'string'
            ? job.logs
            : (Array.isArray(job.logs) ? job.logs.join('\n') : String(job.logs));
          terminalLogBody.textContent = safeLogs;
          terminalLogBody.scrollTop = terminalLogBody.scrollHeight;

          // Alert user on tab if error/warning logged and user is on animation view
          if (activeProgressView === 'animation' && logAlertBadge) {
            const lowerLogs = safeLogs.toLowerCase();
            if (lowerLogs.includes('error') || lowerLogs.includes('fail') || lowerLogs.includes('traceback')) {
              logAlertBadge.classList.remove('hidden');
            }
          }
        }

        // Update Stepper & Visual Scene
        if (job.stage) {
          updateStepper(job.stage, job.progress || 20);
        }

        // Handle Canceling status
        if (job.status === 'canceling') {
          progressTitle.textContent = 'Sedang Menghentikan Pekerjaan...';
          progressSubtitle.textContent = job.cancel_reason || 'Menunggu proses aktif berhenti dengan aman...';
          if (btnCancelJob) {
            btnCancelJob.disabled = true;
            btnCancelJob.classList.add('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Sedang berhenti...';
          }
        }

        // Handle Terminal States
        if (job.status === 'completed') {
          clearInterval(pollInterval);
          pollInterval = null;
          stopTimer();
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          currentJobId = null;

          generateSubmitBtn.disabled = false;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Generate Viral Shorts Sekarang';
          if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.classList.remove('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Batalkan';
          }

          updateStepper('completed', 100);
          showToast('🎉 Shorts berhasil dibuat!', 'success');
          sendBrowserNotif('🎉 ShortsAI Selesai!', 'Klip Shorts kamu sudah siap diunduh.');
          renderResults(job.result);
          updateHistoryCount();
        } else if (job.status === 'partial') {
          clearInterval(pollInterval);
          pollInterval = null;
          stopTimer();
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          currentJobId = null;

          generateSubmitBtn.disabled = false;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Generate Viral Shorts Sekarang';
          if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.classList.remove('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Batalkan';
          }

          progressTitle.textContent = 'Pembuatan Klip Selesai Sebagian';
          progressSubtitle.textContent = job.error || 'Beberapa klip berhasil dibuat sebelum proses terhenti.';
          showToast('Pekerjaan selesai sebagian.', 'info');
          sendBrowserNotif('⚠️ ShortsAI Selesai Sebagian', 'Beberapa klip berhasil — cek hasilnya!');
          if (job.result) renderResults(job.result);
          updateHistoryCount();
        } else if (job.status === 'canceled') {
          clearInterval(pollInterval);
          pollInterval = null;
          stopTimer();
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          currentJobId = null;

          generateSubmitBtn.disabled = false;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Generate Viral Shorts Sekarang';
          if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.classList.remove('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Batalkan';
          }

          progressTitle.textContent = 'Pekerjaan Dibatalkan';
          progressSubtitle.textContent = job.cancel_reason || 'Proses pembuatan klip telah dihentikan.';
          showToast('Pekerjaan berhasil dibatalkan.', 'info');
        } else if (job.status === 'timeout') {
          clearInterval(pollInterval);
          pollInterval = null;
          stopTimer();
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          currentJobId = null;

          generateSubmitBtn.disabled = false;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Coba Lagi';
          if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.classList.remove('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Batalkan';
          }

          progressTitle.textContent = 'Batas Waktu Terlampaui (Timeout)';
          progressSubtitle.textContent = job.error || 'Pekerjaan dihentikan karena melampaui batas waktu pengerjaan.';
          showToast('Pekerjaan dihentikan karena batas waktu.', 'error');
          sendBrowserNotif('⏰ ShortsAI Timeout', 'Proses melampaui batas waktu. Coba lagi.');
        } else if (job.status === 'interrupted') {
          clearInterval(pollInterval);
          pollInterval = null;
          stopTimer();
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          currentJobId = null;

          generateSubmitBtn.disabled = false;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Generate Viral Shorts Sekarang';
          if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.classList.remove('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Batalkan';
          }

          progressTitle.textContent = 'Proses Terputus (Interrupted)';
          progressSubtitle.textContent = job.error || 'Server dimulai ulang atau proses terhenti sebelum selesai.';
          showToast('Proses terputus oleh restart server atau gangguan tak terduga.', 'warning');
          if (job.result && job.result.shorts && job.result.shorts.length > 0) {
            renderResults(job.result);
            updateHistoryCount();
          }
          if (logAlertBadge) logAlertBadge.classList.remove('hidden');
        } else if (job.status === 'failed') {
          clearInterval(pollInterval);
          pollInterval = null;
          stopTimer();
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          currentJobId = null;

          generateSubmitBtn.disabled = false;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Coba Lagi';
          if (btnCancelJob) {
            btnCancelJob.disabled = false;
            btnCancelJob.classList.remove('canceling');
            const span = btnCancelJob.querySelector('span');
            if (span) span.textContent = 'Batalkan';
          }

          progressTitle.textContent = 'Gagal Memproses Video';
          progressSubtitle.textContent = job.error || 'Terjadi kesalahan saat pemrosesan.';
          showToast(`Gagal: ${job.error}`, 'error');
          sendBrowserNotif('❌ ShortsAI Gagal', job.error || 'Terjadi kesalahan saat pemrosesan.');
          if (logAlertBadge) logAlertBadge.classList.remove('hidden');
        }
      } catch (e) {
        consecutiveNetworkErrors++;
        if (consecutiveNetworkErrors >= 5) {
          progressSubtitle.textContent = 'Koneksi jaringan terganggu. Mencoba menghubungkan kembali...';
        }
        console.error('Polling error', e);
      }
    }, 1200);
  }

  function parseClipIndex(fn) {
    if (!fn) return null;
    const m = String(fn).match(/short_(\d+)/i);
    return m ? parseInt(m[1], 10) : null;
  }

  // 9. Render Results
  function renderResults(result) {
    if (!result) return;
    const shorts = result.shorts || [];
    resultsMeta.textContent = `Mode: ${result.mode || 'local'} • Berhasil membuat ${shorts.length} klip video 9:16`;

    shortsGrid.innerHTML = '';

    if (shorts.length === 0) {
      shortsGrid.innerHTML = '<div class="empty-state">Tidak ada klip video yang berhasil dirender.</div>';
      resultsSection.classList.remove('hidden');
      return;
    }

    shorts.forEach((s, idx) => {
      const card = document.createElement('div');
      card.className = 'short-card';

      const videoSrc = (s.web_url || s.clip_url || '').trim();
      const hasVideo = Boolean(videoSrc && videoSrc !== 'null');
      const hasScore = s.score !== null && s.score !== undefined;
      const scoreBadgeHtml = hasScore
        ? `<div class="score-badge">Score ${s.score}/100</div>`
        : `<div class="score-badge" style="background: rgba(255,255,255,0.12); color: var(--text-secondary); border-color: var(--border-moderate);">Belum dinilai</div>`;

      const hasTimestamps = (typeof s.start_time === 'number' && typeof s.end_time === 'number');
      const durationSec = hasTimestamps ? Math.max(1, Math.round(s.end_time - s.start_time)) : 45;
      const startTimeFormatted = hasTimestamps ? formatSeconds(s.start_time) : '00:00';
      const endTimeFormatted = hasTimestamps ? formatSeconds(s.end_time) : '00:00';

      const videoHtml = hasVideo
        ? `
          <video class="short-video" preload="metadata" playsinline controls>
            <source src="${videoSrc}" type="video/mp4">
            ${s.vtt_url ? `<track src="${s.vtt_url}" kind="subtitles" srclang="id" label="Subtitles" default>` : ''}
            Browser Anda tidak mendukung pemutar video HTML5.
          </video>
        `
        : `
          <div class="video-preview-fallback" style="height: 380px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.4); border-radius: 12px; padding: 1.5rem; text-align: center; color: var(--text-secondary);">
            <div style="font-size: 2.2rem; margin-bottom: 0.5rem;">⚠️</div>
            <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 0.25rem;">Klip Belum Tersedia</div>
            <div style="font-size: 0.8rem; color: #ef4444; max-width: 90%; word-break: break-word;">${escapeHtml(s.error || 'Proses pemotongan video tidak menghasilkan berkas.')}</div>
          </div>
        `;

      const actionsHtml = hasVideo
        ? `
          <div class="short-actions">
            <a href="${videoSrc}" download="${s.filename || `short_${idx + 1}.mp4`}" class="btn-download" target="_blank">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span>Unduh MP4</span>
            </a>
            <button type="button" class="btn-edit-clip" title="Koreksi timestamp in/out, caption & framing">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20h9"></path>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
              </svg>
              <span>Edit</span>
            </button>
            <button type="button" class="btn-icon-action btn-expand" title="Perbesar Video">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 3 21 3 21 9"></polyline>
                <polyline points="9 21 3 21 3 15"></polyline>
                <line x1="21" y1="3" x2="14" y2="10"></line>
                <line x1="3" y1="21" x2="10" y2="14"></line>
              </svg>
            </button>
          </div>
        `
        : '';

      card.innerHTML = `
        <div class="video-preview-wrapper">
          <div class="video-overlay-badge">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:2px"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            ${durationSec}s (${startTimeFormatted} → ${endTimeFormatted})
          </div>
          ${scoreBadgeHtml}
          ${videoHtml}
        </div>
        <div class="short-card-body">
          <h3 class="short-title">#${idx + 1}. ${escapeHtml(s.title || 'Viral Highlight')}</h3>
          <div class="hook-box">
            "${escapeHtml(s.hook_sentence || 'Hook tidak terdeteksi.')}"
          </div>
          ${actionsHtml}
        </div>
      `;

      // Expand modal click handler
      const expandBtn = card.querySelector('.btn-expand');
      if (expandBtn && hasVideo) {
        expandBtn.addEventListener('click', () => {
          const currentData = card._clipData || s;
          openVideoModal(currentData.web_url || videoSrc, currentData.title || `Short #${idx + 1}`, currentData.vtt_url);
        });
      }

      card._clipData = {
        ...s,
        clip_index: s.clip_index || parseClipIndex(s.filename) || (idx + 1),
        folder_name: s.folder_name || (result && result.session_folder) || '',
        web_url: videoSrc,
      };

      // Edit modal click handler
      const editBtn = card.querySelector('.btn-edit-clip');
      if (editBtn && hasVideo) {
        editBtn.addEventListener('click', () => {
          const currentData = card._clipData || s;
          openClipEditor({
            ...currentData,
            card_element: card,
          });
        });
      }

      shortsGrid.appendChild(card);
    });

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Modal Accessibility & Keyboard Focus Management (WCAG AA R-32, C-4)
  let lastFocusedElement = null;

  function openDialog(modalEl, triggerEl = null) {
    if (!modalEl) return;
    lastFocusedElement = triggerEl || (document.activeElement && document.activeElement !== document.body ? document.activeElement : null);
    modalEl.classList.remove('hidden');

    const focusables = modalEl.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (focusables.length > 0) {
      focusables[0].focus();
    }
  }

  function closeDialog(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add('hidden');

    if (modalEl === videoModal && modalVideoPlayer) {
      modalVideoPlayer.pause();
      modalVideoPlayer.innerHTML = '';
      modalVideoPlayer.removeAttribute('src');
    }

    if (modalEl === editorModal && editorVideoPlayer) {
      editorVideoPlayer.pause();
      editorVideoPlayer.innerHTML = '';
      editorVideoPlayer.removeAttribute('src');
    }

    if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
      try {
        lastFocusedElement.focus();
      } catch (_) {}
      lastFocusedElement = null;
    }
  }

  // 10. History Modal & Drawer
  historyBtn.addEventListener('click', openHistoryModal);
  closeHistoryBtn.addEventListener('click', () => closeDialog(historyModal));

  const openMainOutputFolderBtn = document.getElementById('openMainOutputFolderBtn');
  if (openMainOutputFolderBtn) {
    openMainOutputFolderBtn.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/open-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ folder: '' }),
        });
        const d = await res.json();
        if (!res.ok || d.error) throw new Error(d.error || 'Gagal membuka folder output');
        showToast('Folder output dibuka di File Explorer', 'info');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  async function openHistoryModal() {
    openDialog(historyModal);
    historyListContainer.innerHTML = '<div class="empty-state">Mengambil riwayat video...</div>';

    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      const sessions = data.sessions || [];

      if (sessions.length === 0) {
        historyListContainer.innerHTML = '<div class="empty-state">Belum ada video yang tersimpan di folder output/.</div>';
        return;
      }

      historyListContainer.innerHTML = '';
      sessions.forEach((session) => {
        const card = document.createElement('div');
        card.className = 'history-session-card';

        const totalMB = (session.total_size_bytes / 1024 / 1024).toFixed(1);
        const folderLabel = session.folder_name ? escapeHtml(session.folder_name) : 'Sesi Arsip';

        // Header
        const header = document.createElement('div');
        header.className = 'session-header open';
        header.innerHTML = `
          <div class="session-info">
            <div class="session-title-row">
              <span class="session-folder-badge" title="Folder Sesi">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                </svg>
                ${folderLabel}
              </span>
              <span class="session-title" title="${escapeHtml(session.title)}">${escapeHtml(session.title)}</span>
            </div>
            <div class="session-meta-row">
              <span class="session-meta-item">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                ${session.created_at || ''}
              </span>
              <span class="session-meta-item">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="23 7 16 12 23 17 23 7"></polygon>
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
                </svg>
                ${session.total_shorts} Klip
              </span>
              <span class="session-meta-item">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                  <polyline points="17 21 17 13 7 13 7 21"></polyline>
                  <polyline points="7 3 7 8 15 8"></polyline>
                </svg>
                ${totalMB} MB
              </span>
            </div>
          </div>
          <div class="session-actions">
            ${session.folder_name ? `
            <button type="button" class="btn-session-action btn-open-folder" title="Buka folder sesi ini di File Explorer" data-folder="${escapeHtml(session.folder_name)}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              </svg>
              <span>Buka Folder</span>
            </button>
            <button type="button" class="btn-session-action btn-danger btn-delete-session" title="Hapus folder sesi ini dari disk" data-folder="${escapeHtml(session.folder_name)}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              <span>Hapus</span>
            </button>
            ` : ''}
            <div class="session-toggle-chevron rotated" title="Buka / Tutup">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </div>
        `;

        // Body
        const body = document.createElement('div');
        body.className = 'session-body';

        (session.shorts || []).forEach((item) => {
          const itemDiv = document.createElement('div');
          itemDiv.className = 'history-item';
          const sizeMB = (item.size_bytes / 1024 / 1024).toFixed(1);

          itemDiv.innerHTML = `
            <div class="history-thumb" title="Klik untuk memutar video">
              <video preload="metadata" playsinline muted>
                <source src="${item.web_url}" type="video/mp4">
              </video>
              <div class="history-play-overlay">
                <div class="play-circle">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                </div>
              </div>
              ${(item.score !== null && item.score !== undefined) ? `<div class="history-score-badge">Score ${item.score}</div>` : ''}
            </div>
            <div class="history-item-body">
              <div class="history-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
              ${item.hook_sentence ? `<div class="history-hook" title="${escapeHtml(item.hook_sentence)}">"${escapeHtml(item.hook_sentence)}"</div>` : ''}
              <div class="history-meta">
                ${item.start_time !== null && item.end_time !== null ? `${item.start_time}s – ${item.end_time}s • ` : ''}${sizeMB} MB
              </div>
              <div class="history-item-actions">
                <button type="button" class="btn-clip-action btn-play-clip">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                  <span>Tonton</span>
                </button>
                ${item.folder_name ? `
                <button type="button" class="btn-clip-action btn-edit-clip-history" title="Edit in/out, caption & framing">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                  </svg>
                  <span>Edit</span>
                </button>
                ` : ''}
                <a href="${item.web_url}" download="${item.filename}" class="btn-clip-action btn-dl-clip">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  <span>Unduh</span>
                </a>
              </div>
            </div>
          `;

          // Video preview trigger
          const thumbEl = itemDiv.querySelector('.history-thumb');
          const playBtn = itemDiv.querySelector('.btn-play-clip');
          const triggerPlay = () => {
            const currentData = itemDiv._clipData || item;
            openVideoModal(currentData.web_url, currentData.title, currentData.vtt_url);
          };
          thumbEl.addEventListener('click', triggerPlay);
          playBtn.addEventListener('click', triggerPlay);

          itemDiv._clipData = {
            ...item,
            clip_index: item.clip_index || parseClipIndex(item.filename),
            folder_name: item.folder_name || session.folder_name || '',
          };

          const editHistoryBtn = itemDiv.querySelector('.btn-edit-clip-history');
          if (editHistoryBtn) {
            editHistoryBtn.addEventListener('click', () => {
              const currentData = itemDiv._clipData || item;
              openClipEditor({
                ...currentData,
                card_element: itemDiv,
              });
            });
          }

          body.appendChild(itemDiv);
        });

        // Toggle accordion on header click
        header.addEventListener('click', (e) => {
          if (e.target.closest('.btn-session-action')) return;
          const isHidden = body.classList.toggle('hidden');
          header.classList.toggle('open', !isHidden);
          const chevron = header.querySelector('.session-toggle-chevron');
          if (chevron) {
            chevron.classList.toggle('rotated', !isHidden);
          }
        });

        // "Buka Folder" action
        const openFolderBtn = header.querySelector('.btn-open-folder');
        if (openFolderBtn) {
          openFolderBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const fName = openFolderBtn.dataset.folder;
            try {
              const oRes = await fetch('/api/open-folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder: fName }),
              });
              const oData = await oRes.json();
              if (!oRes.ok || oData.error) {
                throw new Error(oData.error || 'Gagal membuka folder');
              }
              showToast('Folder berhasil dibuka di File Explorer', 'info');
            } catch (err) {
              showToast(err.message, 'error');
            }
          });
        }

        // "Hapus Sesi" action
        const deleteFolderBtn = header.querySelector('.btn-delete-session');
        if (deleteFolderBtn) {
          deleteFolderBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const fName = deleteFolderBtn.dataset.folder;
            if (!confirm(`Yakin ingin menghapus seluruh sesi "${fName}" beserta semua klip videonya?`)) {
              return;
            }
            try {
              const dRes = await fetch(`/api/history/session/${encodeURIComponent(fName)}`, {
                method: 'DELETE',
              });
              const dData = await dRes.json();
              if (!dRes.ok || dData.error) {
                throw new Error(dData.error || 'Gagal menghapus sesi');
              }
              showToast('Sesi berhasil dihapus.', 'info');
              card.remove();
              updateHistoryCount();
              if (!historyListContainer.children.length) {
                historyListContainer.innerHTML = '<div class="empty-state">Belum ada video yang tersimpan di folder output/.</div>';
              }
            } catch (err) {
              showToast(err.message, 'error');
            }
          });
        }

        card.appendChild(header);
        card.appendChild(body);
        historyListContainer.appendChild(card);
      });
    } catch (e) {
      historyListContainer.innerHTML = `<div class="empty-state">Gagal memuat riwayat: ${e.message}</div>`;
    }
  }

  // 11. Settings Modal
  settingsBtn.addEventListener('click', openSettingsModal);
  closeSettingsBtn.addEventListener('click', () => closeDialog(settingsModal));
  cancelSettingsBtn.addEventListener('click', () => closeDialog(settingsModal));

  function openSettingsModal() {
    openDialog(settingsModal);
  }

  settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const saveBtn = document.getElementById('saveSettingsBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Menyimpan...';

    const payload = {};
    if (geminiApiKeyInput.value.trim() && !geminiApiKeyInput.value.includes('••••')) {
      payload.GEMINI_API_KEY = geminiApiKeyInput.value.trim();
    }
    if (geminiTransModelInput && geminiTransModelInput.value.trim()) {
      payload.GEMINI_TRANSCRIBER_MODEL = geminiTransModelInput.value.trim();
    }
    if (geminiModelInput && geminiModelInput.value.trim()) {
      payload.GEMINI_MODEL = geminiModelInput.value.trim();
    }
    if (openaiApiKeyInput.value.trim() && !openaiApiKeyInput.value.includes('••••')) {
      payload.OPENAI_API_KEY = openaiApiKeyInput.value.trim();
    }
    payload.OPENAI_BASE_URL = openaiBaseUrlInput.value.trim();
    if (muapiKeyInput.value.trim() && !muapiKeyInput.value.includes('••••')) {
      payload.MUAPI_API_KEY = muapiKeyInput.value.trim();
    }
    if (autoDeleteSourceInput) {
      payload.AUTO_DELETE_SOURCE_VIDEO = autoDeleteSourceInput.checked ? 'true' : 'false';
    }

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal menyimpan');

      showToast('Pengaturan API berhasil disimpan!', 'success');
      closeDialog(settingsModal);
      await loadConfig();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Simpan Pengaturan';
    }
  });

  // 12. Video Preview Modal
  function openVideoModal(url, title, vttUrl) {
    modalVideoTitle.textContent = title;
    modalVideoPlayer.innerHTML = `<source src="${url}" type="video/mp4">` + (vttUrl ? `<track src="${vttUrl}" kind="subtitles" srclang="id" label="Subtitles" default>` : '');
    modalVideoPlayer.load();
    openDialog(videoModal);
    modalVideoPlayer.play().catch(() => {});
  }

  closeVideoModalBtn.addEventListener('click', () => closeDialog(videoModal));

  // 13. Clip Editor Modal Logic & Re-rendering (Priority 8 & Item A-2 Timeline Synchronization)
  let activeEditingCard = null;
  let editorPlaybackMode = 'source'; // 'source' or 'clip'
  let clipOriginStart = 0; // Fixed source time for clip preview frame 0 (Finding A-01: never drifts on Set In)
  let editorClipUrl = '';
  let editorSourceUrl = '';

  const editClipFilename = document.getElementById('editClipFilename');
  const btnPreviewSource = document.getElementById('btnPreviewSource');
  const btnPreviewClip = document.getElementById('btnPreviewClip');
  const editorModeBadge = document.getElementById('editorModeBadge');

  function openClipEditor(clipData) {
    if (!editorModal) return;
    activeEditingCard = clipData.card_element || null;

    const folderName = clipData.folder_name || '';
    const clipIdx = clipData.clip_index || parseClipIndex(clipData.filename);
    if (!clipIdx) {
      showToast('Identitas klip tidak valid atau tidak ditemukan.', 'error');
      return;
    }

    editSessionFolder.value = folderName;
    editClipIndex.value = clipIdx;
    if (editClipFilename) {
      editClipFilename.value = clipData.filename || `short_${String(clipIdx).padStart(2, '0')}.mp4`;
    }
    editScore.value = (clipData.score !== undefined && clipData.score !== null) ? clipData.score : '';
    editClipTitle.value = clipData.title || '';
    editClipHook.value = clipData.hook_sentence || '';

    const startVal = typeof clipData.start_time === 'number' ? clipData.start_time : 0;
    const endVal = typeof clipData.end_time === 'number' ? clipData.end_time : (startVal + 30);
    editStartTime.value = startVal.toFixed(1);
    editEndTime.value = endVal.toFixed(1);
    editAspectRatio.value = clipData.aspect_ratio || '9:16';
    if (editFramingMode) {
      editFramingMode.value = clipData.framing_mode || 'podcast';
    }
    if (editGamingPreset) {
      editGamingPreset.value = clipData.gaming_preset || 'clean_2layer';
    }
    if (clipData.gaming_custom_box) {
      const gcb = clipData.gaming_custom_box;
      if (editGamingCustomTop && gcb.top) editGamingCustomTop.value = `${gcb.top.x},${gcb.top.y},${gcb.top.w},${gcb.top.h}`;
      if (editGamingCustomMid && gcb.mid) editGamingCustomMid.value = `${gcb.mid.x},${gcb.mid.y},${gcb.mid.w},${gcb.mid.h}`;
      if (editGamingCustomBot && gcb.bottom) editGamingCustomBot.value = `${gcb.bottom.x},${gcb.bottom.y},${gcb.bottom.w},${gcb.bottom.h}`;
      const fcBox = gcb.facecam || gcb.bottom;
      if (fcBox && typeof fcBox.x === 'number') {
        currentFacecamNormBox = { ...fcBox };
      }
    } else {
      if (editGamingCustomTop) editGamingCustomTop.value = '';
      if (editGamingCustomMid) editGamingCustomMid.value = '';
      if (editGamingCustomBot) editGamingCustomBot.value = '';
      if (clipData.gaming_preset && clipData.gaming_preset.startsWith('clean_2layer_')) {
        const corner = clipData.gaming_preset.replace('clean_2layer_', '');
        if (CORNER_PRESETS[corner]) {
          currentFacecamNormBox = { ...CORNER_PRESETS[corner] };
        }
      } else {
        currentFacecamNormBox = { ...CORNER_PRESETS.bottom_right };
      }
    }
    if (editGamingBoxJson) {
      editGamingBoxJson.value = JSON.stringify(currentFacecamNormBox);
    }
    updateEditGamingVisibility();
    if (editSubtitleStyle) {
      editSubtitleStyle.value = clipData.subtitle_style || (clipData.burn_subtitles === false ? 'none' : 'karaoke');
    }
    editBurnSubtitles.checked = clipData.burn_subtitles !== false && (!editSubtitleStyle || editSubtitleStyle.value !== 'none');

    // Origin of preview file in source timeline remains fixed to initial start_time
    clipOriginStart = startVal;

    editorStatusMessage.className = 'editor-status-msg hidden';
    editorStatusMessage.textContent = '';

    editorClipUrl = clipData.web_url || clipData.clip_url || '';
    editorSourceUrl = folderName ? `/api/session-source/${encodeURIComponent(folderName)}` : '';

    if (btnPreviewSource) {
      btnPreviewSource.disabled = !editorSourceUrl;
      btnPreviewSource.title = editorSourceUrl ? 'Preview video sumber asli (kontrak waktu absolut)' : 'Video sumber tidak tersedia untuk sesi ini';
    }

    // Default to source preview if available, otherwise fallback to clip preview
    if (editorSourceUrl) {
      switchEditorPreviewMode('source');
    } else if (editorClipUrl) {
      switchEditorPreviewMode('clip');
    }

    updateEditorTimeDisplay();
    openDialog(editorModal);
  }

  function switchEditorPreviewMode(mode) {
    if (!editorVideoPlayer) return;
    editorPlaybackMode = mode;
    const st = parseFloat(editStartTime.value) || 0;

    if (mode === 'source') {
      if (btnPreviewSource) {
        btnPreviewSource.classList.add('active');
        btnPreviewSource.setAttribute('aria-pressed', 'true');
      }
      if (btnPreviewClip) {
        btnPreviewClip.classList.remove('active');
        btnPreviewClip.setAttribute('aria-pressed', 'false');
      }
      if (btnPreviewGaming) {
        btnPreviewGaming.classList.remove('active');
        btnPreviewGaming.setAttribute('aria-pressed', 'false');
      }
      if (gamingPreviewCanvas) gamingPreviewCanvas.classList.add('hidden');
      editorVideoPlayer.classList.remove('hidden');

      if (editorModeBadge) {
        editorModeBadge.textContent = 'Mode: Sumber (Absolut)';
        editorModeBadge.className = 'editor-mode-badge badge-source';
      }

      if (editFramingMode && editFramingMode.value === 'gaming') {
        if (facecamOverlay) facecamOverlay.classList.remove('hidden');
        renderFacecamOverlayBox();
      } else {
        if (facecamOverlay) facecamOverlay.classList.add('hidden');
      }

      if (editorSourceUrl) {
        editorVideoPlayer.src = editorSourceUrl;
        editorVideoPlayer.load();

        const onMetadata = () => {
          editorVideoPlayer.removeEventListener('loadedmetadata', onMetadata);
          if (st >= 0 && (!editorVideoPlayer.duration || st <= editorVideoPlayer.duration)) {
            editorVideoPlayer.currentTime = st;
          }
          updateEditorTimeDisplay();
          if (editFramingMode && editFramingMode.value === 'gaming') {
            renderFacecamOverlayBox();
          }
        };
        editorVideoPlayer.addEventListener('loadedmetadata', onMetadata);
      }
    } else if (mode === 'gaming_preview') {
      if (btnPreviewGaming) {
        btnPreviewGaming.classList.add('active');
        btnPreviewGaming.setAttribute('aria-pressed', 'true');
      }
      if (btnPreviewSource) {
        btnPreviewSource.classList.remove('active');
        btnPreviewSource.setAttribute('aria-pressed', 'false');
      }
      if (btnPreviewClip) {
        btnPreviewClip.classList.remove('active');
        btnPreviewClip.setAttribute('aria-pressed', 'false');
      }
      if (facecamOverlay) facecamOverlay.classList.add('hidden');
      editorVideoPlayer.classList.add('hidden');
      if (gamingPreviewCanvas) {
        gamingPreviewCanvas.classList.remove('hidden');
        drawGamingPreviewCanvas();
      }
      if (editorModeBadge) {
        editorModeBadge.textContent = 'Mode: Preview Gaming 9:16';
        editorModeBadge.className = 'editor-mode-badge badge-source';
      }
    } else {
      // Clip mode: video player runs 0..dur, fixed to clipOriginStart (Finding A-01)
      if (btnPreviewClip) {
        btnPreviewClip.classList.add('active');
        btnPreviewClip.setAttribute('aria-pressed', 'true');
      }
      if (btnPreviewSource) {
        btnPreviewSource.classList.remove('active');
        btnPreviewSource.setAttribute('aria-pressed', 'false');
      }
      if (btnPreviewGaming) {
        btnPreviewGaming.classList.remove('active');
        btnPreviewGaming.setAttribute('aria-pressed', 'false');
      }
      if (gamingPreviewCanvas) gamingPreviewCanvas.classList.add('hidden');
      editorVideoPlayer.classList.remove('hidden');
      if (facecamOverlay) facecamOverlay.classList.add('hidden');

      if (editorModeBadge) {
        const cIdx = editClipIndex ? editClipIndex.value : 1;
        editorModeBadge.textContent = `Mode: Klip (#${cIdx})`;
        editorModeBadge.className = 'editor-mode-badge badge-clip';
      }

      if (editorClipUrl) {
        editorVideoPlayer.src = editorClipUrl;
        editorVideoPlayer.load();

        const onMetadata = () => {
          editorVideoPlayer.removeEventListener('loadedmetadata', onMetadata);
          editorVideoPlayer.currentTime = 0;
          updateEditorTimeDisplay();
        };
        editorVideoPlayer.addEventListener('loadedmetadata', onMetadata);
      }
    }
    updateEditorTimeDisplay();
  }

  function updateEditorTimeDisplay() {
    if (!editorTimeDisplay || !editorVideoPlayer) return;
    const playerCur = editorVideoPlayer.currentTime || 0;
    const currentSourceTime = editorPlaybackMode === 'source'
      ? playerCur
      : (clipOriginStart + playerCur);

    const st = parseFloat(editStartTime.value) || 0;
    const et = parseFloat(editEndTime.value) || 0;
    const dur = Math.max(0, et - st).toFixed(1);
    const modeLabel = editorPlaybackMode === 'source' ? 'Waktu Sumber' : 'Waktu Klip Terpetakan';
    editorTimeDisplay.textContent = `Rentang: ${st.toFixed(1)}s → ${et.toFixed(1)}s (Durasi: ${dur}s) • Posisi: ${currentSourceTime.toFixed(1)}s (${modeLabel})`;
  }

  if (editorVideoPlayer) {
    editorVideoPlayer.addEventListener('timeupdate', () => {
      updateEditorTimeDisplay();
      if (editorPlaybackMode === 'gaming_preview') {
        drawGamingPreviewCanvas();
      }
    });
    editorVideoPlayer.addEventListener('error', () => {
      if (editorPlaybackMode === 'source' && editorClipUrl) {
        console.warn('Video sumber tidak dapat dimuat, beralih ke klip hasil.');
        if (btnPreviewSource) {
          btnPreviewSource.disabled = true;
          btnPreviewSource.title = 'Video sumber tidak tersedia untuk sesi ini';
        }
        switchEditorPreviewMode('clip');
      }
    });
  }

  if (btnPreviewSource) {
    btnPreviewSource.addEventListener('click', () => {
      if (editorPlaybackMode !== 'source' && editorSourceUrl) {
        switchEditorPreviewMode('source');
      }
    });
  }

  if (btnPreviewClip) {
    btnPreviewClip.addEventListener('click', () => {
      if (editorPlaybackMode !== 'clip' && editorClipUrl) {
        switchEditorPreviewMode('clip');
      }
    });
  }

  if (btnPreviewGaming) {
    btnPreviewGaming.addEventListener('click', () => {
      if (editorPlaybackMode !== 'gaming_preview') {
        switchEditorPreviewMode('gaming_preview');
      }
    });
  }

  // Finding A-01: Manual In input only refreshes display, NEVER changes clipOriginStart!
  if (editStartTime) {
    editStartTime.addEventListener('input', updateEditorTimeDisplay);
  }
  if (editEndTime) {
    editEndTime.addEventListener('input', updateEditorTimeDisplay);
  }

  // Finding A-01: Set In & Set Out preserve fixed clipOriginStart on repeated clicks
  if (btnSetInFromPlayer) {
    btnSetInFromPlayer.addEventListener('click', () => {
      if (editorVideoPlayer) {
        const playerCur = editorVideoPlayer.currentTime || 0;
        const sourceTime = editorPlaybackMode === 'source'
          ? playerCur
          : (clipOriginStart + playerCur);
        editStartTime.value = sourceTime.toFixed(1);
        updateEditorTimeDisplay();
      }
    });
  }

  if (btnSetOutFromPlayer) {
    btnSetOutFromPlayer.addEventListener('click', () => {
      if (editorVideoPlayer) {
        const playerCur = editorVideoPlayer.currentTime || 0;
        const sourceTime = editorPlaybackMode === 'source'
          ? playerCur
          : (clipOriginStart + playerCur);
        editEndTime.value = sourceTime.toFixed(1);
        updateEditorTimeDisplay();
      }
    });
  }

  if (closeEditorBtn) {
    closeEditorBtn.addEventListener('click', () => closeDialog(editorModal));
  }
  if (cancelEditorBtn) {
    cancelEditorBtn.addEventListener('click', () => closeDialog(editorModal));
  }

  if (editSubtitleStyle && editBurnSubtitles) {
    editSubtitleStyle.addEventListener('change', () => {
      if (editSubtitleStyle.value === 'none') {
        editBurnSubtitles.checked = false;
      } else {
        editBurnSubtitles.checked = true;
      }
    });
    editBurnSubtitles.addEventListener('change', () => {
      if (!editBurnSubtitles.checked) {
        editSubtitleStyle.value = 'none';
      } else if (editSubtitleStyle.value === 'none') {
        editSubtitleStyle.value = 'karaoke';
      }
    });
  }

  if (editorForm) {
    editorForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const st = parseFloat(editStartTime.value);
      const et = parseFloat(editEndTime.value);

      if (isNaN(st) || isNaN(et) || st < 0 || et <= st) {
        showToast('Detik In dan Out tidak valid (Out harus lebih besar dari In).', 'error');
        return;
      }

      saveRenderEditorBtn.disabled = true;
      saveRenderEditorBtn.querySelector('.btn-text').textContent = 'Merender Ulang Klip...';
      editorStatusMessage.className = 'editor-status-msg info';
      editorStatusMessage.textContent = 'Sedang memproses crop, reframing, dan rendering ffmpeg...';

      try {
        const cIdx = parseInt(editClipIndex.value, 10);
        const subStyle = editSubtitleStyle ? editSubtitleStyle.value : (editBurnSubtitles.checked ? 'karaoke' : 'none');
        const payload = {
          session_folder: editSessionFolder.value.trim(),
          clip_index: cIdx,
          filename: (editClipFilename && editClipFilename.value) ? editClipFilename.value.trim() : undefined,
          start_time: st,
          end_time: et,
          title: editClipTitle.value.trim(),
          hook_sentence: editClipHook.value.trim(),
          aspect_ratio: editAspectRatio.value,
          framing_mode: editFramingMode ? editFramingMode.value : 'podcast',
          gaming_preset: (editFramingMode && editFramingMode.value === 'gaming' && editGamingPreset) ? editGamingPreset.value : undefined,
          gaming_custom_box: (editFramingMode && editFramingMode.value === 'gaming') ? {
            top: parseBox(editGamingCustomTop ? editGamingCustomTop.value : ''),
            mid: parseBox(editGamingCustomMid ? editGamingCustomMid.value : ''),
            bottom: currentFacecamNormBox,
            facecam: currentFacecamNormBox
          } : undefined,
          subtitle_style: subStyle,
          burn_subtitles: editBurnSubtitles.checked && subStyle !== 'none',
          score: editScore.value ? parseInt(editScore.value, 10) : null,
        };

        const res = await fetch('/api/edit-clip', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok || data.error) {
          throw new Error(data.error || 'Gagal merender ulang klip.');
        }

        showToast('✅ Klip berhasil dirender ulang!', 'success');
        const updated = data.clip;

        // Finding A-08: Update active card DOM and data object in-place for seamless reopening
        if (activeEditingCard) {
          const rev = updated.rev_id || Date.now();
          const cleanWebUrl = (updated.web_url || '').split('?')[0];
          const freshWebUrl = cleanWebUrl ? `${cleanWebUrl}?v=${rev}` : updated.web_url;
          const freshVttUrl = updated.vtt_url ? `${updated.vtt_url.split('?')[0]}?v=${rev}` : null;

          if (activeEditingCard._clipData) {
            Object.assign(activeEditingCard._clipData, updated);
            activeEditingCard._clipData.web_url = freshWebUrl;
            activeEditingCard._clipData.vtt_url = freshVttUrl;
          }

          const videoEl = activeEditingCard.querySelector('video.short-video') || activeEditingCard.querySelector('.history-thumb video');
          if (videoEl) {
            videoEl.src = freshWebUrl;
            // Synchronize <track> subtitle element
            const existingTrack = videoEl.querySelector('track');
            if (freshVttUrl) {
              if (existingTrack) {
                existingTrack.src = freshVttUrl;
              } else {
                const trackEl = document.createElement('track');
                trackEl.src = freshVttUrl;
                trackEl.kind = 'subtitles';
                trackEl.srclang = 'id';
                trackEl.label = 'Subtitles';
                trackEl.default = true;
                videoEl.appendChild(trackEl);
              }
            } else {
              if (existingTrack) {
                existingTrack.remove();
              }
            }
            videoEl.load();
          }
          const dlBtn = activeEditingCard.querySelector('.btn-download') || activeEditingCard.querySelector('.btn-dl-clip');
          if (dlBtn) {
            dlBtn.href = freshWebUrl;
          }
          const titleEl = activeEditingCard.querySelector('.short-title') || activeEditingCard.querySelector('.history-title');
          if (titleEl) {
            const prefix = updated.clip_index ? `#${updated.clip_index}. ` : '';
            titleEl.textContent = `${prefix}${updated.title}`;
          }
          const hookEl = activeEditingCard.querySelector('.hook-box') || activeEditingCard.querySelector('.history-hook');
          if (hookEl && updated.hook_sentence) {
            hookEl.textContent = `"${updated.hook_sentence}"`;
          }
          const badgeEl = activeEditingCard.querySelector('.video-overlay-badge');
          if (badgeEl) {
            const dur = Math.round(updated.end_time - updated.start_time);
            badgeEl.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:2px"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> ${dur}s (${formatSeconds(updated.start_time)} → ${formatSeconds(updated.end_time)})`;
          }
          const metaEl = activeEditingCard.querySelector('.history-meta');
          if (metaEl) {
            metaEl.textContent = `${updated.start_time.toFixed(1)}s – ${updated.end_time.toFixed(1)}s`;
          }
        }

        // Update active clipOriginStart with the newly rendered start_time
        clipOriginStart = typeof updated.start_time === 'number' ? updated.start_time : clipOriginStart;
        editorClipUrl = updated.web_url || editorClipUrl;

        closeDialog(editorModal);
        updateHistoryCount();
      } catch (err) {
        editorStatusMessage.className = 'editor-status-msg error';
        editorStatusMessage.textContent = err.message;
        showToast(err.message, 'error');
      } finally {
        saveRenderEditorBtn.disabled = false;
        saveRenderEditorBtn.querySelector('.btn-text').textContent = 'Simpan & Render Ulang Klip';
      }
    });
  }

  // 14. Terminal Toggle
  if (terminalToggleBtn && terminalLogBody) {
    terminalToggleBtn.addEventListener('click', () => {
      if (terminalLogBody.style.display === 'none') {
        terminalLogBody.style.display = 'block';
        terminalToggleBtn.textContent = 'Sembunyikan';
      } else {
        terminalLogBody.style.display = 'none';
        terminalToggleBtn.textContent = 'Tampilkan';
      }
    });
  }

  // 15. New Generation Button
  newGenerationBtn.addEventListener('click', () => {
    resultsSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    videoUrlInput.value = '';
    videoUrlInput.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Toast Utility
  function showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function formatSeconds(secs) {
    const s = Math.floor(secs);
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // 16. Keyboard Trapping & Overlay Click Handlers for Accessibility (R-32, C-4)
  window.addEventListener('keydown', (e) => {
    const allModals = [settingsModal, historyModal, videoModal, editorModal].filter(
      (m) => m && !m.classList.contains('hidden')
    );

    if (!allModals.length) return;
    const activeModal = allModals[allModals.length - 1];

    if (e.key === 'Escape') {
      e.preventDefault();
      closeDialog(activeModal);
    } else if (e.key === 'Tab') {
      const focusables = Array.from(
        activeModal.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      if (!focusables.length) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first || !activeModal.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !activeModal.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  });

  [settingsModal, historyModal, videoModal, editorModal].forEach((modal) => {
    if (!modal) return;
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeDialog(modal);
      }
    });
  });

  // 16. Resume Active Job upon Page Refresh
  async function resumeActiveJobIfAny() {
    let savedJobId = localStorage.getItem('shorts_active_job_id');
    if (!savedJobId) {
      try {
        const activeRes = await fetch('/api/jobs/active');
        if (activeRes.ok) {
          const activeData = await activeRes.json();
          if (activeData && activeData.job_id && ['queued', 'running', 'canceling'].includes(activeData.status)) {
            savedJobId = activeData.job_id;
            try {
              localStorage.setItem('shorts_active_job_id', savedJobId);
            } catch (_) {}
          }
        }
      } catch (_) {}
    }
    if (!savedJobId) return;

    let attempts = 0;
    const maxAttempts = 3;

    async function attemptFetch() {
      attempts++;
      try {
        const res = await fetch(`/api/jobs/${savedJobId}`);
        if (res.status === 404) {
          showToast('Pekerjaan aktif sebelumnya tidak ditemukan di server.', 'info');
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          return;
        }
        if (!res.ok) {
          if (attempts < maxAttempts) {
            setTimeout(attemptFetch, 1000 * attempts);
          }
          return;
        }

        const job = await res.json();
        if (['queued', 'running', 'canceling'].includes(job.status)) {
          currentJobId = savedJobId;
          resultsSection.classList.add('hidden');
          progressSection.classList.remove('hidden');
          generateSubmitBtn.disabled = true;
          generateSubmitBtn.querySelector('.btn-text').textContent = 'Memproses Pipeline...';

          startTimer(job.elapsed_seconds || 0);
          if (job.stage) updateStepper(job.stage, job.progress || 20);
          if (job.logs !== undefined && job.logs !== null) {
            const safeLogs = typeof job.logs === 'string'
              ? job.logs
              : (Array.isArray(job.logs) ? job.logs.join('\n') : String(job.logs));
            terminalLogBody.textContent = safeLogs;
            terminalLogBody.scrollTop = terminalLogBody.scrollHeight;
          }

          if (btnCancelJob) {
            btnCancelJob.disabled = job.status === 'canceling';
            if (job.status === 'canceling') {
              btnCancelJob.classList.add('canceling');
              const span = btnCancelJob.querySelector('span');
              if (span) span.textContent = 'Sedang berhenti...';
            } else {
              btnCancelJob.classList.remove('canceling');
              const span = btnCancelJob.querySelector('span');
              if (span) span.textContent = 'Batalkan';
            }
          }

          startPolling(savedJobId);
        } else {
          try {
            localStorage.removeItem('shorts_active_job_id');
          } catch (_) {}
          if ((job.status === 'completed' || job.status === 'partial') && job.result) {
            renderResults(job.result);
            updateHistoryCount();
            if (job.status === 'partial') {
              showToast('Memulihkan hasil klip yang sempat selesai sebagian.', 'info');
            }
          } else if (job.status === 'interrupted') {
            showToast('Pekerjaan sebelumnya terputus sebelum selesai.', 'warning');
            if (job.result && job.result.shorts && job.result.shorts.length > 0) {
              renderResults(job.result);
              updateHistoryCount();
            }
          } else if (job.status === 'failed') {
            showToast(`Pekerjaan sebelumnya gagal: ${job.error || 'Terjadi kesalahan'}`, 'error');
          } else if (job.status === 'timeout') {
            showToast('Pekerjaan sebelumnya dihentikan karena batas waktu.', 'error');
          } else if (job.status === 'canceled') {
            showToast('Pekerjaan sebelumnya telah dibatalkan.', 'info');
          }
        }
      } catch (e) {
        console.warn(`Resume attempt ${attempts} error:`, e);
        if (attempts < maxAttempts) {
          setTimeout(attemptFetch, 1000 * attempts);
        }
      }
    }

    await attemptFetch();
  }

  // Initial load
  loadConfig();
  updateHistoryCount();
  resumeActiveJobIfAny();
});
