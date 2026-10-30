#!/usr/bin/env python3
"""Prueft, dass jeder Reiter einen Inhaltszweig hat und jeder Zweig erreichbar ist.

WARUM ES DIESE PROBE GIBT. Die Projektansicht im ProjectDeck hat zehn Reiter,
und ihr Inhalt haengt an einer `{:else if tab === '<kennung>'}`-Kette. Faellt
eine Kennung aus der Kette heraus oder wird sie umbenannt, ohne den Zweig
mitzuziehen, dann passiert Folgendes: der Reiter bleibt sichtbar, bleibt
anklickbar, und zeigt NICHTS. Svelte faellt durch die Kette und rendert leer.
Kein Fehler, keine Konsolenmeldung, kein Build-Abbruch.

Der Anlass ist die Eindeutschung vom 2026-10-24. Vorher war der englische
ANZEIGETEXT zugleich der Zustandswert ('Public Readiness' stand im Array und in
`tab === 'Public Readiness'`). Jede Sprachaenderung musste also elf Vergleiche
treffen. Seit dem Umbau sind Kennung und Anzeigetext getrennt, womit der
Anzeigetext frei aenderbar ist; die Kette haengt jetzt an den Kennungen, und
genau deren Deckung prueft diese Datei.

Geprueft wird am Quelltext und nicht im Browser, weil der Fehler im Browser
wie eine leere Seite aussieht und nicht wie ein Fehler. Eine Sichtpruefung
muesste jeden Reiter einzeln anklicken, um ihn auszuschliessen.

Kommentarzeilen zaehlen NICHT mit. Der Kommentar an der Reiter-Liste nennt
`tab === 'Public Readiness'` als Beispiel fuer den alten Zustand; wer ihn
mitzaehlt, meldet eine unerreichbare Kennung, die es nicht gibt.

Aufruf:  scripts/reiter-probe.py [--selbsttest]
Ende:    rc=0 alles gedeckt, rc=1 Luecke, rc=2 nichts gefunden (auch kein Bestehen)
"""
import pathlib
import re
import sys

ZIEL = "apps/projectdeck/src/routes/projekte/[slug]/+page.svelte"


def lies(text):
    """Gibt (kennungen, labels, zweige, startwert) zurueck."""
    paare = re.findall(r"\{\s*id:\s*'([a-z-]+)'\s*,\s*label:\s*'([^']+)'\s*\}", text)
    kennungen = [k for k, _ in paare]
    labels = [l for _, l in paare]
    zweige = []
    for zeile in text.split("\n"):
        if zeile.lstrip().startswith("//"):
            continue
        zweige += re.findall(r"tab === '([a-z-]+)'", zeile)
    m = re.search(r"let tab = \$state\('([a-z-]+)'\)", text)
    return kennungen, labels, zweige, (m.group(1) if m else None)


def pruefe(text, name=ZIEL):
    kennungen, labels, zweige, start = lies(text)
    funde = []
    if len(kennungen) < 2:
        return [f"{name}: nur {len(kennungen)} Reiter erkannt. Entweder hat die "
                f"Leiste ihre Form geaendert oder dieses Muster passt nicht mehr. "
                f"Ein stilles 'keine Funde' waere hier eine falsche Entwarnung."], None

    for k in kennungen:
        if k not in zweige:
            funde.append(f"{name}: Reiter '{k}' hat KEINEN Inhaltszweig. Er ist "
                         f"sichtbar und anklickbar und zeigt nichts.")
    for z in set(zweige):
        if z not in kennungen:
            funde.append(f"{name}: Zweig '{z}' gehoert zu keinem Reiter, ist also "
                         f"unerreichbar. Toter Code oder vertippte Kennung.")
    if start is None:
        funde.append(f"{name}: Startwert von `tab` nicht gefunden.")
    elif start not in kennungen:
        funde.append(f"{name}: Startwert '{start}' ist kein Reiter. Die Seite "
                     f"oeffnet damit auf einer leeren Flaeche.")

    # Anzeigetexte: doppelte Beschriftung ist fuer den Benutzer nicht
    # unterscheidbar, auch wenn die Kennungen verschieden sind.
    doppelt = {l for l in labels if labels.count(l) > 1}
    for l in sorted(doppelt):
        funde.append(f"{name}: Beschriftung '{l}' kommt mehrfach vor.")
    return funde, len(kennungen)


def selbsttest():
    """Belegt, dass die Probe anschlaegt. Vier Faelle, drei muessen finden."""
    gut = """
      const TABS = [
        { id: 'a', label: 'Eins' },
        { id: 'b', label: 'Zwei' },
      ];
      let tab = $state('a');
      {#if tab === 'a'}x{:else if tab === 'b'}y{/if}
    """
    faelle = [
        ("heiler Stand schweigt", gut, 0),
        ("Reiter ohne Zweig wird gefunden",
         gut.replace("{:else if tab === 'b'}y", ""), 1),
        ("unerreichbarer Zweig wird gefunden",
         gut.replace("{ id: 'b', label: 'Zwei' },", ""), 1),
        ("falscher Startwert wird gefunden",
         gut.replace("$state('a')", "$state('c')"), 1),
        ("doppelte Beschriftung wird gefunden",
         gut.replace("label: 'Zwei'", "label: 'Eins'"), 1),
        # Der wichtigste Fall: ein Kommentar darf keinen Zweig vortaeuschen
        # und keine unerreichbare Kennung melden.
        ("Kommentar zaehlt nicht mit",
         gut.replace("let tab =", "// tab === 'alt-englisch'\n      let tab ="), 0),
    ]
    schlecht = 0
    for name, text, soll in faelle:
        funde, _ = pruefe(text, "probe")
        ok = (len(funde) >= 1) if soll else (len(funde) == 0)
        print(f"{'ok   ' if ok else 'FEHLT'} {name}")
        if not ok:
            schlecht += 1
            for f in funde:
                print(f"        {f}")
    print(f"\n{len(faelle) - schlecht}/{len(faelle)} bestanden")
    return 1 if schlecht else 0


def main():
    if "--selbsttest" in sys.argv:
        return selbsttest()
    wurzel = pathlib.Path(__file__).resolve().parent.parent
    datei = wurzel / ZIEL
    if not datei.exists():
        print(f"FEHLER: {ZIEL} gibt es nicht. Wurde die Ansicht verschoben? "
              f"Eine Probe, die ihr Ziel nicht findet, darf nicht bestehen.",
              file=sys.stderr)
        return 2
    funde, anzahl = pruefe(datei.read_text(encoding="utf-8"))
    if funde:
        for f in funde:
            print(f"- {f}")
        print(f"\nDurchgefallen: {len(funde)} Fund(e).")
        return 1
    print(f"Bestanden: alle {anzahl} Reiter haben einen Inhaltszweig, "
          f"kein Zweig ist unerreichbar, der Startwert trifft einen Reiter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
