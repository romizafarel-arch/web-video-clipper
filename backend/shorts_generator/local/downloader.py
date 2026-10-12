"""Local YouTube download via yt-dlp.

Returns a local mp4 path so the rest of the local pipeline can read it
directly off disk.
"""
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any, Optional

from ..config import LOCAL_OUTPUT_DIR
from ..job_manager import log_job_message


def _import_ytdlp():
    try:
        import yt_dlp  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "yt-dlp is required for --mode local. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e
    return yt_dlp


def _format_for(fmt: str) -> str:
    """Map our '720' / '1080' shorthand to a yt-dlp format selector."""
    try:
        height = int(fmt)
    except ValueError:
        height = 720
    return (
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height<={height}][ext=mp4]/best"
    )


def _extract_youtube_video_id(source: str) -> Optional[str]:
    """Best-effort extraction of a YouTube video id from a URL."""
    parsed = urlparse(source)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    if host in ("youtu.be", "www.youtu.be"):
        video_id = parsed.path.lstrip("/").split("/", 1)[0]
        return video_id or None

    if "youtube.com" in host:
        if parsed.path.startswith("/watch"):
            qs = parse_qs(parsed.query)
            video_id = qs.get("v", [""])[0]
            return video_id or None
        match = re.search(r"/(?:shorts|embed|live)/([^/?#&]+)", parsed.path)
        if match:
            return match.group(1)

    return None


def _resolve_local_path(source: str) -> Optional[str]:
    """Return a local filesystem path if the input already points at one."""
    parsed = urlparse(source)
    if parsed.scheme == "file":
        raw_path = unquote(parsed.path)
        if parsed.netloc and parsed.netloc not in ("", "localhost"):
            raw_path = f"//{parsed.netloc}{raw_path}"
        candidate = Path(raw_path).expanduser()
        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())
        raise RuntimeError(f"Local file URL does not exist: {source}")

    if parsed.scheme in ("http", "https"):
        return None

    candidate = Path(source).expanduser()
    if candidate.exists() and candidate.is_file():
        return str(candidate.resolve())

    if any(sep in source for sep in (os.sep, "/")) or source.startswith("~") or source.startswith("."):
        raise RuntimeError(f"Local file path does not exist: {source}")

    return None


def _existing_download(out_dir: str, video_id: str, fmt: str = "720") -> Optional[str]:
    """Return a cached download path matching the requested format if available."""
    search_dirs = [out_dir]
    if LOCAL_OUTPUT_DIR and os.path.exists(LOCAL_OUTPUT_DIR):
        search_dirs.append(LOCAL_OUTPUT_DIR)
        try:
            for entry in os.scandir(LOCAL_OUTPUT_DIR):
                if entry.is_dir() and entry.path != out_dir:
                    search_dirs.append(entry.path)
        except OSError:
            pass

    # Format-specific cache first
    for d in search_dirs:
        for ext in (".mp4", ".mkv", ".webm"):
            candidate = os.path.join(d, f"source_{video_id}_{fmt}p{ext}")
            if os.path.exists(candidate) and os.path.getsize(candidate) > 1000:
                return candidate

    # Fallback to generic unformatted source
    for d in search_dirs:
        for ext in (".mp4", ".mkv", ".webm"):
            candidate = os.path.join(d, f"source_{video_id}{ext}")
            if os.path.exists(candidate) and os.path.getsize(candidate) > 1000:
                return candidate
    return None


def download_youtube_local(
    video_url: str,
    fmt: str = "720",
    out_dir: Optional[str] = None,
    job_ctx: Optional[Any] = None,
    cookies_path: Optional[str] = None,
) -> str:
    """Download a remote URL or return a local file path unchanged."""
    local_path = _resolve_local_path(video_url)
    if local_path:
        log_job_message(f"[download/local] using local file: {local_path}", job_ctx=job_ctx)
        return local_path

    yt_dlp = _import_ytdlp()
    out_dir = out_dir or LOCAL_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    video_id = _extract_youtube_video_id(video_url)
    if video_id:
        cached = _existing_download(out_dir, video_id, fmt=fmt)
        if cached:
            log_job_message(f"[download/local] reusing cached download ({fmt}p): {cached}", job_ctx=job_ctx)
            return cached

    log_job_message(f"[download/local] {video_url} @ {fmt}p → {out_dir}/", job_ctx=job_ctx)
    ydl_opts = {
        "format": _format_for(fmt),
        "outtmpl": os.path.join(out_dir, f"source_%(id)s_{fmt}p.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 15,
        "fragment_retries": 15,
        "continuedl": True,
        "concurrent_fragment_downloads": 8,
    }
    if cookies_path and os.path.isfile(cookies_path):
        ydl_opts["cookiefile"] = str(cookies_path)
        log_job_message(f"[download/local] Menggunakan file cookies YouTube: {os.path.basename(cookies_path)}", job_ctx=job_ctx)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        path = ydl.prepare_filename(info)
        # merge_output_format may rename the extension after merge
        if not os.path.exists(path):
            stem, _ = os.path.splitext(path)
            for ext in (".mp4", ".mkv", ".webm"):
                if os.path.exists(stem + ext):
                    path = stem + ext
                    break

    log_job_message(f"[download/local] ready: {path}", job_ctx=job_ctx)
    return path
