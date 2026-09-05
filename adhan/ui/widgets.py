"""Widgets Tk habilles aux couleurs de l'application."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from . import theme as th


class Fonts:
    """Conteneur de polices partage par toute la fenetre."""

    _cache: dict[float, dict] = {}

    @classmethod
    def get(cls, scale: float = 1.0) -> dict:
        key = round(scale, 2)
        if key not in cls._cache:
            cls._cache[key] = th.fonts(key)
        return cls._cache[key]


def card(parent: tk.Misc, **kwargs) -> tk.Frame:
    opts = {"bg": th.BG_ALT, "highlightbackground": th.LINE, "highlightthickness": 1, "bd": 0}
    opts.update(kwargs)
    return tk.Frame(parent, **opts)


def label(parent: tk.Misc, text: str = "", style: str = "body", color: str = th.TEXT,
          bg: str = th.BG_ALT, fonts: dict | None = None, **kwargs) -> tk.Label:
    f = (fonts or Fonts.get())[style]
    return tk.Label(parent, text=text, font=f, fg=color, bg=bg, anchor="w", **kwargs)


def button(parent: tk.Misc, text: str, command: Callable[[], None], primary: bool = False,
           danger: bool = False, fonts: dict | None = None, width: int | None = None,
           **kwargs) -> tk.Button:
    f = (fonts or Fonts.get())["small"]
    if danger:
        bg, fg, active = th.BG_SOFT, th.RED, th.LINE
    elif primary:
        bg, fg, active = th.GOLD, th.BG, th.mix(th.GOLD, "#ffffff", 0.25)
    else:
        bg, fg, active = th.BG_SOFT, th.TEXT, th.LINE
    btn = tk.Button(
        parent, text=text, command=command, font=f, bg=bg, fg=fg,
        activebackground=active, activeforeground=fg, relief="flat", bd=0,
        padx=14, pady=7, cursor="hand2", highlightthickness=0, **kwargs
    )
    if width:
        btn.config(width=width)
    btn.bind("<Enter>", lambda _e: btn.config(bg=active))
    btn.bind("<Leave>", lambda _e: btn.config(bg=bg))
    return btn


def entry(parent: tk.Misc, textvariable: tk.Variable, fonts: dict | None = None,
          width: int = 24, **kwargs) -> tk.Entry:
    f = (fonts or Fonts.get())["body"]
    return tk.Entry(
        parent, textvariable=textvariable, font=f, bg=th.BG_SOFT, fg=th.TEXT,
        insertbackground=th.GOLD, relief="flat", bd=0, width=width,
        highlightthickness=1, highlightbackground=th.LINE, highlightcolor=th.GOLD, **kwargs
    )


def checkbox(parent: tk.Misc, text: str, variable: tk.Variable,
             command: Callable[[], None] | None = None, bg: str = th.BG_ALT,
             fonts: dict | None = None) -> tk.Checkbutton:
    f = (fonts or Fonts.get())["body"]
    return tk.Checkbutton(
        parent, text=text, variable=variable, command=command, font=f,
        bg=bg, fg=th.TEXT, activebackground=bg, activeforeground=th.TEXT,
        selectcolor=th.BG, relief="flat", bd=0, highlightthickness=0,
        anchor="w", cursor="hand2", padx=2,
    )


class Slider(tk.Canvas):
    """Curseur dessine a la main : le widget Tk natif ignore le theme sombre."""

    def __init__(self, parent: tk.Misc, variable: tk.Variable, from_: int, to: int,
                 command: Callable[[str], None] | None = None, bg: str = th.BG_ALT,
                 length: int = 220, scale: float = 1.0, suffix: str = ""):
        self.h = round(30 * scale)
        self.pad = round(11 * scale)
        self.width = round(length)
        super().__init__(parent, width=self.width + round(52 * scale), height=self.h,
                         bg=bg, highlightthickness=0, bd=0)
        self.var = variable
        self.from_, self.to = from_, to
        self.command = command
        self.suffix = suffix
        self.scale_factor = scale
        self.f = Fonts.get(scale)

        y = self.h / 2
        self.track = self.create_line(self.pad, y, self.width - self.pad, y,
                                      fill=th.BG, width=round(5 * scale), capstyle="round")
        self.fill = self.create_line(self.pad, y, self.pad, y,
                                     fill=th.GOLD, width=round(5 * scale), capstyle="round")
        r = round(7 * scale)
        self.knob = self.create_oval(0, y - r, 2 * r, y + r, fill=th.GOLD,
                                     outline=th.BG_ALT, width=round(2 * scale))
        self.text = self.create_text(self.width + round(8 * scale), y, anchor="w",
                                     fill=th.TEXT, font=self.f["small"], text="")
        for seq in ("<Button-1>", "<B1-Motion>"):
            self.bind(seq, self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.config(cursor="hand2")
        try:
            self.var.trace_add("write", lambda *_a: self.redraw())
        except AttributeError:
            pass
        self.redraw()

    def _ratio(self) -> float:
        try:
            value = float(self.var.get())
        except (tk.TclError, ValueError):
            value = self.from_
        span = max(1, self.to - self.from_)
        return max(0.0, min(1.0, (value - self.from_) / span))

    def redraw(self) -> None:
        ratio = self._ratio()
        x = self.pad + (self.width - 2 * self.pad) * ratio
        y = self.h / 2
        r = round(7 * self.scale_factor)
        self.coords(self.fill, self.pad, y, max(self.pad, x), y)
        self.coords(self.knob, x - r, y - r, x + r, y + r)
        self.itemconfig(self.text, text=f"{int(float(self.var.get()))}{self.suffix}")

    def _value_at(self, x: float) -> int:
        span = self.width - 2 * self.pad
        ratio = max(0.0, min(1.0, (x - self.pad) / max(1, span)))
        return round(self.from_ + ratio * (self.to - self.from_))

    def _on_drag(self, event) -> None:
        self.var.set(self._value_at(event.x))
        self.redraw()

    def _on_release(self, event) -> None:
        self._on_drag(event)
        if self.command:
            self.command(str(self.var.get()))


def slider(parent: tk.Misc, variable: tk.Variable, from_: int, to: int,
           command: Callable[[str], None] | None = None, bg: str = th.BG_ALT,
           length: int = 220, scale: float = 1.0, suffix: str = "") -> Slider:
    return Slider(parent, variable, from_, to, command, bg, length, scale, suffix)


class SlimScrollbar(tk.Canvas):
    """Barre de defilement fine, aux couleurs de l'application."""

    def __init__(self, parent: tk.Misc, command, width: int = 10, bg: str = th.BG):
        super().__init__(parent, width=width, bg=bg, highlightthickness=0, bd=0)
        self.command = command
        self.w = width
        self.first, self.last = 0.0, 1.0
        self._drag_origin: tuple[float, float] | None = None
        self.thumb = self.create_rectangle(0, 0, 0, 0, fill=th.LINE, outline="")
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Enter>", lambda _e: self.itemconfig(self.thumb, fill=th.GOLD_DIM))
        self.bind("<Leave>", lambda _e: self.itemconfig(self.thumb, fill=th.LINE))

    def set(self, first, last) -> None:
        self.first, self.last = float(first), float(last)
        self._redraw()

    def _redraw(self) -> None:
        h = self.winfo_height()
        if h <= 1:
            return
        if self.last - self.first >= 0.999:
            self.itemconfig(self.thumb, state="hidden")
            return
        self.itemconfig(self.thumb, state="normal")
        pad = 2
        y1, y2 = self.first * h, self.last * h
        self.coords(self.thumb, pad, y1 + pad, self.w - pad, max(y1 + 24, y2) - pad)

    def _press(self, event) -> None:
        h = max(1, self.winfo_height())
        self._drag_origin = (event.y, self.first)
        span = self.last - self.first
        if not (self.first * h <= event.y <= self.last * h):
            self.command("moveto", max(0.0, min(1.0, event.y / h - span / 2)))

    def _drag(self, event) -> None:
        if not self._drag_origin:
            return
        h = max(1, self.winfo_height())
        start_y, start_first = self._drag_origin
        self.command("moveto", max(0.0, min(1.0, start_first + (event.y - start_y) / h)))


