#!/usr/bin/env python3
"""Prueft die Loeschwege aller Dienste: Kopien gleich, Plaene vorhanden, Abdeckung dicht.

WARUM ES DAS GIBT
=================

Der Loeschweg liegt in zwei Bauarten im Haus, und das ist kein Versehen:

* Die **sieben Saganta-Backends** teilen die Mechanik ueber das Paket
  ``saganta_dienst`` (ein Build-Kontext, eine Datei).
* Die **vier nativen Dienste** (lager, mealprep, fitness, briefkasten) tragen
  sie als **Kopie** in ``app/konto_mechanik.py``, weil sie ohne das saganta-Repo
  baubar bleiben muessen. Dasselbe gilt dort schon fuer ``backend_auth.py`` und
  ``mandant_ableiten.py``.

Vier Kopien driften. Bei ``backend_auth.py`` gibt es dafuer heute **keinen**
Abgleich, und die drei Fassungen sind gemessen verschieden (teils begruendet,
teils vermutlich nicht). Damit das beim Loeschweg nicht genauso endet, prueft
dieses Werkzeug:

1. **Sind die vier Kopien byte-identisch?** Die Mechanik darf keine
   dienstspezifischen Stellen haben; was je Dienst abweicht, gehoert in
   ``app/konto.py``.
2. **Hat jeder Dienst einen Plan?** Ein Dienst ohne ``konto.py`` ist der Fall,
   der sich im Betrieb wie "nichts zu loeschen" anfuehlt.
3. **Ist die Abdeckung dicht?** Je Dienst im laufenden Container gemessen, nicht
   am Quellbaum: ein Quellbaum-Lauf beweist, dass die Datei stimmt, nicht dass
   der Dienst sie hat. Genau diese Luecke war am 30.08.2026 der Fehler.

AUFRUF
======

    python3 scripts/loeschwege-abgleichen.py
    python3 scripts/loeschwege-abgleichen.py --json

Rueckgabewert 0 nur, wenn alles stimmt. Gedacht fuer einen Timer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

DOCKER_WURZEL = pathlib.Path(__file__).resolve().parents[2]

# Dienste mit eigener Kopie der Mechanik: (Repo-Ordner, Container)
MIT_KOPIE = [
    ("lager", "lager"),
    ("mealprep", "mealprep"),
    ("fitness", "fitness"),
    ("postfach", "briefkasten"),
]

# Saganta-Backends: (Dienst-Ordner unter saganta/services, Container)
MIT_PAKET = [
    ("notizen-api", "saganta-notizen-api"),
    ("tagebuch-api", "saganta-tagebuch-api"),
    ("assets-api", "saganta-assets-api"),
    ("projectdeck-api", "saganta-projectdeck-api"),
    ("news-api", "saganta-news-api"),
    ("shell-api", "saganta-shell-api"),
    ("mail-api", "saganta-mail-api"),
]

# Im Container ausgefuehrt: misst die Abdeckung dort, wo der Dienst laeuft.
# Die beiden Bauarten unterscheiden sich nur im Import der Mechanik.
PRUEFUNG = r"""
import json, sys
try:
    try:
        from saganta_dienst import loeschen as mechanik   # Saganta-Backends
    except ImportError:
        from app import konto_mechanik as mechanik        # native Dienste
    try:
        from app import models  # noqa: F401
    except Exception:
        pass
    try:
        from app import briefing_models  # noqa: F401  (news fuehrt zwei Modell-Module)
    except Exception:
        pass
    from app.db import Base, SessionLocal
    from app.konto import PLAN
    # Beide Pruefungen, zwei Quellen: Modelle und Datenbank. Die zweite braucht
    # eine Verbindung und findet alles, was per rohem SQL entstanden ist; sie
    # fand am 2026-10-06 die Einbettungstabelle des briefkastens, von der die
    # erste nichts wissen konnte.
    befunde = mechanik.abdeckung_pruefen(PLAN, Base.metadata)
    db = SessionLocal()
    try:
        befunde = befunde + mechanik.ungedeckte_live_tabellen(PLAN, db, Base.metadata)
        live_tabellen = db.execute(__import__("sqlalchemy").text(
            "SELECT count(*) FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic%'")).scalar()
    finally:
        db.close()
    print(json.dumps({
        "ok": not befunde,
        "tabellen": len(Base.metadata.tables),
        "live_tabellen": live_tabellen,
        "schritte": [s.tabelle for s in PLAN.schritte],
        "gemeinsam": sorted(PLAN.gemeinsam),
        "per_trigger": sorted(getattr(PLAN, "per_trigger", ()) or ()),
        "luecken": befunde,
    }))
except Exception as problem:
    print(json.dumps({"ok": False, "fehler": f"{type(problem).__name__}: {problem}"}))
