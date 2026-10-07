import { useState, useEffect, type FC } from 'react';
import { X, Key, Settings, ExternalLink, Save, ShieldCheck, Cpu } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import type { AppConfig } from '../types';
import { updateConfig, fetchConfig } from '../lib/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AppConfig | null;
  onConfigUpdated: (config: AppConfig) => void;
}

export const SettingsModal: FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  config,
  onConfigUpdated,
}) => {
  const [geminiKey, setGeminiKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState(config?.openai_base_url || '');
  const [muapiKey, setMuapiKey] = useState('');
  const [autoDeleteSource, setAutoDeleteSource] = useState(config?.auto_delete_source_video ?? true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen && config) {
      queueMicrotask(() => {
        setOpenaiBaseUrl(config.openai_base_url || '');
        setAutoDeleteSource(config.auto_delete_source_video ?? true);
      });
    }
  }, [isOpen, config]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);

    const payload: Record<string, unknown> = {
      AUTO_DELETE_SOURCE_VIDEO: autoDeleteSource,
    };

    if (geminiKey.trim()) {
      payload.GEMINI_API_KEY = geminiKey.trim();
    }
    if (openaiKey.trim()) {
      payload.OPENAI_API_KEY = openaiKey.trim();
    }
    if (openaiBaseUrl.trim() !== (config?.openai_base_url || '')) {
      payload.OPENAI_BASE_URL = openaiBaseUrl.trim();
    }
    if (muapiKey.trim()) {
      payload.MUAPI_API_KEY = muapiKey.trim();
    }

    try {
      await updateConfig(payload);
      toast.success('Pengaturan API & Engine berhasil disimpan!');
      const updatedConfig = await fetchConfig();
      onConfigUpdated(updatedConfig);
      setGeminiKey('');
      setOpenaiKey('');
      setMuapiKey('');
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Gagal menyimpan pengaturan.';
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="max-w-xl w-full max-h-[90vh] bg-[#0f0f17] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col p-0 gap-0 sm:max-w-xl"
        showCloseButton={false}
      >
        {/* Header */}
        <DialogHeader className="flex flex-row items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
              <Settings className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <DialogTitle className="text-lg font-bold text-white font-['Sora']">
                Konfigurasi API & Engine
              </DialogTitle>
              <p className="text-xs text-slate-400">
                Kredensial API kunci provider AI dan opsi penyimpanan
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] w-[44px] h-[44px] p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            aria-label="Tutup pengaturan"
          >
            <X className="w-4 h-4" />
          </button>
        </DialogHeader>

        {/* Form */}
        <form onSubmit={handleSave} className="flex flex-col flex-1 min-h-0 overflow-hidden">
          {/* Scrollable Form Body */}
          <div className="p-4 sm:p-6 space-y-5 overflow-y-auto flex-1">
            {/* Gemini Key */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
              <label htmlFor="gemini-key" className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 cursor-pointer">
                <Key className="w-3.5 h-3.5 text-violet-400" />
                Google Gemini API Key
              </label>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-violet-400 hover:text-violet-300 flex items-center gap-1 focus-visible:outline-none focus-visible:underline"
              >
                <span>Dapatkan Kunci</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <div className="relative">
              <input
                id="gemini-key"
                type="password"
                placeholder={config?.gemini_key_masked || 'AIzaSy...'}
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                className="w-full h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-xs text-white placeholder-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:border-transparent font-mono"
              />
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <ShieldCheck className={`w-3.5 h-3.5 ${config?.has_gemini_key ? 'text-emerald-400' : 'text-slate-500'}`} />
              <span>
                Status: {config?.has_gemini_key ? <strong className="text-emerald-400">Tersambung ({config.gemini_key_masked})</strong> : 'Belum disetel'}
              </span>
            </div>
          </div>

          {/* OpenAI Key */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="openai-key" className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 cursor-pointer">
                <Key className="w-3.5 h-3.5 text-emerald-400" />
                OpenAI / APMIX API Key
              </label>
              <a
                href="https://platform.openai.com/api-keys"
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1 focus-visible:outline-none focus-visible:underline"
              >
                <span>Dapatkan Kunci</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <input
              id="openai-key"
              type="password"
              placeholder={config?.openai_key_masked || 'sk-...'}
              value={openaiKey}
              onChange={(e) => setOpenaiKey(e.target.value)}
              className="w-full h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-xs text-white placeholder-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:border-transparent font-mono"
            />
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <ShieldCheck className={`w-3.5 h-3.5 ${config?.has_openai_key ? 'text-emerald-400' : 'text-slate-500'}`} />
              <span>
                Status: {config?.has_openai_key ? <strong className="text-emerald-400">Tersambung ({config.openai_key_masked})</strong> : 'Belum disetel'}
              </span>
            </div>
          </div>

          {/* OpenAI Custom Base URL */}
          <div className="space-y-1.5">
            <label htmlFor="openai-base-url" className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 cursor-pointer">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              OpenAI Base URL (Opsional / Proxy / APMIX)
            </label>
            <input
              id="openai-base-url"
              type="text"
              placeholder="https://api.openai.com/v1 atau proxy kustom"
              value={openaiBaseUrl}
              onChange={(e) => setOpenaiBaseUrl(e.target.value)}
              className="w-full h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-xs text-white placeholder-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:border-transparent font-mono"
            />
            <p className="text-[10px] text-slate-400">
              Kosongkan jika menggunakan endpoint default OpenAI.
            </p>
          </div>

          {/* MuAPI Key (Cloud Mode) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="muapi-key" className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 cursor-pointer">
                <Key className="w-3.5 h-3.5 text-cyan-400" />
                MuAPI Key (Untuk Mode Cloud Engine)
              </label>
              <a
                href="https://muapi.com"
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 focus-visible:outline-none focus-visible:underline"
              >
                <span>MuAPI Portal</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <input
              id="muapi-key"
              type="password"
              placeholder={config?.muapi_key_masked || 'muapi-...'}
              value={muapiKey}
              onChange={(e) => setMuapiKey(e.target.value)}
              className="w-full h-10 px-3 rounded-lg bg-white/5 border border-white/10 text-xs text-white placeholder-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:border-transparent font-mono"
            />
          </div>

          {/* Storage & Auto Cleanup */}
          <div className="pt-3 border-t border-white/10">
            <label htmlFor="auto-delete-source" className="min-h-[44px] flex items-center gap-2.5 cursor-pointer text-xs text-slate-300 hover:text-white select-none py-2 px-1 transition-colors">
              <input
                id="auto-delete-source"
                type="checkbox"
                checked={autoDeleteSource}
                onChange={(e) => setAutoDeleteSource(e.target.checked)}
                className="w-5 h-5 rounded border-white/20 bg-white/5 text-violet-600 focus-visible:ring-2 focus-visible:ring-violet-500 accent-violet-600 cursor-pointer shrink-0"
              />
              <span>Hapus file master video YouTube otomatis setelah render selesai (hemat disk)</span>
            </label>
          </div>
        </div>

        {/* Sticky Submit Actions Footer */}
        <div className="sticky bottom-0 z-20 px-4 sm:px-6 py-3.5 bg-[#0f0f17] border-t border-white/10 flex items-center justify-end gap-3 shrink-0 shadow-lg">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-300 hover:text-white transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="min-h-[44px] px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white flex items-center gap-2 shadow-lg shadow-violet-600/30 transition-all cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
          >
            {isSaving ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Menyimpan...</span>
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                <span>Simpan Perubahan</span>
              </>
            )}
          </button>
        </div>
      </form>
      </DialogContent>
    </Dialog>
  );
};
