#!/usr/bin/env python3
"""Baut die Seiten von saganta.de aus `quelle/` nach `oeffentlich/`.

Warum es einen Generator gibt, obwohl die Seite statisch ist: seit dem
2026-10-30 stellt sie jede App auf einer eigenen Unterseite vor (Entscheid),
das sind rund fuenfzehn Seiten mit demselben Kopf, demselben Fuss und derselben
Navigation. Von Hand gepflegt laeuft das auseinander, und zwar genau in der Art,
gegen die `abgleich.py` gebaut ist: eine Kopie, die niemand nachhaelt.

Was sich dadurch NICHT aendert: auf netcup liegen weiter nur fertige Dateien,
kein Build, kein Node, kein Python. Gebaut wird hier, ausgeliefert wird das
Ergebnis, und das Ergebnis ist eingecheckt. `--pruefen` stellt fest, ob
`oeffentlich/` zum Stand von `quelle/` passt; `abgleich.py` ruft das mit auf,
damit niemand eine Hand-Aenderung an einer erzeugten Datei ausliefert, die der
naechste Lauf wieder ueberschreibt.

Nur Standardbibliothek.

Aufruf:
    python3 bauen.py            # schreibt oeffentlich/*.html
    python3 bauen.py --pruefen  # schreibt nichts, Rueckgabe 1 bei Abweichung
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
QUELLE = HIER / "quelle"
ZIEL = HIER / "oeffentlich"

sys.path.insert(0, str(QUELLE))
import inhalt  # noqa: E402  (liegt in quelle/, nicht im Paketpfad)

MARKE_SVG = """<svg viewBox="0 0 100 100" aria-hidden="true">
            <path
              d="M 69 27 A 19 19 0 1 0 50 46 A 19 19 0 1 1 31 73"
              fill="none"
              stroke="#dd9c3f"
              stroke-width="12.5"
              stroke-linecap="round"
            />
            <circle cx="69" cy="27" r="6" fill="currentColor" />
            <circle cx="31" cy="73" r="6" fill="currentColor" />
          </svg>"""

ABSTAND = ' class="abstand"'
KENNZEICHEN = "<!-- Erzeugt von bauen.py aus quelle/. Nicht von Hand bearbeiten. -->"


def e(text: str) -> str:
    return html.escape(text, quote=True)


def seite(*, datei: str, titel: str, beschreibung: str | None, haupt: str,
          klasse: str = "") -> str:
    """Eine ganze Seite. Titel ohne Zusatz nur auf der Startseite.

    Verweise sind relativ, damit die Seiten auch als Datei im Browser
    stimmen (Vorschau vor dem Ausliefern). Die eine Ausnahme ist `404.html`:
    Caddy liefert sie unter JEDEM unbekannten Pfad aus, auch unter
    `/login/irgendwas`, und dort zeigte `stil.css` relativ auf
    `/login/stil.css`. Die Seite erschien dann ohne Stil, ohne Fehlermeldung.
    """
    w = "/" if datei == "404.html" else ""
    voll = "Saganta" if datei == "index.html" else f"{titel} · Saganta"
    kopf_meta = ""
    if beschreibung:
        kopf_meta = f'\n    <meta name="description" content="{e(beschreibung)}" />'
    og = ""
    if datei == "index.html":
        og = f"""
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Saganta" />
    <meta property="og:title" content="Saganta" />
    <meta property="og:description" content="{e(beschreibung or '')}" />
    <meta property="og:url" content="https://saganta.de/" />"""
    fuss_links = [(d, t) for d, t in (("index.html", "Startseite"),
                                      ("impressum.html", "Impressum"),
                                      ("datenschutz.html", "Datenschutz"))
                  if d != datei]
    fuss = "\n        ".join(
        f'<a{ABSTAND if i == 0 else ""} href="{w}{d}">{t}</a>'
        for i, (d, t) in enumerate(fuss_links)
    )
    body_klasse = f' class="{klasse}"' if klasse else ""
    return f"""<!doctype html>
{KENNZEICHEN}
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{e(voll)}</title>{kopf_meta}
    <link rel="icon" href="{w}saganta.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="{w}stil.css" />{og}
  </head>
  <body{body_klasse}>
    <div class="rahmen">
      <header class="kopf">
        <a class="marke" href="{w}index.html">
          {MARKE_SVG}
          <span>Saganta</span>
        </a>
        <div class="band" aria-hidden="true"></div>
      </header>

      {haupt.strip()}

      <footer>
        <span>Saganta</span>
        {fuss}
      </footer>
    </div>
  </body>
