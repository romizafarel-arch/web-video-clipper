export interface AppConfig {
  mode_default: string;
  llm_provider: string;
  transcriber_provider: string;
  gemini_model: string;
  gemini_transcriber_model?: string;
  openai_model: string;
  openai_base_url?: string;
  whisper_model: string;
  job_timeout_seconds: number;
  auto_delete_source_video: boolean;
  has_gemini_key: boolean;
  has_openai_key: boolean;
  has_muapi_key: boolean;
  has_agnes_key?: boolean;
  agnes_base_url?: string;
  agnes_video_model?: string;
  gemini_key_masked?: string;
  openai_key_masked?: string;
  muapi_key_masked?: string;
  agnes_key_masked?: string;
}

export type IdeaGoal = 'hiburan' | 'informasi' | 'promosi';
export type IdeaTone = 'santai' | 'lucu' | 'serius' | 'meyakinkan';

export interface VideoIdeaDirection {
  title: string;
  summary: string;
  hook: string;
  why: string;
}

export interface VideoIdeaScene {
  visual: string;
  spoken: string;
  onscreen: string;
}

export interface VideoIdeaPlan {
  hooks: string[];
  scenes: VideoIdeaScene[];
  closing: string;
  editing_note: string;
}

export interface VideoIdeaRequest {
  idea: string;
  goal: IdeaGoal;
  tone: IdeaTone;
  duration: 15 | 30 | 45;
}

export interface VideoIdeaGuide {
  idea: string;
  directionTitle: string;
  selectedHook: string;
  plan: VideoIdeaPlan;
}

export type AgnesVideoModel = 'agnes-video-2.5-flash' | 'agnes-video-2.5';
export type AgnesAspectRatio = '9:16' | '16:9' | '1:1' | '3:4' | '4:3' | '21:9';
export type AgnesVideoSize = '720P' | '1080P';

export interface GenerateIdeaVideoPayload {
  prompt: string;
  title?: string;
  idea?: string;
  hook?: string;
  model: AgnesVideoModel;
  duration: number;
  aspect_ratio: AgnesAspectRatio;
  size: AgnesVideoSize;
}

export type FramingMode = 'podcast' | 'single' | 'center' | 'gaming' | 'dual';
export type GamingLayout = 'cam_top' | 'cam_bottom';
export type TextPresetId =
  | 'hormozi'
  | 'tiktok_punch'
  | 'devon_bold'
  | 'vox_box'
  | 'ali_abdaal'
  | 'aesthetic'
  | 'mrbeast'
  | 'karaoke_bounce'
  | 'cyber_neon'
  | 'retro_synth'
  | 'luxury_gold'
  | 'gaming_rage'
  | 'clean_bottom_bar'
  | 'comic_pow'
  | 'nas_daily'
  | 'netflix_sub'
  | 'matrix_hacker'
  | 'dan_koe'
  | 'fire_flame'
  | 'pastel_vlog'
  // 6 New Viral Presets (2025/2026 Trend)
  | 'brat_lime'
  | 'dymo_tape'
  | 'luxury_serif'
  | 'sticker_pop'
  | 'amber_terminal'
  | 'capcut_glow'
  // Legacy aliases for backward compatibility
  | 'hormozi_emerald'
  | 'hormozi_fire'
  | 'vox_cinema'
  | 'ali_cyan'
  | 'aesthetic_warm'
  | 'mrbeast_yellow';

export type SubtitleStyle =
  | 'karaoke'
  | 'clean'
  | 'minimal'
  | 'kinetic'
  | 'classic'
  | 'none'
  | TextPresetId;

export type SubtitleFontSizeScale = 'small' | 'medium' | 'large';

export type LLMProvider = 'gemini' | 'openai';
export type TranscriberProvider = 'whisper' | 'gemini';
export type ProcessingMode = 'local' | 'api';

export interface HistoryShort {
  title?: string;
  hook_sentence?: string;
  enable_sfx?: boolean;
  remove_silence?: boolean;
  score?: number | null;
  web_url: string;
  vtt_url?: string | null;
  filename: string;
  clip_index?: number;
  folder_name?: string;
  aspect_ratio?: string;
  size_bytes?: number;
  created_at?: string;
  start_time?: number | null;
  end_time?: number | null;
  framing_mode?: FramingMode;
  gaming_preset?: string;
  gaming_layout?: GamingLayout;
  font_family?: string;
  font_size_scale?: SubtitleFontSizeScale;
}

export interface HistorySession {
  id: string;
  folder_name: string;
  job_id?: string | null;
  url?: string;
  title: string;
  created_at?: string;
  aspect_ratio?: string;
  total_shorts: number;
  total_size_bytes: number;
  shorts: HistoryShort[];
  is_legacy?: boolean;
}

export interface HistoryResponse {
  sessions: HistorySession[];
  history: HistoryShort[];
  total_videos: number;
}

export interface ModelOption {
  id: string;
  name: string;
  recommended?: boolean;
}

export interface ModelsResponse {
  gemini?: ModelOption[];
  openai?: ModelOption[];
  whisper?: ModelOption[];
  active?: {
    llm_provider: string;
    gemini_model: string;
    openai_model: string;
    transcriber_provider: string;
    gemini_transcriber_model?: string;
    whisper_model: string;
  };
}

