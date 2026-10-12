"""Gaming Party Stream Layout Presets and FFmpeg Filter Complex Builder.

Canvas Output: 9:16 vertical (1080x1920)
Stack Architectures:
  - 2-Layer Clean Gaming Stack (Default/Recommended):
      * Mid (1080x1440): Main gameplay action zone
      * Bottom (1080x480): Streamer facecam
      * Total: 1440 + 480 = 1920h x 1080w
  - 3-Layer Discord Party Stack:
      * Top (1080x340): Discord squad cam strip
      * Mid (1080x1100): Main gameplay action zone
      * Bottom (1080x480): Streamer facecam
      * Total: 340 + 1100 + 480 = 1920h x 1080w
  - Fallback Full Gameplay:
      * 9:16 Center Crop (1080x1920) without empty webcam layer
"""
import os
from typing import Any, Dict, Optional, Tuple

FONTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts"))

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
TOP_HEIGHT = 340
MID_HEIGHT = 1100
BOTTOM_HEIGHT = 480
FACECAM_2L_HEIGHT = 480
GAMEPLAY_2L_HEIGHT = 1440

# Reference 1080p stream dimensions (1920x1080)
REF_WIDTH = 1920
REF_HEIGHT = 1080

GAMING_PRESETS: Dict[str, Dict[str, Any]] = {
    "auto": {
        "name": "Auto-Detect Facecam (AI)",
        "description": "Deteksi posisi facecam otomatis dengan AI (Facecam Atas + Gameplay Bawah)",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 1420, "y": 680, "w": 500, "h": 400},
    },
    "auto_detect": {
        "name": "Auto-Detect Facecam (AI)",
        "description": "Deteksi posisi facecam otomatis dengan AI (Facecam Atas + Gameplay Bawah)",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 1420, "y": 680, "w": 500, "h": 400},
    },
    "clean_2layer": {
        "name": "Clean 2-Layer (Facecam Atas + Gameplay Bawah)",
        "description": "Webcam streamer 480p di atas + Gameplay utama 1440p di bawah (Windah Basudara style)",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 1420, "y": 680, "w": 500, "h": 400},
    },
    "clean_2layer_cam_top": {
        "name": "Clean 2-Layer (Facecam Atas + Gameplay Bawah)",
        "description": "Webcam streamer 480p di atas + Gameplay utama 1440p di bawah (Windah Basudara style)",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 1420, "y": 680, "w": 500, "h": 400},
    },
    "clean_2layer_cam_bottom": {
        "name": "Clean 2-Layer (Gameplay Atas + Facecam Bawah)",
        "description": "Gameplay utama 1440p di atas + Webcam streamer 480p di bawah (Klasik)",
        "layout": "cam_bottom",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 1420, "y": 680, "w": 500, "h": 400},
    },
    "clean_2layer_bottom_right": {
        "name": "Clean 2-Layer (Webcam Kanan Bawah)",
        "description": "Webcam dari pojok kanan bawah + Gameplay utama",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 1420, "y": 680, "w": 500, "h": 400},
    },
    "clean_2layer_bottom_left": {
        "name": "Clean 2-Layer (Webcam Kiri Bawah)",
        "description": "Webcam dari pojok kiri bawah + Gameplay utama",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 0, "y": 680, "w": 500, "h": 400},
    },
    "clean_2layer_top_right": {
        "name": "Clean 2-Layer (Webcam Kanan Atas)",
        "description": "Webcam dari pojok kanan atas + Gameplay utama",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 1420, "y": 0, "w": 500, "h": 400},
    },
    "clean_2layer_top_left": {
        "name": "Clean 2-Layer (Webcam Kiri Atas)",
        "description": "Webcam dari pojok kiri atas + Gameplay utama",
        "layout": "cam_top",
        "top": None,
        "mid": {"x": 240, "y": 0, "w": 1440, "h": 1080},
        "bottom": {"x": 0, "y": 0, "w": 500, "h": 400},
    },
    "discord_top_cam_bottom_right": {
        "name": "Discord Atas + Webcam Kanan Bawah (3-Layer)",
        "description": "Discord cam strip di atas, gameplay tengah, webcam streamer di pojok kanan bawah",
        "layout": "3layer",
        "top": {"x": 0, "y": 0, "w": 1920, "h": 260},
        "mid": {"x": 260, "y": 60, "w": 1400, "h": 960},
        "bottom": {"x": 1420, "y": 680, "w": 500, "h": 400},
    },
    "discord_left_cam_top_right": {
        "name": "Discord Kiri + Webcam Kanan Atas (3-Layer)",
        "description": "Discord cam strip di kiri/vertikal, gameplay tengah, webcam streamer di pojok kanan atas",
        "layout": "3layer",
        "top": {"x": 0, "y": 0, "w": 520, "h": 720},
        "mid": {"x": 240, "y": 80, "w": 1440, "h": 960},
        "bottom": {"x": 1420, "y": 0, "w": 500, "h": 380},
    },
    "custom": {
        "name": "Custom Bounding Box",
        "description": "Kotak area facecam & gameplay yang digambar/diatur pengguna",
        "layout": "cam_top",
    },
}


