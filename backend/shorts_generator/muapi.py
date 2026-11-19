"""Thin MuAPI client: submit a job, poll until it finishes, return the result."""
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from . import config as cfg
from .config import (
    MUAPI_BASE_URL,
    POLL_INTERVAL_SECONDS,
    POLL_TIMEOUT_SECONDS,
    require_api_key,
)


class MuAPIError(RuntimeError):
    pass


def _base_url(base_url: Optional[str] = None) -> str:
    return (base_url or getattr(cfg, "MUAPI_BASE_URL", None) or MUAPI_BASE_URL).strip().rstrip("/")


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    key = (api_key or getattr(cfg, "MUAPI_API_KEY", None) or require_api_key()).strip()
    if not key or key == "your_muapi_key_here":
        raise MuAPIError("MUAPI_API_KEY belum disetel. Isi kunci MuAPI di Pengaturan.")
    return {
        "Content-Type": "application/json",
        "x-api-key": key,
    }


def submit(endpoint: str, payload: Dict[str, Any], retries: int = 3) -> str:
    """POST to /api/v1/{endpoint} and return the request_id; retry transient errors."""
    url = f"{MUAPI_BASE_URL}/{endpoint.lstrip('/')}"
    last_err: Optional[Exception] = None
    for _ in range(retries):
        try:
            resp = requests.post(url, json=payload, headers=_headers(), timeout=120)
            if resp.status_code >= 400:
                raise MuAPIError(f"{endpoint} submit failed [{resp.status_code}]: {resp.text}")
            data = resp.json()
            request_id = data.get("request_id") or data.get("id")
            if not request_id:
                raise MuAPIError(f"{endpoint} response had no request_id: {data}")
            return str(request_id)
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            time.sleep(2)
    raise MuAPIError(f"{endpoint} submit failed after {retries} retries: {last_err}")


def fetch_result(request_id: str, retries: int = 3) -> Dict[str, Any]:
    """GET the latest result for a request_id; retry on transient timeouts."""
    url = f"{MUAPI_BASE_URL}/predictions/{request_id}/result"
    last_err: Optional[Exception] = None
    for _ in range(retries):
        try:
            resp = requests.get(url, headers=_headers(), timeout=90)
            if resp.status_code >= 400:
                raise MuAPIError(f"poll failed [{resp.status_code}]: {resp.text}")
            return resp.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            time.sleep(2)
    raise MuAPIError(f"poll failed after {retries} retries: {last_err}")


