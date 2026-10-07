import { useState, useRef, useEffect, type FC, type ChangeEvent } from 'react';
import { Type, Upload, Check, RefreshCw, AlertCircle } from 'lucide-react';
import type { FontItem } from '../types';
import {
  VIRAL_FONT_LIBRARY,
  findFontByFamily,
  registerCustomFontFace,
  loadPersistedCustomFonts,
  savePersistedCustomFonts,
} from '../lib/fontFamilyLibrary';
import { uploadCustomFont } from '../lib/api';

export interface FontFamilyPickerProps {
  selectedFont: string;
  onSelectFont: (fontFamily: string) => void;
  presetDefaultFont?: string;
  className?: string;
  compact?: boolean;
}

export const FontFamilyPicker: FC<FontFamilyPickerProps> = ({
  selectedFont,
  onSelectFont,
  presetDefaultFont,
  className = '',
  compact = false,
}) => {
  const [customFonts, setCustomFonts] = useState<FontItem[]>(() => loadPersistedCustomFonts());
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Re-register any persisted custom fonts into document.fonts on mount
  useEffect(() => {
    const loaded = loadPersistedCustomFonts();
    loaded.forEach((font) => {
      if (font.url) {
        void registerCustomFontFace(font.family, font.url);
      }
    });
  }, []);

  const allFonts: FontItem[] = [...VIRAL_FONT_LIBRARY, ...customFonts];
  const activeFontItem = findFontByFamily(selectedFont, customFonts);
  const isDefaultSelected = presetDefaultFont ? activeFontItem.family === presetDefaultFont : false;

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset input value so re-uploading same file triggers event
    e.target.value = '';

    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'ttf' && ext !== 'otf') {
      setUploadError('Format tidak didukung. Harap unggah file .ttf atau .otf.');
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setUploadError('Ukuran file font terlalu besar (maksimal 20MB).');
      return;
    }

    setUploadError(null);
    setIsUploading(true);

    try {
      // 1. Clean sanitized font name for client font-face
      const baseName = file.name.replace(/\.[^/.]+$/, '').trim();
      const sanitizedFamily = baseName.replace(/[^a-zA-Z0-9_-]/g, ' ') || 'CustomFont';

      // 2. Client-side instant registration via FontFace
      const arrayBuffer = await file.arrayBuffer();
      await registerCustomFontFace(sanitizedFamily, arrayBuffer);

      // 3. Upload to backend for FFmpeg local bundling
      let backendFamily = sanitizedFamily;
      let fontUrl: string | undefined = undefined;

      try {
        const res = await uploadCustomFont(file);
        if (res.success && res.family) {
          backendFamily = res.family;
          fontUrl = res.url;
        }
      } catch (backendErr) {
        console.warn('Gagal upload ke backend, menggunakan font lokal browser:', backendErr);
      }

      const newFontItem: FontItem = {
        id: `custom_${Date.now()}`,
        name: backendFamily,
        family: backendFamily,
        category: 'custom',
        tag: 'Custom Upload',
        sampleWord: 'CUSTOM',
        cssClass: 'font-bold uppercase tracking-wider',
        isCustom: true,
        fileName: file.name,
        url: fontUrl,
      };

      const updated = [newFontItem, ...customFonts.filter((f) => f.family !== backendFamily)];
      setCustomFonts(updated);
      savePersistedCustomFonts(updated);

      // Auto-select uploaded font
      onSelectFont(backendFamily);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Gagal memproses file font.';
      setUploadError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Header Bar */}
      <div className="flex items-center justify-between text-xs sm:text-sm">
        <div className="flex items-center gap-2 font-semibold text-zinc-200">
          <Type className="w-4 h-4 text-cyan-400" />
          <span>Font Family (Koleksi CapCut)</span>
          <span className="text-xs px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 font-mono">
            {activeFontItem.name}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {presetDefaultFont && !isDefaultSelected && (
            <button
              type="button"
              onClick={() => onSelectFont(presetDefaultFont)}
              className="min-h-[32px] px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer border border-zinc-700 bg-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-700 flex items-center gap-1.5"
              title={`Kembalikan ke font default preset: ${presetDefaultFont}`}
            >
              <RefreshCw className="w-3.5 h-3.5 text-violet-400" />
              <span>Reset Default</span>
            </button>
          )}

          {/* Upload Button */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".ttf,.otf"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            type="button"
            disabled={isUploading}
            onClick={() => fileInputRef.current?.click()}
            className="min-h-[32px] px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer border border-cyan-800/80 bg-cyan-950/40 text-cyan-300 hover:bg-cyan-900/60 hover:text-cyan-100 flex items-center gap-1.5 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>{isUploading ? 'Memuat...' : 'Upload Font'}</span>
          </button>
        </div>
      </div>

      {uploadError && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs sm:text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{uploadError}</span>
        </div>
      )}

      {/* Font Family Cards Grid */}
      <div
        role="radiogroup"
        aria-label="Pilih Jenis Huruf Subtitle"
        className={`grid gap-2.5 overflow-x-auto pb-1 ${
          compact
            ? 'grid-cols-2 sm:grid-cols-3 md:grid-cols-5'
            : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5'
        }`}
      >
        {allFonts.map((font) => {
          const isSelected = activeFontItem.family === font.family;
          const isPresetDefault = presetDefaultFont === font.family;

          return (
            <button
              key={font.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => onSelectFont(font.family)}
              className={`group relative flex flex-col justify-between p-3 rounded-xl border text-left transition-all duration-150 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                isSelected
                  ? 'bg-cyan-950/40 border-cyan-500 ring-2 ring-cyan-500/80 shadow-[0_0_20px_rgba(6,182,212,0.25)]'
                  : 'bg-zinc-900/70 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/60 text-zinc-400'
              } ${compact ? 'min-h-[104px]' : 'min-h-[118px]'}`}
            >
              {/* Selected Badge */}
              {isSelected && (
                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-cyan-500 text-zinc-950 flex items-center justify-center shadow-md ring-2 ring-zinc-950 z-20">
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                </div>
              )}

              {/* Live Typography Preview Stage */}
              <div
                className="w-full h-12 sm:h-14 rounded-lg bg-zinc-950/80 border border-zinc-800/80 flex items-center justify-center p-1.5 relative overflow-hidden"
              >
                <span
                  style={{ fontFamily: font.family }}
                  className={`text-zinc-100 text-base sm:text-lg truncate select-none leading-none drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] ${
                    font.cssClass
                  }`}
                >
                  {font.sampleWord}
                </span>
              </div>

              {/* Meta Label */}
              <div className="pt-2">
                <div className="flex items-center justify-between gap-1">
                  <span
                    className={`text-xs sm:text-sm font-semibold truncate ${
                      isSelected ? 'text-cyan-200' : 'text-zinc-200'
                    }`}
                  >
                    {font.name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="text-[11px] text-zinc-400 truncate">
                    {font.tag}
                  </span>
                  {isPresetDefault && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-950 text-violet-300 border border-violet-800/60">
                      Default
                    </span>
                  )}
                  {font.isCustom && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800/60">
                      Custom
                    </span>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
