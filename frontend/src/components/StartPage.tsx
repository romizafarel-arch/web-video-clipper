import type { FC } from 'react';
import { Clapperboard, Lightbulb } from 'lucide-react';

interface StartPageProps {
  onStartIdeas: () => void;
  onStartClipping: () => void;
}

export const StartPage: FC<StartPageProps> = ({ onStartIdeas, onStartClipping }) => (
  <section className="mx-auto w-full max-w-5xl py-8 sm:py-14">
    <div className="mb-7 sm:mb-9">
      <h1 className="font-headline text-2xl sm:text-3xl font-semibold text-white">Mulai dari mana?</h1>
      <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-400">
        Pilih yang sudah kamu punya. Nanti kamu bisa lanjut ke Studio kapan saja.
      </p>
    </div>

    <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
      <button
        type="button"
        onClick={onStartIdeas}
        className="group min-h-52 rounded-xl border border-zinc-700 bg-zinc-900/70 p-5 text-left transition-colors hover:border-violet-400/70 hover:bg-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 sm:min-h-60 sm:p-6"
      >
        <Lightbulb aria-hidden="true" className="mb-7 h-6 w-6 text-violet-300" />
        <span className="block font-headline text-lg font-semibold text-white">Aku punya ide</span>
        <span className="mt-2 block max-w-sm text-sm leading-6 text-zinc-400">
          Temukan arah cerita, susun naskah, dan dapatkan panduan adegan.
        </span>
        <span className="mt-5 block text-sm font-semibold text-violet-300 group-hover:text-white">Kembangkan ide</span>
      </button>

      <button
        type="button"
        onClick={onStartClipping}
        className="group min-h-52 rounded-xl border border-zinc-700 bg-zinc-900/70 p-5 text-left transition-colors hover:border-cyan-300/70 hover:bg-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 sm:min-h-60 sm:p-6"
      >
        <Clapperboard aria-hidden="true" className="mb-7 h-6 w-6 text-cyan-300" />
        <span className="block font-headline text-lg font-semibold text-white">Aku sudah punya video</span>
        <span className="mt-2 block max-w-sm text-sm leading-6 text-zinc-400">
          Potong video panjang menjadi klip pendek dan lanjutkan edit di Studio.
        </span>
        <span className="mt-5 block text-sm font-semibold text-cyan-300 group-hover:text-white">Potong video</span>
      </button>
    </div>
  </section>
);
