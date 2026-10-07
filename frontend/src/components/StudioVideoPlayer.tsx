import { useState, useRef, useEffect, useCallback, type FC } from 'react';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  RotateCcw,
  Sparkles,
  Download,
  Type,
  Film,
  AlignVerticalJustifyCenter,
  AlignVerticalJustifyStart,
  Scissors,
  Layers,
} from 'lucide-react';
import type { GeneratedShort, HistoryShort, SubtitleStyle, FramingMode } from '../types';
import { LiveSubtitleOverlay } from './LiveSubtitleOverlay';
import { VisualPresetPicker } from './VisualPresetPicker';
import { FontFamilyPicker } from './FontFamilyPicker';
import { getTextPreset, normalizePresetId } from '../lib/textPresets';
import { getDefaultFontForPreset } from '../lib/fontFamilyLibrary';

export interface StudioVideoPlayerProps {
  clip?: GeneratedShort | HistoryShort | null;
  aspectRatio: string;
  subtitleStyle: SubtitleStyle;
  subtitleText: string;
  framingMode?: FramingMode;
  fontFamily?: string;
  onSubtitleTextChange: (text: string) => void;
  onAspectRatioChange: (ratio: string) => void;
  onSubtitleStyleChange: (style: SubtitleStyle) => void;
  onFontFamilyChange?: (font: string) => void;
  onClearClip?: () => void;
  onEditClip?: () => void;
}

const PRESET_HOOK_TEXTS = [
  'RAHASIA UTAMA DI VIDEO INI',
  'CARA CEPAT MEMBUAT KONTEN',
  'POIN PENTING YANG SERING TERLEWAT',
  'JANGAN SKIP BAGIAN INI',
  'LANGKAH MUDAH EDITING VIDEO',
];

