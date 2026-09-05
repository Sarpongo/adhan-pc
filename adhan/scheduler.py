"""Construction et declenchement des evenements (rappels + adhan)."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import Config, PRAYER_KEYS, PRAYER_LABELS
from . import times as tmod

log = logging.getLogger(__name__)

# Un evenement declenche jusqu'a 2 minutes de retard (veille/hibernation courte).
GRACE = dt.timedelta(minutes=2)
# Horizon de planification : aujourd'hui + demain.
HORIZON_DAYS = 2


@dataclass(frozen=True)
class Event:
    when: dt.datetime
    kind: str          # "reminder" ou "adhan"
    prayer: str
    minutes: int = 0   # minutes avant la priere (0 pour l'adhan)
    prayer_time: dt.datetime | None = None

    @property
    def key(self) -> str:
        return f"{self.when:%Y-%m-%d}|{self.prayer}|{self.kind}|{self.minutes}"

    @property
    def label(self) -> str:
        name = PRAYER_LABELS.get(self.prayer, self.prayer.title())
        if self.kind == "adhan":
            return f"{name} — il est l'heure"
        if self.minutes >= 60:
            h, m = divmod(self.minutes, 60)
            delay = f"{h} h" if not m else f"{h} h {m:02d}"
        else:
            delay = f"{self.minutes} minute" + ("s" if self.minutes > 1 else "")
        return f"{name} dans {delay}"


@dataclass
class Scheduler:
    config: Config
    on_event: Callable[[Event], None]
    mosque: dict[str, Any] | None = None
    events: list[Event] = field(default_factory=list)
    _fired: set[str] = field(default_factory=set)
    _built_for: dt.date | None = None

    # ------------------------------------------------------------ donnees
    def set_mosque(self, mosque: dict[str, Any] | None) -> None:
        self.mosque = mosque
        self.rebuild()

    def schedule_for(self, day: dt.date) -> dict[str, dt.datetime]:
        if not self.mosque:
            return {}
        return tmod.day_schedule(self.mosque, day)

    def today_schedule(self) -> dict[str, dt.datetime]:
        return self.schedule_for(dt.date.today())

    # ---------------------------------------------------------- planning
    def rebuild(self, now: dt.datetime | None = None) -> None:
        """Recalcule la file d'evenements et neutralise ceux deja passes."""
        now = now or dt.datetime.now().astimezone()
        today = now.date()
        self._built_for = today
        self._fired = {k for k in self._fired if k.split("|", 1)[0] >= today.isoformat()}

        events: list[Event] = []
        for offset in range(HORIZON_DAYS):
            day = today + dt.timedelta(days=offset)
            schedule = self.schedule_for(day)
            for prayer in PRAYER_KEYS:
                when = schedule.get(prayer)
                if when is None:
                    continue
                entry = self.config.prayer(prayer)
                if not entry.get("enabled", True):
                    continue
                if entry.get("adhan", False):
                    events.append(Event(when, "adhan", prayer, 0, when))
                for minutes in self.config.reminders_for(prayer):
                    events.append(
                        Event(when - dt.timedelta(minutes=minutes), "reminder", prayer, minutes, when)
                    )

        events.sort(key=lambda e: e.when)
        # Les evenements deja expires ne doivent jamais se declencher a posteriori.
        for ev in events:
            if now - ev.when > GRACE:
                self._fired.add(ev.key)
        self.events = events

    # --------------------------------------------------------- execution
    def tick(self, now: dt.datetime | None = None) -> list[Event]:
        """A appeler ~chaque seconde. Declenche et retourne les evenements dus."""
        now = now or dt.datetime.now().astimezone()
        if self._built_for != now.date():
            self.rebuild(now)

        due: list[Event] = []
        for ev in self.events:
            if ev.when > now:
                break
            if ev.key in self._fired:
                continue
            self._fired.add(ev.key)
            if now - ev.when <= GRACE:
                due.append(ev)
            else:
                log.info("evenement manque (machine en veille ?) : %s", ev.key)

        for ev in due:
            try:
                self.on_event(ev)
            except Exception:  # une notification ratee ne doit pas tuer la boucle
                log.exception("echec du declenchement de %s", ev.key)
        return due

    # ------------------------------------------------------------ lecture
    def next_event(self, now: dt.datetime | None = None) -> Event | None:
        now = now or dt.datetime.now().astimezone()
        for ev in self.events:
            if ev.when > now and ev.key not in self._fired:
                return ev
        return None

    def next_prayer(self, now: dt.datetime | None = None) -> tuple[str, dt.datetime] | None:
        """Prochaine priere (chourouq exclu), aujourd'hui ou demain."""
        now = now or dt.datetime.now().astimezone()
        for offset in range(HORIZON_DAYS):
            schedule = self.schedule_for(now.date() + dt.timedelta(days=offset))
            for prayer, when in sorted(schedule.items(), key=lambda kv: kv[1]):
                if prayer == "shuruq":
                    continue
                if when > now:
                    return prayer, when
        return None

    def current_prayer(self, now: dt.datetime | None = None) -> str | None:
        """Derniere priere dont l'heure est passee (pour la mise en evidence)."""
        now = now or dt.datetime.now().astimezone()
        best: tuple[dt.datetime, str] | None = None
        for offset in (0, -1):
            schedule = self.schedule_for(now.date() + dt.timedelta(days=offset))
            for prayer, when in schedule.items():
                if prayer == "shuruq" or when > now:
                    continue
                if best is None or when > best[0]:
                    best = (when, prayer)
            if best:
                break
        return best[1] if best else None
