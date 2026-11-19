# Reef Clipper — Landing Page Design System ("Editing Bay")

> Promotional landing page for Reef Clipper Studio. Built from three SuperDesign library styles,
> fused under one metaphor — **a dark editing bay at night**: the room is dark (Cinematic), the
> machines speak in timecode (Kinetic), and the cuts are calm and precise (Editorial). Each source
> has exactly one job, so the page reads as one voice, not a collage.
>
> | SuperDesign slug | Job on the page | Taken | Dropped |
> |---|---|---|---|
> | `cinematic-style` | **The room** — base mood & depth | `#0A0A0F` near-black, glass cards with 1px white/10 borders, large tight display type, violet glow, cyan→pink gradient CTA, pulsing red "live" dot, mix-blend-difference nav, window-chrome media frames, bento grid | 3D rolodex cube, white pricing card |
> | `kinetic-orange-style` | **The timecode** — data voice & energy | Monospace data voice (source uses Space Mono → here JetBrains Mono), giant marquee band, numbered `[01]` step list with hover arrow, rotating circular "scroll" badge, Archivo Black (used as the subtitle face) | Orange color, skewed sections, 2px black borders |
> | `bold-editorial-studio-style` | **The cut** — rhythm & motion | Expo-out easing, line-by-line slide-up text reveals, grayscale→color media on hover, asymmetric-radius marquee cards, spacious section rhythm, 1px-max borders | White background, strict B&W, custom cursor |
>
> Rejected: `neural-noir-interface-style` (gold + serif would fight the violet/cyan brand).

---

## 1. Product & page goal

- **Product**: Reef Clipper Studio — paste a YouTube link or upload a long video; AI finds the
  viral moments, auto-frames faces to 9:16, burns TikTok-style subtitles, and exports shorts for
  TikTok / Reels / Shorts.
- **Audience**: Indonesian content creators, clippers, podcasters, social media admins. Mostly
  arriving on mobile from social posts.
- **Page goal (one CTA)**: "Coba gratis" / "Mulai clipping" → opens the Studio. Secondary: watch
  demo.
- **Promise to communicate in 5 seconds**: *1 video panjang → banyak short siap viral, otomatis,
  lengkap dengan subtitle.*
- **Language**: Bahasa Indonesia, casual-confident tone (creator slang ok: "FYP", "hook",
  "clip"). Short, punchy lines.

## 2. Color

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0A0A0F` | Page background (whole page stays dark) |
| `--bg-deep` | `#0B0216` | Alternate section (CTA / pricing) with central violet glow |
| `--card` | `rgba(21,21,32,0.65)` + `backdrop-filter: blur(8px)` | Glass cards |
| `--muted` | `#1E1E2D` | Tracks, chips, placeholders |
| `--border` | `rgba(255,255,255,0.08)` → hover `0.16` | All borders, 1px |
| `--fg` | `#F8FAFC` | Text |
| `--fg-2` | `#94A3B8` | Secondary text, labels |
| `--violet` | `#8B5CF6` | Glow, highlighted words, selected states |
| `--cyan` | `#22D3EE` | Timeline playhead, small accents |
| `--pink` | `#F472B6` | Score badges, highlighted words |
| `--gradient` | `linear-gradient(90deg,#22D3EE,#F472B6)` | **Only** primary CTA buttons, progress bars, one hero word |
| `--glow` | radial `rgba(139,92,246,0.25)`, blur 100px | Behind hero phone and final CTA only |
| `--live` | `#EF4444` | Pulsing dot ("LIVE", "AI sedang clipping") |
| Subtitle yellow | `#FDE047` | Only inside subtitle demos (active word) |

Rules: video/thumbnail imagery is the main color source; UI stays monochrome + violet. Max one
gradient element per viewport. No orange, gold, neon green, or drop shadows.

## 3. Typography

| Role | Font | Spec |
|---|---|---|
Preset: **"Editorial serif"** — a tight neo-grotesk headline with one italic serif word per
headline. The contrast (precise sans vs. soft italic serif) is the page's signature.

