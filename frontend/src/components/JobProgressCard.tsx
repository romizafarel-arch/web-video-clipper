import { useState, type FC } from 'react';
import { Terminal, XCircle, Loader2, CheckCircle2, ChevronDown, ChevronUp, AlertTriangle, RefreshCw } from 'lucide-react';
import type { JobState } from '../types';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';

interface JobProgressCardProps {
  job: JobState;
  onCancel: () => void;
  isCanceling: boolean;
  pollingError?: string | null;
  onRetry?: () => void;
}

export const JobProgressCard: FC<JobProgressCardProps> = ({
  job,
  onCancel,
  isCanceling,
  pollingError,
  onRetry,
}) => {
  const [showLogs, setShowLogs] = useState(true);

  const stages = [
    { key: 'downloading', label: '1. Unduh Video' },
    { key: 'transcribing', label: '2. Transkripsi Audio' },
    { key: 'analyzing', label: '3. Seleksi AI Viral' },
    { key: 'cropping', label: '4. Pemotongan & Render' },
  ];

  const normalizeStage = (stage?: string): string | undefined => {
    if (!stage) return undefined;
    return stage === 'rendering' ? 'cropping' : stage;
  };

  const normalizedStage = normalizeStage(job.stage);
  const isTerminalSuccess = job.status === 'completed';
  const isTerminalError =
    job.status === 'failed' || job.status === 'timeout' || job.status === 'interrupted';
  const isTerminalCanceled = job.status === 'canceled' || job.status === 'cancelled';
  const isTerminal =
    isTerminalSuccess || isTerminalError || isTerminalCanceled || job.status === 'partial';

  const currentStageIndex = isTerminalSuccess
    ? stages.length
    : stages.findIndex((s) => s.key === normalizedStage);

  const progressPercent = typeof job.progress === 'number'
    ? Math.min(100, Math.max(0, job.progress))
    : 0;

  const headerTitle = isTerminalError
    ? job.status === 'timeout'
      ? 'Pembuatan video melewati batas waktu'
      : job.status === 'interrupted'
      ? 'Pembuatan video terinterupsi'
      : 'Pipeline pembuatan klip gagal'
    : isTerminalCanceled
    ? 'Pembuatan video dibatalkan'
    : isTerminalSuccess
    ? 'Pipeline Pembuatan Video Selesai'
    : 'Pipeline Pembuatan Video Berjalan';

  const stageLabel = isTerminalError
    ? `Status: ${job.status === 'timeout' ? 'Batas Waktu Terlampaui' : job.status === 'interrupted' ? 'Terinterupsi' : 'Gagal'}`
    : isTerminalCanceled
    ? 'Status: Dibatalkan'
    : isTerminalSuccess
    ? 'Status: Selesai'
    : job.stage
    ? `Tahap: ${job.stage}`
    : 'Menyiapkan Pipeline...';

  const progressIndicatorClass = isTerminalError
    ? '[&_[data-slot=progress-indicator]]:bg-none [&_[data-slot=progress-indicator]]:bg-rose-500 [&_[data-slot=progress-indicator]]:shadow-[0_0_12px_rgba(244,63,94,0.45)] [&_[data-slot=progress-indicator]]:after:hidden'
    : isTerminalCanceled
    ? '[&_[data-slot=progress-indicator]]:bg-none [&_[data-slot=progress-indicator]]:bg-amber-500 [&_[data-slot=progress-indicator]]:shadow-[0_0_12px_rgba(245,158,11,0.35)] [&_[data-slot=progress-indicator]]:after:hidden'
    : isTerminalSuccess
    ? '[&_[data-slot=progress-indicator]]:bg-none [&_[data-slot=progress-indicator]]:bg-emerald-500 [&_[data-slot=progress-indicator]]:shadow-[0_0_12px_rgba(16,185,129,0.35)] [&_[data-slot=progress-indicator]]:after:hidden'
    : '';

  const percentColorClass = isTerminalError
    ? 'text-rose-400'
    : isTerminalCanceled
    ? 'text-amber-400'
    : isTerminalSuccess
    ? 'text-emerald-400'
    : 'text-[#22D3EE]';

  const rawLogs = typeof job.logs === 'string'
    ? job.logs
    : Array.isArray(job.logs)
    ? job.logs.join('\n')
    : '';

  const getStatusBadge = () => {
    switch (job.status) {
      case 'completed':
        return <Badge variant="success">Selesai</Badge>;
      case 'failed':
      case 'timeout':
      case 'interrupted':
        return <Badge variant="destructive">Gagal</Badge>;
      case 'canceling':
      case 'canceled':
      case 'cancelled':
        return <Badge variant="warning">Dibatalkan</Badge>;
      case 'queued':
        return <Badge variant="secondary">Antrean</Badge>;
      case 'partial':
        return <Badge variant="warning">Sebagian</Badge>;
      case 'running':
      default:
        return <Badge variant="default" className="shadow-[0_0_12px_rgba(139,92,246,0.35)]">Memproses</Badge>;
    }
  };

  return (
    <Card className="p-4 sm:p-6 border-white/[0.08] bg-[#151520]/75 backdrop-blur-[20px] shadow-[0_8px_32px_0_rgba(0,0,0,0.4)] space-y-4 animate-in fade-in duration-300 relative">
      {/* Network / Polling Error Warning Bar */}
      {pollingError && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{pollingError}</span>
          </div>
          {onRetry && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="border-amber-500/40 text-amber-200 hover:bg-amber-500/20 cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Coba Lagi</span>
            </Button>
          )}
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="relative flex h-2.5 w-2.5">
              {!isTerminal && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#8B5CF6] opacity-75 motion-reduce:animate-none" />
              )}
              <span
                className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                  isTerminalError
                    ? 'bg-rose-500'
                    : isTerminalCanceled
                    ? 'bg-amber-400'
                    : isTerminalSuccess
                    ? 'bg-emerald-400'
                    : 'bg-[#8B5CF6]'
                }`}
              />
            </span>
            <h3 className="font-bold text-sm sm:text-base text-white font-headline">
              {headerTitle}
            </h3>
            {getStatusBadge()}
          </div>
          <p className="text-[11px] text-zinc-400 font-mono mt-1">
            Job ID: <span className="text-[#A78BFA]">{job.job_id}</span>
          </p>
        </div>

        {!isTerminal && (
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={onCancel}
              disabled={isCanceling || job.status === 'canceling'}
              className="min-h-[44px] cursor-pointer"
            >
              {isCanceling || job.status === 'canceling' ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Membatalkan...</span>
                </>
              ) : (
                <>
                  <XCircle className="w-4 h-4" />
                  <span>Batalkan</span>
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      {/* Progress Bar & Stage Info */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs font-semibold">
          <span className="text-zinc-300 uppercase tracking-wider text-[11px]">
            {stageLabel}
          </span>
          <span className={`${percentColorClass} font-mono font-bold`}>{progressPercent}%</span>
        </div>

        <Progress value={progressPercent} className={`w-full ${progressIndicatorClass}`} />
      </div>

      {isTerminalError && job.error && (
        <div
          role="alert"
          className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-200 text-xs leading-relaxed"
        >
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <span>{job.error}</span>
        </div>
      )}

      {/* Pipeline Stepper */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {stages.map((stg, idx) => {
          const isDone = isTerminalSuccess || currentStageIndex > idx;
          const isCurrent = !isTerminal && currentStageIndex === idx;

          return (
            <div
              key={stg.key}
              className={`p-2.5 rounded-xl border text-center transition-all ${
                isDone
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : isCurrent
                  ? 'bg-[#8B5CF6]/15 border-[#8B5CF6] text-white ring-1 ring-[#8B5CF6]/50 shadow-[0_0_12px_rgba(139,92,246,0.25)] step-active-pulse'
                  : 'bg-[#151520]/60 border-white/[0.06] text-zinc-500'
              }`}
            >
              <div className="flex items-center justify-center gap-1.5 mb-0.5">
                {isDone ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : isCurrent ? (
                  <Loader2 className="w-3.5 h-3.5 text-[#A78BFA] animate-spin motion-reduce:animate-none" />
                ) : (
                  <span className="w-3.5 h-3.5 rounded-full border border-zinc-600 text-[10px] flex items-center justify-center font-mono">
                    {idx + 1}
                  </span>
                )}
              </div>
              <div className="text-[11px] font-medium leading-tight">{stg.label}</div>
            </div>
          );
        })}
      </div>

      {/* Terminal Logs Collapsible */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0A0A0F]/60 overflow-hidden">
        <button
          type="button"
          onClick={() => setShowLogs(!showLogs)}
          className="w-full min-h-[44px] px-3.5 py-2.5 bg-white/[0.02] hover:bg-white/[0.05] flex items-center justify-between text-xs text-zinc-300 font-mono transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8B5CF6]"
        >
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-[#22D3EE]" />
            <span>Terminal Live Logs</span>
          </div>
          {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showLogs && (
          <div className="p-3 max-h-48 overflow-y-auto font-mono text-[11px] text-zinc-300 leading-relaxed space-y-1 select-text scrollbar-thin bg-black/40 border-t border-white/[0.04]">
            {rawLogs ? (
              <pre className="whitespace-pre-wrap break-all font-mono">{rawLogs}</pre>
            ) : (
              <span className="text-zinc-500 italic">Menunggu log aktivitas dari engine...</span>
            )}
          </div>
        )}
      </div>
    </Card>
  );
};
