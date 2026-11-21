#!/usr/bin/env python3
"""Die Projektakte im Klartext, fuer die Arbeit am Terminal.

    python3 scripts/projektakte.py gartiko          # Slug
    python3 scripts/projektakte.py "spiele dash"    # Name, unscharf
    python3 scripts/projektakte.py --liste          # Gliederung aller Projekte

Liest dieselbe Route wie Web und App (`GET /api/projects/{id}/akte`) ueber
den Dienst-Token aus `dienst-token.py`; es gibt keine eigene Sicht. Gedacht
fuer „arbeite an XY weiter": zuerst die Akte lesen, dann an den offenen
Aufgaben weitermachen. Ausgegeben werden Aufgaben, Fristen, Termine, Rollen
und Summen; Telefonnummern, Mailadressen und Notiztitel bewusst nicht
(Notizen nur gezaehlt).
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent


def _deck():
    spec = importlib.util.spec_from_file_location("pflege", HIER / "projectdeck-plaene.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.Deck(modul.container_adresse(), modul.hole_token())


def finde(projekte: list[dict], frage: str) -> dict:
    frage_k = frage.strip().lower()
    for p in projekte:
        if p["slug"] == frage_k or p["name"].lower() == frage_k:
            return p
    treffer = [p for p in projekte if frage_k in p["name"].lower() or frage_k in p["slug"]]
    if len(treffer) == 1:
        return treffer[0]
    namen = {p["name"].lower(): p for p in projekte} | {p["slug"]: p for p in projekte}
    nah = difflib.get_close_matches(frage_k, list(namen), n=5, cutoff=0.5)
    kandidaten = treffer or [namen[n] for n in nah]
    if len(kandidaten) == 1:
        return kandidaten[0]
    vorschlag = ", ".join(f"{p['name']} ({p['slug']})" for p in kandidaten) or "keine"
    raise SystemExit(f"Projekt '{frage}' nicht eindeutig. Kandidaten: {vorschlag}")


def gliederung(projekte: list[dict]) -> None:
    nach_id = {p["id"]: p for p in projekte}

    def zeile(p: dict, tiefe: int, pfad: set[int]) -> None:
        mehr = " (auch woanders)" if len(p.get("eltern_ids") or []) > 1 else ""
        print(f"{'  ' * tiefe}- {p['name']} [{p['slug']}] {p.get('open_tasks', 0)} offen{mehr}")
        for kid in sorted(p.get("kinder_ids") or [], key=lambda i: nach_id.get(i, {}).get("name", "")):
            if kid in nach_id and kid not in pfad:
                zeile(nach_id[kid], tiefe + 1, pfad | {kid})

    wurzeln = [p for p in projekte if not set(p.get("eltern_ids") or []) & set(nach_id)]
    for p in sorted(wurzeln, key=lambda p: p["name"].lower()):
        zeile(p, 0, {p["id"]})


def euro(cent: int | None) -> str:
    return "-" if cent is None else f"{cent / 100:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


def akte_zeigen(a: dict) -> None:
    p = a["projekt"]
    pfad = " / ".join(s["name"] for s in a["pfad"])
    print(f"# {p['name']} [{p['slug']}]  Status {p['status']}" + (f"  (unter {pfad})" if pfad else ""))
    if len(a["eltern"]) > 1:
        print("  steht unter: " + ", ".join(e["name"] for e in a["eltern"]))
    if p.get("next_action"):
        print(f"  naechste Aktion: {p['next_action']}")
    if p.get("description"):
        print(f"  {p['description']}")
    namen = {s: v["name"] for s, v in a["projekte"].items()}
    if a["kinder"]:
        print("\n## Unterprojekte")
        for k in a["kinder"]:
            print(f"  - {k['name']} [{k['slug']}]: {k['offen']} offen, {k['hoch']} hoch, "
                  f"{k['ueberfaellig']} ueberfaellig" + (f", naechstes {k['naechstes_datum']}" if k["naechstes_datum"] else ""))
    print("\n## Offene Aufgaben" + (" (Dienst nicht erreichbar)" if a["aufgaben_fehlen"] else ""))
    rang = {"hoch": 0, "mittel": 1, "niedrig": 2}
    je: dict[str, list[dict]] = {}
    for t in a["aufgaben"]:
        je.setdefault(t.get("projekt") or p["slug"], []).append(t)
    for slug in sorted(je, key=lambda s: (s != p["slug"], namen.get(s, s).lower())):
        if len(je) > 1 or slug != p["slug"]:
            print(f"### {namen.get(slug, slug)}")
        for t in sorted(je[slug], key=lambda t: (t.get("wartet", False), rang.get(t.get("prioritaet"), 1))):
            zusatz = []
            if t.get("prioritaet") == "hoch":
                zusatz.append("hoch")
            if t.get("faellig"):
                zusatz.append(f"faellig {t['faellig']}")
            if t.get("wartet"):
                zusatz.append("wartet" + (f": {t['wartet_grund']}" if t.get("wartet_grund") else ""))
            if t.get("weitere_projekte"):
                zusatz.append("auch " + ", ".join(t["weitere_projekte"]))
            if t.get("notizen"):
                zusatz.append(f"{len(t['notizen'])} Notiz(en)")  # nur gezaehlt
            print(f"  - {t['titel']}" + (f"  [{'; '.join(zusatz)}]" if zusatz else "") + f"  ({t['id']})")
            if t.get("notiz"):
                for z in str(t["notiz"]).splitlines()[:3]:
                    print(f"      {z}")
    if a["zeitleiste"]:
        print("\n## Zeitleiste" + (" (Kalender nicht erreichbar)" if a["termine_fehlen"] else ""))
        for z in a["zeitleiste"]:
            zeit = f" {z['uhrzeit']}" if z.get("uhrzeit") else ""
            print(f"  {z['datum']}{zeit}  {z['art']:<12} {z['titel']}  ({namen.get(z['projekt'], z['projekt'])})")
    if a["kontakte"]:
        print("\n## Kontakte")
        for k in a["kontakte"]:
            name = "geloescht" if k["fehlt"] else (k["name"] or "nicht abrufbar")
            print(f"  - {name}" + (f", {k['rolle']}" if k.get("rolle") else "") + f"  ({k['projekt_name']})")
    b = a["budget"]
    if b["verfuegbar"] and b["gesamt"]:
        g = b["gesamt"]
        print(f"\n## Budget\n  Budget {euro(g['budget_cent'])}, ausgegeben {euro(g['ausgaben_cent'])}, "
              f"Rest {euro(g['rest_cent'])}")
    if a["notizen"]:
        # Nur zaehlen: Notizen sind Inhalte des Owners, auch ihre Titel.
        je_n: dict[str, int] = {}
        for n in a["notizen"]:
            je_n[n["projekt"]] = je_n.get(n["projekt"], 0) + 1
        print("\n## Notizen: " + ", ".join(f"{namen.get(s, s)} {z}" for s, z in je_n.items()))


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    zerleger.add_argument("projekt", nargs="?", help="Slug oder Name (unscharf)")
    zerleger.add_argument("--liste", action="store_true", help="Gliederung aller Projekte")
    args = zerleger.parse_args()
    deck = _deck()
    projekte = deck.projekte()
    if args.liste or not args.projekt:
        gliederung(projekte)
        return 0
    p = finde(projekte, args.projekt)
    akte_zeigen(deck._ruf("GET", f"/api/projects/{p['id']}/akte"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
