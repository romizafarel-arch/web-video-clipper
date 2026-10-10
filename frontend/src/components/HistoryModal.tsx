import { useState, useEffect, useCallback, type FC } from 'react';
import {
  X,
  FolderOpen,
  Trash2,
  Play,
  Download,
  Sparkles,
  RefreshCw,
  Clock,
  ChevronDown,
  ChevronUp,
  Film,
  Scissors,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import type { HistorySession, HistoryShort, EditableClip, EditClipResponse } from '../types';
import { fetchHistory, deleteHistorySession, openOutputFolder } from '../lib/api';
import { ClipEditorModal } from './ClipEditorModal';

const formatBytes = (bytes?: number) => {
  if (!bytes || bytes <= 0) return '0 MB';
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
};

const formatSeconds = (sec?: number | null) => {
  if (typeof sec !== 'number') return '00:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

interface HistoryClipCardProps {
  clip: HistoryShort;
  session: HistorySession;
  idx: number;
  onSelectClipForStudio?: (clip: HistoryShort, sessionShorts?: HistoryShort[]) => void;
  onPreviewClip: (clip: HistoryShort) => void;
  onOpenEditor: (clip: HistoryShort, folderName?: string, idx?: number) => void;
  onCloseModal: () => void;
}

const HistoryClipCard: FC<HistoryClipCardProps> = ({
  clip,
  session,
  idx,
  onSelectClipForStudio,
  onPreviewClip,
  onOpenEditor,
  onCloseModal,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const hasScore = typeof clip.score === 'number' && clip.score > 0;
  const clipAr = clip.aspect_ratio || session.aspect_ratio || '9:16';
  const thumbAspect =
    clipAr === '1:1'
      ? 'aspect-square'
      : clipAr === '16:9'
      ? 'aspect-video'
      : 'aspect-[9/16]';

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={() => setIsHovered(true)}
      onBlur={() => setIsHovered(false)}
      className="group rounded-xl border border-white/10 bg-[#0d0d14] overflow-hidden flex flex-col justify-between hover:border-violet-500/40 transition-all shadow-md"
    >
      {/* Video Thumbnail / Preview Area */}
      <div className={`relative ${thumbAspect} bg-black/80 flex items-center justify-center overflow-hidden`}>
        {/* Static poster placeholder to avoid premature GPU video decoder initialization */}
        <div className="w-full h-full flex flex-col items-center justify-center bg-zinc-950 text-zinc-600 select-none">
          <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/5 flex items-center justify-center">
            <Film className="w-5 h-5 text-zinc-500" />
          </div>
        </div>

        {/* Lazy loaded video decoder: only mounts when hovered/focused */}
        {isHovered && (
          <video
            src={clip.web_url}
            preload="metadata"
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover pointer-events-none group-hover:scale-105 transition-transform duration-300 motion-reduce:transition-none"
          />
        )}

        {/* Accessible Button trigger for Preview */}
        <button
          type="button"
          aria-label={`Tonton video ${clip.title || clip.filename}`}
          onClick={() => onPreviewClip(clip)}
          className="absolute inset-0 bg-black/30 group-hover:bg-black/10 flex items-center justify-center cursor-pointer transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          <div className="w-10 h-10 rounded-full bg-violet-600/90 text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform motion-reduce:transition-none">
            <Play className="w-5 h-5 ml-0.5 fill-white" />
          </div>
        </button>

        {/* Virality score badge */}
        {hasScore && (
          <div className="absolute top-2 left-2 px-2 py-0.5 rounded-full bg-emerald-500/90 text-white text-[10px] font-bold flex items-center gap-1 shadow-md font-mono pointer-events-none">
            <Sparkles className="w-2.5 h-2.5" />
            Score {clip.score}
          </div>
        )}

        {/* Ratio badge */}
        <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white/90 pointer-events-none">
          {clipAr}
        </div>

        {/* Duration badge */}
        <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white/90 pointer-events-none">
          {formatSeconds(clip.start_time)} - {formatSeconds(clip.end_time)}
        </div>
      </div>

      {/* Clip Info */}
      <div className="p-3 flex-1 flex flex-col justify-between space-y-2">
        <div>
          <h5 className="text-xs font-semibold text-white line-clamp-2 leading-tight" title={clip.title}>
            {clip.title || clip.filename}
          </h5>
          {clip.hook_sentence && (
            <p className="text-[10px] text-slate-400 line-clamp-1 italic mt-1" title={clip.hook_sentence}>
              "{clip.hook_sentence}"
            </p>
          )}
        </div>

        {/* Card Footer: 2-Tingkat */}
        <div className="pt-2.5 border-t border-white/5 flex flex-col gap-2">
          {/* Baris Atas: Meta & Download */}
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-mono text-[11px] text-slate-400 font-medium">
              {formatBytes(clip.size_bytes)}
            </span>
            <a
              href={clip.web_url}
              download={clip.filename}
              className="min-h-[36px] min-w-[36px] w-9 h-9 rounded-lg bg-white/5 hover:bg-white/10 hover:text-white border border-white/10 hover:border-white/20 active:scale-95 text-slate-300 flex items-center justify-center transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 shadow-sm"
              title={`Unduh file video MP4 (${clipAr})`}
              aria-label={`Unduh file video MP4 ${clip.filename}`}
            >
              <Download className="w-4 h-4" />
            </a>
          </div>

          {/* Baris Bawah: Main Actions */}
          <div className="grid grid-cols-2 gap-2 w-full">
            <button
              type="button"
              onClick={() => {
                if (onSelectClipForStudio) {
                  onSelectClipForStudio(clip, session.shorts);
                  onCloseModal();
                  toast.success(`Klip "${clip.title || clip.filename}" dimuat di Player Studio`);
                } else {
                  onPreviewClip(clip);
                }
              }}
              className="w-full min-h-[40px] px-2 py-2 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 active:scale-[0.98] border border-cyan-500/20 hover:border-cyan-500/40 text-cyan-300 font-medium transition-all flex items-center justify-center gap-1.5 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 text-xs shadow-sm"
              title="Buka dan tonton di Player Studio Utama"
              aria-label={`Buka klip ${clip.title || clip.filename} di Studio`}
            >
              <Film className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Studio</span>
            </button>

            <button
              type="button"
              onClick={() => onOpenEditor(clip, session.folder_name, idx)}
              className="w-full min-h-[40px] px-2 py-2 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 active:scale-[0.98] border border-violet-500/20 hover:border-violet-500/40 text-violet-300 font-medium transition-all flex items-center justify-center gap-1.5 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 text-xs shadow-sm"
              title="Edit klip (trimmer dan subtitle)"
              aria-label={`Edit klip ${clip.title || clip.filename}`}
            >
              <Scissors className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Edit</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

interface HistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onHistoryChange?: (totalCount: number) => void;
  onSelectClipForStudio?: (clip: HistoryShort, sessionShorts?: HistoryShort[]) => void;
}

export const HistoryModal: FC<HistoryModalProps> = ({
  isOpen,
  onClose,
  onHistoryChange,
  onSelectClipForStudio,
}) => {
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [expandedSessions, setExpandedSessions] = useState<Record<string, boolean>>({});
  const [previewClip, setPreviewClip] = useState<HistoryShort | null>(null);
  const [deletingFolder, setDeletingFolder] = useState<string | null>(null);
  const [editingClip, setEditingClip] = useState<EditableClip | null>(null);

  const handleOpenEditor = (clip: HistoryShort, folderName?: string, idx?: number) => {
    const clipIndex = clip.clip_index ?? (typeof idx === 'number' ? idx + 1 : 1);
    setEditingClip({
      session_folder: clip.folder_name || folderName || '',
      clip_index: clipIndex,
      title: clip.title || clip.filename,
      start_time: typeof clip.start_time === 'number' ? clip.start_time : 0,
      end_time: typeof clip.end_time === 'number' ? clip.end_time : 15,
      aspect_ratio: clip.aspect_ratio || '9:16',
      web_url: clip.web_url,
      vtt_url: clip.vtt_url || null,
      score: clip.score,
    });
  };

  const handleClipSaved = (updatedClip: EditClipResponse['clip']) => {
    if (
      previewClip &&
      (previewClip.filename === updatedClip.filename ||
        previewClip.clip_index === updatedClip.clip_index)
    ) {
      setPreviewClip({
        ...previewClip,
        web_url: updatedClip.web_url,
        vtt_url: updatedClip.vtt_url,
        start_time: updatedClip.start_time,
        end_time: updatedClip.end_time,
        aspect_ratio: updatedClip.aspect_ratio,
        title: updatedClip.title,
        hook_sentence: updatedClip.hook_sentence,
      });
    }

    void loadData();
  };


  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchHistory();
      setSessions(res.sessions || []);
      const initialExpanded: Record<string, boolean> = {};
      (res.sessions || []).forEach((s) => {
        initialExpanded[s.id || s.folder_name] = true;
      });
      setExpandedSessions(initialExpanded);
      if (onHistoryChange) {
        onHistoryChange(res.total_videos);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Kesalahan jaringan';
      toast.error('Gagal memuat riwayat: ' + msg);
    } finally {
      setLoading(false);
    }
  }, [onHistoryChange]);

  useEffect(() => {
    if (isOpen) {
      queueMicrotask(() => {
        void loadData();
      });
    }
  }, [isOpen, loadData]);

  const toggleSession = (id: string) => {
    setExpandedSessions((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleOpenFolder = async (folderName?: string) => {
    try {
      await openOutputFolder(folderName);
      toast.success(
        folderName
          ? `Folder sesi "${folderName}" dibuka di File Explorer`
          : 'Folder output dibuka di File Explorer'
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Gagal membuka folder di file manager';
      toast.error(msg);
    }
  };

  const handleDeleteSession = async (folderName: string, sessionTitle: string) => {
    if (!folderName) {
      toast.error('Sesi legacy root tidak dapat dihapus sekaligus.');
      return;
    }

    const confirmed = window.confirm(
      `Yakin ingin menghapus seluruh sesi "${sessionTitle || folderName}" beserta semua file klip videonya?`
    );
    if (!confirmed) return;

    setDeletingFolder(folderName);
    try {
      await deleteHistorySession(folderName);
      toast.success(`Sesi "${sessionTitle || folderName}" berhasil dihapus.`);
      setSessions((prev) => {
        const next = prev.filter((s) => s.folder_name !== folderName);
        const totalCount = next.reduce((acc, curr) => acc + (curr.shorts?.length || 0), 0);
        if (onHistoryChange) {
          onHistoryChange(totalCount);
        }
        return next;
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Gagal menghapus sesi video.';
      toast.error(msg);
    } finally {
      setDeletingFolder(null);
    }
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
        <DialogContent
          className="max-w-5xl w-full max-h-[90vh] bg-[#0f0f17] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden p-0 gap-0 sm:max-w-5xl"
          showCloseButton={false}
        >
          {/* Modal Header */}
          <DialogHeader className="flex flex-row items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
                <Film className="w-5 h-5 text-violet-400" />
              </div>
              <div>
                <DialogTitle className="text-lg font-bold text-white font-['Sora'] flex items-center gap-2">
                  Riwayat Sesi & Video Shorts
                </DialogTitle>
                <p className="text-xs text-slate-400">
                  Arsip klip video yang tersimpan di direktori lokal output
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleOpenFolder()}
                className="min-h-[44px] px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-300 hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                title="Buka direktori output utama di File Explorer"
              >
                <FolderOpen className="w-3.5 h-3.5 text-amber-400" />
                <span className="hidden sm:inline">Folder Output</span>
              </button>

              <button
                type="button"
                onClick={loadData}
                disabled={loading}
                className="min-h-[44px] min-w-[44px] w-[44px] h-[44px] p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                title="Muat ulang riwayat"
                aria-label="Muat ulang data riwayat"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-violet-400' : ''}`} />
              </button>

              <button
                type="button"
                onClick={onClose}
                className="min-h-[44px] min-w-[44px] w-[44px] h-[44px] p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white flex items-center justify-center transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                title="Tutup dialog"
                aria-label="Tutup dialog riwayat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </DialogHeader>

          {/* Modal Content / Sessions List */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
            {loading && sessions.length === 0 ? (
              <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-3">
                <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
                <p className="text-sm">Memuat data riwayat klip...</p>
              </div>
            ) : sessions.length === 0 ? (
              <div className="py-20 text-center flex flex-col items-center justify-center space-y-3">
                <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-slate-500">
                  <Film className="w-7 h-7" />
                </div>
                <h4 className="text-base font-semibold text-white">Belum Ada Riwayat Shorts</h4>
                <p className="text-xs text-slate-400 max-w-sm">
                  Video shorts yang Anda generate akan otomatis tersimpan dan diarsipkan di halaman ini.
                </p>
              </div>
            ) : (
              sessions.map((session) => {
                const sessionKey = session.id || session.folder_name;
                const isExpanded = expandedSessions[sessionKey] ?? true;
                const isDeleting = deletingFolder === session.folder_name;

                return (
                  <div
                    key={sessionKey}
                    className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden transition-all"
                  >
                    {/* Session Header */}
                    <div
                      role="button"
                      tabIndex={0}
                      aria-expanded={isExpanded}
                      onClick={() => toggleSession(sessionKey)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          toggleSession(sessionKey);
                        }
                      }}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3.5 bg-white/[0.03] hover:bg-white/[0.05] cursor-pointer transition-colors border-b border-white/5 select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded-t-xl"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center shrink-0">
                          <Film className="w-4 h-4 text-violet-400" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-white truncate max-w-md">
                            {session.title || session.folder_name || 'Sesi Pembuatan'}
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                            {session.created_at && (
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3 text-slate-500" />
                                {session.created_at}
                              </span>
                            )}
                            <span>•</span>
                            <span>{session.shorts?.length || 0} Klip</span>
                            <span>•</span>
                            <span>{formatBytes(session.total_size_bytes)}</span>
                            {session.aspect_ratio && (
                              <>
                                <span>•</span>
                                <span className="font-mono text-violet-300">{session.aspect_ratio}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center" onClick={(e) => e.stopPropagation()}>
                        {session.folder_name && (
                          <button
                            type="button"
                            onClick={() => handleOpenFolder(session.folder_name)}
                            className="min-h-[44px] px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-slate-300 hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                            title="Buka folder sesi ini di File Explorer"
                          >
                            <FolderOpen className="w-3.5 h-3.5 text-amber-400" />
                            <span>Folder</span>
                          </button>
                        )}

                        {session.folder_name && (session.shorts?.length || 0) > 0 && (
                          <a
                            href={`/api/sessions/${encodeURIComponent(session.folder_name)}/zip`}
                            download={`${session.folder_name}_clips.zip`}
                            className="min-h-[44px] px-3.5 py-2 rounded-xl bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/20 text-xs text-violet-300 hover:text-violet-200 flex items-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                            title="Download semua klip sesi ini sebagai arsip ZIP"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>ZIP</span>
                          </a>
                        )}

                        {!session.is_legacy && session.folder_name && (
                          <button
                            type="button"
                            disabled={isDeleting}
                            onClick={() => handleDeleteSession(session.folder_name, session.title)}
                            className="min-h-[44px] px-3.5 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-xs text-rose-300 hover:text-rose-200 flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
                            title="Hapus sesi ini dan semua videonya"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>{isDeleting ? 'Menghapus...' : 'Hapus'}</span>
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={() => toggleSession(sessionKey)}
                          aria-label={isExpanded ? 'Tutup sesi' : 'Buka sesi'}
                          aria-expanded={isExpanded}
                          className="min-h-[44px] min-w-[44px] w-[44px] h-[44px] p-2 rounded-xl text-slate-400 hover:text-white flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 cursor-pointer"
                        >
                          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Session Clips Grid */}
                    {isExpanded && (
                      <div className="p-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                        {(session.shorts || []).map((clip, idx) => (
                          <HistoryClipCard
                            key={clip.filename || idx}
                            clip={clip}
                            session={session}
                            idx={idx}
                            onSelectClipForStudio={onSelectClipForStudio}
                            onPreviewClip={setPreviewClip}
                            onOpenEditor={handleOpenEditor}
                            onCloseModal={onClose}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Modal Footer */}
          <div className="px-6 py-3.5 border-t border-white/10 bg-white/[0.02] flex items-center justify-between text-xs text-slate-400">
            <span>
              Total: <strong>{sessions.reduce((acc, s) => acc + (s.shorts?.length || 0), 0)}</strong> Klip Shorts
            </span>
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] px-5 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white transition-colors cursor-pointer text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            >
              Tutup
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Embedded Video Player Modal - Accessible with keyboard and dynamic aspect ratio */}
      {previewClip && (
        <Dialog open={Boolean(previewClip)} onOpenChange={(open) => !open && setPreviewClip(null)}>
          {(() => {
            const ar = previewClip.aspect_ratio || '9:16';
            const modalWidth = ar === '16:9' ? 'sm:max-w-2xl' : ar === '1:1' ? 'sm:max-w-md' : 'sm:max-w-sm';
            const playerAspect = ar === '16:9' ? 'aspect-video' : ar === '1:1' ? 'aspect-square' : 'aspect-[9/16]';

            return (
              <DialogContent
                className={`w-full bg-[#0a0a0f] border border-white/20 rounded-2xl overflow-hidden shadow-2xl flex flex-col p-0 gap-0 ${modalWidth}`}
                showCloseButton={false}
              >
                {/* Player Header */}
                <DialogHeader className="flex flex-row items-center justify-between p-3.5 border-b border-white/10 bg-white/5">
                  <DialogTitle className="text-xs font-semibold text-white truncate max-w-[260px]">
                    {previewClip.title || previewClip.filename}
                  </DialogTitle>
                  <button
                    type="button"
                    onClick={() => setPreviewClip(null)}
                    className="min-h-[44px] min-w-[44px] w-[44px] h-[44px] p-2.5 text-slate-400 hover:text-white flex items-center justify-center rounded-xl cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                    aria-label="Tutup video player"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </DialogHeader>

                {/* Dynamic Aspect Ratio Video Player Container */}
                <div className={`relative w-full ${playerAspect} bg-black flex items-center justify-center`}>
                  <video
                    controls
                    autoPlay
                    playsInline
                    className="w-full h-full object-contain"
                    src={previewClip.web_url}
                  >
                    {previewClip.vtt_url && (
                      <track src={previewClip.vtt_url} kind="subtitles" srcLang="id" label="Subtitles" default />
                    )}
                    Browser Anda tidak mendukung pemutaran video.
                  </video>
                </div>

                {/* Player Footer Action */}
                <div className="p-3 bg-white/5 border-t border-white/10 flex items-center justify-between">
                  <div className="text-[11px] text-slate-400 font-mono">
                    {formatSeconds(previewClip.start_time)} - {formatSeconds(previewClip.end_time)} ({ar})
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        handleOpenEditor(previewClip, previewClip.folder_name);
                      }}
                      className="min-h-[44px] px-3.5 py-2 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 hover:text-white border border-violet-500/30 text-xs font-medium flex items-center gap-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 cursor-pointer"
                    >
                      <Scissors className="w-3.5 h-3.5" />
                      <span>Edit Klip</span>
                    </button>
                    <a
                      href={previewClip.web_url}
                      download={previewClip.filename}
                      className="min-h-[44px] px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium flex items-center gap-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Unduh MP4 ({ar})</span>
                    </a>
                  </div>
                </div>
              </DialogContent>
            );
          })()}
        </Dialog>
      )}

      {/* Clip Editor Modal */}
      {editingClip && (
        <ClipEditorModal
          isOpen={Boolean(editingClip)}
          onClose={() => setEditingClip(null)}
          clip={editingClip}
          onClipSaved={handleClipSaved}
        />
      )}
    </>
  );
};
