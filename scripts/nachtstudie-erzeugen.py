#!/usr/bin/env python3
"""Erzeugt die Nachtstudie als reine CSS-Datei fuer die Hausdienste und bewacht die Kopien.

WARUM ES DIESES SKRIPT GIBT. Die Hausdienste ausserhalb der Suite (fitness,
lager, einkaufsliste, finanzen und die uebrigen) koennen `theme.css` nicht
importieren: sie ist eine Tailwind-v4-Datei mit `@theme`, und die Dienste
bauen mit Tailwind 3, mit Vite ohne Tailwind oder gar nicht. Sie trugen
deshalb abgeschriebene Werte, Wert fuer Wert von Hand, und genau so ist
`design-system` gestorben: eine gewollte Kopie ohne Verteiler, die still
driftet.

Entscheid 2026-11-02: die Hausdienste bekommen eine ERZEUGTE Kopie,
bewacht per Pruefsumme, ohne Laufzeitabhaengigkeit zur Shell. Jeder Dienst
bleibt fuer sich baubar und offline.

QUELLE ist allein `packages/design-tokens/src/theme.css`. Gelesen werden die
Werte `--dunkel-*`, die Messing-Skala `--color-accent-*`, die Bewegungstokens
und die Schriftfamilie. Es gibt nur Dunkel (Entscheid 2026-11-02).

DREI PRUEFUNGEN je Ziel, weil jede eine andere Sorte stilles Scheitern findet:

  vorhanden   liegt die Kopie am erwarteten Ort
  aktuell     ist sie byte-gleich mit dem, was die Quelle heute ergibt
  eingebunden wird sie in der Einstiegsdatei des Dienstes importiert. Eine
              aktuelle Kopie, die niemand laedt, ist der dritte Fall aus der
              Lesson oben (theme.css in sechs Lern-Apps, nie importiert).
              ⚠️ Grenze: geprueft wird der Text, ein auskommentierter Import
              zaehlt also mit. Die Wirkung zeigt erst das gebaute CSS.

Aufruf:
    nachtstudie-erzeugen.py                 # Ausgabe auf stdout, schreibt nichts
    nachtstudie-erzeugen.py --schreiben     # alle Ziele neu schreiben
    nachtstudie-erzeugen.py --pruefen       # Exit 1 bei Abweichung
    nachtstudie-erzeugen.py --selbsttest

Ein neuer Dienst wird unten in ZIELE eingetragen, dann `--schreiben`, dann
in seiner Einstiegsdatei importieren.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "packages/design-tokens/src/theme.css"
DOCKER = WURZEL.parent

#: Ziel: (Kopie, Einstiegsdatei, Muster fuer den Import in der Einstiegsdatei).
#: Das Muster ist ein regulaerer Ausdruck auf den Dateinamen der Kopie, damit
#: `@import './nachtstudie.css'` und `@import "nachtstudie.css"` beide zaehlen.
ZIELE: dict[str, tuple[Path, Path, str]] = {
    "fitness": (
        DOCKER / "fitness/frontend/src/styles/nachtstudie.css",
        DOCKER / "fitness/frontend/src/styles/global.css",
        r"@import\s+['\"](\./)?nachtstudie\.css['\"]",
    ),
    "bibliothek": (
        DOCKER / "bibliothek/static/nachtstudie.css",
        DOCKER / "bibliothek/static/stil.css",
        r"@import\s+url\(['\"]?(\./)?nachtstudie\.css['\"]?\)",
    ),
    "medien": (
        DOCKER / "medien/app/static/nachtstudie.css",
        DOCKER / "medien/app/static/stil.css",
        r"@import\s+url\(['\"]?(\./)?nachtstudie\.css['\"]?\)",
    ),
    "mealprep": (
        DOCKER / "mealprep/app/static/nachtstudie.css",
        DOCKER / "mealprep/app/static/styles.css",
        r"@import\s+url\(['\"]?(\./)?nachtstudie\.css['\"]?\)",
    ),
    "wissen": (
        DOCKER / "wissen/static/nachtstudie.css",
        DOCKER / "wissen/static/style.css",
        r"@import\s+url\(['\"]?(\./)?nachtstudie\.css['\"]?\)",
    ),
    # lager: bis 2026-11-08 standen die Farben von Hand gespiegelt in global.css.
    "lager": (
        DOCKER / "lager/frontend/src/styles/nachtstudie.css",
        DOCKER / "lager/frontend/src/styles/global.css",
        r"@import\s+['\"](\./)?nachtstudie\.css['\"]",
    ),
    "einkaufsliste": (
        DOCKER / "einkaufsliste/frontend/src/nachtstudie.css",
        DOCKER / "einkaufsliste/frontend/src/styles.css",
        r"@import\s+['\"](\./)?nachtstudie\.css['\"]",
    ),
    # karten: nur die Bedienflaechen um die Karte, der Kartenstil bleibt.
    # Die Kopie liegt im host-Klon; ausgerollt wird per git pull auf node1.
    "karten": (
        DOCKER / "karten/static/nachtstudie.css",
        DOCKER / "karten/static/familie.css",
        r"@import\s+url\(['\"]?(\./)?nachtstudie\.css['\"]?\)",
    ),
    # launchpad: Grundtoene und Schrift aus der Nachtstudie, die Wirtsfarben
    # der Kacheln bleiben (sie sind Information, kein Schmuck).
    "launchpad": (
        DOCKER / "launchpad/static/nachtstudie.css",
        DOCKER / "launchpad/static/style.css",
        r"@import\s+url\(['\"]?(\./)?nachtstudie\.css['\"]?\)",
    ),
}

KOPF = """/* ERZEUGT, NICHT VON HAND AENDERN.
 *
 * Quelle: saganta/packages/design-tokens/src/theme.css (Pruefsumme {summe})
 * Werkzeug: saganta/scripts/nachtstudie-erzeugen.py --schreiben
 *
 * Die Nachtstudie fuer Dienste ausserhalb der Saganta-Suite. Nur dunkel
 * (Entscheid 2026-11-02). Jede Farbe gibt es zweimal: als Hexwert zum
 * direkten Gebrauch und als `-rgb`-Dreier fuer Transparenz, also
 * `rgb(var(--saganta-akzent-rgb) / 0.12)`.
 *
 * Wer einen Ton aendern will, aendert ihn in der Quelle und schreibt neu. Eine
 * Aenderung hier meldet der Waechter (`--pruefen`, taeglich) als Abweichung.
 */
