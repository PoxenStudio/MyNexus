"""Generates a title-based placeholder book cover — the last-resort fallback
when a book ends up with no cover from either an explicit cover_url (see
core-api's BookHandler.Import) or EPUB extraction (nodes/parsers/epub_parser.py's
_extract_cover — always the case for TXT, which has no embedded images at
all). Called from pipelines/ingestion.py's run() once per completed ingest,
only when document.cover is still empty at that point.

Ported from MyBooks' webserver/base/image_generator.py
(ImageGenerator.generate_cover) — same rotated-gradient-background +
centered-title-text look, trimmed to what this pipeline actually needs (no
bk_img_path/debug/author-output knobs, single hard-coded JPEG output).
"""

import io
import logging
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Same palette as MyBooks' ImageGenerator, for a consistent look between the
# two systems' generated covers.
_COLORS = [
    "#003e19", "#028c6a", "#283b42", "#1d6a96", "#a46843",
    "#370d00", "#072a24", "#280e3b", "#002c2f", "#023459",
    "#00142f", "#4A2B31",
]

DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 1200

# Font resolution order (see _load_font):
#   1. WorkerConfig.cover_font_path, if the deployer set one explicitly.
#   2. <config dir>/../data/fonts/MiSans-Normal.woff — the shared data/
#      volume both Core API and Worker containers mount (docker-compose.yml
#      binds ./data to /app/data on both), so a deployer can drop a
#      replacement font there without rebuilding the Worker image. Resolved
#      relative to config.yaml's own location (not CWD) since Worker's CWD
#      inside the container (/app/src) isn't the same directory the data/
#      volume is mounted under (/app/data) — see MYNEXUS_CONFIG_PATH.
#   3. The font baked into the Worker image at build time (worker/assets/,
#      copied in by Dockerfile) — guarantees this works out of the box with
#      no deploy-time step required, using the same MiSans-Normal.woff
#      web-ui already ships (web-ui/public/fonts/MiSans-Normal.woff).
#   4. PIL's built-in bitmap font (unscaled, ugly, but never crashes) —
#      matches MyBooks' own graceful-degradation behavior when no font file
#      is available at all.
_CONFIG_PATH = os.getenv("MYNEXUS_CONFIG_PATH", "./config/config.yaml")
_DATA_FONT_CANDIDATE = os.path.normpath(
    os.path.join(os.path.dirname(_CONFIG_PATH), "..", "data", "fonts", "MiSans-Normal.woff")
)
_BUNDLED_FONT_CANDIDATE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts", "MiSans-Normal.woff")
)

_font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
# Resolved once and reused: None = not yet tried, "" = every candidate
# failed (fall back to PIL's default font from here on).
_resolved_font_path: str | None = None
_resolved_font_bytes: bytes | None = None  # set when the winning candidate needed WOFF->TTF conversion


def _woff_to_ttf_bytes(path: str) -> bytes | None:
    """FreeType (Pillow's font backend) supports WOFF directly in most
    builds, but not reliably everywhere (manylinux wheels vs. distro
    packages vs. Alpine/musl) — this is the fallback for when
    ImageFont.truetype(path, ...) raises on a .woff file: unwrap it to a
    plain sfnt (TTF) in memory with fonttools, which Pillow can always load
    regardless of FreeType's own WOFF support."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        logger.warning("[cover] fonttools not installed, cannot convert WOFF font %s", path)
        return None
    try:
        font = TTFont(path)
        font.flavor = None  # strip the WOFF wrapper -> plain sfnt
        buf = io.BytesIO()
        font.save(buf)
        return buf.getvalue()
    except Exception:
        logger.warning("[cover] failed to convert WOFF font %s", path, exc_info=True)
        return None


def _resolve_font(configured_path: str) -> tuple[str, bytes | None]:
    """Tries each candidate path in order, returning (path, ttf_bytes) for
    the first one that actually loads — ttf_bytes is non-None only when the
    candidate needed WOFF->TTF conversion (see _woff_to_ttf_bytes), so
    _load_font knows whether to open the path directly or the converted
    bytes. Returns ("", None) if nothing worked at all."""
    candidates = [p for p in (configured_path, _DATA_FONT_CANDIDATE, _BUNDLED_FONT_CANDIDATE) if p]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            ImageFont.truetype(path, 40)  # probe at an arbitrary size
            logger.info("[cover] using font: %s", path)
            return path, None
        except Exception:
            pass  # fall through to the WOFF->TTF conversion attempt below
        ttf_bytes = _woff_to_ttf_bytes(path)
        if ttf_bytes is not None:
            try:
                ImageFont.truetype(io.BytesIO(ttf_bytes), 40)
                logger.info("[cover] using font (converted from WOFF): %s", path)
                return path, ttf_bytes
            except Exception:
                logger.warning("[cover] converted font %s still failed to load", path, exc_info=True)
    logger.warning("[cover] no usable font found (tried %s), falling back to PIL's default bitmap font", candidates)
    return "", None


def _load_font(size: int, configured_path: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    global _resolved_font_path, _resolved_font_bytes
    if _resolved_font_path is None:
        _resolved_font_path, _resolved_font_bytes = _resolve_font(configured_path)

    if size in _font_cache:
        return _font_cache[size]

    if _resolved_font_path:
        source = io.BytesIO(_resolved_font_bytes) if _resolved_font_bytes is not None else _resolved_font_path
        font = ImageFont.truetype(source, size)
    else:
        font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _rotated_gradient(width: int, height: int) -> Image.Image:
    c1_hex, c2_hex = random.sample(_COLORS, 2)
    color1, color2 = _hex_to_rgb(c1_hex), _hex_to_rgb(c2_hex)
    base, top = Image.new("RGB", (width, height), color1), Image.new("RGB", (width, height), color2)
    diag = int(math.sqrt(width**2 + height**2))
    mask = Image.new("L", (diag, diag), 0)
    mask_draw = ImageDraw.Draw(mask)
    for i in range(diag):
        mask_draw.line([(i, 0), (i, diag)], fill=int(255 * (i / diag)))
    mask = mask.rotate(random.randint(0, 360), resample=Image.BICUBIC)
    left, top_off = (diag - width) // 2, (diag - height) // 2
    mask = mask.crop((left, top_off, left + width, top_off + height))
    base.paste(top, (0, 0), mask)
    return base


def generate_cover(
    title: str, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, font_path: str = ""
) -> bytes | None:
    """Returns JPEG bytes of a cover with `title` centered over a random
    rotated-gradient background, or None on any failure (caller —
    pipelines/ingestion.py — treats that the same as "no cover", it never
    blocks ingestion over a cover generation failure)."""
    try:
        img = _rotated_gradient(width, height)
        draw = ImageDraw.Draw(img)

        title_size = height // 12 if height > 400 else height // 9 - 3
        font = _load_font(title_size, font_path)

        title = (title or "").strip() or "未命名书籍"
        title_lines: list[str] = []
        current_line = ""
        max_lines = 3
        for char in title:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= width * 0.9:
                current_line = test_line
            else:
                title_lines.append(current_line)
                current_line = char
                if len(title_lines) >= max_lines:
                    break
        if len(title_lines) < max_lines and current_line:
            title_lines.append(current_line)
        title_lines = title_lines[:max_lines]
        if len(title_lines) > 1 and len(title_lines[-1]) < 2:
            title_lines[-2] += title_lines[-1]
            title_lines.pop()

        current_y = height // 5
        for line in title_lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (width - w) // 2
            draw.text((x, current_y), line, font=font, fill=(255, 255, 255))
            current_y += h + (title_size // 10)

        output = io.BytesIO()
        img.convert("RGB").save(output, format="JPEG", quality=88)
        return output.getvalue()
    except Exception:
        logger.error("[cover] generation failed", exc_info=True)
        return None


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m util.cover_generator "书名" [font_path]
    import argparse

    parser = argparse.ArgumentParser(description="Dry-run title-based cover generation.")
    parser.add_argument("title")
    parser.add_argument("font_path", nargs="?", default="")
    args = parser.parse_args()

    data = generate_cover(args.title, font_path=args.font_path)
    if data is None:
        print("cover generation failed")
    else:
        with open("/tmp/cover_test.jpg", "wb") as f:
            f.write(data)
        print(f"wrote {len(data)} bytes to /tmp/cover_test.jpg")