export const StudioVideoPlayer: FC<StudioVideoPlayerProps> = ({
  clip,
  aspectRatio,
  subtitleStyle,
  subtitleText,
  framingMode,
  fontFamily,
  onSubtitleTextChange,
  onAspectRatioChange,
  onSubtitleStyleChange,
  onFontFamilyChange,
  onClearClip,
  onEditClip,
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(15);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [subtitleColor, setSubtitleColor] = useState<'yellow' | 'white'>('yellow');
  const [subtitlePosition, setSubtitlePosition] = useState<'bottom' | 'center'>('bottom');
  const [isPresetPickerOpen, setIsPresetPickerOpen] = useState<boolean>(false);

  const presetDefaultFont = getDefaultFontForPreset(normalizePresetId(subtitleStyle));
  const [internalFont, setInternalFont] = useState<string>(() => fontFamily || presetDefaultFont);

  const activeFontFamily = fontFamily || internalFont;

  const handleFontSelect = (font: string) => {
    setInternalFont(font);
    onFontFamilyChange?.(font);
  };

  const videoRef = useRef<HTMLVideoElement | null>(null);

  const hasRealVideo = Boolean(clip?.web_url || ('clip_url' in (clip || {}) && (clip as GeneratedShort)?.clip_url));
  const videoSrc = clip?.web_url || (('clip_url' in (clip || {}) ? (clip as GeneratedShort)?.clip_url : '') ?? '');
  const activeAspectRatio = clip?.aspect_ratio || aspectRatio || '9:16';

  // Format time mm:ss
  const formatTime = (seconds: number) => {
    if (isNaN(seconds) || seconds < 0) return '00:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Handle video playback events
  const handlePlayPause = useCallback(() => {
    if (hasRealVideo && videoRef.current) {
      if (videoRef.current.paused) {
        void videoRef.current.play();
        setIsPlaying(true);
      } else {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    }
  }, [hasRealVideo]);

  // Handle time scrubber
  const handleScrub = (value: number) => {
    setCurrentTime(value);
    if (hasRealVideo && videoRef.current) {
      videoRef.current.currentTime = value;
    }
  };

  // Handle restart / reset
  const handleReset = () => {
    setCurrentTime(0);
    if (hasRealVideo && videoRef.current) {
      videoRef.current.currentTime = 0;
      if (isPlaying) {
        void videoRef.current.play();
      }
    }
  };

  // Handle Mute
  const handleToggleMute = () => {
    setIsMuted((prev) => {
      const next = !prev;
      if (videoRef.current) {
        videoRef.current.muted = next;
      }
      return next;
    });
  };

  // Real video metadata & time sync
  useEffect(() => {
    if (hasRealVideo && videoRef.current) {
      const video = videoRef.current;

      const onTimeUpdate = () => {
        setCurrentTime(video.currentTime);
      };

      const onLoadedMetadata = () => {
        if (video.duration && !isNaN(video.duration)) {
          setDuration(video.duration);
        }
        if (video.videoWidth && video.videoHeight) {
          const rawRatio = video.videoWidth / video.videoHeight;
          let detected = '9:16';
          if (rawRatio >= 1.3) {
            detected = '16:9';
          } else if (rawRatio >= 0.8 && rawRatio < 1.3) {
            detected = '1:1';
          } else {
            detected = '9:16';
          }
          if (detected !== activeAspectRatio) {
            onAspectRatioChange(detected);
          }
        }
      };

      if (video.readyState >= 1) {
        onLoadedMetadata();
      }

      const onEnded = () => {
        setIsPlaying(false);
        setCurrentTime(0);
      };

      video.addEventListener('timeupdate', onTimeUpdate);
      video.addEventListener('loadedmetadata', onLoadedMetadata);
      video.addEventListener('ended', onEnded);

      return () => {
        video.removeEventListener('timeupdate', onTimeUpdate);
        video.removeEventListener('loadedmetadata', onLoadedMetadata);
        video.removeEventListener('ended', onEnded);
      };
    }
  }, [hasRealVideo, videoSrc, activeAspectRatio, onAspectRatioChange]);

  // Sync aspect ratio when clip metadata changes
  useEffect(() => {
    if (clip?.aspect_ratio && clip.aspect_ratio !== activeAspectRatio) {
      onAspectRatioChange(clip.aspect_ratio);
    }
  }, [clip?.aspect_ratio, activeAspectRatio, onAspectRatioChange]);

  // Subtitle text for live monitor display
  const cleanSubtitleText = subtitleText.trim() || 'TEKS SUBTITLE PRATINJAU';

  // Monitor Aspect ratio CSS container
  const aspectClass =
    activeAspectRatio === '1:1'
      ? 'aspect-square h-[340px] sm:h-[420px] max-h-[65vh] w-auto max-w-full rounded-2xl border-2 border-zinc-800 shadow-lg'
      : activeAspectRatio === '16:9'
      ? 'aspect-video w-full max-w-[854px] max-h-[480px] h-auto rounded-xl border border-zinc-800 shadow-lg'
      : 'aspect-[9/16] h-[450px] sm:h-[520px] md:h-[580px] max-h-[75vh] w-auto max-w-full rounded-2xl border-2 border-zinc-800 shadow-xl';

  return (
    <div
      aria-label="Studio Video Monitor"
      className="w-full flex flex-col justify-between overflow-x-hidden min-h-0 bg-[#12121A] border border-white/[0.08] rounded-2xl"
    >
      {/* Top Stage Bar: Title + Status + Framing + Aspect Ratio selector */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-3 bg-zinc-950/70 shrink-0 rounded-t-2xl">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0">
            <Film className="w-4 h-4 text-violet-400" />
          </div>
          <div className="min-w-0 flex items-center gap-2">
            <h2 className="text-sm sm:text-base font-bold text-zinc-100 font-headline flex items-center gap-2 truncate">
              <span>Monitor Studio</span>
              <span className="flex items-center gap-1.5 text-xs font-mono px-2.5 py-0.5 rounded-md bg-zinc-900 text-zinc-300 border border-zinc-800 font-normal shrink-0">
                <span className={`w-2 h-2 rounded-full ${isPlaying ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
                {hasRealVideo ? 'Klip Aktif' : 'Standby'}
              </span>
            </h2>
            {framingMode && (
              <span className="hidden sm:inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800 shrink-0">
                <Layers className="w-3 h-3 text-violet-400" />
                <span>{framingMode}</span>
              </span>
            )}
          </div>
        </div>

        {/* Aspect Ratio Quick Switcher */}
        <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-lg border border-zinc-800 shrink-0">
          {(['9:16', '1:1', '16:9'] as const).map((ratio) => {
            const isSelected = activeAspectRatio === ratio;
            return (
              <button
                key={ratio}
                type="button"
                onClick={() => onAspectRatioChange(ratio)}
                aria-pressed={isSelected}
                className={`min-h-[34px] px-3 py-1 text-xs sm:text-sm font-semibold rounded-md transition-colors cursor-pointer select-none flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  isSelected
                    ? 'bg-violet-600 text-white font-bold'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
                }`}
                title={`Pilih Rasio Aspek ${ratio}`}
              >
                {ratio}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Video Monitor Stage Canvas */}
      <div className="flex-1 min-h-[300px] sm:min-h-[380px] flex items-center justify-center p-3 sm:p-5 relative bg-[#060609] overflow-hidden">
        {/* Aspect ratio bounding box */}
        <div
          className={`relative ${aspectClass} overflow-hidden bg-black flex items-center justify-center select-none`}
        >
          {hasRealVideo ? (
            /* Real Video Player */
            <video
              ref={videoRef}
              src={videoSrc}
              playsInline
              loop
              muted={isMuted}
              className="w-full h-full object-contain bg-black cursor-pointer"
              onClick={handlePlayPause}
            >
              {clip?.vtt_url && (
                <track src={clip.vtt_url} kind="subtitles" srcLang="id" label="Subtitles" default />
              )}
              Browser tidak mendukung pemutaran video HTML5.
            </video>
          ) : (
            /* Honest Standby Screen */
            <div className="relative w-full h-full flex flex-col items-center justify-center p-6 text-center bg-zinc-950">
              <Film className="w-10 h-10 text-zinc-600 mb-2" />
              <p className="text-xs font-semibold text-zinc-300 font-headline">Monitor Siap</p>
              <p className="text-[11px] text-zinc-500 max-w-[220px] mt-1">
                Pilih klip video dari antrean hasil untuk memutar dan memeriksa tampilan subtitle.
              </p>
            </div>
          )}

          {/* Real-Time WYSIWYG Subtitle Overlay */}
          {hasRealVideo && (
            <LiveSubtitleOverlay
              style={subtitleStyle}
              text={cleanSubtitleText}
              fontFamily={activeFontFamily}
              currentTime={currentTime}
              duration={duration}
              isPlaying={isPlaying}
              position={subtitlePosition}
              customColor={subtitleColor}
            />
          )}
        </div>
      </div>

      {/* Stage Bottom Controls Rack */}
      <div className="border-t border-zinc-800 bg-zinc-950/90 p-3 sm:p-4 space-y-3 shrink-0 rounded-b-2xl">
        {/* Scrubber Timeline Bar */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-zinc-400 w-11 text-right shrink-0">
            {formatTime(currentTime)}
          </span>
          <div className="flex-1 min-h-[36px] flex items-center">
            <input
              type="range"
              min={0}
              max={duration || 15}
              step={0.1}
              value={currentTime}
              onChange={(e) => handleScrub(parseFloat(e.target.value))}
              disabled={!hasRealVideo}
              aria-label="Timeline seekbar video"
              className="w-full accent-violet-500 h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-40 disabled:cursor-not-allowed"
            />
          </div>
          <span className="text-[11px] font-mono text-zinc-400 w-11 shrink-0">
            {formatTime(duration)}
          </span>
        </div>

        {/* Buttons Row: Play/Pause, Reset, Mute, Subtitle Options */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            {/* Play/Pause Button */}
            <button
              type="button"
              onClick={handlePlayPause}
              disabled={!hasRealVideo}
              className="min-h-[38px] px-3.5 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
              aria-label={isPlaying ? 'Pause pemutaran' : 'Mulai pemutaran video'}
            >
              {isPlaying ? (
                <>
                  <Pause className="w-3.5 h-3.5 fill-white" />
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-white" />
                  <span>Putar</span>
                </>
              )}
            </button>

            {/* Restart Button */}
            <button
              type="button"
              onClick={handleReset}
              disabled={!hasRealVideo}
              className="min-h-[38px] min-w-[38px] p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              title="Mulai Ulang dari Awal"
              aria-label="Mulai ulang video dari awal"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>

            {/* Mute Toggle */}
            <button
              type="button"
              onClick={handleToggleMute}
              disabled={!hasRealVideo}
              className="min-h-[38px] min-w-[38px] p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              title={isMuted ? 'Nyalakan Suara' : 'Bisukan Suara'}
              aria-label={isMuted ? 'Nyalakan audio video' : 'Bisukan audio video'}
            >
              {isMuted ? <VolumeX className="w-3.5 h-3.5 text-rose-400" /> : <Volume2 className="w-3.5 h-3.5" />}
            </button>
          </div>

          {/* Quick Subtitle Controls Bar */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {/* Subtitle Color Toggle */}
            <button
              type="button"
              onClick={() => setSubtitleColor((prev) => (prev === 'yellow' ? 'white' : 'yellow'))}
              className="min-h-[38px] px-2.5 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs text-zinc-300 hover:text-white flex items-center justify-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              title="Ganti Warna Subtitle (Kuning / Putih)"
              aria-label={`Warna subtitle saat ini: ${subtitleColor}`}
            >
              <span
                className={`w-3 h-3 rounded-full border border-black/40 shrink-0 ${
                  subtitleColor === 'yellow' ? 'bg-[#FACC15]' : 'bg-white'
                }`}
              />
              <span className="hidden sm:inline">{subtitleColor === 'yellow' ? 'Kuning' : 'Putih'}</span>
            </button>

            {/* Subtitle Position Toggle */}
            <button
              type="button"
              onClick={() => setSubtitlePosition((prev) => (prev === 'bottom' ? 'center' : 'bottom'))}
              className="min-h-[38px] px-2.5 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs text-zinc-300 hover:text-white flex items-center justify-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              title="Ganti Posisi Subtitle (Bawah / Tengah)"
              aria-label={`Posisi subtitle: ${subtitlePosition === 'bottom' ? 'Bawah' : 'Tengah'}`}
            >
              {subtitlePosition === 'bottom' ? (
                <AlignVerticalJustifyStart className="w-3.5 h-3.5 rotate-180 text-cyan-400 shrink-0" />
              ) : (
                <AlignVerticalJustifyCenter className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              )}
              <span className="hidden sm:inline">{subtitlePosition === 'bottom' ? 'Bawah' : 'Tengah'}</span>
            </button>

            {/* Preset Picker Toggle Button */}
            <button
              type="button"
              onClick={() => setIsPresetPickerOpen((prev) => !prev)}
              className="min-h-[38px] px-2.5 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs text-zinc-300 hover:text-white flex items-center justify-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              title="Buka / Tutup Pilihan Preset Subtitle"
            >
              <Type className="w-3.5 h-3.5 text-violet-400" />
              <span className="font-semibold text-zinc-200">
                {subtitleStyle === 'none' ? 'Tanpa Teks' : getTextPreset(subtitleStyle).name}
              </span>
            </button>
          </div>
        </div>

        {/* Collapsible Preset & Font Selector in Player */}
        {isPresetPickerOpen && (
          <div className="pt-2.5 pb-1 border-t border-zinc-800 space-y-3 animate-in fade-in duration-200">
            <VisualPresetPicker
              selectedStyle={subtitleStyle}
              onSelectPreset={onSubtitleStyleChange}
              compact={true}
            />
            {subtitleStyle !== 'none' && (
              <FontFamilyPicker
                selectedFont={activeFontFamily}
                onSelectFont={handleFontSelect}
                presetDefaultFont={presetDefaultFont}
                compact={true}
              />
            )}
          </div>
        )}

        {/* Real-Time Interactive Subtitle Editor */}
        <div className="pt-2 border-t border-zinc-800/80 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-zinc-300">
            <label
              htmlFor="live-subtitle-input"
              className="font-semibold flex items-center gap-1.5 cursor-pointer text-zinc-200"
            >
              <Type className="w-3.5 h-3.5 text-cyan-400" />
              <span>Teks Subtitle Langsung</span>
            </label>
            <span className="text-[11px] text-zinc-500">Pratinjau langsung di video</span>
          </div>

          <div className="relative">
            <input
              id="live-subtitle-input"
              type="text"
              value={subtitleText}
              onChange={(e) => onSubtitleTextChange(e.target.value)}
              placeholder="Ketik teks untuk melihat pratinjau di atas video..."
              className="w-full h-10 px-3 rounded-lg bg-zinc-900 border border-zinc-800 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 transition-colors font-medium"
            />
          </div>

          {/* Quick Hook Suggestions */}
          <div className="flex flex-wrap gap-1 pt-0.5">
            {PRESET_HOOK_TEXTS.map((hook, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onSubtitleTextChange(hook)}
                className="px-2 py-1 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer select-none"
              >
                {hook}
              </button>
            ))}
          </div>
        </div>

        {/* Active Clip Action Bar */}
        {hasRealVideo && (
          <div className="pt-2 border-t border-zinc-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-zinc-900/60 p-2.5 sm:p-3 rounded-xl border border-zinc-800">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30">
                  KLIP TERPILIH
                </span>
                {typeof clip?.score === 'number' && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 font-semibold">
                    <Sparkles className="w-3 h-3 text-emerald-400" />
                    Skor {clip.score}/100
                  </span>
                )}
              </div>
              <p className="text-xs font-semibold text-zinc-100 truncate mt-1">
                {clip?.title || clip?.filename || 'Klip Video'}
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {onEditClip && (
                <button
                  type="button"
                  onClick={onEditClip}
                  className="min-h-[38px] px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-100 hover:text-white border border-zinc-700 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
                  title="Buka Editor & Pemotong Video Lengkap"
                >
                  <Scissors className="w-3.5 h-3.5 text-violet-400" />
                  <span>Edit Klip</span>
                </button>
              )}

              {videoSrc && (
                <a
                  href={videoSrc}
                  download={clip?.filename || 'shorts.mp4'}
                  target="_blank"
                  rel="noreferrer"
                  className="min-h-[38px] px-3.5 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Unduh MP4</span>
                </a>
              )}

              {onClearClip && (
                <button
                  type="button"
                  onClick={onClearClip}
                  className="min-h-[38px] px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                  title="Tutup Klip dari Monitor"
                >
                  Tutup
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