def option_menu(parent: tk.Misc, variable: tk.StringVar, values: list[str],
                command: Callable[[str], None] | None = None,
                fonts: dict | None = None) -> tk.OptionMenu:
    f = (fonts or Fonts.get())["body"]
    menu = tk.OptionMenu(parent, variable, *values, command=command)
    menu.config(font=f, bg=th.BG_SOFT, fg=th.TEXT, activebackground=th.LINE,
                activeforeground=th.TEXT, relief="flat", bd=0, highlightthickness=0,
                cursor="hand2", anchor="w", padx=10, pady=4)
    menu["menu"].config(bg=th.BG_SOFT, fg=th.TEXT, font=f, relief="flat",
                        activebackground=th.LINE, activeforeground=th.TEXT, bd=0)
    return menu


def choice_menu(parent: tk.Misc, value_var: tk.StringVar, options: dict[str, str],
                command: Callable[[str], None] | None = None,
                fonts: dict | None = None) -> tk.OptionMenu:
    """Menu deroulant dont l'affichage est accentue mais la valeur stockee neutre.

    `options` associe la valeur enregistree dans la configuration au libelle
    montre a l'utilisateur.
    """
    f = (fonts or Fonts.get())["body"]
    labels = list(options.values())
    display = tk.StringVar(value=options.get(value_var.get(), labels[0]))
    menu = tk.OptionMenu(parent, display, *labels)
    menu.config(font=f, bg=th.BG_SOFT, fg=th.TEXT, activebackground=th.LINE,
                activeforeground=th.TEXT, relief="flat", bd=0, highlightthickness=0,
                cursor="hand2", anchor="w", padx=10, pady=4)
    inner = menu["menu"]
    inner.config(bg=th.BG_SOFT, fg=th.TEXT, font=f, relief="flat",
                 activebackground=th.LINE, activeforeground=th.TEXT, bd=0)
    inner.delete(0, "end")
    for value, text in options.items():
        inner.add_command(
            label=text,
            command=lambda v=value, t=text: (value_var.set(v), display.set(t),
                                             command(v) if command else None),
        )
    menu.display_var = display  # type: ignore[attr-defined]
    return menu


