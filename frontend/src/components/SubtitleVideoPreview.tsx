import { useState, useRef, useEffect, useCallback, type FC } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  Type,
  AlignVerticalJustifyCenter,
  AlignVerticalJustifyStart,
  Film,
  Volume2,
  VolumeX,
  Mic,
} from 'lucide-react';
import type { SubtitleStyle, FramingMode, SubtitleFontSizeScale } from '../types';
import { LiveSubtitleOverlay } from './LiveSubtitleOverlay';
import { normalizePresetId, getTextPreset } from '../lib/textPresets';
import {
  ILLUSTRATION_TRANSCRIPT_TEXT,
  ILLUSTRATION_CUES,
} from '../lib/illustrationTranscript';

export interface SubtitleVideoPreviewProps {
  subtitleStyle: SubtitleStyle;
  activeFont: string;
  aspectRatio: string;
  previewText: string;
  onPreviewTextChange: (text: string) => void;
  framingMode?: FramingMode;
  sampleVideoUrl?: string;
  fontSizeScale?: SubtitleFontSizeScale | number;
}

const QUICK_HOOK_SUGGESTIONS = [
  'KONTEN VIRAL HARI INI',
  'RAHASIA BESAR DI VIDEO INI',
  'CARA CEPAT CUAN DARI TIKTOK',
  'JANGAN SKIP TIPS PENTING INI',
];

export const getIllustrationVideoUrl = (
  aspectRatio: string,
  framingMode: FramingMode = 'podcast'
): string => {
  if (aspectRatio === '16:9') {
    return '/videos/preview-16-9.mp4';
  }
  if (aspectRatio === '1:1') {
    return '/videos/preview-1-1.mp4';
  }
  // 9:16 vertical presets
  switch (framingMode) {
    case 'gaming':
      return '/videos/preview-9-16-gaming.mp4';
    case 'single':
      return '/videos/preview-9-16-single.mp4';
    case 'center':
      return '/videos/preview-9-16-center.mp4';
    case 'podcast':
    default:
      return '/videos/preview-9-16-podcast.mp4';
  }
};

