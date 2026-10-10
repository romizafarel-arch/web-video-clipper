import { useState, useEffect, useRef, useCallback, type FC, type ChangeEvent } from 'react';
import {
  X,
  Play,
  Pause,
  RotateCcw,
  Scissors,
  Plus,
  Trash2,
  Clock,
  AlertCircle,
  Type,
  Sliders,
  RefreshCw,
  Save,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import type { EditableClip, EditClipResponse, SubtitleCue, FramingMode, GamingLayout, SubtitleStyle } from '../types';
import { editClip } from '../lib/api';
import { parseVTT, formatTimeDisplay } from '../lib/vtt';
import { VisualPresetPicker } from './VisualPresetPicker';
import { FontFamilyPicker } from './FontFamilyPicker';
import { LiveSubtitleOverlay } from './LiveSubtitleOverlay';
import { normalizePresetId } from '../lib/textPresets';
import { getDefaultFontForPreset } from '../lib/fontFamilyLibrary';

export interface ClipEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  clip: EditableClip | null;
  onClipSaved: (updatedClip: EditClipResponse['clip']) => void;
}

export const ClipEditorModal: FC<ClipEditorModalProps> = ({
  isOpen,
  onClose,
  clip,
  onClipSaved,
}) => {
  const [startTime, setStartTime] = useState<number>(() => clip?.start_time ?? 0);
  const [endTime, setEndTime] = useState<number>(() => clip?.end_time ?? (clip?.start_time ? clip.start_time + 15 : 15));
  const [aspectRatio, setAspectRatio] = useState<string>(() => clip?.aspect_ratio || '9:16');
  const [framingMode, setFramingMode] = useState<FramingMode>(() => clip?.framing_mode || 'podcast');
  const [gamingPreset, setGamingPreset] = useState<string>(() => clip?.gaming_preset || 'auto');
  const [gamingLayout, setGamingLayout] = useState<GamingLayout>(() => clip?.gaming_layout || 'cam_top');
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>(() =>
    clip?.subtitle_style && clip.subtitle_style !== 'none' ? clip.subtitle_style : 'karaoke'
  );
  const [fontFamily, setFontFamily] = useState<string>(() =>
    clip?.font_family || getDefaultFontForPreset(normalizePresetId(clip?.subtitle_style))
  );
  const [burnSubtitles, setBurnSubtitles] = useState<boolean>(() => clip?.subtitle_style !== 'none');
  const [title, setTitle] = useState<string>(() => clip?.title || `Klip #${clip?.clip_index || 1}`);

  const [cues, setCues] = useState<SubtitleCue[]>([]);
  const [loadingVtt, setLoadingVtt] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'trimmer' | 'subtitles'>('trimmer');

  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [videoDuration, setVideoDuration] = useState<number>(0);

  const [isRendering, setIsRendering] = useState<boolean>(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const playRangeTimerRef = useRef<number | null>(null);

  // Initial reference bounds
  const origStart = clip?.start_time ?? 0;
  const origEnd = clip?.end_time ?? 15;

  // Load VTT subtitles
  useEffect(() => {
    if (!clip?.vtt_url || !isOpen) {
      return;
    }

    let isMounted = true;
    fetch(clip.vtt_url)
      .then((res) => {
        if (!res.ok) throw new Error('VTT file not found');
        return res.text();
      })
      .then((vttContent) => {
        if (isMounted) {
          const parsed = parseVTT(vttContent);
          setCues(parsed);
        }
      })
      .catch((err) => {
        console.warn('Gagal memuat subtitle VTT:', err);
        if (isMounted) setCues([]);
      })
      .finally(() => {
        if (isMounted) setLoadingVtt(false);
      });

    return () => {
      isMounted = false;
      if (playRangeTimerRef.current) {
        window.clearTimeout(playRangeTimerRef.current);
        playRangeTimerRef.current = null;
      }
    };
  }, [clip?.vtt_url, isOpen]);


  // Video event listeners
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setVideoDuration(videoRef.current.duration || 0);
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      void videoRef.current.play();
      setIsPlaying(true);
    }
  };

  // Play range preview
  const handlePlayRange = useCallback(() => {
    if (!videoRef.current) return;

    if (playRangeTimerRef.current) {
      window.clearTimeout(playRangeTimerRef.current);
      playRangeTimerRef.current = null;
    }

    // Offset in preview video relative to original clip
    const relStart = Math.max(0, startTime - origStart);
    const relEnd = Math.min(videoDuration > 0 ? videoDuration : 9999, endTime - origStart);
    const playDuration = Math.max(0.5, relEnd - relStart);

    videoRef.current.currentTime = relStart;
    void videoRef.current.play();
    setIsPlaying(true);

    playRangeTimerRef.current = window.setTimeout(() => {
      if (videoRef.current) {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    }, playDuration * 1000);
  }, [startTime, endTime, origStart, videoDuration]);

  // Set start / end to current playback position
  const handleSetStartToCurrent = () => {
    if (!videoRef.current) return;
    const currentInSource = origStart + videoRef.current.currentTime;
    const newStart = Math.max(0, Math.min(currentInSource, endTime - 0.5));
    setStartTime(Number(newStart.toFixed(1)));
    toast.info(`Titik mulai diset ke ${newStart.toFixed(1)}s`);
  };

  const handleSetEndToCurrent = () => {
    if (!videoRef.current) return;
    const currentInSource = origStart + videoRef.current.currentTime;
    const newEnd = Math.max(startTime + 0.5, currentInSource);
    setEndTime(Number(newEnd.toFixed(1)));
    toast.info(`Titik selesai diset ke ${newEnd.toFixed(1)}s`);
  };

  const handleResetTiming = () => {
    setStartTime(origStart);
    setEndTime(origEnd);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
    }
    toast.info('Rentang waktu dikembalikan ke posisi asal.');
  };

  // Subtitle cue operations
  const handleUpdateCueText = (id: string, text: string) => {
    setCues((prev) =>
      prev.map((cue) => (cue.id === id ? { ...cue, text } : cue))
    );
  };

  const handleUpdateCueTiming = (id: string, field: 'start' | 'end', value: number) => {
    setCues((prev) =>
      prev.map((cue) => {
        if (cue.id !== id) return cue;
        return {
          ...cue,
          [field]: Math.max(0, Number(value.toFixed(2))),
        };
      })
    );
  };

  const handleDeleteCue = (id: string) => {
    setCues((prev) => prev.filter((cue) => cue.id !== id));
  };

  const handleAddCue = () => {
    const currentRelTime = videoRef.current ? videoRef.current.currentTime : 0;
    const newCue: SubtitleCue = {
      id: `cue-${Date.now()}`,
      start: Number(currentRelTime.toFixed(2)),
      end: Number((currentRelTime + 2).toFixed(2)),
      text: 'Teks subtitle baru',
    };
    setCues((prev) => [...prev, newCue].sort((a, b) => a.start - b.start));
  };

  const handleSeekToCue = (cueStart: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = cueStart;
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  // Submission / Re-render execution
  const handleSaveAndRender = async () => {
    if (!clip) return;

    if (endTime <= startTime) {
      toast.error('Waktu selesai harus lebih besar dari waktu mulai.');
      return;
    }

    const duration = endTime - startTime;
    if (duration < 0.5) {
      toast.error('Durasi klip minimal 0.5 detik.');
      return;
    }

    setIsRendering(true);
    setRenderError(null);

    try {
      const payload = {
        session_folder: clip.session_folder,
        clip_index: clip.clip_index,
        start_time: Number(startTime.toFixed(2)),
        end_time: Number(endTime.toFixed(2)),
        aspect_ratio: aspectRatio,
        framing_mode: framingMode,
        gaming_preset: framingMode === 'gaming' ? gamingPreset : undefined,
        gaming_layout: framingMode === 'gaming' ? gamingLayout : undefined,
        subtitle_style: burnSubtitles ? subtitleStyle : 'none',
        font_family: burnSubtitles ? fontFamily : undefined,
        burn_subtitles: burnSubtitles,
        title: title.trim() || clip.title,
        segments: cues.map((c) => ({
          start: Number(c.start.toFixed(3)),
          end: Number(c.end.toFixed(3)),
          text: c.text.trim(),
        })),
        subtitles: cues.map((c) => ({
          start: Number(c.start.toFixed(3)),
          end: Number(c.end.toFixed(3)),
          text: c.text.trim(),
        })),
      };

      const res = await editClip(payload);
      if (res.success && res.clip) {
        toast.success(`🎉 Klip #${clip.clip_index} berhasil dirender ulang!`);
        onClipSaved(res.clip);
        onClose();
      } else {
        throw new Error('Server tidak mengembalikan hasil klip yang valid.');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Terjadi kesalahan saat merender.';
      setRenderError(msg);
      toast.error(msg);
    } finally {
      setIsRendering(false);
    }
  };

  if (!clip) return null;

  const currentDuration = Math.max(0, endTime - startTime);
  const isValidTiming = endTime > startTime && currentDuration >= 0.5;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isRendering && onClose()}>
      <DialogContent
        className="max-w-5xl w-full max-h-[92vh] bg-[#0c0c14] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden p-0 gap-0 sm:max-w-5xl"
        showCloseButton={false}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && !isRendering) {
            e.preventDefault();
            onClose();
          }
        }}
      >
        {/* Modal Header */}
        <DialogHeader className="flex flex-row items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
              <Scissors className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <DialogTitle className="text-lg font-bold text-white font-['Sora'] flex items-center gap-2">
                Editor Klip #{clip.clip_index}
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-violet-500/20 text-violet-300 border border-violet-500/30 font-mono font-normal">
                  {clip.aspect_ratio || aspectRatio}
                </span>
              </DialogTitle>
              <p className="text-xs text-slate-400 truncate max-w-lg">
                Sesuaikan durasi pemotongan, tata letak framing, dan subtitle teks VTT
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isRendering}
            className="min-h-[44px] min-w-[44px] w-[44px] h-[44px] p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white flex items-center justify-center transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            aria-label="Tutup editor klip"
          >
            <X className="w-4 h-4" />
          </button>
        </DialogHeader>

        {/* Modal Body: 2 Columns on desktop */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Video Preview & Playback Controls (lg: 5 cols) */}
          <div className="lg:col-span-5 flex flex-col space-y-4">
            <div className="@container [container-type:inline-size] relative w-full aspect-[9/16] max-h-[420px] sm:max-h-[460px] bg-black/90 rounded-2xl overflow-hidden border border-white/10 flex items-center justify-center shadow-lg group mx-auto">
              <video
                ref={videoRef}
                src={clip.web_url}
                playsInline
                preload="metadata"
                className="w-full h-full object-contain"
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
              >
                {clip.vtt_url && (
                  <track src={clip.vtt_url} kind="subtitles" srcLang="id" label="Subtitles" default />
                )}
              </video>

              {/* Overlay Play/Pause Button on Hover */}
              <button
                type="button"
                onClick={togglePlay}
                className="absolute inset-0 bg-black/30 group-hover:bg-black/10 flex items-center justify-center cursor-pointer transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                aria-label={isPlaying ? 'Jeda video' : 'Putar video'}
              >
                <div className="w-12 h-12 rounded-full bg-violet-600/90 text-white flex items-center justify-center shadow-xl group-hover:scale-110 transition-transform">
                  {isPlaying ? (
                    <Pause className="w-6 h-6 fill-white" />
                  ) : (
                    <Play className="w-6 h-6 ml-0.5 fill-white" />
                  )}
                </div>
              </button>

              {/* Timestamp badge */}
              <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/80 text-[11px] font-mono text-white/90 z-20">
                {formatTimeDisplay(currentTime)} / {formatTimeDisplay(videoDuration)}
              </div>

              {/* WYSIWYG Subtitle Overlay */}
              {burnSubtitles && subtitleStyle !== 'none' && (
                <LiveSubtitleOverlay
                  style={subtitleStyle}
                  fontFamily={fontFamily}
                  text={
                    cues.find((c) => currentTime >= c.start && currentTime <= c.end)?.text ||
                    cues[0]?.text ||
                    title ||
                    'Pratinjau Subtitle'
                  }
                  currentTime={currentTime}
                  duration={videoDuration || 15}
                  isPlaying={isPlaying}
                  position="bottom"
                  aspectRatio="9:16"
                  framingMode={clip.framing_mode || 'podcast'}
                />
              )}
            </div>

            {/* Playback & Scrub Bar */}
            <div className="space-y-2 bg-white/[0.02] p-3 rounded-xl border border-white/5">
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                <span>Posisi: {formatTimeDisplay(currentTime)}</span>
                <span>Sumber: {(origStart + currentTime).toFixed(1)}s</span>
              </div>

              <input
                type="range"
                min="0"
                max={videoDuration || 1}
                step="0.05"
                value={currentTime}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setCurrentTime(val);
                  if (videoRef.current) {
                    videoRef.current.currentTime = val;
                  }
                }}
                className="w-full accent-violet-500 cursor-pointer h-2 bg-white/10 rounded-lg"
                aria-label="Posisi pemutaran video"
              />

              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  type="button"
                  onClick={togglePlay}
                  className="min-h-[40px] px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border border-white/10 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                >
                  {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-white" />}
                  <span>{isPlaying ? 'Jeda' : 'Putar'}</span>
                </button>

                <button
                  type="button"
                  onClick={handlePlayRange}
                  className="min-h-[40px] px-3 py-1.5 rounded-lg bg-violet-600/30 hover:bg-violet-600/40 text-violet-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors border border-violet-500/30 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                  title="Putar segmen yang dipilih sesuai start dan end time"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Putar Rentang</span>
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Settings & Subtitles Editor (lg: 7 cols) */}
          <div className="lg:col-span-7 flex flex-col space-y-4">
            {/* Tabs Selector */}
            <div className="flex items-center gap-2 border-b border-white/10 pb-3">
              <button
                type="button"
                onClick={() => setActiveTab('trimmer')}
                className={`min-h-[44px] px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  activeTab === 'trimmer'
                    ? 'bg-violet-600 text-white shadow-md'
                    : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10'
                }`}
              >
                <Sliders className="w-4 h-4" />
                <span>Timeline & Framing</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('subtitles')}
                className={`min-h-[44px] px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  activeTab === 'subtitles'
                    ? 'bg-violet-600 text-white shadow-md'
                    : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10'
                }`}
              >
                <Type className="w-4 h-4" />
                <span>Editor Subtitle VTT ({cues.length})</span>
              </button>
            </div>

            {/* Tab 1: Timeline Trimmer & Framing Settings */}
            {activeTab === 'trimmer' && (
              <div className="space-y-4">
                {/* Title & Metadata */}
                <div className="space-y-1.5">
                  <label htmlFor="clip-title" className="text-xs font-medium text-slate-300">
                    Judul Klip
                  </label>
                  <input
                    id="clip-title"
                    type="text"
                    value={title}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
                    className="w-full min-h-[44px] px-3.5 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-xs focus:border-violet-500 focus:outline-none"
                    placeholder="Judul klip shorts..."
                  />
                </div>

                {/* Range Sliders Container */}
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/10 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-white flex items-center gap-1.5 font-['Sora']">
                      <Clock className="w-3.5 h-3.5 text-violet-400" />
                      Pengaturan Timeline In / Out
                    </span>
                    <span
                      className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full border ${
                        isValidTiming
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                      }`}
                    >
                      Durasi: {currentDuration.toFixed(1)}s
                    </span>
                  </div>

                  {/* Start Time Control */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-300">
                      <label htmlFor="start-time-input" className="font-medium">
                        Waktu Mulai (Start Time):
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          id="start-time-input"
                          type="number"
                          step="0.1"
                          min="0"
                          value={startTime}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => {
                            const val = parseFloat(e.target.value) || 0;
                            setStartTime(Number(val.toFixed(1)));
                          }}
                          className="w-24 min-h-[36px] px-2.5 py-1 text-right font-mono text-xs rounded-lg bg-black/40 border border-white/10 text-white"
                        />
                        <span className="text-slate-400 font-mono">detik</span>
                      </div>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max={Math.max(origEnd + 30, endTime + 10)}
                      step="0.1"
                      value={startTime}
                      onChange={(e) => setStartTime(Number(parseFloat(e.target.value).toFixed(1)))}
                      className="w-full accent-violet-500 cursor-pointer h-2 bg-white/10 rounded-lg"
                      aria-label="Slider waktu mulai"
                    />
                    <div className="flex items-center justify-between">
                      <button
                        type="button"
                        onClick={handleSetStartToCurrent}
                        className="text-[11px] text-violet-300 hover:text-violet-200 underline cursor-pointer"
                      >
                        Set Dari Posisi Video ({(origStart + currentTime).toFixed(1)}s)
                      </button>
                      <span className="text-[10px] text-slate-500 font-mono">
                        Asal: {origStart.toFixed(1)}s
                      </span>
                    </div>
                  </div>

                  {/* End Time Control */}
                  <div className="space-y-2 pt-2 border-t border-white/5">
                    <div className="flex items-center justify-between text-xs text-slate-300">
                      <label htmlFor="end-time-input" className="font-medium">
                        Waktu Selesai (End Time):
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          id="end-time-input"
                          type="number"
                          step="0.1"
                          min="0.5"
                          value={endTime}
                          onChange={(e: ChangeEvent<HTMLInputElement>) => {
                            const val = parseFloat(e.target.value) || 0;
                            setEndTime(Number(val.toFixed(1)));
                          }}
                          className="w-24 min-h-[36px] px-2.5 py-1 text-right font-mono text-xs rounded-lg bg-black/40 border border-white/10 text-white"
                        />
                        <span className="text-slate-400 font-mono">detik</span>
                      </div>
                    </div>
                    <input
                      type="range"
                      min="0.5"
                      max={Math.max(origEnd + 60, endTime + 30)}
                      step="0.1"
                      value={endTime}
                      onChange={(e) => setEndTime(Number(parseFloat(e.target.value).toFixed(1)))}
                      className="w-full accent-violet-500 cursor-pointer h-2 bg-white/10 rounded-lg"
                      aria-label="Slider waktu selesai"
                    />
                    <div className="flex items-center justify-between">
                      <button
                        type="button"
                        onClick={handleSetEndToCurrent}
                        className="text-[11px] text-violet-300 hover:text-violet-200 underline cursor-pointer"
                      >
                        Set Dari Posisi Video ({(origStart + currentTime).toFixed(1)}s)
                      </button>
                      <span className="text-[10px] text-slate-500 font-mono">
                        Asal: {origEnd.toFixed(1)}s
                      </span>
                    </div>
                  </div>

                  {/* Timing Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-white/5">
                    <button
                      type="button"
                      onClick={handleResetTiming}
                      className="text-xs text-slate-400 hover:text-white flex items-center gap-1 cursor-pointer transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Reset ke Waktu Asal</span>
                    </button>

                    {!isValidTiming && (
                      <span className="text-xs text-rose-400 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" />
                        Rentang tidak valid (min 0.5s)
                      </span>
                    )}
                  </div>
                </div>

                {/* Aspect Ratio & Video Layout Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Aspect Ratio */}
                  <div className="space-y-1.5">
                    <label htmlFor="aspect-ratio-select" className="text-sm font-semibold text-slate-200">
                      Aspek Rasio Render
                    </label>
                    <select
                      id="aspect-ratio-select"
                      value={aspectRatio}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setAspectRatio(e.target.value)}
                      className="w-full min-h-[44px] px-3.5 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:border-violet-500 focus:outline-none"
                    >
                      <option value="9:16">9:16 (Shorts / Reels / TikTok)</option>
                      <option value="1:1">1:1 (Square Feed)</option>
                      <option value="16:9">16:9 (Landscape / YouTube)</option>
                    </select>
                  </div>

                  {/* Framing Mode */}
                  <div className="space-y-1.5">
                    <label htmlFor="framing-mode-select" className="text-sm font-semibold text-slate-200">
                      Mode Framing AI
                    </label>
                    <select
                      id="framing-mode-select"
                      value={framingMode}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setFramingMode(e.target.value as FramingMode)}
                      className="w-full min-h-[44px] px-3.5 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:border-violet-500 focus:outline-none"
                    >
                      <option value="podcast">Podcast (Face Tracking Multi-speaker)</option>
                      <option value="single">Single Speaker (Fokus 1 Wajah)</option>
                      <option value="center">Center Crop (Tanpa Deteksi)</option>
                      <option value="gaming">Gaming (2-Layer Clean / Webcam)</option>
                    </select>
                  </div>

                  {/* Gaming Webcam Preset & Layout when framingMode === 'gaming' */}
                  {framingMode === 'gaming' && (
                    <div className="space-y-3 sm:col-span-2 p-3 rounded-xl bg-white/[0.03] border border-white/10">
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-300">
                          Susunan Layout 9:16
                        </label>
                        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Susunan Layout Gaming">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={gamingLayout === 'cam_top'}
                            onClick={() => setGamingLayout('cam_top')}
                            className={`min-h-[44px] p-2 rounded-lg border text-left transition-all cursor-pointer ${
                              gamingLayout === 'cam_top'
                                ? 'bg-fuchsia-950/50 border-fuchsia-500 text-white shadow-sm ring-1 ring-fuchsia-500/50'
                                : 'bg-white/5 border-white/10 text-slate-300 hover:text-white hover:bg-white/10'
                            }`}
                          >
                            <div className="text-xs font-bold truncate">Facecam Atas</div>
                            <div className="text-[11px] text-fuchsia-300/90 font-medium truncate">Windah Basudara style</div>
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={gamingLayout === 'cam_bottom'}
                            onClick={() => setGamingLayout('cam_bottom')}
                            className={`min-h-[44px] p-2 rounded-lg border text-left transition-all cursor-pointer ${
                              gamingLayout === 'cam_bottom'
                                ? 'bg-fuchsia-950/50 border-fuchsia-500 text-white shadow-sm ring-1 ring-fuchsia-500/50'
                                : 'bg-white/5 border-white/10 text-slate-300 hover:text-white hover:bg-white/10'
                            }`}
                          >
                            <div className="text-xs font-bold truncate">Gameplay Atas</div>
                            <div className="text-[11px] text-slate-400 font-medium truncate">Facecam Bawah (Klasik)</div>
                          </button>
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <label htmlFor="gaming-preset-select" className="text-xs font-semibold text-slate-300">
                          Posisi Webcam di Video Sumber
                        </label>
                        <select
                          id="gaming-preset-select"
                          value={gamingPreset}
                          onChange={(e: ChangeEvent<HTMLSelectElement>) => setGamingPreset(e.target.value)}
                          className="w-full min-h-[44px] px-3.5 py-2 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:border-violet-500 focus:outline-none"
                        >
                          <option value="auto">Deteksi Otomatis (AI)</option>
                          <option value="clean_2layer_bottom_right">Clean 2-Layer (Kanan Bawah)</option>
                          <option value="clean_2layer_bottom_left">Clean 2-Layer (Kiri Bawah)</option>
                          <option value="clean_2layer_top_right">Clean 2-Layer (Kanan Atas)</option>
                          <option value="clean_2layer_top_left">Clean 2-Layer (Kiri Atas)</option>
                          <option value="discord_top_cam_bottom_right">Discord 3-Layer (Squad Atas + Webcam Kanan Bawah)</option>
                        </select>
                      </div>
                    </div>
                  )}
                </div>

                {/* Subtitle Style & Burn Toggle */}
                <div className="space-y-3 pt-1">
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2.5 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={burnSubtitles}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => {
                          const checked = e.target.checked;
                          setBurnSubtitles(checked);
                          if (!checked) {
                            setSubtitleStyle('none');
                          } else if (subtitleStyle === 'none') {
                            setSubtitleStyle('hormozi');
                          }
                        }}
                        className="w-4 h-4 rounded accent-violet-600 cursor-pointer"
                      />
                      <span className="text-xs text-white font-medium">
                        Bakar Subtitle ke Video (Hardsub FFmpeg)
                      </span>
                    </label>
                  </div>

                  {burnSubtitles && (
                    <div className="bg-white/[0.02] p-3 rounded-xl border border-white/5 space-y-3">
                      <VisualPresetPicker
                        selectedStyle={subtitleStyle}
                        onSelectPreset={(st) => {
                          if (st === 'none') {
                            setBurnSubtitles(false);
                            setSubtitleStyle('none');
                          } else {
                            setBurnSubtitles(true);
                            setSubtitleStyle(st);
                          }
                        }}
                        showDisableOption={true}
                        compact={true}
                      />

                      {subtitleStyle !== 'none' && (
                        <div className="pt-2 border-t border-white/10">
                          <FontFamilyPicker
                            selectedFont={fontFamily}
                            onSelectFont={setFontFamily}
                            presetDefaultFont={getDefaultFontForPreset(normalizePresetId(subtitleStyle))}
                            compact={true}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>

              </div>
            )}

            {/* Tab 2: Subtitle Editor (VTT Lines) */}
            {activeTab === 'subtitles' && (
              <div className="space-y-4 flex-1 flex flex-col">
                <div className="flex items-center justify-between pb-2 border-b border-white/10">
                  <div className="text-xs text-slate-400">
                    Edit baris subtitle untuk pembakaran video baru. Total: <strong>{cues.length}</strong> segmen.
                  </div>
                  <button
                    type="button"
                    onClick={handleAddCue}
                    className="min-h-[40px] px-3 py-1.5 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Tambah Baris</span>
                  </button>
                </div>

                {loadingVtt ? (
                  <div className="py-16 flex flex-col items-center justify-center text-slate-400 gap-3">
                    <RefreshCw className="w-6 h-6 animate-spin text-violet-400" />
                    <p className="text-xs">Memuat berkas subtitle VTT...</p>
                  </div>
                ) : cues.length === 0 ? (
                  <div className="py-16 text-center flex flex-col items-center justify-center space-y-3 bg-white/[0.01] rounded-xl border border-white/5">
                    <Type className="w-8 h-8 text-slate-500" />
                    <p className="text-xs text-slate-400">
                      Belum ada segmen subtitle untuk klip ini. Klik "Tambah Baris" untuk membuat subtitle manual.
                    </p>
                    <button
                      type="button"
                      onClick={handleAddCue}
                      className="min-h-[40px] px-4 py-2 rounded-xl bg-violet-600 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Buat Subtitle Pertama</span>
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                    {cues.map((cue, idx) => (
                      <div
                        key={cue.id || idx}
                        className="p-3 rounded-xl bg-white/[0.02] border border-white/10 space-y-2 hover:border-violet-500/30 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-mono text-violet-300 font-bold">
                            #{idx + 1}
                          </span>

                          <div className="flex items-center gap-2 text-xs">
                            <div className="flex items-center gap-1">
                              <span className="text-slate-500 text-[10px]">Mulai:</span>
                              <input
                                type="number"
                                step="0.05"
                                min="0"
                                value={cue.start}
                                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                                  handleUpdateCueTiming(cue.id, 'start', parseFloat(e.target.value) || 0)
                                }
                                className="w-16 px-1.5 py-0.5 text-right font-mono text-[11px] rounded bg-black/40 border border-white/10 text-white"
                                aria-label={`Waktu mulai subtitle #${idx + 1}`}
                              />
                            </div>

                            <span className="text-slate-600">→</span>

                            <div className="flex items-center gap-1">
                              <span className="text-slate-500 text-[10px]">Akhir:</span>
                              <input
                                type="number"
                                step="0.05"
                                min="0"
                                value={cue.end}
                                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                                  handleUpdateCueTiming(cue.id, 'end', parseFloat(e.target.value) || 0)
                                }
                                className="w-16 px-1.5 py-0.5 text-right font-mono text-[11px] rounded bg-black/40 border border-white/10 text-white"
                                aria-label={`Waktu akhir subtitle #${idx + 1}`}
                              />
                            </div>

                            <button
                              type="button"
                              onClick={() => handleSeekToCue(cue.start)}
                              className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-[11px] text-slate-300 hover:text-white transition-colors cursor-pointer"
                              title="Lompat video ke detik ini"
                            >
                              Lompat
                            </button>

                            <button
                              type="button"
                              onClick={() => handleDeleteCue(cue.id)}
                              className="p-1 rounded text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors cursor-pointer"
                              title="Hapus baris subtitle"
                              aria-label={`Hapus baris subtitle #${idx + 1}`}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>

                        <textarea
                          rows={2}
                          value={cue.text}
                          onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
                            handleUpdateCueText(cue.id, e.target.value)
                          }
                          className="w-full px-3 py-1.5 rounded-lg bg-black/30 border border-white/10 text-white text-xs font-sans focus:border-violet-500 focus:outline-none resize-none"
                          placeholder="Ketik teks subtitle..."
                          aria-label={`Teks subtitle baris #${idx + 1}`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Error Banner if render failed */}
            {renderError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                <span className="truncate">{renderError}</span>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer with Re-render Progress & CTA */}
        <div className="px-6 py-4 border-t border-white/10 bg-white/[0.02] flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-xs text-slate-400">
            {isRendering ? (
              <span className="flex items-center gap-2 text-violet-400 font-medium">
                <RefreshCw className="w-4 h-4 animate-spin" />
                Merender ulang klip... Memotong video & membakar subtitle via FFmpeg.
              </span>
            ) : (
              <span>
                Klip akan dirender ulang dan menggantikan arsip lama secara otomatis.
              </span>
            )}
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <button
              type="button"
              onClick={onClose}
              disabled={isRendering}
              className="min-h-[44px] flex-1 sm:flex-initial px-5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white transition-colors cursor-pointer text-xs font-semibold disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            >
              Batal
            </button>

            <button
              type="button"
              onClick={handleSaveAndRender}
              disabled={isRendering || !isValidTiming}
              className="min-h-[44px] flex-1 sm:flex-initial px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white transition-all cursor-pointer text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-violet-600/20 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
            >
              {isRendering ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Merender...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Simpan & Render Ulang</span>
                </>
              )}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