export interface ModelTestResponse {
  success: boolean;
  provider?: string;
  model?: string;
  latency_ms?: number;
  reply?: string;
  message?: string;
  error?: string;
}

export interface GeneratePayload {
  url: string;
  mode: string;
  num_clips: number;
  aspect_ratio: string;
  framing_mode: FramingMode;
  subtitle_style: SubtitleStyle;
  format: string;
  llm_provider: string;
  transcriber_provider: string;
  auto_delete_source_video: boolean;
  gemini_model?: string;
  openai_model?: string;
  gemini_transcriber_model?: string;
  whisper_model?: string;
  gaming_preset?: string;
  gaming_layout?: GamingLayout;
  font_family?: string;
  font_size_scale?: SubtitleFontSizeScale;
  cookies_file?: File;
  enable_sfx?: boolean;
  remove_silence?: boolean;
}

export interface GeneratedShort {
  title?: string;
  score?: number;
  web_url?: string;
  clip_url?: string;
  vtt_url?: string;
  filename?: string;
  aspect_ratio?: string;
  start_time?: number;
  end_time?: number;
  summary?: string;
  error?: string;
  framing_mode?: FramingMode;
  gaming_preset?: string;
  gaming_layout?: GamingLayout;
  font_family?: string;
  clip_index?: number;
}

export interface JobResult {
  session_folder?: string;
  aspect_ratio?: string;
  shorts?: GeneratedShort[];
  stats?: {
    total: number;
    success: number;
    failed: number;
  };
  video_title?: string;
  message?: string;
}

export type JobStatusType =
  | 'queued'
  | 'running'
  | 'canceling'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'timeout'
  | 'interrupted'
  | 'canceled'
  | 'cancelled';

export interface JobState {
  job_id: string;
  status: JobStatusType;
  stage?: string;
  progress?: number;
  logs?: string | string[];
  cancel_reason?: string;
  error?: string;
  result?: JobResult;
  start_time?: number;
}

export interface ActiveJobResponse {
  active: boolean;
  job_id?: string;
  status?: JobStatusType | 'none';
  stage?: string;
  progress?: number;
  logs?: string | string[];
  result?: JobResult;
  error?: string;
  cancel_reason?: string;
  created_at?: number;
  started_at?: number;
  ended_at?: number;
  elapsed_seconds?: number;
  session_folder?: string;
}

export interface SubtitleCue {
  id: string;
  start: number;
  end: number;
  text: string;
  words?: Array<{
    word: string;
    start: number;
    end: number;
    duration_cs?: number;
  }>;
}

export interface EditClipPayload {
  session_folder: string;
  clip_index: number;
  start_time: number;
  end_time: number;
  segments?: Array<{ start: number; end: number; text: string }>;
  subtitles?: Array<{ start: number; end: number; text: string }>;
  aspect_ratio?: string;
  framing_mode?: FramingMode;
  subtitle_style?: SubtitleStyle;
  gaming_preset?: string;
  gaming_layout?: GamingLayout;
  font_family?: string;
  burn_subtitles?: boolean;
  title?: string;
  hook_sentence?: string;
  enable_sfx?: boolean;
  remove_silence?: boolean;
}

export interface EditClipResponse {
  clip: {
    title: string;
    hook_sentence?: string;
  enable_sfx?: boolean;
  remove_silence?: boolean;
    start_time: number;
    end_time: number;
    score?: number | null;
    aspect_ratio: string;
    framing_mode: FramingMode;
    subtitle_style: SubtitleStyle;
    font_family?: string;
    web_url: string;
    vtt_url?: string | null;
    filename: string;
    clip_index: number;
    folder_name: string;
    rev_id?: string;
    burn_subtitles?: boolean;
    size_bytes?: number;
  };
  error?: string;
  success: boolean;
}

export interface EditableClip {
  session_folder: string;
  clip_index: number;
  title?: string;
  start_time: number;
  end_time: number;
  aspect_ratio?: string;
  web_url: string;
  vtt_url?: string | null;
  framing_mode?: FramingMode;
  gaming_preset?: string;
  gaming_layout?: GamingLayout;
  subtitle_style?: SubtitleStyle;
  font_family?: string;
  font_size_scale?: SubtitleFontSizeScale;
  hook_sentence?: string;
  enable_sfx?: boolean;
  remove_silence?: boolean;
  score?: number | null;
}

export interface User {
  id: string;
  name?: string;
  email?: string;
}

export interface VideoClip {
  id: string;
  title: string;
  startTime: number;
  endTime: number;
  aspectRatio: string;
  subtitleStyle: SubtitleStyle;
  fontFamily?: string;
  fontSizeScale?: SubtitleFontSizeScale;
  videoUrl: string;
  vttUrl?: string;
}

export interface SavedClipItem {
  id: string;
  sessionFolder: string;
  clipIndex: number;
  title: string;
  startTime: number;
  endTime: number;
  aspectRatio: string;
  subtitleStyle: SubtitleStyle;
  fontFamily?: string;
  fontSizeScale?: SubtitleFontSizeScale;
  webUrl: string;
  vttUrl?: string | null;
  savedAt: number;
  blobSize?: number;
}

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

