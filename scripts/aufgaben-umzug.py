#!/usr/bin/env python3
"""Die Aufgaben des ProjectDecks in den Aufgaben-Dienst umziehen.

Entschieden in der sechsten Fragerunde (`docs/RICHTUNG.md`, 04.11.): **alle**
`project_tasks` ziehen um, offene wie erledigte. Eine Aufgabe hat kein Feld
fuer eine Zustaendigkeit, auch nicht unsichtbar.

| ProjectDeck | Aufgaben-Dienst |
|---|---|
| Titel mit „Owner:" / „Owner-" | Titel ohne Praefix |
| ``priority`` 1-2 / 3 / 4-5 | ``hoch`` / ``mittel`` / ``niedrig`` |
| ``blocked`` | offen, ``wartet_grund`` |
| ``in_progress``, ``scheduled`` | offen (die Zeit haelt der Dienst selbst) |
| ``done`` | erledigt, ``erledigt_am`` = ``completed_at`` (fehlt es: ``updated_at``) |
| ``description`` | ``notiz`` |
| ``deadline`` | ``faellig`` |
| ``remaining_minutes`` sonst ``estimated_minutes`` | ``dauer_min`` |
| Projekt-Slug | ``projekt`` |
| Kennung | ``herkunft = projectdeck:<id>`` |

⚠️ **Nicht per SQL.** Beide Dienste fuehren Loeschplan und Mandantenspalten;
der Mandant kommt aus dem Token. Deshalb ueber beide APIs.

**Wiederholbar.** Jede umgezogene Aufgabe traegt ihre Herkunft, und der
Dienst nimmt dieselbe Herkunft kein zweites Mal an (409). Ein zweiter Lauf
legt nichts doppelt an, ein abgebrochener setzt dort fort, wo er stand.

**Liest jede Zeile zurueck** und vergleicht sie Feld fuer Feld mit dem Soll.
Ein unbekannter Feldname ergibt bis zur Scharfschaltung von
``SAGANTA_FREMDFELDER`` eine 201 ohne Wirkung (`docs/FELDNAMEN_BEFUND.md`).

⚠️ Der Umzug kopiert nur. ``project_tasks`` bleibt stehen, bis das ProjectDeck
ueber den Aufgaben-Dienst liest (Schritt 4 in
interne Notiz); bis dahin gibt es zwei
Orte. Deshalb erst ``--anwenden``, wenn Schritt 4 ausgerollt wird.

Aufruf::

    python3 scripts/aufgaben-umzug.py --pruefen     # zaehlt und zeigt, schreibt nichts
    python3 scripts/aufgaben-umzug.py --anwenden
    python3 scripts/aufgaben-umzug.py --selbsttest  # die Zuordnung an erfundenen Zeilen
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
TOKEN_WERKZEUG = WURZEL / "scripts" / "dienst-token.py"
PORT = 8000

_OWNER_PRAEFIX = re.compile(r"^\s*owner\s*[:\-]\s*", re.IGNORECASE)

#: Laenger darf eine Aufgabe im Dienst nicht sein (``dauer_min`` le=1440).
MAX_DAUER = 1440

#: Felder, die nach dem Anlegen zurueckgelesen und verglichen werden.
VERGLICHEN = ("titel", "notiz", "prioritaet", "faellig", "dauer_min", "projekt",
              "wartet_grund", "erledigt", "herkunft")


def prioritaet(stufe: int | None) -> str:
    if stufe is None:
        return "mittel"
    if stufe <= 2:
        return "hoch"
    if stufe == 3:
        return "mittel"
    return "niedrig"


def zuordnen(aufgabe: dict, slug: str) -> dict:
    """Eine Zeile des ProjectDecks als Rumpf fuer ``POST /api/aufgaben``."""
    titel = aufgabe["title"].strip()
    if _OWNER_PRAEFIX.match(titel):
        titel = _OWNER_PRAEFIX.sub("", titel, count=1)
        titel = titel[:1].upper() + titel[1:]
    rumpf = {
        "titel": titel[:500],
        "notiz": (aufgabe.get("description") or None),
        "prioritaet": prioritaet(aufgabe.get("priority")),
        "faellig": aufgabe.get("deadline"),
        "dauer_min": aufgabe.get("remaining_minutes") or aufgabe.get("estimated_minutes"),
        "projekt": slug,
        "herkunft": f"projectdeck:{aufgabe['id']}",
    }
    # Der Dienst nimmt hoechstens einen Tag je Aufgabe. Eine groessere
    # Schaetzung wird nicht still gekappt (das waere eine falsche Zahl), sondern
    # als Satz in die Notiz gelegt; gefunden beim ersten --anwenden (2400 Min.).
    if rumpf["dauer_min"] and rumpf["dauer_min"] > MAX_DAUER:
        satz = (f"Schaetzung aus dem ProjectDeck: {rumpf['dauer_min']} Min. "
                f"(mehr als ein Tag, deshalb nicht als Dauer gesetzt).")
        rumpf["notiz"] = f"{rumpf['notiz']}\n\n{satz}" if rumpf["notiz"] else satz
        rumpf["dauer_min"] = None
    if rumpf["notiz"]:
        rumpf["notiz"] = rumpf["notiz"][:5000]
    status = aufgabe.get("status")
    if status == "done":
        rumpf["erledigt_am"] = aufgabe.get("completed_at") or aufgabe.get("updated_at")
    elif status == "blocked":
        rumpf["wartet_grund"] = "blockiert (aus dem ProjectDeck)"
    return {k: v for k, v in rumpf.items() if v is not None}


def abweichungen(soll: dict, ist: dict) -> list[str]:
    erwartet = dict(soll)
    erwartet["erledigt"] = "erledigt_am" in soll
    fehler = []
    for feld in VERGLICHEN:
        if erwartet.get(feld) != ist.get(feld):
            fehler.append(f"{feld}: soll {erwartet.get(feld)!r}, ist {ist.get(feld)!r}")
    return fehler


# ------------------------------------------------------------------ Technik


def container_adresse(container: str) -> str:
    roh = subprocess.run(
        ["docker", "inspect", container, "--format",
         "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    if not roh:
        raise SystemExit(f"Container {container} hat keine Adresse (laeuft er?)")
    return f"http://{roh[0]}:{PORT}"


def hole_token(dienst: str) -> str:
    """Ueber dienst-token.py; das Token wird nie ausgegeben."""
    erg = subprocess.run([sys.executable, str(TOKEN_WERKZEUG), dienst, "--minuten", "15"],
                         capture_output=True, text=True)
    if erg.returncode != 0:
        raise SystemExit(f"Token fuer {dienst} fehlgeschlagen:\n{erg.stderr.strip()}")
    return erg.stdout.strip()


class Api:
    def __init__(self, container: str, dienst: str) -> None:
        self.basis = container_adresse(container)
        self.token = hole_token(dienst)

    def ruf(self, methode: str, pfad: str, rumpf: dict | None = None):
        anfrage = urllib.request.Request(
            f"{self.basis}{pfad}",
            data=json.dumps(rumpf).encode() if rumpf is not None else None,
            method=methode,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=30) as antwort:
                inhalt = antwort.read()
                return json.loads(inhalt) if inhalt else None
        except urllib.error.HTTPError as fehler:
            raise SystemExit(f"{methode} {pfad} -> HTTP {fehler.code}: {fehler.read().decode()[:300]}") from fehler


def soll_bestand(deck: Api) -> list[tuple[str, dict]]:
    """(Slug, Rumpf) fuer jede Aufgabe jedes Projekts, offen und erledigt."""
    bestand = []
    for projekt in deck.ruf("GET", "/api/projects"):
        for aufgabe in deck.ruf("GET", f"/api/projects/{projekt['id']}/tasks"):
            bestand.append((projekt["slug"], zuordnen(aufgabe, projekt["slug"])))
    return bestand


def vorhanden(dienst: Api, herkunft: str) -> dict | None:
    treffer = dienst.ruf("GET", "/api/aufgaben?herkunft=" + urllib.parse.quote(herkunft))
    return treffer[0] if treffer else None


def zaehlung(bestand: list[tuple[str, dict]]) -> dict[str, Counter]:
    je: dict[str, Counter] = {}
    for slug, rumpf in bestand:
        je.setdefault(slug, Counter())["erledigt" if "erledigt_am" in rumpf else "offen"] += 1
    return je


def lauf(anwenden: bool) -> int:
    deck = Api("saganta-projectdeck-api", "projectdeck-api")
    dienst = Api("saganta-aufgaben-api", "aufgaben-api")
    bestand = soll_bestand(deck)

    gesamt = Counter("erledigt" if "erledigt_am" in rumpf else "offen" for _, rumpf in bestand)
    print(f"ProjectDeck: {len(bestand)} Aufgaben, {gesamt['offen']} offen, {gesamt['erledigt']} erledigt, "
          f"{len({s for s, _ in bestand})} Projekte")

    neu = schon = falsch = 0
    for slug, rumpf in bestand:
        ist = vorhanden(dienst, rumpf["herkunft"])
        if ist is not None:
            schon += 1
            fehler = abweichungen(rumpf, ist)
            if fehler:
                falsch += 1
                print(f"  ABWEICHUNG {rumpf['herkunft']} ({slug}): " + "; ".join(fehler))
            continue
        if not anwenden:
            neu += 1
            continue
        angelegt = dienst.ruf("POST", "/api/aufgaben", rumpf)
        zurueck = dienst.ruf("GET", f"/api/aufgaben/{angelegt['id']}")
        fehler = abweichungen(rumpf, zurueck)
        if fehler:
            falsch += 1
            print(f"  ABWEICHUNG nach Anlegen {rumpf['herkunft']} ({slug}): " + "; ".join(fehler))
        neu += 1

    verb = "angelegt" if anwenden else "wuerden angelegt"
    print(f"Aufgaben-Dienst: {neu} {verb}, {schon} schon da, {falsch} mit Abweichung")

    # Zaehlung je Projekt: Soll gegen das, was der Dienst nach dem Lauf zaehlt.
    ist_je = dienst.ruf("GET", "/api/projekte/zaehlung")
    luecken = 0
    for slug, soll in sorted(zaehlung(bestand).items()):
        ist = ist_je.get(slug, {"offen": 0, "erledigt": 0})
        if anwenden and (ist["offen"] < soll["offen"] or ist["erledigt"] < soll["erledigt"]):
            luecken += 1
            print(f"  LUECKE {slug}: soll {dict(soll)}, ist {ist}")
    if anwenden:
        print(f"Zaehlung je Projekt: {luecken} Projekte mit Luecke")
    return 1 if (falsch or luecken) else 0


def selbsttest() -> int:
    """Die Zuordnung an erfundenen Zeilen, ohne Netz."""
    faelle = [
        ({"id": 1, "title": "Owner: DNS eintragen", "status": "open", "priority": 1}, "x",
         {"titel": "DNS eintragen", "prioritaet": "hoch"}),
        ({"id": 2, "title": "Owner-Geraetetest auf 0.4.0", "status": "done", "priority": 3,
          "completed_at": None, "updated_at": "2026-10-01T10:00:00Z"}, "x",
         {"titel": "Geraetetest auf 0.4.0", "prioritaet": "mittel",
          "erledigt_am": "2026-10-01T10:00:00Z"}),
        ({"id": 3, "title": "Tests nachziehen", "status": "blocked", "priority": 5,
          "estimated_minutes": 30, "remaining_minutes": None, "deadline": "2026-12-01"}, "y",
         {"titel": "Tests nachziehen", "prioritaet": "niedrig", "dauer_min": 30,
          "faellig": "2026-12-01", "wartet_grund": "blockiert (aus dem ProjectDeck)",
          "projekt": "y", "herkunft": "projectdeck:3"}),
        ({"id": 4, "title": "Ownership klaeren", "status": "in_progress", "priority": 4}, "z",
         {"titel": "Ownership klaeren", "prioritaet": "niedrig"}),
        ({"id": 5, "title": "Grosser Umbau", "status": "open", "priority": 3,
          "estimated_minutes": 2400, "description": "Stand."}, "z",
         {"dauer_min": None, "notiz": "Stand.\n\nSchaetzung aus dem ProjectDeck: 2400 Min. "
          "(mehr als ein Tag, deshalb nicht als Dauer gesetzt)."}),
    ]
    rot = 0
    for zeile, slug, erwartet in faelle:
        ist = zuordnen(zeile, slug)
        if "wer" in ist:
            rot += 1
            print(f"ROT Fall {zeile['id']}: Feld wer gesetzt (Nachentscheid 05.11.)")
        for feld, wert in erwartet.items():
            if ist.get(feld) != wert:
                rot += 1
                print(f"ROT Fall {zeile['id']}: {feld} soll {wert!r}, ist {ist.get(feld)!r}")
        if zeile["status"] != "done" and "erledigt_am" in ist:
            rot += 1
            print(f"ROT Fall {zeile['id']}: offen, aber erledigt_am gesetzt")
    print("Selbsttest", "gruen" if not rot else f"rot ({rot})")
    return 1 if rot else 0


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    gruppe = zerleger.add_mutually_exclusive_group()
    gruppe.add_argument("--pruefen", action="store_true", help="nur zaehlen und zeigen (Vorgabe)")
    gruppe.add_argument("--anwenden", action="store_true", help="fehlende anlegen und zuruecklesen")
    gruppe.add_argument("--selbsttest", action="store_true", help="Zuordnung an erfundenen Zeilen")
    args = zerleger.parse_args()
    if args.selbsttest:
        return selbsttest()
    return lauf(anwenden=args.anwenden)


if __name__ == "__main__":
    raise SystemExit(main())
