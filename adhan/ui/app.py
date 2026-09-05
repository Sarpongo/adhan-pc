"""Fenetre principale d'Adhan PC."""

from __future__ import annotations

import datetime as dt
import logging
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog
from typing import Any

from PIL import Image, ImageTk

from .. import mawaqit, screens, startup, times as tmod
from ..audio import Player
from ..config import (ADHAN_KEYS, Config, PRAYER_KEYS, PRAYER_LABELS,
                      PRAYER_LABELS_AR)
from ..paths import AUDIO_DIR, DATA_DIR, ICON_ICO, ICON_PNG, resolve_audio
from ..scheduler import Event, Scheduler
from . import theme as th
from . import widgets as w
from .notifier import Notifier
from .overlay import Overlay, format_delay

log = logging.getLogger(__name__)

PAGES = [
    ("today", "Aujourd'hui"),
    ("mosque", "Mosquée"),
    ("reminders", "Rappels"),
    ("notifications", "Notifications"),
    ("audio", "Audio"),
    ("general", "Général"),
]

POSITIONS = {
    "bas-droite": "En bas à droite",
    "bas-gauche": "En bas à gauche",
    "haut-droite": "En haut à droite",
    "haut-gauche": "En haut à gauche",
    "centre": "Au centre",
}
STYLES = {"banniere": "Bannière", "plein-ecran": "Plein écran"}


