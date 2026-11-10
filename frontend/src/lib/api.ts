import type {
  AppConfig,
  GeneratePayload,
  JobState,
  HistoryResponse,
  ActiveJobResponse,
  ModelOption,
  ModelsResponse,
  ModelTestResponse,
  EditClipPayload,
  EditClipResponse,
  VideoIdeaDirection,
  VideoIdeaPlan,
  VideoIdeaRequest,
} from '../types';

async function postIdeaRequest<T>(path: string, payload: VideoIdeaRequest & { direction?: VideoIdeaDirection }): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Belum berhasil memproses ide. Coba lagi.');
  }
  return data as T;
}

export async function fetchIdeaDirections(payload: VideoIdeaRequest): Promise<{ directions: VideoIdeaDirection[]; notice?: string }> {
  return postIdeaRequest('/api/ideas/directions', payload);
}

export async function fetchIdeaPlan(
  payload: VideoIdeaRequest & { direction: VideoIdeaDirection },
): Promise<VideoIdeaPlan & { notice?: string }> {
  return postIdeaRequest('/api/ideas/plan', payload);
}

export async function fetchConfig(): Promise<AppConfig> {
  const res = await fetch('/api/config');
  if (!res.ok) {
    throw new Error('Failed to load system config');
  }
  return res.json();
}

export async function updateConfig(payload: Record<string, unknown>): Promise<{ success: boolean; message?: string }> {
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Failed to update config');
  }
  return data;
}

export async function submitGenerate(payload: GeneratePayload): Promise<{ job_id: string; message?: string }> {
  let res: Response;

  if (payload.cookies_file) {
    const formData = new FormData();
    formData.append('cookies_file', payload.cookies_file);
    const { cookies_file: _cookies_file, ...rest } = payload;
    formData.append('data', JSON.stringify(rest));

    res = await fetch('/api/generate', {
      method: 'POST',
      body: formData,
    });
  } else {
    res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Failed to start generation job');
  }
  return data;
}

export function getSessionZipDownloadUrl(folderName: string): string {
  return `/api/sessions/${encodeURIComponent(folderName)}/zip`;
}

export async function fetchJob(jobId: string): Promise<JobState | null> {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Job fetch failed with status ${res.status}`);
  }
  return res.json();
}

export async function cancelJob(jobId: string): Promise<boolean> {
  const res = await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
  return res.ok;
}

export async function fetchActiveJob(): Promise<ActiveJobResponse> {
  const res = await fetch('/api/jobs/active');
  if (!res.ok) {
    throw new Error(`Active job fetch failed with status ${res.status}`);
  }
  const data = await res.json();
  const isActive = Boolean(
    data.active === true ||
    (data.job_id && ['queued', 'running', 'canceling'].includes(data.status))
  );
  return {
    ...data,
    active: isActive,
  };
}

export async function fetchHistory(): Promise<HistoryResponse> {
  const res = await fetch('/api/history');
  if (!res.ok) {
    throw new Error(`History fetch failed with status ${res.status}`);
  }
  const data = await res.json();
  return {
    sessions: data.sessions || [],
    history: data.history || [],
    total_videos: data.total_videos ?? (data.history?.length || 0),
  };
}

export async function deleteHistorySession(folderName: string): Promise<{ success: boolean; message?: string }> {
  const res = await fetch(`/api/history/session/${encodeURIComponent(folderName)}`, {
    method: 'DELETE',
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Failed to delete session');
  }
  return data;
}

export async function openOutputFolder(folderName?: string): Promise<{ success: boolean }> {
  const res = await fetch('/api/open-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder: folderName || '' }),
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Failed to open folder');
  }
  return data;
}

export async function fetchModels(provider?: string, refresh: boolean = false): Promise<ModelOption[] | ModelsResponse> {
  const query = new URLSearchParams();
  if (provider) query.set('provider', provider);
  if (refresh) query.set('refresh', 'true');
  const res = await fetch(`/api/models?${query.toString()}`);
  if (!res.ok) {
    throw new Error('Failed to fetch models');
  }
  return res.json();
}

export async function testModel(provider: string, model: string): Promise<ModelTestResponse> {
  const res = await fetch('/api/models/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, model }),
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Failed to test model');
  }
  return data;
}

export async function editClip(payload: EditClipPayload): Promise<EditClipResponse> {
  const res = await fetch('/api/edit-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Gagal merender ulang klip video.');
  }
  return data;
}

export interface UploadFontResponse {
  success: boolean;
  font_name: string;
  family: string;
  filename: string;
  url: string;
  message?: string;
  error?: string;
}

export async function uploadCustomFont(file: File): Promise<UploadFontResponse> {
  const formData = new FormData();
  formData.append('font_file', file);
  const res = await fetch('/api/fonts/upload', {
    method: 'POST',
    body: formData,
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || 'Gagal mengunggah file font.');
  }
  return data;
}

export async function fetchAvailableFonts(): Promise<{
  fonts: Array<{ name: string; family: string; filename: string; url: string; is_custom: boolean }>;
}> {
  const res = await fetch('/api/fonts');
  if (!res.ok) {
    throw new Error('Gagal mengambil daftar font');
  }
  return res.json();
}


