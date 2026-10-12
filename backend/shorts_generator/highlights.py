"""Find the most viral-worthy highlights in a transcript.

Logic ported from ViralVadoo's transcript_analysis/highlight_generator.py:
  - content-type / density detection
  - chunking for long videos with overlap
  - virality-criteria prompt
  - score-based dedupe with overlap suppression

The LLM call is pluggable via the `llm_fn` argument so the same prompts can
drive either MuAPI (default, --mode api) or a direct local LLM client
(--mode local).
"""
import json
import math
import os
import re
from typing import Any, Callable, Dict, List, Optional

from . import muapi
from .audio_peaks import boost_highlights_with_audio_peaks, scan_audio_energy
from .job_manager import log_job_message


LLMFn = Callable[[str], str]


CONTENT_TYPE_PROMPT = """Analyze this video transcript sample and classify the content type.
Choose one: podcast, interview, tutorial, lecture, commentary, debate, vlog, gaming, other.
Also estimate content density: low (mostly filler/chit-chat), medium, or high (dense info/stories).
Respond with JSON only: {"content_type": "...", "density": "..."}"""


VIRALITY_CRITERIA = """
Virality signals to prioritize (ranked by impact):
1. HOOK MOMENTS — statements that create immediate curiosity ("The secret is...", "Nobody talks about...", "I was completely wrong about...")
2. EMOTIONAL PEAKS — genuine surprise, laughter, anger, vulnerability, excitement; raw unscripted reactions
3. OPINION BOMBS — strong, polarizing or counter-intuitive statements that trigger agree/disagree
4. REVELATION MOMENTS — surprising facts, stats, or confessions that reframe how the viewer thinks
5. CONFLICT/TENSION — disagreement, pushback, or a problem being confronted head-on
6. QUOTABLE ONE-LINERS — a sentence that works as a standalone quote card
7. STORY PEAKS — the climax or twist of an anecdote; the payoff moment
8. PRACTICAL VALUE — a concrete tip, hack, or insight the viewer can immediately apply
"""


HIGHLIGHT_SYSTEM_PROMPT = """You are an elite short-form video editor who has studied thousands of viral clips on TikTok, Instagram Reels, and YouTube Shorts. You know exactly what makes viewers stop scrolling, watch to the end, and share.

{virality_criteria}

Content type: {content_type} | Density: {density}

Your task: identify the most viral-worthy highlights from the transcript.

Rules:
- Every highlight must open with a strong HOOK — a line that grabs attention within the first 3 seconds
- Duration sweet spot: 45-90 seconds. Go shorter (20-44s) only for a perfect standalone one-liner. Go longer (91-180s) only when a story arc needs full context to land
- Never cut mid-sentence or mid-thought — each clip must feel complete and self-contained
- Clips must not overlap significantly with each other
- Score 0-100 on viral potential (not general quality)
- {num_clips_instruction}
- For each highlight, identify the single best "hook_sentence" — the opening line that would make someone stop scrolling
- Explain in one sentence why this clip is viral ("virality_reason")

Respond ONLY with valid JSON (no markdown, no explanation):
{{"highlights":[{{"title":"string","start_time":float,"end_time":float,"score":int,"hook_sentence":"string","virality_reason":"string"}}]}}"""


GAMING_VIRALITY_CRITERIA = """
Gaming party stream virality signals to prioritize (ranked by impact):
1. SCREAMS & JUMPSCARES — intense screams, panic reactions, jumpscare screams, sudden volume bursts, horror moments ("WHAT IS THAT?!", "NOOOO!", high-pitch panic)
2. CHAOS & UNCONTROLLABLE LAUGHTER — wheezing laughter, collective party wheezing, trolling, hilarious game physics glitches, absurdity
3. ROASTING & DISCORD BANTER — savage banter between party members, friendly betrayals, instant karma, funny misunderstandings in voice chat
4. CLUTCH OR FAIL MOMENTS — insane 1vX clutch, last-second win, or catastrophic hilarious throw/choke
5. RAGE & BAFFLEMENT — unexpected defeat reactions, genuine disbelief, funny rage quits or desk slams
6. QUICK FUNNY ONE-LINERS / MEMES — witty gamer quips and viral punchlines
"""


