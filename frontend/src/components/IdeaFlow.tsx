import { useState, type FC, type FormEvent } from 'react';
import { ArrowLeft, Check, ClipboardCopy, RotateCcw } from 'lucide-react';
import type {
  AppConfig,
  IdeaGoal,
  IdeaTone,
  VideoIdeaDirection,
  VideoIdeaGuide,
  VideoIdeaPlan,
  VideoIdeaRequest,
} from '../types';
import { fetchIdeaDirections, fetchIdeaPlan } from '../lib/api';
import { Button } from './ui/button';

interface IdeaFlowProps {
  config: AppConfig | null;
  onBack: () => void;
  onOpenSettings: () => void;
  onUseFootage: (guide: VideoIdeaGuide) => void;
}

const GOALS: Array<{ value: IdeaGoal; label: string }> = [
  { value: 'hiburan', label: 'Menghibur' },
  { value: 'informasi', label: 'Informasi' },
  { value: 'promosi', label: 'Promosi' },
];

const TONES: Array<{ value: IdeaTone; label: string }> = [
  { value: 'santai', label: 'Santai' },
  { value: 'lucu', label: 'Lucu' },
  { value: 'serius', label: 'Serius' },
  { value: 'meyakinkan', label: 'Meyakinkan' },
];

const DURATIONS = [15, 30, 45] as const;

function formatPlanText(idea: string, direction: string, hook: string, plan: VideoIdeaPlan): string {
  const scenes = plan.scenes.map((scene, index) =>
    `${index + 1}. Gambar: ${scene.visual}\n   Ucapan: ${scene.spoken}\n   Teks layar: ${scene.onscreen}`,
  );
  return [
    `IDE: ${idea}`,
    `ARAH CERITA: ${direction}`,
    `PEMBUKA: ${hook}`,
    'ADEGAN:',
    ...scenes,
    `PENUTUP: ${plan.closing}`,
    `CATATAN EDIT: ${plan.editing_note}`,
  ].join('\n\n');
}

