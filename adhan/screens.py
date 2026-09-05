"""Detection des ecrans (multi-moniteurs) et gestion du DPI."""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from dataclasses import dataclass

log = logging.getLogger(__name__)

_MONITORINFOF_PRIMARY = 1


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT), ("rcWork", _RECT),
                ("dwFlags", ctypes.c_ulong), ("szDevice", ctypes.c_wchar * 32)]


@dataclass(frozen=True)
class Screen:
    index: int
    name: str
    primary: bool
    # Zone totale et zone utile (hors barre des taches).
    x: int
    y: int
    width: int
    height: int
    work: tuple[int, int, int, int]

    @property
    def label(self) -> str:
        tag = " (principal)" if self.primary else ""
        return f"Écran {self.index + 1} — {self.width}×{self.height}{tag}"


def enable_dpi_awareness() -> None:
    """Evite une interface floue sur les ecrans a forte densite."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # System DPI aware
    except (OSError, AttributeError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (OSError, AttributeError):
            log.debug("prise en charge DPI indisponible")


def scaling_factor() -> float:
    """Facteur d'echelle de l'ecran principal (1.0 = 96 dpi)."""
    try:
        dc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, dc)
        return max(1.0, dpi / 96.0)
    except (OSError, AttributeError):
        return 1.0


def list_screens() -> list[Screen]:
    """Enumere les moniteurs connectes, ecran principal en premier."""
    found: list[Screen] = []

    proc_type = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_RECT), ctypes.c_double
    )

    def _callback(hmon, _hdc, _lprect, _data):
        info = _MONITORINFOEX()
        info.cbSize = ctypes.sizeof(_MONITORINFOEX)
        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            m, w = info.rcMonitor, info.rcWork
            found.append(
                Screen(
                    index=len(found),
                    name=info.szDevice,
                    primary=bool(info.dwFlags & _MONITORINFOF_PRIMARY),
                    x=m.left, y=m.top,
                    width=m.right - m.left, height=m.bottom - m.top,
                    work=(w.left, w.top, w.right, w.bottom),
                )
            )
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc_type(_callback), 0)
    except (OSError, AttributeError) as exc:
        log.warning("enumeration des ecrans impossible : %s", exc)

    if not found:
        try:
            w = ctypes.windll.user32.GetSystemMetrics(0)
            h = ctypes.windll.user32.GetSystemMetrics(1)
        except (OSError, AttributeError):
            w, h = 1920, 1080
        found.append(Screen(0, "PRIMARY", True, 0, 0, w, h, (0, 0, w, h - 48)))

    # L'ecran principal en tete, puis de gauche a droite : ordre stable pour l'UI.
    ordered = sorted(found, key=lambda s: (not s.primary, s.x))
    return [
        Screen(i, s.name, s.primary, s.x, s.y, s.width, s.height, s.work)
        for i, s in enumerate(ordered)
    ]


def screen_at(index: int) -> Screen:
    """Ecran demande, ou ecran principal si l'index n'existe plus."""
    screens = list_screens()
    if 0 <= index < len(screens):
        return screens[index]
    return screens[0]


def ui_scale(screen: Screen | None = None) -> float:
    """Facteur d'agrandissement de l'interface deduit de la resolution reelle.

    Rapporte a une reference 1920x1080 et adouci par une racine carree, pour
    rester lisible aussi bien sur un 1366x768 que sur un 4K, sans reglage manuel.
    """
    screen = screen or screen_at(0)
    ratio = min(screen.width / 1920, screen.height / 1080)
    if ratio <= 0:
        return 1.0
    return max(0.85, min(1.7, round(ratio ** 0.5, 3)))


def anchor_box(screen: Screen, position: str, width: int, height: int,
               margin: int = 18, offset: int = 0) -> tuple[int, int]:
    """Coordonnees d'ancrage d'une fenetre dans un coin de l'ecran choisi."""
    left, top, right, bottom = screen.work
    x = right - width - margin
    y = bottom - height - margin - offset
    if "gauche" in position:
        x = left + margin
    if "haut" in position:
        y = top + margin + offset
    if position == "centre":
        x = (left + right - width) // 2
        y = (top + bottom - height) // 2
    return int(x), int(y)


GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000


def _update_exstyle(hwnd: int, add: int = 0, remove: int = 0) -> None:
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = wintypes.LONG
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | add) & ~remove)


def make_click_through(hwnd: int, enabled: bool) -> None:
    """Rend une fenetre transparente aux clics (widget permanent non genant).

    On ne touche jamais a WS_EX_LAYERED ici : le reposer via SetWindowLong
    efface la couleur-cle et l'opacite deja definies par Tk, et la fenetre
    devient noire. Tk garde la main sur ce bit.
    """
    try:
        _update_exstyle(hwnd,
                        add=WS_EX_TRANSPARENT if enabled else 0,
                        remove=0 if enabled else WS_EX_TRANSPARENT)
    except (OSError, AttributeError) as exc:
        log.debug("clic traversant indisponible : %s", exc)


def make_no_activate(hwnd: int) -> None:
    """Empeche la fenetre de voler le focus de l'application en cours.

    WS_EX_NOACTIVATE : la fenetre s'affiche et reste cliquable, mais n'est
    jamais activee. WS_EX_TOOLWINDOW la retire d'Alt+Tab et de la barre des
    taches. Le jeu, la video ou le document en cours gardent le clavier.
    """
    try:
        _update_exstyle(hwnd, add=WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    except (OSError, AttributeError) as exc:
        log.debug("mode sans activation indisponible : %s", exc)


def foreground_is_fullscreen() -> bool:
    """Vrai si l'application au premier plan occupe tout un ecran (jeu, video).

    Sert a ne pas recouvrir brutalement une application immersive : la
    notification bascule alors sur le format banniere.
    """
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd == user32.GetShellWindow():
            return False

        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 255)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
            return False

        rect = _RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        info = _MONITORINFOEX()
        info.cbSize = ctypes.sizeof(_MONITORINFOEX)
        hmon = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return False
        m = info.rcMonitor
        # Tolerance de quelques pixels (bordures invisibles de certaines apps).
        return (rect.left <= m.left + 2 and rect.top <= m.top + 2
                and rect.right >= m.right - 2 and rect.bottom >= m.bottom - 2)
    except (OSError, AttributeError) as exc:
        log.debug("detection plein ecran indisponible : %s", exc)
        return False
