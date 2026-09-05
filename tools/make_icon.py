"""Genere assets/icon.png et assets/icon.ico (croissant sur fond emeraude)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adhan.paths import ASSETS_DIR  # noqa: E402

S = 1024  # rendu haute resolution puis reduction (anti-aliasing)
BG_TOP = (13, 74, 61)
BG_BOTTOM = (6, 42, 36)
GOLD = (240, 196, 106)
GOLD_DIM = (214, 168, 82)


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=255)
    return m


def build() -> Image.Image:
    # Fond degrade vertical.
    bg = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        bg.putpixel(
            (0, y),
            tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )
    img = bg.resize((S, S)).convert("RGBA")
    img.putalpha(rounded_mask(S, int(S * 0.22)))

    # Croissant : disque plein moins disque decale.
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy, r = S * 0.46, S * 0.50, S * 0.30
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD)
    r2 = r * 0.86
    ox, oy = cx + r * 0.34, cy - r * 0.10
    d.ellipse((ox - r2, oy - r2, ox + r2, oy + r2), fill=(0, 0, 0, 0))
    img.alpha_composite(layer)

    # Petite etoile a cinq branches.
    star = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(star)
    import math

    sx, sy, sr = S * 0.735, S * 0.335, S * 0.075
    pts = []
    for i in range(10):
        rad = sr if i % 2 == 0 else sr * 0.42
        a = math.radians(-90 + i * 36)
        pts.append((sx + rad * math.cos(a), sy + rad * math.sin(a)))
    sd.polygon(pts, fill=GOLD_DIM)
    img.alpha_composite(star)
    return img


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    img = build()
    img.resize((256, 256), Image.LANCZOS).save(ASSETS_DIR / "icon.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.resize((256, 256), Image.LANCZOS).save(ASSETS_DIR / "icon.ico", sizes=sizes)
    print("ecrit :", ASSETS_DIR / "icon.png", "et", ASSETS_DIR / "icon.ico")


if __name__ == "__main__":
    main()
