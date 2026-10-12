"""Local LLM backend — OpenAI or Gemini, selected by LLM_PROVIDER."""
import time
from typing import Any, Optional

from .. import config as cfg
from ..config import require_gemini_key, require_openai_key
from ..job_manager import log_job_message


def call_openai_llm(
    prompt: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    job_ctx: Optional[Any] = None,
) -> str:
    """OpenAI Chat Completions backend used by --mode local (supports custom base_url like APMIX)."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "openai is required for --mode local. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    target_model = (model or cfg.OPENAI_MODEL or "gpt-4o-mini").strip()
    key = api_key or require_openai_key()
    client_kwargs = {"api_key": key}
    effective_base_url = base_url if base_url is not None else cfg.OPENAI_BASE_URL
    if effective_base_url:
        client_kwargs["base_url"] = effective_base_url
        log_job_message(f"[llm/local] Using custom OpenAI base URL: {effective_base_url} (model={target_model})", job_ctx=job_ctx)
    else:
        log_job_message(f"[llm/local] Using OpenAI model: {target_model}", job_ctx=job_ctx)

    client = OpenAI(**client_kwargs)
    response = client.chat.completions.create(
        model=target_model,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def call_gemini_llm(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    job_ctx: Optional[Any] = None,
) -> str:
    """Gemini backend used by --mode local when LLM_PROVIDER=gemini."""
    try:
        from google import genai  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "google-genai is required for LLM_PROVIDER=gemini. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    target_model = (model or cfg.GEMINI_MODEL or "gemini-3.5-flash").strip()
    # Normalize model prefix if needed
    if target_model.startswith("models/"):
        target_model = target_model[7:]

    models_to_try = [target_model]
    if target_model != "gemini-3.5-flash-lite":
        models_to_try.append("gemini-3.5-flash-lite")

    key = api_key or require_gemini_key()
    client = genai.Client(api_key=key)

    last_err = None
    for cur_model in models_to_try:
        log_job_message(f"[llm/local] Using Gemini model: {cur_model}", job_ctx=job_ctx)
        for attempt in range(1, 4):
            if job_ctx is not None and hasattr(job_ctx, "check_cancellation_or_timeout"):
                job_ctx.check_cancellation_or_timeout()
            try:
                response = client.models.generate_content(
                    model=cur_model,
                    contents=prompt,
                    config={
                        "temperature": 0.2,
                        "response_mime_type": "application/json",
                        "max_output_tokens": 8192,
                    },
                )
                return response.text or ""
            except Exception as e:
                last_err = e
                err_str = str(e)
                if ("503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < 3:
                    log_job_message(f"[llm/local] Gemini model {cur_model} busy/rate-limited (attempt {attempt}/3), retrying in {attempt * 2}s...", job_ctx=job_ctx)
                    time.sleep(attempt * 2)
                    continue
                break
        if cur_model != models_to_try[-1]:
            log_job_message(f"[llm/local] Model {cur_model} unavailable ({last_err}), falling back to {models_to_try[-1]}...", job_ctx=job_ctx)

    if last_err:
        raise last_err
    return ""


def create_llm_callable(config: Optional[dict] = None, job_ctx: Optional[Any] = None):
    """Return an isolated LLM function driven by the provided job config snapshot."""
    cfg_dict = config or {}
    provider = (cfg_dict.get("llm_provider") or getattr(cfg, "LLM_PROVIDER", "gemini")).strip().lower()
    if provider == "openai":
        model = cfg_dict.get("openai_model") or getattr(cfg, "OPENAI_MODEL", "gpt-4o-mini")
        base_url = cfg_dict.get("openai_base_url") if "openai_base_url" in cfg_dict else getattr(cfg, "OPENAI_BASE_URL", None)
        api_key = cfg_dict.get("openai_api_key") or getattr(cfg, "OPENAI_API_KEY", None)
        return lambda prompt: call_openai_llm(prompt, model=model, base_url=base_url, api_key=api_key, job_ctx=job_ctx)
    elif provider == "gemini":
        model = cfg_dict.get("gemini_model") or getattr(cfg, "GEMINI_MODEL", "gemini-3.5-flash")
        api_key = cfg_dict.get("gemini_api_key") or getattr(cfg, "GEMINI_API_KEY", None)
        return lambda prompt: call_gemini_llm(prompt, model=model, api_key=api_key, job_ctx=job_ctx)
    raise RuntimeError(
        f"Unknown LLM_PROVIDER={provider!r}. Use 'openai' or 'gemini'."
    )


def call_local_llm(prompt: str, model: Optional[str] = None) -> str:
    """Dispatch to the configured local LLM provider."""
    provider = (cfg.LLM_PROVIDER or "gemini").strip().lower()
    if provider == "openai":
        return call_openai_llm(prompt, model=model)
    if provider == "gemini":
        return call_gemini_llm(prompt, model=model)
    raise RuntimeError(
        f"Unknown LLM_PROVIDER={provider!r}. Use 'openai' or 'gemini'."
    )
