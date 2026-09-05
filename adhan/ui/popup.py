"""Notifications visuelles : banniere ornementee ou plein ecran.

Toutes les dimensions sont exprimees dans une grille de reference (1920x1080)
puis multipliees par le facteur deduit de l'ecran reellement detecte : la
notification garde les memes proportions sur un portable 1366x768 comme sur
un 4K, sans reglage manuel.
"""

from __future__ import annotations

import logging
import math
import tkinter as tk
from typing import Callable

from PIL import Image, ImageTk

from .. import screens
from ..paths import ICON_PNG
from . import theme as th

log = logging.getLogger(__name__)

# Dimensions de reference de la carte, avant mise a l'echelle.
BASE_W, BASE_H = 444, 176
FRAME_MS = 16

_icon_cache: dict[int, ImageTk.PhotoImage] = {}


def _icon(size: int) -> ImageTk.PhotoImage | None:
    """Icone de l'application redimensionnee (mise en cache par taille)."""
    size = max(8, int(size))
    if size in _icon_cache:
        return _icon_cache[size]
    try:
        img = Image.open(ICON_PNG).convert("RGBA").resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        _icon_cache[size] = photo
        return photo
    except (OSError, ValueError) as exc:
        log.debug("icone popup indisponible : %s", exc)
        return None


class _Popup(tk.Toplevel):
    """Base commune : fondu d'entree/sortie et arret propre des animations."""

    def __init__(self, master: tk.Misc, alpha: float = 0.92):
        super().__init__(master)
        self.max_alpha = alpha
        self._closing = False
        self._jobs: list[str] = []
        self.on_close: Callable[[], None] | None = None
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)
        self.bind("<Escape>", lambda _e: self.dismiss())
        # Visible et cliquable, mais sans jamais activer la fenetre : l'application
        # en cours d'utilisation garde le focus clavier.
        self.update_idletasks()
        screens.make_no_activate(self.winfo_id())
        self.bind("<Map>", lambda _e: screens.make_no_activate(self.winfo_id()), add="+")

    def _after(self, ms: int, func, *args) -> None:
        if not self._closing:
            self._jobs.append(self.after(ms, func, *args))

    def fade_in(self, step: int = 0, total: int = 14) -> None:
        if self._closing or not self.winfo_exists():
            return
        eased = 1 - (1 - min(1.0, step / total)) ** 3
        try:
            self.attributes("-alpha", self.max_alpha * eased)
        except tk.TclError:
            return
        self._on_fade(eased)
        if step < total:
            self._after(FRAME_MS, self.fade_in, step + 1, total)

    def _on_fade(self, eased: float) -> None:
        """Point d'extension : glissement de la banniere pendant le fondu."""

    def dismiss(self) -> None:
        if self._closing:
            return
        self._closing = True
        for job in self._jobs:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._jobs.clear()
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                log.exception("callback de fermeture en echec")
        self._fade_out()

    def _fade_out(self, step: int = 0, total: int = 8) -> None:
        if not self.winfo_exists():
            return
        try:
            self.attributes("-alpha", max(0.0, self.max_alpha * (1 - step / total)))
        except tk.TclError:
            return
        if step < total:
            self.after(FRAME_MS, self._fade_out, step + 1, total)
        else:
            self.destroy()


