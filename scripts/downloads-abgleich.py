#!/usr/bin/env python3
"""Downloads-Volume gegen die Seite ``/apps``: wird jedes Artefakt gezeigt?

**Warum es dieses Skript gibt.** Die Download-Seite hatte denselben Fehler
zweimal, mit Jahren Abstand und beide Male wortlos:

* Die Kalender-APK lag ab dem 19.07.2026 ausgeliefert im Volume und stand in
  ``catalog.ts`` bis August auf ``'soon'`` -- gehostet und unsichtbar.
* Am 25.10.2026 fehlten ``aufgaben``, ``tagebuch`` und ``assets`` ganz, weil die
  Kartenliste von Hand neben ``packages/ui/src/apps.ts`` gefuehrt wurde.

Beide Male sah die Seite vollstaendig aus. Die Liste kommt seither aus dem
App-Katalog und die Knoepfe aus dem Volume, womit die naheliegenden Fehler weg
sind. Es bleibt **eine** Stelle, an der ein Artefakt still verschwinden kann:
ein Manifest, dessen ``app`` zu keiner Karte passt. Genau das misst dieses
Skript -- nicht „passt das Muster", sondern umgekehrt „bleibt eine Datei
uebrig, die keine Karte findet".

Die eine echte Abweichung ist der Kalender: im Katalog heisst er ``calendar``
(nach dem Heim-Vhost), das Artefakt heisst ``kalender`` (nach dem Gradle-Modul).
Die Zuordnung dafuer steht in ``apps/shell/src/lib/catalog.ts`` und wird hier
**gelesen**, nicht abgeschrieben: eine zweite Kopie waere die naechste Liste,
die veraltet.

    python3 scripts/downloads-abgleich.py              # Abgleich, Exit 1 bei Befund
    python3 scripts/downloads-abgleich.py --sha        # zusaetzlich Pruefsummen
    python3 scripts/downloads-abgleich.py --selbsttest # findet es einen Fehler?
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tarfile
import tempfile
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CATALOG_TS = WURZEL / "apps/shell/src/lib/catalog.ts"
VOLUME = Path(os.environ.get("DOWNLOADS_DIR", WURZEL / "downloads"))

#: Plattformen, fuer die die Seite einen Knopf aus einem Artefakt baut. Muss zu
#: ``artefaktPlattformen`` in catalog.ts passen; steht hier, weil eine fehlende
#: Plattform hier nur eine fehlende Pruefung ist und nichts kaputt macht.
PLATTFORMEN = ("android", "linux")

#: Suffixe, die der Auslieferungs-Endpunkt herausgibt (``downloads/[file]``).
ARTEFAKT_SUFFIXE = (".apk", ".pkg.tar.zst")

#: Name des pacman-Repos im Volume. Muss zu ``REPO_NAME`` in
#: ``saganta-apps/packaging/arch/repo.sh`` passen.
REPO_NAME = "saganta"

#: Das Laufzeitpaket ist **keine App** und hat deshalb weder Karte noch
#: Manifest. Es wird trotzdem ausgeliefert, weil die vier Programme es als
#: Abhaengigkeit verlangen.
#:
#: Seit 2026-10-25, und die Zeile ist der Grund, warum dieses Skript
#: mitwachsen musste: ohne sie meldet es die Laufzeit als „liegt im Volume,
#: aber kein Manifest zeigt darauf". Ein Dauerbefund, der bei jedem Lauf
#: erscheint, ist schlimmer als keiner -- nach dem dritten Mal liest ihn
#: niemand mehr, und der echte Befund daneben verschwindet darin mit.
RUNTIME_PAKET = "saganta-runtime.pkg.tar.zst"

#: Wohin der Herzschlag geht. ⚠️ Der Pfad ist im Haus NICHT einheitlich: auf
#: host und jetson ``textfile_collector``, auf allen uebrigen Wirten
#: ``/var/lib/prometheus/node-exporter``. Dieses Skript laeuft auf host.
TEXTFILE = os.environ.get(
    "DOWNLOADS_ABGLEICH_TEXTFILE",
    "/var/lib/node_exporter/textfile_collector/downloads-abgleich.prom",
)


def katalog_ids() -> set[str]:
    """Die App-Kennungen aus ``packages/ui/src/apps.ts``.

    Der Leser dafuer steht schon in ``app-katalog-abgleich.py`` und wird von
    dort geholt statt ein zweites Mal geschrieben. Der Dateiname enthaelt
    Bindestriche, ein normales ``import`` geht deshalb nicht.
    """
    pfad = WURZEL / "scripts/app-katalog-abgleich.py"
    spec = importlib.util.spec_from_file_location("katalog_leser", pfad)
    if spec is None or spec.loader is None:
        raise SystemExit(f"FEHLER: {pfad} nicht ladbar")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return set(modul.aus_typescript())


def release_namen() -> dict[str, str]:
    """``RELEASE_NAME`` aus catalog.ts: Katalog-Kennung -> Artefakt-Name."""
    text = CATALOG_TS.read_text(encoding="utf-8")
    m = re.search(r"const RELEASE_NAME:\s*Record<string, string>\s*=\s*\{([^}]*)\}", text)
    if not m:
        raise SystemExit(f"FEHLER: RELEASE_NAME nicht in {CATALOG_TS} gefunden")
    paare = re.findall(r"(\w+)\s*:\s*'([^']+)'", m.group(1))
    return dict(paare)


def erwartete_namen() -> dict[str, str]:
    """Artefakt-Name -> Katalog-Kennung, fuer alle Apps ausser der Shell."""
    abweichend = release_namen()
    namen: dict[str, str] = {}
    for app_id in katalog_ids():
        if app_id == "shell":
            continue  # die Uebersicht ist die Seite selbst, kein Download
        namen[abweichend.get(app_id, app_id)] = app_id
    return namen


def manifeste(volume: Path) -> list[tuple[Path, dict]]:
    gefunden = []
    for datei in sorted(volume.glob("*.json")):
        try:
            gefunden.append((datei, json.loads(datei.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as fehler:
            gefunden.append((datei, {"__fehler": str(fehler)}))
    return gefunden


def artefakt_datei(manifest: dict) -> str | None:
    """Der Dateiname, den die Seite verlinkt.

    Android verlinkt den festen Namen (``saganta-<app>.apk``), nicht die
    versionierte Kopie aus ``apkUrl`` -- die gehoert dem Updater. Linux nennt
    seine Datei im Feld ``datei``.
    """
    plattform = manifest.get("platform", "android")
    if plattform == "android":
        return f"saganta-{manifest.get('app')}.apk"
    return manifest.get("datei")


def sha256_von(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def repo_befunde(volume: Path) -> list[str]:
    """Ist das pacman-Repo aus Sicht von ``pacman`` brauchbar?

    Zwei Arten, auf die ein Linux-Paket unsichtbar wird, und beide sehen im
    Verzeichnis nach Vollstaendigkeit aus:

    * **ohne Signatur** -- der Einbauweg traegt ``SigLevel = Required``, pacman
      lehnt ein unsigniertes Paket also ab. Die Datei liegt da, ist richtig,
      hat die richtige Groesse, und niemand kann sie installieren.
    * **nicht in der Datenbank** -- ``repo-add`` erfasst nur, was man ihm
      nennt. Ein Paket, das beim letzten Lauf nicht dabei war, ist ueber
      ``pacman -S`` schlicht nicht vorhanden.

    Dieselbe Fehlerklasse wie die Manifeste oben, nur eine Schicht tiefer:
    gefragt wird nicht „ist die Datei da", sondern „findet der Abnehmer sie".

    Liegt noch gar keine Datenbank im Volume, ist das **kein** Befund: dann
    gibt es das Repo noch nicht, und die Pakete werden von Hand eingebaut.
    """
    befunde: list[str] = []
    db = volume / f"{REPO_NAME}.db"
    pakete = sorted(p for p in volume.glob("*.pkg.tar.zst"))
    if not db.is_file():
        return befunde

    for paket in pakete:
        if not (volume / f"{paket.name}.sig").is_file():
            befunde.append(
                f"{paket.name}: ohne Signatur -- mit 'SigLevel = Required' "
                f"lehnt pacman es ab. 'bash repo.sh' laufen lassen."
            )

    # Die Datenbank ist ein tar.gz mit einem Verzeichnis je Paket, benannt
    # <name>-<version>. Der Verzeichnisname genuegt fuer den Abgleich.
    try:
        with tarfile.open(db) as t:
            eintraege = {n.rstrip("/") for n in t.getnames() if "/" not in n.rstrip("/")}
    except (OSError, tarfile.TarError) as fehler:
        return befunde + [f"{db.name}: nicht lesbar ({fehler})"]

    if len(eintraege) != len(pakete):
        befunde.append(
            f"{db.name}: {len(eintraege)} Eintraege, aber {len(pakete)} Pakete "
            f"im Volume -- was fehlt, ist ueber 'pacman -S' unsichtbar"
        )
    return befunde


def abgleich(volume: Path, mit_sha: bool, still: bool = False) -> list[str]:
    """Befunde als Liste. Leer heisst: jedes Artefakt ist auf der Seite."""
    befunde: list[str] = []
    if not volume.is_dir():
        return [f"Downloads-Verzeichnis fehlt: {volume}"]

    erwartet = erwartete_namen()
    gesehen: set[str] = set()
    zeilen: list[str] = []

    for datei, manifest in manifeste(volume):
        if "__fehler" in manifest:
            befunde.append(f"{datei.name}: nicht lesbar ({manifest['__fehler']})")
            continue
        app = manifest.get("app")
        plattform = manifest.get("platform", "android")
        if not app or not manifest.get("versionName"):
            befunde.append(f"{datei.name}: ohne 'app' oder 'versionName', die Seite ueberspringt es")
            continue
        if app not in erwartet:
            befunde.append(
                f"{datei.name}: 'app: {app}' passt zu keiner Karte -- "
                f"das Artefakt ist auf /apps unsichtbar. "
                f"Entweder Name falsch oder RELEASE_NAME in catalog.ts ergaenzen."
            )
            continue
        if plattform not in PLATTFORMEN:
            befunde.append(
                f"{datei.name}: Plattform '{plattform}' baut keinen Knopf "
                f"(gezeigt werden {', '.join(PLATTFORMEN)})"
            )
            continue

        name = artefakt_datei(manifest)
        if not name:
            befunde.append(f"{datei.name}: nennt keine Datei ('datei' fehlt)")
            continue
        pfad = volume / name
        if not pfad.is_file():
            befunde.append(f"{datei.name}: verweist auf {name}, die Datei fehlt -- Knopf fuehrt in einen 404")
            continue
        gesehen.add(name)
        groesse = pfad.stat().st_size
        if manifest.get("size") != groesse:
            befunde.append(
                f"{datei.name}: Groesse {manifest.get('size')} im Manifest, "
                f"{groesse} auf der Platte -- Manifest und Datei gehoeren nicht zusammen"
            )
        if mit_sha:
            ist = sha256_von(pfad)
            if manifest.get("sha256") != ist:
                befunde.append(f"{datei.name}: sha256 weicht ab (Manifest {manifest.get('sha256')}, Datei {ist})")
        zeilen.append(f"  {erwartet[app]:<12} {plattform:<8} {manifest['versionName']:<10} {name}")

    # Die Gegenrichtung: ein Artefakt ohne Manifest ist ebenso unsichtbar, nur
    # faellt es noch weniger auf -- die Datei liegt da und niemand verlinkt sie.
    # Versionierte APK-Kopien gehoeren dem Updater und zaehlen nicht mit.
    for datei in sorted(volume.iterdir()):
        if not datei.is_file() or datei.name in gesehen:
            continue
        if not datei.name.endswith(ARTEFAKT_SUFFIXE):
            continue
        if re.fullmatch(r"saganta-[a-z]+-\d+\.apk", datei.name):
            continue  # versionierte Kopie fuer den In-App-Updater
        if datei.name == RUNTIME_PAKET:
            continue  # kein App-Artefakt, siehe oben
        befunde.append(f"{datei.name}: liegt im Volume, aber kein Manifest zeigt darauf")

    befunde.extend(repo_befunde(volume))

    if not still:
        apps_ohne = sorted(
            set(erwartet.values())
            - {z.split()[0] for z in zeilen}
        )
        print(f"Volume: {volume}")
        print("Ausgeliefert und auf /apps sichtbar:")
        print("\n".join(zeilen) if zeilen else "  (nichts)")
        if apps_ohne:
            print(f"Ohne jedes Artefakt ({len(apps_ohne)}): {', '.join(apps_ohne)}")
    return befunde


def selbsttest() -> int:
    """Findet der Abgleich einen eingebauten Fehler?

    Ohne diese Probe ist ein leerer Befund nicht von einem Abgleich zu
    unterscheiden, der gar nichts prueft.
    """
    with tempfile.TemporaryDirectory() as tmp:
        volume = Path(tmp)
        # 1. Manifest mit unbekanntem App-Namen (der eigentliche Zweck).
        (volume / "fremd.json").write_text(
            json.dumps({"app": "gibtsnicht", "versionName": "1.0", "sha256": "x", "size": 1})
        )
        # 2. Manifest, dessen Datei fehlt.
        (volume / "notizen-linux.json").write_text(
            json.dumps(
                {
                    "app": "notizen",
                    "platform": "linux",
                    "versionName": "0.1.0-1",
                    "datei": "saganta-notizen-linux.pkg.tar.zst",
                    "sha256": "x",
                    "size": 1,
                }
            )
        )
        # 3. Artefakt ohne Manifest.
        (volume / "saganta-post.apk").write_bytes(b"x")
        # 4. Ein pacman-Repo, in dem ein Paket weder signiert noch in der
        #    Datenbank steht. Beides macht es unsichtbar, ohne dass man es dem
        #    Verzeichnis ansieht.
        #
        #    ⚠️ Bewusst NICHT `saganta-notizen-linux…`: dessen Manifest steht
        #    in Fall 2 und prueft gerade, dass die Datei FEHLT. Die beiden
        #    Faelle heben sich sonst gegenseitig auf, und der Selbsttest meldet
        #    einen Fehler, den es nicht gibt.
        (volume / "saganta-fitness-linux.pkg.tar.zst").write_bytes(b"x")
        with tarfile.open(volume / f"{REPO_NAME}.db", "w:gz"):
            pass  # eine leere Datenbank: null Eintraege gegen ein Paket

        befunde = abgleich(volume, mit_sha=False, still=True)
        erwartete_stichworte = [
            "keiner Karte",
            "die Datei fehlt",
            "kein Manifest zeigt darauf",
            "ohne Signatur",
            "unsichtbar",
        ]
        fehlend = [s for s in erwartete_stichworte if not any(s in b for b in befunde)]
        for b in befunde:
            print(f"  gefunden: {b}")
        if fehlend:
            print(f"SELBSTTEST FEHLGESCHLAGEN: nicht erkannt: {fehlend}")
            return 1
        print(f"Selbsttest ok: alle {len(erwartete_stichworte)} eingebauten Fehler erkannt.")
        return 0


def herzschlag(befunde: list[str], start: float) -> None:
    """Den Lauf nach Prometheus melden.

    Ohne diese Zeilen ist ein Pruefer, der nicht mehr laeuft, von einem
    Pruefer ohne Befund nicht zu unterscheiden. Beide schweigen. Das Register
    in interne Notiz fuehrt dafuer das
    **Soll**: dort steht, dass es diesen Waechter geben muss, und daraus kommt
    die Alarmierung, ohne dass hier eine eigene Regel noetig waere.

    ⚠️ Keine Dateinamen und keine App-Namen in den Metriken. Die Zahl der
    Befunde genuegt, um zu wissen, dass man nachsehen muss; was es ist, steht
    im Journal.
    """
    ordner = os.path.dirname(TEXTFILE)
    if not os.path.isdir(ordner):
        print(f"(kein Collector-Ordner {ordner}, kein Herzschlag geschrieben)")
        return
    zeilen = [
        "# HELP homelab_downloads_abgleich_lauf_zeitstempel Unix-Zeit des letzten Laufs",
        "# TYPE homelab_downloads_abgleich_lauf_zeitstempel gauge",
        f"homelab_downloads_abgleich_lauf_zeitstempel {int(time.time())}",
        "# HELP homelab_downloads_abgleich_lauf_dauer_sekunden Laufzeit",
        "# TYPE homelab_downloads_abgleich_lauf_dauer_sekunden gauge",
        f"homelab_downloads_abgleich_lauf_dauer_sekunden {round(time.time() - start, 2)}",
        "# HELP homelab_downloads_abgleich_befunde Zahl der Artefakte, die niemand erreicht",
        "# TYPE homelab_downloads_abgleich_befunde gauge",
        f"homelab_downloads_abgleich_befunde {len(befunde)}",
    ]
    tmp = TEXTFILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(zeilen) + "\n")
        os.replace(tmp, TEXTFILE)
    except OSError as fehler:
        print(f"(Herzschlag nicht schreibbar: {fehler})")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sha", action="store_true", help="Pruefsummen mitrechnen (bei Linux-Paketen je ~100 MB)")
    p.add_argument("--selbsttest", action="store_true", help="eingebaute Fehler, muessen alle gefunden werden")
    p.add_argument("--volume", type=Path, default=VOLUME, help=f"Downloads-Verzeichnis (Vorgabe {VOLUME})")
    p.add_argument("--herzschlag", action="store_true",
                   help="Lauf nach Prometheus melden (fuer den Timer)")
    a = p.parse_args()

    if a.selbsttest:
        return selbsttest()

    start = time.time()
    befunde = abgleich(a.volume, a.sha)
    if a.herzschlag:
        herzschlag(befunde, start)
    if befunde:
        print(f"\n{len(befunde)} Befund(e):")
        for b in befunde:
            print(f"  - {b}")
        return 1
    print("\nKein Befund: jedes Manifest findet seine Karte und seine Datei.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
