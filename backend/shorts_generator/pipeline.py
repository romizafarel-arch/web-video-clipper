"""End-to-end orchestrator.

Two modes:
  * mode="api"   (default) — MuAPI does download / transcribe / LLM / autocrop.
                              Fast, no local deps, pay-per-call.
  * mode="local"            — yt-dlp + faster-whisper + OpenAI or Gemini + ffmpeg/opencv.
                              Self-hosted, LLM_PROVIDER selects OpenAI or Gemini.
"""
from typing import Any, Dict, List, Optional

from .clipper import crop_highlights
from .downloader import download_youtube
from .highlights import call_muapi_llm, get_highlights
from .job_manager import log_job_message
from .transcriber import transcribe


def cleanup_source_video(
    source_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    job_ctx: Optional[Any] = None,
) -> List[str]:
    """Safely delete raw source video file(s) while strictly preserving shorts, subtitles, and metadata."""
    import gc
    import time
    from pathlib import Path

    deleted_files: List[str] = []
    targets: set = set()

    # 1. Target directly from source_path if it's a source_* file
    if source_path:
        p = Path(source_path).resolve()
        if p.is_file() and p.name.startswith("source_"):
            targets.add(p)

    # 2. Target any source_* video/temp files inside out_dir
    if out_dir:
        out_p = Path(out_dir).resolve()
        if out_p.is_dir():
            for item in out_p.glob("source_*"):
                if (
                    item.is_file()
                    and item.name.startswith("source_")
                    and not item.name.startswith("short_")
                    and not item.name.startswith("job_")
                    and not item.name.endswith(".vtt")
                    and not item.name.endswith(".json")
                ):
                    targets.add(item.resolve())

    # Release any lingering file handles before deletion
    gc.collect()

    for target in targets:
        for attempt in range(3):
            try:
                if target.exists():
                    target.unlink()
                    deleted_files.append(str(target))
                    log_job_message(f"[cleanup] File video sumber mentahan berhasil dihapus: {target.name}", job_ctx=job_ctx)
                break
            except (PermissionError, OSError) as pe:
                if attempt < 2:
                    time.sleep(0.3)
                    gc.collect()
                else:
                    log_job_message(f"[cleanup/warning] Tidak dapat menghapus file sumber {target.name}: {pe}", job_ctx=job_ctx)
            except Exception as e:
                log_job_message(f"[cleanup/warning] Kesalahan saat menghapus {target.name}: {e}", job_ctx=job_ctx)
                break

    return deleted_files


