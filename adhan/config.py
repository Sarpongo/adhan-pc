"""Configuration persistante (%APPDATA%/AdhanPC/config.json)."""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from .paths import CONFIG_FILE, ensure_dirs

log = logging.getLogger(__name__)

# Ordre d'affichage. `shuruq` n'est pas une priere mais sert de reperes/rappels.
PRAYER_KEYS = ["fajr", "shuruq", "dhuhr", "asr", "maghrib", "isha"]
ADHAN_KEYS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]

PRAYER_LABELS = {
    "fajr": "Fajr",
    "shuruq": "Chourouq",
    "dhuhr": "Dhohr",
    "asr": "Asr",
    "maghrib": "Maghrib",
    "isha": "Isha",
}

PRAYER_LABELS_AR = {
    "fajr": "\u0627\u0644\u0641\u062c\u0631",
    "shuruq": "\u0627\u0644\u0634\u0631\u0648\u0642",
    "dhuhr": "\u0627\u0644\u0638\u0647\u0631",
    "asr": "\u0627\u0644\u0639\u0635\u0631",
    "maghrib": "\u0627\u0644\u0645\u063a\u0631\u0628",
    "isha": "\u0627\u0644\u0639\u0634\u0627\u0621",
}

DEFAULT_REMINDERS = [30, 15, 10, 5]

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "mosque": {
        # Rempli au premier lancement via l'assistant de recherche.
        "slug": None,
        "name": None,
        "city": None,
        "timezone": None,
        "latitude": None,
        "longitude": None,
    },
    # Rappels par defaut, en minutes avant l'heure de la priere.
    "reminders": list(DEFAULT_REMINDERS),
    # Reglages par priere. `reminders: null` => utilise la liste globale.
    "prayers": {
        "fajr": {"enabled": True, "adhan": True, "reminders": None, "audio": "adhan_fajr.mp3"},
        "shuruq": {"enabled": False, "adhan": False, "reminders": [10], "audio": None},
        "dhuhr": {"enabled": True, "adhan": True, "reminders": None, "audio": None},
        "asr": {"enabled": True, "adhan": True, "reminders": None, "audio": None},
        "maghrib": {"enabled": True, "adhan": True, "reminders": None, "audio": None},
        "isha": {"enabled": True, "adhan": True, "reminders": None, "audio": None},
    },
    "audio": {
        "file": "adhan_makkah.mp3",   # adhan par defaut
        "volume": 70,                  # volume de l'adhan, 0-100
        "reminder_sound": True,        # petit signal sonore sur les rappels
    },
    "notifications": {
        "popup": True,                  # notification maison (ornementee)
        "adhan_style": "banniere",      # banniere | plein-ecran
        "reminder_style": "banniere",   # banniere | plein-ecran
        "position": "bas-droite",       # coin d'apparition de la banniere
        "screen": 0,                    # index de l'ecran (multi-moniteurs)
        "accent": "Or",                 # couleur d'accent
        "ornaments": True,              # encadrement arabesque
        "popup_seconds": 25,            # duree d'affichage d'un rappel
        "adhan_seconds": 90,            # duree d'affichage de l'adhan
        "avoid_fullscreen_apps": True,  # ne pas recouvrir un jeu / une video
        "native_toast": True,           # notification Windows (centre de notifications)
    },
    "overlay": {
        "enabled": True,          # rappel permanent a l'ecran
        "opacity": 18,            # opacite en pourcentage
        "screen": 0,              # ecran d'affichage
        "position": "haut-droite",
        "rel_x": 0.8,             # position libre, en fraction de l'ecran
        "rel_y": 0.05,
        "click_through": False,   # laisser passer les clics
        "size": "normal",         # normal | compact
        "accent": None,           # None => couleur d'accent des notifications
    },
    "general": {
        "start_with_windows": False,
        "start_minimized": True,
        "close_to_tray": True,
        "refresh_hours": 24,
    },
}


