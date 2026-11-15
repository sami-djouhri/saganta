"""Wohnort auf der Karte: Adresse -> Koordinate.

Gefragt wird allein die Offline-Adresssuche des Karten-Portals (node1,
``settings.adresssuche_url``), nie ein fremder Dienst: eine Adressliste an
einen Geocoder draussen waere genau die Sammelabfrage, die das Haus nicht
verlassen soll.

Nichts aus der Adresse kommt ins Protokoll, weder hier noch als Fehlertext.
  Geloggt werden nur Zahlen. Auf node1 protokolliert der nginx ``/adressen/``
  aus demselben Grund ohne Query.

Der Weg in zwei Stufen:

1. Strukturiert, wenn die Adresse ein Komma hat (``Hauptstrasse 5, 12345
   Musterstadt``): Ort nachschlagen, darin die Strasse, darin die Hausnummer.
   Das ist der genaue Weg; die freie Suche liest ein Strassenwort mitunter als
   Ort (im Index stehen Orte namens „Rathausplatz").
2. Sonst die freie Suche der Adresssuche, mit der Bedingung, dass ein Treffer
   im dort erkannten Ort liegt. Ohne diese Bedingung landete eine
   gleichnamige Strasse aus einer anderen Stadt auf der Karte, und ein
   falscher Punkt sieht genauso richtig aus wie ein richtiger.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Kontakt

log = structlog.get_logger()

#: Dieselbe Form wie ``HAUSNUMMER`` in ``karten/adressen/dienst.py``.
HAUSNUMMER = re.compile(r"^\d{1,4}[a-zA-Z]?$|^\d{1,4}[-/]\d{1,4}[a-zA-Z]?$")
PLZ = re.compile(r"^\d{5}$")
_LAENDER = {"deutschland", "germany", "de", "brd"}
ZEITLIMIT_S = 4.0


class NichtErreichbar(Exception):
    """Die Adresssuche antwortet nicht. Der Kontakt wird spaeter erneut gesucht."""


@dataclass(frozen=True)
class Fund:
    lat: float
    lon: float
    genauigkeit: str  # adresse | strasse | ort


def _grund(s: str) -> str:
    """Vergleichsform: klein, ohne Akzente, ß als ss, ``str.`` als ``strasse``."""
    s = s.casefold().replace("ß", "ss")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"str\.?$", "strasse", s.strip())
    return re.sub(r"\s+", " ", s)


def _hol(pfad: str, **params: object) -> object:
    url = settings.adresssuche_url.rstrip("/") + pfad
    try:
        r = httpx.get(url, params=params, timeout=ZEITLIMIT_S)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Nur die Art des Fehlers: die URL traegt die Adresse als Query.
        raise NichtErreichbar(type(exc).__name__) from None


def _teile(adresse: str) -> list[str]:
    roh = re.split(r"[,\n;]+", adresse)
    teile = []
    for t in roh:
        woerter = [w for w in t.split() if _grund(w) not in _LAENDER]
        if woerter:
            teile.append(" ".join(woerter))
    return teile


def _ohne_plz(text: str) -> tuple[str, str | None]:
    plz = None
    rest = []
    for w in text.split():
        if PLZ.match(w):
            plz = w
        else:
            rest.append(w)
    return " ".join(rest), plz


def _nummer_abtrennen(text: str) -> tuple[str, str | None]:
    """``Hauptstrasse 5a`` -> (``Hauptstrasse``, ``5a``); auch ``5 a``."""
    woerter = text.split()
    if len(woerter) >= 3 and len(woerter[-1]) == 1 and woerter[-1].isalpha() \
            and woerter[-2].isdigit():
        woerter[-2:] = [woerter[-2] + woerter[-1]]
    if len(woerter) >= 2 and HAUSNUMMER.match(woerter[-1]):
        return " ".join(woerter[:-1]), woerter[-1]
    return text, None


def _strukturiert(teile: list[str]) -> Fund | None:
    ortsname, plz = _ohne_plz(teile[-1])
    if not ortsname:
        return None
    orte = _hol("/orte", q=ortsname)
    passend = [o for o in orte if _grund(o["name"]) == _grund(ortsname)]
    if plz:
        # Gleichnamige Orte (es gibt mehrere „Neustadt“): die Postleitzahl
        # entscheidet, wenn sie passt; sonst der groesste, wie die Liste sortiert.
        passend.sort(key=lambda o: (o.get("plz") or "")[:3] != plz[:3])
    if not passend:
        return None
    ort = passend[0]
    strasse_text, nummer = _nummer_abtrennen(teile[0]) if len(teile) > 1 else ("", None)
    if strasse_text:
        strassen = _hol("/strassen", ort=ort["id"], q=strasse_text)
        gleich = [s for s in strassen if _grund(s["name"]) == _grund(strasse_text)]
        if gleich:
            strasse = gleich[0]
            if nummer:
                for h in _hol("/nummern", strasse=strasse["id"], q=nummer):
                    if _grund(h["nummer"]) == _grund(nummer):
                        return Fund(h["lat"], h["lon"], "adresse")
            return Fund(strasse["lat"], strasse["lon"], "strasse")
    return Fund(ort["lat"], ort["lon"], "ort")


def _frei(teile: list[str]) -> Fund | None:
    text, _plz = _ohne_plz(" ".join(teile))
    if len(text) < 2:
        return None
    antwort = _hol("/suche", q=text)
    treffer = antwort.get("treffer") or []
    erkannt = (antwort.get("ort") or {}).get("name")
    # Der ganze Text ist ein Ortsname („Musterstadt"): der Ort, nicht eine
    # gleichnamige Strasse irgendwo anders.
    for t in treffer:
        if t["typ"] == "ort" and _grund(t["name"]) == _grund(text):
            return Fund(t["lat"], t["lon"], "ort")
    # Strasse oder Hausnummer nur im erkannten Ort. Ohne Ort waere „Hauptstrasse
    # 5" irgendeine der tausend Hauptstrassen im Land.
    if not erkannt:
        return None
    for typ in ("adresse", "strasse"):
        for t in treffer:
            if t["typ"] == typ and _grund(t.get("ort") or "") == _grund(erkannt):
                return Fund(t["lat"], t["lon"], typ)
    return None


def aufloesen(adresse: str) -> Fund | None:
    """Koordinate zur Adresse oder ``None``. Wirft ``NichtErreichbar``."""
    teile = _teile(adresse)
    if not teile:
        return None
    if len(teile) > 1:
        fund = _strukturiert(teile)
        if fund is not None and fund.genauigkeit != "ort":
            return fund
        frei = _frei(teile)
        return frei or fund
    return _frei(teile)


def an(k: Kontakt) -> bool:
    """Ist die Suche eingeschaltet und hat der Kontakt etwas zu suchen?"""
    return bool(settings.adresssuche_url) and bool(k.adresse)


def zuruecksetzen(k: Kontakt) -> None:
    k.lat = k.lon = None
    k.ort_stand = k.ort_genauigkeit = None


def suchen(k: Kontakt) -> bool:
    """Sucht den Ort eines Kontakts und traegt ihn ein. ``False`` = nicht erreicht.

    Schreibt nur das Objekt, der Aufrufer committet.
    """
    if not an(k):
        return True
    try:
        fund = aufloesen(k.adresse or "")
    except NichtErreichbar:
        return False
    if fund is None:
        k.lat = k.lon = None
        k.ort_stand, k.ort_genauigkeit = "nicht_gefunden", None
    else:
        k.lat, k.lon = fund.lat, fund.lon
        k.ort_stand, k.ort_genauigkeit = "gefunden", fund.genauigkeit
    return True


def nachziehen(db: Session, grenze: int = 100) -> dict[str, int]:
    """Sucht alle noch nicht gesuchten Orte (Hintergrundlauf, auch Altbestand)."""
    zahl = {"gefunden": 0, "nicht_gefunden": 0, "unerreicht": 0}
    if not settings.adresssuche_url:
        return zahl
    offen = db.scalars(
        select(Kontakt).where(
            Kontakt.ort_stand.is_(None), Kontakt.adresse.is_not(None),
            Kontakt.geloescht_am.is_(None),
        ).limit(grenze)
    ).all()
    for k in offen:
        if not suchen(k):
            zahl["unerreicht"] += 1
            break  # Adresssuche weg: nicht jeden Kontakt einzeln in den Zeitablauf schicken
        zahl[k.ort_stand or "nicht_gefunden"] += 1
    db.commit()
    if any(zahl.values()):
        log.info("kontakte.orte_nachgezogen", **zahl)
    return zahl