</html>
"""


def bild(app_id: str, alt: str) -> str:
    """Das Bild einer App, wenn es da ist. Fehlt es, meldet `abgleich.py`."""
    datei = f"bilder/{app_id}.webp"
    if not (ZIEL / datei).exists():
        return ""
    return (f'<figure class="bildschirm"><img src="{datei}" alt="{e(alt)}" '
            f'loading="lazy" /></figure>')


def liste(punkte: list[str], klasse: str) -> str:
    zeilen = "\n".join(f"            <li>{p}</li>" for p in punkte)
    return f'<ul class="{klasse}">\n{zeilen}\n          </ul>'


def app_seite(app: dict, nachbarn: tuple[dict | None, dict | None]) -> str:
    teile = [
        f'<p class="ueberzeile"><a href="index.html#apps">Die Apps</a></p>',
        f"<h1>{e(app['name'])}</h1>",
        f'<p class="anriss">{app["satz"]}</p>',
        bild(app["seite"], app["bild_alt"]),
        "<section>",
        "  <h2>Was sie kann</h2>",
        "  " + liste(app["funktionen"], "punkte"),
        "</section>",
    ]
    if app.get("verbindungen"):
        teile += [
            "<section>",
            "  <h2>Wie sie mit den anderen zusammenhängt</h2>",
            "  " + liste(app["verbindungen"], "punkte"),
            "</section>",
        ]
    if app.get("telefon"):
        teile += [f'<p class="leise nachsatz">{app["telefon"]} '
                  f'<a href="telefon.html">Mehr zu den Telefon-Apps</a></p>']
    vor, nach = nachbarn
    blaettern = []
    if vor:
        blaettern.append(f'<a class="zurueck" href="{vor["seite"]}.html">{e(vor["name"])}</a>')
    if nach:
        blaettern.append(f'<a class="weiter" href="{nach["seite"]}.html">{e(nach["name"])}</a>')
    teile.append(f'<nav class="blaettern" aria-label="Weitere Apps">{"".join(blaettern)}</nav>')
    return "<main>\n" + "\n".join(t for t in teile if t) + "\n</main>"


def startseite() -> str:
    kacheln = "\n".join(
        f'''            <li><a href="{a["seite"]}.html"><span class="name">{e(a["name"])}</span><span class="was">{a["kurz"]}</span></a></li>'''
        for a in inhalt.APPS
    )
    return f"""<main>
        <h1>{inhalt.START["titel"]}</h1>
        <p class="anriss">{inhalt.START["anriss"]}</p>
        {bild("uebersicht", inhalt.START["bild_alt"])}

        <section id="apps">
          <h2>Die Apps</h2>
          <ul class="kacheln">
{kacheln}
          </ul>
          <p class="leise nachsatz">{inhalt.START["zusammen"]}</p>
        </section>

        <section>
          <h2>Auf dem Telefon</h2>
          <p>{inhalt.START["telefon"]} <a href="telefon.html">Die Telefon-Apps</a></p>
        </section>

        <section>
          <h2>Woraus es besteht</h2>
          {liste(inhalt.START["technik"], "technik")}
          <p class="leise nachsatz">{inhalt.START["technik_mehr"]}</p>
        </section>

        <section>
          <h2>Kein öffentlicher Zugang</h2>
          <p class="leise">{inhalt.START["privat"]}</p>
        </section>

        <div class="anfrage">
          <h2 class="ohne-abstand">Bei Ihnen einrichten</h2>
          <p>{inhalt.START["anfrage"]}</p>
          <p><a href="einrichtung.html">Wie eine Einrichtung abläuft</a></p>
        </div>
      </main>"""


def fragment(name: str) -> str:
    return (QUELLE / f"{name}.html").read_text(encoding="utf-8")


def alle_seiten() -> dict[str, str]:
    s: dict[str, str] = {}
    s["index.html"] = seite(datei="index.html", titel="Saganta",
                            beschreibung=inhalt.START["beschreibung"],
                            haupt=startseite())
    apps = inhalt.APPS
    for i, app in enumerate(apps):
        vor = apps[i - 1] if i > 0 else None
        nach = apps[i + 1] if i + 1 < len(apps) else None
        s[f"{app['seite']}.html"] = seite(
            datei=f"{app['seite']}.html", titel=app["name"],
            beschreibung=app["beschreibung"], haupt=app_seite(app, (vor, nach)))
    for name, titel, beschreibung, klasse in inhalt.FRAGMENTE:
        s[f"{name}.html"] = seite(datei=f"{name}.html", titel=titel,
                                  beschreibung=beschreibung, haupt=fragment(name),
                                  klasse=klasse)
    return s


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pruefen", action="store_true")
    args = p.parse_args()

    seiten = alle_seiten()
    abweichend = []
    for datei, text in seiten.items():
        ziel = ZIEL / datei
        if not ziel.exists() or ziel.read_text(encoding="utf-8") != text:
            abweichend.append(datei)
            if not args.pruefen:
                ziel.write_text(text, encoding="utf-8")

    # Erzeugte Seiten, die keine Quelle mehr haben (eine umbenannte App): sie
    # blieben sonst liegen und wuerden mit ausgeliefert.
    verwaist = sorted(
        d.name for d in ZIEL.glob("*.html")
        if d.name not in seiten and KENNZEICHEN in d.read_text(encoding="utf-8")
    )

    if args.pruefen:
        for d in abweichend:
            print(f"weicht von quelle/ ab: {d}")
        for d in verwaist:
            print(f"erzeugt, aber ohne Quelle: {d}")
        return 1 if abweichend or verwaist else 0

    for d in verwaist:
        (ZIEL / d).unlink()
        print(f"entfernt (ohne Quelle): {d}")
    print(f"{len(seiten)} Seiten, davon {len(abweichend)} neu geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