"""


def lies_quelle(text: str) -> dict[str, list[tuple[str, str]]]:
    """Zerlegt theme.css in die Gruppen, die die Kopie traegt."""
    farben = re.findall(
        r"--dunkel-([a-z0-9-]+):\s*([0-9]{1,3})\s+([0-9]{1,3})\s+([0-9]{1,3})\s*;", text)
    messing = re.findall(r"--color-accent-(\d+|ink):\s*(#[0-9a-fA-F]{6})\s*;", text)
    bewegung = re.findall(r"--saganta-(ease|motion-[a-z]+):\s*([^;]+);", text)
    schrift = re.search(r"--font-sans:\s*([^;]+);", text)
    if not farben or not messing or not schrift:
        # Ein Leser, der nichts findet, darf keine leere Kopie schreiben: die
        # saehe aus wie eine gueltige und liesse jeden Dienst ungestylt.
        raise ValueError(
            f"Quelle unvollstaendig gelesen: {len(farben)} Farben, "
            f"{len(messing)} Messingstufen, Schrift {'ja' if schrift else 'nein'}")
    return {
        "farben": [(n, f"{int(r)} {int(g)} {int(b)}") for n, r, g, b in farben],
        "messing": [(n, w.lower()) for n, w in messing],
        "bewegung": [(n, w.strip()) for n, w in bewegung],
        "schrift": [("schrift", " ".join(schrift.group(1).split()))],
    }


def hexwert(dreier: str) -> str:
    return "#" + "".join(f"{int(x):02x}" for x in dreier.split())


def erzeuge(text: str) -> str:
    g = lies_quelle(text)
    summe = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    z = [KOPF.format(summe=summe), ":root {", "  color-scheme: dark;", ""]
    z.append("  /* Rollen, Werte aus --dunkel-* */")
    for name, dreier in g["farben"]:
        z.append(f"  --saganta-{name}: {hexwert(dreier)};")
        z.append(f"  --saganta-{name}-rgb: {dreier};")
    z += ["", "  /* Messing-Skala: als FLAECHE gedacht, als Text nur `--saganta-akzent` */"]
    for stufe, wert in g["messing"]:
        name = "auf-messing" if stufe == "ink" else f"messing-{stufe}"
        z.append(f"  --saganta-{name}: {wert};")
    z += ["", "  /* Bewegung */"]
    for name, wert in g["bewegung"]:
        z.append(f"  --saganta-{name}: {wert};")
    z += ["", "  /* Schrift: die Dateien legt jeder Dienst selbst ab (Inter, OFL) */"]
    for _, wert in g["schrift"]:
        z.append(f"  --saganta-schrift: {wert};")
    z += ["}", ""]
    return "\n".join(z)


def pruefe(soll: str) -> list[tuple[str, str, str]]:
    """(Ziel, Stufe, Satz) je Befund; leer heisst alles in Ordnung."""
    funde = []
    for ziel, (kopie, einstieg, muster) in sorted(ZIELE.items()):
        if not kopie.exists():
            funde.append((ziel, "vorhanden", f"{kopie} fehlt"))
            continue
        if kopie.read_text(encoding="utf-8") != soll:
            funde.append((ziel, "aktuell", f"{kopie} weicht von der Quelle ab"))
        if not einstieg.exists():
            funde.append((ziel, "eingebunden", f"Einstiegsdatei {einstieg} fehlt"))
        elif not re.search(muster, einstieg.read_text(encoding="utf-8")):
            funde.append((ziel, "eingebunden",
                          f"{einstieg.name} importiert die Kopie nicht"))
    return funde


def selbsttest() -> int:
    """Findet der Waechter die drei Fehlerklassen, und scheitert der Leser laut?"""
    global ZIELE
    quelle = QUELLE.read_text(encoding="utf-8")
    soll = erzeuge(quelle)
    faelle = []
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        ein = d / "global.css"
        ein.write_text("@import './nachtstudie.css';\n")
        (d / "nachtstudie.css").write_text(soll)
        alt, ZIELE = ZIELE, {"probe": (d / "nachtstudie.css", ein, r"@import\s+['\"](\./)?nachtstudie\.css['\"]")}
        try:
            faelle.append(("saubere Kopie ergibt keinen Fund", pruefe(soll) == []))
            (d / "nachtstudie.css").write_text(soll.replace("--saganta-akzent:", "--saganta-akzent: #000000; --x:"))
            faelle.append(("geaenderte Kopie wird als veraltet erkannt",
                           [f[1] for f in pruefe(soll)] == ["aktuell"]))
            (d / "nachtstudie.css").write_text(soll)
            ein.write_text("body{}\n")
            faelle.append(("fehlender Import wird erkannt",
                           [f[1] for f in pruefe(soll)] == ["eingebunden"]))
            (d / "nachtstudie.css").unlink()
            faelle.append(("fehlende Kopie wird erkannt",
                           [f[1] for f in pruefe(soll)] == ["vorhanden"]))
        finally:
            ZIELE = alt
    try:
        erzeuge("/* leer */")
        laut = False
    except ValueError:
        laut = True
    faelle.append(("leere Quelle scheitert laut statt leere Kopie zu schreiben", laut))
    faelle.append(("Akzent dunkel ist accent-400 (#dd9c3f)", "--saganta-akzent: #dd9c3f;" in soll))
    faelle.append(("kein Hell in der Kopie", "hell" not in soll.split("*/", 1)[1]))
    schlecht = 0
    for name, ok in faelle:
        print(f"{'ok   ' if ok else 'FEHLT'} {name}")
        schlecht += not ok
    print(f"\n{len(faelle) - schlecht}/{len(faelle)} bestanden")
    return 1 if schlecht else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--schreiben", action="store_true")
    p.add_argument("--pruefen", action="store_true")
    p.add_argument("--selbsttest", action="store_true")
    a = p.parse_args()
    if a.selbsttest:
        return selbsttest()
    soll = erzeuge(QUELLE.read_text(encoding="utf-8"))
    if a.schreiben:
        for ziel, (kopie, _, _) in sorted(ZIELE.items()):
            kopie.write_text(soll, encoding="utf-8")
            print(f"geschrieben: {ziel} -> {kopie}")
        return 0
    if a.pruefen:
        funde = pruefe(soll)
        for ziel, stufe, satz in funde:
            print(f"{ziel:14} {stufe:12} {satz}")
        print(f"{len(ZIELE)} Ziel(e) geprueft, {len(funde)} Befund(e)")
        return 1 if funde else 0
    sys.stdout.write(soll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
