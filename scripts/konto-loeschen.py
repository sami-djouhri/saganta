#!/usr/bin/env python3
"""Den Bestand eines Mandanten ueber alle Dienste zeigen und entfernen.

WARUM ES DAS GIBT
=================

Ein Loeschrecht, das je Dienst einzeln ausgeuebt werden muss, ist in einer Suite
aus zwoelf Diensten keines. Dieses Werkzeug verkettet die Loeschwege, die es
gibt, und **benennt die, die es nicht gibt**, mit Zeilenzahl.

Gegenstueck zu ``verwaiste-mandanten.py``: das findet Mandanten, deren Konto weg
ist. Dieses hier raeumt einen ab.

WAS ES AUSDRUECKLICH NICHT TUT
==============================

1. **Es loescht das Konto nicht in der Anmelde-Datenbank.** Das ist der letzte
   Schritt und gehoert dem Auth-Dienst. Erst die Daten, dann die Anmeldung:
   andersherum entsteht genau der verwaiste Bestand, gegen den das hier gebaut
   ist.

2. **Es fasst den Kalender nicht an.** Er hat einen eigenen, aelteren Loeschweg
   (``backend/account.py:delete_account_data``), und an seinem Owner-Sub haengt
   ueber den headerlosen Pfad ``day-type/today`` die **Weckkette der Wohnung**.
   Ein verketteter Lauf, der versehentlich den Owner traefe, nimmt die Heizung
   mit. Der Befehl wird genannt, nicht ausgefuehrt. Das ist eine Entscheidung,
   keine Luecke: hier ist Nichtstun reversibel und Tun nicht.

3. **Es erfindet keine Loeschwege.** Vier Dienste haben keinen. Sie erscheinen
   im Bericht mit dem, was dort liegen bleibt. Ein Werkzeug von aussen, das in
   fremden Datenbanken Zeilen entfernt, ohne deren Fremdschluesselketten zu
   kennen, waere die schlechtere Haelfte dieser Loesung.

AUFRUF
======

    python3 scripts/konto-loeschen.py --sub <sub>              # nur zeigen
    python3 scripts/konto-loeschen.py --sub <sub> --loeschen   # wirklich loeschen
    python3 scripts/konto-loeschen.py --sub <sub> --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

# Alle Dienste mit einem Loeschplan (``app/konto.py``), in zwei Bauarten:
# die sieben Saganta-Backends teilen die Mechanik ueber ``saganta_dienst``, die
# vier nativen tragen sie als abgeglichene Kopie (``konto_mechanik.py``).
# Gerufen wird beide Male gleich, deshalb steht hier eine Liste und nicht zwei.
# Dass die Kopien nicht driften, prueft ``loeschwege-abgleichen.py``.
MIT_LOESCHWEG = [
    ("saganta-notizen-api", "notizen"),
    ("saganta-tagebuch-api", "tagebuch"),
    ("saganta-assets-api", "assets"),
    ("saganta-projectdeck-api", "projectdeck"),
    ("saganta-news-api", "news"),
    ("saganta-shell-api", "shell"),
    ("saganta-mail-api", "mail"),
    ("lager", "lager"),
    ("mealprep", "mealprep"),
    ("fitness", "fitness"),
    ("briefkasten", "briefkasten"),
]

# Dienste, die Mandantenbestand halten und keinen Loeschweg haben. Sie werden
# gezaehlt, nicht angefasst. Die Liste ist seit dem 2026-10-06 leer, und sie
# bleibt hier stehen: wer einen neuen Dienst anbindet, hat den Platz, ihn
# einzutragen, statt ihn stillschweigend auszulassen.
OHNE_LOESCHWEG: list[tuple[str, str, str]] = []

# Eigener Loeschweg, bewusst nicht verkettet. Siehe Punkt 2 im Modulkopf.
EIGENER_WEG = [
    (
        "kalender",
        "/app/data/*.db",
        "docker/kalender",
        'docker exec kalender python -c "'
        "from backend.database import SessionLocal; from backend.account import delete_account_data; "
        "db=SessionLocal(); print(delete_account_data(db, '<sub>')); db.commit()\"",
    ),
]

MANDANTEN_SPALTEN = ("owner_sub", "sub", "owner", "created_by_sub", "user_sub")

# Zaehlt den Bestand eines Mandanten in einer fremden Datenbank. Bewusst
# Standardbibliothek: in den Dienst-Images liegt kein zusaetzliches Paket, und
# ein `pip install` nur fuer eine Messung veraendert den gemessenen Zustand.
IM_CONTAINER = r"""
import glob, json, sqlite3, sys
sub = sys.argv[1]
spalten = set(sys.argv[2].split(","))
treffer = {}
dateien = []
for muster in sys.argv[3].split():
    dateien.extend(glob.glob(muster))
for pfad in sorted(set(dateien)):
    try:
        verb = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        tabellen = [r[0] for r in verb.execute(
            "select name from sqlite_master where type='table'")]
    except Exception:
        continue
    for tabelle in tabellen:
        if tabelle.startswith("sqlite_") or tabelle.startswith("alembic"):
            continue
        try:
            vorhanden = [r[1] for r in verb.execute(f"pragma table_info({tabelle})")]
        except Exception:
            continue
        for spalte in vorhanden:
            if spalte not in spalten:
                continue
            try:
                anzahl = verb.execute(
                    f"select count(*) from {tabelle} where {spalte} = ?", (sub,)
                ).fetchone()[0]
            except Exception:
                continue
            if anzahl:
                treffer[f"{tabelle}.{spalte}"] = anzahl
print(json.dumps(treffer))
"""


def _docker(argumente: list[str], eingabe: str | None = None) -> tuple[int, str]:
    ergebnis = subprocess.run(
        ["docker", *argumente],
        capture_output=True,
        text=True,
        input=eingabe,
        timeout=180,
    )
    return ergebnis.returncode, (ergebnis.stdout or "") + (ergebnis.stderr or "")


def _laeuft(container: str) -> bool:
    rc, ausgabe = _docker(["inspect", "-f", "{{.State.Running}}", container])
    return rc == 0 and ausgabe.strip() == "true"


def dienst_bearbeiten(container: str, name: str, sub: str, loeschen: bool) -> dict:
    """Einen Dienst mit Loeschplan aufrufen. Der Dienst selbst entscheidet, was faellt."""
    if not _laeuft(container):
        # Nicht still ueberspringen. Ein nicht laufender Dienst ist kein
        # leerer Dienst, und ein Bericht, der ihn weglaesst, behauptet mehr als
        # er weiss.
        return {"dienst": name, "erreichbar": False,
                "hinweis": f"Container {container} laeuft nicht. Bestand ungeprueft."}

    befehl = ["exec", "-w", "/app", container, "python", "-m", "app.konto", "--sub", sub]
    if loeschen:
        befehl.append("--loeschen")
    rc, ausgabe = _docker(befehl)
    try:
        bericht = json.loads(ausgabe)
    except json.JSONDecodeError:
        return {"dienst": name, "erreichbar": True, "fehler": ausgabe.strip()[:400]}
    bericht["erreichbar"] = True
    bericht["rc"] = rc
    return bericht


def bestand_zaehlen(container: str, glob_muster: str, sub: str) -> dict:
    if not _laeuft(container):
        return {"erreichbar": False}
    rc, ausgabe = _docker(
        ["exec", "-i", container, "python3", "-", sub,
         ",".join(MANDANTEN_SPALTEN), glob_muster],
        eingabe=IM_CONTAINER,
    )
    try:
        return {"erreichbar": True, "zeilen": json.loads(ausgabe)}
    except json.JSONDecodeError:
        return {"erreichbar": True, "fehler": ausgabe.strip()[:300]}


def main() -> int:
    zerleger = argparse.ArgumentParser(
        description="Bestand eines Mandanten ueber alle Saganta-Dienste zeigen und entfernen.",
    )
    zerleger.add_argument("--sub", required=True, help="Mandant (sub aus der Anmeldung)")
    zerleger.add_argument(
        "--loeschen", action="store_true",
        help="wirklich loeschen. Ohne diesen Schalter nur anzeigen.",
    )
    zerleger.add_argument("--json", action="store_true", help="maschinenlesbar")
    args = zerleger.parse_args()

    gesamt: dict = {"sub": args.sub, "geloescht": args.loeschen,
                    "mit_loeschweg": [], "ohne_loeschweg": [], "eigener_weg": []}

    for container, name in MIT_LOESCHWEG:
        gesamt["mit_loeschweg"].append(
            dienst_bearbeiten(container, name, args.sub, args.loeschen))

    for container, muster, repo in OHNE_LOESCHWEG:
        eintrag = bestand_zaehlen(container, muster, args.sub)
        eintrag.update({"dienst": container, "repo": repo})
        gesamt["ohne_loeschweg"].append(eintrag)

    for container, muster, repo, befehl in EIGENER_WEG:
        eintrag = bestand_zaehlen(container, muster, args.sub)
        eintrag.update({"dienst": container, "repo": repo,
                        "befehl": befehl.replace("<sub>", args.sub)})
        gesamt["eigener_weg"].append(eintrag)

    if args.json:
        print(json.dumps(gesamt, indent=2, ensure_ascii=False))
    else:
        _bericht_drucken(gesamt, args)

    # Rueckgabewert: 0 nur, wenn jeder verkettete Dienst sauber war UND nirgends
    # ungeloeschter Bestand zurueckbleibt. Ein Loeschlauf, nach dem noch Daten da
    # sind, ist kein Erfolg, auch wenn jeder Einzelschritt gelang.
    unsauber = [d for d in gesamt["mit_loeschweg"]
                if not d.get("erreichbar") or d.get("fehler") or (
                    args.loeschen and not d.get("sauber"))]
    reste = _offene_summe(gesamt)
    return 0 if not unsauber and not (args.loeschen and reste) else 1


def _offene_summe(gesamt: dict) -> int:
    summe = 0
    for eintrag in gesamt["ohne_loeschweg"] + gesamt["eigener_weg"]:
        summe += sum((eintrag.get("zeilen") or {}).values())
    return summe


def _bericht_drucken(gesamt: dict, args) -> None:
    tun = "GELOESCHT" if gesamt["geloescht"] else "VORSCHAU, es wurde nichts entfernt"
    print(f"Mandant {gesamt['sub']}   [{tun}]")
    print()
    print("Dienste mit Loeschweg")
    print("-" * 70)
    for d in gesamt["mit_loeschweg"]:
        name = d.get("dienst", "?")
        if not d.get("erreichbar"):
            print(f"  {name:<14} NICHT ERREICHBAR  {d.get('hinweis','')}")
            continue
        if d.get("fehler"):
            print(f"  {name:<14} FEHLER  {d['fehler']}")
            continue
        zeilen = {k: v for k, v in (d.get("zeilen") or {}).items() if v}
        marke = "ok " if d.get("sauber") else "!! "
        print(f"  {marke}{name:<12} {d.get('summe', 0):>6} Zeile(n)  "
              f"{zeilen if zeilen else '(nichts)'}")
        for zusatz in d.get("nebenwirkungen") or []:
            print(f"     {zusatz}")
        for luecke in d.get("luecken") or []:
            print(f"     LUECKE: {luecke}")
        for ort, anzahl in (d.get("reste") or {}).items():
            print(f"     REST: {ort} = {anzahl}")

    print()
    print("Eigener Loeschweg, bewusst NICHT verkettet")
    print("-" * 70)
    for e in gesamt["eigener_weg"]:
        summe = sum((e.get("zeilen") or {}).values())
        print(f"  {e['dienst']:<14} {summe:>6} Zeile(n)   Repo {e['repo']}")
        print("     Grund: an seinem Owner-Sub haengt die headerlose Weckkette (day-type).")
        print(f"     Von Hand: {e['befehl']}")

    print()
    print("Dienste OHNE Loeschweg (hier bleibt Bestand stehen)")
    print("-" * 70)
    for e in gesamt["ohne_loeschweg"]:
        if not e.get("erreichbar"):
            print(f"  {e['dienst']:<14} nicht erreichbar, Bestand ungeprueft")
            continue
        zeilen = e.get("zeilen") or {}
        summe = sum(zeilen.values())
        if summe:
            print(f"  {e['dienst']:<14} {summe:>6} Zeile(n)   Repo {e['repo']}")
            for ort, anzahl in sorted(zeilen.items(), key=lambda p: -p[1])[:4]:
                print(f"                      {ort} = {anzahl}")
        else:
            print(f"  {e['dienst']:<14} {0:>6} Zeile(n)   Repo {e['repo']}")

    # Zwei Arten von Rest, und sie bedeuten Verschiedenes. Ein Dienst mit
    # eigenem, nur nicht verkettetem Weg verlangt einen zweiten Befehl; ein
    # Dienst ohne Weg verlangt erst Arbeit am Code. Die frueher hier stehende
    # gemeinsame Zahl las sich in beiden Faellen wie "nicht erfuellbar".
    ohne_weg = sum(sum((e.get("zeilen") or {}).values()) for e in gesamt["ohne_loeschweg"])
    nicht_verkettet = sum(sum((e.get("zeilen") or {}).values()) for e in gesamt["eigener_weg"])
    print()
    if ohne_weg:
        print(f"ERGEBNIS: {ohne_weg} Zeile(n) liegen in Diensten OHNE Loeschweg.")
        print("Das Loeschrecht ist dort nicht erfuellbar, ohne vorher Code zu bauen.")
    elif nicht_verkettet:
        print(f"ERGEBNIS: jeder Dienst hat einen Loeschweg. {nicht_verkettet} Zeile(n) liegen")
        print("im Kalender, der bewusst von Hand gefahren wird (Befehl oben).")
        print("Das Loeschrecht ist erfuellbar, aber nicht mit einem einzigen Befehl.")
    else:
        print("ERGEBNIS: kein Bestand ausserhalb der verketteten Dienste gefunden.")
    print()
    print("Die Anmeldung selbst (saganta-auth) ist hier nicht angefasst.")
    print("Erst die Daten, dann das Konto: andersherum entsteht ein verwaister Bestand.")


if __name__ == "__main__":
    raise SystemExit(main())
