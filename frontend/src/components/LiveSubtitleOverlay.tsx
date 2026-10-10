import { type FC } from 'react';
import type { SubtitleStyle, FramingMode, SubtitleFontSizeScale } from '../types';
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
  fontSizeScale?: SubtitleFontSizeScale | number;
}

export interface PacedWordItem {
  word: string;
  originalIndex: number;
}

const KINETIC_PRESET_IDS = new Set<string>([
  'hormozi',
  'hormozi_emerald',
  'tiktok_punch',
  'devon_bold',
  'mrbeast',
  'mrbeast_yellow',
  'karaoke_bounce',
  'cyber_neon',
  'retro_synth',
  'luxury_gold',
  'gaming_rage',
  'comic_pow',
  'fire_flame',
  'hormozi_fire',
  'ali_abdaal',
  'ali_cyan',
]);

function getKineticBeatWords(
  words: string[],
  activeWordIndex: number,
  maxWordsPerBeat: number = 3
): {
  visibleWords: PacedWordItem[];
  activeVisibleIndex: number;
} {
  if (words.length === 0) {
    return { visibleWords: [], activeVisibleIndex: 0 };
  }
  if (words.length <= maxWordsPerBeat) {
    return {
      visibleWords: words.map((word, idx) => ({ word, originalIndex: idx })),
      activeVisibleIndex: Math.max(0, Math.min(words.length - 1, activeWordIndex)),
    };
  }

  // Create beats of 2 words (or 3 words for remainders) so words are 1-3 per beat
  const beats: { start: number; end: number }[] = [];
  let i = 0;
  while (i < words.length) {
    const remaining = words.length - i;
    if (remaining === 3) {
      beats.push({ start: i, end: i + 3 });
      i += 3;
    } else if (remaining === 1 && beats.length > 0) {
      beats[beats.length - 1].end += 1;
      i += 1;
    } else {
      const take = Math.min(2, remaining);
      beats.push({ start: i, end: i + take });
      i += take;
    }
  }

  const safeActiveIndex = Math.max(0, Math.min(words.length - 1, activeWordIndex));
  const currentBeat = beats.find(
    (b) => safeActiveIndex >= b.start && safeActiveIndex < b.end
  ) || beats[0];

  const visibleWords = words
    .slice(currentBeat.start, currentBeat.end)
    .map((word, offset) => ({
      word,
      originalIndex: currentBeat.start + offset,
    }));

  const activeVisibleIndex = safeActiveIndex - currentBeat.start;

  return { visibleWords, activeVisibleIndex };
}

function getSentencePacedWords(
  words: string[],
  activeWordIndex: number,
  maxWordsPerSentence: number = 8
): {
  visibleWords: PacedWordItem[];
  activeVisibleIndex: number;
} {
  if (words.length <= maxWordsPerSentence) {
    return {
      visibleWords: words.map((word, idx) => ({ word, originalIndex: idx })),
      activeVisibleIndex: Math.max(0, Math.min(words.length - 1, activeWordIndex)),
    };
  }

  const chunks: { start: number; end: number }[] = [];
  let i = 0;
  while (i < words.length) {
    const take = Math.min(6, words.length - i);
    chunks.push({ start: i, end: i + take });
    i += take;
  }
  const safeActiveIndex = Math.max(0, Math.min(words.length - 1, activeWordIndex));
  const currentChunk = chunks.find(
    (c) => safeActiveIndex >= c.start && safeActiveIndex < c.end
  ) || chunks[0];

  return {
    visibleWords: words.slice(currentChunk.start, currentChunk.end).map((word, offset) => ({
      word,
      originalIndex: currentChunk.start + offset,
    })),
    activeVisibleIndex: safeActiveIndex - currentChunk.start,
  };
}

