"""Lancement automatique avec Windows (cle Run de HKEY_CURRENT_USER)."""

from __future__ import annotations

import logging
import sys
import winreg
from pathlib import Path

from .paths import BASE_DIR

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AdhanPC"


def pythonw() -> Path:
    """Interpreteur sans console, pour un demarrage silencieux."""
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return candidate if candidate.exists() else exe


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    script = BASE_DIR / "adhan_pc.py"
    return f'"{pythonw()}" "{script}" --minimized'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("lecture du demarrage automatique impossible : %s", exc)
        return False


def set_enabled(enabled: bool) -> bool:
    """Active ou desactive le demarrage automatique. Retourne l'etat obtenu."""
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return enabled
    except OSError as exc:
        log.error("modification du demarrage automatique impossible : %s", exc)
        return is_enabled()


def sync(enabled: bool) -> bool:
    """Reecrit la commande si elle a change (deplacement du dossier, autre Python)."""
    if not enabled:
        return set_enabled(False) if is_enabled() else False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            current, _ = winreg.QueryValueEx(key, VALUE_NAME)
        if current == launch_command():
            return True
    except (FileNotFoundError, OSError):
        pass
    return set_enabled(True)