def _deep_merge(base: Any, override: Any) -> Any:
    """Fusionne `override` dans une copie de `base` (dict recursif)."""
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            out[k] = _deep_merge(base[k], v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(override)


def _clamp(value: Any, low: int, high: int, fallback: int) -> int:
    """Entier borne, avec repli si la valeur stockee est invalide."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return fallback


def _clean_reminders(values: Any) -> list[int] | None:
    """Normalise une liste de minutes: entiers > 0, uniques, tries decroissant."""
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        return None
    seen: set[int] = set()
    for v in values:
        try:
            m = int(v)
        except (TypeError, ValueError):
            continue
        if 0 < m <= 24 * 60:
            seen.add(m)
    return sorted(seen, reverse=True)


class Config:
    """Acces typé a la configuration, avec sauvegarde atomique."""

    def __init__(self, data: dict[str, Any] | None = None):
        self.data = _deep_merge(DEFAULTS, data or {})
        self._normalize()

    # ---------------------------------------------------------------- io
    @classmethod
    def load(cls) -> "Config":
        ensure_dirs()
        if CONFIG_FILE.exists():
            try:
                raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                return cls(raw)
            except (OSError, ValueError) as exc:
                log.warning("config illisible (%s), retour aux valeurs par defaut", exc)
        return cls()

    def save(self) -> None:
        ensure_dirs()
        self._normalize()
        tmp = CONFIG_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_FILE)

    def _normalize(self) -> None:
        self.data["reminders"] = _clean_reminders(self.data.get("reminders")) or list(DEFAULT_REMINDERS)
        prayers = self.data.setdefault("prayers", {})
        for key in PRAYER_KEYS:
            entry = prayers.setdefault(key, copy.deepcopy(DEFAULTS["prayers"][key]))
            entry["enabled"] = bool(entry.get("enabled", True))
            entry["adhan"] = bool(entry.get("adhan", key in ADHAN_KEYS))
            entry["reminders"] = _clean_reminders(entry.get("reminders"))
        self.data["audio"]["volume"] = _clamp(self.data["audio"].get("volume"), 0, 100, 70)
        notif = self.data["notifications"]
        notif["popup_seconds"] = _clamp(notif.get("popup_seconds"), 5, 600, 25)
        notif["adhan_seconds"] = _clamp(notif.get("adhan_seconds"), 5, 900, 90)
        notif["screen"] = _clamp(notif.get("screen"), 0, 16, 0)
        overlay = self.data["overlay"]
        overlay["opacity"] = _clamp(overlay.get("opacity"), 5, 100, 18)
        overlay["screen"] = _clamp(overlay.get("screen"), 0, 16, 0)

    # ------------------------------------------------------------ acces
    @property
    def mosque(self) -> dict[str, Any]:
        return self.data["mosque"]

    @property
    def reminders(self) -> list[int]:
        return self.data["reminders"]

    def prayer(self, key: str) -> dict[str, Any]:
        return self.data["prayers"][key]

    def reminders_for(self, key: str) -> list[int]:
        """Rappels effectifs d'une priere: liste dediee sinon liste globale."""
        entry = self.prayer(key)
        if not entry.get("enabled", True):
            return []
        custom = entry.get("reminders")
        return list(custom) if custom is not None else list(self.reminders)

    def audio_for(self, key: str) -> str | None:
        """Fichier adhan a jouer pour une priere (specifique sinon global)."""
        return self.prayer(key).get("audio") or self.data["audio"].get("file")

    def is_configured(self) -> bool:
        return bool(self.mosque.get("slug"))

    def set_mosque(self, mosque: dict[str, Any]) -> None:
        self.mosque.update(
            {
                "slug": mosque.get("slug"),
                "name": mosque.get("name"),
                "city": mosque.get("localisation") or mosque.get("city"),
                "timezone": mosque.get("timezone") or self.mosque.get("timezone"),
                "latitude": mosque.get("latitude"),
                "longitude": mosque.get("longitude"),
            }
        )