class AdhanApp(tk.Tk):
    """Assemble l'interface, le planificateur et les notifications."""

    def __init__(self, start_minimized: bool = False) -> None:
        super().__init__()
        self.config_data = Config.load()
        self.player = Player()
        self.mosque: dict[str, Any] | None = None
        self.results: list[dict[str, Any]] = []
        self.overlay: Overlay | None = None
        self.tray = None
        self._queue: queue.Queue = queue.Queue()
        self._quitting = False
        self._last_refresh: dt.datetime | None = None

        self.S = screens.ui_scale(screens.screen_at(0))
        self.f = w.Fonts.get(self.S)

        self._setup_window()
        self.notifier = Notifier(self, self.config_data, self.player)
        self.scheduler = Scheduler(self.config_data, self._on_event)
        self.notifier.scheduler = self.scheduler

        self._build()
        self._apply_overlay_setting()
        startup.sync(self.config_data.data["general"].get("start_with_windows", False))

        if self.config_data.is_configured():
            self.load_mosque(refresh=True)
        else:
            self.show_page("mosque")
            self.set_status("Choisissez une mosquée pour démarrer.")

        if start_minimized:
            self.after(200, self.hide_window)
        self._tick()
        self.after(150, self._drain)

    # --------------------------------------------------------------- fenetre
    def _setup_window(self) -> None:
        self.title("Adhan PC")
        self.configure(bg=th.BG)
        width, height = round(900 * self.S), round(640 * self.S)
        scr = screens.screen_at(0)
        x = scr.x + (scr.width - width) // 2
        y = scr.y + (scr.height - height) // 3
        self.geometry(f"{width}x{height}+{max(scr.x, x)}+{max(scr.y, y)}")
        self.minsize(round(760 * self.S), round(560 * self.S))
        try:
            if ICON_ICO.exists():
                self.iconbitmap(default=str(ICON_ICO))
        except tk.TclError:
            log.debug("icone de fenetre non appliquee")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ----------------------------------------------------------- construction
    def _build(self) -> None:
        self._build_header()
        body = tk.Frame(self, bg=th.BG)
        body.pack(fill="both", expand=True)
        self._build_sidebar(body)

        self.content = tk.Frame(body, bg=th.BG)
        self.content.pack(side="left", fill="both", expand=True, padx=round(18 * self.S),
                          pady=round(14 * self.S))
        self.pages: dict[str, tk.Frame] = {}
        for key, _ in PAGES:
            page = getattr(self, f"_page_{key}")()
            self.pages[key] = page
        self._build_footer()
        self.show_page("today")

    def _build_header(self) -> None:
        head = tk.Frame(self, bg=th.BG_ALT, height=round(64 * self.S))
        head.pack(fill="x")
        head.pack_propagate(False)

        try:
            img = Image.open(ICON_PNG).resize((round(34 * self.S),) * 2, Image.LANCZOS)
            self._logo = ImageTk.PhotoImage(img)
            tk.Label(head, image=self._logo, bg=th.BG_ALT).pack(
                side="left", padx=(round(16 * self.S), round(10 * self.S)))
        except (OSError, ValueError):
            pass

        title_box = tk.Frame(head, bg=th.BG_ALT)
        title_box.pack(side="left", pady=round(10 * self.S))
        w.label(title_box, "Adhan PC", "h2", th.TEXT, th.BG_ALT, self.f).pack(anchor="w")
        self.lbl_mosque = w.label(title_box, "Aucune mosquée sélectionnée", "small",
                                  th.MUTED, th.BG_ALT, self.f)
        self.lbl_mosque.pack(anchor="w")

        right = tk.Frame(head, bg=th.BG_ALT)
        right.pack(side="right", padx=round(16 * self.S))
        self.lbl_hijri = w.label(right, "", "small", th.GOLD, th.BG_ALT, self.f)
        self.lbl_hijri.pack(anchor="e")
        self.lbl_clock = w.label(right, "", "clock_sm", th.TEXT, th.BG_ALT, self.f)
        self.lbl_clock.pack(anchor="e")

    def _build_sidebar(self, parent: tk.Misc) -> None:
        bar = tk.Frame(parent, bg=th.BG_ALT, width=round(158 * self.S))
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)
        self.nav_buttons: dict[str, tk.Label] = {}
        for key, text in PAGES:
            item = tk.Label(bar, text="   " + text, font=self.f["body"], bg=th.BG_ALT,
                            fg=th.MUTED, anchor="w", padx=round(12 * self.S),
                            pady=round(10 * self.S), cursor="hand2")
            item.pack(fill="x", padx=round(8 * self.S), pady=1)
            item.bind("<Button-1>", lambda _e, k=key: self.show_page(k))
            item.bind("<Enter>", lambda _e, i=item: i.config(bg=th.BG_SOFT)
                      if i.cget("fg") != th.BG else None)
            item.bind("<Leave>", lambda _e, i=item: i.config(bg=th.BG_ALT)
                      if i.cget("fg") != th.BG else None)
            self.nav_buttons[key] = item

    def _build_footer(self) -> None:
        foot = tk.Frame(self, bg=th.BG_ALT, height=round(44 * self.S))
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        self.lbl_status = w.label(foot, "", "small", th.MUTED, th.BG_ALT, self.f)
        self.lbl_status.pack(side="left", padx=round(16 * self.S))
        w.button(foot, "Quitter", self.quit_app, fonts=self.f).pack(
            side="right", padx=(4, round(12 * self.S)), pady=round(7 * self.S))
        w.button(foot, "Réduire dans la barre", self.hide_window, fonts=self.f).pack(
            side="right", padx=4, pady=round(7 * self.S))
        w.button(foot, "Arrêter l'adhan", self.notifier.stop_audio, danger=True,
                 fonts=self.f).pack(side="right", padx=4, pady=round(7 * self.S))

    def show_page(self, key: str) -> None:
        for name, page in self.pages.items():
            page.pack_forget()
            item = self.nav_buttons[name]
            item.config(bg=th.BG_ALT, fg=th.MUTED)
        self.pages[key].pack(fill="both", expand=True)
        self.nav_buttons[key].config(bg=th.GOLD, fg=th.BG)

    # ------------------------------------------------------------ page : jour
    def _page_today(self) -> tk.Frame:
        page = tk.Frame(self.content, bg=th.BG)
        S = self.S

        hero = w.card(page)
        hero.pack(fill="x")
        inner = tk.Frame(hero, bg=th.BG_ALT)
        inner.pack(fill="x", padx=round(20 * S), pady=round(16 * S))

        left = tk.Frame(inner, bg=th.BG_ALT)
        left.pack(side="left", anchor="n")
        w.label(left, "PROCHAINE PRIÈRE", "tiny", th.MUTED, th.BG_ALT, self.f).pack(anchor="w")
        self.lbl_next_name = w.label(left, "—", "h1", th.TEXT, th.BG_ALT, self.f)
        self.lbl_next_name.pack(anchor="w")
        self.lbl_next_sub = w.label(left, "", "small", th.MUTED, th.BG_ALT, self.f)
        self.lbl_next_sub.pack(anchor="w")

        right = tk.Frame(inner, bg=th.BG_ALT)
        right.pack(side="right", anchor="n")
        self.lbl_next_time = w.label(right, "--:--", "clock", th.GOLD, th.BG_ALT, self.f)
        self.lbl_next_time.pack(anchor="e")
        self.lbl_countdown = w.label(right, "", "h3", th.TEXT, th.BG_ALT, self.f)
        self.lbl_countdown.pack(anchor="e")

        self.progress = tk.Canvas(hero, height=round(6 * S), bg=th.BG_ALT,
                                  highlightthickness=0, bd=0)
        self.progress.pack(fill="x", padx=round(20 * S), pady=(0, round(16 * S)))

        table = w.card(page)
        table.pack(fill="both", expand=True, pady=(round(14 * S), 0))
        self.rows: dict[str, dict[str, tk.Label]] = {}
        for i, key in enumerate(PRAYER_KEYS):
            row = tk.Frame(table, bg=th.BG_ALT)
            row.pack(fill="x", padx=round(18 * S), pady=round(7 * S))
            name = w.label(row, PRAYER_LABELS[key], "h3", th.TEXT, th.BG_ALT, self.f)
            name.pack(side="left")
            w.label(row, PRAYER_LABELS_AR[key], "arabic", th.GOLD_DIM, th.BG_ALT,
                    self.f).pack(side="left", padx=round(12 * S))
            time_lbl = w.label(row, "--:--", "clock_sm", th.TEXT, th.BG_ALT, self.f)
            time_lbl.pack(side="right")
            badge = w.label(row, "", "tiny", th.MUTED, th.BG_ALT, self.f)
            badge.pack(side="right", padx=round(14 * S))
            self.rows[key] = {"name": name, "time": time_lbl, "badge": badge, "row": row}
            if i < len(PRAYER_KEYS) - 1:
                w.separator(table).pack(fill="x", padx=round(18 * S))

        self.lbl_jumua = w.label(page, "", "small", th.GOLD, th.BG, self.f)
        self.lbl_jumua.pack(anchor="w", pady=(round(10 * S), 0))
        return page

    # --------------------------------------------------------- page : mosquee
    def _page_mosque(self) -> tk.Frame:
        page = w.ScrollFrame(self.content)
        root = page.inner
        S = self.S

        current = w.section(root, "Mosquée suivie",
                            "Les horaires proviennent de Mawaqit, calendrier annuel inclus.",
                            self.f)
        current.pack(fill="x")
        box = tk.Frame(current.body, bg=th.BG_ALT)
        box.pack(fill="x", padx=round(16 * S), pady=round(14 * S))
        self.lbl_current_mosque = w.label(box, "Aucune mosquée", "h3", th.TEXT, th.BG_ALT, self.f)
        self.lbl_current_mosque.pack(anchor="w")
        self.lbl_current_city = w.label(box, "", "small", th.MUTED, th.BG_ALT, self.f)
        self.lbl_current_city.pack(anchor="w", pady=(2, round(10 * S)))
        actions = tk.Frame(box, bg=th.BG_ALT)
        actions.pack(anchor="w")
        w.button(actions, "Actualiser les horaires", lambda: self.load_mosque(refresh=True),
                 fonts=self.f).pack(side="left")
        w.button(actions, "Ouvrir sur Mawaqit", self._open_mawaqit,
                 fonts=self.f).pack(side="left", padx=6)

        search = w.section(root, "Chercher une mosquée",
                           "Par ville, quartier ou nom — ou automatiquement autour de vous.",
                           self.f)
        search.pack(fill="x", pady=(round(18 * S), 0))
        bar = tk.Frame(search.body, bg=th.BG_ALT)
        bar.pack(fill="x", padx=round(16 * S), pady=round(14 * S))
        self.var_search = tk.StringVar()
        e = w.entry(bar, self.var_search, self.f, width=30)
        e.pack(side="left", ipady=round(6 * S))
        e.bind("<Return>", lambda _ev: self.search_mosques())
        w.button(bar, "Rechercher", self.search_mosques, primary=True,
                 fonts=self.f).pack(side="left", padx=6)
        w.button(bar, "Autour de moi", self.search_nearby,
                 fonts=self.f).pack(side="left")

        self.lst_results = w.listbox(search.body, self.f, height=9)
        self.lst_results.pack(fill="x", padx=round(16 * S), pady=(0, round(10 * S)))
        self.lst_results.bind("<Double-Button-1>", lambda _e: self.choose_mosque())
        w.button(search.body, "Choisir cette mosquée", self.choose_mosque, primary=True,
                 fonts=self.f).pack(anchor="w", padx=round(16 * S), pady=(0, round(14 * S)))
        return page

    # --------------------------------------------------------- page : rappels
    def _page_reminders(self) -> tk.Frame:
        page = w.ScrollFrame(self.content)
        root = page.inner
        S = self.S

        glob = w.section(root, "Rappels par défaut",
                         "Minutes avant chaque prière. Ajoutez-en ou retirez-en librement.",
                         self.f)
        glob.pack(fill="x")
        holder = tk.Frame(glob.body, bg=th.BG_ALT)
        holder.pack(fill="x", padx=round(16 * S), pady=round(14 * S))
        self.chips = tk.Frame(holder, bg=th.BG_ALT)
        self.chips.pack(fill="x", pady=(0, round(10 * S)))
        add = tk.Frame(holder, bg=th.BG_ALT)
        add.pack(anchor="w")
        self.var_new_reminder = tk.StringVar()
        ent = w.entry(add, self.var_new_reminder, self.f, width=6)
        ent.pack(side="left", ipady=round(5 * S))
        ent.bind("<Return>", lambda _e: self._add_reminder())
        w.label(add, "minutes", "small", th.MUTED, th.BG_ALT, self.f).pack(side="left", padx=6)
        w.button(add, "Ajouter", self._add_reminder, primary=True, fonts=self.f).pack(side="left")
        w.button(add, "Rétablir 30/15/10/5", lambda: self._set_reminders([30, 15, 10, 5]),
                 fonts=self.f).pack(side="left", padx=6)

        per = w.section(root, "Réglage par prière",
                        "Rappels propres à une prière : laissez vide pour utiliser la liste "
                        "par défaut.", self.f)
        per.pack(fill="x", pady=(round(18 * S), 0))
        grid = tk.Frame(per.body, bg=th.BG_ALT)
        grid.pack(fill="x", padx=round(16 * S), pady=round(12 * S))
        headers = ["Prière", "Activée", "Adhan", "Rappels personnalisés (minutes)"]
        for col, text in enumerate(headers):
            w.label(grid, text, "tiny", th.MUTED, th.BG_ALT, self.f).grid(
                row=0, column=col, sticky="w", padx=round(6 * S), pady=(0, round(6 * S)))
        self.prayer_vars: dict[str, dict[str, tk.Variable]] = {}
        for r, key in enumerate(PRAYER_KEYS, start=1):
            entry_cfg = self.config_data.prayer(key)
            v_en = tk.BooleanVar(value=entry_cfg.get("enabled", True))
            v_ad = tk.BooleanVar(value=entry_cfg.get("adhan", False))
            custom = entry_cfg.get("reminders")
            v_rem = tk.StringVar(value=", ".join(str(m) for m in custom) if custom else "")
            self.prayer_vars[key] = {"enabled": v_en, "adhan": v_ad, "reminders": v_rem}

            w.label(grid, PRAYER_LABELS[key], "body", th.TEXT, th.BG_ALT, self.f).grid(
                row=r, column=0, sticky="w", padx=round(6 * S), pady=round(3 * S))
            w.checkbox(grid, "", v_en, lambda k=key: self._save_prayer(k), fonts=self.f).grid(
                row=r, column=1, sticky="w")
            cb = w.checkbox(grid, "", v_ad, lambda k=key: self._save_prayer(k), fonts=self.f)
            cb.grid(row=r, column=2, sticky="w")
            if key not in ADHAN_KEYS:
                cb.config(state="disabled")
            ent = w.entry(grid, v_rem, self.f, width=26)
            ent.grid(row=r, column=3, sticky="w", padx=round(6 * S), ipady=round(3 * S))
            ent.bind("<FocusOut>", lambda _e, k=key: self._save_prayer(k))
            ent.bind("<Return>", lambda _e, k=key: self._save_prayer(k))
        self._refresh_chips()
        return page

    # --------------------------------------------------- page : notifications
    def _page_notifications(self) -> tk.Frame:
        page = w.ScrollFrame(self.content)
        root = page.inner
        S = self.S
        n = self.config_data.data["notifications"]

        look = w.section(root, "Apparence des notifications",
                         "Elles s'affichent sans jamais prendre le focus de "
                         "l'application en cours.", self.f)
        look.pack(fill="x")
        g = tk.Frame(look.body, bg=th.BG_ALT)
        g.pack(fill="x", padx=round(16 * S), pady=round(12 * S))

        self.var_adhan_style = tk.StringVar(value=n.get("adhan_style", "banniere"))
        self.var_rem_style = tk.StringVar(value=n.get("reminder_style", "banniere"))
        self.var_position = tk.StringVar(value=n.get("position", "bas-droite"))
        self.var_accent = tk.StringVar(value=n.get("accent", "Or"))
        self.var_notif_screen = tk.StringVar()
        self.var_ornaments = tk.BooleanVar(value=n.get("ornaments", True))
        self.var_toast = tk.BooleanVar(value=n.get("native_toast", True))
        self.var_popup = tk.BooleanVar(value=n.get("popup", True))
        self.var_avoid_fs = tk.BooleanVar(value=n.get("avoid_fullscreen_apps", True))
        self.var_popup_secs = tk.IntVar(value=n.get("popup_seconds", 25))
        self.var_adhan_secs = tk.IntVar(value=n.get("adhan_seconds", 90))

        def row(r, text, widget):
            w.label(g, text, "body", th.TEXT, th.BG_ALT, self.f).grid(
                row=r, column=0, sticky="w", pady=round(5 * S), padx=(0, round(14 * S)))
            widget.grid(row=r, column=1, sticky="w", pady=round(5 * S))

        row(0, "Style de l'adhan", w.choice_menu(g, self.var_adhan_style, STYLES,
                                                 lambda _v: self._save_notifications(), self.f))
        row(1, "Style des rappels", w.choice_menu(g, self.var_rem_style, STYLES,
                                                  lambda _v: self._save_notifications(), self.f))
        row(2, "Coin d'apparition", w.choice_menu(g, self.var_position, POSITIONS,
                                                  lambda _v: self._save_notifications(), self.f))
        self.opt_notif_screen = w.option_menu(g, self.var_notif_screen, ["Écran 1"],
                                              lambda _v: self._save_notifications(), self.f)
        row(3, "Écran d'affichage", self.opt_notif_screen)
        row(4, "Couleur d'accent", w.option_menu(g, self.var_accent, list(th.ACCENTS),
                                                 lambda _v: self._save_notifications(), self.f))
        row(5, "Durée d'un rappel", w.slider(g, self.var_popup_secs, 5, 120,
                                            lambda _v: self._save_notifications(),
                                            length=round(200 * S), scale=S, suffix=" s"))
        row(6, "Durée de l'adhan", w.slider(g, self.var_adhan_secs, 10, 300,
                                           lambda _v: self._save_notifications(),
                                           length=round(200 * S), scale=S, suffix=" s"))

        opts = tk.Frame(look.body, bg=th.BG_ALT)
        opts.pack(fill="x", padx=round(16 * S), pady=(0, round(12 * S)))
        for text, var in [
            ("Afficher la notification ornementée", self.var_popup),
            ("Ornements arabesques", self.var_ornaments),
            ("Notification Windows (centre de notifications)", self.var_toast),
            ("Ne pas recouvrir un jeu ou une vidéo en plein écran", self.var_avoid_fs),
        ]:
            w.checkbox(opts, text, var, self._save_notifications, fonts=self.f).pack(anchor="w")

        preview = tk.Frame(look.body, bg=th.BG_ALT)
        preview.pack(anchor="w", padx=round(16 * S), pady=(0, round(14 * S)))
        w.button(preview, "Aperçu d'un rappel",
                 lambda: self.notifier.preview("reminder"), primary=True,
                 fonts=self.f).pack(side="left")
        w.button(preview, "Aperçu de l'adhan",
                 lambda: self.notifier.preview("adhan"), fonts=self.f).pack(side="left", padx=6)

        # ------------------------------------------------------ suivi post-adhan
        post = self.config_data.data["post_check"]
        checksec = w.section(root, "Suivi post-adhan",
                             "Après l'adhan, une alerte demande si vous avez prié — "
                             "en boucle jusqu'à ce que vous répondiez « J'ai prié ». "
                             "S'applique aux prières pour lesquelles l'adhan est activé.",
                             self.f)
        checksec.pack(fill="x", pady=(round(18 * S), 0))
        c3 = tk.Frame(checksec.body, bg=th.BG_ALT)
        c3.pack(fill="x", padx=round(16 * S), pady=round(14 * S))

        self.var_check_enabled = tk.BooleanVar(value=post.get("enabled", True))
        w.checkbox(c3, "Activer le suivi post-adhan", self.var_check_enabled,
                   self._save_post_check, fonts=self.f).pack(anchor="w", pady=(0, round(10 * S)))

        self.post_chips = tk.Frame(c3, bg=th.BG_ALT)
        self.post_chips.pack(fill="x", pady=(0, round(10 * S)))
        add3 = tk.Frame(c3, bg=th.BG_ALT)
        add3.pack(anchor="w")
        self.var_new_post_delay = tk.StringVar()
        ent3 = w.entry(add3, self.var_new_post_delay, self.f, width=6)
        ent3.pack(side="left", ipady=round(5 * S))
        ent3.bind("<Return>", lambda _e: self._add_post_delay())
        w.label(add3, "minutes après l'adhan", "small", th.MUTED, th.BG_ALT, self.f).pack(
            side="left", padx=6)
        w.button(add3, "Ajouter", self._add_post_delay, primary=True, fonts=self.f).pack(side="left")
        w.button(add3, "Rétablir 5/10/20", lambda: self._set_post_delays([5, 10, 20]),
                 fonts=self.f).pack(side="left", padx=6)

        preview3 = tk.Frame(checksec.body, bg=th.BG_ALT)
        preview3.pack(anchor="w", padx=round(16 * S), pady=(0, round(14 * S)))
        w.button(preview3, "Aperçu de l'alerte", lambda: self.notifier.preview("check"),
                 fonts=self.f).pack(side="left")
        self._refresh_post_chips()

        # ------------------------------------------------------------ widget
        ov = self.config_data.data["overlay"]
        section = w.section(root, "Rappel permanent à l'écran",
                            "Petite carte toujours visible, très peu opaque. "
                            "Glissez-la où vous voulez, y compris sur un autre écran.", self.f)
        section.pack(fill="x", pady=(round(18 * S), 0))
        g2 = tk.Frame(section.body, bg=th.BG_ALT)
        g2.pack(fill="x", padx=round(16 * S), pady=round(12 * S))

        self.var_ov_enabled = tk.BooleanVar(value=ov.get("enabled", True))
        self.var_ov_opacity = tk.IntVar(value=ov.get("opacity", 18))
        self.var_ov_screen = tk.StringVar()
        self.var_ov_position = tk.StringVar(value=ov.get("position", "haut-droite"))
        self.var_ov_size = tk.StringVar(value=ov.get("size", "normal"))
        self.var_ov_click = tk.BooleanVar(value=ov.get("click_through", False))

        def row2(r, text, widget):
            w.label(g2, text, "body", th.TEXT, th.BG_ALT, self.f).grid(
                row=r, column=0, sticky="w", pady=round(5 * S), padx=(0, round(14 * S)))
            widget.grid(row=r, column=1, sticky="w", pady=round(5 * S))

        row2(0, "Opacité", w.slider(g2, self.var_ov_opacity, 5, 100,
                                   lambda _v: self._save_overlay(),
                                   length=round(200 * S), scale=S, suffix=" %"))
        self.opt_ov_screen = w.option_menu(g2, self.var_ov_screen, ["Écran 1"],
                                           lambda _v: self._save_overlay(), self.f)
        row2(1, "Écran", self.opt_ov_screen)
        row2(2, "Coin", w.choice_menu(g2, self.var_ov_position,
                                      POSITIONS | {"libre": "Libre (glissée à la souris)"},
                                      lambda _v: self._save_overlay(), self.f))
        row2(3, "Taille", w.choice_menu(g2, self.var_ov_size,
                                        {"normal": "Normale", "compact": "Compacte"},
                                        lambda _v: self._save_overlay(), self.f))

        opts2 = tk.Frame(section.body, bg=th.BG_ALT)
        opts2.pack(fill="x", padx=round(16 * S), pady=(0, round(14 * S)))
        w.checkbox(opts2, "Afficher le rappel permanent", self.var_ov_enabled,
                   self._save_overlay, fonts=self.f).pack(anchor="w")
        w.checkbox(opts2, "Laisser passer les clics (carte non sélectionnable)",
                   self.var_ov_click, self._save_overlay, fonts=self.f).pack(anchor="w")
        return page

    # ----------------------------------------------------------- page : audio
    def _page_audio(self) -> tk.Frame:
        page = w.ScrollFrame(self.content)
        root = page.inner
        S = self.S
        a = self.config_data.data["audio"]

        section = w.section(root, "Adhan",
                            "Volume appliqué au déclenchement automatique comme au test.",
                            self.f)
        section.pack(fill="x")
        box = tk.Frame(section.body, bg=th.BG_ALT)
        box.pack(fill="x", padx=round(16 * S), pady=round(12 * S))

        self.var_volume = tk.IntVar(value=a.get("volume", 70))
        self.var_audio_file = tk.StringVar(value=a.get("file") or "")
        self.var_reminder_sound = tk.BooleanVar(value=a.get("reminder_sound", True))

        w.label(box, "Volume de l'adhan", "body", th.TEXT, th.BG_ALT, self.f).grid(
            row=0, column=0, sticky="w", padx=(0, round(14 * S)))
        w.slider(box, self.var_volume, 0, 100, self._on_volume,
                 length=round(240 * S), scale=S, suffix=" %").grid(
            row=0, column=1, sticky="w")

        w.label(box, "Adhan par défaut", "body", th.TEXT, th.BG_ALT, self.f).grid(
            row=1, column=0, sticky="w", pady=round(6 * S), padx=(0, round(14 * S)))
        self.opt_audio = w.option_menu(box, self.var_audio_file, self._audio_choices(),
                                       lambda _v: self._save_audio(), self.f)
        self.opt_audio.grid(row=1, column=1, sticky="w", pady=round(6 * S))

        buttons = tk.Frame(section.body, bg=th.BG_ALT)
        buttons.pack(anchor="w", padx=round(16 * S), pady=(0, round(14 * S)))
        w.button(buttons, "Écouter", self._test_audio, primary=True, fonts=self.f).pack(side="left")
        w.button(buttons, "Arrêter", self.notifier.stop_audio,
                 fonts=self.f).pack(side="left", padx=6)
        w.button(buttons, "Ajouter un fichier...", self._browse_audio,
                 fonts=self.f).pack(side="left")
        w.checkbox(section.body, "Signal sonore discret sur les rappels",
                   self.var_reminder_sound, self._save_audio, fonts=self.f).pack(
            anchor="w", padx=round(16 * S), pady=(0, round(12 * S)))

        per = w.section(root, "Adhan par prière",
                        "Laissez « (par défaut) » pour utiliser l'adhan ci-dessus.", self.f)
        per.pack(fill="x", pady=(round(18 * S), 0))
        grid = tk.Frame(per.body, bg=th.BG_ALT)
        grid.pack(fill="x", padx=round(16 * S), pady=round(12 * S))
        self.audio_vars: dict[str, tk.StringVar] = {}
        for r, key in enumerate(ADHAN_KEYS):
            var = tk.StringVar(value=self.config_data.prayer(key).get("audio") or "(par défaut)")
            self.audio_vars[key] = var
            w.label(grid, PRAYER_LABELS[key], "body", th.TEXT, th.BG_ALT, self.f).grid(
                row=r, column=0, sticky="w", pady=round(4 * S), padx=(0, round(14 * S)))
            w.option_menu(grid, var, ["(par défaut)"] + self._audio_choices(),
                          lambda _v, k=key: self._save_prayer_audio(k), self.f).grid(
                row=r, column=1, sticky="w", pady=round(4 * S))
        return page

    # --------------------------------------------------------- page : general
    def _page_general(self) -> tk.Frame:
        page = w.ScrollFrame(self.content)
        root = page.inner
        S = self.S
        g = self.config_data.data["general"]

        section = w.section(root, "Démarrage", "", self.f)
        section.pack(fill="x")
        box = tk.Frame(section.body, bg=th.BG_ALT)
        box.pack(fill="x", padx=round(16 * S), pady=round(12 * S))
        self.var_startup = tk.BooleanVar(value=startup.is_enabled())
        self.var_start_min = tk.BooleanVar(value=g.get("start_minimized", True))
        self.var_close_tray = tk.BooleanVar(value=g.get("close_to_tray", True))
        w.checkbox(box, "Lancer Adhan PC au démarrage de Windows", self.var_startup,
                   self._save_general, fonts=self.f).pack(anchor="w")
        w.checkbox(box, "Démarrer directement dans la barre des tâches", self.var_start_min,
                   self._save_general, fonts=self.f).pack(anchor="w")
        w.checkbox(box, "La croix réduit dans la barre au lieu de quitter",
                   self.var_close_tray, self._save_general, fonts=self.f).pack(anchor="w")

        info = w.section(root, "À propos", "", self.f)
        info.pack(fill="x", pady=(round(18 * S), 0))
        box2 = tk.Frame(info.body, bg=th.BG_ALT)
        box2.pack(fill="x", padx=round(16 * S), pady=round(12 * S))
        for text in (
            "Horaires fournis par Mawaqit (calendrier annuel mis en cache).",
            f"Configuration et cache : {DATA_DIR}",
            f"Sons disponibles : {AUDIO_DIR}",
        ):
            w.label(box2, text, "small", th.MUTED, th.BG_ALT, self.f).pack(anchor="w", pady=1)
        w.button(box2, "Ouvrir le dossier de configuration",
                 lambda: webbrowser.open(str(DATA_DIR)), fonts=self.f).pack(
            anchor="w", pady=(round(10 * S), 0))
        return page

    # -------------------------------------------------------------- donnees
    def load_mosque(self, refresh: bool = True) -> None:
        slug = self.config_data.mosque.get("slug")
        if not slug:
            return
        self.set_status("Récupération des horaires...")

        def work():
            try:
                payload, fresh = mawaqit.get_mosque(slug, refresh=refresh)
                self._queue.put(("mosque", payload, fresh))
            except mawaqit.MawaqitError as exc:
                self._queue.put(("error", str(exc), None))

        threading.Thread(target=work, daemon=True).start()

    def search_mosques(self) -> None:
        word = self.var_search.get().strip()
        if not word:
            self.set_status("Indiquez une ville ou un nom de mosquée.")
            return
        self.set_status(f"Recherche de « {word} »...")
        self._run_search(word=word)

    def search_nearby(self) -> None:
        self.set_status("Localisation en cours...")

        def work():
            try:
                lat, lon, city = mawaqit.locate_by_ip()
                self._queue.put(("results", mawaqit.search(lat=lat, lon=lon), city))
            except mawaqit.MawaqitError as exc:
                self._queue.put(("error", str(exc), None))

        threading.Thread(target=work, daemon=True).start()

    def _run_search(self, word: str) -> None:
        def work():
            try:
                self._queue.put(("results", mawaqit.search(word=word), ""))
            except mawaqit.MawaqitError as exc:
                self._queue.put(("error", str(exc), None))

        threading.Thread(target=work, daemon=True).start()

    def choose_mosque(self) -> None:
        selection = self.lst_results.curselection()
        if not selection:
            self.set_status("Sélectionnez une mosquée dans la liste.")
            return
        mosque = self.results[selection[0]]
        self.config_data.set_mosque(mosque)
        self.config_data.save()
        self.load_mosque(refresh=True)
        self.show_page("today")

    def _open_mawaqit(self) -> None:
        slug = self.config_data.mosque.get("slug")
        if slug:
            webbrowser.open(f"https://mawaqit.net/fr/{slug}")

    def _drain(self) -> None:
        """Recupere les resultats des threads reseau dans la boucle Tk."""
        try:
            while True:
                kind, payload, extra = self._queue.get_nowait()
                if kind == "mosque":
                    self._apply_mosque(payload, fresh=extra)
                elif kind == "results":
                    self._apply_results(payload, extra)
                elif kind == "error":
                    self.set_status(payload, error=True)
        except queue.Empty:
            pass
        self.after(200, self._drain)

    def _apply_mosque(self, payload: dict[str, Any], fresh: bool) -> None:
        self.mosque = payload
        self._last_refresh = dt.datetime.now()
        self.config_data.mosque["timezone"] = payload.get("timezone")
        self.config_data.mosque["name"] = payload.get("name")
        self.config_data.save()
        self.scheduler.set_mosque(payload)
        self.notifier.mosque_name = payload.get("name") or ""
        name = payload.get("name") or "Mosquee"
        city = payload.get("city") or self.config_data.mosque.get("city") or ""
        self.lbl_mosque.config(text=f"{name}")
        self.lbl_current_mosque.config(text=name)
        self.lbl_current_city.config(text=city)
        self.set_status("Horaires à jour." if fresh else "Hors ligne : horaires du cache local.")
        self.refresh_today()

    def _apply_results(self, results: list[dict[str, Any]], city: str) -> None:
        self.results = results
        self.lst_results.delete(0, tk.END)
        for m in results:
            place = m.get("localisation") or ""
            self.lst_results.insert(tk.END, f"{m.get('name', '?')}   —   {place}")
        if results:
            self.lst_results.selection_set(0)
        origin = f" autour de {city}" if city else ""
        self.set_status(f"{len(results)} mosquée(s) trouvée(s){origin}."
                        if results else "Aucune mosquée trouvée.")

    # ------------------------------------------------------------ affichage
    def refresh_today(self) -> None:
        if not self.mosque:
            return
        today = dt.date.today()
        schedule = self.scheduler.today_schedule()
        current = self.scheduler.current_prayer()
        for key in PRAYER_KEYS:
            when = schedule.get(key)
            row = self.rows[key]
            row["time"].config(text=f"{when:%H:%M}" if when else "--:--")
            reminders = self.config_data.reminders_for(key)
            entry_cfg = self.config_data.prayer(key)
            bits = []
            if entry_cfg.get("adhan") and key in ADHAN_KEYS:
                bits.append("adhan")
            if reminders:
                bits.append(f"{len(reminders)} rappel" + ("s" if len(reminders) > 1 else ""))
            row["badge"].config(text=" · ".join(bits) if bits else "silencieux")
            active = key == current
            row["name"].config(fg=th.GOLD if active else th.TEXT)
            row["time"].config(fg=th.GOLD if active else th.TEXT)

        self.lbl_hijri.config(text=tmod.hijri_label(today, self.mosque.get("hijri_adjustment", 0)))
        jumua = tmod.is_jumua(self.mosque, today)
        self.lbl_jumua.config(text=f"Jumu'a aujourd'hui à {jumua}." if jumua else "")

    def _tick(self) -> None:
        now = dt.datetime.now().astimezone()
        self.lbl_clock.config(text=f"{now:%H:%M:%S}")
        if self.mosque:
            self.scheduler.tick(now)
            nxt = self.scheduler.next_prayer(now)
            if nxt:
                key, when = nxt
                self.lbl_next_name.config(text=PRAYER_LABELS[key])
                self.lbl_next_time.config(text=f"{when:%H:%M}")
                self.lbl_countdown.config(text="dans " + format_delay(when - now))
                extra = " (demain)" if when.date() != now.date() else ""
                self.lbl_next_sub.config(text=PRAYER_LABELS_AR[key] + extra)
                self._draw_progress(now, when)
                if self.overlay:
                    self.overlay.update_content(PRAYER_LABELS[key], when, now,
                                                self.mosque.get("name", ""))
            if now.date() != getattr(self, "_shown_day", None):
                self._shown_day = now.date()
                self.refresh_today()
            hours = self.config_data.data["general"].get("refresh_hours", 24)
            if self._last_refresh and (now.replace(tzinfo=None) - self._last_refresh
                                       > dt.timedelta(hours=hours)):
                self.load_mosque(refresh=True)
        self.after(1000, self._tick)

    def _draw_progress(self, now: dt.datetime, target: dt.datetime) -> None:
        """Barre de progression entre la priere precedente et la suivante."""
        self.progress.delete("all")
        width = self.progress.winfo_width()
        if width < 10:
            return
        schedule = self.scheduler.today_schedule()
        past = [t for k, t in schedule.items() if k != "shuruq" and t <= now]
        start = max(past) if past else target - dt.timedelta(hours=5)
        span = max(1.0, (target - start).total_seconds())
        ratio = min(1.0, max(0.0, (now - start).total_seconds() / span))
        h = round(6 * self.S)
        self.progress.create_rectangle(0, 0, width, h, fill=th.BG, outline="")
        self.progress.create_rectangle(0, 0, width * ratio, h, fill=th.GOLD, outline="")

    def set_status(self, text: str, error: bool = False) -> None:
        self.lbl_status.config(text=text, fg=th.RED if error else th.MUTED)
        if error:
            log.warning(text)

    # ----------------------------------------------------- sauvegarde reglages
    def _refresh_chips(self) -> None:
        for child in self.chips.winfo_children():
            child.destroy()
        for minutes in self.config_data.reminders:
            chip = tk.Frame(self.chips, bg=th.BG_SOFT, highlightbackground=th.LINE,
                            highlightthickness=1)
            chip.pack(side="left", padx=(0, round(6 * self.S)))
            w.label(chip, f"{minutes} min", "small", th.TEXT, th.BG_SOFT, self.f).pack(
                side="left", padx=(round(10 * self.S), 4), pady=round(5 * self.S))
            x = tk.Label(chip, text="✕", font=self.f["tiny"], bg=th.BG_SOFT, fg=th.MUTED,
                         cursor="hand2", padx=round(8 * self.S))
            x.pack(side="left")
            x.bind("<Button-1>", lambda _e, m=minutes: self._remove_reminder(m))
            x.bind("<Enter>", lambda _e, lbl=x: lbl.config(fg=th.RED))
            x.bind("<Leave>", lambda _e, lbl=x: lbl.config(fg=th.MUTED))

    def _add_reminder(self) -> None:
        raw = self.var_new_reminder.get().strip()
        try:
            minutes = int(raw)
        except ValueError:
            self.set_status("Entrez un nombre de minutes.", error=True)
            return
        if not 0 < minutes <= 1440:
            self.set_status("Le rappel doit être compris entre 1 et 1440 minutes.", error=True)
            return
        self._set_reminders(self.config_data.reminders + [minutes])
        self.var_new_reminder.set("")

    def _remove_reminder(self, minutes: int) -> None:
        self._set_reminders([m for m in self.config_data.reminders if m != minutes])

    def _set_reminders(self, values: list[int]) -> None:
        self.config_data.data["reminders"] = values
        self._commit()
        self._refresh_chips()

    def _refresh_post_chips(self) -> None:
        for child in self.post_chips.winfo_children():
            child.destroy()
        for minutes in self.config_data.data["post_check"]["delays"]:
            chip = tk.Frame(self.post_chips, bg=th.BG_SOFT, highlightbackground=th.LINE,
                            highlightthickness=1)
            chip.pack(side="left", padx=(0, round(6 * self.S)))
            w.label(chip, f"+{minutes} min", "small", th.TEXT, th.BG_SOFT, self.f).pack(
                side="left", padx=(round(10 * self.S), 4), pady=round(5 * self.S))
            x = tk.Label(chip, text="✕", font=self.f["tiny"], bg=th.BG_SOFT, fg=th.MUTED,
                         cursor="hand2", padx=round(8 * self.S))
            x.pack(side="left")
            x.bind("<Button-1>", lambda _e, m=minutes: self._remove_post_delay(m))
            x.bind("<Enter>", lambda _e, lbl=x: lbl.config(fg=th.RED))
            x.bind("<Leave>", lambda _e, lbl=x: lbl.config(fg=th.MUTED))

    def _add_post_delay(self) -> None:
        raw = self.var_new_post_delay.get().strip()
        try:
            minutes = int(raw)
        except ValueError:
            self.set_status("Entrez un nombre de minutes.", error=True)
            return
        if not 0 < minutes <= 1440:
            self.set_status("Le délai doit être compris entre 1 et 1440 minutes.", error=True)
            return
        self._set_post_delays(self.config_data.data["post_check"]["delays"] + [minutes])
        self.var_new_post_delay.set("")

    def _remove_post_delay(self, minutes: int) -> None:
        self._set_post_delays(
            [m for m in self.config_data.data["post_check"]["delays"] if m != minutes])

    def _set_post_delays(self, values: list[int]) -> None:
        self.config_data.data["post_check"]["delays"] = values
        self._commit()
        self._refresh_post_chips()

    def _save_post_check(self, *_args) -> None:
        self.config_data.data["post_check"]["enabled"] = bool(self.var_check_enabled.get())
        self._commit()

    def _save_prayer(self, key: str) -> None:
        v = self.prayer_vars[key]
        entry_cfg = self.config_data.prayer(key)
        entry_cfg["enabled"] = bool(v["enabled"].get())
        entry_cfg["adhan"] = bool(v["adhan"].get())
        raw = str(v["reminders"].get()).replace(";", ",").replace(" ", "")
        if raw:
            parsed = []
            for part in raw.split(","):
                try:
                    parsed.append(int(part))
                except ValueError:
                    continue
            entry_cfg["reminders"] = parsed or None
        else:
            entry_cfg["reminders"] = None
        self._commit()
        custom = entry_cfg.get("reminders")
        v["reminders"].set(", ".join(str(m) for m in custom) if custom else "")

    def _save_prayer_audio(self, key: str) -> None:
        value = self.audio_vars[key].get()
        self.config_data.prayer(key)["audio"] = None if value == "(par défaut)" else value
        self._commit()

    def _save_notifications(self, *_args) -> None:
        n = self.config_data.data["notifications"]
        n["adhan_style"] = self.var_adhan_style.get()
        n["reminder_style"] = self.var_rem_style.get()
        n["position"] = self.var_position.get()
        n["accent"] = self.var_accent.get()
        n["ornaments"] = bool(self.var_ornaments.get())
        n["native_toast"] = bool(self.var_toast.get())
        n["popup"] = bool(self.var_popup.get())
        n["avoid_fullscreen_apps"] = bool(self.var_avoid_fs.get())
        n["popup_seconds"] = int(self.var_popup_secs.get())
        n["adhan_seconds"] = int(self.var_adhan_secs.get())
        n["screen"] = self._screen_index(self.var_notif_screen.get())
        self._commit()

    def _save_overlay(self, *_args) -> None:
        o = self.config_data.data["overlay"]
        o["enabled"] = bool(self.var_ov_enabled.get())
        o["opacity"] = int(self.var_ov_opacity.get())
        o["position"] = self.var_ov_position.get()
        o["size"] = self.var_ov_size.get()
        o["click_through"] = bool(self.var_ov_click.get())
        o["screen"] = self._screen_index(self.var_ov_screen.get())
        self._commit()
        self._apply_overlay_setting()

    def _save_audio(self, *_args) -> None:
        a = self.config_data.data["audio"]
        a["volume"] = int(self.var_volume.get())
        a["file"] = self.var_audio_file.get() or None
        a["reminder_sound"] = bool(self.var_reminder_sound.get())
        self._commit()

    def _save_general(self, *_args) -> None:
        g = self.config_data.data["general"]
        g["start_minimized"] = bool(self.var_start_min.get())
        g["close_to_tray"] = bool(self.var_close_tray.get())
        wanted = bool(self.var_startup.get())
        g["start_with_windows"] = startup.set_enabled(wanted)
        self.var_startup.set(g["start_with_windows"])
        self._commit()

    def _on_volume(self, _value: str) -> None:
        self.player.set_volume(int(self.var_volume.get()))
        self._save_audio()

    def _commit(self) -> None:
        """Enregistre puis repercute les reglages sur le planning et l'affichage."""
        self.config_data.save()
        self.scheduler.rebuild()
        if self.mosque:
            self.refresh_today()

    # ---------------------------------------------------------------- audio
    def _audio_choices(self) -> list[str]:
        files = sorted(p.name for p in AUDIO_DIR.glob("*")
                       if p.suffix.lower() in (".mp3", ".wav"))
        custom = self.config_data.data["audio"].get("file")
        if custom and custom not in files:
            files.append(custom)
        return files or ["(aucun fichier)"]

    def _test_audio(self) -> None:
        path = resolve_audio(self.var_audio_file.get())
        if path is None:
            self.set_status("Fichier audio introuvable.", error=True)
            return
        if not self.player.play(path, volume=int(self.var_volume.get())):
            self.set_status("Lecture impossible (format non pris en charge ?).", error=True)

    def _browse_audio(self) -> None:
        path = filedialog.askopenfilename(
            title="Choisir un adhan",
            filetypes=[("Fichiers audio", "*.mp3 *.wav"), ("Tous les fichiers", "*.*")],
        )
        if not path:
            return
        self.var_audio_file.set(path)
        menu = self.opt_audio["menu"]
        menu.delete(0, "end")
        for choice in self._audio_choices() + [path]:
            menu.add_command(label=choice,
                             command=lambda v=choice: (self.var_audio_file.set(v),
                                                       self._save_audio()))
        self._save_audio()

    # -------------------------------------------------------------- ecrans
    def _screen_index(self, label: str) -> int:
        for scr in screens.list_screens():
            if scr.label == label:
                return scr.index
        return 0

    def refresh_screen_menus(self) -> None:
        """Recharge la liste des ecrans (branchement/debranchement d'un moniteur)."""
        labels = [s.label for s in screens.list_screens()]
        for menu_widget, var, stored, save in (
            (self.opt_notif_screen, self.var_notif_screen,
             self.config_data.data["notifications"].get("screen", 0), self._save_notifications),
            (self.opt_ov_screen, self.var_ov_screen,
             self.config_data.data["overlay"].get("screen", 0), self._save_overlay),
        ):
            menu = menu_widget["menu"]
            menu.delete(0, "end")
            for lab in labels:
                menu.add_command(label=lab,
                                 command=lambda v=lab, vr=var, fn=save: (vr.set(v), fn()))
            var.set(labels[min(stored, len(labels) - 1)])

    # -------------------------------------------------------------- overlay
    def _apply_overlay_setting(self) -> None:
        wanted = self.config_data.data["overlay"].get("enabled", True)
        if wanted and self.overlay is None:
            self.overlay = Overlay(self, self.config_data, on_move=self.config_data.save)
        elif wanted and self.overlay is not None:
            self.overlay.refresh_style()
        elif not wanted and self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None

    # ------------------------------------------------------------ evenements
    def _on_event(self, event: Event) -> None:
        log.info("declenchement : %s", event.key)
        self.notifier.handle(event)

    # ----------------------------------------------------------- cycle de vie
    def hide_window(self) -> None:
        self.withdraw()

    def show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self.refresh_today()

    def on_close(self) -> None:
        if self.config_data.data["general"].get("close_to_tray", True) and self.tray:
            self.hide_window()
        else:
            self.quit_app()

    def quit_app(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self.player.stop()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                log.debug("arret de l'icone systeme", exc_info=True)
        self.destroy()
