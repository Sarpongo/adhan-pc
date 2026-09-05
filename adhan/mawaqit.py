"""Client Mawaqit : recherche de mosquee et recuperation des horaires.

Deux sources sont utilisees :
  * `/api/2.0/mosque/search` pour trouver une mosquee (par mot-cle ou position) ;
  * la page publique de la mosquee, qui embarque un objet `confData` contenant
    le calendrier annuel complet -> l'application fonctionne ensuite hors ligne.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from .paths import CACHE_DIR, ensure_dirs

log = logging.getLogger(__name__)

BASE = "https://mawaqit.net"
SEARCH_URL = BASE + "/api/2.0/mosque/search"
PAGE_URL = BASE + "/fr/{slug}"
GEOIP_URL = "http://ip-api.com/json/?fields=status,lat,lon,city,countryCode"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

TIMEOUT = 20


class MawaqitError(RuntimeError):
    pass


# ------------------------------------------------------------------ recherche
def search(word: str = "", lat: float | None = None, lon: float | None = None) -> list[dict[str, Any]]:
    """Cherche des mosquees par mot-cle (ville, nom) ou par coordonnees."""
    params: dict[str, Any] = {}
    if word:
        params["word"] = word
    if lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon
    if not params:
        raise MawaqitError("Recherche vide : indiquez une ville ou utilisez la géolocalisation.")
    try:
        r = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        raise MawaqitError(f"Mawaqit injoignable : {exc}") from exc
    except ValueError as exc:
        raise MawaqitError("Réponse Mawaqit illisible.") from exc
    return [m for m in data if isinstance(m, dict) and m.get("slug")]


def locate_by_ip() -> tuple[float, float, str]:
    """Position approximative via l'IP publique (pour la recherche 'autour de moi')."""
    try:
        r = requests.get(GEOIP_URL, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        if d.get("status") != "success":
            raise MawaqitError("Géolocalisation indisponible.")
        return float(d["lat"]), float(d["lon"]), d.get("city") or ""
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise MawaqitError(f"Géolocalisation impossible : {exc}") from exc


# -------------------------------------------------------------- confData
def _extract_conf_data(html: str) -> dict[str, Any]:
    """Extrait l'objet JSON `confData` inclus dans la page de la mosquee."""
    marker = "confData"
    idx = html.find(marker)
    while idx != -1:
        brace = html.find("{", idx)
        if brace == -1:
            break
        try:
            obj, _ = json.JSONDecoder().raw_decode(html[brace:])
        except ValueError:
            idx = html.find(marker, idx + len(marker))
            continue
        if isinstance(obj, dict) and "times" in obj:
            return obj
        idx = html.find(marker, idx + len(marker))
    raise MawaqitError("Horaires introuvables sur la page Mawaqit (format modifié ?).")


def fetch_mosque(slug: str) -> dict[str, Any]:
    """Telecharge et normalise les donnees d'une mosquee."""
    try:
        r = requests.get(PAGE_URL.format(slug=slug), headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 404:
            raise MawaqitError(f"Mosquée introuvable sur Mawaqit : {slug}")
        r.raise_for_status()
    except requests.RequestException as exc:
        raise MawaqitError(f"Mawaqit injoignable : {exc}") from exc

    conf = _extract_conf_data(r.text)
    payload = {
        "slug": slug,
        "name": conf.get("name") or slug,
        "city": conf.get("localisation") or conf.get("label"),
        "timezone": conf.get("timezone"),
        "latitude": conf.get("latitude"),
        "longitude": conf.get("longitude"),
        "times": conf.get("times"),
        "shuruq": conf.get("shuruq"),
        "calendar": conf.get("calendar"),
        "iqama_calendar": conf.get("iqamaCalendar"),
        "iqama_enabled": bool(conf.get("iqamaEnabled")),
        "jumua": conf.get("jumua"),
        "jumua2": conf.get("jumua2"),
        "jumua_as_dhuhr": bool(conf.get("jumuaAsDuhr")),
        "hijri_adjustment": conf.get("hijriAdjustment") or 0,
        "fetched_at": time.time(),
    }
    if not payload["calendar"] and not payload["times"]:
        raise MawaqitError("Aucun horaire publié par cette mosquée.")
    return payload


# ------------------------------------------------------------------- cache
def cache_path(slug: str):
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)[:120]
    return CACHE_DIR / f"{safe}.json"


def save_cache(payload: dict[str, Any]) -> None:
    ensure_dirs()
    path = cache_path(payload["slug"])
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_cache(slug: str) -> dict[str, Any] | None:
    path = cache_path(slug)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("cache illisible pour %s : %s", slug, exc)
        return None


def get_mosque(slug: str, refresh: bool = True) -> tuple[dict[str, Any], bool]:
    """Retourne (donnees, frais_du_reseau). Retombe sur le cache si hors ligne."""
    if refresh:
        try:
            payload = fetch_mosque(slug)
            save_cache(payload)
            return payload, True
        except MawaqitError as exc:
            log.warning("recuperation en ligne echouee : %s", exc)
    cached = load_cache(slug)
    if cached:
        return cached, False
    raise MawaqitError(
        "Impossible de récupérer les horaires et aucun cache disponible. "
        "Vérifiez votre connexion internet."
    )