| Role | Font | Spec |
|---|---|---|
| Display (hero, section titles, stats, prices) | `Inter Tight` 600 | **Sentence case** (not uppercase), letter-spacing -0.055em, line-height 0.9. Hero `clamp(3rem, 7.4vw, 8.5rem)`; section titles `clamp(2.25rem, 6vw, 6rem)` |
| Accent word (inside display) | `Instrument Serif` Italic 400 | Exactly 1 word (max 2) per headline, letter-spacing -0.02em, filled with `--gradient` (text-clip) or `--violet`. Add `padding-right: .06em` so the italic isn't clipped |
| Body | `Inter` 400/500 | 16–18px, line-height 1.6, max 60ch |
| Buttons | `Inter` 700 | UPPERCASE, letter-spacing 0.1em, 13–15px |
| Labels / metadata / numbers | `JetBrains Mono` 400/700 | 11–13px, UPPERCASE, letter-spacing 0.2em, `tabular-nums` (timecodes `00:42`, step numbers `[01]`, badges `VIRAL 92`) |
| Subtitle demos | `Archivo Black` | UPPERCASE, white fill, 6–8px black stroke (`paint-order: stroke fill`), active word `#FDE047` |
| Logo wordmark | `Inter Tight` 600 | "Reef Clipper", sentence case, -0.03em |

Serif is allowed ONLY as the italic accent word inside a display headline — never for body,
labels, buttons or whole headlines. Never more than these five families. Accent words carry the
color; the rest of the headline stays `--fg`.

Google Fonts: `Inter Tight:wght@500;600;700`, `Instrument Serif:ital@0;1`,
`Inter:wght@400;500;600;700`, `JetBrains Mono:wght@400;700`, `Archivo Black`.

Relation to the Studio app (`design.md`, headline font Sora): the landing uses its own editorial
type voice for promotion, while sharing the exact same colors, dark base and mono-for-numbers rule,
so moving from landing → app still feels like one product.

## 4. Layout & spacing

- Container max-width 90rem, side padding 24px (mobile 16px). Section padding 120px desktop /
  72px mobile. Mobile-first, `min-h-dvh` hero.
- Radius: 12px cards, 20px media, 9999px pills/buttons. Editorial exception: marquee cards use
  asymmetric radius (`border-top-left-radius:100px` / `border-top-right-radius:100px;
  border-bottom-left-radius:40px` / `40px` all), alternating.
- Grid: 12-col desktop; bento uses 3 cols × 2 rows; collapses to 1 col under 768px.

## 5. Page structure (top → bottom)

1. **Nav** — fixed, `mix-blend-mode: difference`, 24px padding. Left: logo "Reef Clipper" (Inter
   Tight 600) + pulsing red dot. Center (desktop): Fitur · Cara kerja · Harga · FAQ in JetBrains Mono 12px.
   Right: gradient pill "Coba gratis".
2. **Hero** — 100dvh, dark with violet glow. Left: JetBrains Mono eyebrow `AI CLIPPER · 9:16 · AUTO
   SUBTITLE`; giant headline e.g. "Satu video. *Sepuluh* short siap viral." ("Sepuluh" = Instrument Serif Italic with gradient);
   sub line in Inter; CTA row: gradient pill "Mulai clipping" + glass pill "Lihat demo ▶".
   Right: a 9:16 phone/player in a glass window-chrome frame (3 dots + mono title
   `SHORT_01 · 00:42`) playing a clip with a burned-in Archivo Black subtitle; a floating glass
   "LIVE" pill (`● AI sedang clipping… 72%`) and a floating score badge (`VIRAL 92`). Bottom
   center: rotating circular "SCROLL ↓" badge (JetBrains Mono, 12s spin).
3. **Marquee band** — full-width, two rows of display text at 10vw: row 1 `PASTE · CLIP · CAPTION ·
   POST ·` in white at 12% opacity, row 2 reverse direction with outlined text
   (`-webkit-text-stroke:1px rgba(255,255,255,.3)`, transparent fill). 30s linear, pauses on hover.
4. **Before → After** — "1 video 2 jam" (wide 16:9 glass frame with a long timeline strip) →
   arrow → a fanned row of 3–5 vertical 9:16 short cards. Mono captions: `INPUT 02:13:40` →
   `OUTPUT 8 KLIP · 00:15–00:59`.
