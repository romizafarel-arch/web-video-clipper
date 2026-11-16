"""Agnes AI API client for idea-to-video generation and chat fallback."""
from pathlib import Path
import random
import re
import time
from typing import Any, Callable, Dict, Optional

import requests

from . import config as cfg

AGNES_VIDEO_MODELS = ("agnes-video-2.5-flash", "agnes-video-2.5")
AGNES_ASPECT_RATIOS = ("9:16", "16:9", "1:1", "3:4", "4:3", "21:9")
AGNES_SIZES = ("720P", "1080P", "1K", "2K")


class AgnesAPIError(RuntimeError):
    """Raised when Agnes AI API returns an error or times out."""


def normalize_base_url(base_url: Optional[str] = None) -> str:
    raw = (base_url or cfg.AGNES_BASE_URL or "https://apihub.agnes-ai.com").strip().rstrip("/")
    if raw.endswith("/v1"):
        raw = raw[:-3].rstrip("/")
    return raw or "https://apihub.agnes-ai.com"


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    key = (api_key or cfg.require_agnes_key()).strip()
    if not key or key == "your_agnes_key_here":
        raise RuntimeError(
            "AGNES_API_KEY is not set. Add it in Settings or .env to generate videos from ideas."
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _extract_error_message(resp: requests.Response) -> str:
    try:
        payload = resp.json()
        err = payload.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("code")
            if msg:
                return str(msg)
        elif isinstance(err, str) and err:
            return err
        if payload.get("message"):
            return str(payload["message"])
    except Exception:
        pass
    return resp.text[:300] if resp.text else f"HTTP {resp.status_code}"


def _format_http_error(resp: requests.Response, context: str) -> AgnesAPIError:
    detail = _extract_error_message(resp)
    if resp.status_code == 401:
        return AgnesAPIError("AGNES_API_KEY tidak valid atau kedaluwarsa. Periksa kunci di Pengaturan.")
    if resp.status_code == 403:
        if "quota" in detail.lower() or "insufficient" in detail.lower():
            return AgnesAPIError("Saldo / kuota akun Agnes AI habis ($0.00). Isi saldo Agnes AI atau gunakan model flash.")
        return AgnesAPIError(f"Akses Agnes AI ditolak (403): {detail}")
    if resp.status_code == 429:
        return AgnesAPIError(f"Batas permintaan Agnes AI tercapai (429): {detail}")
    if resp.status_code == 503:
        return AgnesAPIError(f"Antrean server Agnes AI sedang penuh (503): {detail}. Silakan coba lagi sebentar lagi.")
    return AgnesAPIError(f"Agnes AI {context} gagal [{resp.status_code}]: {detail}")


def _normalize_size(model: str, size: Optional[str]) -> str:
    if model == "agnes-video-2.5-flash":
        return "720P"
    candidate = (size or "1080P").strip().upper()
    return candidate if candidate in AGNES_SIZES else "1080P"


def agnes_chat(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 90.0,
) -> str:
    """Call Agnes AI OpenAI-compatible chat completions endpoint."""
    root = normalize_base_url(base_url)
    url = f"{root}/v1/chat/completions"
    payload = {
        "model": (model or cfg.AGNES_CHAT_MODEL or "agnes-2.5-flash").strip(),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    resp = requests.post(url, json=payload, headers=_headers(api_key), timeout=timeout)
    if resp.status_code >= 400:
        raise _format_http_error(resp, "chat")
    data = resp.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AgnesAPIError(f"Respons chat Agnes AI tidak memiliki choices: {data}")
    content = (choices[0].get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise AgnesAPIError("Respons chat Agnes AI kosong.")
    return content.strip()


def _clean_visual_fragment(text: str) -> str:
    cleaned = str(text or "").strip().strip("\"'“”‘’")
    cleaned = cleaned.replace("->", ", ")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,")
    return cleaned


def build_video_prompt(
    idea: str,
    direction: Optional[Dict[str, str]] = None,
    hook: str = "",
    plan: Optional[Dict[str, Any]] = None,
    aspect_ratio: str = "9:16",
) -> str:
    """Synthesize a concise visual-only cinematic prompt from an idea and optional scene plan."""
    _ = hook  # Spoken hook is intentionally excluded from visual-only text-to-video prompt.
    parts = [_clean_visual_fragment(idea)]
    if isinstance(direction, dict) and direction.get("summary"):
        summary = _clean_visual_fragment(str(direction["summary"]))
        if summary:
            parts.append(summary)
    if isinstance(plan, dict) and isinstance(plan.get("scenes"), list):
        visuals = [
            _clean_visual_fragment(str(scene.get("visual", "")))
            for scene in plan["scenes"]
            if isinstance(scene, dict) and _clean_visual_fragment(str(scene.get("visual", "")))
        ]
        if visuals:
            parts.append(", ".join(visuals[:4]))
    framing = "vertikal 9:16" if aspect_ratio == "9:16" else f"rasio {aspect_ratio}"
    parts.append(
        f"Sinematik realistis, gerakan kamera halus dengan close-up subjek dan aksi jelas, "
        f"pencahayaan hangat natural, suasana hidup, format {framing} tanpa teks atau dialog"
    )
    prompt = ". ".join(p for p in parts if p)
    prompt = re.sub(r"\.{2,}", ".", prompt).strip()
    return prompt[:2000]


def _sleep_with_cancel(delay: float, check_cancel: Optional[Callable[[], None]] = None) -> None:
    remaining = max(0.0, float(delay))
    while remaining > 0:
        if check_cancel:
            check_cancel()
        chunk = min(0.5, remaining)
        time.sleep(chunk)
        remaining -= chunk
    if check_cancel:
        check_cancel()


def _is_queue_full_503(resp: requests.Response) -> bool:
    if resp.status_code != 503:
        return False
    body = (resp.text or "").lower()
    detail = _extract_error_message(resp).lower()
    return "video_queue_full" in body or "queue" in detail


def submit_video(
    prompt: str,
    model: Optional[str] = None,
    duration: int = 6,
    aspect_ratio: str = "9:16",
    size: str = "720P",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    retries: int = 12,
    check_cancel: Optional[Callable[[], None]] = None,
    on_status: Optional[Callable[[str, Optional[int], str], None]] = None,
) -> str:
    """Submit a video generation task to Agnes AI and return its video_id."""
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        raise ValueError("Prompt video tidak boleh kosong.")

    chosen_model = (model or cfg.AGNES_VIDEO_MODEL or "agnes-video-2.5-flash").strip()
    if chosen_model not in AGNES_VIDEO_MODELS:
        chosen_model = "agnes-video-2.5-flash"

    chosen_ratio = aspect_ratio if aspect_ratio in AGNES_ASPECT_RATIOS else "9:16"
    chosen_duration = max(4, min(12, int(duration)))
    chosen_size = _normalize_size(chosen_model, size)

    root = normalize_base_url(base_url)
    url = f"{root}/v1/videos"
    payload = {
        "model": chosen_model,
        "mode": "text",
        "prompt": clean_prompt,
        "aspect_ratio": chosen_ratio,
        "size": chosen_size,
        "seconds": str(chosen_duration),
    }

    max_queue_retries = max(0, int(retries))
    max_transient_retries = min(3, max_queue_retries)
    queue_retry_count = 0
    transient_retry_count = 0

    while True:
        if check_cancel:
            check_cancel()
        try:
            resp = requests.post(url, json=payload, headers=_headers(api_key), timeout=60)
            if resp.status_code in (401, 403):
                raise _format_http_error(resp, "submit video")

            if _is_queue_full_503(resp):
                if queue_retry_count < max_queue_retries:
                    queue_retry_count += 1
                    if on_status:
                        pct = min(22, 10 + queue_retry_count)
                        on_status(
                            "submitting",
                            pct,
                            f"Menunggu slot antrean Agnes AI ({queue_retry_count}/{max_queue_retries})...",
                        )
                    delay = random.uniform(8.0, 10.0) + random.uniform(0.0, 1.5)
                    _sleep_with_cancel(delay, check_cancel)
                    continue
                raise _format_http_error(resp, "submit video")

            if resp.status_code in (429, 503):
                if transient_retry_count < max_transient_retries:
                    transient_retry_count += 1
                    _sleep_with_cancel(2.0 * transient_retry_count, check_cancel)
                    continue
                raise _format_http_error(resp, "submit video")

            if resp.status_code >= 400:
                raise _format_http_error(resp, "submit video")

            data = resp.json()
            inner = data.get("data") if isinstance(data.get("data"), dict) else {}
            video_id = (
                data.get("video_id")
                or data.get("id")
                or data.get("task_id")
                or inner.get("video_id")
                or inner.get("id")
            )
            if not video_id:
                raise AgnesAPIError(f"Agnes AI tidak mengembalikan video_id: {data}")
            return str(video_id)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if transient_retry_count < max_transient_retries:
                transient_retry_count += 1
                _sleep_with_cancel(2.0 * transient_retry_count, check_cancel)
                continue
            raise AgnesAPIError(f"Gagal terhubung ke Agnes AI: {exc}") from exc


def fetch_video_status(
    video_id: str,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Poll Agnes AI status endpoint for a video_id."""
    root = normalize_base_url(base_url)
    url = f"{root}/agnesapi"
    params: Dict[str, str] = {"video_id": video_id}
    if model_name:
        params["model_name"] = model_name

    resp = requests.get(url, params=params, headers=_headers(api_key), timeout=60)
    if resp.status_code >= 400:
        raise _format_http_error(resp, "cek status video")

    raw = resp.json()
    inner = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    status = str(raw.get("status") or raw.get("state") or inner.get("status") or "").strip().lower()
    video_url = raw.get("url") or raw.get("video_url") or inner.get("url") or inner.get("video_url")
    progress = raw.get("progress") if raw.get("progress") is not None else inner.get("progress")
    err_obj = raw.get("error") or inner.get("error")
    if isinstance(err_obj, dict):
        err_msg = err_obj.get("message") or err_obj.get("code") or str(err_obj)
    elif err_obj:
        err_msg = str(err_obj)
    else:
        err_msg = None

    return {
        "video_id": video_id,
        "status": status,
        "progress": progress,
        "url": video_url,
        "error": err_msg,
        "raw": raw,
    }


def download_video(video_url: str, dest_path: Path, timeout: float = 180.0) -> Path:
    """Download the rendered MP4 without Authorization header (required by Agnes CDN)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.parent / f".tmp_{dest_path.name}"
    resp = requests.get(video_url, stream=True, timeout=timeout)
    if resp.status_code >= 400:
        raise AgnesAPIError(f"Gagal mengunduh file video hasil [{resp.status_code}].")
    try:
        with open(tmp_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 128):
                if chunk:
                    fh.write(chunk)
        if tmp_path.stat().st_size == 0:
            raise AgnesAPIError("File video hasil dari Agnes AI kosong.")
        tmp_path.replace(dest_path)
        return dest_path
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def generate_video_to_file(
    prompt: str,
    dest_path: Path,
    model: Optional[str] = None,
    duration: int = 6,
    aspect_ratio: str = "9:16",
    size: str = "720P",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    poll_interval: float = 3.0,
    timeout: float = 600.0,
    check_cancel: Optional[Callable[[], None]] = None,
    on_status: Optional[Callable[[str, Optional[int], str], None]] = None,
) -> Dict[str, Any]:
    """Submit an Agnes AI video task, poll until completion, and save the MP4 locally."""
    chosen_model = (model or cfg.AGNES_VIDEO_MODEL or "agnes-video-2.5-flash").strip()
    if chosen_model not in AGNES_VIDEO_MODELS:
        chosen_model = "agnes-video-2.5-flash"

    video_id = submit_video(
        prompt=prompt,
        model=chosen_model,
        duration=duration,
        aspect_ratio=aspect_ratio,
        size=size,
        api_key=api_key,
        base_url=base_url,
        check_cancel=check_cancel,
        on_status=on_status,
    )
    if on_status:
        on_status("queued", 25, f"Tugas Agnes AI dibuat (video_id={video_id})")

    deadline = time.time() + timeout
    last_status = None
    consecutive_errors = 0
    while time.time() < deadline:
        if check_cancel:
            check_cancel()

        try:
            info = fetch_video_status(
                video_id=video_id,
                model_name=chosen_model,
                api_key=api_key,
                base_url=base_url,
            )
            consecutive_errors = 0
        except (requests.Timeout, requests.ConnectionError) as exc:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                raise AgnesAPIError(f"Koneksi terputus saat memantau video Agnes AI: {exc}") from exc
            _sleep_with_cancel(poll_interval, check_cancel)
            continue

        status = info["status"]
        pct = info["progress"] if isinstance(info["progress"], (int, float)) else None
        if status != last_status and on_status:
            on_status(status or "processing", int(pct) if pct is not None else None, f"Status Agnes AI: {status or 'processing'}")
            last_status = status

        if status in ("completed", "succeeded", "success"):
            video_url = info.get("url")
            if not video_url:
                raise AgnesAPIError("Agnes AI selesai tetapi tidak menyertakan URL video.")
            if on_status:
                on_status("downloading", 90, "Mengunduh video hasil Agnes AI...")
            download_video(str(video_url), dest_path)
            return {
                "video_id": video_id,
                "model": chosen_model,
                "remote_url": video_url,
                "file_path": str(dest_path),
            }

        if status in ("failed", "error"):
            raise AgnesAPIError(info.get("error") or "Pembuatan video di Agnes AI gagal.")

        _sleep_with_cancel(poll_interval, check_cancel)

    raise AgnesAPIError(f"Pembuatan video Agnes AI melewati batas waktu ({int(timeout)} detik).")
