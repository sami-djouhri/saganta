#!/usr/bin/env python3
"""Backend-Registry gegen Frontend-Katalog: kennen beide dieselben Apps?

**Warum es dieses Skript gibt.** Der App-Katalog steht an **zwei** Orten:
``services/shell-api/app/registry.py`` (das Launchpad fragt es ab) und
``packages/ui/src/apps.ts`` (der App-Wechsler in jeder App). Beide bilden die
Adresse aus dem Raum des Aufrufers, und beide muessen dafuer dieselben Namen und
dieselben Ausnahmen kennen.

Die ``registry.py`` verspricht diese Pruefung seit dem 2026-09-13 woertlich:
"Beide muessen dieselben Namen kennen, die Pruefung dazu steht in
``tests/test_registry.py``". Am 2026-10-16 nachgesehen: **dort stand sie nicht**.
Es gab keinen einzigen Test, der die TS-Datei ueberhaupt anfasst. Eine
zugesicherte Pruefung, die es nicht gibt, ist schlechter als keine, weil man sich
beim Aendern auf sie verlaesst.

Warum ein Skript und nicht ein Test: der Test laeuft im Image, und dort liegt
``packages/`` nicht. Er muesste also ueberspringen, wenn die Datei fehlt -- und
ein Waechter, der im Normalfall ueberspringt, meldet nie etwas. Dieses Skript
laeuft im Quellbaum, wo beide Dateien liegen, und sagt es, wenn eine fehlt.

Gelesen wird **beide Seiten textuell**: die Python-Seite ueber ``ast`` (keine
Abhaengigkeiten, kein Import des Dienstes), die TS-Seite ueber einen
Zeilenleser. Damit laeuft es auf jedem Wirt mit python3 und braucht weder
fastapi noch node.

    python3 scripts/app-katalog-abgleich.py          # Abgleich, Exit 1 bei Abweichung
    python3 scripts/app-katalog-abgleich.py --zeigen # beide Katalterge nebeneinander
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
REGISTRY = WURZEL / "services/shell-api/app/registry.py"
KATALOG = WURZEL / "packages/ui/src/apps.ts"

#: Die Felder, die auf beiden Seiten gleich sein muessen. Name links wie in
#: Python, rechts wie in TypeScript. Was NICHT verglichen wird: Name,
#: Beschreibung, Icon, Signatur und Tags -- die duerfen sich unterscheiden, weil
#: die beiden Kataloge verschiedene Flaechen bedienen (Launchpad gegen
#: App-Wechsler). Verglichen wird, was ueber die **Adresse** entscheidet.
FELDER = [("sub", "sub"), ("sub_heim", "subHeim"), ("nur_heim", "nurHeim")]

#: Kennungen, die absichtlich nur im Frontend stehen, mit Begruendung. Eine
#: Ausnahmeliste ist hier das kleinere Uebel gegenueber einem Abgleich, der
#: dauerhaft rot steht und deshalb nicht mehr gelesen wird -- aber nur, solange
#: jede Zeile einen Grund traegt. Ohne Grund gehoert sie geloescht, nicht
#: ergaenzt.
NUR_FRONTEND = {
    # Die Shell ist der App-Wechsler selbst. Sie gehoert in dessen Liste (man
    # springt von einer App zurueck zur Uebersicht), aber nicht in den Katalog,
    # aus dem das Launchpad seine Kacheln baut: eine Uebersicht, die sich selbst
    # als Kachel zeigt, ist ein Kreis.
    "shell": "App-Wechsler-Ziel, aber keine Kachel im eigenen Launchpad",
}


def aus_python() -> dict[str, dict]:
    """Die ``AppVorlage(...)``-Aufrufe aus der Registry, ohne sie zu importieren."""
    baum = ast.parse(REGISTRY.read_text(encoding="utf-8"))
    gefunden: dict[str, dict] = {}
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        name = getattr(knoten.func, "id", None) or getattr(knoten.func, "attr", None)
        if name != "AppVorlage":
            continue
        eintrag: dict = {}
        for kw in knoten.keywords:
            if kw.arg is None:
                continue
            try:
                eintrag[kw.arg] = ast.literal_eval(kw.value)
            except ValueError:
                eintrag[kw.arg] = "<nicht auswertbar>"
        kennung = eintrag.get("id")
        if kennung:
            gefunden[kennung] = eintrag
    return gefunden


def aus_typescript() -> dict[str, dict]:
    """Die Objekt-Literale aus ``SAGANTA_APPS``.

    Bewusst zeilenweise und nicht mit einem Alles-Muster: die Datei enthaelt
    mehrzeilige Kommentare und CSS-Gradienten mit Klammern und Kommas, an denen
    ein Klammerzaehler scheitert. Ein Eintrag beginnt mit ``id:`` und endet beim
    naechsten ``id:`` oder am Ende der Liste.

    ⚠️ Gelesen wird **nur** der Bereich von ``SAGANTA_APPS`` bis zur
    schliessenden Zeile ``];``. Ohne diese Grenze fand der erste Lauf
    ``nav-downloads`` als App: das ist ein Eintrag der Befehlspalette weiter
    unten in derselben Datei, und er traegt ebenfalls ein ``id:``. Ein
    Fehlbefund aus dem eigenen Leser sieht genauso aus wie ein echter.
    """
    text = KATALOG.read_text(encoding="utf-8")
    gefunden: dict[str, dict] = {}
    aktuell: str | None = None
    in_liste = False
    for rohe in text.splitlines():
        zeile = rohe.strip()
        if zeile.startswith("//"):
            continue
        if not in_liste:
            if re.match(r"export const SAGANTA_APPS\b", zeile):
                in_liste = True
            continue
        if zeile == "];":
            break
        m = re.match(r"id:\s*'([^']+)'", zeile)
        if m:
            aktuell = m.group(1)
            gefunden[aktuell] = {"id": aktuell}
            continue
        if aktuell is None:
            continue
        m = re.match(r"(sub|subHeim|nurHeim):\s*(.+?),?\s*$", zeile)
        if m:
            schluessel, wert = m.group(1), m.group(2).rstrip(",").strip()
            if wert in ("true", "false"):
                gefunden[aktuell][schluessel] = wert == "true"
            else:
                gefunden[aktuell][schluessel] = wert.strip("'\"")
    return gefunden


def _norm(wert) -> object:
    """``None``, ``False`` und ein fehlendes Feld bedeuten dasselbe.

    Die Python-Seite schreibt ``nur_heim: bool = False`` und ``sub_heim: str |
    None = None``, die TS-Seite laesst beide Felder einfach weg. Ohne diese
    Angleichung meldete der Abgleich zehn Abweichungen, die keine sind.
    """
    if wert in (None, False, ""):
        return None
    return wert


def abgleich(zeigen: bool) -> int:
    fehlende = [p for p in (REGISTRY, KATALOG) if not p.exists()]
    if fehlende:
        for p in fehlende:
            print(f"FEHLT: {p.relative_to(WURZEL)}")
        print("\nOhne beide Dateien ist kein Abgleich moeglich. Das ist ein Fehler,")
        print("kein Ueberspringen: dieses Skript gehoert in den Quellbaum.")
        return 2

    py = aus_python()
    ts = aus_typescript()

    if zeigen:
        print(f"{'id':14} {'registry.py':34} {'apps.ts'}")
        for kennung in sorted(set(py) | set(ts)):
            def kurz(d: dict) -> str:
                if kennung not in d:
                    return "-- fehlt --"
                e = d[kennung]
                teile = []
                for links, rechts in FELDER:
                    wert = _norm(e.get(links if d is py else rechts))
                    if wert is not None:
                        teile.append(f"{links}={wert}")
                return " ".join(teile) or "(nur sub leer)"
            print(f"{kennung:14} {kurz(py):34} {kurz(ts)}")
        print()

    abweichungen: list[str] = []
    nur_py = sorted(set(py) - set(ts))
    nur_ts = sorted(set(ts) - set(py))
    for kennung in nur_py:
        abweichungen.append(f"{kennung}: nur in registry.py (im App-Wechsler fehlt die App)")
    for kennung in nur_ts:
        if kennung in NUR_FRONTEND:
            print(f"  (gewollt nur im Frontend: {kennung} -- {NUR_FRONTEND[kennung]})")
            continue
        abweichungen.append(f"{kennung}: nur in apps.ts (im Launchpad fehlt die Kachel)")

    for kennung in sorted(set(py) & set(ts)):
        for links, rechts in FELDER:
            a, b = _norm(py[kennung].get(links)), _norm(ts[kennung].get(rechts))
            if a != b:
                abweichungen.append(
                    f"{kennung}.{links}: registry.py={a!r} gegen apps.ts={b!r}"
                )

    if not abweichungen:
        print(f"Deckungsgleich: {len(py)} Apps, je {len(FELDER)} adressbildende Felder geprueft.")
        heim = sorted(k for k, e in py.items() if e.get("nur_heim"))
        print(f"Davon heim-only: {heim or '(keine)'}")
        return 0

    print(f"{len(abweichungen)} Abweichung(en):\n")
    for a in abweichungen:
        print(f"  {a}")
    print()
    print("Beide Kataloge bilden Adressen. Wer nur einen aendert, bekommt keinen")
    print("Fehler, sondern zwei verschiedene Antworten auf dieselbe Frage: das")
    print("Launchpad zeigt eine Kachel, die der App-Wechsler nicht kennt, oder")
    print("umgekehrt. Beide Dateien in einem Vorgang aendern.")
    return 1


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--zeigen", action="store_true", help="beide Kataloge nebeneinander")
    a = p.parse_args()
    return abgleich(a.zeigen)


if __name__ == "__main__":
    sys.exit(main())
