"""CLI entry point.

Usage:
    python main.py "https://www.youtube.com/watch?v=..." \
        --num-clips 3 --aspect-ratio 9:16
"""
import argparse
import json
import sys

# Windows uses 'charmap' by default, which can't encode Unicode characters
# like →. Reconfigure stdout/stderr to UTF-8 so output works on all platforms.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from shorts_generator import generate_shorts


def main() -> int:
    parser = argparse.ArgumentParser(description="AI YouTube Shorts Generator")
    parser.add_argument("url", help="YouTube URL, file:// URL, or local file path")
    parser.add_argument(
        "--mode",
        choices=["api", "local"],
        default="api",
        help="api (default, MuAPI) or local (remote URL, file://, or local path + faster-whisper + LLM provider + ffmpeg).",
    )
    parser.add_argument("--num-clips", type=int, default=3, help="How many shorts to render (default: 3)")
    parser.add_argument("--aspect-ratio", default="9:16", help="Output aspect ratio (default: 9:16)")
    parser.add_argument("--format", default="1080", help="Source download resolution: 360 / 480 / 720 / 1080 (default: 1080)")
    parser.add_argument("--framing", default="podcast", choices=["podcast", "single", "center", "gaming"], help="Framing style: podcast / single / center / gaming (default: podcast)")
    parser.add_argument("--gaming-preset", default="clean_2layer", choices=["clean_2layer", "discord_top_cam_bottom_right", "discord_left_cam_top_right", "custom"], help="Gaming layout preset (default: clean_2layer)")
    parser.add_argument("--subtitle-style", default="karaoke", choices=["karaoke", "clean", "none"], help="Subtitle style: karaoke / clean / none (default: karaoke)")
    parser.add_argument("--language", default=None, help="Force Whisper language code, e.g. 'en' (default: auto-detect)")
    parser.add_argument("--output-json", default=None, help="Write the full result JSON to this path")
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Jangan hapus video mentahan YouTube setelah selesai render klip (default: auto-hapus jika AUTO_DELETE_SOURCE_VIDEO=true)",
    )
    args = parser.parse_args()

    auto_delete = False if args.keep_source else None

    try:
        result = generate_shorts(
            youtube_url=args.url,
            num_clips=args.num_clips,
            aspect_ratio=args.aspect_ratio,
            download_format=args.format,
            language=args.language,
            mode=args.mode,
            framing_mode=args.framing,
            gaming_preset=args.gaming_preset,
            subtitle_style=args.subtitle_style,
            auto_delete_source_video=auto_delete,
        )
    except Exception as e:
        import traceback
        from shorts_generator import report_error_to_reef_flow
        report_error_to_reef_flow(
            title=f"[CLI Pipeline Error] {str(e)[:80]}",
            description=f"URL: {args.url}\nError: {e}\n\nStack Trace:\n{traceback.format_exc()}",
            priority="URGENT",
            async_mode=False,
        )
        print(f"\nFAILED: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 72)
    print(f"Mode:          {result.get('mode', args.mode)}")
    print(f"Source video:  {result['source_video_url']}")
    print(f"Highlights:    {len(result['highlights'])} candidates → kept top {len(result['shorts'])}")
    print("=" * 72)
    for i, s in enumerate(result["shorts"], 1):
        print(f"\n#{i}  score={s.get('score')}  {s.get('start_time'):.1f}s → {s.get('end_time'):.1f}s")
        print(f"     title:  {s.get('title')}")
        print(f"     hook:   {s.get('hook_sentence')}")
        if s.get("clip_url"):
            print(f"     clip:   {s['clip_url']}")
        else:
            print(f"     clip:   FAILED ({s.get('error')})")

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nFull JSON written to {args.output_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