def poll(
    request_id: str,
    interval: float = POLL_INTERVAL_SECONDS,
    timeout: float = POLL_TIMEOUT_SECONDS,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Block until the prediction is done; return the final payload."""
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        data = fetch_result(request_id)
        status = (data.get("status") or "").lower()
        if status and status != last_status:
            print(f"[muapi] {label or request_id}: {status}", flush=True)
            last_status = status

        if status in ("completed", "succeeded", "success"):
            return data
        if status in ("failed", "error"):
            raise MuAPIError(f"{label or request_id} failed: {data}")

        time.sleep(interval)

    raise MuAPIError(f"{label or request_id} timed out after {timeout}s")


def run(
    endpoint: str,
    payload: Dict[str, Any],
    label: Optional[str] = None,
    interval: float = POLL_INTERVAL_SECONDS,
    timeout: float = POLL_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Submit then poll. Returns the final result payload."""
    request_id = submit(endpoint, payload)
    return poll(request_id, interval=interval, timeout=timeout, label=label or endpoint)


def list_text_to_video_models(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 15.0,
) -> List[Dict[str, Any]]:
    """Fetch enabled prompt-based Text-to-Video models from MuAPI /models."""
    root = _base_url(base_url)
    resp = requests.get(f"{root}/models", headers=_headers(api_key), timeout=timeout)
    if resp.status_code >= 400:
        raise MuAPIError(f"Gagal mengambil daftar model MuAPI [{resp.status_code}]: {resp.text[:200]}")

    raw_models = resp.json().get("models", [])
    if not isinstance(raw_models, list):
        return []

    popular_families = {"veo3.1", "veo3", "veo", "sora", "kling", "wan", "seedance", "grok", "runway"}
    items: List[Dict[str, Any]] = []
    for m in raw_models:
        if not isinstance(m, dict):
            continue
        category = str(m.get("category") or "").lower()
        if "text to video" not in category:
            continue
        if not m.get("is_enabled") or m.get("is_coming_soon"):
            continue
        req_fields = m.get("required_fields") or []
        if req_fields != ["prompt"]:
            continue

        model_id = str(m.get("name") or "").strip()
        endpoint_url = str(m.get("endpoint_url") or model_id).strip().lstrip("/")
        if not model_id or not endpoint_url:
            continue

        family = str(m.get("family") or "other").strip() or "other"
        cost = m.get("cost")
        cost_label = f" (${cost:.2f})" if isinstance(cost, (int, float)) else ""
        items.append({
            "id": model_id,
            "name": f"{model_id}{cost_label}",
            "endpoint_url": endpoint_url,
            "family": family,
            "description": str(m.get("description") or "").strip(),
            "cost": cost if isinstance(cost, (int, float)) else None,
            "input_fields": [str(f) for f in (m.get("input_fields") or []) if isinstance(f, str)],
            "recommended": family.lower() in popular_families or any(
                k in model_id.lower() for k in ("veo", "sora", "kling", "wan3", "seedance-2.5", "grok-imagine", "runway")
            ),
        })

    items.sort(key=lambda x: (not x.get("recommended", False), str(x.get("family") or ""), x["id"]))
    return items


def get_model_input_schema(
    model_id: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Fetch normalized input parameter constraints for a MuAPI model."""
    root = _base_url(base_url)
    resp = requests.get(f"{root}/models/{model_id.strip()}", headers=_headers(api_key), timeout=timeout)
    if resp.status_code >= 400:
        raise MuAPIError(f"Gagal mengambil skema model MuAPI {model_id} [{resp.status_code}]")

    data = resp.json()
    props = (
        data.get("input_schema", {})
        .get("schemas", {})
        .get("input_data", {})
        .get("properties", {})
    )
    if not isinstance(props, dict):
        props = {}

    schema: Dict[str, Any] = {
        "endpoint_url": str(data.get("endpoint_url") or model_id).strip().lstrip("/"),
        "input_fields": [str(f) for f in (data.get("input_fields") or list(props.keys())) if isinstance(f, str)],
    }
    for key in ("aspect_ratio", "duration", "resolution"):
        prop = props.get(key)
        if not isinstance(prop, dict):
            continue
        entry: Dict[str, Any] = {}
        if isinstance(prop.get("enum"), list) and prop["enum"]:
            entry["enum"] = prop["enum"]
        if prop.get("default") is not None:
            entry["default"] = prop["default"]
        if prop.get("type"):
            entry["type"] = prop["type"]
        schema[key] = entry
    return schema


def _extract_media_url(result: Dict[str, Any]) -> str:
    for key in ("video_url", "url", "output_url", "result_url", "video"):
        v = result.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v

    for container_key in ("outputs", "output", "result", "data"):
        container = result.get(container_key)
        if isinstance(container, dict):
            for key in ("video_url", "url", "output_url", "video"):
                v = container.get(key)
                if isinstance(v, str) and v.startswith("http"):
                    return v
        elif isinstance(container, list):
            for item in container:
                if isinstance(item, str) and item.startswith("http"):
                    return item
                if isinstance(item, dict):
                    for key in ("video_url", "url", "output_url", "video"):
                        v = item.get(key)
                        if isinstance(v, str) and v.startswith("http"):
                            return v

    raise MuAPIError(f"MuAPI selesai tetapi tidak menyertakan URL video: {result}")


def _sleep_with_cancel(seconds: float, check_cancel: Optional[Callable[[], None]]) -> None:
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        if check_cancel:
            check_cancel()
        time.sleep(min(0.5, max(0.05, deadline - time.time())))


def generate_video_to_file(
    prompt: str,
    dest_path: Path,
    endpoint_url: str,
    payload_options: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    poll_interval: float = 3.0,
    timeout: float = 600.0,
    check_cancel: Optional[Callable[[], None]] = None,
    on_status: Optional[Callable[[str, Optional[int], str], None]] = None,
) -> Dict[str, Any]:
    """Submit a MuAPI text-to-video task, poll until done, and download the MP4."""
    root = _base_url(base_url)
    headers = _headers(api_key)
    endpoint = endpoint_url.strip().lstrip("/")
    payload: Dict[str, Any] = {"prompt": prompt}
    if payload_options:
        for k, v in payload_options.items():
            if v is not None and v != "":
                payload[k] = v

    if check_cancel:
        check_cancel()
    if on_status:
        on_status("submitting", 15, f"Mengirim prompt ke MuAPI ({endpoint})...")

    resp = requests.post(f"{root}/{endpoint}", json=payload, headers=headers, timeout=120)
    if resp.status_code >= 400:
        raise MuAPIError(f"MuAPI {endpoint} gagal [{resp.status_code}]: {resp.text[:300]}")
    sub_data = resp.json()
    request_id = str(sub_data.get("request_id") or sub_data.get("id") or "").strip()
    if not request_id:
        raise MuAPIError(f"MuAPI {endpoint} tidak mengembalikan request_id: {sub_data}")

    if on_status:
        on_status("queued", 25, f"Tugas MuAPI dibuat (request_id={request_id})")

    deadline = time.time() + timeout
    last_status = None
    consecutive_errors = 0
    while time.time() < deadline:
        if check_cancel:
            check_cancel()
        try:
            poll_resp = requests.get(f"{root}/predictions/{request_id}/result", headers=headers, timeout=90)
            if poll_resp.status_code >= 400:
                raise MuAPIError(f"MuAPI status gagal [{poll_resp.status_code}]: {poll_resp.text[:200]}")
            info = poll_resp.json()
            consecutive_errors = 0
        except (requests.Timeout, requests.ConnectionError) as exc:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                raise MuAPIError(f"Koneksi terputus saat memantau MuAPI: {exc}") from exc
            _sleep_with_cancel(poll_interval, check_cancel)
            continue

        status = str(info.get("status") or "").strip().lower()
        if status and status != last_status:
            pct = 45 if status in ("queued", "pending") else 70 if status in ("processing", "running", "in_progress") else None
            if on_status:
                on_status(status, pct, f"Status MuAPI ({endpoint}): {status}")
            last_status = status

        if status in ("completed", "succeeded", "success"):
            video_url = _extract_media_url(info)
            if on_status:
                on_status("downloading", 90, "Mengunduh video hasil MuAPI...")
            dl_resp = requests.get(video_url, stream=True, timeout=180)
            if dl_resp.status_code >= 400:
                raise MuAPIError(f"Gagal mengunduh video hasil MuAPI [{dl_resp.status_code}].")
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            total_bytes = 0
            with open(dest_path, "wb") as f:
                for chunk in dl_resp.iter_content(chunk_size=1024 * 256):
                    if check_cancel:
                        check_cancel()
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)
            if total_bytes == 0:
                raise MuAPIError("File video hasil dari MuAPI kosong.")
            return {
                "request_id": request_id,
                "model": endpoint,
                "remote_url": video_url,
                "file_path": str(dest_path),
            }

        if status in ("failed", "error"):
            err_detail = info.get("error") or info.get("message") or info
            raise MuAPIError(f"Pembuatan video MuAPI gagal: {err_detail}")

        _sleep_with_cancel(poll_interval, check_cancel)

    raise MuAPIError(f"Pembuatan video MuAPI melewati batas waktu ({int(timeout)} detik).")