GAMING_HIGHLIGHT_SYSTEM_PROMPT = """You are an elite gaming short-form video editor specializing in viral TikToks, YouTube Shorts, and Twitch/Discord party clips. You know exactly what energetic, hilarious, or high-stakes moments make viewers stop scrolling and share with friends.

{virality_criteria}

Content type: {content_type} | Density: {density}

Your task: identify the most viral, hilarious, and high-energy gaming highlights from the stream transcript.

Rules:
- Prioritize high-energy moments: screams, jumpscares, chaotic group laughter, Discord roasting/banter, clutches, and epic fails
- Duration sweet spot: 20-60 seconds. Keep clips punchy, dynamic, and fast-paced
- Every highlight must capture the buildup, the climax (scream/reaction/fail/clutch), and the immediate aftermath
- Never cut mid-sentence or mid-reaction — each clip must feel complete and punchy
- Clips must not overlap significantly with each other
- Score 0-100 on viral gaming potential
- {num_clips_instruction}
- For each highlight, identify the single best "hook_sentence" — the attention-grabbing opening line or reaction
- Explain in one sentence why this clip is viral ("virality_reason")

Respond ONLY with valid JSON (no markdown, no explanation):
{{"highlights":[{{"title":"string","start_time":float,"end_time":float,"score":int,"hook_sentence":"string","virality_reason":"string"}}]}}"""


CHUNK_SIZE_SECONDS = 1200       # 20-min chunks for long videos
LONG_VIDEO_THRESHOLD = 1800     # chunk videos longer than 30 min
CHUNK_OVERLAP_SECONDS = 60
GPT_CALL_TIMEOUT_SECONDS = 300  # cap LLM polls at 5 min — a wedged call should fail fast
MAX_HIGHLIGHT_API_ATTEMPTS = 3


def call_muapi_llm(prompt: str) -> str:
    """Default LLM backend: MuAPI gpt-5-mini."""
    result = muapi.run(
        "gpt-5-mini",
        {"prompt": prompt},
        label="gpt-5-mini",
        timeout=GPT_CALL_TIMEOUT_SECONDS,
    )

    outputs = result.get("outputs")
    if isinstance(outputs, list) and outputs and isinstance(outputs[0], str) and outputs[0].strip():
        return outputs[0]

    for key in ("output", "text", "response", "result", "content"):
        v = result.get(key)
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, dict):
            inner = v.get("text") or v.get("content")
            if isinstance(inner, str) and inner.strip():
                return inner
        if isinstance(v, list) and v and isinstance(v[0], str):
            return v[0]

    raise RuntimeError(f"Could not extract gpt-5-mini text from response: {result}")


