#!/usr/bin/env python3
"""Sichtprobe fuer die Hausdienste: Oberflaeche von der Platte, Daten erfunden, gemessen in Chromium.

WARUM. Die Hausdienste (wissen, launchpad, bibliothek, finanzen, medien,
mealprep, fitness, lager, einkaufsliste) liegen ausserhalb der SvelteKit-Suite
und hatten bis 2026-11-08 keine gemeinsame Pruefung fuer Handy, Schrift und
Tippflaechen. Gegen den echten Dienst darf nicht fotografiert werden
, also laeuft hier kein
Dienst: Chromium bekommt jede Anfrage aus dem Handler dieser Probe beantwortet,
statische Dateien aus dem Repo, `/api/...` aus `daten/<dienst>.py`. Es gibt
keinen Server, keinen Port, keinen Weg zum echten Bestand.

GEMESSEN je Seite und Breite (Handy 390 px mit Beruehrung, Schreibtisch 1280 px):
  * Skriptfehler und unbediente Anfragen (sonst misst die Probe eine leere
    Seite und meldet „ok").
  * waagerechter Ueberlauf der Seite
  * Text unter 12 px
  * Tippflaechen unter 44 px (nur Handy; Links im Fliesstext zaehlen nicht)
  * Bedienelemente ohne zugaenglichen Namen
  * Textkontrast unter 4.5:1 (3:1 ab 18,66 px fett bzw. 24 px)
Ausgegeben werden nur Zahlen und Element-Kennungen (tag.klasse), nie Text.

Aufruf (Playwright aus dem medien-venv, Chromium aus dem Playwright-Cache):
  ~/docker/medien/.venv/bin/python probe.py <dienst> [--bilder DIR] [--seite NAME] [--alle-befunde]
  ~/docker/medien/.venv/bin/python probe.py --alle
Exit 1, wenn eine Seite einen Skriptfehler hat oder unbediente Anfragen offen sind.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright

HIER = Path(__file__).resolve().parent
BASIS = "http://localhost:18471"
BREITEN = {"handy": (390, 844, True), "pc": (1280, 860, False)}
DIENSTE = ["wissen", "launchpad", "bibliothek", "finanzen", "medien",
           "mealprep", "fitness", "lager", "einkaufsliste"]

MESSEN = Path(HIER / "messen.js").read_text()


def chromium_finden() -> str | None:
    kandidaten = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux*/chrome"))
    return str(kandidaten[-1]) if kandidaten else None


def daten_laden(dienst: str):
    spec = importlib.util.spec_from_file_location(f"daten_{dienst}", HIER / "daten" / f"{dienst}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class Antwort:
    def __init__(self, status=200, body=b"", typ="application/json", kopf=None):
        self.status, self.body, self.typ, self.kopf = status, body, typ, kopf or {}


def als_antwort(wert) -> Antwort:
    # Duck-Typing: die Datenmodule importieren `probe` ein zweites Mal (nicht als __main__).
    if hasattr(wert, "typ") and hasattr(wert, "body"):
        return wert
    if isinstance(wert, (bytes, str)):
        body = wert.encode() if isinstance(wert, str) else wert
        return Antwort(200, body, "text/html; charset=utf-8")
    return Antwort(200, json.dumps(wert).encode(), "application/json")


def statisch(wurzeln: list[tuple[str, Path]], pfad: str) -> Antwort | None:
    for praefix, ordner in wurzeln:
        if not pfad.startswith(praefix):
            continue
        rest = pfad[len(praefix):].lstrip("/") or "index.html"
        datei = (ordner / rest).resolve()
        if datei.is_dir():
            datei = datei / "index.html"
        if ordner.resolve() in datei.parents and datei.is_file():
            typ = mimetypes.guess_type(datei.name)[0] or "application/octet-stream"
            if datei.suffix in (".js", ".mjs"):
                typ = "text/javascript"
            return Antwort(200, datei.read_bytes(), typ)
    return None


def seite_messen(browser, modul, seite_def, breite, bilder: Path | None, dienst: str):
    name, pfad = seite_def["name"], seite_def["pfad"]
    w, h, tasten = BREITEN[breite]
    kontext = browser.new_context(viewport={"width": w, "height": h}, has_touch=tasten,
                                  is_mobile=tasten, device_scale_factor=1,
                                  service_workers="block", locale="de-DE",
                                  color_scheme=getattr(modul, "FARBSCHEMA", "dark"))
    unbedient, fehler = [], []

    def bedienen(route, anfrage):
        teile = urlsplit(anfrage.url)
        if not anfrage.url.startswith(BASIS):
            unbedient.append(f"extern {teile.netloc}{teile.path}")
            return route.abort()
        query = {k: v[-1] for k, v in parse_qs(teile.query).items()}
        try:
            body = anfrage.post_data_json if anfrage.post_data else None
        except Exception:
            body = anfrage.post_data
        wert = modul.api(anfrage.method, teile.path, query, body)
        if wert is None:
            wert = statisch(modul.WURZELN, teile.path)
        if wert is None:
            unbedient.append(f"{anfrage.method} {teile.path}")
            return route.fulfill(status=404, body="{}", content_type="application/json")
        a = als_antwort(wert)
        route.fulfill(status=a.status, body=a.body, content_type=a.typ, headers=a.kopf or None)

    kontext.route("**/*", bedienen)
    seite = kontext.new_page()
    seite.on("pageerror", lambda e: fehler.append(str(e).splitlines()[0][:160]))
    seite.on("console", lambda m: fehler.append("console: " + m.text[:160]) if m.type == "error" else None)
    seite.goto(BASIS + pfad, wait_until="networkidle")
    for schritt in seite_def.get("schritte", []):
        schritt(seite)
        seite.wait_for_timeout(250)
    seite.wait_for_timeout(seite_def.get("warten", 400))
    befund = seite.evaluate(MESSEN, {"tippen": tasten, "wurzel": seite_def.get("wurzel")})
    if bilder:
        ziel = bilder / dienst
        ziel.mkdir(parents=True, exist_ok=True)
        seite.screenshot(path=str(ziel / f"{name}-{breite}.png"), full_page=True)
    kontext.close()
    befund["fehler"] = fehler
    befund["unbedient"] = sorted(set(unbedient))
    return befund


def ausgeben(dienst, name, breite, b, alle):
    n = 6 if not alle else 999
    kopf = (f"{dienst:13} {name:16} {breite:5} ueberlauf={b['ueberlauf']:<4} "
            f"klein={len(b['klein']):<3} tippen={len(b['tippen']):<3} "
            f"namenlos={len(b['namenlos']):<3} kontrast={len(b['kontrast']):<3} "
            f"elemente={b['sichtbar']}")
    print(kopf)
    for art in ("fehler", "unbedient", "namenlos", "kontrast", "klein", "tippen", "breit"):
        eintraege = b.get(art) or []
        if eintraege:
            zaehl = {}
            for e in eintraege:
                zaehl[e] = zaehl.get(e, 0) + 1
            zeilen = sorted(zaehl.items(), key=lambda x: -x[1])[:n]
            print(f"    {art}: " + " | ".join(f"{k} x{v}" if v > 1 else k for k, v in zeilen))


def dienst_pruefen(browser, dienst, bilder, nur_seite, alle) -> bool:
    modul = daten_laden(dienst)
    gut = True
    for seite_def in modul.SEITEN:
        if nur_seite and seite_def["name"] != nur_seite:
            continue
        for breite in BREITEN:
            b = seite_messen(browser, modul, seite_def, breite, bilder, dienst)
            ausgeben(dienst, seite_def["name"], breite, b, alle)
            # `fehler_erwartet`: Seiten, die einen Ausfall absichtlich nachstellen
            # (503 vom Dienst), melden den Fehler in der Konsole und sind trotzdem gut.
            fehler = [] if seite_def.get("fehler_erwartet") else b["fehler"]
            if fehler or b["unbedient"] or b["sichtbar"] < 3:
                gut = False
    return gut


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dienst", nargs="?")
    ap.add_argument("--alle", action="store_true")
    ap.add_argument("--bilder", type=Path)
    ap.add_argument("--seite")
    ap.add_argument("--alle-befunde", action="store_true")
    a = ap.parse_args()
    dienste = DIENSTE if a.alle else [a.dienst]
    if not dienste[0]:
        ap.error("Dienst oder --alle angeben")
    gut = True
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_finden())
        for d in dienste:
            if not (HIER / "daten" / f"{d}.py").exists():
                print(f"{d:13} (noch keine Daten)")
                continue
            gut &= dienst_pruefen(browser, d, a.bilder, a.seite, a.alle_befunde)
        browser.close()
    return 0 if gut else 1


if __name__ == "__main__":
    sys.exit(main())
