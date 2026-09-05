"""Aiguillage des evenements vers les notifications visuelles et sonores."""

from __future__ import annotations

import datetime as dt
import logging
import tkinter as tk

from .. import notify, screens
from ..audio import Player, beep
from ..config import Config, PRAYER_LABELS, PRAYER_LABELS_AR
from ..paths import resolve_audio
from ..scheduler import Event, Scheduler
from . import theme as th
from .popup import Banner, Fullscreen, PrayerCheck

log = logging.getLogger(__name__)


class Notifier:
    """Traduit un evenement du planificateur en notification visible et audible."""

    def __init__(self, root: tk.Misc, config: Config, player: Player) -> None:
        self.root = root
        self.config = config
        self.player = player
        self.mosque_name = ""
        # Branche apres coup par l'appelant (app.py) : necessaire pour que
        # "J'ai prie" puisse annuler les alertes de suivi restantes.
        self.scheduler: Scheduler | None = None

    # --------------------------------------------------------------- reglages
    @property
    def settings(self) -> dict:
        return self.config.data["notifications"]

    @property
    def accent(self) -> str:
        return th.ACCENTS.get(self.settings.get("accent", "Or"), th.GOLD)

    def _style(self, kind: str) -> str:
        """Style demande, retrograde en banniere devant une application immersive."""
        key = "adhan_style" if kind == "adhan" else "reminder_style"
        style = self.settings.get(key, "banniere")
        if style == "plein-ecran" and self.settings.get("avoid_fullscreen_apps", True):
            if screens.foreground_is_fullscreen():
                log.info("application plein ecran detectee : notification en banniere")
                return "banniere"
        return style

    # ------------------------------------------------------------ declenchement
    def handle(self, event: Event) -> None:
        """Point d'entree appele par le planificateur."""
        arabic = PRAYER_LABELS_AR.get(event.prayer, "")
        when = event.prayer_time or event.when
        subtitle = f"{when:%H:%M}  ·  {self.mosque_name}" if self.mosque_name else f"{when:%H:%M}"

        if event.kind == "adhan":
            self._play_adhan(event.prayer)
            self.show(event.label, subtitle, arabic, kind="adhan",
                      clock=f"{when:%H:%M}", stoppable=True)
        elif event.kind == "check":
            self._show_check(event.prayer, event.minutes, when)
            return  # notification dediee : pas de doublon banniere/toast standard
        else:
            if self.config.data["audio"].get("reminder_sound", True):
                beep("reminder")
            self.show(event.label, subtitle, arabic, kind="reminder", clock=f"{when:%H:%M}")

        if self.settings.get("native_toast", True):
            notify.toast(event.label, subtitle, "Adhan PC")

    def _play_adhan(self, prayer: str) -> None:
        path = resolve_audio(self.config.audio_for(prayer))
        if path is None:
            log.warning("aucun fichier adhan utilisable pour %s", prayer)
            beep("warn")
            return
        self.player.play(path, volume=self.config.data["audio"].get("volume", 70))

    def stop_audio(self) -> None:
        self.player.stop()

    # --------------------------------------------------------- suivi post-adhan
    def _show_check(self, prayer: str, minutes_after: int, prayer_time: dt.datetime) -> None:
        """Alerte « avez-vous prie ? », `minutes_after` minutes apres l'adhan."""
        post = self.config.data["post_check"]
        if not post.get("enabled", True) or not self.settings.get("popup", True):
            return
        label = PRAYER_LABELS.get(prayer, prayer.title())
        subtitle = f"{label} était à {prayer_time:%H:%M}  ·  il y a {minutes_after} min"
        s = self.settings
        day = prayer_time.date()

        def on_yes() -> None:
            if self.scheduler:
                self.scheduler.mark_prayed(prayer, day)

        try:
            PrayerCheck(
                self.root, prayer_label=f"Avez-vous prié le {label} ?", subtitle=subtitle,
                arabic=PRAYER_LABELS_AR.get(prayer, ""), seconds=post.get("seconds", 45),
                position=s.get("position", "bas-droite"), screen_index=s.get("screen", 0),
                on_yes=on_yes, ornaments=s.get("ornaments", True),
            )
            beep("warn")
        except tk.TclError:
            log.exception("affichage de l'alerte de suivi impossible")

    # ----------------------------------------------------------------- affichage
    def show(self, title: str, subtitle: str, arabic: str = "", kind: str = "reminder",
             clock: str = "", stoppable: bool = False) -> None:
        """Affiche la notification maison selon le style configure."""
        if not self.settings.get("popup", True):
            return
        s = self.settings
        seconds = s.get("adhan_seconds", 90) if kind == "adhan" else s.get("popup_seconds", 25)
        on_stop = self.stop_audio if stoppable else None
        # Tant que l'adhan joue, la notification ne doit pas se fermer toute
        # seule : sinon un delai d'affichage court laisserait le son continuer
        # sans plus aucun bouton pour l'arreter.
        stay_while = self.player.is_playing if stoppable else None
        try:
            if self._style(kind) == "plein-ecran":
                Fullscreen(self.root, title=title, subtitle=subtitle, clock=clock or "",
                           arabic=arabic, accent=self.accent, seconds=seconds,
                           screen_index=s.get("screen", 0), on_stop=on_stop,
                           ornaments=s.get("ornaments", True), stay_while=stay_while)
            else:
                Banner(self.root, title=title, subtitle=subtitle, arabic=arabic,
                       accent=self.accent, seconds=seconds,
                       position=s.get("position", "bas-droite"),
                       screen_index=s.get("screen", 0), on_stop=on_stop,
                       pulse=(kind == "adhan"), ornaments=s.get("ornaments", True),
                       stay_while=stay_while)
        except tk.TclError:
            log.exception("affichage de la notification impossible")

    # ---------------------------------------------------------------------- test
    def preview(self, kind: str = "reminder", prayer: str = "maghrib",
                with_sound: bool = False) -> None:
        """Apercu depuis l'interface, sans toucher au planning."""
        label = PRAYER_LABELS.get(prayer, prayer.title())
        now = dt.datetime.now()
        if kind == "check":
            self._show_check(prayer, 10, now)
            return
        subtitle = f"{now:%H:%M}  ·  {self.mosque_name or 'Aperçu'}"
        title = f"{label} — il est l'heure" if kind == "adhan" else f"{label} dans 15 minutes"
        if kind == "adhan" and with_sound:
            self._play_adhan(prayer)
        elif with_sound:
            beep("reminder")
        self.show(title, subtitle, PRAYER_LABELS_AR.get(prayer, ""), kind=kind,
                  clock=f"{now:%H:%M}", stoppable=(kind == "adhan" and with_sound))