function getFontSizeMultiplier(scale?: SubtitleFontSizeScale | number): number {
  if (typeof scale === 'number') {
    return scale > 0 ? scale : 1.0;
  }
  if (scale === 'small') return 0.85;
  if (scale === 'large') return 1.2;
  return 1.0;
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
  fontSizeScale = 'medium',
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

  const isKinetic = KINETIC_PRESET_IDS.has(presetId);
  const { visibleWords, activeVisibleIndex } = isKinetic
    ? getKineticBeatWords(words, activeWordIndex)
    : getSentencePacedWords(words, activeWordIndex);

  const scaleMult = getFontSizeMultiplier(fontSizeScale);

  // Container-relative typography styles using cqw (container query width) and clamp
  const kineticBigStyle: React.CSSProperties = {
    fontSize: `clamp(${(14 * scaleMult).toFixed(1)}px, ${(7.6 * scaleMult).toFixed(2)}cqw, ${(24 * scaleMult).toFixed(1)}px)`,
  };

  const kineticMediumStyle: React.CSSProperties = {
    fontSize: `clamp(${(13 * scaleMult).toFixed(1)}px, ${(6.8 * scaleMult).toFixed(2)}cqw, ${(22 * scaleMult).toFixed(1)}px)`,
  };

  const boxSubStyle: React.CSSProperties = {
    fontSize: `clamp(${(10.5 * scaleMult).toFixed(1)}px, ${(4.4 * scaleMult).toFixed(2)}cqw, ${(15.5 * scaleMult).toFixed(1)}px)`,
  };

  const cinemaSubStyle: React.CSSProperties = {
    fontSize: `clamp(${(11.5 * scaleMult).toFixed(1)}px, ${(4.8 * scaleMult).toFixed(2)}cqw, ${(16.5 * scaleMult).toFixed(1)}px)`,
  };

  // Safe bottom offset relative to video box
  const bottomOffsetClass =
    framingMode === 'gaming' && aspectRatio === '9:16'
      ? 'bottom-[28%]'
      : aspectRatio === '16:9'
      ? 'bottom-[8%]'
      : aspectRatio === '1:1'
      ? 'bottom-[10%]'
      : 'bottom-[13%]';

  const positionClass = position === 'center' ? 'top-1/2 -translate-y-1/2' : bottomOffsetClass;

  return (
    <div
      aria-label="Pratinjau Subtitle"
      className={`absolute inset-x-0 px-2 sm:px-3 z-30 pointer-events-none select-none transition-all duration-200 ${positionClass}`}
    >
      {/* 1. HORMOZI CLASSIC */}
      {(presetId === 'hormozi' || presetId === 'hormozi_emerald') && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isHighlighted = isPlaying ? idx === activeVisibleIndex : idx === 0;
            const upper = item.word.toUpperCase();
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`font-black uppercase tracking-wider leading-tight transition-all duration-150 stroke-hormozi inline-block ${
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

      {/* 2. TIKTOK PUNCH */}
      {presetId === 'tiktok_punch' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isHighlighted = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`font-black uppercase tracking-wider leading-tight transition-all duration-150 stroke-hormozi inline-block ${
                  isHighlighted
                    ? 'scale-125 text-[#FFE600] z-10'
                    : 'text-white scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 3. DEVON IMPACT */}
      {presetId === 'devon_bold' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isHighlighted = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`uppercase tracking-tight leading-tight transition-all duration-150 stroke-hormozi inline-block ${
                  isHighlighted
                    ? 'scale-120 text-[#FFFF00] z-10'
                    : 'text-white scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 4. PODCAST VOX */}
      {presetId === 'vox_box' && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont, ...boxSubStyle }}>
          <div className="inline-block bg-black/85 backdrop-blur-md px-3.5 py-1.5 sm:px-5 sm:py-2 rounded-xl border border-white/15 shadow-2xl max-w-[94%] text-center">
            <span className="font-semibold text-white tracking-normal leading-relaxed">
              {visibleWords.map((item, idx) => {
                const isCurrent = isPlaying && idx === activeVisibleIndex;
                return (
                  <span
                    key={`${item.originalIndex}-${item.word}`}
                    className={`transition-all duration-150 inline-block ${
                      isCurrent
                        ? 'text-amber-300 font-bold underline decoration-amber-400 decoration-2 scale-105 mx-0.5'
                        : 'text-white'
                    }`}
                  >
                    {item.word}{idx < visibleWords.length - 1 ? ' ' : ''}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 5. DAN KOE MINIMAL */}
      {(presetId === 'dan_koe' || presetId === 'vox_cinema') && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont, ...boxSubStyle }}>
          <div className="inline-block bg-zinc-950/85 backdrop-blur-md px-3.5 py-1.5 sm:px-5 sm:py-2 rounded-xl border border-zinc-700/50 shadow-2xl max-w-[94%] text-center">
            <span className="font-medium text-zinc-100 tracking-tight leading-relaxed">
              {visibleWords.map((item, idx) => {
                const isCurrent = isPlaying && idx === activeVisibleIndex;
                return (
                  <span
                    key={`${item.originalIndex}-${item.word}`}
                    className={`transition-all duration-150 inline-block ${
                      isCurrent
                        ? 'text-white font-bold scale-105 mx-0.5 underline decoration-zinc-400 decoration-1'
                        : 'text-zinc-400'
                    }`}
                  >
                    {item.word}{idx < visibleWords.length - 1 ? ' ' : ''}
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
          style={{ fontFamily: activeFont, ...kineticMediumStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isHighlight = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return isHighlight ? (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className="font-bold bg-[#FEF08A] text-zinc-950 px-2 py-0.5 rounded-md shadow-lg scale-110 inline-block transform transition-all duration-150 mx-0.5 leading-snug"
              >
                {item.word}
              </span>
            ) : (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className="font-bold text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.95)] transition-all duration-150 leading-snug inline-block"
              >
                {item.word}
              </span>
            );
          })}
        </div>
      )}

      {/* 7. AESTHETIC CINEMA */}
      {(presetId === 'aesthetic' || presetId === 'aesthetic_warm') && (
        <div className="flex flex-wrap justify-center items-center gap-2 px-3 text-center" style={{ fontFamily: activeFont, ...cinemaSubStyle }}>
          {visibleWords.map((item, idx) => {
            const isCurrent = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`uppercase tracking-[0.22em] leading-snug transition-all duration-200 inline-block ${
                  isCurrent
                    ? 'text-white font-bold drop-shadow-[0_0_16px_rgba(255,255,255,0.95)] scale-105'
                    : 'text-zinc-300/80 shadow-cinema'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 8. MRBEAST POP CYAN */}
      {(presetId === 'mrbeast' || presetId === 'mrbeast_yellow') && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center rotate-[-2deg]"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isPop = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`italic uppercase tracking-wider leading-none transition-all duration-150 stroke-mrbeast inline-block ${
                  isPop
                    ? 'scale-125 text-[#FFE600] drop-shadow-[0_0_24px_rgba(255,230,0,0.9)] -translate-y-1'
                    : 'text-[#00F0FF] scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 9. KARAOKE BOUNCE */}
      {presetId === 'karaoke_bounce' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`font-black uppercase leading-tight transition-all duration-150 stroke-hormozi inline-block ${
                  isActive
                    ? 'scale-130 text-amber-300 drop-shadow-[0_0_20px_rgba(251,191,36,0.95)] z-10'
                    : 'text-cyan-300/80 scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 10. CYBER NEON */}
      {presetId === 'cyber_neon' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont, ...kineticMediumStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`font-bold uppercase tracking-wider leading-tight transition-all duration-150 stroke-cyber-neon inline-block ${
                  isActive
                    ? 'scale-125 text-[#FF00FF] z-10'
                    : 'text-cyan-400 scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 11. RETRO SYNTH */}
      {presetId === 'retro_synth' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center rotate-[-1deg]"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`uppercase tracking-wider leading-none transition-all duration-150 stroke-hormozi inline-block ${
                  isActive
                    ? 'scale-120 text-[#FFAA00] drop-shadow-[0_0_16px_rgba(255,170,0,0.9)] z-10'
                    : 'text-[#FFFF00] scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 12. LUXURY GOLD */}
      {presetId === 'luxury_gold' && (
        <div
          className="flex flex-wrap justify-center items-center gap-2 px-2 text-center"
          style={{ fontFamily: activeFont, ...kineticMediumStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`uppercase tracking-[0.18em] leading-snug transition-all duration-150 shadow-luxury-gold inline-block ${
                  isActive
                    ? 'scale-115 text-[#FEE68A] font-bold z-10'
                    : 'text-white/90 scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 13. GAMING RAGE */}
      {presetId === 'gaming_rage' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center italic rotate-[-2deg]"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`uppercase tracking-wider leading-none transition-all duration-150 stroke-fire-glow inline-block ${
                  isActive
                    ? 'scale-125 text-[#FF2222] z-10'
                    : 'text-white scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 14. CLEAN BOTTOM BAR */}
      {presetId === 'clean_bottom_bar' && (
        <div className="flex justify-center px-1" style={{ fontFamily: activeFont, ...boxSubStyle }}>
          <div className="bg-black/95 px-3 py-1.5 border-y-2 border-amber-400 text-center w-full max-w-[96%]">
            <span className="font-bold text-white uppercase tracking-wider">
              {visibleWords.map((item, idx) => {
                const isActive = isPlaying && idx === activeVisibleIndex;
                return (
                  <span
                    key={`${item.originalIndex}-${item.word}`}
                    className={`transition-all duration-150 inline-block mx-0.5 ${
                      isActive ? 'text-amber-400 font-black' : 'text-white'
                    }`}
                  >
                    {item.word.toUpperCase()}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 15. COMIC POW */}
      {presetId === 'comic_pow' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center rotate-[2deg]"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`uppercase leading-none transition-all duration-150 stroke-mrbeast inline-block ${
                  isActive
                    ? 'scale-125 text-[#FFFF00] -translate-y-1'
                    : 'text-white'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 16. NAS DAILY TAG */}
      {presetId === 'nas_daily' && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont, ...boxSubStyle }}>
          <div className="inline-block bg-[#E11D48] px-3.5 py-1.5 sm:px-5 sm:py-2 rounded-full border border-red-300/40 shadow-2xl max-w-[94%] text-center">
            <span className="font-black text-white uppercase tracking-tight leading-tight">
              {visibleWords.map((item, idx) => {
                const isActive = isPlaying && idx === activeVisibleIndex;
                return (
                  <span
                    key={`${item.originalIndex}-${item.word}`}
                    className={`transition-all duration-150 inline-block mx-0.5 ${
                      isActive ? 'text-yellow-200 scale-110 drop-shadow' : 'text-white'
                    }`}
                  >
                    {item.word.toUpperCase()}
                  </span>
                );
              })}
            </span>
          </div>
        </div>
      )}

      {/* 17. NETFLIX CINEMA SUBTITLE */}
      {presetId === 'netflix_sub' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-3 text-center"
          style={{ fontFamily: activeFont, ...cinemaSubStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`font-bold leading-relaxed transition-all duration-150 inline-block ${
                  isActive
                    ? 'text-[#FFE600] scale-105 drop-shadow-[0_2px_4px_rgba(0,0,0,1)]'
                    : 'text-white/95 drop-shadow-[0_2px_4px_rgba(0,0,0,1)]'
                }`}
              >
                {item.word}
              </span>
            );
          })}
        </div>
      )}

      {/* 18. MATRIX HACKER TERMINAL */}
      {presetId === 'matrix_hacker' && (
        <div className="flex justify-center px-2" style={{ fontFamily: activeFont, ...boxSubStyle }}>
          <div className="inline-block bg-emerald-950/90 border border-emerald-500/70 px-3.5 py-1.5 rounded shadow-[0_0_24px_rgba(0,255,102,0.35)] text-center max-w-[94%]">
            <span className="font-mono font-bold uppercase tracking-widest text-[#00FF66] drop-shadow-[0_0_8px_rgba(0,255,102,0.9)]">
              {visibleWords.map((item, idx) => {
                const isActive = isPlaying && idx === activeVisibleIndex;
                return (
                  <span
                    key={`${item.originalIndex}-${item.word}`}
                    className={`transition-all duration-150 inline-block mx-0.5 ${
                      isActive ? 'text-white bg-emerald-800/80 px-1 rounded scale-105' : 'text-[#00FF66]'
                    }`}
                  >
                    {item.word.toUpperCase()}
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
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-1 text-center"
          style={{ fontFamily: activeFont, ...kineticBigStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`uppercase tracking-wider leading-none transition-all duration-150 stroke-fire-glow inline-block ${
                  isActive
                    ? 'scale-125 text-[#FF4500] drop-shadow-[0_0_24px_rgba(255,69,0,0.95)] -translate-y-1'
                    : 'text-[#FFA500] scale-100'
                }`}
              >
                {item.word.toUpperCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* 20. PASTEL VLOG DREAM */}
      {presetId === 'pastel_vlog' && (
        <div
          className="flex flex-wrap justify-center items-center gap-1.5 sm:gap-2 px-3 text-center"
          style={{ fontFamily: activeFont, ...cinemaSubStyle }}
        >
          {visibleWords.map((item, idx) => {
            const isActive = isPlaying ? idx === activeVisibleIndex : idx === 0;
            return (
              <span
                key={`${item.originalIndex}-${item.word}`}
                className={`font-semibold leading-relaxed transition-all duration-150 inline-block ${
                  isActive
                    ? 'scale-115 text-[#E9D5FF] font-bold drop-shadow-[0_2px_12px_rgba(168,85,247,0.8)]'
                    : 'text-white/90 drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)]'
                }`}
              >
                {item.word}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
};