def get_default_gameplay_box(src_w: int, src_h: int) -> Tuple[int, int, int, int]:
    """Calculate 3:4 centered gameplay action crop from source frame (maps cleanly to 1080x1440)."""
    target_ratio = 1080.0 / float(GAMEPLAY_2L_HEIGHT)  # 0.75
    crop_w = int(round(src_h * target_ratio))
    crop_w = max(2, min(src_w, crop_w))
    crop_w = crop_w - (crop_w % 2)
    crop_h = max(2, src_h - (src_h % 2))
    crop_x = max(0, (src_w - crop_w) // 2)
    crop_x = crop_x - (crop_x % 2)
    return crop_x, 0, crop_w, crop_h


def _clamp_box(box: Optional[Dict[str, Any]], src_w: int, src_h: int) -> Tuple[int, int, int, int]:
    """Parse, scale, and clamp a bounding box (x, y, w, h) strictly within source dimensions."""
    if not box or not isinstance(box, dict):
        return 0, 0, src_w, src_h

    x_raw = float(box.get("x", 0))
    y_raw = float(box.get("y", 0))
    w_raw = float(box.get("w", src_w))
    h_raw = float(box.get("h", src_h))

    # Check if normalized (0.0 - 1.0)
    is_normalized = (0.0 <= x_raw <= 1.0 and 0.0 <= y_raw <= 1.0 and
                     0.0 < w_raw <= 1.0 and 0.0 < h_raw <= 1.0)

    if is_normalized:
        x = int(round(x_raw * src_w))
        y = int(round(y_raw * src_h))
        w = int(round(w_raw * src_w))
        h = int(round(h_raw * src_h))
    else:
        # Scale proportionally from 1080p reference if source differs
        scale_x = src_w / float(REF_WIDTH)
        scale_y = src_h / float(REF_HEIGHT)
        x = int(round(x_raw * scale_x))
        y = int(round(y_raw * scale_y))
        w = int(round(w_raw * scale_x))
        h = int(round(h_raw * scale_y))

    # Clamp bounds
    x = max(0, min(src_w - 2, x))
    y = max(0, min(src_h - 2, y))
    w = max(2, min(src_w - x, w))
    h = max(2, min(src_h - y, h))

    # Ensure even pixel values for codec compatibility
    w = max(2, w - (w % 2))
    h = max(2, h - (h % 2))
    x = max(0, x - (x % 2))
    y = max(0, y - (y % 2))
    return x, y, w, h


def resolve_gaming_crop_boxes(
    preset_name: str = "clean_2layer",
    src_w: int = 1920,
    src_h: int = 1080,
    custom_box: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Tuple[int, int, int, int]], Tuple[int, int, int, int], Tuple[int, int, int, int]]:
    """Resolve source crop rectangles (x, y, w, h) for (top, mid, bottom) layers.
    Returns (top_crop, mid_crop, bot_crop). If 2-layer layout is active, top_crop is None.
    Supports keys: 'facecam' (bottom webcam), 'gameplay' (mid action zone), 'top' (discord strip).
    """
    preset_key = preset_name.strip().lower() if isinstance(preset_name, str) else "clean_2layer"

    if (preset_key == "custom" or custom_box) and isinstance(custom_box, dict):
        top_def = custom_box.get("top")
        mid_def = custom_box.get("mid") or custom_box.get("gameplay")
        bot_def = custom_box.get("bottom") or custom_box.get("facecam") or GAMING_PRESETS["clean_2layer"]["bottom"]

        top_crop = _clamp_box(top_def, src_w, src_h) if top_def else None
        if mid_def:
            mid_crop = _clamp_box(mid_def, src_w, src_h)
        else:
            mid_crop = get_default_gameplay_box(src_w, src_h)
        bot_crop = _clamp_box(bot_def, src_w, src_h)
        return top_crop, mid_crop, bot_crop
    else:
        preset = GAMING_PRESETS.get(preset_key, GAMING_PRESETS["clean_2layer"])
        top_def = preset.get("top")
        mid_def = preset.get("mid", GAMING_PRESETS["clean_2layer"]["mid"])
        bot_def = preset.get("bottom", GAMING_PRESETS["clean_2layer"]["bottom"])

        top_crop = _clamp_box(top_def, src_w, src_h) if top_def else None
        mid_crop = _clamp_box(mid_def, src_w, src_h)
        bot_crop = _clamp_box(bot_def, src_w, src_h)
        return top_crop, mid_crop, bot_crop


