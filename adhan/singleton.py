"""Verrou mono-instance : un seul Adhan PC a la fois (double-clic, demarrage

Windows et raccourci manuel peuvent tous lancer l'application ; sans ce
verrou on se retrouverait avec deux planificateurs, deux adhans qui se
chevauchent et deux icones dans la barre des taches.
"""

from __future__ import annotations

import ctypes
import logging

log = logging.getLogger(__name__)

_ERROR_ALREADY_EXISTS = 183
_mutex_handle: int | None = None


def acquire(name: str = "AdhanPC.SingleInstance") -> bool:
    """Tente de prendre le verrou global. False si une instance tourne deja."""
    global _mutex_handle
    try:
        # use_last_error=True : sans lui, ctypes.get_last_error() ne reflete pas
        # le vrai code d'erreur Win32 renvoye par CreateMutexW.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, False, f"Global\\{name}")
        already_running = ctypes.get_last_error() == _ERROR_ALREADY_EXISTS
        if not handle or already_running:
            if handle:
                kernel32.CloseHandle(handle)
            return False
        _mutex_handle = handle
        return True
    except OSError as exc:
        log.warning("verrou mono-instance indisponible (%s) : poursuite sans lui", exc)
        return True


def release() -> None:
    global _mutex_handle
    if _mutex_handle:
        try:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        except OSError:
            pass
        _mutex_handle = None
