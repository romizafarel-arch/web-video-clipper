import { useEffect, useState, useRef, useCallback } from 'react';
import { Toaster, toast } from 'sonner';
import { ArrowLeft, Film } from 'lucide-react';
import { Header } from './components/Header';
import { StudioVideoPlayer } from './components/StudioVideoPlayer';
import { GeneratorForm } from './components/GeneratorForm';
import { JobProgressCard } from './components/JobProgressCard';
import { ResultsGallery } from './components/ResultsGallery';
import { HistoryModal } from './components/HistoryModal';
import { SettingsModal } from './components/SettingsModal';
import { ClipEditorModal } from './components/ClipEditorModal';
import { StartPage } from './components/StartPage';
import { IdeaFlow } from './components/IdeaFlow';
import { Button } from './components/ui/button';
import type { AppConfig, GeneratePayload, JobState, JobResult, GeneratedShort, HistoryShort, SubtitleStyle, EditableClip, EditClipResponse, FramingMode, VideoIdeaGuide } from './types';
import { fetchConfig, submitGenerate, fetchJob, cancelJob, fetchActiveJob, fetchHistory } from './lib/api';

const TERMINAL_STATUSES = new Set([
  'completed',
  'partial',
  'failed',
  'cancelled',
  'canceled',
  'timeout',
  'interrupted',
]);