5. **Cara kerja (numbered list, Kinetic)** — full-width rows separated by 1px borders: `[01]`
   (JetBrains Mono, violet) → title in display 5vw ("Tempel link", "AI cari momen", "Edit & export")
   → pill tags (`YouTube`, `Upload`, `Whisper`, `Face tracking`…). Hover: title shifts +16px, ↗
   arrow fades in and rotates 45°.
6. **Fitur bento (Cinematic)** — 3×2 glass grid: big tile "AI Highlight Detection" (clip list with
   viral scores), tile "Auto framing 9:16" (face-tracking box over a frame), tile "Subtitle gaya
   TikTok" (live subtitle preview with style chips), tile "Silence cutter", tile "Trimmer
   presisi" (timeline with in/out timecodes), tile "Riwayat sesi". Each tile: JetBrains Mono label top-
   left, title Inter 600 20px, one line body.
7. **Subtitle showcase** — horizontal marquee of 9:16 cards (asymmetric radius, grayscale →
   color on hover), each showing a different subtitle preset (Karaoke glow, Kuning bold, Minimal,
   Pop highlight) labelled in JetBrains Mono.
8. **Stats strip** — 3–4 numbers in Inter Tight 600 (e.g. `10×` lebih cepat, `9:16` otomatis, `0`
   editing manual), labels in JetBrains Mono. Separated by 1px vertical borders.
9. **Harga** — `--bg-deep` section with central violet glow. 3 glass cards; middle "Pro" card
   scaled 1.05 with 1px violet/40 border and mono badge `PALING LARIS`. Prices Inter Tight 600 48px.
   Monthly/annual pill toggle.
10. **FAQ** — accordion rows with 1px borders, `+` icon rotates to `×`, question Inter 500 18px.
11. **Final CTA** — huge display line "Siap *FYP*?" (14vw, "FYP" in Instrument Serif Italic gradient), gradient pill CTA scaled up on hover,
    glow behind.
12. **Footer** — 4 columns, logo + short bio, Produk, Sosial, Kontak; bottom bar 1px border with
    copyright in JetBrains Mono 12px.

## 6. Signature components

- **Glass window frame**: 1px border, blur(8px), top bar with three 10px dots (#FF5F57, #FEBC2E,
  #28C840) and a JetBrains Mono title on the right.
- **Live pill**: glass pill, 8px red pulsing dot + `LIVE` (JetBrains Mono 10px bold) + status text.
- **Score badge**: pill, 1px border, JetBrains Mono 11px `VIRAL 92` in `--pink`.
- **Primary CTA**: pill 48–56px tall, gradient fill, `#0A0A0F` text, Inter 700 uppercase
  tracking 0.1em, hover scale 1.02. Secondary: glass pill with 1px border.
- **Subtitle chip**: Archivo Black uppercase with black stroke over a video frame.

## 7. Motion

- Easing everywhere: `cubic-bezier(0.16, 1, 0.3, 1)`. Hovers 300–500ms, media 700ms.
- Headlines: each line slides up from `translateY(100%)` inside an overflow-hidden mask, 80ms
  stagger, on scroll into view.
- Media: grayscale(1) → grayscale(0) + scale(1.03) on hover.
- Marquees: linear 30s infinite, pause on hover. Scroll badge: 12s linear rotation.
- Live dot: 1.6s pulse. Hero progress `72%` fills once on load.
- `prefers-reduced-motion`: stop marquees, rotation and reveals; keep fades.

## 8. Do / Don't

DO: keep it dark end to end · let video frames bring the color · use JetBrains Mono for every
number · one italic serif accent word per headline · one gradient per viewport · lots of
breathing room between sections.

DON'T: white/light sections · serif outside the accent word · uppercase display headlines ·
orange/gold/neon · drop shadows · borders over 1px
(except selected 2px violet bar) · custom cursor · stock "AI robot" imagery · more than one
primary CTA per section.

## 9. Fidelity line (append to every SuperDesign prompt)

"Use ONLY the fonts, colors, spacing, and component styles defined in this design system. Do not
introduce any fonts, colors, or visual styles not in it. Keep #0A0A0F dark background throughout,
Inter Tight 600 sentence-case display with exactly one Instrument Serif Italic accent word per
headline, Inter body, JetBrains Mono labels/numbers, Archivo Black only for subtitle demos, violet #8B5CF6 accents and the cyan→pink gradient only on the primary CTA."
