from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter

SIZE = 256
BG_GREEN = "#16A34A"
BG_GREEN_DARK = "#0E7A33"
FG_WHITE = "#FFFFFF"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _gradient(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    r1, g1, b1 = (0x16, 0xA3, 0x4A)
    r2, g2, b2 = (0x0E, 0x7A, 0x33)
    pixels = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        for x in range(size):
            pixels[x, y] = (r, g, b, 255)
    return img


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _draw_bracket(draw: ImageDraw.ImageDraw, cx: int, cy: int, height: int, thickness: int, left: bool) -> None:
    tip_x = cx + (-16 if left else 16)
    draw.line([(cx, cy - height // 2), (tip_x, cy)], fill=FG_WHITE, width=thickness, joint="curve")
    draw.line([(tip_x, cy), (cx, cy + height // 2)], fill=FG_WHITE, width=thickness, joint="curve")


def _draw_arrow(draw: ImageDraw.ImageDraw, cx: int, shaft_top: int, shaft_bot: int,
                head_half: int, thickness: int) -> None:
    shaft_left = cx - thickness // 2
    shaft_right = cx + thickness // 2 + 1
    draw.rectangle([shaft_left, shaft_top, shaft_right, shaft_bot], fill=FG_WHITE)
    head_bot = shaft_top + head_half * 2
    draw.polygon([(cx, shaft_top - head_half * 2),
                  (cx + head_half, head_bot - head_half),
                  (cx - head_half, head_bot - head_half)], fill=FG_WHITE)


def _draw_dot(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int) -> None:
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=FG_WHITE)


def build_icon(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = _gradient(size)
    radius = max(2, int(size * 0.22))
    mask = _rounded_mask(size, radius)
    img.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    cx = size // 2
    cy = size // 2 + int(size * 0.02)

    bracket_height = int(size * 0.44)
    bracket_offset = int(size * 0.31)
    thickness = max(2, int(size * 0.035))
    _draw_bracket(draw, cx - bracket_offset, cy, bracket_height, thickness, left=True)
    _draw_bracket(draw, cx + bracket_offset, cy, bracket_height, thickness, left=False)

    head_half = max(3, int(size * 0.10))
    arrow_thickness = max(3, int(size * 0.055))
    shaft_top = cy - int(size * 0.04)
    shaft_bot = cy + int(size * 0.20)
    _draw_arrow(draw, cx, shaft_top, shaft_bot, head_half, arrow_thickness)

    dot_radius = max(3, int(size * 0.058))
    dot_y = shaft_top - head_half * 2 - dot_radius - max(2, int(size * 0.02))
    _draw_dot(draw, cx, dot_y, dot_radius)

    return img


def save_png(path: str, size: int = SIZE) -> None:
    img = build_icon(size)
    img.save(path, "PNG")


def save_ico(path: str, sizes=(16, 24, 32, 48, 64, 128, 256)) -> None:
    images = [build_icon(s) for s in sizes]
    images[-1].save(path, format="ICO",
                    sizes=[(s, s) for s in sizes],
                    append_images=images[:-1])


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    png_path = os.path.join(OUT_DIR, "icon.png")
    ico_path = os.path.join(OUT_DIR, "icon.ico")
    save_png(png_path)
    save_ico(ico_path)
    print(f"Wrote {png_path}")
    print(f"Wrote {ico_path}")


if __name__ == "__main__":
    main()
