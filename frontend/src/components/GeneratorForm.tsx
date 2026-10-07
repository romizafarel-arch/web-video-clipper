import { useState, type FC } from 'react';
import {
  Video,
  Sparkles,
  Wand2,
  Users,
  User,
  Crop,
  Gamepad2,
  Layers,
  ClipboardPaste,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  HardDrive,
  Cloud,
  Check,
  AlertTriangle,
  Settings2,
} from 'lucide-react';
import { toast } from 'sonner';
import type {
  GeneratePayload,
  FramingMode,
  SubtitleStyle,
  AppConfig,
  ProcessingMode,
  LLMProvider,
  TranscriberProvider,
  ModelOption,
} from '../types';
import { fetchModels, testModel } from '../lib/api';
import { VisualPresetPicker } from './VisualPresetPicker';
import { FontFamilyPicker } from './FontFamilyPicker';
import { SubtitleVideoPreview } from './SubtitleVideoPreview';
import { TEXT_PRESETS, normalizePresetId } from '../lib/textPresets';
import { getDefaultFontForPreset } from '../lib/fontFamilyLibrary';
import { ILLUSTRATION_TRANSCRIPT_TEXT } from '../lib/illustrationTranscript';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Tabs, TabsList, TabsTrigger } from './ui/tabs';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

interface GeneratorFormProps {
  config: AppConfig | null;
  isLoading: boolean;
  onSubmit: (payload: GeneratePayload) => void;
  aspectRatio?: string;
  onAspectRatioChange?: (ratio: string) => void;
  subtitleStyle?: SubtitleStyle;
  onSubtitleStyleChange?: (style: SubtitleStyle) => void;
  fontFamily?: string;
  onFontFamilyChange?: (font: string) => void;
  framingMode?: FramingMode;
  onFramingModeChange?: (mode: FramingMode) => void;
}