def listbox(parent: tk.Misc, fonts: dict | None = None, height: int = 8, **kwargs) -> tk.Listbox:
    f = (fonts or Fonts.get())["body"]
    return tk.Listbox(
        parent, font=f, bg=th.BG_SOFT, fg=th.TEXT, selectbackground=th.GOLD,
        selectforeground=th.BG, relief="flat", bd=0, highlightthickness=1,
        highlightbackground=th.LINE, activestyle="none", height=height, **kwargs
    )


def separator(parent: tk.Misc, bg: str = th.BG_ALT) -> tk.Frame:
    return tk.Frame(parent, bg=th.LINE, height=1, bd=0, highlightthickness=0)


def section(parent: tk.Misc, title: str, subtitle: str = "", fonts: dict | None = None,
            bg: str = th.BG) -> tk.Frame:
    """Bloc titre + sous-titre + cadre de contenu pretes a remplir."""
    f = fonts or Fonts.get()
    holder = tk.Frame(parent, bg=bg)
    label(holder, title, "h2", th.TEXT, bg, f).pack(anchor="w")
    if subtitle:
        label(holder, subtitle, "small", th.MUTED, bg, f).pack(anchor="w", pady=(2, 0))
    body = card(holder)
    body.pack(fill="x", pady=(10, 0))
    holder.body = body  # type: ignore[attr-defined]
    return holder


class ScrollFrame(tk.Frame):
    """Zone defilante : les onglets de reglages depassent souvent la fenetre."""

    def __init__(self, parent: tk.Misc, bg: str = th.BG, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.scroll = SlimScrollbar(self, command=self.canvas.yview, bg=bg)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>",
                        lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self._window, width=e.width))
        self.bind_all("<MouseWheel>", self._on_wheel, add="+")

    def _on_wheel(self, event) -> None:
        # Ne defile que si la souris survole cette zone.
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                self.canvas.yview_scroll(-1 * (event.delta // 120), "units")
                return
            widget = getattr(widget, "master", None)