def _parse_json_loose(raw: str) -> Dict:
    """gpt-5-4 sometimes wraps JSON in markdown fences — strip and parse."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


def _coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        val = float(value)
        if not math.isfinite(val):
            return default
        return val
    except (TypeError, ValueError):
        return default


def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        val = float(value)
        if not math.isfinite(val):
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def _sanitize_highlights(raw_highlights: object, duration: float) -> List[Dict]:
    """Normalize model output into the expected shape; skip invalid entries."""
    if not isinstance(raw_highlights, list):
        return []

    max_end = duration if (math.isfinite(duration) and duration > 0) else float("inf")
    cleaned: List[Dict] = []
    for item in raw_highlights:
        if not isinstance(item, dict):
            continue

        start = _coerce_float(item.get("start_time"), default=-1.0)
        end = _coerce_float(item.get("end_time"), default=-1.0)
        if start < 0 or end <= start or not (math.isfinite(start) and math.isfinite(end)):
            continue

        if max_end != float("inf"):
            start = min(start, max_end)
            end = min(end, max_end)
            if end <= start:
                continue

        cleaned.append(
            {
                "title": str(item.get("title") or "Untitled Highlight").strip(),
                "start_time": start,
                "end_time": end,
                "score": max(0, min(100, _coerce_int(item.get("score"), default=0))),
                "hook_sentence": str(item.get("hook_sentence") or "").strip(),
                "virality_reason": str(item.get("virality_reason") or "").strip(),
            }
        )

    return cleaned


def detect_content_type(transcript: Dict, llm_fn: LLMFn = call_muapi_llm) -> Dict[str, str]:
    segments = transcript.get("segments", [])
    sample = " ".join(s["text"] for s in segments[:25])[:3000]
    prompt = f"{CONTENT_TYPE_PROMPT}\n\nTranscript sample:\n{sample}"
    try:
        raw = llm_fn(prompt)
        return _parse_json_loose(raw)
    except Exception:
        return {"content_type": "other", "density": "medium"}


def build_transcript_text(transcript: Dict) -> str:
    segments = transcript.get("segments", [])
    return "\n".join(f"[{s['start']:.1f}s] {s['text'].strip()}" for s in segments)


def chunk_transcript(transcript: Dict) -> List[Dict]:
    segments = transcript.get("segments", [])
    duration = float(transcript.get("duration") or (segments[-1]["end"] if segments else 0.0))
    if duration <= 0:
        return []
    untrusted_spans = transcript.get("untrusted_spans", [])
    chunks = []
    start = 0.0
    step = CHUNK_SIZE_SECONDS - CHUNK_OVERLAP_SECONDS
    while start < duration:
        end = min(start + CHUNK_SIZE_SECONDS, duration)
        chunk_end = min(end + CHUNK_OVERLAP_SECONDS, duration)
        rel_segs = []
        for s in segments:
            s_start = float(s.get("start", 0.0))
            s_end = float(s.get("end", 0.0))
            if s_end > start and s_start < chunk_end:
                rel_segs.append({
                    **s,
                    "start": max(0.0, s_start - start),
                    "end": max(0.0, s_end - start),
                })
        if rel_segs:
            chunk = dict(transcript)
            chunk["segments"] = rel_segs
            chunk["duration"] = chunk_end - start
            chunk["_offset"] = start
            if untrusted_spans:
                rel_untrusted = []
                for sp in untrusted_spans:
                    sp_st = float(sp.get("start", 0.0))
                    sp_et = float(sp.get("end", 0.0))
                    if sp_et > start and sp_st < chunk_end:
                        rel_untrusted.append({
                            **sp,
                            "start": max(0.0, sp_st - start),
                            "end": max(0.0, sp_et - start),
                        })
                chunk["untrusted_spans"] = rel_untrusted
            chunks.append(chunk)
        if end >= duration:
            break
        start += step
    return chunks


def call_highlight_api(
    transcript_text: str,
    content_info: Dict,
    duration: float,
    num_clips: int,
    is_chunk: bool = False,
    llm_fn: LLMFn = call_muapi_llm,
    job_ctx: Optional[Any] = None,
    framing_mode: str = "podcast",
) -> Dict:
    # Ask for ~2× the user's target so dedupe has headroom, but cap so the model
    # doesn't have to generate a huge JSON payload (which times out gpt-5-mini).
    target = max(num_clips * 2, 5)
    is_gaming = (framing_mode or "").strip().lower() == "gaming" or str(content_info.get("content_type", "")).lower() == "gaming"

    if is_gaming:
        natural_max = max(2 if is_chunk else 3, int(duration / 45))
        min_clips = min(target, natural_max, 10)
        system = GAMING_HIGHLIGHT_SYSTEM_PROMPT.format(
            virality_criteria=GAMING_VIRALITY_CRITERIA,
            content_type="gaming" if str(content_info.get("content_type", "")).lower() == "gaming" else content_info.get("content_type", "other"),
            density=content_info.get("density", "medium"),
            num_clips_instruction=f"Generate at least {min_clips} highlights",
        )
    else:
        natural_max = max(2 if is_chunk else 3, int(duration / 90))
        min_clips = min(target, natural_max, 8)
        system = HIGHLIGHT_SYSTEM_PROMPT.format(
            virality_criteria=VIRALITY_CRITERIA,
            content_type=content_info.get("content_type", "other"),
            density=content_info.get("density", "medium"),
            num_clips_instruction=f"Generate at least {min_clips} highlights",
        )
    base_prompt = f"{system}\n\nTranscript:\n{transcript_text}"
    prompt = base_prompt
    last_error = "unknown"

    for attempt in range(1, MAX_HIGHLIGHT_API_ATTEMPTS + 1):
        raw = llm_fn(prompt)
        try:
            parsed = _parse_json_loose(raw)
            highlights = _sanitize_highlights(parsed.get("highlights"), duration=duration)
            if highlights:
                return {"highlights": highlights}
            last_error = "no valid highlights in response"
        except Exception as e:
            last_error = str(e)

        if attempt < MAX_HIGHLIGHT_API_ATTEMPTS:
            log_job_message(
                f"[highlights] invalid model output on attempt {attempt}/{MAX_HIGHLIGHT_API_ATTEMPTS}; retrying",
                job_ctx=job_ctx,
            )
            prompt = (
                base_prompt
                + "\n\nIMPORTANT: Return ONLY valid JSON with a top-level 'highlights' array."
                + " Each item must include: title, start_time, end_time, score, hook_sentence, virality_reason."
                + " No markdown fences, no commentary."
            )

    raise RuntimeError(
        f"Highlight generator produced invalid output after {MAX_HIGHLIGHT_API_ATTEMPTS} attempts: {last_error}"
    )


def _filter_untrusted_highlights(
    highlights: List[Dict],
    untrusted_spans: Optional[List[Dict]] = None,
    job_ctx: Optional[Any] = None,
) -> List[Dict]:
    """Reject any highlight candidate whose time interval crosses an untrusted span."""
    if not untrusted_spans:
        return highlights
    kept: List[Dict] = []
    for h in highlights:
        h_start = float(h.get("start_time", 0.0))
        h_end = float(h.get("end_time", 0.0))
        overlap_found = False
        for sp in untrusted_spans:
            s_start = float(sp.get("start", 0.0))
            s_end = float(sp.get("end", 0.0))
            if h_start < s_end - 0.05 and h_end > s_start + 0.05:
                overlap_found = True
                log_job_message(
                    f"[highlights] candidate {h.get('title')!r} [{h_start:.1f}s..{h_end:.1f}s] "
                    f"rejected: intersects untrusted span [{s_start:.1f}s..{s_end:.1f}s]",
                    job_ctx=job_ctx,
                )
                break
        if not overlap_found:
            kept.append(h)
    return kept


def dedupe_highlights(highlights: List[Dict]) -> List[Dict]:
    """Drop a highlight if it overlaps >50% with a higher-scoring one already kept."""
    highlights = sorted(highlights, key=lambda x: int(x.get("score", 0)), reverse=True)
    kept: List[Dict] = []
    for h in highlights:
        h_start = float(h["start_time"])
        h_end = float(h["end_time"])
        h_dur = h_end - h_start
        overlapping = False
        for k in kept:
            latest_start = max(h_start, float(k["start_time"]))
            earliest_end = min(h_end, float(k["end_time"]))
            overlap = earliest_end - latest_start
            if overlap > 0 and overlap > 0.5 * h_dur:
                overlapping = True
                break
        if not overlapping:
            kept.append(h)
    return kept


def get_highlights(
    transcript: Dict,
    num_clips: int = 3,
    llm_fn: Optional[LLMFn] = None,
    job_ctx: Optional[Any] = None,
    framing_mode: str = "podcast",
    media_path: Optional[str] = None,
) -> Dict:
    """Main entry point — returns {highlights: [...]} sorted by score.

    `llm_fn` swaps the underlying LLM. Defaults to MuAPI gpt-5-mini; local
    mode passes in a local LLM-backed callable.
    """
    llm_fn = llm_fn or call_muapi_llm
    duration = transcript.get("duration", 0)
    untrusted_spans = transcript.get("untrusted_spans", [])
    log_job_message(f"[highlights] analyzing transcript ({duration:.0f}s)...", job_ctx=job_ctx)
    content_info = detect_content_type(transcript, llm_fn=llm_fn)
    log_job_message(f"[highlights] content={content_info.get('content_type')} density={content_info.get('density')} duration={duration:.0f}s", job_ctx=job_ctx)

    if (framing_mode or "").strip().lower() == "gaming":
        log_job_message("[highlights] Mode gaming active: using gaming virality criteria (screams, laughter, discord banter, clutch/fail) & 20-60s sweet spot.", job_ctx=job_ctx)

    if duration >= LONG_VIDEO_THRESHOLD:
        chunks = chunk_transcript(transcript)
        log_job_message(f"[highlights] long video — splitting into {len(chunks)} chunks", job_ctx=job_ctx)
        all_highlights: List[Dict] = []
        for i, chunk in enumerate(chunks):
            offset = float(chunk.get("_offset", 0.0))
            text = build_transcript_text(chunk)
            log_job_message(f"[highlights] chunk {i + 1}/{len(chunks)} (offset {offset:.0f}s, dur {chunk['duration']:.0f}s)", job_ctx=job_ctx)
            result = call_highlight_api(text, content_info, chunk["duration"], num_clips=num_clips, is_chunk=True, llm_fn=llm_fn, job_ctx=job_ctx, framing_mode=framing_mode)
            for h in result.get("highlights", []):
                h["start_time"] = round(float(h["start_time"]) + offset, 2)
                h["end_time"] = round(float(h["end_time"]) + offset, 2)
                all_highlights.append(h)
        clean_candidates = _filter_untrusted_highlights(all_highlights, untrusted_spans, job_ctx=job_ctx)
        highlights = dedupe_highlights(clean_candidates)
    else:
        text = build_transcript_text(transcript)
        result = call_highlight_api(text, content_info, duration, num_clips=num_clips, llm_fn=llm_fn, job_ctx=job_ctx, framing_mode=framing_mode)
        raw_candidates = result.get("highlights", [])
        clean_candidates = _filter_untrusted_highlights(raw_candidates, untrusted_spans, job_ctx=job_ctx)
        highlights = dedupe_highlights(clean_candidates)

    if media_path and os.path.exists(media_path):
        log_job_message("[highlights] Scanning audio peaks (screams & laughter) to boost scores...", job_ctx=job_ctx)
        energy_series = scan_audio_energy(media_path, job_ctx=job_ctx)
        if energy_series:
            highlights = boost_highlights_with_audio_peaks(highlights, energy_series, job_ctx=job_ctx)

    return {"highlights": highlights}
