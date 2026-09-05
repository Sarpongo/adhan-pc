"""Icone dans la zone de notification de Windows."""

from __future__ import annotations

import logging
import threading

from PIL import Image

from ..paths import ICON_PNG

log = logging.getLogger(__name__)


def build(app) -> object | None:
    """Cree et demarre l'icone systeme. Retourne None si pystray est absent."""
    try:
        import pystray
    except ImportError:
        log.info("pystray non installe : pas d'icone dans la barre des taches")
        return None

    try:
        image = Image.open(ICON_PNG)
    except OSError as exc:
        log.warning("icone introuvable : %s", exc)
        return None

    def run(action):
        """Renvoie l'action vers la boucle Tk (pystray tourne dans un thread)."""
        return lambda *_a: app.after(0, action)

    menu = pystray.Menu(
        pystray.MenuItem("Ouvrir Adhan PC", run(app.show_window), default=True),
        pystray.MenuItem("Horaires du jour", run(lambda: (app.show_window(),
                                                          app.show_page("today")))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Arrêter l'adhan", run(app.notifier.stop_audio)),
        pystray.MenuItem("Actualiser les horaires", run(lambda: app.load_mosque(refresh=True))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter", run(app.quit_app)),
    )
    icon = pystray.Icon("AdhanPC", image, "Adhan PC", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon
