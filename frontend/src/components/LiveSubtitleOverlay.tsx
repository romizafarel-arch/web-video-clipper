import { type FC } from 'react';
import type { SubtitleStyle, FramingMode } from '../types';
import { normalizePresetId } from '../lib/textPresets';
import { getDefaultFontForPreset } from '../lib/fontFamilyLibrary';
import {
  ILLUSTRATION_TRANSCRIPT_TEXT,
  ILLUSTRATION_CUES,
} from '../lib/illustrationTranscript';

export interface LiveSubtitleOverlayProps {
  style: SubtitleStyle;
  text: string;
  fontFamily?: string;
  currentTime?: number;
  duration?: number;
  isPlaying?: boolean;
  position?: 'bottom' | 'center';
  customColor?: 'yellow' | 'white';
  aspectRatio?: string;
  framingMode?: FramingMode;
}

export const LiveSubtitleOverlay: FC<LiveSubtitleOverlayProps> = ({
  style,
  text,
  fontFamily,
  currentTime = 0,
  duration = 15,
  isPlaying = false,
  position = 'bottom',
  customColor = 'yellow',
  aspectRatio = '9:16',
  framingMode = 'podcast',
}) => {
  if (style === 'none') {
    return null;
  }

  const rawText = text.trim() || 'TEKS SUBTITLE TIKTOK';
  const isSpeechTranscript =
    rawText.toLowerCase() === ILLUSTRATION_TRANSCRIPT_TEXT.toLowerCase();

  let words: string[];
  let activeWordIndex = 0;

  if (isSpeechTranscript) {
    const activeCue =
      ILLUSTRATION_CUES.find(
        (cue) => currentTime >= cue.start && currentTime < cue.end
      ) ||
      (currentTime >= 5.9
        ? ILLUSTRATION_CUES[ILLUSTRATION_CUES.length - 1]
        : ILLUSTRATION_CUES[0]);

    words = activeCue.words.map((w) => w.word);

    const foundIdx = activeCue.words.findIndex(
      (w) => currentTime >= w.start && currentTime <= w.end
    );
    if (foundIdx !== -1) {
      activeWordIndex = foundIdx;
    } else {
      let lastStarted = 0;
      for (let i = 0; i < activeCue.words.length; i++) {
        if (currentTime >= activeCue.words[i].start) {
          lastStarted = i;
        }
      }
      activeWordIndex = lastStarted;
    }
  } else {
    words = rawText.split(/\s+/).filter(Boolean);
    const totalWords = Math.max(1, words.length);
    const safeDuration = Math.max(0.1, duration);
    activeWordIndex = Math.min(
      totalWords - 1,
      Math.floor((currentTime / safeDuration) * totalWords)
    );
  }

  const presetId = normalizePresetId(style);
  const activeFont = fontFamily?.trim() || getDefaultFontForPreset(presetId);

  const bottomOffsetClass =
    framingMode === 'gaming' && aspectRatio === '9:16'
      ? 'bottom-[28%] sm:bottom-[30%]'
      : aspectRatio === '16:9'
      ? 'bottom-3.5 sm:bottom-5'
      : aspectRatio === '1:1'
      ? 'bottom-5 sm:bottom-7'
      : 'bottom-8 sm:bottom-12';

  const positionClass = position === 'center' ? 'top-1/2 -translate-y-1/2' : bottomOffsetClass;

  return (
    <div
      aria-label="Pratinjau Subtitle"
      className={`absolute inset-x-0 px-3 z-30 pointer-events-none select-none transition-all duration-200 ${positionClass}`}
    >
      {/* 1. HORMOZI CLASSIC */}
      {(presetId === 'hormozi' || presetId === 'hormozi_emerald') && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2.5 px-1 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isHighlighted = isPlaying ? idx === activeWordIndex : idx === 0;
            const upper = w.toUpperCase();
            return (
              <span
                key={idx}
                className={`font-black uppercase tracking-wider text-base sm:text-lg md:text-xl lg:text-2xl leading-tight transition-all duration-150 stroke-hormozi inline-block ${
                  isHighlighted
                    ? customColor === 'white'
                      ? 'scale-125 text-white drop-shadow-[0_0_24px_rgba(255,255,255,0.95)] z-10'
                      : 'scale-125 text-[#FFE600] drop-shadow-[0_0_24px_rgba(255,230,0,0.95)] z-10'
                    : 'text-white/90 scale-100'
                }`}
              >
                {upper}
              </span>
            );
          })}
        </div>
      )}

      {/* 4. TIKTOK PUNCH */}
      {presetId === 'tiktok_punch' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isHighlighted = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`font-black uppercase tracking-wider text-base sm:text-lg md:text-xl lg:text-2xl leading-tight transition-all duration-150 stroke-hormozi inline-block ${
                  isHighlighted
                    ? 'scale-125 text-[#FFE600] z-10'
                    : 'text-white scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 5. DEVON IMPACT */}
      {presetId === 'devon_bold' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2.5 px-1 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isHighlighted = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`uppercase tracking-tight text-xl sm:text-2xl md:text-3xl leading-tight transition-all duration-150 stroke-hormozi inline-block ${
                  isHighlighted
                    ? 'scale-120 text-[#FFFF00] z-10'
                    : 'text-white scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 6. PODCAST VOX */}
      {presetId === 'vox_box' && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont }}>
          <div className="inline-block bg-black/85 backdrop-blur-md px-4 py-2 sm:px-6 sm:py-2.5 rounded-xl border border-white/15 shadow-2xl max-w-[92%] text-center">
            <span className="font-semibold text-sm sm:text-base md:text-lg text-white tracking-normal leading-relaxed">
              {words.map((w, idx) => {
                const isCurrent = isPlaying && idx === activeWordIndex;
                return (
                  <span
                    key={idx}
                    className={`transition-all duration-150 inline-block ${
                      isCurrent
                        ? 'text-amber-300 font-bold underline decoration-amber-400 decoration-2 scale-105 mx-0.5'
                        : 'text-white'
                    }`}
                  >
                    {w}{idx < words.length - 1 ? ' ' : ''}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 5. DAN KOE MINIMAL */}
      {(presetId === 'dan_koe' || presetId === 'vox_cinema') && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont }}>
          <div className="inline-block bg-zinc-950/85 backdrop-blur-md px-4 py-2 sm:px-6 sm:py-2.5 rounded-xl border border-zinc-700/50 shadow-2xl max-w-[92%] text-center">
            <span className="font-medium text-sm sm:text-base md:text-lg text-zinc-100 tracking-tight leading-relaxed">
              {words.map((w, idx) => {
                const isCurrent = isPlaying && idx === activeWordIndex;
                return (
                  <span
                    key={idx}
                    className={`transition-all duration-150 inline-block ${
                      isCurrent
                        ? 'text-white font-bold scale-105 mx-0.5 underline decoration-zinc-400 decoration-1'
                        : 'text-zinc-400'
                    }`}
                  >
                    {w}{idx < words.length - 1 ? ' ' : ''}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 6. ALI ABDAAL HIGHLIGHTER */}
      {(presetId === 'ali_abdaal' || presetId === 'ali_cyan') && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-2 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isHighlight = isPlaying ? idx === activeWordIndex : idx === 0;
            return isHighlight ? (
              <span
                key={idx}
                className="font-bold text-sm sm:text-base md:text-lg bg-[#FEF08A] text-zinc-950 px-2.5 py-1 rounded-md shadow-lg scale-110 inline-block transform transition-all duration-150 mx-0.5 leading-snug"
              >
                {w}
              </span>
            ) : (
              <span
                key={idx}
                className="font-bold text-sm sm:text-base md:text-lg text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.95)] transition-all duration-150 leading-snug inline-block"
              >
                {w}
              </span>
            );
          })}
        </div>
      )}

      {/* 7. AESTHETIC CINEMA */}
      {(presetId === 'aesthetic' || presetId === 'aesthetic_warm') && (
        <div className="flex flex-wrap justify-center items-center gap-2 px-3 text-center" style={{ fontFamily: activeFont }}>
          {words.map((w, idx) => {
            const isCurrent = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`uppercase tracking-[0.22em] text-sm sm:text-base md:text-xl leading-snug transition-all duration-200 inline-block ${
                  isCurrent
                    ? 'text-white font-bold drop-shadow-[0_0_16px_rgba(255,255,255,0.95)] scale-105'
                    : 'text-zinc-300/80 shadow-cinema'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 8. MRBEAST POP CYAN */}
      {(presetId === 'mrbeast' || presetId === 'mrbeast_yellow') && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2.5 px-1 text-center rotate-[-2deg]"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isPop = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`italic uppercase tracking-wider text-lg sm:text-xl md:text-2xl lg:text-3xl leading-none transition-all duration-150 stroke-mrbeast inline-block ${
                  isPop
                    ? 'scale-125 text-[#FFE600] drop-shadow-[0_0_24px_rgba(255,230,0,0.9)] -translate-y-1'
                    : 'text-[#00F0FF] scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 14. KARAOKE BOUNCE */}
      {presetId === 'karaoke_bounce' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`font-black uppercase text-base sm:text-lg md:text-xl leading-tight transition-all duration-150 stroke-hormozi inline-block ${
                  isActive
                    ? 'scale-130 text-amber-300 drop-shadow-[0_0_20px_rgba(251,191,36,0.95)] z-10'
                    : 'text-cyan-300/80 scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 15. CYBER NEON */}
      {presetId === 'cyber_neon' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2.5 px-1 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`font-bold uppercase tracking-wider text-base sm:text-lg md:text-xl leading-tight transition-all duration-150 stroke-cyber-neon inline-block ${
                  isActive
                    ? 'scale-125 text-[#FF00FF] z-10'
                    : 'text-cyan-400 scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 16. RETRO SYNTH */}
      {presetId === 'retro_synth' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center rotate-[-1deg]"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`uppercase tracking-wider text-lg sm:text-xl md:text-2xl leading-none transition-all duration-150 stroke-hormozi inline-block ${
                  isActive
                    ? 'scale-120 text-[#FFAA00] drop-shadow-[0_0_16px_rgba(255,170,0,0.9)] z-10'
                    : 'text-[#FFFF00] scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 17. LUXURY GOLD */}
      {presetId === 'luxury_gold' && (
        <div
          className="flex flex-wrap justify-center items-center gap-2 px-2 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`uppercase tracking-[0.18em] text-base sm:text-lg md:text-xl leading-snug transition-all duration-150 shadow-luxury-gold inline-block ${
                  isActive
                    ? 'scale-115 text-[#FEE68A] font-bold z-10'
                    : 'text-white/90 scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 18. GAMING RAGE */}
      {presetId === 'gaming_rage' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center italic rotate-[-2deg]"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`uppercase tracking-wider text-xl sm:text-2xl md:text-3xl leading-none transition-all duration-150 stroke-fire-glow inline-block ${
                  isActive
                    ? 'scale-125 text-[#FF2222] z-10'
                    : 'text-white scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 19. CLEAN BOTTOM BAR */}
      {presetId === 'clean_bottom_bar' && (
        <div className="flex justify-center px-1" style={{ fontFamily: activeFont }}>
          <div className="bg-black/95 px-4 py-1.5 sm:px-6 sm:py-2 border-y-2 border-amber-400 text-center w-full max-w-[94%]">
            <span className="font-bold text-sm sm:text-base md:text-lg text-white uppercase tracking-wider">
              {words.map((w, idx) => {
                const isActive = isPlaying && idx === activeWordIndex;
                return (
                  <span
                    key={idx}
                    className={`transition-all duration-150 inline-block mx-0.5 ${
                      isActive ? 'text-amber-400 font-black' : 'text-white'
                    }`}
                  >
                    {w.toUpperCase()}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 14. COMIC POW */}
      {presetId === 'comic_pow' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center rotate-[2deg]"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`uppercase text-lg sm:text-xl md:text-2xl leading-none transition-all duration-150 stroke-mrbeast inline-block ${
                  isActive
                    ? 'scale-125 text-[#FFFF00] -translate-y-1'
                    : 'text-white'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 15. NAS DAILY TAG */}
      {presetId === 'nas_daily' && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont }}>
          <div className="inline-block bg-[#E11D48] px-4 py-2 sm:px-6 sm:py-2.5 rounded-full border border-red-300/40 shadow-2xl max-w-[92%] text-center">
            <span className="font-black text-sm sm:text-base md:text-xl text-white uppercase tracking-tight leading-tight">
              {words.map((w, idx) => {
                const isActive = isPlaying && idx === activeWordIndex;
                return (
                  <span
                    key={idx}
                    className={`transition-all duration-150 inline-block mx-0.5 ${
                      isActive ? 'text-yellow-200 scale-110 drop-shadow' : 'text-white'
                    }`}
                  >
                    {w.toUpperCase()}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 16. NETFLIX CINEMA SUBTITLE */}
      {presetId === 'netflix_sub' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-3 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`text-base sm:text-lg md:text-xl font-bold leading-relaxed transition-all duration-150 inline-block ${
                  isActive
                    ? 'text-[#FFE600] scale-110 drop-shadow-[0_2px_4px_rgba(0,0,0,1)]'
                    : 'text-white/95 drop-shadow-[0_2px_4px_rgba(0,0,0,1)]'
                }`}
              >
                {w}
              </span>
            );
          })}
        </div>
      )}

      {/* 17. MATRIX HACKER TERMINAL */}
      {presetId === 'matrix_hacker' && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont }}>
          <div className="inline-block bg-emerald-950/90 border border-emerald-500/70 px-4 py-1.5 sm:px-6 sm:py-2 rounded shadow-[0_0_24px_rgba(0,255,102,0.35)] text-center max-w-[94%]">
            <span className="font-mono font-bold uppercase tracking-widest text-sm sm:text-base md:text-lg text-[#00FF66] drop-shadow-[0_0_8px_rgba(0,255,102,0.9)]">
              {words.map((w, idx) => {
                const isActive = isPlaying && idx === activeWordIndex;
                return (
                  <span
                    key={idx}
                    className={`transition-all duration-150 inline-block mx-0.5 ${
                      isActive ? 'text-white bg-emerald-800/80 px-1 rounded scale-105' : 'text-[#00FF66]'
                    }`}
                  >
                    {w.toUpperCase()}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 19. FIRE FLAME HYPE */}
      {(presetId === 'fire_flame' || presetId === 'hormozi_fire') && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2.5 px-1 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`uppercase tracking-wider text-xl sm:text-2xl md:text-3xl leading-none transition-all duration-150 stroke-fire-glow inline-block ${
                  isActive
                    ? 'scale-125 text-[#FF4500] drop-shadow-[0_0_24px_rgba(255,69,0,0.95)] -translate-y-1'
                    : 'text-[#FFA500] scale-100'
                }`}
              >
                {w.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 20. PASTEL VLOG DREAM */}
      {presetId === 'pastel_vlog' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-3 text-center"
          style={{ fontFamily: activeFont }}
        >
          {words.map((w, idx) => {
            const isActive = isPlaying ? idx === activeWordIndex : idx === 0;
            return (
              <span
                key={idx}
                className={`font-semibold text-base sm:text-lg md:text-xl leading-relaxed transition-all duration-150 inline-block ${
                  isActive
                    ? 'scale-115 text-[#E9D5FF] font-bold drop-shadow-[0_2px_12px_rgba(168,85,247,0.8)]'
                    : 'text-white/90 drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)]'
                }`}
              >
                {w}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
};
