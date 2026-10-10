import { useState, useRef, useEffect, useCallback, type FC, type WheelEvent } from 'react';
import { Check, Sparkles, ChevronLeft, ChevronRight } from 'lucide-react';
import type { SubtitleStyle, TextPresetId } from '../types';
import { TEXT_PRESETS, normalizePresetId, type TextPresetDefinition } from '../lib/textPresets';

export interface VisualPresetPickerProps {
  selectedStyle: SubtitleStyle;
  onSelectPreset: (style: SubtitleStyle) => void;
  showDisableOption?: boolean;
  className?: string;
  compact?: boolean;
  hideHeader?: boolean;
}

type CategoryFilter = 'all' | 'viral' | 'podcast' | 'aesthetic' | 'gaming' | 'bold';

const CATEGORIES: { id: CategoryFilter; label: string }[] = [
  { id: 'all', label: 'Semua (26)' },
  { id: 'viral', label: '🔥 Viral Shorts' },
  { id: 'podcast', label: '🎙️ Podcast & Vox' },
  { id: 'aesthetic', label: '✨ Aesthetic' },
  { id: 'gaming', label: '🎮 Gaming & Comic' },
  { id: 'bold', label: '⚡ Ultra Bold' },
];

function renderPresetThumbnail(preset: TextPresetDefinition) {
  switch (preset.id) {
    case 'hormozi':
      return (
        <div className="relative z-10 flex flex-col items-center justify-center leading-none text-center">
          <span className="font-montserrat font-black uppercase tracking-wider text-[#FFE600] stroke-hormozi text-sm sm:text-base">
            {preset.sampleWords[0]}
          </span>
          <span className="font-montserrat font-black uppercase tracking-wider text-white stroke-hormozi text-xs sm:text-sm mt-0.5">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'tiktok_punch':
      return (
        <div className="relative z-10 flex flex-col items-center justify-center leading-none text-center">
          <span className="font-the-bold uppercase tracking-wider text-[#FFE600] stroke-hormozi text-sm sm:text-base">
            {preset.sampleWords[0]}
          </span>
          <span className="font-the-bold uppercase tracking-wider text-white stroke-hormozi text-xs sm:text-sm mt-0.5">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'devon_bold':
      return (
        <div className="relative z-10 text-center leading-none">
          <span className="font-anton uppercase tracking-tight text-white stroke-hormozi text-base sm:text-lg">
            {preset.sampleWords[0]}
          </span>
          <span className="block font-anton uppercase text-[#FFFF00] stroke-hormozi text-sm mt-0.5">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'vox_box':
      return (
        <div className="relative z-10 max-w-[95%]">
          <div className="bg-black/90 border border-white/20 px-2.5 py-1.5 rounded-md shadow-lg text-center">
            <p className="font-inter font-semibold text-white text-xs sm:text-[13px] leading-tight">
              {preset.sampleWords[0]}
            </p>
          </div>
        </div>
      );

    case 'ali_abdaal':
      return (
        <div className="relative z-10 flex items-center gap-1 font-poppins text-center">
          <span className="text-white font-bold text-xs drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]">
            {preset.sampleWords[0]}
          </span>
          <span className="bg-[#FEF08A] text-zinc-950 font-black text-[11px] px-1.5 py-0.5 rounded shadow-sm">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'aesthetic':
      return (
        <div className="relative z-10 text-center px-1">
          <span className="font-bebas uppercase tracking-[0.26em] text-white shadow-cinema text-sm sm:text-base leading-none">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'mrbeast':
      return (
        <div className="relative z-10 rotate-[-3deg] text-center">
          <span className="font-bangers italic uppercase tracking-wider text-[#00F0FF] stroke-mrbeast text-base sm:text-lg leading-none">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'karaoke_bounce':
      return (
        <div className="relative z-10 text-center">
          <span className="font-montserrat font-black uppercase text-amber-300 stroke-hormozi text-xs sm:text-sm">
            {preset.sampleWords[0]}
          </span>
          <span className="block font-montserrat font-bold uppercase text-cyan-300 stroke-hormozi text-[11px]">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'cyber_neon':
      return (
        <div className="relative z-10 text-center">
          <span className="font-oswald uppercase tracking-wider text-[#FF00FF] stroke-cyber-neon text-sm sm:text-base leading-none">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'retro_synth':
      return (
        <div className="relative z-10 rotate-[-1deg] text-center">
          <span className="font-bangers uppercase tracking-wider text-[#FFAA00] stroke-hormozi text-sm sm:text-base leading-none">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'luxury_gold':
      return (
        <div className="relative z-10 text-center px-1">
          <span className="font-bebas uppercase tracking-[0.18em] text-[#FEE68A] shadow-luxury-gold text-sm sm:text-base leading-none font-bold">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'gaming_rage':
      return (
        <div className="relative z-10 italic rotate-[-2deg] text-center">
          <span className="font-anton uppercase tracking-wider text-[#FF2222] stroke-fire-glow text-base sm:text-lg leading-none">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'clean_bottom_bar':
      return (
        <div className="relative z-10 w-full px-1">
          <div className="bg-black/95 py-1 px-1 border-y border-amber-400 text-center">
            <span className="font-inter font-bold uppercase text-amber-400 text-[11px] tracking-wider">
              {preset.sampleWords[0]}
            </span>
          </div>
        </div>
      );

    case 'comic_pow':
      return (
        <div className="relative z-10 rotate-[2deg] text-center">
          <span className="font-bangers uppercase text-[#FFFF00] stroke-mrbeast text-base sm:text-lg leading-none">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'nas_daily':
      return (
        <div className="relative z-10 max-w-[95%]">
          <div className="bg-[#E11D48] px-2.5 py-1 rounded-full shadow-lg border border-red-300/40 text-center">
            <p className="font-montserrat font-black text-white text-[11px] sm:text-xs uppercase tracking-tight leading-tight">
              {preset.sampleWords[0]}
            </p>
          </div>
        </div>
      );

    case 'netflix_sub':
      return (
        <div className="relative z-10 text-center px-1">
          <span className="font-inter font-bold text-[#FFE600] text-xs sm:text-sm drop-shadow-[0_2px_4px_rgba(0,0,0,0.95)]">
            {preset.sampleWords[0]}
          </span>
          <span className="block font-inter font-semibold text-white text-[11px] mt-0.5 drop-shadow-[0_2px_4px_rgba(0,0,0,0.95)]">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'matrix_hacker':
      return (
        <div className="relative z-10 max-w-[95%]">
          <div className="bg-emerald-950/90 border border-emerald-500/60 px-2 py-1 rounded shadow-md text-center">
            <p className="font-mono font-bold text-[#00FF66] text-[11px] uppercase tracking-widest leading-none drop-shadow-[0_0_8px_rgba(0,255,102,0.8)]">
              {preset.sampleWords[0]}
            </p>
          </div>
        </div>
      );

    case 'dan_koe':
      return (
        <div className="relative z-10 max-w-[95%]">
          <div className="bg-zinc-900/90 border border-zinc-700/60 px-2.5 py-1.5 rounded-lg shadow-md text-center">
            <p className="font-inter font-medium text-zinc-100 text-xs leading-tight">
              {preset.sampleWords[0]}
            </p>
          </div>
        </div>
      );

    case 'fire_flame':
      return (
        <div className="relative z-10 text-center leading-none">
          <span className="font-anton uppercase tracking-wider text-[#FF4500] stroke-fire-glow text-base sm:text-lg">
            {preset.sampleWords[0]}
          </span>
          <span className="block font-anton uppercase text-[#FFA500] stroke-fire-glow text-sm mt-0.5">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'pastel_vlog':
      return (
        <div className="relative z-10 text-center px-1">
          <span className="font-poppins font-bold text-[#E9D5FF] text-xs sm:text-sm drop-shadow-[0_2px_10px_rgba(168,85,247,0.7)]">
            {preset.sampleWords[0]}
          </span>
          <span className="block font-poppins text-white/90 text-[11px] mt-0.5 drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)]">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'brat_lime':
      return (
        <div className="relative z-10 flex flex-col items-center justify-center leading-none text-center">
          <span className="font-montserrat-black uppercase tracking-tight text-[#8ACE00] stroke-brat-lime text-sm sm:text-base">
            {preset.sampleWords[0]}
          </span>
          <span className="font-montserrat-black uppercase tracking-tight text-white stroke-brat-lime text-xs sm:text-sm mt-0.5">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    case 'dymo_tape':
      return (
        <div className="relative z-10 max-w-[95%]">
          <div className="bg-black/95 border-y-2 border-white/40 px-2.5 py-1 shadow-lg text-center -rotate-1">
            <span className="font-special-elite text-white text-[11px] sm:text-xs tracking-wider leading-none uppercase">
              {preset.sampleWords[0]}
            </span>
          </div>
        </div>
      );

    case 'luxury_serif':
      return (
        <div className="relative z-10 text-center px-1">
          <span className="font-cinzel uppercase tracking-[0.22em] text-[#FEF2DC] shadow-luxury-serif text-xs sm:text-sm leading-none font-bold">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'sticker_pop':
      return (
        <div className="relative z-10 rotate-[-2deg] text-center">
          <span className="font-rubik font-black uppercase text-[#FFFF00] stroke-sticker-pop text-base sm:text-lg leading-none">
            {preset.sampleWords[0]}
          </span>
        </div>
      );

    case 'amber_terminal':
      return (
        <div className="relative z-10 max-w-[95%]">
          <div className="bg-[#120800]/90 border border-amber-500/70 px-2 py-1 rounded shadow-md text-center">
            <p className="font-vt323 text-[#FF9F00] text-sm sm:text-base uppercase tracking-widest leading-none shadow-amber-crt">
              {preset.sampleWords[0]}
            </p>
          </div>
        </div>
      );

    case 'capcut_glow':
      return (
        <div className="relative z-10 text-center px-1">
          <span className="font-poppins font-black uppercase tracking-wide text-white glow-capcut-cyan text-xs sm:text-sm leading-none">
            {preset.sampleWords[0]}
          </span>
          <span className="block font-poppins font-bold uppercase text-[#00F5D4] text-[10px] mt-0.5 tracking-wider">
            {preset.sampleWords[1]}
          </span>
        </div>
      );

    default:
      return (
        <span className="font-bold text-white text-xs">
          {preset.sampleWords[0]}
        </span>
      );
  }
}

export const VisualPresetPicker: FC<VisualPresetPickerProps> = ({
  selectedStyle,
  onSelectPreset,
  showDisableOption = true,
  className = '',
  compact = false,
  hideHeader = false,
}) => {
  const isNone = selectedStyle === 'none';
  const activePresetId: TextPresetId = normalizePresetId(selectedStyle);
  const [activeTab, setActiveTab] = useState<CategoryFilter>('all');
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const filteredPresets =
    activeTab === 'all'
      ? TEXT_PRESETS
      : TEXT_PRESETS.filter((p) => p.category === activeTab);

  const checkScrollState = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const { scrollLeft, scrollWidth, clientWidth } = el;
    setCanScrollLeft(scrollLeft > 6);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 6);
  }, []);

  useEffect(() => {
    checkScrollState();
    const handleResize = () => checkScrollState();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [checkScrollState, filteredPresets]);

  // Auto-scroll to selected preset on mount or style change
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el || isNone) return;
    const activeBtn = el.querySelector(`[data-preset-id="${activePresetId}"]`) as HTMLElement | null;
    if (activeBtn) {
      activeBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  }, [activePresetId, isNone]);

  const handleScrollBy = (direction: 'left' | 'right') => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const scrollAmount = el.clientWidth * 0.75;
    el.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    });
  };

  const handleWheel = (e: WheelEvent<HTMLDivElement>) => {
    // If vertical scroll wheel over horizontal list, scroll sideways smoothly
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({
        left: e.deltaY * 0.9,
      });
    }
  };

  return (
    <div className={`space-y-2.5 ${className}`}>
      {/* Header bar */}
      {!hideHeader && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs sm:text-sm">
          <div className="flex items-center gap-2 font-semibold text-zinc-200">
            <Sparkles className="w-4 h-4 text-violet-400" />
            <span>Preset Visual Subtitle (20 Gaya Unik & Swipeable)</span>
          </div>

          {showDisableOption && (
            <button
              type="button"
              onClick={() => onSelectPreset(isNone ? 'hormozi' : 'none')}
              className={`min-h-[32px] px-3 py-1 rounded-lg text-xs font-mono transition-colors cursor-pointer border ${
                isNone
                  ? 'bg-rose-950/40 border-rose-800/80 text-rose-300 font-bold'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
              }`}
            >
              {isNone ? '✕ Subtitle Nonaktif' : 'Nonaktifkan'}
            </button>
          )}
        </div>
      )}

      {/* Category Pills Bar */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => {
              setActiveTab(cat.id);
              setTimeout(checkScrollState, 50);
            }}
            className={`px-3 py-1.5 rounded-lg whitespace-nowrap font-medium transition-all cursor-pointer ${
              activeTab === cat.id
                ? 'bg-violet-600 text-white shadow-sm'
                : 'bg-zinc-900 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 border border-zinc-800/60'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* 1-Baris Scrollable Presets Track (Swipeable / Slider) */}
      <div className="relative group/carousel">
        {/* Left Scroll Arrow */}
        {canScrollLeft && (
          <button
            type="button"
            onClick={() => handleScrollBy('left')}
            aria-label="Geser preset ke kiri"
            className="absolute left-1 top-1/2 -translate-y-1/2 z-30 p-2 rounded-full bg-zinc-950/90 hover:bg-zinc-850 text-zinc-200 border border-zinc-700/80 shadow-2xl backdrop-blur transition-all duration-150 cursor-pointer hover:scale-110 active:scale-95"
          >
            <ChevronLeft className="w-4 h-4 stroke-[2.5]" />
          </button>
        )}

        {/* Horizontal 1-Row Container */}
        <div
          ref={scrollContainerRef}
          role="radiogroup"
          aria-label="Pilih Gaya Subtitle Visual"
          onScroll={checkScrollState}
          onWheel={handleWheel}
          className="flex flex-row items-stretch gap-3 overflow-x-auto pb-2.5 pt-1 px-1 scroll-smooth no-scrollbar snap-x snap-mandatory"
        >
          {filteredPresets.map((preset) => {
            const isActive = !isNone && activePresetId === preset.id;

            return (
              <button
                key={preset.id}
                data-preset-id={preset.id}
                type="button"
                role="radio"
                aria-checked={isActive}
                onClick={() => onSelectPreset(preset.id)}
                className={`group/card relative flex flex-col justify-between p-3 rounded-xl border text-left transition-all duration-200 cursor-pointer select-none w-[155px] sm:w-[170px] shrink-0 snap-start focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 min-h-[148px] sm:min-h-[158px] ${
                  isActive
                    ? 'bg-violet-950/50 border-violet-500 ring-2 ring-violet-500/80 shadow-[0_0_24px_rgba(139,92,246,0.3)]'
                    : 'bg-zinc-900/70 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/60 text-zinc-400'
                }`}
              >
                {/* Active Check Badge */}
                {isActive && (
                  <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-violet-500 text-white flex items-center justify-center shadow-md ring-2 ring-zinc-950 z-20">
                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                  </div>
                )}

                {/* Live CSS Thumbnail Stage */}
                <div
                  className={`w-full rounded-lg overflow-hidden flex items-center justify-center p-2 relative bg-gradient-to-b from-[#0c0c14] to-[#06060a] border border-zinc-800/80 ${
                    compact ? 'h-16' : 'h-18 sm:h-20'
                  }`}
                >
                  {/* Subtle vignette/grid overlay */}
                  <div
                    className="absolute inset-0 opacity-15 pointer-events-none"
                    style={{
                      backgroundImage:
                        'radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.2) 1px, transparent 0)',
                      backgroundSize: '12px 12px',
                    }}
                  />

                  {renderPresetThumbnail(preset)}
                </div>

                {/* Card Meta Footer */}
                <div className="pt-2">
                  <div className="flex items-center justify-between gap-1">
                    <span
                      className={`text-xs sm:text-sm font-bold truncate ${
                        isActive ? 'text-violet-200' : 'text-zinc-100'
                      }`}
                    >
                      {preset.name}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                    {preset.tagline}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Scroll Arrow */}
        {canScrollRight && (
          <button
            type="button"
            onClick={() => handleScrollBy('right')}
            aria-label="Geser preset ke kanan"
            className="absolute right-1 top-1/2 -translate-y-1/2 z-30 p-2 rounded-full bg-zinc-950/90 hover:bg-zinc-850 text-zinc-200 border border-zinc-700/80 shadow-2xl backdrop-blur transition-all duration-150 cursor-pointer hover:scale-110 active:scale-95"
          >
            <ChevronRight className="w-4 h-4 stroke-[2.5]" />
          </button>
        )}
      </div>
    </div>
  );
};