def get_gaming_layout(
    preset_name: str = "clean_2layer",
    custom_box: Optional[Dict[str, Any]] = None,
    requested_layout: Optional[str] = None,
) -> str:
    """Resolve gaming stack vertical layout: 'cam_top' (default Windah style), 'cam_bottom', or '3layer'."""
    if requested_layout and str(requested_layout).strip().lower() in ("cam_top", "cam_bottom", "3layer"):
        return str(requested_layout).strip().lower()
    if custom_box and isinstance(custom_box, dict) and "layout" in custom_box:
        l = str(custom_box["layout"]).strip().lower()
        if l in ("cam_top", "cam_bottom", "3layer"):
            return l
    preset_key = preset_name.strip().lower() if isinstance(preset_name, str) else "clean_2layer"
    preset = GAMING_PRESETS.get(preset_key, {})
    return preset.get("layout", "cam_top")


def build_gaming_filter_complex(
    top_crop: Optional[Tuple[int, int, int, int]],
    mid_crop: Tuple[int, int, int, int],
    bot_crop: Tuple[int, int, int, int],
    ass_path: Optional[str] = None,
    layout: str = "cam_top",
) -> str:
    """Build single-pass FFmpeg filter_complex for vertical canvas (1080x1920).
    - If top_crop is None:
        * layout == 'cam_top' (Default/Windah style): Facecam 1080x480 (atas) + Gameplay 1080x1440 (bawah) = 1920.
        * layout == 'cam_bottom' (Classic 2-layer): Gameplay 1080x1440 (atas) + Facecam 1080x480 (bawah) = 1920.
    - If top_crop is Tuple: 3-layer stack (Top 1080x340 + Mid 1080x1100 + Bottom 1080x480 = 1920).
    """
    mx, my, mw, mh = mid_crop
    bx, by, bw, bh = bot_crop
    layout_norm = (layout or "cam_top").strip().lower()

    if top_crop is None:
        if layout_norm == "cam_bottom":
            filters = [
                "[0:v]split=2[raw_mid][raw_bot]",
                f"[raw_mid]crop={mw}:{mh}:{mx}:{my},scale={CANVAS_WIDTH}:{GAMEPLAY_2L_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{GAMEPLAY_2L_HEIGHT}[v_mid]",
                f"[raw_bot]crop={bw}:{bh}:{bx}:{by},scale={CANVAS_WIDTH}:{BOTTOM_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{BOTTOM_HEIGHT}[v_bot]",
                "[v_mid][v_bot]vstack=inputs=2[v_stacked]",
            ]
        else:
            # Default Windah Basudara style: Facecam Atas + Gameplay Bawah
            filters = [
                "[0:v]split=2[raw_mid][raw_bot]",
                f"[raw_mid]crop={mw}:{mh}:{mx}:{my},scale={CANVAS_WIDTH}:{GAMEPLAY_2L_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{GAMEPLAY_2L_HEIGHT}[v_mid]",
                f"[raw_bot]crop={bw}:{bh}:{bx}:{by},scale={CANVAS_WIDTH}:{BOTTOM_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{BOTTOM_HEIGHT}[v_bot]",
                "[v_bot][v_mid]vstack=inputs=2[v_stacked]",
            ]
    else:
        tx, ty, tw, th = top_crop
        filters = [
            "[0:v]split=3[raw_top][raw_mid][raw_bot]",
            f"[raw_top]crop={tw}:{th}:{tx}:{ty},scale={CANVAS_WIDTH}:{TOP_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{TOP_HEIGHT}[v_top]",
            f"[raw_mid]crop={mw}:{mh}:{mx}:{my},scale={CANVAS_WIDTH}:{MID_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{MID_HEIGHT}[v_mid]",
            f"[raw_bot]crop={bw}:{bh}:{bx}:{by},scale={CANVAS_WIDTH}:{BOTTOM_HEIGHT}:force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{BOTTOM_HEIGHT}[v_bot]",
            "[v_top][v_mid][v_bot]vstack=inputs=3[v_stacked]",
        ]

    if ass_path and os.path.exists(ass_path):
        escaped_ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        if os.path.isdir(FONTS_DIR):
            escaped_fontsdir = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
            filters.append(f"[v_stacked]ass=filename='{escaped_ass}':fontsdir='{escaped_fontsdir}'[v_out]")
        else:
            filters.append(f"[v_stacked]ass=filename='{escaped_ass}'[v_out]")
    else:
        filters.append("[v_stacked]null[v_out]")

    return ";".join(filters)