export function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [historyCount, setHistoryCount] = useState<number>(0);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [activeJob, setActiveJob] = useState<JobState | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobResult, setJobResult] = useState<JobResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isCanceling, setIsCanceling] = useState<boolean>(false);
  const [pollingError, setPollingError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'clipper' | 'studio'>('clipper');
  const [workspace, setWorkspace] = useState<'start' | 'ideas' | 'clipper'>('start');
  const [ideaGuide, setIdeaGuide] = useState<VideoIdeaGuide | null>(null);

  // Studio Player Sync States
  const [selectedClip, setSelectedClip] = useState<GeneratedShort | HistoryShort | null>(null);
  const [activeClipList, setActiveClipList] = useState<Array<GeneratedShort | HistoryShort>>([]);
  const [aspectRatio, setAspectRatio] = useState<string>('9:16');
  const [framingMode, setFramingMode] = useState<FramingMode>('podcast');
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>('karaoke');
  const [fontFamily, setFontFamily] = useState<string>('Montserrat Black');
  const [previewSubtitleText, setPreviewSubtitleText] = useState<string>('TEKS SUBTITLE PRATINJAU');
  const [studioEditingClip, setStudioEditingClip] = useState<EditableClip | null>(null);

  const pollIntervalRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const startPolling = useCallback((jobId: string, initialJob?: JobState | null) => {
    stopPolling();
    setIsLoading(true);
    setPollingError(null);
    setActiveJobId(jobId);
    if (initialJob) {
      setActiveJob(initialJob);
    }

    const poll = async () => {
      try {
        const job = await fetchJob(jobId);
        if (!job) {
          stopPolling();
          setIsLoading(false);
          setActiveJob(null);
          return;
        }

        setActiveJob(job);
        setPollingError(null);

        if (TERMINAL_STATUSES.has(job.status)) {
          stopPolling();
          setIsLoading(false);

          if (job.status === 'completed') {
            toast.success('Pembuatan klip selesai.');
            if (job.result) {
              setJobResult(job.result);
              if (job.result.shorts && job.result.shorts.length > 0) {
                setActiveClipList(job.result.shorts);
                setSelectedClip(job.result.shorts[0]);
                if (job.result.shorts[0].title) {
                  setPreviewSubtitleText(job.result.shorts[0].title);
                }
                setViewMode('studio');
                setWorkspace('clipper');
              }
            }
            fetchHistory().then((h) => setHistoryCount(h.total_videos)).catch(() => {});
          } else if (job.status === 'partial') {
            const successClips = job.result?.shorts?.length ?? job.result?.stats?.success ?? 0;
            const failedCount = job.result?.stats?.failed ?? 0;
            if (job.result && successClips > 0) {
              setJobResult(job.result);
              if (job.result.shorts && job.result.shorts.length > 0) {
                setActiveClipList(job.result.shorts);
                setSelectedClip(job.result.shorts[0]);
                if (job.result.shorts[0].title) {
                  setPreviewSubtitleText(job.result.shorts[0].title);
                }
                setViewMode('studio');
                setWorkspace('clipper');
              }
              toast.warning(
                job.error || `Selesai sebagian: ${successClips} klip berhasil dibuat, ${failedCount} klip gagal.`
              );
              fetchHistory().then((h) => setHistoryCount(h.total_videos)).catch(() => {});
            } else {
              toast.error(job.error || 'Proses dihentikan dan tidak ada klip yang berhasil dibuat.');
            }
          } else if (job.status === 'failed') {
            toast.error(job.error || 'Proses pembuatan klip gagal.');
          } else if (job.status === 'cancelled' || job.status === 'canceled') {
            if (job.result?.shorts && job.result.shorts.length > 0) {
              setJobResult(job.result);
              setActiveClipList(job.result.shorts);
              setSelectedClip(job.result.shorts[0]);
              if (job.result.shorts[0].title) {
                setPreviewSubtitleText(job.result.shorts[0].title);
              }
              setViewMode('studio');
              setWorkspace('clipper');
              toast.info(`Pekerjaan dibatalkan. ${job.result.shorts.length} klip tersimpan.`);
              fetchHistory().then((h) => setHistoryCount(h.total_videos)).catch(() => {});
            } else {
              toast.info('Pekerjaan telah dibatalkan.');
            }
          } else if (job.status === 'timeout') {
            if (job.result?.shorts && job.result.shorts.length > 0) {
              setJobResult(job.result);
              setActiveClipList(job.result.shorts);
              setSelectedClip(job.result.shorts[0]);
              if (job.result.shorts[0].title) {
                setPreviewSubtitleText(job.result.shorts[0].title);
              }
              setViewMode('studio');
              setWorkspace('clipper');
              fetchHistory().then((h) => setHistoryCount(h.total_videos)).catch(() => {});
            }
            toast.error(job.error || 'Pekerjaan melampaui batas waktu pengerjaan.');
          } else if (job.status === 'interrupted') {
            toast.error(job.error || 'Pekerjaan terinterupsi (server terhenti).');
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
        setPollingError('Koneksi polling ke server terputus. Memeriksa kembali...');
      }
    };

    void poll();
    pollIntervalRef.current = window.setInterval(poll, 1500);
  }, [stopPolling]);

  // Initialize config, check active job, load history
  useEffect(() => {
    async function init() {
      try {
        const conf = await fetchConfig();
        setConfig(conf);
      } catch (err) {
        console.warn('Config fetch error:', err);
      }

      try {
        const hist = await fetchHistory();
        setHistoryCount(hist.total_videos);
      } catch (err) {
        console.warn('History fetch error:', err);
      }

      try {
        const active = await fetchActiveJob();
        if (active.active && active.job_id) {
          toast.info(`Melanjutkan pemantauan pekerjaan (${active.job_id})...`);
          startPolling(active.job_id, active as unknown as JobState);
        }
      } catch (err) {
        console.warn('Active job check error:', err);
      }
    }

    init();

    return () => {
      stopPolling();
    };
  }, [startPolling, stopPolling]);

  const handleGenerate = async (payload: GeneratePayload) => {
    setJobResult(null);
    setIsLoading(true);
    setPollingError(null);

    try {
      const res = await submitGenerate(payload);
      toast.info('Pekerjaan dimulai di server. Menginisialisasi pipeline...');
      startPolling(res.job_id);
    } catch (err) {
      setIsLoading(false);
      const msg = err instanceof Error ? err.message : 'Gagal memulai proses.';
      toast.error(msg);
    }
  };

  const handleCancel = async () => {
    if (!activeJob?.job_id) return;
    setIsCanceling(true);

    try {
      const success = await cancelJob(activeJob.job_id);
      if (success) {
        toast.info('Perintah pembatalan terkirim.');
      } else {
        toast.error('Gagal mengirim perintah pembatalan.');
      }
    } catch {
      toast.error('Terjadi kesalahan jaringan saat membatalkan.');
    } finally {
      setIsCanceling(false);
    }
  };

  const handleRetryPolling = () => {
    if (activeJobId) {
      toast.info('Menyambungkan kembali ke server...');
      startPolling(activeJobId);
    }
  };

  const handleClipUpdated = (updatedClip: EditClipResponse['clip']) => {
    setJobResult((prev) => {
      if (!prev || !prev.shorts) return prev;
      return {
        ...prev,
        shorts: prev.shorts.map((s, idx) => {
          const matches =
            s.filename === updatedClip.filename ||
            idx + 1 === updatedClip.clip_index;
          if (matches) {
            return {
              ...s,
              web_url: updatedClip.web_url,
              vtt_url: updatedClip.vtt_url || undefined,
              start_time: updatedClip.start_time,
              end_time: updatedClip.end_time,
              aspect_ratio: updatedClip.aspect_ratio,
              title: updatedClip.title,
              hook_sentence: updatedClip.hook_sentence,
            };
          }
          return s;
        }),
      };
    });

    if (
      selectedClip &&
      (selectedClip.filename === updatedClip.filename ||
        (selectedClip as GeneratedShort).title === updatedClip.title)
    ) {
      setSelectedClip((prev) =>
        prev
          ? {
              ...prev,
              ...updatedClip,
              vtt_url: updatedClip.vtt_url || undefined,
            }
          : null
      );
      if (updatedClip.title) {
        setPreviewSubtitleText(updatedClip.title);
      }
    }

    setActiveClipList((prev) =>
      prev.map((c) =>
        c.filename === updatedClip.filename ||
        ('web_url' in c && c.web_url === updatedClip.web_url)
          ? {
              ...c,
              ...updatedClip,
              vtt_url: updatedClip.vtt_url || undefined,
            }
          : c
      )
    );

    fetchHistory()
      .then((h) => setHistoryCount(h.total_videos))
      .catch(() => {});
  };

  const handleSelectStudioClip = (clip: GeneratedShort | HistoryShort) => {
    setSelectedClip(clip);
    if (clip.title) {
      setPreviewSubtitleText(clip.title);
    }
  };

  const handleOpenStudioEditor = () => {
    if (!selectedClip) return;

    let folder = '';
    let clipIndex = 1;

    if ('folder_name' in selectedClip && selectedClip.folder_name) {
      folder = selectedClip.folder_name;
    } else if (jobResult?.session_folder) {
      folder = jobResult.session_folder;
    }

    if ('clip_index' in selectedClip && typeof selectedClip.clip_index === 'number') {
      clipIndex = selectedClip.clip_index;
    } else if (jobResult?.shorts) {
      const idx = jobResult.shorts.findIndex(
        (s) => s.filename === selectedClip.filename || (s.web_url && s.web_url === selectedClip.web_url)
      );
      if (idx !== -1) clipIndex = idx + 1;
    }

    setStudioEditingClip({
      session_folder: folder,
      clip_index: clipIndex,
      title: selectedClip.title || selectedClip.filename || `Klip #${clipIndex}`,
      start_time: typeof selectedClip.start_time === 'number' ? selectedClip.start_time : 0,
      end_time: typeof selectedClip.end_time === 'number' ? selectedClip.end_time : 15,
      aspect_ratio: selectedClip.aspect_ratio || aspectRatio || '9:16',
      web_url: selectedClip.web_url || ('clip_url' in selectedClip ? (selectedClip as GeneratedShort).clip_url : '') || '',
      vtt_url: selectedClip.vtt_url || null,
      score: selectedClip.score,
      framing_mode: selectedClip.framing_mode || framingMode,
      gaming_preset: selectedClip.gaming_preset,
    });
  };

  return (
    <div className="min-h-dvh flex flex-col bg-[#0A0A0F] text-[#F8FAFC] selection:bg-violet-600/30 selection:text-violet-300 w-full max-w-full overflow-x-hidden font-sans">
      <div className="ambient-bg" aria-hidden="true" />
      <Toaster position="top-right" richColors theme="dark" />
      <Header
        config={config}
        historyCount={historyCount}
        onOpenHistory={() => setIsHistoryOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      <main className="flex-1 w-full max-w-[1536px] mx-auto px-3.5 sm:px-6 lg:px-8 py-5 sm:py-6">
        {workspace === 'start' ? (
          <StartPage
            onStartIdeas={() => setWorkspace('ideas')}
            onStartClipping={() => {
              setWorkspace('clipper');
              setViewMode('clipper');
            }}
          />
        ) : workspace === 'ideas' ? (
          <IdeaFlow
            config={config}
            activeJob={activeJob}
            isCanceling={isCanceling}
            pollingError={pollingError}
            onCancelJob={handleCancel}
            onRetryPolling={handleRetryPolling}
            onVideoJobStarted={(jobId) => {
              setJobResult(null);
              toast.info('Tugas video dikirim ke Agnes AI...');
              startPolling(jobId);
            }}
            onBack={() => setWorkspace('start')}
            onOpenSettings={() => setIsSettingsOpen(true)}
            onUseFootage={(guide) => {
              setIdeaGuide(guide);
              setWorkspace('clipper');
              setViewMode('clipper');
            }}
          />
        ) : viewMode === 'clipper' ? (
          /* Mode 1: Clipper (1 kolom luas, max-w-7xl mx-auto) */
          <div className="w-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-200">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setWorkspace('start')}
              className="min-h-11 px-2 text-sm text-zinc-300 hover:text-white"
            >
              <ArrowLeft aria-hidden="true" />
              Kembali ke Mulai
            </Button>
            {ideaGuide && (
              <details className="rounded-lg border border-violet-400/30 bg-violet-950/15 px-4 py-3 text-sm">
                <summary className="min-h-9 cursor-pointer py-1 font-medium text-violet-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400">
                  Panduan ide: {ideaGuide.directionTitle}
                </summary>
                <div className="mt-3 space-y-3 border-t border-violet-400/15 pt-3">
                  <p className="text-zinc-300">Pembuka: <span className="text-white">{ideaGuide.selectedHook}</span></p>
                  <ol className="space-y-3">
                    {ideaGuide.plan.scenes.map((scene, index) => (
                      <li key={`${scene.visual}-${index}`} className="grid gap-1 border-b border-zinc-800/80 pb-3 sm:grid-cols-3 sm:gap-4">
                        <span className="text-xs text-violet-200">Adegan {index + 1}: {scene.visual}</span>
                        <span className="text-xs leading-5 text-zinc-300">{scene.spoken}</span>
                        <span className="text-xs leading-5 text-zinc-400">Teks layar: {scene.onscreen}</span>
                      </li>
                    ))}
                  </ol>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-400">
                    <span>Penutup: {ideaGuide.plan.closing}</span>
                    <button type="button" onClick={() => setIdeaGuide(null)} className="min-h-11 rounded-md px-3 text-zinc-300 underline underline-offset-4 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400">Tutup panduan</button>
                  </div>
                </div>
              </details>
            )}
            <GeneratorForm
              config={config}
              isLoading={isLoading}
              onSubmit={handleGenerate}
              aspectRatio={aspectRatio}
              onAspectRatioChange={(ratio) => setAspectRatio(ratio)}
              subtitleStyle={subtitleStyle}
              onSubtitleStyleChange={(style) => setSubtitleStyle(style)}
              fontFamily={fontFamily}
              onFontFamilyChange={(font) => setFontFamily(font)}
              framingMode={framingMode}
              onFramingModeChange={(mode) => setFramingMode(mode)}
            />

            {/* Status Progres Pekerjaan */}
            {activeJob && (activeJob.status === 'running' || activeJob.status === 'queued' || activeJob.status === 'canceling') && (
              <div className="animate-in fade-in duration-300">
                <JobProgressCard
                  job={activeJob}
                  onCancel={handleCancel}
                  isCanceling={isCanceling}
                  pollingError={pollingError}
                  onRetry={handleRetryPolling}
                />
              </div>
            )}

            {/* Tombol Buka Studio jika klip sebelumnya ada */}
            {Boolean(jobResult?.shorts && jobResult.shorts.length > 0) && (
              <div className="flex justify-center sm:justify-end pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setViewMode('studio')}
                  className="text-xs h-9 px-4 text-violet-300 hover:text-white border-violet-800/60 bg-violet-950/40 hover:bg-violet-900/50 cursor-pointer flex items-center gap-2 transition-colors font-medium rounded-xl shadow-lg shadow-violet-950/20"
                >
                  <Film className="w-3.5 h-3.5 text-violet-400" />
                  <span>Buka Studio →</span>
                </Button>
              </div>
            )}
          </div>
        ) : (
          /* Mode 2: Studio (1 kolom luas, max-w-7xl mx-auto) */
          <div className="w-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-200">
            {/* Header Bar Studio: Tombol Balik & Judul Klip Aktif */}
            <div className="flex items-center justify-between pb-3 gap-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setViewMode('clipper')}
                className="text-xs h-8 px-3 text-zinc-300 hover:text-white border-zinc-800 hover:bg-zinc-800/60 cursor-pointer shrink-0 flex items-center gap-1.5 rounded-lg"
              >
                ← Buat Klip Baru
              </Button>

              {selectedClip && (
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs text-zinc-400 hidden sm:inline">Klip Aktif:</span>
                  <span className="text-xs font-mono text-cyan-400 bg-cyan-950/40 px-2.5 py-1 rounded-md border border-cyan-800/40 truncate max-w-xs sm:max-w-md">
                    {selectedClip.title || selectedClip.filename}
                  </span>
                </div>
              )}
            </div>
            <div className="glow-divider" aria-hidden="true" />

            {/* Stage Pemutar Video & Monitor Subtitle */}
            <StudioVideoPlayer
              clip={selectedClip}
              clipsList={
                activeClipList.length > 0
                  ? activeClipList
                  : jobResult?.shorts && jobResult.shorts.length > 0
                  ? jobResult.shorts
                  : selectedClip
                  ? [selectedClip]
                  : []
              }
              onSelectClip={handleSelectStudioClip}
              aspectRatio={aspectRatio}
              subtitleStyle={subtitleStyle}
              fontFamily={fontFamily}
              subtitleText={previewSubtitleText}
              framingMode={framingMode}
              onSubtitleTextChange={(txt) => setPreviewSubtitleText(txt)}
              onAspectRatioChange={(ratio) => setAspectRatio(ratio)}
              onSubtitleStyleChange={(style) => setSubtitleStyle(style)}
              onFontFamilyChange={(font) => setFontFamily(font)}
              onClearClip={() => setSelectedClip(null)}
              onEditClip={handleOpenStudioEditor}
            />

            {/* Antrean Klip Hasil */}
            {jobResult && (
              <div className="pt-2">
                <ResultsGallery
                  result={jobResult}
                  selectedClip={selectedClip}
                  onSelectClip={(clip: GeneratedShort) => {
                    handleSelectStudioClip(clip);
                    if (jobResult.shorts && jobResult.shorts.length > 0) {
                      setActiveClipList(jobResult.shorts);
                    }
                  }}
                  onClipUpdated={handleClipUpdated}
                />
              </div>
            )}
          </div>
        )}
      </main>

      <div className="glow-divider w-full max-w-[1536px] mx-auto" aria-hidden="true" />
      <footer className="py-4 text-center text-xs text-zinc-500 w-full max-w-[1536px] mx-auto px-4 font-sans">
        <p>Reef Clipper • Studio Pemotong Video YouTube ke Klip Pendek</p>
      </footer>

      {/* Studio Clip Editor Modal */}
      {studioEditingClip && (
        <ClipEditorModal
          isOpen={Boolean(studioEditingClip)}
          onClose={() => setStudioEditingClip(null)}
          clip={studioEditingClip}
          onClipSaved={(updatedClip) => {
            handleClipUpdated(updatedClip);
            setStudioEditingClip(null);
          }}
        />
      )}

      {/* History Modal */}
      <HistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onHistoryChange={(newCount) => setHistoryCount(newCount)}
        onSelectClipForStudio={(clip, sessionClips) => {
          setSelectedClip(clip);
          if (sessionClips && sessionClips.length > 0) {
            setActiveClipList(sessionClips);
          } else {
            setActiveClipList([clip]);
          }
          if (clip.title) setPreviewSubtitleText(clip.title);
          setViewMode('studio');
          setWorkspace('clipper');
        }}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onConfigUpdated={(newConfig) => setConfig(newConfig)}
      />
    </div>
  );
}

export default App;
