"""Adhan PC — point d'entree.

Usage :
    python adhan_pc.py               interface visible
    pythonw adhan_pc.py --minimized  demarrage silencieux (barre des taches)
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys

from adhan import APP_NAME, __version__, notify, screens, singleton
from adhan.paths import LOG_FILE, ensure_dirs


def setup_logging(verbose: bool = False) -> None:
    ensure_dirs()
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=512_000, backupCount=2, encoding="utf-8"
        )
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        handlers=handlers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {__version__}")
    parser.add_argument("--minimized", action="store_true",
                        help="demarrer reduit dans la barre des taches")
    parser.add_argument("--verbose", action="store_true", help="journal detaille")
    args = parser.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("adhan")
    log.info("demarrage de %s %s", APP_NAME, __version__)

    if not singleton.acquire():
        # Une instance tourne deja (demarrage Windows + double-clic manuel, par
        # exemple) : on ne duplique jamais le planificateur ni l'adhan.
        log.info("une instance d'Adhan PC tourne deja : arret immediat")
        notify.toast(APP_NAME, "Adhan PC fonctionne deja (voir la barre des taches).")
        return 0

    try:
        # Interface nette sur les ecrans haute densite, avant toute fenetre Tk.
        screens.enable_dpi_awareness()
        notify.register_app_id()

        from adhan.ui.app import AdhanApp
        from adhan.ui import tray as tray_module

        app = AdhanApp(start_minimized=args.minimized)
        app.tray = tray_module.build(app)
        app.refresh_screen_menus()
        if app.tray is None and args.minimized:
            # Sans icone systeme, une fenetre cachee serait irrecuperable.
            app.deiconify()
        try:
            app.mainloop()
        except KeyboardInterrupt:
            app.quit_app()
    finally:
        singleton.release()
    log.info("arret")
    return 0


if __name__ == "__main__":
    sys.exit(main())
