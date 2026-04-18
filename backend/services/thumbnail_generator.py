import asyncio
import logging
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

THUMB_WIDTH = 1280
THUMB_HEIGHT = 720


async def extract_frame(video_path: str, time_seconds: float) -> str:
    """Extract a single frame from a video at the given timestamp."""
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time_seconds),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        tmp.name,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Frame extraction failed: {stderr.decode()[-300:]}")
    logger.info(f"Extracted frame at {time_seconds:.1f}s from {video_path}")
    return tmp.name


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load Inter ExtraBold (variable font at weight 800), fall back to system fonts."""
    # Inter variable font — use variation axis to set ExtraBold (800)
    inter_paths = [
        Path.home() / "Library/Fonts/Inter-VariableFont_opsz,wght.ttf",
        Path("/usr/share/fonts/truetype/inter/Inter-VariableFont_opsz,wght.ttf"),
    ]
    for path in inter_paths:
        if path.exists():
            try:
                font = ImageFont.truetype(str(path), size)
                font.set_variation_by_axes([24, 800])  # opsz=24, wght=800 (ExtraBold)
                return font
            except Exception:
                pass

    fallback_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in fallback_paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def compose_thumbnail(frame_path: str, title_text: str, output_path: str) -> str:
    """Compose a thumbnail by overlaying title text on a video frame."""
    img = Image.open(frame_path).convert("RGB")

    # Resize/crop to 1280x720
    img_ratio = img.width / img.height
    target_ratio = THUMB_WIDTH / THUMB_HEIGHT
    if img_ratio > target_ratio:
        new_height = THUMB_HEIGHT
        new_width = int(THUMB_HEIGHT * img_ratio)
    else:
        new_width = THUMB_WIDTH
        new_height = int(THUMB_WIDTH / img_ratio)
    img = img.resize((new_width, new_height), Image.LANCZOS)

    # Center crop
    left = (new_width - THUMB_WIDTH) // 2
    top = (new_height - THUMB_HEIGHT) // 2
    img = img.crop((left, top, left + THUMB_WIDTH, top + THUMB_HEIGHT))

    draw = ImageDraw.Draw(img, "RGBA")

    # Darken the whole image slightly for text readability
    overlay = Image.new("RGBA", (THUMB_WIDTH, THUMB_HEIGHT), (0, 0, 0, 80))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(img, "RGBA")

    # Text overlay with negative kerning
    font = _load_font(96)
    kerning = -4  # negative kerning (pixels)
    wrapped = textwrap.fill(title_text, width=20)
    lines = wrapped.split("\n")

    def _kerned_line_width(line: str) -> int:
        """Calculate width of a line with custom kerning."""
        if not line:
            return 0
        total = 0
        for ch in line:
            bbox_ch = font.getbbox(ch)
            total += (bbox_ch[2] - bbox_ch[0]) + kerning
        return total - kerning  # remove trailing kerning

    def _draw_kerned_line(d: ImageDraw.ImageDraw, x: int, y: int, line: str, fill):
        """Draw a single line of text with custom kerning."""
        cx = x
        for ch in line:
            d.text((cx, y), ch, font=font, fill=fill)
            bbox_ch = font.getbbox(ch)
            cx += (bbox_ch[2] - bbox_ch[0]) + kerning

    # Measure total text block size
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
    line_spacing = int(line_height * 0.25)
    line_widths = [_kerned_line_width(l) for l in lines]
    max_line_w = max(line_widths) if line_widths else 0
    total_h = line_height * len(lines) + line_spacing * (len(lines) - 1)

    # Center the text block
    block_x = (THUMB_WIDTH - max_line_w) // 2
    block_y = (THUMB_HEIGHT - total_h) // 2

    for i, line in enumerate(lines):
        # Center each line individually
        lx = (THUMB_WIDTH - line_widths[i]) // 2
        ly = block_y + i * (line_height + line_spacing)
        # Shadow
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3)]:
            _draw_kerned_line(draw, lx + dx, ly + dy, line, (0, 0, 0, 180))
        # Main text
        _draw_kerned_line(draw, lx, ly, line, (255, 255, 255, 255))

    img.convert("RGB").save(output_path, "JPEG", quality=90)
    logger.info(f"Composed thumbnail: {output_path}")
    return output_path
