"""Erfundene Daten fuer einkaufsliste. Kein Eintrag hier stammt aus der echten Liste.

Die Oberflaeche ist der Vite-Bau nach /tmp/sichtprobe-build/einkaufsliste:
  cd ~/docker/einkaufsliste/frontend && npx vite build --outDir /tmp/sichtprobe-build/einkaufsliste --emptyOutDir
Der Zustand haengt am Seitenpfad: "/" volle Liste, "/leer" nichts offen,
"/fehler" Dienst antwortet 503, "/ausfall" eine Quelle nicht erreichbar.
"""
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

BAU = Path("/tmp/sichtprobe-build/einkaufsliste")
WURZELN = [("/", BAU)]
MODUS = {"wert": "voll"}

GRUPPEN = [{"schluessel": s, "name": n} for s, n in [
    ("obst_gemuese", "Obst und Gemüse"), ("kuehlung", "Kühlregal"), ("trocken", "Trockenware"),
    ("drogerie", "Drogerie"), ("sonstiges", "Sonstiges")]]


def eintrag(i, text, gruppe, **mehr):
    e = {"id": f"e{i}", "text": text, "menge": None, "einheit": None, "menge_text": "", "warengruppe": gruppe,
         "herkunft": "auto", "gruende": [], "zustand": "offen", "buchung": None, "buchung_fehler": None,
         "lager_product_id": None, "preis_schaetzung": None, "preis_kette": None, "preis_am": None,
         "preis_alt": False, "gekauft_am": None}
    e.update(mehr)
    if "quellen" not in mehr:
        e["quellen"] = ["hand"] if e["herkunft"] == "hand" else (
            (["essensplan"] if any(g.startswith("für") for g in e["gruende"]) else [])
            + (["lager"] if any(not g.startswith("für") for g in e["gruende"]) else [])) or ["lager"]
    return e


def liste():
    m = MODUS["wert"]
    eintraege = [] if m == "leer" else [
        eintrag(1, "Paprika rot", "obst_gemuese", menge_text="3 Stück", gruende=["für Kichererbsen-Curry (morgen, Fr)"],
                preis_schaetzung=1.49, preis_kette="lidl", preis_am="2026-11-01"),
        eintrag(2, "Bananen", "obst_gemuese", menge_text="1 kg", gruende=["unter Mindestbestand (2 von 4)"],
                preis_schaetzung=1.19, preis_kette="kaufland", preis_am="2026-08-20", preis_alt=True),
        eintrag(3, "Milch 1,5 %", "kuehlung", menge_text="2 l", herkunft="hand", preis_schaetzung=2.18),
        eintrag(4, "Naturjoghurt", "kuehlung", menge_text="500 g",
                gruende=["für Haferbrei (Fr)", "unter Mindestbestand"]),
        eintrag(5, "Rote Linsen aus kontrolliert biologischem Anbau, große Packung", "trocken",
                menge_text="500 g", preis_schaetzung=2.49, preis_kette="netto", preis_am="2026-10-30"),
        eintrag(6, "Zahnpasta", "drogerie", herkunft="hand"),
        eintrag(7, "Haferflocken", "trocken", zustand="gekauft", menge_text="1 kg", gekauft_am="2026-11-08T10:00:00"),
        eintrag(8, "Kaffee", "trocken", zustand="gekauft", buchung="abgelehnt",
                buchung_fehler="Lager nicht erreichbar, noch nicht gebucht", gekauft_am="2026-11-08T10:01:00"),
        eintrag(9, "Gurke", "obst_gemuese", zustand="weggewischt", menge_text="1 Stück"),
    ]
    quellen = [{"quelle": "lager", "gelungen_am": "2026-11-08T09:58:00", "fehler": None},
               {"quelle": "mealprep", "gelungen_am": "2026-11-08T07:12:00",
                "fehler": "Zeitüberschreitung" if m == "ausfall" else None}]
    mit = [e for e in eintraege if e["zustand"] == "offen" and e["preis_schaetzung"]]
    ohne = [e for e in eintraege if e["zustand"] == "offen" and not e["preis_schaetzung"]]
    return {"eintraege": eintraege, "warengruppen": GRUPPEN, "quellen": quellen, "stand": "2026-11-08T10:02:00",
            "schaetzung": {"summe_eur": round(sum(e["preis_schaetzung"] for e in mit), 2),
                           "eintraege_mit_preis": len(mit), "eintraege_ohne_preis": len(ohne)}}


def api(methode, pfad, query, body):
    if pfad in ("/", "/leer", "/fehler", "/ausfall"):
        MODUS["wert"] = {"/": "voll"}.get(pfad, pfad[1:])
        return Antwort(200, (BAU / "index.html").read_bytes(), "text/html; charset=utf-8")
    if pfad in ("/api/liste", "/api/abgleich"):
        if MODUS["wert"] == "fehler":
            return Antwort(503, b'{"detail": "Datenbank gesperrt"}', "application/json")
        return liste()
    if pfad == "/api/produkte":
        return [{"id": i, "name": n, "einheit": "g", "warengruppe": "kuehlung"}
                for i, n in enumerate(["Milch 1,5 %", "Milch 3,5 %", "Milchreis"], 1)]
    return None


def tippen(seite):
    seite.fill("input[aria-label='Neuer Eintrag']", "2 Milch")
    seite.wait_for_timeout(500)


SEITEN = [
    {"name": "liste", "pfad": "/"},
    {"name": "vorschlaege", "pfad": "/", "schritte": [tippen]},
    {"name": "gruppe-waehlen", "pfad": "/", "schritte": [lambda s: s.click("button[aria-label^='Warengruppe von']")]},
    {"name": "weggewischt", "pfad": "/", "schritte": [lambda s: s.click(".weg .knopf-still")]},
    {"name": "leer", "pfad": "/leer"},
    {"name": "ausfall", "pfad": "/ausfall"},
    {"name": "fehler", "pfad": "/fehler", "fehler_erwartet": True},
]
