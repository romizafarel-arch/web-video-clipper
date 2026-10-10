import type { TextPresetId } from '../types';

export interface FontItem {
  id: string;
  name: string;
  family: string;
  category: 'viral' | 'sans' | 'display' | 'custom';
  tag: string;
  sampleWord: string;
  cssClass: string;
  isCustom?: boolean;
  fileName?: string;
  url?: string;
}

export const VIRAL_FONT_LIBRARY: FontItem[] = [
  {
    id: 'montserrat_black',
    name: 'Montserrat Black',
    family: 'Montserrat Black',
    category: 'viral',
    tag: 'Hormozi Viral',
    sampleWord: 'IMPACT',
    cssClass: 'font-montserrat-black uppercase tracking-wide',
  },
  {
    id: 'the_bold_font',
    name: 'The Bold Font',
    family: 'The Bold Font',
    category: 'viral',
    tag: 'TikTok Punch',
    sampleWord: 'ATTENTION',
    cssClass: 'font-the-bold uppercase tracking-wider',
  },
  {
    id: 'anton',
    name: 'Anton',
    family: 'Anton',
    category: 'viral',
    tag: 'High Energy',
    sampleWord: 'POWERFUL',
    cssClass: 'font-anton uppercase tracking-wider',
  },
  {
    id: 'bebas_neue',
    name: 'Bebas Neue',
    family: 'Bebas Neue',
    category: 'display',
    tag: 'Cinema Minimal',
    sampleWord: 'CINEMATIC',
    cssClass: 'font-bebas uppercase tracking-[0.2em]',
  },
  {
    id: 'bangers',
    name: 'Bangers',
    family: 'Bangers',
    category: 'display',
    tag: 'MrBeast Pop',
    sampleWord: 'CRAZY POP!',
    cssClass: 'font-bangers uppercase tracking-wider',
  },
  {
    id: 'poppins',
    name: 'Poppins Bold',
    family: 'Poppins',
    category: 'sans',
    tag: 'Ali Abdaal',
    sampleWord: 'Clarity Focus',
    cssClass: 'font-poppins font-bold',
  },
  {
    id: 'inter',
    name: 'Inter Semibold',
    family: 'Inter',
    category: 'sans',
    tag: 'Vox Documentary',
    sampleWord: 'Clean Vox',
    cssClass: 'font-inter font-bold',
  },
  {
    id: 'oswald',
    name: 'Oswald Bold',
    family: 'Oswald',
    category: 'viral',
    tag: 'Compact Punch',
    sampleWord: 'HEADLINE',
    cssClass: 'font-oswald font-bold uppercase tracking-wide',
  },
  {
    id: 'roboto',
    name: 'Roboto Bold',
    family: 'Roboto',
    category: 'sans',
    tag: 'Modern Neutral',
    sampleWord: 'Universal',
    cssClass: 'font-roboto font-bold',
  },
  {
    id: 'special_elite',
    name: 'Special Elite',
    family: 'Special Elite',
    category: 'display',
    tag: 'Dymo Docu Typewriter',
    sampleWord: 'CLASSIFIED',
    cssClass: 'font-special-elite uppercase tracking-wider',
  },
  {
    id: 'cinzel',
    name: 'Cinzel Serif',
    family: 'Cinzel',
    category: 'display',
    tag: 'Editorial Luxury',
    sampleWord: 'ETERNAL',
    cssClass: 'font-cinzel uppercase tracking-[0.2em]',
  },
  {
    id: 'vt323',
    name: 'VT323 Pixel CRT',
    family: 'VT323',
    category: 'display',
    tag: 'Bloomberg Terminal',
    sampleWord: 'ALPHA_24/7',
    cssClass: 'font-vt323 uppercase tracking-widest',
  },
  {
    id: 'rubik',
    name: 'Rubik Black',
    family: 'Rubik',
    category: 'viral',
    tag: 'Sticker Die-Cut',
    sampleWord: 'STICKER',
    cssClass: 'font-rubik font-black uppercase tracking-tight',
  },
];

/**
 * Maps default font family corresponding to each visual subtitle preset.
 */
export function getDefaultFontForPreset(presetId: TextPresetId): string {
  switch (presetId) {
    case 'hormozi':
    case 'hormozi_emerald':
    case 'karaoke_bounce':
    case 'nas_daily':
    case 'brat_lime':
      return 'Montserrat Black';
    case 'tiktok_punch':
      return 'The Bold Font';
    case 'devon_bold':
    case 'gaming_rage':
    case 'fire_flame':
    case 'hormozi_fire':
      return 'Anton';
    case 'vox_box':
    case 'vox_cinema':
    case 'clean_bottom_bar':
    case 'dan_koe':
      return 'Inter';
    case 'netflix_sub':
      return 'Roboto Bold';
    case 'ali_abdaal':
    case 'ali_cyan':
    case 'pastel_vlog':
    case 'capcut_glow':
      return 'Poppins';
    case 'aesthetic':
    case 'aesthetic_warm':
    case 'luxury_gold':
      return 'Bebas Neue';
    case 'luxury_serif':
      return 'Cinzel';
    case 'dymo_tape':
      return 'Special Elite';
    case 'sticker_pop':
      return 'Rubik';
    case 'amber_terminal':
      return 'VT323';
    case 'mrbeast':
    case 'mrbeast_yellow':
    case 'retro_synth':
    case 'comic_pow':
      return 'Bangers';
    case 'cyber_neon':
      return 'Oswald';
    case 'matrix_hacker':
      return 'Space Mono';
    default:
      return 'Montserrat Black';
  }
}

/**
 * Finds font item by font family name or id.
 */
export function findFontByFamily(familyOrId: string, customFonts: FontItem[] = []): FontItem {
  const normalized = (familyOrId || '').trim().toLowerCase();
  const allFonts = [...VIRAL_FONT_LIBRARY, ...customFonts];

  const matched = allFonts.find(
    (f) =>
      f.id.toLowerCase() === normalized ||
      f.family.toLowerCase() === normalized ||
      f.name.toLowerCase() === normalized
  );

  return matched || VIRAL_FONT_LIBRARY[0];
}

/**
 * Dynamically registers a custom FontFace in the browser DOM.
 */
export async function registerCustomFontFace(
  fontFamily: string,
  source: ArrayBuffer | Blob | string
): Promise<boolean> {
  if (typeof window === 'undefined' || !('fonts' in document)) {
    return false;
  }

  try {
    let fontSource: string | ArrayBuffer;
    if (source instanceof Blob) {
      fontSource = await source.arrayBuffer();
    } else {
      fontSource = source;
    }

    const face = new FontFace(
      fontFamily,
      typeof fontSource === 'string' ? `url(${fontSource})` : fontSource
    );
    const loaded = await face.load();
    document.fonts.add(loaded);
    return true;
  } catch (err) {
    console.warn(`[FontLibrary] Gagal mendaftarkan FontFace '${fontFamily}':`, err);
    return false;
  }
}

const LOCAL_CUSTOM_FONTS_KEY = 'shortsai_custom_fonts';

/**
 * Reads user-uploaded custom fonts metadata from localStorage.
 */
export function loadPersistedCustomFonts(): FontItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(LOCAL_CUSTOM_FONTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((f) => f && typeof f.family === 'string' && f.isCustom);
    }
  } catch {
    // Ignore parsing error
  }
  return [];
}

/**
 * Persists updated custom fonts metadata to localStorage.
 */
export function savePersistedCustomFonts(fonts: FontItem[]): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(LOCAL_CUSTOM_FONTS_KEY, JSON.stringify(fonts));
  } catch {
    // Ignore quota error
  }
}
