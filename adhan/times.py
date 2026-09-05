"""Calcul des horaires du jour a partir des donnees Mawaqit."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import PRAYER_KEYS

log = logging.getLogger(__name__)

# Ordre des colonnes dans le calendrier Mawaqit.
CALENDAR_ORDER = ["fajr", "shuruq", "dhuhr", "asr", "maghrib", "isha"]
# Ordre du champ `times` (chourouq est fourni a part).
TIMES_ORDER = ["fajr", "dhuhr", "asr", "maghrib", "isha"]


def _parse_hhmm(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    h, _, m = value.partition(":")
    try:
        hh, mm = int(h), int(m[:2])
    except ValueError:
        return None
    if 0 <= hh < 24 and 0 <= mm < 60:
        return hh, mm
    return None


def mosque_tz(mosque: dict[str, Any]) -> dt.tzinfo:
    """Fuseau de la mosquee ; retombe sur le fuseau local si inconnu."""
    name = mosque.get("timezone")
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            log.warning("fuseau inconnu : %s", name)
    return dt.datetime.now().astimezone().tzinfo or dt.timezone.utc


def raw_times_for(mosque: dict[str, Any], day: dt.date) -> dict[str, str]:
    """Horaires 'HH:MM' du jour demande, depuis le calendrier annuel si possible."""
    calendar = mosque.get("calendar")
    if isinstance(calendar, list) and len(calendar) >= 12:
        month = calendar[day.month - 1]
        if isinstance(month, dict):
            entry = month.get(str(day.day))
            if isinstance(entry, list) and len(entry) >= 6:
                return {k: entry[i] for i, k in enumerate(CALENDAR_ORDER)}

    # Repli : champ `times` (valable uniquement pour aujourd'hui).
    times = mosque.get("times")
    if isinstance(times, list) and len(times) >= 5:
        out = {k: times[i] for i, k in enumerate(TIMES_ORDER)}
        if mosque.get("shuruq"):
            out["shuruq"] = mosque["shuruq"]
        return out
    return {}


def day_schedule(mosque: dict[str, Any], day: dt.date, tz: dt.tzinfo | None = None) -> dict[str, dt.datetime]:
    """Horaires du jour en datetimes *locaux a la machine*, tries."""
    tz = tz or mosque_tz(mosque)
    raw = raw_times_for(mosque, day)
    out: dict[str, dt.datetime] = {}
    for key in PRAYER_KEYS:
        hm = _parse_hhmm(raw.get(key))
        if hm is None:
            continue
        aware = dt.datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=tz)
        out[key] = aware.astimezone()  # -> fuseau de l'ordinateur
    return out


def is_jumua(mosque: dict[str, Any], day: dt.date) -> str | None:
    """Heure de la priere du vendredi, si la mosquee la publie."""
    if day.weekday() != 4:
        return None
    if mosque.get("jumua_as_dhuhr"):
        return None
    value = mosque.get("jumua")
    return value if _parse_hhmm(value) else None


# ------------------------------------------------------------ date hijri
_HIJRI_MONTHS = [
    "Mouharram", "Safar", "Rabi al-awwal", "Rabi al-thani", "Joumada al-oula",
    "Joumada al-thania", "Rajab", "Chaabane", "Ramadan", "Chawwal",
    "Dhou al-qi'da", "Dhou al-hijja",
]


def to_hijri(day: dt.date, adjustment: int = 0) -> tuple[int, int, int]:
    """Conversion vers le calendrier hijri tabulaire (approximation +/- 1 jour)."""
    jd = day.toordinal() + 1721425 + int(adjustment)
    n = jd - 1948440 + 10632
    n2 = (n - 1) // 10631
    n = n - 10631 * n2 + 354
    j = (10985 - n) // 5316 * ((50 * n) // 17719) + (n // 5670) * ((43 * n) // 15238)
    n = n - (30 - j) // 15 * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
    month = (24 * n) // 709
    dayh = n - (709 * month) // 24
    year = 30 * n2 + j - 30
    return year, month, dayh


def hijri_label(day: dt.date, adjustment: int = 0) -> str:
    year, month, dayh = to_hijri(day, adjustment)
    name = _HIJRI_MONTHS[month - 1] if 1 <= month <= 12 else str(month)
    return f"{dayh} {name} {year}"