class Banner(_Popup):
    """Carte flottante ornementee, animee, avec compte a rebours de fermeture."""

    _stack: list["Banner"] = []

    def __init__(
        self,
        master: tk.Misc,
        title: str,
        subtitle: str,
        arabic: str = "",
        accent: str = th.GOLD,
        seconds: int = 30,
        position: str = "bas-droite",
        screen_index: int = 0,
        on_stop: Callable[[], None] | None = None,
        pulse: bool = False,
        ornaments: bool = True,
    ) -> None:
        super().__init__(master)
        self.accent = accent
        self.on_stop = on_stop
        self.position = position
        self.total_ms = max(3, int(seconds)) * 1000
        self.left_ms = self.total_ms
        self._phase = 0.0

        # Ecran et echelle resolus a l'affichage : suit les changements de setup.
        self.screen = screens.screen_at(screen_index)
        self.S = screens.ui_scale(self.screen)
        self.W = round(BASE_W * self.S)
        self.H = round(BASE_H * self.S)

        self.configure(bg=th.CHROMA)
        try:
            self.attributes("-transparentcolor", th.CHROMA)
        except tk.TclError:
            self.configure(bg=th.BG_ALT)

        self.f = th.fonts(self.S)
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg=th.CHROMA,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self._draw(title, subtitle, arabic, pulse, ornaments)
        self._place()

        Banner._stack.append(self)
        self.on_close = lambda: Banner._stack.remove(self) if self in Banner._stack else None
        self.fade_in()
        self._tick()
        if pulse:
            self._pulse()

    # ------------------------------------------------------------- dessin
    def _draw(self, title: str, subtitle: str, arabic: str, pulse: bool, ornaments: bool) -> None:
        c, S = self.canvas, self.S
        w, h = self.W - 4 * S, self.H - 5 * S

        # Ombre portee puis fond degrade de la carte.
        th.round_rect(c, 4 * S, 5 * S, w + 3 * S, h + 4 * S, r=20 * S, fill="#040f0c", outline="")
        th.round_rect(c, 0, 0, w, h, r=20 * S, fill=th.BG_ALT, outline="")
        for i in range(40):
            y = 2 * S + i * ((h - 4 * S) / 40)
            c.create_line(3 * S, y, w - 3 * S, y, fill=th.mix(th.BG_SOFT, th.BG, i / 39))
        th.round_rect(c, 0, 0, w, h, r=20 * S, fill="",
                      outline=th.mix(th.LINE, self.accent, 0.35), width=max(1, 1.6 * S))

        # Encadrement arabesque.
        if ornaments:
            th.arabesque_frame(c, 9 * S, 9 * S, w - 9 * S, h - 9 * S, self.accent,
                               radius=15 * S, corner_r=8 * S)

        # Medaillon a croissant, avec halo pulsant pendant l'adhan.
        cx, cy, r = 66 * S, 74 * S, 26 * S
        self._medallion = (cx, cy, r)
        self._halo = c.create_oval(cx - r - 6 * S, cy - r - 6 * S, cx + r + 6 * S, cy + r + 6 * S,
                                   outline=th.mix(th.BG_ALT, self.accent, 0.5), width=max(1, 1.5 * S))
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=th.mix(th.BG, self.accent, 0.10), outline=self.accent, width=max(1, 1.2 * S))
        self._img = _icon(38 * S)
        if self._img:
            c.create_image(cx, cy, image=self._img)
        else:
            th.crescent(c, cx, cy, r * 0.6, self.accent, th.BG)
        if not pulse:
            c.itemconfig(self._halo, state="hidden")

        # Textes — tronques avec ellipse pour ne jamais deborder de la carte
        # (le nom d'une mosquee n'est pas borne en longueur).
        arabic_w = self.f["arabic"].measure(arabic) if arabic else 0
        title_avail = w - 112 * S - 16 * S - (arabic_w + 14 * S if arabic else 0)
        subtitle_avail = w - 112 * S - 16 * S
        c.create_text(112 * S, 50 * S, text=th.fit_text(self.f["h2"], title, title_avail),
                      anchor="w", fill=th.TEXT, font=self.f["h2"])
        c.create_text(112 * S, 76 * S, text=th.fit_text(self.f["body"], subtitle, subtitle_avail),
                      anchor="w", fill=th.MUTED, font=self.f["body"])
        if arabic:
            c.create_text(w - 26 * S, 50 * S, text=arabic, anchor="e",
                          fill=self.accent, font=self.f["arabic"])

        # Actions.
        if self.on_stop:
            self._button(112 * S, 98 * S, 168 * S, 28 * S, "■   Arrêter l'adhan", self._stop)
            self._button(292 * S, 98 * S, 92 * S, 28 * S, "Fermer", self.dismiss, subtle=True)
        else:
            self._button(112 * S, 98 * S, 116 * S, 28 * S, "OK, compris", self.dismiss, subtle=True)

        # Barre de progression, entre les etoiles d'angle du bas.
        y, x1, x2 = h - 26 * S, 46 * S, w - 46 * S
        c.create_rectangle(x1, y, x2, y + 3 * S, fill=th.mix(th.BG, self.accent, 0.18), outline="")
        self._bar = c.create_rectangle(x1, y, x2, y + 3 * S, fill=self.accent, outline="")
        self._bar_span = (x1, x2, y)

    def _button(self, x, y, w, h, text, command, subtle: bool = False):
        c, S = self.canvas, self.S
        fill = th.BG_SOFT if subtle else self.accent
        fg = th.TEXT if subtle else th.BG
        rect = th.round_rect(c, x, y, x + w, y + h, r=14 * S, fill=fill,
                             outline=th.LINE if subtle else "")
        label = c.create_text(x + w / 2, y + h / 2, text=text, fill=fg, font=self.f["small"])
        hover = th.LINE if subtle else th.mix(fill, "#ffffff", 0.2)
        for item in (rect, label):
            c.tag_bind(item, "<Button-1>", lambda _e: command())
            c.tag_bind(item, "<Enter>", lambda _e: (c.itemconfig(rect, fill=hover),
                                                    c.config(cursor="hand2")))
            c.tag_bind(item, "<Leave>", lambda _e: (c.itemconfig(rect, fill=fill),
                                                    c.config(cursor="")))
        return rect

    # ---------------------------------------------------------- placement
    def _place(self) -> None:
        offset = sum(b.H + 12 * b.S for b in Banner._stack if b.winfo_exists())
        x, y = screens.anchor_box(self.screen, self.position, self.W, self.H,
                                  margin=round(20 * self.S), offset=round(offset))
        self._target = (x, y)
        self._slide = round((-46 if "gauche" in self.position else 46) * self.S)
        self.geometry(f"{self.W}x{self.H}+{x + self._slide}+{y}")

    def _on_fade(self, eased: float) -> None:
        x, y = self._target
        self.geometry(f"{self.W}x{self.H}+{int(x + self._slide * (1 - eased))}+{y}")

    # ---------------------------------------------------------- animation
    def _pulse(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        self._phase += 0.13
        cx, cy, r = self._medallion
        grow = 7 * self.S * (1 + math.sin(self._phase)) / 2
        pad = 4 * self.S + grow
        self.canvas.coords(self._halo, cx - r - pad, cy - r - pad, cx + r + pad, cy + r + pad)
        t = 0.25 + 0.55 * (1 + math.sin(self._phase)) / 2
        self.canvas.itemconfig(self._halo, outline=th.mix(th.BG, self.accent, t))
        self._after(45, self._pulse)

    def _tick(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        self.left_ms -= 100
        ratio = max(0.0, self.left_ms / self.total_ms)
        x1, x2, y = self._bar_span
        self.canvas.coords(self._bar, x1, y, x1 + (x2 - x1) * ratio, y + 3 * self.S)
        if self.left_ms <= 0:
            self.dismiss()
            return
        self._after(100, self._tick)

    def _stop(self) -> None:
        if self.on_stop:
            self.on_stop()
        self.dismiss()


# Dimensions de reference de l'alerte de suivi post-adhan.
CHECK_W, CHECK_H = 460, 200


class PrayerCheck(_Popup):
    """Alerte post-adhan : « avez-vous prie ? », avec boutons a icone de mosquee.

    Distincte des rappels par sa couleur ambre et son icone pulsante, pour
    ne pas se confondre avec une simple notification informative. Repond
    « Oui » annule les alertes suivantes pour cette priere ; « Pas encore »
    (ou l'expiration du delai) laisse les prochaines alertes se declencher
    normalement.
    """

    def __init__(
        self,
        master: tk.Misc,
        prayer_label: str,
        subtitle: str,
        arabic: str = "",
        seconds: int = 45,
        position: str = "bas-droite",
        screen_index: int = 0,
        on_yes: Callable[[], None] | None = None,
        on_no: Callable[[], None] | None = None,
        ornaments: bool = True,
    ) -> None:
        super().__init__(master)
        self.accent = th.ALERT
        self.on_yes = on_yes
        self.on_no = on_no
        self.position = position
        self.total_ms = max(3, int(seconds)) * 1000
        self.left_ms = self.total_ms
        self._phase = 0.0
        self._answered = False

        self.screen = screens.screen_at(screen_index)
        self.S = screens.ui_scale(self.screen)
        self.W = round(CHECK_W * self.S)
        self.H = round(CHECK_H * self.S)

        self.configure(bg=th.CHROMA)
        try:
            self.attributes("-transparentcolor", th.CHROMA)
        except tk.TclError:
            self.configure(bg=th.BG_ALT)

        self.f = th.fonts(self.S)
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg=th.CHROMA,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self._draw(prayer_label, subtitle, arabic, ornaments)
        self._place()

        self.fade_in()
        self._tick()
        self._pulse()

    # ------------------------------------------------------------- dessin
    def _draw(self, prayer_label: str, subtitle: str, arabic: str, ornaments: bool) -> None:
        c, S = self.canvas, self.S
        w, h = self.W - 4 * S, self.H - 5 * S

        th.round_rect(c, 4 * S, 5 * S, w + 3 * S, h + 4 * S, r=20 * S, fill="#0f0a04", outline="")
        th.round_rect(c, 0, 0, w, h, r=20 * S, fill=th.BG_ALT, outline="")
        for i in range(40):
            y = 2 * S + i * ((h - 4 * S) / 40)
            c.create_line(3 * S, y, w - 3 * S, y, fill=th.mix(th.BG_SOFT, th.BG, i / 39))
        th.round_rect(c, 0, 0, w, h, r=20 * S, fill="",
                      outline=th.mix(th.LINE, self.accent, 0.5), width=max(1, 1.6 * S))
        if ornaments:
            th.arabesque_frame(c, 9 * S, 9 * S, w - 9 * S, h - 9 * S, self.accent,
                               radius=15 * S, corner_r=8 * S)

        # Icone de mosquee pulsante : le point d'alerte.
        cx, cy, r = 60 * S, 56 * S, 24 * S
        self._medallion = (cx, cy, r)
        self._halo = c.create_oval(cx - r - 6 * S, cy - r - 6 * S, cx + r + 6 * S, cy + r + 6 * S,
                                   outline=self.accent, width=max(1, 1.5 * S))
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=th.mix(th.BG, self.accent, 0.12), outline=self.accent, width=max(1, 1.2 * S))
        th.mosque_glyph(c, cx, cy + r * 0.12, r * 0.62, self.accent,
                        th.mix(th.BG, self.accent, 0.12), filled=True)

        # Textes — memes precautions de troncature que la banniere.
        arabic_w = self.f["arabic"].measure(arabic) if arabic else 0
        title_avail = w - 104 * S - 16 * S - (arabic_w + 14 * S if arabic else 0)
        subtitle_avail = w - 104 * S - 16 * S
        c.create_text(104 * S, 34 * S, text=th.fit_text(self.f["h2"], prayer_label, title_avail),
                      anchor="w", fill=th.TEXT, font=self.f["h2"])
        c.create_text(104 * S, 60 * S, text=th.fit_text(self.f["small"], subtitle, subtitle_avail),
                      anchor="w", fill=th.MUTED, font=self.f["small"])
        if arabic:
            c.create_text(w - 26 * S, 34 * S, text=arabic, anchor="e",
                          fill=self.accent, font=self.f["arabic"])

        # Boutons a icone de mosquee : contour = pas encore, plein = confirme.
        # Largeur calculee depuis les marges reelles de la carte (26*S de
        # chaque cote) : l'ancien calcul supposait des boutons partant de 0
        # alors qu'ils demarrent a 94*S, ce qui faisait deborder le second.
        by, bh = 92 * S, 46 * S
        margin, gap = 26 * S, 12 * S
        bw = (w - 2 * margin - gap) / 2
        self._icon_button(margin, by, bw, bh, "Pas encore", self._no,
                          filled=False, fg=th.TEXT, fill=th.BG_SOFT)
        self._icon_button(margin + bw + gap, by, bw, bh, "J'ai prié", self._yes,
                          filled=True, fg=th.BG, fill=self.accent)

        y, x1, x2 = h - 20 * S, 46 * S, w - 46 * S
        c.create_rectangle(x1, y, x2, y + 3 * S, fill=th.mix(th.BG, self.accent, 0.18), outline="")
        self._bar = c.create_rectangle(x1, y, x2, y + 3 * S, fill=self.accent, outline="")
        self._bar_span = (x1, x2, y)

    def _icon_button(self, x, y, w, h, text, command, filled: bool, fg: str, fill: str):
        c, S = self.canvas, self.S
        rect = th.round_rect(c, x, y, x + w, y + h, r=13 * S, fill=fill,
                             outline="" if filled else th.LINE)
        icon_cx = x + 20 * S
        th.mosque_glyph(c, icon_cx, y + h / 2 + 2 * S, 9 * S, fg, fill,
                        filled=filled, width=max(1, 1.3 * S))
        label = c.create_text(x + 36 * S, y + h / 2, text=text, anchor="w", fill=fg, font=self.f["small"])
        hover = th.mix(fill, "#ffffff", 0.18) if filled else th.LINE
        for item in (rect, label):
            c.tag_bind(item, "<Button-1>", lambda _e: command())
            c.tag_bind(item, "<Enter>", lambda _e: (c.itemconfig(rect, fill=hover),
                                                    c.config(cursor="hand2")))
            c.tag_bind(item, "<Leave>", lambda _e: (c.itemconfig(rect, fill=fill),
                                                    c.config(cursor="")))

    # ---------------------------------------------------------- placement
    def _place(self) -> None:
        x, y = screens.anchor_box(self.screen, self.position, self.W, self.H, margin=round(20 * self.S))
        self._target = (x, y)
        self._slide = round((-46 if "gauche" in self.position else 46) * self.S)
        self.geometry(f"{self.W}x{self.H}+{x + self._slide}+{y}")

    def _on_fade(self, eased: float) -> None:
        x, y = self._target
        self.geometry(f"{self.W}x{self.H}+{int(x + self._slide * (1 - eased))}+{y}")

    # ---------------------------------------------------------- animation
    def _pulse(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        self._phase += 0.13
        cx, cy, r = self._medallion
        grow = 7 * self.S * (1 + math.sin(self._phase)) / 2
        pad = 4 * self.S + grow
        self.canvas.coords(self._halo, cx - r - pad, cy - r - pad, cx + r + pad, cy + r + pad)
        t = 0.35 + 0.5 * (1 + math.sin(self._phase)) / 2
        self.canvas.itemconfig(self._halo, outline=th.mix(th.BG, self.accent, t))
        self._after(45, self._pulse)

    def _tick(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        self.left_ms -= 100
        ratio = max(0.0, self.left_ms / self.total_ms)
        x1, x2, y = self._bar_span
        self.canvas.coords(self._bar, x1, y, x1 + (x2 - x1) * ratio, y + 3 * self.S)
        if self.left_ms <= 0:
            # Expiration sans reponse = equivalent a « pas encore » : les
            # prochaines alertes ne sont pas annulees.
            self.dismiss()
            return
        self._after(100, self._tick)

    def _yes(self) -> None:
        if not self._answered:
            self._answered = True
            if self.on_yes:
                self.on_yes()
        self.dismiss()

    def _no(self) -> None:
        if not self._answered:
            self._answered = True
            if self.on_no:
                self.on_no()
        self.dismiss()


class Fullscreen(_Popup):
    """Voile plein ecran, tres visible, pour l'adhan."""

    def __init__(
        self,
        master: tk.Misc,
        title: str,
        subtitle: str,
        clock: str,
        arabic: str = "",
        accent: str = th.GOLD,
        seconds: int = 90,
        screen_index: int = 0,
        on_stop: Callable[[], None] | None = None,
        ornaments: bool = True,
    ) -> None:
        super().__init__(master, alpha=0.86)
        self.accent = accent
        self.on_stop = on_stop
        self.total_ms = max(5, int(seconds)) * 1000
        self.left_ms = self.total_ms
        self._phase = 0.0

        screen = screens.screen_at(screen_index)
        # Le voile epouse la resolution reelle de l'ecran choisi.
        self.S = screens.ui_scale(screen)
        self.geometry(f"{screen.width}x{screen.height}+{screen.x}+{screen.y}")
        self.configure(bg=th.BG)
        self.f = th.fonts(self.S)
        self.canvas = tk.Canvas(self, width=screen.width, height=screen.height,
                                bg=th.BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._draw(screen.width, screen.height, title, subtitle, clock, arabic, ornaments)
        self.canvas.bind("<Button-3>", lambda _e: self.dismiss())
        self.fade_in(total=18)
        self._tick()
        self._pulse()

    def _draw(self, w: int, h: int, title: str, subtitle: str, clock: str,
              arabic: str, ornaments: bool) -> None:
        c, S = self.canvas, self.S
        th.vertical_gradient(c, 0, 0, w, h, th.BG_ALT, "#04100d", steps=90)

        # Semis d'etoiles tres discret, densite proportionnelle a l'ecran.
        faint = th.mix(th.BG, self.accent, 0.10)
        step = round(120 * S)
        for row in range(0, h + step, step):
            for col in range(0, w + step, step):
                th.star_filled(c, col + (step // 2 if (row // step) % 2 else 0), row, 5 * S, faint)

        margin = round(46 * S)
        if ornaments:
            th.arabesque_frame(c, margin, margin, w - margin, h - margin,
                               th.mix(th.BG, self.accent, 0.75), radius=34 * S, corner_r=17 * S)
            th.arch(c, w / 2, margin + 104 * S, min(w * 0.4, 320 * S), 74 * S,
                    th.mix(th.BG, self.accent, 0.55), width=max(1, 1.6 * S))

        # Bloc central : proportions calees sur la hauteur reelle de l'ecran.
        cy = h / 2
        r = min(78 * S, h * 0.085)
        gap = min(210 * S, h * 0.21)
        mx, my = w / 2, cy - gap
        self._halo_box = (mx, my, r)
        self._halo = c.create_oval(mx - r, my - r, mx + r, my + r,
                                   outline=th.mix(th.BG, self.accent, 0.4), width=max(1, 2 * S))
        c.create_oval(mx - r, my - r, mx + r, my + r,
                      fill=th.mix(th.BG, self.accent, 0.08), outline=self.accent, width=max(1, 2 * S))
        self._img = _icon(r * 1.45)
        if self._img:
            c.create_image(mx, my, image=self._img)
        else:
            th.crescent(c, mx, my, r * 0.6, self.accent, th.BG)

        # Le titre est borne (liste fixe de prieres) mais le nom de mosquee
        # dans le sous-titre ne l'est pas : on le tronque par securite.
        text_avail = w - 2 * margin - 60 * S
        if arabic:
            c.create_text(mx, cy - h * 0.09, text=arabic, fill=self.accent, font=self.f["arabic_big"])
        c.create_text(mx, cy - h * 0.03, text=th.fit_text(self.f["huge"], title, text_avail),
                      fill=th.TEXT, font=self.f["huge"])
        c.create_text(mx, cy + h * 0.065, text=clock, fill=self.accent, font=self.f["huge_clock"])
        c.create_text(mx, cy + h * 0.13, text=th.fit_text(self.f["h3"], subtitle, text_avail),
                      fill=th.MUTED, font=self.f["h3"])

        by, bh = cy + h * 0.19, 46 * S
        if self.on_stop:
            self._button(mx - 200 * S, by, 200 * S, bh, "■   Arrêter l'adhan", self._stop)
            self._button(mx + 12 * S, by, 188 * S, bh, "Fermer", self.dismiss, subtle=True)
        else:
            self._button(mx - 94 * S, by, 188 * S, bh, "Fermer", self.dismiss, subtle=True)

        c.create_text(mx, h - margin - 28 * S, text="Échap ou clic droit pour fermer",
                      fill=th.mix(th.BG, th.MUTED, 0.7), font=self.f["small"])

        y, x1, x2 = h - margin + 6 * S, margin + 74 * S, w - margin - 74 * S
        c.create_rectangle(x1, y, x2, y + 4 * S, fill=th.mix(th.BG, self.accent, 0.2), outline="")
        self._bar = c.create_rectangle(x1, y, x2, y + 4 * S, fill=self.accent, outline="")
        self._bar_span = (x1, x2, y)

    def _button(self, x, y, w, h, text, command, subtle: bool = False):
        c, S = self.canvas, self.S
        fill = th.BG_SOFT if subtle else self.accent
        fg = th.TEXT if subtle else th.BG
        rect = th.round_rect(c, x, y, x + w, y + h, r=22 * S, fill=fill,
                             outline=th.LINE if subtle else "")
        label = c.create_text(x + w / 2, y + h / 2, text=text, fill=fg, font=self.f["h3"])
        hover = th.LINE if subtle else th.mix(fill, "#ffffff", 0.2)
        for item in (rect, label):
            c.tag_bind(item, "<Button-1>", lambda _e: command())
            c.tag_bind(item, "<Enter>", lambda _e: (c.itemconfig(rect, fill=hover),
                                                    c.config(cursor="hand2")))
            c.tag_bind(item, "<Leave>", lambda _e: (c.itemconfig(rect, fill=fill),
                                                    c.config(cursor="")))

    def _pulse(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        self._phase += 0.09
        cx, cy, r = self._halo_box
        pad = 8 * self.S + 18 * self.S * (1 + math.sin(self._phase)) / 2
        self.canvas.coords(self._halo, cx - r - pad, cy - r - pad, cx + r + pad, cy + r + pad)
        t = 0.18 + 0.5 * (1 + math.sin(self._phase)) / 2
        self.canvas.itemconfig(self._halo, outline=th.mix(th.BG, self.accent, t))
        self._after(45, self._pulse)

    def _tick(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        self.left_ms -= 200
        ratio = max(0.0, self.left_ms / self.total_ms)
        x1, x2, y = self._bar_span
        self.canvas.coords(self._bar, x1, y, x1 + (x2 - x1) * ratio, y + 4 * self.S)
        if self.left_ms <= 0:
            self.dismiss()
            return
        self._after(200, self._tick)

    def _stop(self) -> None:
        if self.on_stop:
            self.on_stop()
        self.dismiss()