export const SubtitleVideoPreview: FC<SubtitleVideoPreviewProps> = ({
  subtitleStyle,
  activeFont,
  aspectRatio,
  previewText,
  onPreviewTextChange,
  framingMode = 'podcast',
  sampleVideoUrl,
  fontSizeScale = 'medium',
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(6);
  const [subtitlePosition, setSubtitlePosition] = useState<'center' | 'bottom'>('bottom');
  const [isMuted, setIsMuted] = useState<boolean>(true);
  const [videoLoaded, setVideoLoaded] = useState<boolean>(false);
  const [hasVideoError, setHasVideoError] = useState<boolean>(false);
  const [fitMode, setFitMode] = useState<'contain' | 'cover'>('contain');

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(performance.now());

  const resolvedVideoUrl = sampleVideoUrl || getIllustrationVideoUrl(aspectRatio, framingMode);

  const presetId = normalizePresetId(subtitleStyle);
  const activePreset = getTextPreset(presetId);

  // Toggle audio mute / sound
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      if (videoRef.current) {
        videoRef.current.muted = next;
        if (!next) {
          videoRef.current.volume = 1;
          void videoRef.current.play().catch(() => {});
        }
      }
      return next;
    });
  }, []);

  // Auto-play / update when video source changes based on aspect ratio or framing
  useEffect(() => {
    setHasVideoError(false);
    setVideoLoaded(false);
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      setCurrentTime(0);
      if (isPlaying) {
        void videoRef.current.play().catch(() => {});
      }
    }
  }, [resolvedVideoUrl, isPlaying]);

  // Play / Pause toggle
  const togglePlayPause = useCallback(() => {
    if (videoRef.current && videoLoaded && !hasVideoError) {
      if (videoRef.current.paused) {
        void videoRef.current.play().catch(() => {});
        setIsPlaying(true);
      } else {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    } else {
      setIsPlaying((prev) => !prev);
    }
  }, [videoLoaded, hasVideoError]);

  // Reset to beginning
  const handleReset = useCallback(() => {
    if (videoRef.current && videoLoaded && !hasVideoError) {
      videoRef.current.currentTime = 0;
      void videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
    setCurrentTime(0);
  }, [videoLoaded, hasVideoError]);

  // Video timeupdate sync
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    if (videoRef.current) {
      const dur = videoRef.current.duration;
      if (dur && !isNaN(dur) && isFinite(dur)) {
        setDuration(dur);
      }
      setVideoLoaded(true);
      setHasVideoError(false);
      if (isPlaying) {
        void videoRef.current.play().catch(() => {});
      }
    }
  }, [isPlaying]);

  const handleVideoError = useCallback(() => {
    setHasVideoError(true);
    setVideoLoaded(false);
  }, []);

  // Fallback animation ticker if video fails or is unsupported
  useEffect(() => {
    if (videoLoaded && !hasVideoError) return;

    let animId: number;
    lastTimeRef.current = performance.now();

    const loop = (now: number) => {
      const delta = (now - lastTimeRef.current) / 1000;
      lastTimeRef.current = now;

      if (isPlaying) {
        setCurrentTime((prev) => {
          const next = prev + delta;
          return next >= duration ? 0 : next;
        });
      }
      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, duration, videoLoaded, hasVideoError]);

  // Clean up
  useEffect(() => {
    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, []);

  // Responsive aspect ratio styling - cleanly proportioned and well-fitted
  const aspectClass =
    aspectRatio === '9:16'
      ? 'aspect-[9/16] h-[340px] sm:h-[400px] md:h-[440px] max-h-[62vh] w-auto max-w-full'
      : aspectRatio === '1:1'
      ? 'aspect-square h-[280px] sm:h-[340px] md:h-[380px] max-h-[55vh] w-auto max-w-full'
      : 'aspect-video w-full max-w-[560px] h-auto max-h-[360px]';

  const formatBadgeLabel =
    aspectRatio === '9:16'
      ? framingMode === 'gaming'
        ? '9:16 Gaming 2-Layer'
        : framingMode === 'single'
        ? '9:16 Single Face'
        : framingMode === 'center'
        ? '9:16 Center Crop'
        : '9:16 Podcast Multi'
      : aspectRatio === '1:1'
      ? '1:1 Persegi'
      : '16:9 Lanskap';

  // Speech transcript synchronization check
  const isSpeechTranscript =
    previewText.trim().toLowerCase() === ILLUSTRATION_TRANSCRIPT_TEXT.toLowerCase();

  let activeWord = '';
  let wordIndexDisplay = 0;
  let totalWordsDisplay = 0;

  if (isSpeechTranscript) {
    const activeCue =
      ILLUSTRATION_CUES.find(
        (cue) => currentTime >= cue.start && currentTime < cue.end
      ) ||
      (currentTime >= 5.9
        ? ILLUSTRATION_CUES[ILLUSTRATION_CUES.length - 1]
        : ILLUSTRATION_CUES[0]);

    totalWordsDisplay = activeCue.words.length;
    const foundIdx = activeCue.words.findIndex(
      (w) => currentTime >= w.start && currentTime <= w.end
    );
    if (foundIdx !== -1) {
      wordIndexDisplay = foundIdx + 1;
      activeWord = activeCue.words[foundIdx].word;
    } else {
      let lastStarted = 0;
      for (let i = 0; i < activeCue.words.length; i++) {
        if (currentTime >= activeCue.words[i].start) {
          lastStarted = i;
        }
      }
      wordIndexDisplay = lastStarted + 1;
      activeWord = activeCue.words[lastStarted]?.word || '';
    }
  } else {
    const words = previewText.trim().split(/\s+/).filter(Boolean);
    totalWordsDisplay = Math.max(1, words.length);
    const idx = Math.min(
      totalWordsDisplay - 1,
      Math.floor((currentTime / Math.max(0.1, duration)) * totalWordsDisplay)
    );
    wordIndexDisplay = idx + 1;
    activeWord = words[idx] || '';
  }

  return (
    <div className="space-y-3">
      {/* Main Video Monitor Stage */}
      <div className="relative w-full min-h-[300px] sm:min-h-[340px] md:min-h-[380px] rounded-2xl bg-[#07070b] border border-zinc-800/90 overflow-hidden flex flex-col items-center justify-center p-3 sm:p-5 shadow-2xl group select-none">
        {/* Subtle Ambient Background Grid / Theater Mood */}
        <div
          className="absolute inset-0 opacity-15 pointer-events-none"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.25) 1px, transparent 0)',
            backgroundSize: '16px 16px',
          }}
        />

        {/* Top Floating Status Bar */}
        <div className="absolute top-3 inset-x-3 z-30 flex items-center justify-between gap-2 pointer-events-none">
          {/* Live Indicator */}
          <div className="flex items-center gap-1.5 pointer-events-auto">
            <span className="text-[11px] font-mono font-bold px-2.5 py-1 rounded-lg bg-zinc-950/90 text-violet-300 border border-violet-500/30 flex items-center gap-1.5 backdrop-blur-md shadow-lg">
              <span
                className={`w-2 h-2 rounded-full ${
                  isPlaying ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'
                }`}
              />
              <span>{isPlaying ? 'PREVIEW VIDEO ANIMASI' : 'VIDEO DIJEDA'}</span>
            </span>

            {subtitleStyle !== 'none' && isSpeechTranscript && (
              <span className="hidden lg:inline-flex text-[11px] font-mono px-2 py-1 rounded-lg bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 backdrop-blur-md items-center gap-1">
                <Mic className="w-3 h-3 text-emerald-400" />
                <span>Audio Sinkron</span>
              </span>
            )}

            {subtitleStyle !== 'none' && activePreset && (
              <span className="hidden md:inline-flex text-[11px] font-mono px-2 py-1 rounded-lg bg-violet-950/70 text-violet-300 border border-violet-800/60 backdrop-blur-md">
                {activePreset.name}
              </span>
            )}

            {subtitleStyle !== 'none' && activeWord && (
              <span className="hidden sm:inline-flex text-[11px] font-mono px-2 py-1 rounded-lg bg-black/70 text-amber-300 border border-amber-500/30 backdrop-blur-md">
                Kata {wordIndexDisplay}/{totalWordsDisplay}: &quot;{activeWord}&quot;
              </span>
            )}
          </div>

          {/* Top Right Controls (Position Toggle + Aspect Ratio) */}
          <div className="flex items-center gap-1.5 pointer-events-auto">
            {/* Fit Mode Toggle */}
            <button
              type="button"
              onClick={() => setFitMode((prev) => (prev === 'contain' ? 'cover' : 'contain'))}
              className="text-[11px] font-medium px-2 py-1 rounded-lg bg-zinc-900/90 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-700/80 transition-colors flex items-center gap-1 cursor-pointer backdrop-blur-md shadow-sm"
              title="Ganti Mode Pas Video (Pas: utuh 100% / Penuh: cover frame)"
              aria-label={`Mode tampilan video: ${fitMode === 'contain' ? 'Pas (Fit)' : 'Penuh (Fill)'}`}
            >
              <span>{fitMode === 'contain' ? '📐 Pas' : '🔍 Penuh'}</span>
            </button>

            <button
              type="button"
              onClick={() =>
                setSubtitlePosition((prev) => (prev === 'bottom' ? 'center' : 'bottom'))
              }
              className="text-[11px] font-medium px-2.5 py-1 rounded-lg bg-zinc-900/90 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-700/80 transition-colors flex items-center gap-1.5 cursor-pointer backdrop-blur-md shadow-sm"
              title="Ganti Posisi Subtitle (Bawah / Tengah)"
            >
              {subtitlePosition === 'bottom' ? (
                <>
                  <AlignVerticalJustifyStart className="w-3 h-3 text-cyan-400 rotate-180" />
                  <span className="hidden xs:inline">Posisi:</span> Bawah
                </>
              ) : (
                <>
                  <AlignVerticalJustifyCenter className="w-3 h-3 text-violet-400" />
                  <span className="hidden xs:inline">Posisi:</span> Tengah
                </>
              )}
            </button>

            <span className="text-[11px] font-mono font-medium px-2 py-1 rounded-lg bg-zinc-950/90 text-zinc-300 border border-zinc-800 backdrop-blur-md">
              {formatBadgeLabel}
            </span>
          </div>
        </div>

        {/* Video Canvas Box (Framed to Selected Aspect Ratio) */}
        <div
          className={`@container [container-type:inline-size] relative ${aspectClass} rounded-2xl overflow-hidden border-2 border-zinc-800/90 bg-black shadow-2xl flex items-center justify-center transition-all duration-300 cursor-pointer`}
          onClick={togglePlayPause}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === ' ' || e.key === 'Enter') {
              e.preventDefault();
              togglePlayPause();
            }
          }}
          aria-label="Klik untuk putar atau jeda pratinjau video animasi subtitle"
        >
          {/* Looping Sample Video matched to format */}
          <video
            ref={videoRef}
            key={resolvedVideoUrl}
            src={resolvedVideoUrl}
            playsInline
            loop
            muted={isMuted}
            autoPlay
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onError={handleVideoError}
            className={`w-full h-full ${
              fitMode === 'contain' ? 'object-contain' : 'object-cover'
            } bg-black select-none pointer-events-none transition-all duration-200`}
          />

          {/* Cinematic Vignette / Contrast Layer for Subtitle Readability */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/40 pointer-events-none" />

          {/* Fallback Display if Video Fails to Load */}
          {hasVideoError && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950 p-4 text-center z-10 pointer-events-none">
              <Film className="w-8 h-8 text-zinc-600 mb-2" />
              <p className="text-xs font-semibold text-zinc-300">Pratinjau Kanvas Animasi</p>
              <p className="text-[10px] text-zinc-500 mt-0.5">Mode simulasi subtitle aktif</p>
            </div>
          )}

          {/* Subtitle Rendering Overlay */}
          {subtitleStyle === 'none' ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center z-20 pointer-events-none bg-black/40 backdrop-blur-[2px]">
              <Sparkles className="w-5 h-5 text-zinc-500 mb-1.5" />
              <p className="text-xs font-bold text-zinc-200">Subtitle Dinonaktifkan</p>
              <p className="text-[11px] text-zinc-400 mt-0.5 max-w-[180px]">
                Video diproses bersih tanpa teks overlay
              </p>
            </div>
          ) : (
            <LiveSubtitleOverlay
              style={subtitleStyle}
              text={previewText.trim() || 'KONTEN VIRAL HARI INI'}
              fontFamily={activeFont}
              position={subtitlePosition}
              currentTime={currentTime}
              duration={duration}
              isPlaying={isPlaying}
              aspectRatio={aspectRatio}
              framingMode={framingMode}
              fontSizeScale={fontSizeScale}
            />
          )}

          {/* Pause overlay icon when paused */}
          {!isPlaying && (
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center z-25 pointer-events-none backdrop-blur-[1px]">
              <div className="w-12 h-12 rounded-full bg-violet-600/90 text-white flex items-center justify-center shadow-xl ring-4 ring-white/10 transform scale-100 transition-transform">
                <Play className="w-5 h-5 fill-white ml-0.5" />
              </div>
            </div>
          )}
        </div>

        {/* Bottom Playback Controls Bar */}
        <div className="w-full max-w-md mt-3 pt-2 flex items-center gap-2 z-30">
          {/* Play/Pause Button */}
          <button
            type="button"
            onClick={togglePlayPause}
            aria-label={isPlaying ? 'Jeda video' : 'Putar video'}
            className="w-8 h-8 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 hover:text-white border border-zinc-700/80 flex items-center justify-center cursor-pointer transition-colors shrink-0 shadow-sm"
          >
            {isPlaying ? (
              <Pause className="w-3.5 h-3.5 fill-current" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
            )}
          </button>

          {/* Replay Button */}
          <button
            type="button"
            onClick={handleReset}
            aria-label="Ulang dari awal"
            className="w-8 h-8 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 hover:text-white border border-zinc-700/80 flex items-center justify-center cursor-pointer transition-colors shrink-0 shadow-sm"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          {/* Sound Toggle (Mute / Unmute) */}
          <button
            type="button"
            onClick={toggleMute}
            aria-label={isMuted ? 'Nyalakan audio video' : 'Bisukan audio video'}
            className={`h-8 px-2.5 rounded-lg border flex items-center gap-1.5 cursor-pointer transition-colors shrink-0 text-xs font-semibold shadow-sm ${
              !isMuted
                ? 'bg-emerald-950/80 border-emerald-500 text-emerald-300 hover:bg-emerald-900/90 ring-1 ring-emerald-500/30'
                : 'bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border-zinc-700/80'
            }`}
            title={isMuted ? 'Nyalakan Suara Pembicara (Audio Asli)' : 'Bisukan Suara'}
          >
            {isMuted ? (
              <>
                <VolumeX className="w-3.5 h-3.5 text-zinc-400" />
                <span className="hidden sm:inline">Mute</span>
              </>
            ) : (
              <>
                <Volume2 className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                <span className="hidden sm:inline">Suara Nyala</span>
              </>
            )}
          </button>

          {/* Scrubber Progress Bar */}
          <div className="flex-1 flex items-center gap-2">
            <span className="text-[10px] font-mono text-zinc-400 w-8 text-right shrink-0">
              {currentTime.toFixed(1)}s
            </span>
            <input
              type="range"
              min={0}
              max={duration || 6}
              step={0.05}
              value={currentTime}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setCurrentTime(val);
                if (videoRef.current && videoLoaded && !hasVideoError) {
                  videoRef.current.currentTime = val;
                }
              }}
              aria-label="Timeline seekbar video animasi"
              className="w-full accent-violet-500 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            />
            <span className="text-[10px] font-mono text-zinc-400 w-8 shrink-0">
              {duration.toFixed(1)}s
            </span>
          </div>
        </div>
      </div>

      {/* Input Ubah Teks Pratinjau Cepat + Saran Hook */}
      {subtitleStyle !== 'none' && (
        <div className="space-y-2 px-0.5">
          <div className="flex items-center gap-2">
            <label
              htmlFor="preview-subtitle-input"
              className="text-xs sm:text-sm font-semibold text-zinc-300 shrink-0 flex items-center gap-1.5 cursor-pointer"
            >
              <Type className="w-3.5 h-3.5 text-cyan-400" />
              <span>Teks Pratinjau:</span>
            </label>
            <input
              id="preview-subtitle-input"
              type="text"
              value={previewText}
              onChange={(e) => onPreviewTextChange(e.target.value)}
              placeholder="Ketik teks untuk melihat animasinya..."
              className="h-9 px-3 text-xs sm:text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 placeholder-zinc-500 focus-visible:outline-none focus-visible:border-violet-500 w-full font-medium shadow-inner"
            />
          </div>

          {/* Quick Hook Suggestions Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            <span className="text-[11px] text-zinc-500 shrink-0">Pilihan Teks:</span>
            {/* Real speech transcript pill */}
            <button
              type="button"
              onClick={() => {
                onPreviewTextChange(ILLUSTRATION_TRANSCRIPT_TEXT);
                handleReset();
              }}
              className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors whitespace-nowrap cursor-pointer flex items-center gap-1 ${
                isSpeechTranscript
                  ? 'bg-emerald-950/80 border-emerald-500 text-emerald-200 font-bold shadow-sm'
                  : 'bg-zinc-900/80 border-zinc-800 text-zinc-400 hover:text-emerald-300 hover:border-emerald-700/60'
              }`}
              title="Gunakan transkrip asli omongan pembicara di video"
            >
              <Mic className="w-3 h-3 text-emerald-400" />
              <span>🎙️ Transkrip Asli Video</span>
            </button>

            {QUICK_HOOK_SUGGESTIONS.map((hook) => (
              <button
                key={hook}
                type="button"
                onClick={() => {
                  onPreviewTextChange(hook);
                  handleReset();
                }}
                className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors whitespace-nowrap cursor-pointer ${
                  previewText === hook
                    ? 'bg-violet-950/60 border-violet-600 text-violet-200 font-semibold'
                    : 'bg-zinc-900/80 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
                }`}
              >
                {hook}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