def _run_local(
    youtube_url: str,
    num_clips: int,
    aspect_ratio: str,
    download_format: str,
    language: Optional[str],
    out_dir: Optional[str] = None,
    config: Optional[Dict] = None,
    job_ctx: Optional[Any] = None,
    framing_mode: str = "podcast",
    subtitle_style: str = "karaoke",
    gaming_preset: str = "auto",
    gaming_custom_box: Optional[Dict] = None,
    auto_delete_source_video: Optional[bool] = None,
    font_family: Optional[str] = None,
    cookies_path: Optional[str] = None,
    gaming_layout: Optional[str] = None,
    enable_sfx: bool = True,
    remove_silence: bool = False,
) -> Dict:
    import uuid
    from datetime import datetime
    import os
    from .config import LOCAL_OUTPUT_DIR
    from .local.clipper import crop_highlights_local
    from .local.downloader import download_youtube_local
    from .local.llm import create_llm_callable
    from .local.transcriber import transcribe_local

    cfg_dict = config or {}
    if out_dir is None:
        session_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.join(LOCAL_OUTPUT_DIR, f"{timestamp}_{session_id}")
    os.makedirs(out_dir, exist_ok=True)

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    source_path = download_youtube_local(
        youtube_url,
        fmt=download_format,
        out_dir=out_dir,
        job_ctx=job_ctx,
        cookies_path=cookies_path,
    )

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    trans_provider = cfg_dict.get("transcriber_provider")
    trans_model = (
        cfg_dict.get("gemini_transcriber_model")
        if trans_provider == "gemini"
        else cfg_dict.get("whisper_model")
    )
    transcript = transcribe_local(
        source_path,
        language=language,
        provider=trans_provider,
        model=trans_model,
        config=cfg_dict,
        job_ctx=job_ctx,
    )
    if not transcript.get("segments"):
        raise RuntimeError(
            "Transkripsi audio tidak menghasilkan segmen percakapan. Video mungkin tidak memiliki suara atau dialog yang dapat dideteksi."
        )

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    llm_fn = create_llm_callable(config=cfg_dict, job_ctx=job_ctx)
    highlights_result = get_highlights(
        transcript,
        num_clips=num_clips,
        llm_fn=llm_fn,
        job_ctx=job_ctx,
        framing_mode=framing_mode,
        media_path=source_path,
    )
    all_highlights: List[Dict] = highlights_result.get("highlights", [])
    if not all_highlights:
        raise RuntimeError("Highlight generator tidak menemukan segmen kandidat.")

    top = sorted(all_highlights, key=lambda h: int(h.get("score", 0)), reverse=True)[:num_clips]
    log_job_message(f"[pipeline/local] cropping {len(top)} of {len(all_highlights)} candidates into {out_dir}", job_ctx=job_ctx)

    if job_ctx is not None and hasattr(job_ctx, "pipeline_context"):
        job_ctx.pipeline_context = {
            "mode": "local",
            "source_video_url": source_path,
            "transcript": transcript,
            "highlights": all_highlights,
        }

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    shorts = crop_highlights_local(
        source_path,
        top,
        aspect_ratio=aspect_ratio,
        out_dir=out_dir,
        transcript=transcript,
        job_ctx=job_ctx,
        framing_mode=framing_mode,
        subtitle_style=subtitle_style,
        gaming_preset=gaming_preset,
        gaming_custom_box=gaming_custom_box,
        font_family=font_family,
        gaming_layout=gaming_layout,
        enable_sfx=enable_sfx,
        remove_silence=remove_silence,
    )

    success_count = sum(1 for s in shorts if s.get("clip_url"))
    stats = {
        "total": len(shorts),
        "success": success_count,
        "failed": len(shorts) - success_count,
    }

    # Auto-cleanup raw source video if enabled and clips were successfully rendered
    should_delete = auto_delete_source_video
    if should_delete is None:
        if config and "auto_delete_source_video" in config:
            should_delete = bool(config["auto_delete_source_video"])
        else:
            from .config import AUTO_DELETE_SOURCE_VIDEO
            should_delete = AUTO_DELETE_SOURCE_VIDEO

    deleted_sources: List[str] = []
    if should_delete and success_count > 0:
        try:
            deleted_sources = cleanup_source_video(source_path, out_dir=out_dir, job_ctx=job_ctx)
        except Exception as e:
            log_job_message(f"[cleanup/warning] Auto-cleanup error: {e}", job_ctx=job_ctx)

    return {
        "mode": "local",
        "source_video_url": source_path,
        "source_deleted": bool(deleted_sources),
        "deleted_sources": deleted_sources,
        "transcript": transcript,
        "highlights": all_highlights,
        "shorts": shorts,
        "out_dir": out_dir,
        "stats": stats,
    }


