"""Widget permanent : rappel discret de la prochaine priere, toujours visible.

Fenetre sans bordure, tres peu opaque, posable sur n'importe quel ecran.
La position est memorisee en fractions de la zone utile, donc conservee
meme si la resolution ou le nombre d'ecrans change.
"""

from __future__ import annotations

import datetime as dt
import logging
import tkinter as tk
from typing import Callable

from PIL import Image, ImageTk

from .. import screens
from ..paths import ICON_PNG
from . import theme as th

log = logging.getLogger(__name__)

BASE_W, BASE_H = 268, 84
BASE_W_COMPACT, BASE_H_COMPACT = 196, 56


def format_delay(delta: dt.timedelta) -> str:
    """Duree restante en texte court : 1 h 23 / 12 min / 45 s."""
    total = max(0, int(delta.total_seconds()))
    if total >= 3600:
        h, rest = divmod(total, 3600)
        return f"{h} h {rest // 60:02d}"
    if total >= 60:
        return f"{total // 60} min"
    return f"{total} s"


class Overlay(tk.Toplevel):
    """Petite carte flottante, deplacable, mise a jour chaque seconde."""

    def __init__(self, master: tk.Misc, config, on_move: Callable[[], None] | None = None):
        super().__init__(master)
        self.config_ref = config
        self.on_move = on_move
        self._drag: tuple[int, int] | None = None
        self._img: ImageTk.PhotoImage | None = None
        self._hovering = False

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=th.CHROMA)
        try:
            self.attributes("-transparentcolor", th.CHROMA)
        except tk.TclError:
            self.configure(bg=th.BG_ALT)

        self.canvas = tk.Canvas(self, bg=th.CHROMA, highlightthickness=0, bd=0)
        self.canvas.pack()
        # Jamais d'activation : le widget ne prend pas la main sur l'application
        # en cours et n'apparait ni dans Alt+Tab ni dans la barre des taches.
        self.update_idletasks()
        screens.make_no_activate(self.winfo_id())
        self.bind("<Map>", lambda _e: screens.make_no_activate(self.winfo_id()), add="+")
        self._bind_events()
        self.refresh_style()

    # -------------------------------------------------------------- reglages
    @property
    def settings(self) -> dict:
        return self.config_ref.data["overlay"]

    def refresh_style(self) -> None:
        """Reconstruit la carte apres un changement de reglage."""
        s = self.settings
        self.screen = screens.screen_at(int(s.get("screen", 0)))
        self.S = screens.ui_scale(self.screen)
        compact = s.get("size") == "compact"
        base_w, base_h = (BASE_W_COMPACT, BASE_H_COMPACT) if compact else (BASE_W, BASE_H)
        self.W, self.H = round(base_w * self.S), round(base_h * self.S)
        self.compact = compact
        self.accent = s.get("accent") or th.GOLD
        self.f = th.fonts(self.S)
        self.canvas.config(width=self.W, height=self.H)
        self._build()
        self.apply_position()
        self.apply_opacity()
        self.apply_click_through()

    def apply_opacity(self) -> None:
        base = max(5, min(100, int(self.settings.get("opacity", 18)))) / 100
        value = min(0.97, base + 0.5) if self._hovering else base
        try:
            self.attributes("-alpha", value)
        except tk.TclError:
            pass

    def apply_click_through(self) -> None:
        enabled = bool(self.settings.get("click_through", False))
        try:
            screens.make_click_through(self.winfo_id(), enabled)
            # Toute modification du style etendu peut invalider la couleur-cle :
            # on la redemande a Tk juste apres.
            self.attributes("-transparentcolor", th.CHROMA)
            self.apply_opacity()
        except tk.TclError:
            pass

    def apply_position(self) -> None:
        """Place la carte d'apres le coin choisi, ou les fractions memorisees."""
        s = self.settings
        left, top, right, bottom = self.screen.work
        if s.get("position") == "libre":
            x = left + float(s.get("rel_x", 0.8)) * (right - left)
            y = top + float(s.get("rel_y", 0.05)) * (bottom - top)
        else:
            x, y = screens.anchor_box(self.screen, s.get("position", "haut-droite"),
                                      self.W, self.H, margin=round(16 * self.S))
        # On garde toujours la carte entierement visible sur son ecran.
        x = max(left, min(int(x), right - self.W))
        y = max(top, min(int(y), bottom - self.H))
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")

    def _store_position(self) -> None:
        left, top, right, bottom = self.screen.work
        s = self.settings
        s["position"] = "libre"
        s["rel_x"] = round((self.winfo_x() - left) / max(1, right - left), 4)
        s["rel_y"] = round((self.winfo_y() - top) / max(1, bottom - top), 4)
        if self.on_move:
            self.on_move()

    # ----------------------------------------------------------------- dessin
    def _build(self) -> None:
        c, S = self.canvas, self.S
        c.delete("all")
        w, h = self.W - 2, self.H - 2

        th.round_rect(c, 0, 0, w, h, r=(10 if self.compact else 14) * S,
                      fill=th.BG_ALT, outline=th.mix(th.LINE, self.accent, 0.5),
                      width=max(1, 1.2 * S))
        if not self.compact:
            # Ornement leger : filet interieur et etoiles d'angle.
            th.arabesque_frame(c, 5 * S, 5 * S, w - 5 * S, h - 5 * S, self.accent,
                               radius=9 * S, corner_r=4.5 * S, dots=False)

        icon_size = (20 if self.compact else 30) * S
        cx = (22 if self.compact else 34) * S
        self._img = None
        try:
            img = Image.open(ICON_PNG).convert("RGBA").resize(
                (max(8, int(icon_size)),) * 2, Image.LANCZOS)
            self._img = ImageTk.PhotoImage(img)
            c.create_image(cx, h / 2, image=self._img)
        except (OSError, ValueError):
            th.crescent(c, cx, h / 2, icon_size * 0.4, self.accent, th.BG_ALT)

        tx = cx + icon_size * 0.75
        if self.compact:
            self.t_name = c.create_text(tx, h / 2, text="—", anchor="w",
                                        fill=th.TEXT, font=self.f["small"])
            self.t_time = c.create_text(w - 10 * S, h / 2, text="", anchor="e",
                                        fill=self.accent, font=self.f["small"])
            self.t_delay = None
            self._time_avail = w - tx - 20 * S
        else:
            self.t_name = c.create_text(tx, 28 * S, text="—", anchor="w",
                                        fill=th.TEXT, font=self.f["h3"])
            self.t_time = c.create_text(tx, 52 * S, text="", anchor="w",
                                        fill=th.MUTED, font=self.f["small"])
            self.t_delay = c.create_text(w - 16 * S, 40 * S, text="", anchor="e",
                                         fill=self.accent, font=self.f["clock_sm"])
            # Largeur disponible pour la ligne heure+mosquee, mesuree en pixels :
            # un nom de mosquee n'est pas borne en longueur.
            self._time_avail = w - tx - 14 * S

    # ----------------------------------------------------------- interaction
    def _bind_events(self) -> None:
        for widget in (self, self.canvas):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<ButtonRelease-1>", self._drag_end)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)

    def _enter(self, _e=None) -> None:
        self._hovering = True
        self.apply_opacity()

    def _leave(self, _e=None) -> None:
        self._hovering = False
        self.apply_opacity()

    def _drag_start(self, event) -> None:
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_move(self, event) -> None:
        if not self._drag:
            return
        self.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def _drag_end(self, _event) -> None:
        if not self._drag:
            return
        self._drag = None
        # La carte peut avoir ete deposee sur un autre ecran : on le retrouve.
        cx, cy = self.winfo_x() + self.W // 2, self.winfo_y() + self.H // 2
        for scr in screens.list_screens():
            if scr.x <= cx < scr.x + scr.width and scr.y <= cy < scr.y + scr.height:
                self.screen = scr
                self.settings["screen"] = scr.index
                break
        self._store_position()

    # ---------------------------------------------------------------- contenu
    def update_content(self, prayer_label: str, prayer_time: dt.datetime | None,
                       now: dt.datetime, mosque: str = "") -> None:
        if not self.winfo_exists():
            return
        c = self.canvas
        if prayer_time is None:
            c.itemconfig(self.t_name, text="Aucun horaire")
            c.itemconfig(self.t_time, text=th.fit_text(self.f["small"], mosque or "", self._time_avail))
            if self.t_delay:
                c.itemconfig(self.t_delay, text="—")
            return
        delay = format_delay(prayer_time - now)
        if self.compact:
            c.itemconfig(self.t_name, text=f"{prayer_label}  {prayer_time:%H:%M}")
            c.itemconfig(self.t_time, text=delay)
        else:
            c.itemconfig(self.t_name, text=prayer_label)
            line = f"{prayer_time:%H:%M}  ·  {mosque}"
            c.itemconfig(self.t_time, text=th.fit_text(self.f["small"], line, self._time_avail))
            c.itemconfig(self.t_delay, text=delay)
