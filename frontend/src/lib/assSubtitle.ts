import type { SubtitleCue, SubtitleStyle } from '../types';
import { getTextPreset } from './textPresets';

/**
 * Format float seconds into ASS timestamp format: H:MM:SS.cc
 */
export function formatAssTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '0:00:00.00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const cs = Math.floor((seconds % 1) * 100);
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${cs.toString().padStart(2, '0')}`;
}

export interface AssGenerationOptions {
  width?: number;
  height?: number;
  marginV?: number;
  fontName?: string;
}

export interface TimedWordCs {
  word: string;
  duration_cs: number;
}

/**
 * Computes per-word centisecond duration matching backend pacing logic.
 */
export function computeWordCentiseconds(
  words: string[],
  totalDuration: number,
  explicitWords?: Array<{ word: string; start: number; end: number; duration_cs?: number }>
): TimedWordCs[] {
  const totalCs = Math.max(1, Math.round(totalDuration * 100));
  const n = words.length;
  if (n === 0) return [];
  if (n === 1) return [{ word: words[0], duration_cs: totalCs }];

  let alloc: number[];
  if (explicitWords && explicitWords.length === n) {
    const rawDurs = explicitWords.map((ew) =>
      ew.duration_cs && ew.duration_cs > 0
        ? ew.duration_cs
        : Math.max(0.01, ew.end - ew.start) * 100
    );
    const sumRaw = rawDurs.reduce((acc, d) => acc + d, 0);
    if (sumRaw > 0) {
      alloc = rawDurs.map((d) => Math.max(1, Math.round(totalCs * (d / sumRaw))));
    } else {
      alloc = Array(n).fill(Math.max(1, Math.floor(totalCs / n)));
    }
  } else {
    // Character-length weighted distribution for natural speech pacing
    const lengths = words.map((w) => Math.max(1, w.length));
    const totalLen = lengths.reduce((acc, l) => acc + l, 0);
    alloc = lengths.map((l) => Math.max(1, Math.round(totalCs * (l / totalLen))));
  }

  // Adjust rounding discrepancy on largest allocation to preserve exact cue duration
  const currentSum = alloc.reduce((acc, v) => acc + v, 0);
  const diff = totalCs - currentSum;
  let maxIdx = 0;
  for (let i = 1; i < n; i++) {
    if (alloc[i] > alloc[maxIdx]) maxIdx = i;
  }
  alloc[maxIdx] = Math.max(1, alloc[maxIdx] + diff);

  return words.map((w, idx) => ({ word: w, duration_cs: alloc[idx] }));
}

/**
 * Generates an ASS v4.00+ subtitle file string matching the selected preset styling.
 * Ready to be written into MEMFS for @ffmpeg/ffmpeg WASM or sent to backend.
 */
export function generateAssSubtitleContent(
  cues: SubtitleCue[],
  style: SubtitleStyle,
  options: AssGenerationOptions = {}
): string {
  if (style === 'none' || cues.length === 0) {
    return '';
  }

  const preset = getTextPreset(style);
  const cfg = preset.assConfig;
  const activeFontName = options.fontName?.trim() || cfg.fontName;
  const width = options.width || 720;
  const height = options.height || 1280;
  const fontsize = Math.max(26, Math.round(height * 0.046));
  const marginV = options.marginV || Math.round(height * 0.16);

  const styleNorm = (style || 'karaoke').trim().toLowerCase();
  const isSmoothSweep = [
    'hormozi',
    'karaoke',
    'karaoke_bounce',
    'tiktok_punch',
    'nas_daily',
    'hormozi_emerald',
    'ali_abdaal',
    'dan_koe',
    'matrix_hacker',
    'ali_cyan',
    'vox_cinema',
  ].includes(styleNorm);

  const isDiscreteJump = [
    'mrbeast',
    'kinetic',
    'comic_pow',
    'retro_synth',
    'gaming_rage',
    'fire_flame',
    'mrbeast_yellow',
    'hormozi_fire',
  ].includes(styleNorm);

  const header = `[Script Info]
Title: Reef Clipper Subtitles - ${preset.name}
ScriptType: v4.00+
PlayResX: ${width}
PlayResY: ${height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,${activeFontName},${fontsize},${cfg.primaryColour},${cfg.secondaryColour},${cfg.outlineColour},${cfg.backColour},${cfg.bold ? -1 : 0},${cfg.italic ? -1 : 0},0,0,100,100,${cfg.spacing},0,${cfg.borderStyle},${cfg.outline},${cfg.shadow},2,20,20,${marginV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;

  const dialogues = cues.map((cue) => {
    const tStart = formatAssTime(cue.start);
    const tEnd = formatAssTime(cue.end);
    const cueDur = Math.max(0.05, cue.end - cue.start);
    let rawText = cue.text.trim();
    if (cfg.uppercase) {
      rawText = rawText.toUpperCase();
    }
    const wordsList = rawText.split(/\s+/).filter(Boolean);

    if (wordsList.length === 0) {
      return `Dialogue: 0,${tStart},${tEnd},Default,,0,0,0,,`;
    }

    const wordTimings = computeWordCentiseconds(wordsList, cueDur, cue.words);

    let dialogueText: string;
    if (isSmoothSweep) {
      dialogueText = wordTimings
        .map((w) => `{\\kf${w.duration_cs}}${w.word}`)
        .join(' ');
    } else if (isDiscreteJump) {
      dialogueText = wordTimings
        .map((w) => `{\\k${w.duration_cs}}${w.word}`)
        .join(' ');
    } else {
      dialogueText = rawText;
    }

    return `Dialogue: 0,${tStart},${tEnd},Default,,0,0,0,,${dialogueText}`;
  });

  return header + dialogues.join('\n') + '\n';
}

/**
 * Creates a Blob Object URL for the ASS file.
 * Returns the URL along with an explicit cleanup/revoke callback for memory safety.
 */
export function createAssBlobUrl(
  cues: SubtitleCue[],
  style: SubtitleStyle,
  options?: AssGenerationOptions
): { url: string; revoke: () => void } | null {
  const content = generateAssSubtitleContent(cues, style, options);
  if (!content) return null;

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);

  return {
    url,
    revoke: () => {
      URL.revokeObjectURL(url);
    },
  };
}