export const GeneratorForm: FC<GeneratorFormProps> = ({
  config,
  isLoading,
  onSubmit,
  aspectRatio: propAspectRatio,
  onAspectRatioChange,
  subtitleStyle: propSubtitleStyle,
  onSubtitleStyleChange,
  fontFamily: propFontFamily,
  onFontFamilyChange,
  framingMode: propFramingMode,
  onFramingModeChange,
}) => {
  // Creative parameters
  const [url, setUrl] = useState('');
  const [numClips, setNumClips] = useState(3);
  const [localAspectRatio, setLocalAspectRatio] = useState('9:16');
  const [localFramingMode, setLocalFramingMode] = useState<FramingMode>('podcast');
  const [localSubtitleStyle, setLocalSubtitleStyle] = useState<SubtitleStyle>('karaoke');
  const [subtitleTab, setSubtitleTab] = useState<'preset' | 'font'>('preset');
  const [previewText, setPreviewText] = useState(ILLUSTRATION_TRANSCRIPT_TEXT);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  const aspectRatio = propAspectRatio ?? localAspectRatio;
  const subtitleStyle = propSubtitleStyle ?? localSubtitleStyle;
  const framingMode = propFramingMode ?? localFramingMode;

  const defaultFontForActivePreset = getDefaultFontForPreset(normalizePresetId(subtitleStyle));
  const [localFontFamily, setLocalFontFamily] = useState<string>(() => propFontFamily || defaultFontForActivePreset);
  const activeFont = propFontFamily ?? localFontFamily;

  const handleFontChange = (val: string) => {
    setLocalFontFamily(val);
    onFontFamilyChange?.(val);
  };

  const [gamingPreset, setGamingPreset] = useState<string>('auto');
  const [videoQuality, setVideoQuality] = useState('720');
  const [autoDeleteSource, setAutoDeleteSource] = useState(
    () => config?.auto_delete_source_video ?? true
  );

  const handleAspectRatioChange = (val: string) => {
    setLocalAspectRatio(val);
    onAspectRatioChange?.(val);
  };

  const handleSubtitleStyleChange = (val: SubtitleStyle) => {
    setLocalSubtitleStyle(val);
    onSubtitleStyleChange?.(val);
    if (val !== 'none') {
      const nextDefault = getDefaultFontForPreset(normalizePresetId(val));
      setLocalFontFamily(nextDefault);
      onFontFamilyChange?.(nextDefault);
    }
  };

  const handleFramingModeChange = (val: FramingMode) => {
    setLocalFramingMode(val);
    onFramingModeChange?.(val);
  };

  // Engine & Model parameters
  const [mode, setMode] = useState<ProcessingMode>(() =>
    config?.mode_default === 'api' || config?.mode_default === 'local' ? config.mode_default : 'local'
  );
  const [llmProvider, setLlmProvider] = useState<LLMProvider>(() =>
    config?.llm_provider === 'openai' ? 'openai' : 'gemini'
  );
  const [geminiModel, setGeminiModel] = useState(() => config?.gemini_model || 'gemini-3.5-flash');
  const [openaiModel, setOpenaiModel] = useState(() => config?.openai_model || 'gpt-4o-mini');
  const [transcriberProvider, setTranscriberProvider] = useState<TranscriberProvider>(() =>
    config?.transcriber_provider === 'whisper' ? 'whisper' : 'gemini'
  );
  const [geminiTranscriberModel, setGeminiTranscriberModel] = useState(
    () => config?.gemini_transcriber_model || 'gemini-3.5-transcribe'
  );
  const [whisperModel, setWhisperModel] = useState(() => config?.whisper_model || 'base');
  const [geminiModels, setGeminiModels] = useState<ModelOption[]>([
    { id: 'gemini-3.5-flash', name: 'gemini-3.5-flash (Direkomendasikan)' },
    { id: 'gemini-2.5-flash', name: 'gemini-2.5-flash (Cepat)' },
    { id: 'gemini-2.5-pro', name: 'gemini-2.5-pro (Analisis Mendalam)' },
  ]);
  const [openaiModels, setOpenaiModels] = useState<ModelOption[]>([
    { id: 'gpt-4o-mini', name: 'gpt-4o-mini (Cepat & Ringan)' },
    { id: 'gpt-4o', name: 'gpt-4o (Standar)' },
    { id: 'gpt-4.1-mini', name: 'gpt-4.1-mini (Preview)' },
  ]);
  const [whisperModels] = useState<ModelOption[]>([
    { id: 'tiny', name: 'tiny (Sangat Cepat)' },
    { id: 'base', name: 'base (Standar Cepat)' },
    { id: 'small', name: 'small (Seimbang)' },
    { id: 'medium', name: 'medium (Akurasi Tinggi)' },
    { id: 'large-v3', name: 'large-v3 (Maksimal)' },
  ]);
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const [isTestingModel, setIsTestingModel] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Load models from API
  const loadModels = async (forceRefresh: boolean = false) => {
    setIsFetchingModels(true);
    try {
      const data = await fetchModels(llmProvider, forceRefresh);
      const list = Array.isArray(data)
        ? data
        : Array.isArray((data as unknown as { models: ModelOption[] })?.models)
        ? (data as unknown as { models: ModelOption[] }).models
        : [];

      if (list && list.length > 0) {
        if (llmProvider === 'gemini') {
          setGeminiModels(list);
          if (!list.some((m) => m.id === geminiModel)) {
            setGeminiModel(list[0].id);
          }
        } else {
          setOpenaiModels(list);
          if (!list.some((m) => m.id === openaiModel)) {
            setOpenaiModel(list[0].id);
          }
        }
        toast.success(`Daftar model ${llmProvider.toUpperCase()} diperbarui (${list.length} model).`);
      }
    } catch {
      toast.error('Gagal mengambil daftar model dari server.');
    } finally {
      setIsFetchingModels(false);
    }
  };

  const handleTestModel = async () => {
    setIsTestingModel(true);
    setTestResult(null);
    const targetModel = llmProvider === 'gemini' ? geminiModel : openaiModel;
    try {
      const res = await testModel(llmProvider, targetModel);
      const msg = res.message || res.error || (res.success ? 'Model berhasil merespons.' : 'Pengujian model gagal.');
      setTestResult({ success: res.success, message: msg });
      if (res.success) {
        toast.success(msg);
      } else {
        toast.error(msg);
      }
    } catch {
      const failMsg = 'Koneksi ke endpoint pengujian model gagal.';
      setTestResult({ success: false, message: failMsg });
      toast.error(failMsg);
    } finally {
      setIsTestingModel(false);
    }
  };

  // Clipboard Paste Helper
  const handlePaste = async () => {
    try {
      if (!navigator.clipboard?.readText) {
        toast.error('Browser tidak mendukung pembacaan clipboard otomatis.');
        return;
      }
      const text = await navigator.clipboard.readText();
      if (!text || !text.trim()) {
        toast.warning('Clipboard kosong.');
        return;
      }
      const trimmed = text.trim();
      setUrl(trimmed);
      toast.success('URL video berhasil ditempel.');
    } catch {
      toast.error('Gagal membaca clipboard. Berikan izin clipboard pada browser.');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      toast.error('Harap masukkan URL video YouTube.');
      return;
    }

    const payload: GeneratePayload = {
      url: url.trim(),
      num_clips: numClips,
      aspect_ratio: aspectRatio,
      framing_mode: framingMode,
      subtitle_style: subtitleStyle,
      font_family: activeFont,
      format: videoQuality,
      auto_delete_source_video: autoDeleteSource,
      mode,
      llm_provider: llmProvider,
      gemini_model: geminiModel,
      openai_model: openaiModel,
      transcriber_provider: transcriberProvider,
      gemini_transcriber_model: geminiTranscriberModel,
      whisper_model: whisperModel,
    };

    if (framingMode === 'gaming') {
      payload.gaming_preset = gamingPreset;
    }

    onSubmit(payload);
  };

  const activePresetDef = TEXT_PRESETS.find((p) => p.id === normalizePresetId(subtitleStyle));

  return (
    <Card className="border border-white/[0.08] bg-[#12121A] text-zinc-100 shadow-md relative overflow-hidden rounded-2xl w-full max-w-full">
      <form onSubmit={handleSubmit} className="p-3 sm:p-5 space-y-3.5 sm:space-y-4">
        {/* Header Modul */}
        <CardHeader className="p-0 border-b border-white/[0.08] pb-3">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="text-lg sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2 font-headline">
                <Video className="w-5 h-5 text-violet-400 shrink-0" />
                <span className="truncate">Pengaturan Klip</span>
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm text-zinc-400 mt-1 font-sans line-clamp-1">
                Tempel URL YouTube dan tentukan parameter untuk memotong klip video.
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-xs sm:text-sm font-mono px-2.5 py-1 rounded-lg bg-zinc-950 border-zinc-800 text-zinc-300 shrink-0">
              {mode.toUpperCase()}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-0 space-y-4 sm:space-y-4.5">
          {/* 1. URL Input Field */}
          <div className="space-y-1.5">
            <label
              htmlFor="youtube-url"
              className="text-xs sm:text-sm font-semibold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5 cursor-pointer font-headline"
            >
              <span>URL Video YouTube</span>
            </label>
            <div className="relative flex items-center">
              <Input
                id="youtube-url"
                type="url"
                required
                placeholder="https://www.youtube.com/watch?v=..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isLoading}
                className="w-full h-11 sm:h-12 pl-3.5 pr-24 rounded-xl bg-zinc-950 border-zinc-800 text-zinc-100 placeholder-zinc-500 focus-visible:border-violet-500 focus-visible:ring-violet-500 text-sm sm:text-base font-medium transition-colors"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handlePaste}
                className="absolute right-1.5 h-8 sm:h-9 px-3 rounded-lg bg-zinc-900 hover:bg-zinc-800 border-zinc-700/80 text-xs sm:text-sm text-zinc-200 flex items-center gap-1.5 font-medium cursor-pointer"
                title="Tempel dari Clipboard"
                aria-label="Tempel URL dari Clipboard"
              >
                <ClipboardPaste className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span>Tempel</span>
              </Button>
            </div>
          </div>

          {/* 2. Pengaturan Inti: Rasio Aspek & Target Jumlah Klip */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            {/* Rasio Aspek */}
            <div className="p-3 sm:p-3.5 rounded-xl border border-white/[0.08] bg-zinc-950/60 space-y-2">
              <label className="text-xs sm:text-sm font-semibold text-zinc-200 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-violet-400" />
                <span>Rasio Aspek</span>
              </label>
              <div className="grid grid-cols-3 gap-1.5 sm:gap-2" role="radiogroup" aria-label="Pilih Rasio Aspek Video">
                {[
                  { id: '9:16', label: '9:16', desc: 'Vertikal' },
                  { id: '1:1', label: '1:1', desc: 'Persegi' },
                  { id: '16:9', label: '16:9', desc: 'Lanskap' },
                ].map((ar) => (
                  <button
                    key={ar.id}
                    type="button"
                    role="radio"
                    aria-checked={aspectRatio === ar.id}
                    onClick={() => handleAspectRatioChange(ar.id)}
                    className={`py-1.5 px-1.5 sm:px-2.5 rounded-lg border text-center transition-colors cursor-pointer ${
                      aspectRatio === ar.id
                        ? 'bg-violet-600 text-white border-violet-500 font-semibold'
                        : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/80'
                    }`}
                  >
                    <div className="text-sm sm:text-base font-bold font-mono">{ar.label}</div>
                    <div className="text-xs text-zinc-300/80 mt-0.5">{ar.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Target Jumlah Klip */}
            <div className="p-3 sm:p-3.5 rounded-xl border border-white/[0.08] bg-zinc-950/60 space-y-2 flex flex-col justify-between">
              <div className="flex justify-between items-center">
                <label htmlFor="num-clips" className="text-xs sm:text-sm font-semibold text-zinc-200 cursor-pointer">
                  Jumlah Klip
                </label>
                <Badge variant="default" className="text-xs sm:text-sm font-mono font-bold px-2 py-0.5 bg-violet-600 text-white">
                  {numClips} Klip
                </Badge>
              </div>
              <div className="min-h-[28px] flex items-center">
                <input
                  id="num-clips"
                  type="range"
                  min="1"
                  max="5"
                  step="1"
                  value={numClips}
                  onChange={(e) => setNumClips(parseInt(e.target.value, 10))}
                  aria-label="Jumlah klip yang dihasilkan"
                  className="w-full accent-violet-500 h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                />
              </div>
              <div className="flex justify-between text-xs font-semibold text-zinc-400 px-0.5 font-mono">
                <span>1</span>
                <span>2</span>
                <span>3</span>
                <span>4</span>
                <span>5</span>
              </div>
            </div>
          </div>

          {/* 3. Mode Framing Kamera */}
          <div className="space-y-2">
            <label className="text-sm sm:text-base font-bold text-zinc-100 flex items-center gap-2">
              <User className="w-4 h-4 text-cyan-400" />
              <span>Mode Framing Kamera</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-2.5" role="radiogroup" aria-label="Mode Framing Kamera">
              {[
                { id: 'podcast', label: 'Podcast Multi', desc: 'Auto track speaker', icon: Users },
                { id: 'single', label: 'Single Face', desc: 'Kunci 1 wajah', icon: User },
                { id: 'center', label: 'Center Crop', desc: 'Tengah statis', icon: Crop },
                { id: 'gaming', label: 'Gaming 2-Layer', desc: 'Facecam + game', icon: Gamepad2 },
              ].map((m) => {
                const Icon = m.icon;
                const isSelected = framingMode === m.id;
                return (
                  <button
                    type="button"
                    key={m.id}
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => handleFramingModeChange(m.id as FramingMode)}
                    className={`min-h-[64px] sm:min-h-[72px] p-2.5 sm:p-3 rounded-xl border text-left transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-violet-950/50 border-violet-500 text-white'
                        : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                      <Icon className={`w-4 h-4 shrink-0 ${isSelected ? 'text-violet-400' : 'text-zinc-400'}`} />
                      <span className="text-sm sm:text-base font-bold truncate">{m.label}</span>
                    </div>
                    <div className="text-xs sm:text-sm text-zinc-300 font-medium mt-1 truncate">{m.desc}</div>
                  </button>
                );
              })}
            </div>

            {framingMode === 'gaming' && (
              <div className="p-3 sm:p-3.5 rounded-xl bg-zinc-950/80 border border-zinc-800 space-y-2 mt-2">
                <label htmlFor="generator-gaming-preset" className="text-sm sm:text-base font-bold text-zinc-100 flex items-center gap-2">
                  <Gamepad2 className="w-4 h-4 text-violet-400" />
                  <span>Posisi Facecam / Webcam</span>
                </label>
                <select
                  id="generator-gaming-preset"
                  value={gamingPreset}
                  onChange={(e) => setGamingPreset(e.target.value)}
                  className="w-full h-10 px-3 rounded-lg bg-zinc-900 border border-zinc-700/80 text-zinc-100 text-sm sm:text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 font-medium cursor-pointer"
                >
                  <option value="auto">Deteksi Otomatis (AI)</option>
                  <option value="clean_2layer_bottom_right">Kanan Bawah</option>
                  <option value="clean_2layer_bottom_left">Kiri Bawah</option>
                  <option value="clean_2layer_top_right">Kanan Atas</option>
                  <option value="clean_2layer_top_left">Kiri Atas</option>
                  <option value="discord_top_cam_bottom_right">Squad Atas + Webcam Kanan Bawah</option>
                </select>
              </div>
            )}
          </div>

          {/* 4. Subtitle & Tipografi (Inline Picker + Segmented Tabs + Mini Live Preview) */}
          <div className="p-3.5 sm:p-5 rounded-xl border border-white/[0.08] bg-zinc-950/70 space-y-3.5 sm:space-y-4">
            {/* Header Section */}
            <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] pb-3">
              <div className="flex items-center gap-2 min-w-0">
                <Sparkles className="w-4 h-4 text-violet-400 shrink-0" />
                <span className="text-sm sm:text-base font-bold text-zinc-100 truncate font-headline">
                  Gaya Subtitle & Tipografi
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs sm:text-sm">
                <span className={`text-xs font-mono px-2.5 py-1 rounded-md font-medium ${
                  subtitleStyle === 'none'
                    ? 'bg-rose-950/60 text-rose-300 border border-rose-800/60'
                    : 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/60'
                }`}>
                  {subtitleStyle === 'none' ? 'Mati' : `${activePresetDef?.name || subtitleStyle} • ${activeFont}`}
                </span>
              </div>
            </div>

            {/* Live Video Animated Subtitle Preview Stage */}
            <SubtitleVideoPreview
              subtitleStyle={subtitleStyle}
              activeFont={activeFont}
              aspectRatio={aspectRatio}
              previewText={previewText}
              onPreviewTextChange={setPreviewText}
              framingMode={framingMode}
            />

            {/* Segmented Control Tabs */}
            <div className="space-y-3 pt-1">
              <div className="flex p-1 bg-zinc-950 border border-zinc-800/90 rounded-xl gap-1.5" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={subtitleTab === 'preset'}
                  onClick={() => setSubtitleTab('preset')}
                  className={`flex-1 min-h-[38px] py-1.5 px-3.5 rounded-lg text-xs sm:text-sm font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                    subtitleTab === 'preset'
                      ? 'bg-violet-600 text-white shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                  }`}
                >
                  <span>🎨 Gaya Preset</span>
                  {subtitleStyle !== 'none' && (
                    <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-violet-700/80 text-violet-100 ml-1">
                      {activePresetDef?.name?.split(' ')[0] || 'Aktif'}
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={subtitleTab === 'font'}
                  onClick={() => setSubtitleTab('font')}
                  className={`flex-1 min-h-[38px] py-1.5 px-3.5 rounded-lg text-xs sm:text-sm font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                    subtitleTab === 'font'
                      ? 'bg-violet-600 text-white shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                  }`}
                >
                  <span>🔤 Pilihan Font</span>
                  <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 ml-1 truncate max-w-[120px]">
                    {activeFont}
                  </span>
                </button>
              </div>

              {/* Inline Picker Panes */}
              {subtitleTab === 'preset' ? (
                <div className="pt-1 animate-in fade-in duration-150">
                  <VisualPresetPicker
                    selectedStyle={subtitleStyle}
                    onSelectPreset={handleSubtitleStyleChange}
                    compact={false}
                  />
                </div>
              ) : (
                <div className="pt-1 space-y-2 animate-in fade-in duration-150">
                  {subtitleStyle === 'none' && (
                    <div className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-800/40 text-xs sm:text-sm text-amber-300 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>Subtitle saat ini nonaktif. Font yang dipilih akan otomatis diterapkan saat mengaktifkan preset subtitle.</span>
                    </div>
                  )}
                  <FontFamilyPicker
                    selectedFont={activeFont}
                    onSelectFont={handleFontChange}
                    presetDefaultFont={defaultFontForActivePreset}
                    compact={false}
                  />
                </div>
              )}
            </div>
          </div>

          {/* 5. Pengaturan Lanjutan (Accordion) */}
          <div className="rounded-xl border border-white/[0.08] bg-zinc-950/40 overflow-hidden">
            <button
              type="button"
              onClick={() => setIsAdvancedOpen((prev) => !prev)}
              className="w-full min-h-[44px] sm:min-h-[48px] flex items-center justify-between px-3.5 py-2.5 text-sm sm:text-base font-bold text-zinc-200 hover:text-white transition-colors cursor-pointer select-none"
            >
              <div className="flex items-center gap-2">
                <Settings2 className="w-4 h-4 sm:w-5 sm:h-5 text-violet-400 shrink-0" />
                <span>Pengaturan Lanjutan (Resolusi & AI)</span>
              </div>
              {isAdvancedOpen ? <ChevronUp className="w-4 h-4 text-zinc-400 shrink-0" /> : <ChevronDown className="w-4 h-4 text-zinc-400 shrink-0" />}
            </button>

            {isAdvancedOpen && (
              <div className="p-3.5 sm:p-4 border-t border-white/[0.08] space-y-4 bg-zinc-950/90 text-sm sm:text-base">
                {/* Engine Selector */}
                <div className="space-y-2">
                  <span className="text-sm sm:text-base font-bold text-zinc-100 block">Mode Engine</span>
                  <Tabs value={mode} onValueChange={(val) => setMode(val as ProcessingMode)} className="w-full">
                    <TabsList className="grid grid-cols-2 w-full h-auto p-1.5 bg-zinc-900 border border-zinc-800 rounded-lg gap-1.5">
                      <TabsTrigger
                        value="local"
                        className="py-2 px-3 text-sm sm:text-base font-semibold cursor-pointer data-active:bg-violet-600 data-active:text-white"
                      >
                        <HardDrive className="w-4 h-4 mr-2" />
                        <span>Lokal</span>
                      </TabsTrigger>
                      <TabsTrigger
                        value="api"
                        className="py-2 px-3 text-sm sm:text-base font-semibold cursor-pointer data-active:bg-cyan-600 data-active:text-white"
                      >
                        <Cloud className="w-4 h-4 mr-2" />
                        <span>Cloud API</span>
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>

                {/* Resolusi */}
                <div className="space-y-2">
                  <span className="text-sm sm:text-base font-bold text-zinc-100 block">Resolusi Video</span>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: '720', label: '720p HD' },
                      { id: '1080', label: '1080p FHD' },
                      { id: '480', label: '480p SD' },
                    ].map((q) => (
                      <button
                        type="button"
                        key={q.id}
                        onClick={() => setVideoQuality(q.id)}
                        className={`py-2 px-2.5 rounded-lg border text-center transition-colors cursor-pointer text-sm sm:text-base font-semibold ${
                          videoQuality === q.id
                            ? 'bg-violet-600 border-violet-500 text-white'
                            : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:text-zinc-100'
                        }`}
                      >
                        {q.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Model LLM Provider & Selector */}
                <div className="space-y-2.5 pt-2 border-t border-zinc-800">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="llm-provider" className="text-sm sm:text-base font-semibold text-zinc-100 block mb-1.5">
                        Penyedia LLM
                      </label>
                      <select
                        id="llm-provider"
                        value={llmProvider}
                        onChange={(e) => setLlmProvider(e.target.value as LLMProvider)}
                        className="w-full h-10 px-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 text-sm sm:text-base font-medium cursor-pointer"
                      >
                        <option value="gemini">Google Gemini</option>
                        <option value="openai">OpenAI / Kompatibel</option>
                      </select>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <label htmlFor="llm-model" className="text-sm sm:text-base font-semibold text-zinc-100">
                          Model
                        </label>
                        <div className="flex items-center gap-2 text-xs sm:text-sm">
                          <button
                            type="button"
                            onClick={() => loadModels(true)}
                            disabled={isFetchingModels}
                            className="text-violet-400 hover:text-white cursor-pointer"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${isFetchingModels ? 'animate-spin' : ''}`} />
                          </button>
                          <button
                            type="button"
                            onClick={handleTestModel}
                            disabled={isTestingModel}
                            className="text-cyan-400 hover:text-white cursor-pointer"
                          >
                            {isTestingModel ? 'Tes...' : 'Ping'}
                          </button>
                        </div>
                      </div>
                      <select
                        id="llm-model"
                        value={llmProvider === 'gemini' ? geminiModel : openaiModel}
                        onChange={(e) =>
                          llmProvider === 'gemini'
                            ? setGeminiModel(e.target.value)
                            : setOpenaiModel(e.target.value)
                        }
                        className="w-full h-10 px-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 text-sm sm:text-base font-mono cursor-pointer"
                      >
                        {(llmProvider === 'gemini' ? geminiModels : openaiModels).map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name || m.id}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {testResult && (
                    <div className={`text-xs sm:text-sm flex items-center gap-1.5 ${testResult.success ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {testResult.success ? <Check className="w-3.5 h-3.5 shrink-0" /> : <AlertTriangle className="w-3.5 h-3.5 shrink-0" />}
                      <span className="truncate">{testResult.message}</span>
                    </div>
                  )}
                </div>

                {/* Transcriber Selector */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-zinc-800">
                  <div>
                    <label htmlFor="transcriber-provider" className="text-sm sm:text-base font-semibold text-zinc-100 block mb-1.5">
                      Transkripsi Audio
                    </label>
                    <select
                      id="transcriber-provider"
                      value={transcriberProvider}
                      onChange={(e) => setTranscriberProvider(e.target.value as TranscriberProvider)}
                      className="w-full h-10 px-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 text-sm sm:text-base font-medium cursor-pointer"
                    >
                      <option value="gemini">Google Gemini Audio</option>
                      <option value="whisper">Faster-Whisper Lokal</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="transcriber-model" className="text-sm sm:text-base font-semibold text-zinc-100 block mb-1.5">
                      Model Transkripsi
                    </label>
                    {transcriberProvider === 'whisper' ? (
                      <select
                        id="transcriber-model"
                        value={whisperModel}
                        onChange={(e) => setWhisperModel(e.target.value)}
                        className="w-full h-10 px-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 text-sm sm:text-base font-mono cursor-pointer"
                      >
                        {whisperModels.map((wm) => (
                          <option key={wm.id} value={wm.id}>
                            {wm.name || wm.id}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <select
                        id="transcriber-model"
                        value={geminiTranscriberModel}
                        onChange={(e) => setGeminiTranscriberModel(e.target.value)}
                        className="w-full h-10 px-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100 text-sm sm:text-base font-mono cursor-pointer"
                      >
                        <option value="gemini-3.5-transcribe">gemini-3.5-transcribe</option>
                        <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                      </select>
                    )}
                  </div>
                </div>

                {/* Auto Delete Master Checkbox */}
                <div className="pt-2 border-t border-zinc-800">
                  <label htmlFor="auto-delete-form" className="flex items-center gap-2 cursor-pointer text-zinc-300 hover:text-white select-none">
                    <input
                      id="auto-delete-form"
                      type="checkbox"
                      checked={autoDeleteSource}
                      onChange={(e) => setAutoDeleteSource(e.target.checked)}
                      className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-violet-600 focus-visible:ring-2 focus-visible:ring-violet-500 accent-violet-600 cursor-pointer shrink-0"
                    />
                    <span className="text-xs sm:text-sm">Hapus file master setelah selesai</span>
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* 6. Grand Primary Submit Button */}
          <Button
            type="submit"
            variant="default"
            size="lg"
            disabled={isLoading || !url.trim()}
            className="w-full min-h-[48px] h-12 sm:h-14 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-sm sm:text-base tracking-wide active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none transition-all flex items-center justify-center gap-2.5 cursor-pointer font-headline shadow-md"
          >
            {isLoading ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Memproses Video...</span>
              </>
            ) : (
              <>
                <Wand2 className="w-5 h-5" />
                <span>Buat Klip Video</span>
              </>
            )}
          </Button>
        </CardContent>
      </form>
    </Card>
  );
};