export const IdeaFlow: FC<IdeaFlowProps> = ({ config, onBack, onOpenSettings, onUseFootage }) => {
  const [idea, setIdea] = useState('');
  const [goal, setGoal] = useState<IdeaGoal>('informasi');
  const [tone, setTone] = useState<IdeaTone>('santai');
  const [duration, setDuration] = useState<15 | 30 | 45>(30);
  const [directions, setDirections] = useState<VideoIdeaDirection[]>([]);
  const [selectedDirection, setSelectedDirection] = useState<VideoIdeaDirection | null>(null);
  const [plan, setPlan] = useState<VideoIdeaPlan | null>(null);
  const [selectedHook, setSelectedHook] = useState('');
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelNotice, setModelNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const request: VideoIdeaRequest = { idea: idea.trim(), goal, tone, duration };
  const hasConfiguredKey = config
    ? config.llm_provider === 'openai'
      ? config.has_openai_key
      : config.has_gemini_key
    : true;

  const handleDirections = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!request.idea) {
      setError('Tulis dulu topik atau ide videomu.');
      return;
    }
    setIsLoading(true);
    setError(null);
    setModelNotice(null);
    setPlan(null);
    setSelectedDirection(null);
    try {
      const result = await fetchIdeaDirections(request);
      setDirections(result.directions);
      setModelNotice(result.notice ?? null);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Arah cerita belum berhasil dibuat. Coba lagi.');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePlan = async () => {
    if (!selectedDirection) return;
    setIsLoading(true);
    setError(null);
    setModelNotice(null);
    try {
      const result = await fetchIdeaPlan({ ...request, direction: selectedDirection });
      setPlan(result);
      setModelNotice(result.notice ?? null);
      setSelectedHook(result.hooks[0]);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Panduan video belum berhasil dibuat. Coba lagi.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!plan || !selectedDirection) return;
    try {
      await navigator.clipboard.writeText(formatPlanText(idea, selectedDirection.title, selectedHook, plan));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError('Panduan belum bisa disalin. Coba pilih dan salin teksnya secara manual.');
    }
  };

  const goBack = () => {
    setError(null);
    setStep(step === 3 ? 2 : 1);
  };

  const renderProgress = () => (
    <div className="mb-7 flex items-center gap-2 text-xs text-zinc-400" aria-label={`Langkah ${step} dari 3`}>
      {[1, 2, 3].map((item) => (
        <div key={item} className="flex items-center gap-2">
          <span className={`grid h-7 w-7 place-items-center rounded-full border ${item === step ? 'border-violet-400 bg-violet-500/15 text-white' : item < step ? 'border-emerald-500/50 text-emerald-300' : 'border-zinc-700 text-zinc-500'}`}>
            {item < step ? <Check aria-hidden="true" className="h-3.5 w-3.5" /> : item}
          </span>
          <span className={item === step ? 'text-zinc-100' : 'hidden sm:inline'}>
            {item === 1 ? 'Tulis ide' : item === 2 ? 'Pilih cerita' : 'Panduan video'}
          </span>
          {item < 3 && <span aria-hidden="true" className="mx-1 h-px w-5 bg-zinc-700 sm:w-9" />}
        </div>
      ))}
    </div>
  );

  return (
    <section className="mx-auto w-full max-w-4xl py-5 sm:py-8">
      <button type="button" onClick={onBack} className="mb-5 inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm text-zinc-300 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400">
        <ArrowLeft aria-hidden="true" className="h-4 w-4" />
        Kembali ke Mulai
      </button>

      {renderProgress()}

      {step === 1 && (
        <form onSubmit={handleDirections} className="space-y-6">
          <div>
            <h1 className="font-headline text-2xl font-semibold text-white sm:text-3xl">Kembangkan ide videomu</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">Tulis ide sesederhana apa pun. Kita cari dulu sudut cerita yang cocok.</p>
          </div>

          <div>
            <label htmlFor="idea-input" className="mb-2 block text-sm font-medium text-zinc-200">Mau bikin video tentang apa?</label>
            <textarea
              id="idea-input"
              value={idea}
              onChange={(event) => setIdea(event.target.value.slice(0, 1000))}
              placeholder="Contoh: promosi kopi susu buat anak kos"
              rows={4}
              maxLength={1000}
              required
              className="min-h-32 w-full resize-y rounded-lg border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm leading-6 text-white placeholder:text-zinc-500 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
            />
            <div className="mt-1 flex justify-between gap-3 text-xs text-zinc-500">
              <span>Belum perlu jadi judul atau naskah.</span>
              <span>{idea.length}/1000</span>
            </div>
          </div>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-zinc-200">Tujuan video</legend>
            <div className="grid grid-cols-3 gap-2">
              {GOALS.map((item) => (
                <button key={item.value} type="button" aria-pressed={goal === item.value} onClick={() => setGoal(item.value)} className={`min-h-11 rounded-md border px-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${goal === item.value ? 'border-violet-400 bg-violet-500/15 text-white' : 'border-zinc-700 bg-zinc-900/50 text-zinc-300 hover:border-zinc-500'}`}>
                  {item.label}
                </button>
              ))}
            </div>
          </fieldset>

          <div className="grid gap-5 sm:grid-cols-2">
            <label className="block text-sm font-medium text-zinc-200" htmlFor="idea-tone">
              Gaya bicara
              <select id="idea-tone" value={tone} onChange={(event) => setTone(event.target.value as IdeaTone)} className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30">
                {TONES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>

            <fieldset>
              <legend className="mb-2 text-sm font-medium text-zinc-200">Durasi video</legend>
              <div className="grid grid-cols-3 gap-2">
                {DURATIONS.map((seconds) => (
                  <button key={seconds} type="button" aria-pressed={duration === seconds} onClick={() => setDuration(seconds)} className={`min-h-11 rounded-md border px-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${duration === seconds ? 'border-violet-400 bg-violet-500/15 text-white' : 'border-zinc-700 bg-zinc-900/50 text-zinc-300 hover:border-zinc-500'}`}>
                    {seconds} detik
                  </button>
                ))}
              </div>
            </fieldset>
          </div>

          {error && <div role="alert" className="rounded-md border border-rose-500/40 bg-rose-950/30 p-3 text-sm leading-5 text-rose-200">{error}</div>}
          {!hasConfiguredKey && (
            <div className="flex flex-col gap-3 border-l-2 border-amber-400 pl-3 text-sm text-amber-100 sm:flex-row sm:items-center sm:justify-between">
              <span>AI belum tersambung. Atur aksesnya sebelum membuat arah cerita.</span>
              <Button type="button" variant="outline" onClick={onOpenSettings} className="min-h-11">Buka Pengaturan</Button>
            </div>
          )}
          <Button type="submit" disabled={isLoading || !idea.trim()} className="min-h-12 w-full sm:w-auto">
            {isLoading ? 'Mencari arah cerita...' : 'Cari arah cerita'}
          </Button>
        </form>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <div>
            <h1 className="font-headline text-2xl font-semibold text-white sm:text-3xl">Pilih cara bercerita</h1>
            <p className="mt-2 text-sm leading-6 text-zinc-400">Untuk ide: <span className="text-zinc-200">{idea}</span></p>
          </div>
          <div className="space-y-3">
            {directions.map((direction, index) => {
              const selected = selectedDirection?.title === direction.title;
              return (
                <button key={`${direction.title}-${index}`} type="button" aria-pressed={selected} onClick={() => setSelectedDirection(direction)} className={`w-full rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 sm:p-5 ${selected ? 'border-violet-400 bg-violet-500/[0.08]' : 'border-zinc-700 bg-zinc-900/50 hover:border-zinc-500'}`}>
                  <span className="flex items-start gap-3">
                    <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border ${selected ? 'border-violet-300 bg-violet-400 text-zinc-950' : 'border-zinc-600'}`}>{selected && <Check aria-hidden="true" className="h-3.5 w-3.5" />}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-headline text-base font-semibold text-white">{direction.title}</span>
                      <span className="mt-1 block text-sm leading-6 text-zinc-300">{direction.summary}</span>
                      <span className="mt-3 block border-l-2 border-cyan-400/60 pl-3 text-sm leading-6 text-cyan-100">“{direction.hook}”</span>
                      <span className="mt-2 block text-xs leading-5 text-zinc-400">{direction.why}</span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
          {modelNotice && <p role="status" className="border-l-2 border-amber-400 pl-3 text-sm leading-6 text-amber-100">{modelNotice}</p>}
          {error && <div role="alert" className="rounded-md border border-rose-500/40 bg-rose-950/30 p-3 text-sm leading-5 text-rose-200">{error}</div>}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            <Button type="button" variant="outline" onClick={goBack} className="min-h-11"><ArrowLeft aria-hidden="true" />Ubah ide</Button>
            <Button type="button" variant="outline" disabled={isLoading} onClick={() => void handleDirections()} className="min-h-11"><RotateCcw aria-hidden="true" />Buat arah lain</Button>
            <Button type="button" disabled={!selectedDirection || isLoading} onClick={() => void handlePlan()} className="min-h-11 sm:order-last">
              {isLoading ? 'Menyusun panduan...' : 'Pakai arah ini'}
            </Button>
          </div>
        </div>
      )}

      {step === 3 && plan && selectedDirection && (
        <div className="space-y-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="font-headline text-2xl font-semibold text-white sm:text-3xl">Panduan videomu</h1>
              <p className="mt-2 text-sm text-zinc-400">{selectedDirection.title} · sekitar {duration} detik</p>
            </div>
            <Button type="button" variant="outline" onClick={goBack} className="min-h-11 self-start sm:self-auto"><ArrowLeft aria-hidden="true" />Ganti arah</Button>
          </div>

          <section aria-labelledby="hooks-heading">
            <h2 id="hooks-heading" className="mb-3 font-headline text-base font-semibold text-white">Pilih kalimat pembuka</h2>
            <div className="space-y-2">
              {plan.hooks.map((hook) => (
                <button key={hook} type="button" aria-pressed={selectedHook === hook} onClick={() => setSelectedHook(hook)} className={`w-full min-h-12 rounded-md border px-4 py-3 text-left text-sm leading-6 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${selectedHook === hook ? 'border-cyan-300/70 bg-cyan-400/[0.08] text-white' : 'border-zinc-700 text-zinc-300 hover:border-zinc-500'}`}>
                  {hook}
                </button>
              ))}
            </div>
          </section>

          <section aria-labelledby="scenes-heading">
            <h2 id="scenes-heading" className="mb-3 font-headline text-base font-semibold text-white">Urutan adegan</h2>
            <ol className="divide-y divide-zinc-800 border-y border-zinc-800">
              {plan.scenes.map((scene, index) => (
                <li key={`${scene.visual}-${index}`} className="grid gap-2 py-4 sm:grid-cols-[92px_minmax(0,1fr)] sm:gap-4">
                  <span className="text-xs font-medium text-violet-300">Adegan {index + 1}</span>
                  <div className="grid gap-2 text-sm leading-6 sm:grid-cols-3">
                    <p><span className="block text-xs text-zinc-500">Gambar</span><span className="text-zinc-200">{scene.visual}</span></p>
                    <p><span className="block text-xs text-zinc-500">Ucapan</span><span className="text-zinc-200">{scene.spoken}</span></p>
                    <p><span className="block text-xs text-zinc-500">Teks layar</span><span className="text-zinc-200">{scene.onscreen}</span></p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="grid gap-4 border-b border-zinc-800 pb-5 sm:grid-cols-2">
            <div>
              <h2 className="text-sm font-semibold text-white">Penutup</h2>
              <p className="mt-1 text-sm leading-6 text-zinc-300">{plan.closing}</p>
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Catatan edit</h2>
              <p className="mt-1 text-sm leading-6 text-zinc-300">{plan.editing_note}</p>
            </div>
          </section>

          {modelNotice && <p role="status" className="border-l-2 border-amber-400 pl-3 text-sm leading-6 text-amber-100">{modelNotice}</p>}
          {error && <div role="alert" className="rounded-md border border-rose-500/40 bg-rose-950/30 p-3 text-sm leading-5 text-rose-200">{error}</div>}
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <Button type="button" variant="outline" onClick={() => void handleCopy()} className="min-h-11">
              {copied ? <Check aria-hidden="true" /> : <ClipboardCopy aria-hidden="true" />}
              {copied ? 'Panduan tersalin' : 'Salin panduan'}
            </Button>
            <Button type="button" onClick={() => onUseFootage({ idea, directionTitle: selectedDirection.title, selectedHook, plan })} className="min-h-11">
              Saya sudah punya video
            </Button>
          </div>
          <p className="text-xs leading-5 text-zinc-500">Panduan ini membantu menyiapkan rekaman. Untuk membuat klip, lanjutkan dengan video yang kamu punya.</p>
        </div>
      )}
    </section>
  );
};
