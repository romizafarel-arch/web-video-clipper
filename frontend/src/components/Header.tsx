import type { FC } from 'react';
import { CheckCircle2, AlertCircle, Clock, Settings } from 'lucide-react';
import type { AppConfig } from '../types';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

interface HeaderProps {
  config: AppConfig | null;
  historyCount: number;
  onOpenHistory?: () => void;
  onOpenSettings?: () => void;
}

export const Header: FC<HeaderProps> = ({ config, historyCount, onOpenHistory, onOpenSettings }) => {
  const isConnected = Boolean(config?.has_gemini_key || config?.has_openai_key);

  return (
    <header className="header-glow-line sticky top-0 z-40 w-full shrink-0 border-b border-white/[0.08] bg-[#0A0A0F]/85 backdrop-blur-2xl px-4 sm:px-6 md:px-8 py-3 sm:py-3.5">
      <div className="max-w-[1536px] mx-auto flex items-center justify-between gap-3 sm:gap-4">
        {/* Brand / Title Reef Clipper */}
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0 shrink">
          <img
            src="/favicon.svg"
            alt=""
            aria-hidden="true"
            width="40"
            height="40"
            className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl shrink-0 object-contain drop-shadow-[0_0_12px_rgba(139,92,246,0.35)]"
          />
          <span className="font-extrabold text-base sm:text-xl md:text-2xl tracking-tight text-white font-headline truncate">
            Reef Clipper
          </span>
        </div>

        {/* Engine Status & Quick Actions */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="hidden sm:flex items-center">
            {isConnected ? (
              <Badge
                variant="success"
                className="gap-2 px-3 sm:px-3.5 py-1.5 min-h-[40px] sm:min-h-[44px] h-auto text-xs sm:text-sm font-sans rounded-xl border border-emerald-500/25 bg-emerald-500/10 shadow-[0_0_16px_rgba(52,211,153,0.12)]"
              >
                <CheckCircle2 className="w-4 h-4 sm:w-4.5 sm:h-4.5 text-emerald-400 shrink-0" />
                <span className="text-zinc-100 font-semibold">Engine Siap</span>
                <span className="text-zinc-500">•</span>
                <span className="text-[#A78BFA] font-mono text-xs sm:text-[13px] font-bold bg-violet-500/15 border border-violet-500/25 px-2 py-0.5 rounded-md">
                  {config?.llm_provider || 'Local'}
                </span>
              </Badge>
            ) : (
              <Badge
                variant="warning"
                className="gap-2 px-3 sm:px-3.5 py-1.5 min-h-[40px] sm:min-h-[44px] h-auto text-xs sm:text-sm font-sans rounded-xl border border-amber-500/25 bg-amber-500/10 shadow-[0_0_16px_rgba(251,191,36,0.12)]"
              >
                <AlertCircle className="w-4 h-4 sm:w-4.5 sm:h-4.5 text-amber-400 shrink-0" />
                <span className="text-amber-200 font-semibold">Cek API Key</span>
              </Badge>
            )}
          </div>

          <Button
            type="button"
            variant="outline"
            size="default"
            onClick={onOpenHistory}
            className="min-h-[44px] h-11 px-3.5 sm:px-4 gap-2 text-xs sm:text-sm font-semibold rounded-xl border-white/12 bg-white/[0.05] hover:bg-white/[0.1] hover:border-white/20 text-zinc-200 hover:text-white cursor-pointer transition-all shadow-sm"
            title="Buka Riwayat Sesi & Video Shorts"
            aria-label={`Buka Riwayat Sesi (${historyCount} klip)`}
          >
            <Clock className="w-4 h-4 sm:w-4.5 sm:h-4.5 text-cyan-400 shrink-0" />
            <span className="hidden sm:inline">Riwayat:</span>
            <span className="text-cyan-300 font-mono font-bold text-xs sm:text-sm bg-cyan-500/15 border border-cyan-500/30 px-2 py-0.5 rounded-lg shadow-[0_0_10px_rgba(34,211,238,0.15)]">
              {historyCount}
            </span>
          </Button>

          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={onOpenSettings}
            className="min-h-[44px] min-w-[44px] size-11 rounded-xl border-white/12 bg-white/[0.05] hover:bg-white/[0.1] hover:border-white/20 text-zinc-300 hover:text-white cursor-pointer transition-all"
            title="Pengaturan API & Engine"
            aria-label="Buka Pengaturan API & Engine"
          >
            <Settings className="w-5 h-5" />
          </Button>

          <a
            href="/"
            className="min-h-[44px] hidden md:inline-flex items-center px-3 text-xs sm:text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors underline decoration-dotted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded-xl"
            title="Buka interface klasik Flask jika perlu"
          >
            Versi Klasik
          </a>
        </div>
      </div>
    </header>
  );
};