"""


def _pruefsumme(pfad: pathlib.Path) -> str | None:
    if not pfad.is_file():
        return None
    return hashlib.sha256(pfad.read_bytes()).hexdigest()[:16]


def _im_container(container: str) -> dict:
    lauf = subprocess.run(
        ["docker", "exec", "-i", "-w", "/app", container, "python3", "-"],
        input=PRUEFUNG, capture_output=True, text=True, timeout=120,
    )
    if lauf.returncode != 0 and not lauf.stdout.strip():
        return {"ok": False, "fehler": (lauf.stderr or "docker exec fehlgeschlagen").strip()[:300]}
    try:
        return json.loads(lauf.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "fehler": (lauf.stdout + lauf.stderr).strip()[:300]}


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument("--json", action="store_true")
    args = zerleger.parse_args()

    ergebnis: dict = {"kopien": {}, "dienste": [], "befunde": []}

    # --- 1. Sind die vier Kopien der Mechanik identisch? ---
    summen: dict[str, str | None] = {}
    for ordner, _container in MIT_KOPIE:
        pfad = DOCKER_WURZEL / ordner / "app" / "konto_mechanik.py"
        summen[ordner] = _pruefsumme(pfad)
    ergebnis["kopien"] = summen

    fehlend = [o for o, s in summen.items() if s is None]
    if fehlend:
        ergebnis["befunde"].append(
            f"konto_mechanik.py fehlt in: {', '.join(fehlend)}")
    vorhanden = {o: s for o, s in summen.items() if s}
    if len(set(vorhanden.values())) > 1:
        ergebnis["befunde"].append(
            "Die Kopien der Mechanik sind NICHT identisch: "
            + ", ".join(f"{o}={s}" for o, s in sorted(vorhanden.items()))
            + ". Was je Dienst abweichen soll, gehoert in app/konto.py."
        )

    # --- 2. und 3. Plan vorhanden und Abdeckung dicht, je laufender Dienst ---
    for ordner, container in MIT_KOPIE:
        plan_pfad = DOCKER_WURZEL / ordner / "app" / "konto.py"
        eintrag = {"dienst": container, "bauart": "kopie", "repo": ordner,
                   "plan_im_baum": plan_pfad.is_file()}
        eintrag.update(_im_container(container))
        ergebnis["dienste"].append(eintrag)

    for ordner, container in MIT_PAKET:
        plan_pfad = (DOCKER_WURZEL / "saganta" / "services" / ordner / "app" / "konto.py")
        eintrag = {"dienst": container, "bauart": "paket", "repo": f"saganta/{ordner}",
                   "plan_im_baum": plan_pfad.is_file()}
        eintrag.update(_im_container(container))
        ergebnis["dienste"].append(eintrag)

    for eintrag in ergebnis["dienste"]:
        if not eintrag.get("plan_im_baum"):
            ergebnis["befunde"].append(f"{eintrag['dienst']}: app/konto.py fehlt im Quellbaum")
        if eintrag.get("fehler"):
            ergebnis["befunde"].append(f"{eintrag['dienst']}: {eintrag['fehler']}")
        for luecke in eintrag.get("luecken") or []:
            ergebnis["befunde"].append(f"{eintrag['dienst']}: {luecke}")

    if args.json:
        print(json.dumps(ergebnis, indent=2, ensure_ascii=False))
    else:
        _drucken(ergebnis)

    return 0 if not ergebnis["befunde"] else 1


def _drucken(ergebnis: dict) -> None:
    print("Mechanik-Kopien (muessen identisch sein)")
    print("-" * 68)
    for ordner, summe in sorted(ergebnis["kopien"].items()):
        print(f"  {ordner:<12} {summe or 'FEHLT'}")
    print()
    print("Loeschwege je Dienst, im laufenden Container gemessen")
    print("-" * 68)
    for e in ergebnis["dienste"]:
        if e.get("fehler"):
            print(f"  !! {e['dienst']:<26} {e['fehler']}")
            continue
        marke = "ok " if e.get("ok") else "!! "
        # Beide Zahlen nebeneinander: weichen sie ab, legt der Dienst Tabellen
        # per rohem SQL an, und genau die sieht die Modell-Pruefung nicht.
        modelle = e.get("tabellen", "?")
        live = e.get("live_tabellen", "?")
        zusatz = f"{modelle:>3} Modelle / {live:>3} in der DB"
        print(f"  {marke}{e['dienst']:<26} {zusatz}, "
              f"{len(e.get('schritte') or []):>2} Schritte"
              + (f", gemeinsam {e['gemeinsam']}" if e.get("gemeinsam") else "")
              + (f", per Trigger {e['per_trigger']}" if e.get("per_trigger") else ""))
    print()
    if ergebnis["befunde"]:
        print(f"{len(ergebnis['befunde'])} BEFUND(E):")
        for b in ergebnis["befunde"]:
            print(f"  - {b}")
    else:
        print("Kein Befund: Kopien gleich, jeder Dienst hat einen Plan, Abdeckung dicht.")


if __name__ == "__main__":
    raise SystemExit(main())
