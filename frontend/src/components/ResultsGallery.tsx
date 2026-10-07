import { useState, type FC } from 'react';
import { Download, Sparkles, CheckCircle2, Scissors, Play, Film } from 'lucide-react';
import type { JobResult, GeneratedShort, HistoryShort, EditableClip, EditClipResponse } from '../types';
import { ClipEditorModal } from './ClipEditorModal';

export interface ResultsGalleryProps {
  result: JobResult;
  onClipUpdated?: (updatedClip: EditClipResponse['clip']) => void;
  selectedClip?: GeneratedShort | HistoryShort | null;
  onSelectClip?: (clip: GeneratedShort) => void;
}

export const ResultsGallery: FC<ResultsGalleryProps> = ({
  result,
  onClipUpdated,
  selectedClip,
  onSelectClip,
}) => {
  const [editingClip, setEditingClip] = useState<EditableClip | null>(null);
  const shortsList = result.shorts || [];

  if (shortsList.length === 0) {
    return null;
  }

  const formatSeconds = (sec?: number) => {
    if (typeof sec !== 'number') return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const handleOpenEditor = (short: GeneratedShort, idx: number) => {
    setEditingClip({
      session_folder: result.session_folder || '',
      clip_index: idx + 1,
      title: short.title || `Klip #${idx + 1}`,
      start_time: typeof short.start_time === 'number' ? short.start_time : 0,
      end_time: typeof short.end_time === 'number' ? short.end_time : 15,
      aspect_ratio: short.aspect_ratio || result.aspect_ratio || '9:16',
      web_url: short.web_url || short.clip_url || '',
      vtt_url: short.vtt_url || null,
      score: short.score,
      framing_mode: short.framing_mode,
      gaming_preset: short.gaming_preset,
    });
  };

  const handleClipSaved = (updatedClip: EditClipResponse['clip']) => {
    if (onClipUpdated) {
      onClipUpdated(updatedClip);
    }
  };

  return (
    <div className="space-y-3.5 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800 pb-3">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-zinc-100 flex items-center gap-2 font-headline">
            <CheckCircle2 className="w-4.5 h-4.5 text-emerald-400" />
            <span>Antrean Klip Hasil ({shortsList.length} Klip)</span>
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5 truncate max-w-xl">
            {result.video_title || 'Hasil pemotongan video YouTube'}
          </p>
        </div>
      </div>

      {/* Grid of Video Cards in Inspector Panel */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3.5">
        {shortsList.map((short, idx) => {
          const videoSrc = short.web_url || short.clip_url || '';
          const hasScore = typeof short.score === 'number';
          const isSelected = Boolean(
            selectedClip &&
              (selectedClip.filename === short.filename ||
                ('web_url' in selectedClip && selectedClip.web_url && selectedClip.web_url === videoSrc))
          );

          return (
            <div
              key={short.filename || idx}
              className={`rounded-xl p-3 flex flex-col justify-between border transition-colors relative bg-[#12121A] ${
                isSelected
                  ? 'border-violet-500 ring-1 ring-violet-500/50 shadow-sm'
                  : 'border-zinc-800 hover:border-zinc-700'
              }`}
            >
              <div className="space-y-2.5">
                {/* Header card with Score & Ratio */}
                <div className="flex items-center justify-between gap-1.5 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-violet-600/20 text-violet-300 border border-violet-500/30 font-headline">
                      Klip #{idx + 1}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
                      {short.aspect_ratio || result.aspect_ratio || '9:16'}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {isSelected && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-violet-600/30 text-violet-200 border border-violet-400/40 flex items-center gap-1 font-mono">
                        <Film className="w-3 h-3 text-violet-300" />
                        Di Monitor
                      </span>
                    )}

                    {hasScore && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 font-mono">
                        <Sparkles className="w-3 h-3 text-emerald-400" />
                        Skor {short.score}/100
                      </span>
                    )}
                  </div>
                </div>

                {/* Video Player Container */}
                {(() => {
                  const ar = short.aspect_ratio || result.aspect_ratio || '9:16';
                  const aspectClass =
                    ar === '1:1'
                      ? 'aspect-square max-h-[260px]'
                      : ar === '16:9'
                      ? 'aspect-video max-h-[220px]'
                      : 'aspect-[9/16] max-h-[320px]';

                  return (
                    <div className={`relative w-full ${aspectClass} bg-black rounded-lg overflow-hidden border border-zinc-800 flex items-center justify-center`}>
                      {videoSrc ? (
                        <video
                          key={videoSrc}
                          controls
                          playsInline
                          preload="metadata"
                          className="w-full h-full object-contain"
                        >
                          <source src={videoSrc} type="video/mp4" />
                          {short.vtt_url && (
                            <track src={short.vtt_url} kind="subtitles" srcLang="id" label="Subtitles" default />
                          )}
                          Browser tidak mendukung video HTML5.
                        </video>
                      ) : (
                        <div className="p-4 text-center text-xs text-rose-400">
                          File video tidak tersedia.
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Metadata & Summary */}
                <div className="space-y-1 pt-0.5">
                  <div className="text-xs font-semibold text-zinc-100 line-clamp-2">
                    {short.title || `Klip Highlight #${idx + 1}`}
                  </div>

                  <div className="flex items-center gap-2 text-[11px] text-zinc-400 font-mono">
                    <span>
                      {formatSeconds(short.start_time)} - {formatSeconds(short.end_time)}
                    </span>
                    {typeof short.start_time === 'number' && typeof short.end_time === 'number' && (
                      <span>({Math.round(short.end_time - short.start_time)} dtk)</span>
                    )}
                  </div>

                  {short.summary && (
                    <p className="text-[11px] text-zinc-400 line-clamp-2 italic">
                      "{short.summary}"
                    </p>
                  )}
                </div>
              </div>

              {/* Action Buttons: Tonton di Monitor + Edit Klip + Unduh */}
              {videoSrc && (
                <div className="pt-2.5 mt-2 border-t border-zinc-800 flex items-center gap-1.5">
                  {onSelectClip && (
                    <button
                      type="button"
                      onClick={() => onSelectClip(short)}
                      className={`min-h-[36px] flex-1 py-1.5 px-2.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                        isSelected
                          ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50'
                          : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60'
                      }`}
                      title="Tonton di Monitor Studio"
                      aria-label={`Tonton klip #${idx + 1} di Monitor Studio`}
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>{isSelected ? 'Di Monitor' : 'Tonton'}</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => handleOpenEditor(short, idx)}
                    className="min-h-[36px] py-1.5 px-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border border-zinc-700/60 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                    title="Buka timeline trimmer & editor subtitle"
                    aria-label={`Edit klip #${idx + 1}`}
                  >
                    <Scissors className="w-3.5 h-3.5" />
                    <span>Edit</span>
                  </button>

                  <a
                    href={videoSrc}
                    download={short.filename || `short_${idx + 1}.mp4`}
                    target="_blank"
                    rel="noreferrer"
                    className="min-h-[36px] py-1.5 px-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
                    title={`Unduh MP4 (${short.aspect_ratio || result.aspect_ratio || '9:16'})`}
                    aria-label={`Unduh video MP4 klip #${idx + 1}`}
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Unduh</span>
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Clip Editor Modal */}
      {editingClip && (
        <ClipEditorModal
          isOpen={Boolean(editingClip)}
          onClose={() => setEditingClip(null)}
          clip={editingClip}
          onClipSaved={handleClipSaved}
        />
      )}
    </div>
  );
};
