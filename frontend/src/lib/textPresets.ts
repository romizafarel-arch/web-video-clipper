import type { TextPresetId, SubtitleStyle } from '../types';

export interface AssStyleConfig {
  fontName: string;
  bold: boolean;
  italic: boolean;
  primaryColour: string; // ASS format &HAABBGGRR
  secondaryColour: string;
  outlineColour: string;
  backColour: string;
  outline: number;
  shadow: number;
  spacing: number;
  borderStyle: number; // 1 = Outline + drop shadow, 3 = Opaque background box
  uppercase: boolean;
}

export interface TextPresetDefinition {
  id: TextPresetId;
  name: string;
  creator: string;
  tagline: string;
  description: string;
  category: 'viral' | 'podcast' | 'aesthetic' | 'gaming' | 'bold';
  sampleWords: [string, string];
  fontClass: string;
  fontName: string;
  assConfig: AssStyleConfig;
}

export const TEXT_PRESETS: TextPresetDefinition[] = [
  // 1. Alex Hormozi Classic
  {
    id: 'hormozi',
    name: 'Hormozi Classic',
    creator: 'Alex Hormozi',
    tagline: 'Neon Yellow Viral',
    description: 'Uppercase super tebal, kuning neon + putih, stroke hitam pekat 5px.',
    category: 'viral',
    sampleWords: ['SCALE', 'FASTER'],
    fontClass: 'font-montserrat font-black',
    fontName: 'Montserrat',
    assConfig: {
      fontName: 'Montserrat',
      bold: true,
      italic: false,
      primaryColour: '&H0000E6FF', // #FFE600 (BGR)
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&H80000000',
      outline: 5.0,
      shadow: 2.0,
      spacing: 0,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 2. TikTok Punch (The Bold Font)
  {
    id: 'tiktok_punch',
    name: 'TikTok Punch',
    creator: 'TikTok Viral',
    tagline: 'The Bold Font Pure Punch',
    description: 'Font ikonik TikTok Creator, outline hitam tebal, kontras maksimal.',
    category: 'viral',
    sampleWords: ['THIS IS', 'INSANE'],
    fontClass: 'font-the-bold uppercase',
    fontName: 'The Bold Font',
    assConfig: {
      fontName: 'The Bold Font',
      bold: true,
      italic: false,
      primaryColour: '&H00FFFFFF',
      secondaryColour: '&H0000E6FF',
      outlineColour: '&H00000000',
      backColour: '&H90000000',
      outline: 4.5,
      shadow: 2.0,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 3. Devon Bold Impact
  {
    id: 'devon_bold',
    name: 'Devon Impact',
    creator: 'Devon Crawford',
    tagline: 'Ultra Condensed Anton',
    description: 'Font Anton condensed tinggi, punchy di setiap kata kunci pendek.',
    category: 'bold',
    sampleWords: ['MASSIVE', 'RESULTS'],
    fontClass: 'font-anton uppercase',
    fontName: 'Anton',
    assConfig: {
      fontName: 'Anton',
      bold: true,
      italic: false,
      primaryColour: '&H0000FFFF', // Yellow/Gold
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&H90000000',
      outline: 4.0,
      shadow: 2.0,
      spacing: 0,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 4. Podcast Vox (Pill Box Badge)
  {
    id: 'vox_box',
    name: 'Podcast Vox',
    creator: 'Vox / DOAC',
    tagline: 'Clean Badge Pill',
    description: 'Sentence case rapi, background badge kotak hitam semi-transparan.',
    category: 'podcast',
    sampleWords: ['The untold truth', 'of focus'],
    fontClass: 'font-inter font-semibold',
    fontName: 'Inter',
    assConfig: {
      fontName: 'Inter',
      bold: true,
      italic: false,
      primaryColour: '&H00FFFFFF',
      secondaryColour: '&H00D4D4D8',
      outlineColour: '&H00000000',
      backColour: '&HCC000000', // ~80% black box
      outline: 2.0,
      shadow: 0,
      spacing: 0,
      borderStyle: 3,
      uppercase: false,
    },
  },

  // 5. Ali Abdaal Yellow Highlighter
  {
    id: 'ali_abdaal',
    name: 'Ali Abdaal',
    creator: 'Ali Abdaal',
    tagline: 'Highlighter Clean',
    description: 'Font modern, highlight kotak stabilo kuning cerah di kata aktif.',
    category: 'podcast',
    sampleWords: ['Deep Focus', 'Framework'],
    fontClass: 'font-poppins font-bold',
    fontName: 'Poppins',
    assConfig: {
      fontName: 'Poppins',
      bold: true,
      italic: false,
      primaryColour: '&H00FFFFFF',
      secondaryColour: '&H0000E6FF',
      outlineColour: '&H00000000',
      backColour: '&H60000000',
      outline: 2.5,
      shadow: 1.0,
      spacing: 0,
      borderStyle: 1,
      uppercase: false,
    },
  },

  // 6. Aesthetic Cinema White
  {
    id: 'aesthetic',
    name: 'Aesthetic Cinema',
    creator: 'Cinematic Minimal',
    tagline: 'Wide Kerning Film',
    description: 'All caps spasi lebar, putih bersih dengan soft Gaussian drop shadow.',
    category: 'aesthetic',
    sampleWords: ['SILENT', 'MOMENTS'],
    fontClass: 'font-bebas tracking-[0.24em]',
    fontName: 'Bebas Neue',
    assConfig: {
      fontName: 'Bebas Neue',
      bold: false,
      italic: false,
      primaryColour: '&H00FFFFFF',
      secondaryColour: '&H00E4E4E7',
      outlineColour: '&H0018181B',
      backColour: '&HA0000000',
      outline: 0.8,
      shadow: 2.5,
      spacing: 4,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 7. MrBeast Comic Pop Cyan
  {
    id: 'mrbeast',
    name: 'MrBeast Pop',
    creator: 'MrBeast',
    tagline: 'Comic Punch Cyan',
    description: 'Font komik miring tebal, double outline + bayangan pop magenta.',
    category: 'gaming',
    sampleWords: ['WIN 100K', 'CHALLENGE'],
    fontClass: 'font-bangers italic',
    fontName: 'Bangers',
    assConfig: {
      fontName: 'Bangers',
      bold: true,
      italic: true,
      primaryColour: '&H0000F0FF', // #00F0FF
      secondaryColour: '&H0000FFFF',
      outlineColour: '&H00000000',
      backColour: '&H00FF00EA', // Magenta hard shadow
      outline: 5.0,
      shadow: 3.5,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 8. Karaoke Bounce
  {
    id: 'karaoke_bounce',
    name: 'Karaoke Glow',
    creator: 'Opus Viral',
    tagline: 'Active Word Glowing',
    description: 'Word-by-word karaoke dengan warna aktif emas bersinar melompat.',
    category: 'viral',
    sampleWords: ['SING', 'ALONG'],
    fontClass: 'font-montserrat font-extrabold',
    fontName: 'Montserrat',
    assConfig: {
      fontName: 'Montserrat',
      bold: true,
      italic: false,
      primaryColour: '&H0022D3EE', // Bright Cyan
      secondaryColour: '&H0000FFFF', // Gold
      outlineColour: '&H00000000',
      backColour: '&H80000000',
      outline: 4.0,
      shadow: 2.0,
      spacing: 0,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 9. Cyber Neon Synthwave
  {
    id: 'cyber_neon',
    name: 'Cyber Neon',
    creator: 'Synthwave Studio',
    tagline: 'Purple & Magenta Glow',
    description: 'Gaya cyberpunk neon ungu-pink futuristik dengan glow pekat.',
    category: 'gaming',
    sampleWords: ['CYBER', 'FUTURE'],
    fontClass: 'font-oswald uppercase tracking-wider',
    fontName: 'Oswald',
    assConfig: {
      fontName: 'Oswald',
      bold: true,
      italic: false,
      primaryColour: '&H00FF00FF', // Magenta
      secondaryColour: '&H00FFAA00', // Cyan
      outlineColour: '&H002E0854', // Dark purple outline
      backColour: '&H00800080',
      outline: 4.0,
      shadow: 3.0,
      spacing: 2,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 10. Retro Synth 80s
  {
    id: 'retro_synth',
    name: 'Retro 80s',
    creator: 'Outrun Retro',
    tagline: 'Arcade Sun Yellow & Orange',
    description: 'Warna oranye-kuning matahari arcade retro 80-an klasik.',
    category: 'gaming',
    sampleWords: ['LEVEL UP', 'SCORE 999'],
    fontClass: 'font-bangers uppercase',
    fontName: 'Bangers',
    assConfig: {
      fontName: 'Bangers',
      bold: true,
      italic: false,
      primaryColour: '&H0000AAFF', // Orange
      secondaryColour: '&H0000FFFF', // Yellow
      outlineColour: '&H00000000',
      backColour: '&H00990099',
      outline: 4.5,
      shadow: 3.0,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 11. Luxury Gold
  {
    id: 'luxury_gold',
    name: 'Luxury Gold',
    creator: 'Iman Gadzhi / Luxury',
    tagline: 'Champagne Gold Clean',
    description: 'Font elegan warna emas sampanye, cocok untuk konten edukasi finansial/kekayaan.',
    category: 'aesthetic',
    sampleWords: ['WEALTH', 'MINDSET'],
    fontClass: 'font-bebas tracking-[0.2em]',
    fontName: 'Bebas Neue',
    assConfig: {
      fontName: 'Bebas Neue',
      bold: true,
      italic: false,
      primaryColour: '&H008AE6FE', // Champagne Gold
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H0018181B',
      backColour: '&H80000000',
      outline: 2.0,
      shadow: 2.5,
      spacing: 2,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 12. Gaming Rage Red
  {
    id: 'gaming_rage',
    name: 'Gaming Rage',
    creator: 'Streamer Clip',
    tagline: 'High Voltage Blood Red',
    description: 'Warna merah darah bold tebal dengan outline hitam tebal miring.',
    category: 'gaming',
    sampleWords: ['CLUTCH', '1V4 ACE'],
    fontClass: 'font-anton uppercase',
    fontName: 'Anton',
    assConfig: {
      fontName: 'Anton',
      bold: true,
      italic: true,
      primaryColour: '&H001E1EFF', // Bright Red
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&H90000000',
      outline: 5.0,
      shadow: 3.0,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 13. Clean Bottom Bar (News / Pro)
  {
    id: 'clean_bottom_bar',
    name: 'News Bar',
    creator: 'Broadcast Pro',
    tagline: 'White on Dark Bar',
    description: 'Teks rapi dengan bar latar belakang persegi panjang penuh ala TV news.',
    category: 'bold',
    sampleWords: ['BREAKING', 'UPDATE TODAY'],
    fontClass: 'font-inter font-bold uppercase',
    fontName: 'Inter',
    assConfig: {
      fontName: 'Inter',
      bold: true,
      italic: false,
      primaryColour: '&H00FFFFFF',
      secondaryColour: '&H00FACC15',
      outlineColour: '&H00000000',
      backColour: '&HF0000000', // Solid black box
      outline: 1.0,
      shadow: 0,
      spacing: 1,
      borderStyle: 3,
      uppercase: true,
    },
  },

  // 14. Comic POW
  {
    id: 'comic_pow',
    name: 'Comic POW',
    creator: 'Anime & Comic',
    tagline: 'Yellow Pop White Stroke',
    description: 'Font komik dengan stroke putih ganda dan bayangan pekat ceria.',
    category: 'bold',
    sampleWords: ['BOOM!', 'JACKPOT'],
    fontClass: 'font-bangers uppercase',
    fontName: 'Bangers',
    assConfig: {
      fontName: 'Bangers',
      bold: true,
      italic: false,
      primaryColour: '&H0000FFFF', // Yellow
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&H00FF3300', // Deep blue drop shadow
      outline: 4.5,
      shadow: 3.5,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 15. Nas Daily Tag (Red Pill Badge)
  {
    id: 'nas_daily',
    name: 'Nas Daily Tag',
    creator: 'Nas Daily',
    tagline: 'White on Crimson Pill',
    description: 'Huruf putih tebal di dalam pill badge merah khas video 1 menit viral.',
    category: 'viral',
    sampleWords: ["THAT'S 1 MINUTE", 'SEE YOU'],
    fontClass: 'font-montserrat font-black uppercase',
    fontName: 'Montserrat',
    assConfig: {
      fontName: 'Montserrat',
      bold: true,
      italic: false,
      primaryColour: '&H00FFFFFF',
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&HCC0000E6', // Solid Crimson Red pill box
      outline: 1.5,
      shadow: 0,
      spacing: 0.5,
      borderStyle: 3,
      uppercase: true,
    },
  },

  // 16. Cinema Classic (Netflix Yellow Subtitle)
  {
    id: 'netflix_sub',
    name: 'Cinema Classic',
    creator: 'Streaming Film',
    tagline: 'Gold Movie Yellow',
    description: 'Kuning subtitle klasik sinematik film dengan outline hitam halus & shadow lembut.',
    category: 'aesthetic',
    sampleWords: ['Everything changes', 'forever.'],
    fontClass: 'font-inter font-bold',
    fontName: 'Inter',
    assConfig: {
      fontName: 'Inter',
      bold: true,
      italic: false,
      primaryColour: '&H0000E6FF', // Cinema Yellow #FFE600
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&H90000000',
      outline: 2.2,
      shadow: 1.5,
      spacing: 0.5,
      borderStyle: 1,
      uppercase: false,
    },
  },

  // 17. Matrix Terminal (Phosphor Green Monospace)
  {
    id: 'matrix_hacker',
    name: 'Matrix Hacker',
    creator: 'Tech & Terminal',
    tagline: 'Phosphor Green Monospace',
    description: 'Teks hijau terminal hacker #00FF66 dengan monospace Space Mono & dark pill.',
    category: 'gaming',
    sampleWords: ['ACCESS', 'GRANTED'],
    fontClass: 'font-mono uppercase tracking-widest',
    fontName: 'Space Mono',
    assConfig: {
      fontName: 'Space Mono',
      bold: true,
      italic: false,
      primaryColour: '&H0066FF00', // Phosphor green #00FF66
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00003300',
      backColour: '&HE0051105', // Deep green-black box
      outline: 1.5,
      shadow: 0,
      spacing: 1.5,
      borderStyle: 3,
      uppercase: true,
    },
  },

  // 18. Dan Koe Minimal
  {
    id: 'dan_koe',
    name: 'Dan Koe Minimal',
    creator: 'Dan Koe / Modern Mind',
    tagline: 'Monochrome Philosophy',
    description: 'Teks monokrom elegan abu-abu/putih minimalis untuk konten filosofi & self-improvement.',
    category: 'podcast',
    sampleWords: ['Master your mind', 'or be mastered'],
    fontClass: 'font-inter font-medium tracking-tight',
    fontName: 'Inter',
    assConfig: {
      fontName: 'Inter',
      bold: true,
      italic: false,
      primaryColour: '&H00F4F4F5', // Crisp off-white
      secondaryColour: '&H00A1A1AA',
      outlineColour: '&H0018181B',
      backColour: '&HB018181B', // Translucent charcoal capsule
      outline: 1.2,
      shadow: 0,
      spacing: 0,
      borderStyle: 3,
      uppercase: false,
    },
  },

  // 19. Fire Flame (Gym & Beast Hype)
  {
    id: 'fire_flame',
    name: 'Fire Hype',
    creator: 'Beast Motivation',
    tagline: 'Flame Orange-Red Glow',
    description: 'Warna api membara gradasi oranye-merah dengan glow panas, cocok buat gym/fitness.',
    category: 'bold',
    sampleWords: ['NEVER', 'GIVE UP'],
    fontClass: 'font-anton uppercase',
    fontName: 'Anton',
    assConfig: {
      fontName: 'Anton',
      bold: true,
      italic: false,
      primaryColour: '&H000066FF', // Flame Orange #FF6600
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&H000000FF', // Red back glow
      outline: 4.8,
      shadow: 3.5,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 20. Pastel Vlog (Soft Lavender Aesthetic)
  {
    id: 'pastel_vlog',
    name: 'Pastel Dream',
    creator: 'Aesthetic Vlog',
    tagline: 'Soft Lavender Glow',
    description: 'Warna ungu pastel lembut #E9D5FF dengan aura manis untuk daily vlog & reels.',
    category: 'aesthetic',
    sampleWords: ['a quiet day', 'in my life'],
    fontClass: 'font-poppins font-semibold',
    fontName: 'Poppins',
    assConfig: {
      fontName: 'Poppins',
      bold: true,
      italic: false,
      primaryColour: '&H00FFD5E9', // Lavender pastel #E9D5FF
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H002E1065', // Dark violet outline
      backColour: '&H807C3AED',
      outline: 2.2,
      shadow: 2.0,
      spacing: 0.5,
      borderStyle: 1,
      uppercase: false,
    },
  },

  // 21. Brat Acid Lime (Trend Gen Z & Streetwear)
  {
    id: 'brat_lime',
    name: 'Brat Acid Lime',
    creator: 'Brat Trend / Pop',
    tagline: 'Acid Lime Hyperpop',
    description: 'Warna hijau acid lime neon #8ACE00 khas Brat pop-culture, all-caps tebal dengan outline hitam tipis.',
    category: 'viral',
    sampleWords: ['BRAT', 'SUMMER'],
    fontClass: 'font-montserrat-black uppercase tracking-tight',
    fontName: 'Montserrat Black',
    assConfig: {
      fontName: 'Montserrat',
      bold: true,
      italic: false,
      primaryColour: '&H0000E68A', // Acid Lime #8AE600 (BGR)
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00000000',
      backColour: '&H90000000',
      outline: 3.2,
      shadow: 1.5,
      spacing: 0,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 22. Dymo Tape Docu (Johnny Harris / MagnatesMedia)
  {
    id: 'dymo_tape',
    name: 'Dymo Tape Docu',
    creator: 'Johnny Harris / Docu',
    tagline: 'Embossed Typewriter Label',
    description: 'Font mesin tik Dymo di atas label tape hitam tebal, cocok untuk video dokumenter rahasia & investigasi.',
    category: 'podcast',
    sampleWords: ['CLASSIFIED', 'DOSSIER'],
    fontClass: 'font-special-elite uppercase tracking-wider',
    fontName: 'Special Elite',
    assConfig: {
      fontName: 'Special Elite',
      bold: true,
      italic: false,
      primaryColour: '&H00F0F0F0', // Clean tape white
      secondaryColour: '&H0000E6FF',
      outlineColour: '&H00101010',
      backColour: '&HF50A0A0A', // Opaque black tape box
      outline: 2.0,
      shadow: 0,
      spacing: 2,
      borderStyle: 3,
      uppercase: true,
    },
  },

  // 23. Editorial Luxury Serif (Sam Kolder / Vogue Reels)
  {
    id: 'luxury_serif',
    name: 'Editorial Serif',
    creator: 'Sam Kolder / Vogue',
    tagline: 'Cinematic Golden Serif',
    description: 'Font serif sinematik elegan spasi lebar dengan warna emas mutiara & soft ambient glow.',
    category: 'aesthetic',
    sampleWords: ['ETERNAL', 'JOURNEY'],
    fontClass: 'font-cinzel uppercase tracking-[0.28em]',
    fontName: 'Cinzel',
    assConfig: {
      fontName: 'Cinzel',
      bold: true,
      italic: false,
      primaryColour: '&H00DCF2FE', // Pearl Gold Ivory #FEF2DC (BGR)
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H0018181B',
      backColour: '&H70000000',
      outline: 1.2,
      shadow: 2.2,
      spacing: 4,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 24. 3-Layer Sticker Pop (Finzar / Y2K Editor Cutout)
  {
    id: 'sticker_pop',
    name: 'Sticker Pop',
    creator: 'Finzar / Y2K Cutout',
    tagline: 'Die-Cut Sticker Punch',
    description: 'Gaya stiker cut-out dengan inner stroke putih tebal & outer drop shadow offset untuk vlog & editing seru.',
    category: 'bold',
    sampleWords: ['POP!', 'STICKER'],
    fontClass: 'font-rubik font-black uppercase tracking-tight',
    fontName: 'Rubik',
    assConfig: {
      fontName: 'Rubik',
      bold: true,
      italic: false,
      primaryColour: '&H0000FFFF', // Yellow #FFFF00
      secondaryColour: '&H00FF00FF',
      outlineColour: '&H00000000',
      backColour: '&H00201005',
      outline: 5.5,
      shadow: 4.0,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },

  // 25. Bloomberg Amber Terminal (Luke Belmar / Money Twitter)
  {
    id: 'amber_terminal',
    name: 'Amber Terminal',
    creator: 'Luke Belmar / Alpha',
    tagline: 'CRT Retro Bloomberg',
    description: 'Monospace amber oranye #FF9F00 di atas capsule monitor retro untuk video crypto alpha & tech.',
    category: 'gaming',
    sampleWords: ['SYSTEM_ALPHA', 'ONLINE_24/7'],
    fontClass: 'font-vt323 uppercase tracking-widest text-base',
    fontName: 'VT323',
    assConfig: {
      fontName: 'VT323',
      bold: true,
      italic: false,
      primaryColour: '&H00009FFF', // CRT Amber #FF9F00 (BGR)
      secondaryColour: '&H00FFFFFF',
      outlineColour: '&H00003060',
      backColour: '&HE80A0502',
      outline: 1.5,
      shadow: 0,
      spacing: 1.5,
      borderStyle: 3,
      uppercase: true,
    },
  },

  // 26. CapCut Soft Glow Aura (Anime MV / Car Edits)
  {
    id: 'capcut_glow',
    name: 'CapCut Glow',
    creator: 'Anime & AMV Scene',
    tagline: 'Cyan Aura Outer Glow',
    description: 'Teks putih halus dengan aura glow cyan menyala diffused tanpa outline kasar, ala edit AMV & car aesthetic.',
    category: 'aesthetic',
    sampleWords: ['DRIFTING', 'INTO NIGHT'],
    fontClass: 'font-poppins font-black tracking-wide',
    fontName: 'Poppins',
    assConfig: {
      fontName: 'Poppins',
      bold: true,
      italic: false,
      primaryColour: '&H00FFFFFF',
      secondaryColour: '&H00F5F500', // Cyan highlight #00F5F5 (BGR)
      outlineColour: '&H00D4F500', // Cyan aura #00F5D4 (BGR)
      backColour: '&H60D4F500',
      outline: 3.2,
      shadow: 3.5,
      spacing: 1,
      borderStyle: 1,
      uppercase: true,
    },
  },
];

/**
 * Normalizes any subtitle style (including legacy values) to one of the 20 visual presets.
 */
export function normalizePresetId(style?: SubtitleStyle | null): TextPresetId {
  if (!style || style === 'none') return 'hormozi';
  if (style === 'karaoke') return 'karaoke_bounce';
  if (style === 'kinetic') return 'mrbeast';
  if (style === 'classic' || style === 'clean' || style === 'minimal') return 'vox_box';
  // Legacy aliases
  if (style === 'hormozi_emerald') return 'hormozi';
  if (style === 'hormozi_fire') return 'fire_flame';
  if (style === 'vox_cinema') return 'dan_koe';
  if (style === 'ali_cyan') return 'ali_abdaal';
  if (style === 'aesthetic_warm') return 'aesthetic';
  if (style === 'mrbeast_yellow') return 'mrbeast';
  const found = TEXT_PRESETS.find((p) => p.id === style);
  return found ? found.id : 'hormozi';
}

/**
 * Retrieves the definition for the specified preset or fallback to Hormozi.
 */
export function getTextPreset(style?: SubtitleStyle | null): TextPresetDefinition {
  const id = normalizePresetId(style);
  return TEXT_PRESETS.find((p) => p.id === id) ?? TEXT_PRESETS[0];
}
