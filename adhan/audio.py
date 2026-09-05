"""Lecture audio via MCI (winmm) : MP3/WAV sans dependance externe."""

from __future__ import annotations

import ctypes
import itertools
import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)

_alias_seq = itertools.count(1)
_lock = threading.Lock()


def _mci(command: str) -> tuple[int, str]:
    buf = ctypes.create_unicode_buffer(1024)
    err = ctypes.windll.winmm.mciSendStringW(command, buf, 1023, 0)
    if err:
        eb = ctypes.create_unicode_buffer(512)
        ctypes.windll.winmm.mciGetErrorStringW(err, eb, 511)
        return err, eb.value
    return 0, buf.value


class Player:
    """Lecteur simple : une piste a la fois, arret possible a tout moment."""

    def __init__(self) -> None:
        self._alias: str | None = None

    # ------------------------------------------------------------ public
    def play(self, path: Path | str, volume: int = 80) -> bool:
        """Joue un fichier. Retourne False si la lecture a echoue."""
        path = Path(path)
        if not path.exists():
            log.error("fichier audio introuvable : %s", path)
            return False
        with _lock:
            self._close_locked()
            alias = f"adhanpc{next(_alias_seq)}"
            device = "waveaudio" if path.suffix.lower() == ".wav" else "mpegvideo"
            err, msg = _mci(f'open "{path}" type {device} alias {alias}')
            if err:
                # Certains systemes preferent laisser MCI deviner le type.
                err, msg = _mci(f'open "{path}" alias {alias}')
            if err:
                log.error("MCI open a echoue (%s) : %s", path.name, msg)
                return False
            self._alias = alias
            _mci(f"setaudio {alias} volume to {max(0, min(100, int(volume))) * 10}")
            err, msg = _mci(f"play {alias}")
            if err:
                log.error("MCI play a echoue : %s", msg)
                self._close_locked()
                return False
        return True

    def stop(self) -> None:
        with _lock:
            self._close_locked()

    def is_playing(self) -> bool:
        with _lock:
            if not self._alias:
                return False
            err, mode = _mci(f"status {self._alias} mode")
            return not err and mode.strip() == "playing"

    def set_volume(self, volume: int) -> None:
        with _lock:
            if self._alias:
                _mci(f"setaudio {self._alias} volume to {max(0, min(100, int(volume))) * 10}")

    # ----------------------------------------------------------- interne
    def _close_locked(self) -> None:
        if self._alias:
            _mci(f"stop {self._alias}")
            _mci(f"close {self._alias}")
            self._alias = None


def beep(kind: str = "reminder") -> None:
    """Petit signal sonore systeme pour les rappels (non bloquant)."""
    sounds = {"reminder": 0x00000040, "warn": 0x00000030, "default": 0x00000000}
    flags = 0x00000001 | 0x00010000  # SND_ASYNC | SND_SYSTEM_ALIAS
    try:
        ctypes.windll.user32.MessageBeep(sounds.get(kind, 0x40))
    except OSError:
        log.debug("MessageBeep indisponible", exc_info=True)


def duration_seconds(path: Path | str) -> float | None:
    """Duree d'un fichier audio, ou None si indeterminable."""
    path = Path(path)
    if not path.exists():
        return None
    alias = f"probe{next(_alias_seq)}"
    err, _ = _mci(f'open "{path}" type mpegvideo alias {alias}')
    if err:
        err, _ = _mci(f'open "{path}" alias {alias}')
    if err:
        return None
    try:
        err, value = _mci(f"status {alias} length")
        return int(value) / 1000 if not err and value.isdigit() else None
    finally:
        _mci(f"close {alias}")