def build_gameplay_fallback_filter_complex(
    src_w: int = 1920,
    src_h: int = 1080,
    ass_path: Optional[str] = None,
) -> str:
    """Build single-pass FFmpeg filter_complex for Full Gameplay 9:16 Center Crop fallback (1080x1920)."""
    target_ratio = 9.0 / 16.0
    if (src_w / src_h) > target_ratio:
        crop_h = src_h
        crop_w = int(crop_h * target_ratio)
    else:
        crop_w = src_w
        crop_h = int(crop_w / target_ratio)

    crop_w = max(2, crop_w - (crop_w % 2))
    crop_h = max(2, crop_h - (crop_h % 2))
    crop_x = max(0, (src_w - crop_w) // 2)
    crop_y = max(0, (src_h - crop_h) // 2)
    crop_x = crop_x - (crop_x % 2)
    crop_y = crop_y - (crop_y % 2)

    filters = [
        f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}[v_gameplay]",
    ]
    if ass_path and os.path.exists(ass_path):
        escaped_ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        if os.path.isdir(FONTS_DIR):
            escaped_fontsdir = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
            filters.append(f"[v_gameplay]ass=filename='{escaped_ass}':fontsdir='{escaped_fontsdir}'[v_out]")
        else:
            filters.append(f"[v_gameplay]ass=filename='{escaped_ass}'[v_out]")
    else:
        filters.append("[v_gameplay]null[v_out]")

    return ";".join(filters)