def _run_api(
    youtube_url: str,
    num_clips: int,
    aspect_ratio: str,
    download_format: str,
    language: Optional[str],
    job_ctx: Optional[Any] = None,
) -> Dict:
    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    source_url = download_youtube(youtube_url, fmt=download_format)

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    transcript = transcribe(source_url, language=language)
    if not transcript["segments"]:
        raise RuntimeError(
            "Whisper produced no segments. The video may have no detectable speech."
        )

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    highlights_result = get_highlights(transcript, num_clips=num_clips, llm_fn=call_muapi_llm, job_ctx=job_ctx)
    all_highlights: List[Dict] = highlights_result.get("highlights", [])
    if not all_highlights:
        raise RuntimeError("Highlight generator returned zero clips.")

    top = sorted(all_highlights, key=lambda h: int(h.get("score", 0)), reverse=True)[:num_clips]
    log_job_message(f"[pipeline] cropping {len(top)} of {len(all_highlights)} candidates", job_ctx=job_ctx)

    if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
        job_ctx.check_cancellation_or_timeout()

    shorts = crop_highlights(source_url, top, aspect_ratio=aspect_ratio)
    success_count = sum(1 for s in shorts if s.get("clip_url"))
    stats = {
        "total": len(shorts),
        "success": success_count,
        "failed": len(shorts) - success_count,
    }

    return {
        "mode": "api",
        "source_video_url": source_url,
        "transcript": transcript,
        "highlights": all_highlights,
        "shorts": shorts,
        "stats": stats,
    }


def generate_shorts(
    youtube_url: str,
    num_clips: int = 3,
    aspect_ratio: str = "9:16",
    download_format: str = "720",
    language: Optional[str] = None,
    mode: str = "api",
    out_dir: Optional[str] = None,
    config: Optional[Dict] = None,
    job_ctx: Optional[Any] = None,
    framing_mode: str = "podcast",
    subtitle_style: str = "karaoke",
    gaming_preset: str = "auto",
    gaming_custom_box: Optional[Dict] = None,
    auto_delete_source_video: Optional[bool] = None,
    font_family: Optional[str] = None,
    cookies_path: Optional[str] = None,
    gaming_layout: Optional[str] = None,
    enable_sfx: bool = True,
    remove_silence: bool = False,
) -> Dict:
    """Run the full pipeline and return a structured result.

    Args:
        youtube_url: source URL.
        num_clips: how many shorts to render.
        aspect_ratio: e.g. "9:16", "1:1".
        download_format: source resolution ("360" / "480" / "720" / "1080").
        language: ISO-639-1 to force Whisper language detection.
        mode: "api" (default, MuAPI) or "local" (yt-dlp + faster-whisper +
            OpenAI or Gemini + ffmpeg).
        out_dir: directory to store generated shorts in local mode.
        config: optional dictionary with isolated LLM & transcriber settings.
        job_ctx: optional JobContext for cancellation and timeout monitoring.
        framing_mode: framing style for local crop ("podcast", "single", "center", "gaming").
        subtitle_style: animation/style for subtitles ("karaoke", "kinetic", "classic", "none").
        gaming_preset: layout preset for 3-layer gaming stack.
        gaming_custom_box: custom bounding boxes for top, mid, bottom layers.
        auto_delete_source_video: whether to delete raw downloaded YouTube video after render.
        font_family: custom font family name to override subtitle font.
        cookies_path: optional path to YouTube cookies.txt file for yt-dlp authentication.
        gaming_layout: optional vertical stack layout ('cam_top' for Windah style, 'cam_bottom' for classic).

    Returns:
        {
          "mode": "api" | "local",
          "source_video_url": str,
          "transcript": {...},
          "highlights": [...],
          "shorts": [...],
          "stats": {"total": int, "success": int, "failed": int}
        }
    """
    mode = (mode or "api").lower()
    if mode == "local":
        return _run_local(
            youtube_url,
            num_clips,
            aspect_ratio,
            download_format,
            language,
            out_dir=out_dir,
            config=config,
            job_ctx=job_ctx,
            framing_mode=framing_mode,
            subtitle_style=subtitle_style,
            gaming_preset=gaming_preset,
            gaming_custom_box=gaming_custom_box,
            auto_delete_source_video=auto_delete_source_video,
            font_family=font_family,
            cookies_path=cookies_path,
            gaming_layout=gaming_layout,
        enable_sfx=enable_sfx,
        remove_silence=remove_silence,
        )
    if mode == "api":
        return _run_api(youtube_url, num_clips, aspect_ratio, download_format, language, job_ctx=job_ctx)
    raise ValueError(f"Unknown mode: {mode!r}. Use 'api' or 'local'.")
