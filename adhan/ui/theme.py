"""Palette, polices et primitives de dessin (dont les ornements arabesques)."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import font as tkfont

# --------------------------------------------------------------- palette
BG = "#0b1f1a"          # fond principal
BG_ALT = "#102a24"      # cartes
BG_SOFT = "#16382f"     # survol / champs
LINE = "#1e4a3e"        # separateurs
TEXT = "#eaf3ef"        # texte principal
MUTED = "#8fb3a6"       # texte secondaire
GOLD = "#f0c46a"        # accent principal
GOLD_DIM = "#c9a253"
GREEN = "#4ec98f"       # etat OK
RED = "#e2725b"         # alerte / arret

# Couleurs d'accent proposees pour les notifications.
ACCENTS = {
    "Or": "#f0c46a",
    "Émeraude": "#4ec98f",
    "Turquoise": "#5bc8d6",
    "Ambre": "#f0a04b",
    "Rose": "#e58fa5",
    "Violet": "#b492e8",
    "Blanc": "#e8eef0",
}

# Couleur-cle rendue transparente par Windows (absente de la palette).
CHROMA = "#ff00fe"


# --------------------------------------------------------------- polices
_BASE_SIZES = {
    "h1": ("ui", 22, "bold"),
    "h2": ("ui", 14, "bold"),
    "h3": ("ui", 11, "bold"),
    "body": ("ui", 10, "normal"),
    "small": ("ui", 9, "normal"),
    "tiny": ("ui", 8, "normal"),
    "clock": ("mono", 30, "bold"),
    "clock_sm": ("mono", 13, "bold"),
    "arabic": ("ar", 13, "normal"),
    "arabic_big": ("ar", 26, "normal"),
    "huge": ("ui", 46, "bold"),
    "huge_clock": ("mono", 64, "bold"),
}


def fonts(scale: float = 1.0) -> dict[str, tkfont.Font]:
    """Polices de l'application, mises a l'echelle de l'ecran (racine Tk requise)."""
    available = set(tkfont.families())
    ui = "Segoe UI" if "Segoe UI" in available else "Arial"
    mono = "Consolas" if "Consolas" in available else "Courier New"
    arabic = next((f for f in ("Segoe UI", "Traditional Arabic", "Arial") if f in available), ui)
    families = {"ui": ui, "mono": mono, "ar": arabic}
    return {
        name: tkfont.Font(family=families[fam], size=max(7, round(size * scale)), weight=weight)
        for name, (fam, size, weight) in _BASE_SIZES.items()
    }


# ------------------------------------------------------------- couleurs
def mix(color_a: str, color_b: str, t: float) -> str:
    """Interpolation lineaire entre deux couleurs #rrggbb."""
    t = max(0.0, min(1.0, t))
    a = tuple(int(color_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# ---------------------------------------------------------------- formes
def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r=14, **kwargs):
    """Rectangle a coins arrondis sur un Canvas."""
    r = min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def vertical_gradient(canvas: tk.Canvas, x1, y1, x2, y2, top: str, bottom: str, steps: int = 60):
    """Remplit une zone d'un degrade vertical (bandes fines)."""
    band = max(1, (y2 - y1)) / steps
    for i in range(steps):
        canvas.create_rectangle(
            x1, y1 + i * band, x2, y1 + (i + 1) * band + 1,
            fill=mix(top, bottom, i / max(1, steps - 1)), outline="",
        )


# ------------------------------------------------------------ ornements
def star8(canvas: tk.Canvas, cx: float, cy: float, r: float, color: str, width: float = 1.4):
    """Rub el Hizb : deux carres superposes formant une etoile a huit branches."""
    items = []
    for rot in (0, 45):
        pts = []
        for i in range(4):
            a = math.radians(rot + 45 + i * 90)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        items.append(canvas.create_polygon(pts, fill="", outline=color, width=width))
    return items


def star_filled(canvas: tk.Canvas, cx: float, cy: float, r: float, color: str, points: int = 8):
    """Etoile pleine a N branches (motif discret)."""
    pts = []
    for i in range(points * 2):
        rad = r if i % 2 == 0 else r * 0.42
        a = math.radians(-90 + i * (180 / points))
        pts += [cx + rad * math.cos(a), cy + rad * math.sin(a)]
    return canvas.create_polygon(pts, fill=color, outline="")


def diamond(canvas: tk.Canvas, cx: float, cy: float, r: float, color: str, fill: bool = True):
    pts = [cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy]
    if fill:
        return canvas.create_polygon(pts, fill=color, outline="")
    return canvas.create_polygon(pts, fill="", outline=color, width=1)


def arch(canvas: tk.Canvas, cx: float, cy: float, w: float, h: float, color: str, width: float = 1.4):
    """Arc brise (mihrab) stylise, dessine en polyligne."""
    half = w / 2
    pts = [(cx - half, cy)]
    for i in range(21):
        t = i / 20
        # Deux quarts d'ellipse se rejoignant en pointe au sommet.
        x = -half + w * t
        y = -h * math.sin(math.pi * t) ** 0.75
        pts.append((cx + x, cy + y))
    pts.append((cx + half, cy))
    flat = [c for p in pts for c in p]
    return canvas.create_line(*flat, fill=color, width=width, smooth=True)


def arabesque_frame(
    canvas: tk.Canvas,
    x1: float, y1: float, x2: float, y2: float,
    color: str,
    radius: float = 18,
    corner_r: float = 9,
    dots: bool = True,
) -> None:
    """Encadrement ornemental : double filet, etoiles d'angle et semis de losanges."""
    faint = mix(BG_ALT, color, 0.45)
    # Double filet (le classique cadre de manuscrit).
    round_rect(canvas, x1, y1, x2, y2, r=radius, fill="", outline=color, width=1.4)
    round_rect(canvas, x1 + 5, y1 + 5, x2 - 5, y2 - 5, r=max(4, radius - 5),
               fill="", outline=faint, width=1)

    # Etoiles a huit branches dans les quatre angles.
    inset = radius * 0.72
    for cx, cy in ((x1 + inset, y1 + inset), (x2 - inset, y1 + inset),
                   (x1 + inset, y2 - inset), (x2 - inset, y2 - inset)):
        star8(canvas, cx, cy, corner_r, color, width=1.2)
        canvas.create_oval(cx - 1.6, cy - 1.6, cx + 1.6, cy + 1.6, fill=color, outline="")

    if not dots:
        return
    # Semis de losanges le long des bords horizontaux.
    span_x = (x2 - x1) - 2 * (inset + corner_r + 10)
    count = max(3, int(span_x // 26))
    start = x1 + inset + corner_r + 10
    step = span_x / max(1, count)
    for i in range(count + 1):
        cx = start + i * step
        diamond(canvas, cx, y1 + 5, 2.6, faint)
        diamond(canvas, cx, y2 - 5, 2.6, faint)


def crescent(canvas: tk.Canvas, cx: float, cy: float, r: float, color: str, bg: str):
    """Croissant dessine par soustraction visuelle (disque + disque de fond)."""
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
    r2 = r * 0.86
    ox, oy = cx + r * 0.34, cy - r * 0.10
    canvas.create_oval(ox - r2, oy - r2, ox + r2, oy + r2, fill=bg, outline="")
