import { useEffect, useMemo, useState, type FC, type FormEvent } from 'react';
import { ArrowLeft, Check, ClipboardCopy, Film, RefreshCw, RotateCcw, Sparkles } from 'lucide-react';
import type {
  AgnesAspectRatio,
  AgnesVideoModel,
  AgnesVideoSize,
  AllModelsResponse,
  AppConfig,
  IdeaGoal,
  IdeaLlmProvider,
  IdeaTone,
  JobState,
  ModelOption,
  MuapiModelSchema,
  VideoGenerationProvider,
  VideoIdeaDirection,
  VideoIdeaGuide,
  VideoIdeaPlan,
  VideoIdeaRequest,
} from '../types';
import { fetchAllModels, fetchIdeaDirections, fetchIdeaPlan, fetchMuapiModelSchema, generateIdeaVideo } from '../lib/api';
import { Button } from './ui/button';
import { JobProgressCard } from './JobProgressCard';

interface IdeaFlowProps {
  config: AppConfig | null;
  activeJob: JobState | null;
  isCanceling: boolean;
  pollingError: string | null;
  onCancelJob: () => void;
  onRetryPolling: () => void;
  onVideoJobStarted: (jobId: string) => void;
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
const AGNES_DURATIONS = [4, 6, 8, 10, 12] as const;
const AGNES_RATIOS: AgnesAspectRatio[] = ['9:16', '16:9', '1:1', '3:4', '4:3'];

function stripHookQuotes(text: string): string {
  const trimmed = text.trim();
  const stripped = trimmed.replace(/^["'“”‘’]+|["'“”‘’]+$/g, '').trim();
  return stripped || trimmed;
}

function cleanVisualFragment(text: string): string {
  return text
    .trim()
    .replace(/^["'“”‘’]+|["'“”‘’]+$/g, '')
    .replace(/->/g, ', ')
    .replace(/\.{2,}/g, '.')
    .replace(/\s+/g, ' ')
    .replace(/[.,\s]+$/, '')
    .trim();
}

function buildDefaultVideoPrompt(
  idea: string,
  direction?: VideoIdeaDirection | null,
  _hook?: string,
  plan?: VideoIdeaPlan | null,
  aspectRatio: AgnesAspectRatio = '9:16',
): string {
  const parts: string[] = [];
  const cleanIdea = cleanVisualFragment(idea);
  if (cleanIdea) parts.push(cleanIdea);

  if (direction?.summary) {
    const cleanSummary = cleanVisualFragment(direction.summary);
    if (cleanSummary) parts.push(cleanSummary);
  }

  if (plan?.scenes?.length) {
    const visuals = plan.scenes
      .map((s) => cleanVisualFragment(s.visual))
      .filter(Boolean)
      .slice(0, 4);
    if (visuals.length > 0) parts.push(visuals.join(', '));
  }

  const framing = aspectRatio === '9:16' ? 'vertikal 9:16' : `rasio ${aspectRatio}`;
  parts.push(
    `Sinematik realistis, gerakan kamera halus dengan close-up subjek dan aksi jelas, pencahayaan hangat natural, suasana hidup, format ${framing} tanpa teks atau dialog`,
  );

  return parts
    .filter(Boolean)
    .join('. ')
    .replace(/\.{2,}/g, '.')
    .slice(0, 2000);
}

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

export const IdeaFlow: FC<IdeaFlowProps> = ({
  config,
  activeJob,
  isCanceling,
  pollingError,
  onCancelJob,
  onRetryPolling,
  onVideoJobStarted,
  onBack,
  onOpenSettings,
  onUseFootage,
}) => {
  const [idea, setIdea] = useState('');
  const [goal, setGoal] = useState<IdeaGoal>('informasi');
  const [tone, setTone] = useState<IdeaTone>('santai');
  const [duration, setDuration] = useState<15 | 30 | 45>(30);
  const [directions, setDirections] = useState<VideoIdeaDirection[]>([]);
  const [selectedDirection, setSelectedDirection] = useState<VideoIdeaDirection | null>(null);
  const [plan, setPlan] = useState<VideoIdeaPlan | null>(null);
  const [selectedHook, setSelectedHook] = useState('');
  const [step, setStep] = useState<1 | 2 | 3 | 'video'>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelNotice, setModelNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // LLM Provider & Model selection (from configured APIs in Reef Clipper)
  const [allModels, setAllModels] = useState<AllModelsResponse | null>(null);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [llmProvider, setLlmProvider] = useState<IdeaLlmProvider>(() => {
    if (config?.llm_provider === 'openai' && config.has_openai_key) return 'openai';
    if (config?.has_gemini_key) return 'gemini';
    if (config?.has_openai_key) return 'openai';
    if (config?.has_agnes_key) return 'agnes';
    return config?.llm_provider === 'openai' ? 'openai' : 'gemini';
  });
  const [llmModel, setLlmModel] = useState<string>('');

  // Video Generation state (Agnes AI & MuAPI)
  const [videoProvider, setVideoProvider] = useState<VideoGenerationProvider>(() => {
    if (config?.has_agnes_key) return 'agnes';
    if (config?.has_muapi_key) return 'muapi';
    return 'agnes';
  });
  const [videoPrompt, setVideoPrompt] = useState('');
  const [videoModel, setVideoModel] = useState<AgnesVideoModel>(
    config?.agnes_video_model === 'agnes-video-2.5' ? 'agnes-video-2.5' : 'agnes-video-2.5-flash',
  );
  const [videoRatio, setVideoRatio] = useState<AgnesAspectRatio>('9:16');
  const [videoDuration, setVideoDuration] = useState<number>(6);
  const [videoSize, setVideoSize] = useState<AgnesVideoSize>('720P');
  const [muapiModelFilter, setMuapiModelFilter] = useState('');
  const [muapiModel, setMuapiModel] = useState('');
  const [muapiSchema, setMuapiSchema] = useState<MuapiModelSchema | null>(null);
  const [isLoadingMuapiSchema, setIsLoadingMuapiSchema] = useState(false);
  const [muapiRatio, setMuapiRatio] = useState('9:16');
  const [muapiDuration, setMuapiDuration] = useState<number>(5);
  const [muapiResolution, setMuapiResolution] = useState('720p');
  const [isSubmittingVideo, setIsSubmittingVideo] = useState(false);

  const loadModels = async (refresh: boolean = false) => {
    setIsLoadingModels(true);
    try {
      const data = await fetchAllModels(refresh);
      setAllModels(data);
    } catch {
      // Keep fallback options if /api/models fails
    } finally {
      setIsLoadingModels(false);
    }
  };

  useEffect(() => {
    void loadModels(false);
  }, [config?.has_gemini_key, config?.has_openai_key, config?.has_agnes_key, config?.has_muapi_key]);

  const currentLlmModels: ModelOption[] =
    llmProvider === 'openai'
      ? (allModels?.openai?.models ?? [])
      : llmProvider === 'agnes'
      ? (allModels?.agnes?.models ?? [])
      : (allModels?.gemini?.models ?? []);

  useEffect(() => {
    if (currentLlmModels.length === 0) return;
    if (llmModel && currentLlmModels.some((m) => m.id === llmModel)) return;
    const activeDefault =
      llmProvider === 'openai'
        ? allModels?.active?.openai_model
        : llmProvider === 'agnes'
        ? allModels?.active?.agnes_chat_model
        : allModels?.active?.gemini_model;
    const matched = activeDefault && currentLlmModels.find((m) => m.id === activeDefault);
    setLlmModel(matched ? matched.id : currentLlmModels[0].id);
  }, [llmProvider, currentLlmModels, allModels, llmModel]);

  const agnesVideoModels: ModelOption[] =
    allModels?.agnes?.video_models && allModels.agnes.video_models.length > 0
      ? allModels.agnes.video_models
      : [
          { id: 'agnes-video-2.5-flash', name: 'agnes-video-2.5-flash (Cepat · 720P)' },
          { id: 'agnes-video-2.5', name: 'agnes-video-2.5 (HD · 720P / 1080P)' },
        ];

  const muapiVideoModels: ModelOption[] = useMemo(
    () => allModels?.muapi?.video_models ?? [],
    [allModels],
  );

  const filteredMuapiModels = useMemo(() => {
    const q = muapiModelFilter.trim().toLowerCase();
    if (!q) return muapiVideoModels;
    return muapiVideoModels.filter(
      (m) =>
        m.id.toLowerCase().includes(q) ||
        (m.family || '').toLowerCase().includes(q) ||
        (m.description || '').toLowerCase().includes(q),
    );
  }, [muapiVideoModels, muapiModelFilter]);

  const groupedMuapiModels = useMemo(() => {
    const groups = new Map<string, ModelOption[]>();
    for (const m of filteredMuapiModels) {
      const fam = (m.family || 'lainnya').toUpperCase();
      const bucket = groups.get(fam);
      if (bucket) bucket.push(m);
      else groups.set(fam, [m]);
    }
    return Array.from(groups.entries());
  }, [filteredMuapiModels]);

  useEffect(() => {
    if (muapiVideoModels.length === 0) return;
    if (muapiModel && muapiVideoModels.some((m) => m.id === muapiModel)) return;
    const preferred =
      muapiVideoModels.find((m) => m.id === 'veo3.1-fast-text-to-video') ||
      muapiVideoModels.find((m) => m.recommended) ||
      muapiVideoModels[0];
    setMuapiModel(preferred.id);
  }, [muapiVideoModels, muapiModel]);

  useEffect(() => {
    if (videoProvider !== 'muapi' || !muapiModel) return;
    let cancelled = false;
    setIsLoadingMuapiSchema(true);
    fetchMuapiModelSchema(muapiModel)
      .then((schema) => {
        if (cancelled) return;
        setMuapiSchema(schema);
        const ratios = schema.aspect_ratio?.enum;
        if (ratios && ratios.length > 0) {
          setMuapiRatio(ratios.includes('9:16') ? '9:16' : String(schema.aspect_ratio?.default ?? ratios[0]));
        }
        const durations = schema.duration?.enum;
        if (durations && durations.length > 0) {
          setMuapiDuration(Number(schema.duration?.default ?? durations[0]));
        } else if (schema.duration?.default !== undefined) {
          setMuapiDuration(Number(schema.duration.default));
        }
        const resolutions = schema.resolution?.enum;
        if (resolutions && resolutions.length > 0) {
          setMuapiResolution(String(schema.resolution?.default ?? resolutions[0]));
        }
      })
      .catch(() => {
        if (!cancelled) setMuapiSchema(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingMuapiSchema(false);
      });
    return () => {
      cancelled = true;
    };
  }, [videoProvider, muapiModel]);

  const selectedMuapiMeta = useMemo(
    () => muapiVideoModels.find((m) => m.id === muapiModel) ?? null,
    [muapiVideoModels, muapiModel],
  );

  const request: VideoIdeaRequest = {
    idea: idea.trim(),
    goal,
    tone,
    duration,
    llm_provider: llmProvider,
    llm_model: llmModel || undefined,
  };
  const hasConfiguredKey = config
    ? (config.llm_provider === 'openai' ? config.has_openai_key : config.has_gemini_key) || Boolean(config.has_agnes_key)
    : true;
  const hasAgnesKey = config ? Boolean(config.has_agnes_key) : true;
  const hasMuapiKey = config ? Boolean(config.has_muapi_key) : true;
  const hasSelectedVideoKey = videoProvider === 'muapi' ? hasMuapiKey : hasAgnesKey;
  const isJobActive = Boolean(
    activeJob && (activeJob.status === 'running' || activeJob.status === 'queued' || activeJob.status === 'canceling'),
  );

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
      const cleanedHooks = result.hooks.map(stripHookQuotes);
      const normalizedPlan = { ...result, hooks: cleanedHooks };
      setPlan(normalizedPlan);
      setModelNotice(result.notice ?? null);
      setSelectedHook(cleanedHooks[0] ?? '');
      setVideoPrompt(buildDefaultVideoPrompt(idea, selectedDirection, cleanedHooks[0], normalizedPlan, videoRatio));
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Panduan video belum berhasil dibuat. Coba lagi.');
    } finally {
      setIsLoading(false);
    }
  };

  const openVideoComposer = () => {
    setError(null);
    if (!videoPrompt.trim() && idea.trim()) {
      setVideoPrompt(buildDefaultVideoPrompt(idea, selectedDirection, selectedHook, plan, videoRatio));
    }
    setStep('video');
  };

  const handleGenerateVideo = async (event: FormEvent) => {
    event.preventDefault();
    const cleanPrompt = videoPrompt.trim();
    if (!cleanPrompt) {
      setError('Tulis dulu deskripsi visual video.');
      return;
    }
    if (videoProvider === 'muapi' && !muapiModel) {
      setError('Pilih model video MuAPI terlebih dahulu.');
      return;
    }
    setIsSubmittingVideo(true);
    setError(null);
    try {
      if (videoProvider === 'muapi') {
        const res = await generateIdeaVideo({
          provider: 'muapi',
          prompt: cleanPrompt,
          title: selectedDirection?.title || idea.trim().slice(0, 80) || 'Video Ide MuAPI',
          idea: idea.trim(),
          hook: stripHookQuotes(selectedHook || selectedDirection?.hook || ''),
          model: muapiModel,
          duration: muapiDuration,
          aspect_ratio: muapiRatio,
          resolution: muapiResolution,
        });
        onVideoJobStarted(res.job_id);
      } else {
        const effectiveSize: AgnesVideoSize = videoModel === 'agnes-video-2.5-flash' ? '720P' : videoSize;
        const res = await generateIdeaVideo({
          provider: 'agnes',
          prompt: cleanPrompt,
          title: selectedDirection?.title || idea.trim().slice(0, 80) || 'Video Ide Agnes AI',
          idea: idea.trim(),
          hook: stripHookQuotes(selectedHook || selectedDirection?.hook || ''),
          model: videoModel,
          duration: videoDuration,
          aspect_ratio: videoRatio,
          size: effectiveSize,
        });
        onVideoJobStarted(res.job_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Belum berhasil memulai pembuatan video AI.');
    } finally {
      setIsSubmittingVideo(false);
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
    if (step === 'video') {
      setStep(plan ? 3 : 1);
      return;
    }
    setStep(step === 3 ? 2 : 1);
  };

  const activeStepNum = step === 'video' ? 4 : step;
  const renderProgress = () => (
    <div className="mb-7 flex flex-wrap items-center gap-2 text-xs text-zinc-400" aria-label={`Langkah ${activeStepNum} dari 4`}>
      {([1, 2, 3, 4] as const).map((item) => (
        <div key={item} className="flex items-center gap-2">
          <span className={`grid h-7 w-7 place-items-center rounded-full border ${item === activeStepNum ? 'border-violet-400 bg-violet-500/15 text-white' : item < activeStepNum ? 'border-emerald-500/50 text-emerald-300' : 'border-zinc-700 text-zinc-500'}`}>
            {item < activeStepNum ? <Check aria-hidden="true" className="h-3.5 w-3.5" /> : item}
          </span>
          <span className={item === activeStepNum ? 'text-zinc-100' : 'hidden sm:inline'}>
            {item === 1 ? 'Tulis ide' : item === 2 ? 'Pilih cerita' : item === 3 ? 'Panduan video' : 'Video AI'}
          </span>
          {item < 4 && <span aria-hidden="true" className="mx-1 h-px w-4 bg-zinc-700 sm:w-7" />}
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

          <div className="grid gap-5 sm:grid-cols-2">
            <label className="block text-sm font-medium text-zinc-200" htmlFor="idea-llm-provider">
              API AI (Ide &amp; Naskah)
              <select
                id="idea-llm-provider"
                value={llmProvider}
                onChange={(event) => {
                  setLlmProvider(event.target.value as IdeaLlmProvider);
                  setLlmModel('');
                }}
                className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              >
                <option value="gemini" disabled={Boolean(config && !config.has_gemini_key)}>
                  Gemini {config && !config.has_gemini_key ? '(Belum disetel)' : ''}
                </option>
                <option value="openai" disabled={Boolean(config && !config.has_openai_key)}>
                  OpenAI / Proxy {config && !config.has_openai_key ? '(Belum disetel)' : ''}
                </option>
                <option value="agnes" disabled={Boolean(config && !config.has_agnes_key)}>
                  Agnes AI {config && !config.has_agnes_key ? '(Belum disetel)' : ''}
                </option>
              </select>
            </label>

            <div>
              <div className="flex items-center justify-between gap-2">
                <label className="block text-sm font-medium text-zinc-200" htmlFor="idea-llm-model">
                  Model AI
                </label>
                <button
                  type="button"
                  onClick={() => void loadModels(true)}
                  disabled={isLoadingModels}
                  className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
                >
                  <RefreshCw aria-hidden="true" className={`h-3 w-3 ${isLoadingModels ? 'animate-spin' : ''}`} />
                  Muat ulang
                </button>
              </div>
              <select
                id="idea-llm-model"
                value={llmModel}
                onChange={(event) => setLlmModel(event.target.value)}
                disabled={currentLlmModels.length === 0}
                className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white disabled:opacity-60 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
              >
                {currentLlmModels.length === 0 ? (
                  <option value="">{isLoadingModels ? 'Memuat model...' : 'Belum ada model'}</option>
                ) : (
                  currentLlmModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name || m.id}
                    </option>
                  ))
                )}
              </select>
            </div>
          </div>

          {error && <div role="alert" className="rounded-md border border-rose-500/40 bg-rose-950/30 p-3 text-sm leading-5 text-rose-200">{error}</div>}
          {!hasConfiguredKey && (
            <div className="flex flex-col gap-3 border-l-2 border-amber-400 pl-3 text-sm text-amber-100 sm:flex-row sm:items-center sm:justify-between">
              <span>AI belum tersambung. Atur aksesnya sebelum membuat arah cerita.</span>
              <Button type="button" variant="outline" onClick={onOpenSettings} className="min-h-11">Buka Pengaturan</Button>
            </div>
          )}
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <Button type="submit" disabled={isLoading || !idea.trim()} className="min-h-12 w-full sm:w-auto">
              {isLoading ? 'Mencari arah cerita...' : 'Cari arah cerita'}
            </Button>
            <Button type="button" variant="outline" disabled={isLoading || !idea.trim()} onClick={openVideoComposer} className="min-h-12 w-full sm:w-auto">
              <Sparkles aria-hidden="true" className="h-4 w-4 text-amber-400" />
              Langsung jadi video AI
            </Button>
          </div>
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
                      <span className="mt-3 block border-l-2 border-cyan-400/60 pl-3 text-sm leading-6 text-cyan-100">“{stripHookQuotes(direction.hook)}”</span>
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
            <Button type="button" onClick={openVideoComposer} className="min-h-11">
              <Film aria-hidden="true" className="h-4 w-4" />
              Buat Video AI
            </Button>
            <Button type="button" variant="outline" onClick={() => void handleCopy()} className="min-h-11">
              {copied ? <Check aria-hidden="true" /> : <ClipboardCopy aria-hidden="true" />}
              {copied ? 'Panduan tersalin' : 'Salin panduan'}
            </Button>
            <Button type="button" variant="outline" onClick={() => onUseFootage({ idea, directionTitle: selectedDirection.title, selectedHook, plan })} className="min-h-11">
              Saya sudah punya video
            </Button>
          </div>
          <p className="text-xs leading-5 text-zinc-500">Render langsung jadi video AI (Agnes AI / MuAPI), atau lanjutkan ke pemotong jika sudah punya rekaman sendiri.</p>
        </div>
      )}

      {step === 'video' && (
        <form onSubmit={handleGenerateVideo} className="space-y-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="font-headline text-2xl font-semibold text-white sm:text-3xl">Buat video dari ide</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">Pilih API dan model video AI dari Reef Clipper, sesuaikan prompt, lalu render otomatis ke MP4.</p>
            </div>
            <Button type="button" variant="outline" onClick={goBack} className="min-h-11 self-start sm:self-auto">
              <ArrowLeft aria-hidden="true" />
              {plan ? 'Kembali ke panduan' : 'Ubah ide'}
            </Button>
          </div>

          <fieldset>
            <legend className="mb-2 text-sm font-medium text-zinc-200">API Video AI</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                aria-pressed={videoProvider === 'agnes'}
                onClick={() => setVideoProvider('agnes')}
                className={`min-h-11 rounded-md border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${videoProvider === 'agnes' ? 'border-violet-400 bg-violet-500/15 text-white' : 'border-zinc-700 bg-zinc-900/50 text-zinc-300 hover:border-zinc-500'}`}
              >
                <span className="block font-medium">Agnes AI</span>
                <span className="block text-xs text-zinc-400">
                  {agnesVideoModels.length} model {hasAgnesKey ? '· Tersambung' : '· Belum disetel'}
                </span>
              </button>
              <button
                type="button"
                aria-pressed={videoProvider === 'muapi'}
                onClick={() => setVideoProvider('muapi')}
                className={`min-h-11 rounded-md border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${videoProvider === 'muapi' ? 'border-violet-400 bg-violet-500/15 text-white' : 'border-zinc-700 bg-zinc-900/50 text-zinc-300 hover:border-zinc-500'}`}
              >
                <span className="block font-medium">MuAPI (Veo, Sora, Kling, Wan, dll)</span>
                <span className="block text-xs text-zinc-400">
                  {muapiVideoModels.length > 0 ? `${muapiVideoModels.length} model aktif` : isLoadingModels ? 'Memuat model...' : 'Belum ada model'} {hasMuapiKey ? '· Tersambung' : '· Belum disetel'}
                </span>
              </button>
            </div>
          </fieldset>

          <div>
            <label htmlFor="agnes-video-prompt" className="mb-2 block text-sm font-medium text-zinc-200">Prompt visual video</label>
            <textarea
              id="agnes-video-prompt"
              value={videoPrompt}
              onChange={(event) => setVideoPrompt(event.target.value.slice(0, 2000))}
              placeholder="Deskripsikan adegan, gerakan kamera, pencahayaan, dan suasana video..."
              rows={5}
              maxLength={2000}
              required
              className="min-h-36 w-full resize-y rounded-lg border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm leading-6 text-white placeholder:text-zinc-500 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
            />
            <div className="mt-1 flex justify-between gap-3 text-xs text-zinc-500">
              <span>Tip: jelaskan subjek, aksi, sudut kamera, dan pencahayaan.</span>
              <span>{videoPrompt.length}/2000</span>
            </div>
          </div>

          {videoProvider === 'agnes' ? (
            <>
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="block text-sm font-medium text-zinc-200" htmlFor="agnes-model-select">
                  Model Video AI (Agnes AI)
                  <select
                    id="agnes-model-select"
                    value={videoModel}
                    onChange={(event) => {
                      const nextModel = event.target.value as AgnesVideoModel;
                      setVideoModel(nextModel);
                      if (nextModel === 'agnes-video-2.5-flash') setVideoSize('720P');
                    }}
                    className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                  >
                    {agnesVideoModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name || m.id}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block text-sm font-medium text-zinc-200" htmlFor="agnes-size-select">
                  Resolusi
                  <select
                    id="agnes-size-select"
                    value={videoModel === 'agnes-video-2.5-flash' ? '720P' : videoSize}
                    disabled={videoModel === 'agnes-video-2.5-flash'}
                    onChange={(event) => setVideoSize(event.target.value as AgnesVideoSize)}
                    className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white disabled:opacity-60 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                  >
                    <option value="720P">720P</option>
                    {videoModel === 'agnes-video-2.5' && <option value="1080P">1080P</option>}
                  </select>
                </label>
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <fieldset>
                  <legend className="mb-2 text-sm font-medium text-zinc-200">Rasio aspek</legend>
                  <div className="grid grid-cols-5 gap-2">
                    {AGNES_RATIOS.map((ratio) => (
                      <button
                        key={ratio}
                        type="button"
                        aria-pressed={videoRatio === ratio}
                        onClick={() => setVideoRatio(ratio)}
                        className={`min-h-11 rounded-md border px-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${videoRatio === ratio ? 'border-violet-400 bg-violet-500/15 text-white' : 'border-zinc-700 bg-zinc-900/50 text-zinc-300 hover:border-zinc-500'}`}
                      >
                        {ratio}
                      </button>
                    ))}
                  </div>
                </fieldset>

                <fieldset>
                  <legend className="mb-2 text-sm font-medium text-zinc-200">Durasi klip (Agnes AI)</legend>
                  <div className="grid grid-cols-5 gap-2">
                    {AGNES_DURATIONS.map((sec) => (
                      <button
                        key={sec}
                        type="button"
                        aria-pressed={videoDuration === sec}
                        onClick={() => setVideoDuration(sec)}
                        className={`min-h-11 rounded-md border px-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 ${videoDuration === sec ? 'border-violet-400 bg-violet-500/15 text-white' : 'border-zinc-700 bg-zinc-900/50 text-zinc-300 hover:border-zinc-500'}`}
                      >
                        {sec}d
                      </button>
                    ))}
                  </div>
                </fieldset>
              </div>
            </>
          ) : (
            <div className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-zinc-200" htmlFor="muapi-model-filter">
                  Cari model MuAPI
                  <input
                    id="muapi-model-filter"
                    type="search"
                    value={muapiModelFilter}
                    onChange={(event) => setMuapiModelFilter(event.target.value)}
                    placeholder="Ketik veo, sora, kling, wan, seedance, grok..."
                    className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white placeholder:text-zinc-500 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                  />
                </label>

                <div>
                  <div className="flex items-center justify-between gap-2">
                    <label className="block text-sm font-medium text-zinc-200" htmlFor="muapi-model-select">
                      Model Video MuAPI ({filteredMuapiModels.length})
                    </label>
                    <button
                      type="button"
                      onClick={() => void loadModels(true)}
                      disabled={isLoadingModels}
                      className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 disabled:opacity-50"
                    >
                      <RefreshCw aria-hidden="true" className={`h-3 w-3 ${isLoadingModels ? 'animate-spin' : ''}`} />
                      Muat ulang
                    </button>
                  </div>
                  <select
                    id="muapi-model-select"
                    value={muapiModel}
                    onChange={(event) => setMuapiModel(event.target.value)}
                    disabled={filteredMuapiModels.length === 0}
                    className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white disabled:opacity-60 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                  >
                    {groupedMuapiModels.length === 0 ? (
                      <option value="">{isLoadingModels ? 'Memuat model MuAPI...' : 'Model tidak ditemukan'}</option>
                    ) : (
                      groupedMuapiModels.map(([family, items]) => (
                        <optgroup key={family} label={family}>
                          {items.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.name || m.id}
                            </option>
                          ))}
                        </optgroup>
                      ))
                    )}
                  </select>
                </div>
              </div>

              {selectedMuapiMeta?.description && (
                <p className="text-xs leading-5 text-zinc-400">{selectedMuapiMeta.description}</p>
              )}

              <div className="grid gap-4 sm:grid-cols-3">
                {(!muapiSchema || muapiSchema.aspect_ratio) && (
                  <label className="block text-sm font-medium text-zinc-200" htmlFor="muapi-ratio-select">
                    Rasio aspek
                    <select
                      id="muapi-ratio-select"
                      value={muapiRatio}
                      disabled={isLoadingMuapiSchema}
                      onChange={(event) => setMuapiRatio(event.target.value)}
                      className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white disabled:opacity-60 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                    >
                      {(muapiSchema?.aspect_ratio?.enum ?? ['9:16', '16:9', '1:1']).map((ratio) => (
                        <option key={ratio} value={ratio}>
                          {ratio}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {(!muapiSchema || muapiSchema.duration) && (
                  <label className="block text-sm font-medium text-zinc-200" htmlFor="muapi-duration-select">
                    Durasi
                    {muapiSchema?.duration?.enum && muapiSchema.duration.enum.length > 0 ? (
                      <select
                        id="muapi-duration-select"
                        value={muapiDuration}
                        disabled={isLoadingMuapiSchema}
                        onChange={(event) => setMuapiDuration(Number(event.target.value))}
                        className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white disabled:opacity-60 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                      >
                        {muapiSchema.duration.enum.map((sec) => (
                          <option key={sec} value={sec}>
                            {sec} detik
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id="muapi-duration-select"
                        type="number"
                        min={1}
                        max={30}
                        value={muapiDuration}
                        disabled={isLoadingMuapiSchema}
                        onChange={(event) => setMuapiDuration(Math.max(1, Number(event.target.value) || 5))}
                        className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white disabled:opacity-60 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                      />
                    )}
                  </label>
                )}

                {(!muapiSchema || muapiSchema.resolution) && (
                  <label className="block text-sm font-medium text-zinc-200" htmlFor="muapi-resolution-select">
                    Resolusi
                    <select
                      id="muapi-resolution-select"
                      value={muapiResolution}
                      disabled={isLoadingMuapiSchema}
                      onChange={(event) => setMuapiResolution(event.target.value)}
                      className="mt-2 h-11 w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-white disabled:opacity-60 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/30"
                    >
                      {(muapiSchema?.resolution?.enum ?? ['480p', '720p', '1080p']).map((res) => (
                        <option key={res} value={res}>
                          {res}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
            </div>
          )}

          {!hasSelectedVideoKey && (
            <div className="flex flex-col gap-3 border-l-2 border-amber-400 pl-3 text-sm text-amber-100 sm:flex-row sm:items-center sm:justify-between">
              <span>
                {videoProvider === 'muapi'
                  ? 'MUAPI_API_KEY belum terpasang. Masukkan kunci MuAPI di Pengaturan untuk generate video.'
                  : 'AGNES_API_KEY belum terpasang. Masukkan kunci Agnes AI di Pengaturan untuk generate video.'}
              </span>
              <Button type="button" variant="outline" onClick={onOpenSettings} className="min-h-11">Buka Pengaturan</Button>
            </div>
          )}

          {error && <div role="alert" className="rounded-md border border-rose-500/40 bg-rose-950/30 p-3 text-sm leading-5 text-rose-200">{error}</div>}

          <Button
            type="submit"
            disabled={
              isSubmittingVideo ||
              isJobActive ||
              !videoPrompt.trim() ||
              !hasSelectedVideoKey ||
              (videoProvider === 'muapi' && !muapiModel)
            }
            className="min-h-12 w-full sm:w-auto"
          >
            <Film aria-hidden="true" className="h-4 w-4" />
            {isSubmittingVideo
              ? `Mengirim ke ${videoProvider === 'muapi' ? 'MuAPI' : 'Agnes AI'}...`
              : isJobActive
              ? 'Video sedang dibuat...'
              : 'Generate Video AI'}
          </Button>

          {activeJob &&
            (activeJob.status === 'running' ||
              activeJob.status === 'queued' ||
              activeJob.status === 'canceling' ||
              ((Boolean(activeJob.url?.startsWith('agnes://')) || Boolean(activeJob.url?.startsWith('muapi://'))) &&
                ['failed', 'timeout', 'canceled', 'cancelled', 'interrupted', 'completed'].includes(activeJob.status))) && (
            <div className="pt-2">
              <JobProgressCard
                job={activeJob}
                onCancel={onCancelJob}
                isCanceling={isCanceling}
                pollingError={pollingError}
                onRetry={onRetryPolling}
              />
            </div>
          )}
        </form>
      )}
    </section>
  );
};
