"""Emplacements des fichiers de l'application."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _base_dir() -> Path:
    """Racine du projet (dossier contenant adhan_pc.py et assets/)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
ASSETS_DIR = BASE_DIR / "assets"
AUDIO_DIR = ASSETS_DIR / "audio"

DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AdhanPC"
CACHE_DIR = DATA_DIR / "cache"
CONFIG_FILE = DATA_DIR / "config.json"
LOG_FILE = DATA_DIR / "adhan.log"

ICON_ICO = ASSETS_DIR / "icon.ico"
ICON_PNG = ASSETS_DIR / "icon.png"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def resolve_audio(name: str | None) -> Path | None:
    """Un nom court designe un fichier de assets/audio, sinon chemin absolu."""
    if not name:
        return None
    p = Path(name)
    if p.is_absolute():
        return p if p.exists() else None
    p = AUDIO_DIR / name
    return p if p.exists() else None
