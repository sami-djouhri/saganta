#!/usr/bin/env python3
"""Erzeugt den Saganta-Kopf als Web-Component fuer die Hausdienste und bewacht die Kopien.

WARUM ES DIESES SKRIPT GIBT. Die Hausdienste ausserhalb der SvelteKit-Suite
(fitness, lager, einkaufsliste, finanzen) trugen bis 2026-11-02 je einen
Nachbau von `packages/ui/src/components/TopBar.svelte`: drei in React, einer
in reinem HTML, jeder mit eigener Abschrift von Signatur und Sinnbild und
alle ohne App-Wechsler (nur ein Knopf auf die Download-Liste `/apps`). Ein
neues Strichmuster im Katalog erreichte keinen davon, und es gab keinen Weg,
das zu bemerken.

Jetzt gibt es EINE erzeugte Datei `saganta-kopf.js`: ein Custom Element ohne
Abhaengigkeiten, das in React wie in reinem HTML laeuft:

    <saganta-kopf app="lager"></saganta-kopf>
    <saganta-kopf app="finanzen"><span slot="aktionen">...</span></saganta-kopf>

QUELLEN, beide gelesen und nichts davon abgeschrieben:
    packages/ui/src/apps.ts               Name, Sinnbild, Signatur, Adressen
    packages/ui/src/components/Icon.svelte Lucide-Pfade der Sinnbilder
    packages/design-tokens/src/theme.css  Farben (ueber nachtstudie-erzeugen.py)

Entscheid 2026-11-02: erzeugte Kopie plus Pruefsummen-Waechter, keine
Laufzeitabhaengigkeit zur Shell. Jeder Dienst bleibt fuer sich baubar und
offline. Geprueft wird wie bei der Nachtstudie: vorhanden, aktuell,
eingebunden (der dritte Fall ist eine aktuelle Kopie, die niemand laedt).

Aufruf:
    kopf-erzeugen.py                 # Ausgabe auf stdout, schreibt nichts
    kopf-erzeugen.py --schreiben     # alle Ziele neu schreiben
    kopf-erzeugen.py --pruefen       # Exit 1 bei Abweichung
    kopf-erzeugen.py --selbsttest
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
KATALOG = WURZEL / "packages/ui/src/apps.ts"
SYMBOLE = WURZEL / "packages/ui/src/components/Icon.svelte"
DOCKER = WURZEL.parent

_spec = importlib.util.spec_from_file_location(
    "nachtstudie", Path(__file__).resolve().parent / "nachtstudie-erzeugen.py")
nachtstudie = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nachtstudie)

#: Ziel: (Ordner fuer die Kopie, Einstiegsdatei, Muster fuer die Einbindung).
#: In den Ordner kommen `saganta-kopf.js` und, wo `typ` gesetzt ist, die
#: Deklaration `saganta-kopf.d.ts` fuer TSX.
ZIELE: dict[str, tuple[Path, Path, str, bool]] = {
    "fitness": (
        DOCKER / "fitness/frontend/src",
        DOCKER / "fitness/frontend/src/main.tsx",
        r"import\s+['\"]\./saganta-kopf(\.js)?['\"]",
        True,
    ),
    "lager": (
        DOCKER / "lager/frontend/src",
        DOCKER / "lager/frontend/src/main.tsx",
        r"import\s+['\"]\./saganta-kopf(\.js)?['\"]",
        True,
    ),
    "bibliothek": (
        DOCKER / "bibliothek/static",
        DOCKER / "bibliothek/vorlagen/regal.html",
        r"<script[^>]+src=['\"][^'\"]*saganta-kopf\.js['\"]",
        False,
    ),
    "einkaufsliste": (
        DOCKER / "einkaufsliste/frontend/src",
        DOCKER / "einkaufsliste/frontend/src/main.tsx",
        r"import\s+['\"]\./saganta-kopf(\.js)?['\"]",
        True,
    ),
    "medien": (
        DOCKER / "medien/app/static",
        DOCKER / "medien/app/static/index.html",
        r"<script[^>]+src=['\"][^'\"]*saganta-kopf\.js['\"]",
        False,
    ),
    "mealprep": (
        DOCKER / "mealprep/app/static",
        DOCKER / "mealprep/app/templates/base.html",
        r"<script[^>]+src=['\"][^'\"]*saganta-kopf\.js['\"]",
        False,
    ),
    "finanzen": (
        DOCKER / "finanzen/app/static",
        DOCKER / "finanzen/app/static/index.html",
        r"<script[^>]+src=['\"][^'\"]*saganta-kopf\.js['\"]",
        False,
    ),
    "wissen": (
        DOCKER / "wissen/static",
        DOCKER / "wissen/static/index.html",
        r"<script[^>]+src=['\"][^'\"]*saganta-kopf\.js['\"]",
        False,
    ),
}

#: Wert von `SIGNATUR_DURCHGEHEND` in apps.ts.
SIGNATUR_DURCHGEHEND = "linear-gradient(currentColor, currentColor)"

#: Diese Sinnbilder braucht der Kopf selbst, unabhaengig von den Apps.
EIGENE_SYMBOLE = ("layout-grid",)

KOPFKOMMENTAR = """/* ERZEUGT, NICHT VON HAND AENDERN.
 *
 * Quellen: saganta/packages/ui/src/apps.ts, packages/ui/src/components/Icon.svelte,
 * packages/design-tokens/src/theme.css (Pruefsumme {summe})
 * Werkzeug: saganta/scripts/kopf-erzeugen.py --schreiben
 *
 * Der Saganta-Kopf fuer Dienste ausserhalb der SvelteKit-Suite, Gegenstueck
 * zu TopBar.svelte: App-Wechsler, Wortmarke "Saganta /" (fuehrt zur
 * Uebersicht), Sinnbild in Messing, App-Name, Platz fuer Aktionen
 * (slot="aktionen"), darunter das 2-px-Band mit der Signatur der App.
 *
 *   <saganta-kopf app="lager"></saganta-kopf>
 *
 * Unter einem Namen ohne Domain (Direktport, LAN-IP, localhost) gibt es keine
 * Geschwister-Adressen: dann entfallen Wechsler und Link, statt ins Leere zu
 * zeigen. Eine Aenderung hier meldet der Waechter als Abweichung.
 */
"""

DEKLARATION = """/* ERZEUGT, NICHT VON HAND AENDERN (saganta/scripts/kopf-erzeugen.py).
 * Macht <saganta-kopf> in TSX bekannt. */
import type { DetailedHTMLProps, HTMLAttributes } from 'react';

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'saganta-kopf': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        /** Kennung aus apps.ts, z. B. "lager". */
        app: string;
        /** Abweichender Titel, sonst der Name aus dem Katalog. */
        titel?: string;
      };
    }
  }
}

export {};
"""


def lies_katalog(text: str) -> list[dict]:
    """Die Eintraege aus ``SAGANTA_APPS``, in Katalogreihenfolge.

    Zeilenweise wie `app-katalog-abgleich.py`, aus demselben Grund: Kommentare
    und Gradienten mit Klammern und Kommas. Gelesen wird nur bis zur
    schliessenden ``];`` der Liste, sonst kaemen die Eintraege der
    Befehlspalette darunter mit.
    """
    apps: list[dict] = []
    in_liste = False
    for rohe in text.splitlines():
        zeile = rohe.strip()
        if zeile.startswith("//"):
            continue
        if not in_liste:
            in_liste = bool(re.match(r"export const SAGANTA_APPS\b", zeile))
            continue
        if zeile == "];":
            break
        m = re.match(r"id:\s*'([^']+)'", zeile)
        if m:
            apps.append({"id": m.group(1)})
            continue
        if not apps:
            continue
        m = re.match(r"(name|description|icon|sub|subHeim|signatur):\s*'((?:[^'\\]|\\.)*)',?$", zeile)
        if m:
            apps[-1][m.group(1)] = m.group(2).replace("\\'", "'")
            continue
        # Die Uebersicht traegt die Konstante, nicht den Wert.
        if re.match(r"signatur:\s*SIGNATUR_DURCHGEHEND,?$", zeile):
            apps[-1]["signatur"] = SIGNATUR_DURCHGEHEND
            continue
        m = re.match(r"nurHeim:\s*(true|false),?$", zeile)
        if m:
            apps[-1]["nurHeim"] = m.group(1) == "true"
    for a in apps:
        fehlt = [k for k in ("name", "icon", "sub", "signatur") if k not in a]
        if fehlt:
            # Ein halb gelesener Eintrag ergaebe einen Kopf ohne Namen oder
            # Band, der trotzdem aussieht wie ein fertiger.
            raise ValueError(f"apps.ts: Eintrag {a['id']!r} ohne {', '.join(fehlt)}")
    if len(apps) < 3:
        raise ValueError(f"apps.ts: nur {len(apps)} Eintraege gelesen")
    return apps


def lies_symbole(text: str) -> dict[str, str]:
    """``iconPaths`` aus Icon.svelte: Name auf SVG-Inhalt."""
    block = text[text.index("iconPaths"):]
    block = block[:block.index("\n  };")]
    return {
        (a or b): pfad
        for a, b, pfad in re.findall(r"(?:'([\w-]+)'|\b([\w]+)):\s*\n?\s*'([^']*)'", block)
    }


def erzeuge(katalog: str, symbole_text: str, theme: str) -> str:
    apps = lies_katalog(katalog)
    symbole = lies_symbole(symbole_text)
    benoetigt = sorted({a["icon"] for a in apps} | set(EIGENE_SYMBOLE))
    fehlend = [n for n in benoetigt if n not in symbole]
    if fehlend:
        raise ValueError(f"Icon.svelte kennt {', '.join(fehlend)} nicht")
    farben = {n: nachtstudie.hexwert(d) for n, d in nachtstudie.lies_quelle(theme)["farben"]}
    farben_rgb = {n: d for n, d in nachtstudie.lies_quelle(theme)["farben"]}
    schrift = nachtstudie.lies_quelle(theme)["schrift"][0][1]
    summe = hashlib.sha256((katalog + symbole_text + theme).encode("utf-8")).hexdigest()[:12]

    daten = [
        {
            "id": a["id"], "name": a["name"], "beschreibung": a.get("description", ""),
            "icon": a["icon"], "sub": a["sub"], "subHeim": a.get("subHeim"),
            "nurHeim": a.get("nurHeim", False), "signatur": a["signatur"],
        }
        for a in apps
    ]
    js = JS_VORLAGE
    for platzhalter, wert in {
        "__APPS__": json.dumps(daten, ensure_ascii=False, indent=2),
        "__SYMBOLE__": json.dumps({n: symbole[n] for n in benoetigt}, ensure_ascii=False, indent=2),
        "__FLAECHE_RGB__": farben_rgb["surface"],
        "__FLAECHE2__": farben["surface-2"],
        "__HOVER__": farben["surface-hover"],
        "__TEXT__": farben["text"],
        "__MATT__": farben["muted"],
        "__RAND__": farben["border"],
        "__RAND_STARK__": farben["border-stark"],
        "__AKZENT__": farben["akzent"],
        "__AKZENT_RGB__": farben_rgb["akzent"],
        "__FOKUS__": farben["focus"],
        "__SCHRIFT__": schrift,
    }.items():
        js = js.replace(platzhalter, wert)
    if "__" in re.sub(r"__proto__", "", js.split("*/", 1)[1]):
        raise ValueError("Platzhalter nicht ersetzt")
    return KOPFKOMMENTAR.format(summe=summe) + js


JS_VORLAGE = r"""(() => {
  if (customElements.get('saganta-kopf')) return;

  const APPS = __APPS__;

  const SYMBOLE = __SYMBOLE__;

  const STIL = `
    :host {
      display: block;
      position: sticky;
      top: 0;
      z-index: 30;
      font-family: var(--saganta-schrift, __SCHRIFT__);
      color: __TEXT__;
      background: rgb(__FLAECHE_RGB__ / 0.8);
      -webkit-backdrop-filter: blur(12px);
      backdrop-filter: blur(12px);
    }
    * { box-sizing: border-box; }
    .zeile {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      height: 56px; padding: 0 12px;
      padding-left: max(12px, env(safe-area-inset-left));
      padding-right: max(12px, env(safe-area-inset-right));
    }
    .links { display: flex; align-items: center; gap: 6px; min-width: 0; }
    .rechts { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
    .marke {
      display: flex; align-items: center; gap: 8px; min-width: 0;
      color: inherit; text-decoration: none; border-radius: 6px;
    }
    .wort { font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
    .trenner { color: __MATT__; }
    .sinnbild { color: __AKZENT__; display: inline-flex; }
    .app { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .wechsler { position: relative; }
    .knopf {
      display: grid; place-items: center; width: 44px; height: 44px;
      background: none; border: 0; padding: 0; color: __MATT__; cursor: pointer;
    }
    .knopf:hover { color: __TEXT__; }
    .knopf > span {
      display: grid; place-items: center; width: 32px; height: 32px;
      border: 1px solid __RAND_STARK__; border-radius: 6px;
    }
    .knopf:hover > span { background: __FLAECHE2__; }
    a:focus-visible, button:focus-visible { outline: 2px solid __FOKUS__; outline-offset: 2px; }
    .tafel {
      position: absolute; left: 0; top: 100%; margin-top: 6px; z-index: 40;
      width: 18rem; max-width: calc(100vw - 24px);
      border: 1px solid __RAND__; border-radius: 12px; overflow: hidden;
      background: __FLAECHE2__; box-shadow: 0 12px 32px rgb(0 0 0 / 0.45);
    }
    .tafel[hidden] { display: none; }
    .tafel-kopf {
      padding: 8px 12px; border-bottom: 1px solid __RAND__;
      font-size: 12px; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; color: __MATT__;
    }
    .raster {
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; padding: 8px;
      max-height: 70vh; overflow-y: auto;
    }
    .raster a {
      display: flex; flex-direction: column; align-items: center; gap: 6px;
      padding: 12px 8px; border-radius: 8px; text-align: center; text-decoration: none;
      color: __MATT__; font-size: 12px; line-height: 1.2;
    }
    .raster a:hover { background: __HOVER__; color: __TEXT__; }
    .raster a[aria-current="page"] { background: rgb(__AKZENT_RGB__ / 0.1); color: __AKZENT__; }
    .band { height: 2px; color: __RAND_STARK__; }
    @media (max-width: 639px) {
      .wort, .trenner { display: none; }
    }
  `;

  /** Der Raum eines Hosts, wie `raumVon` in apps.ts: die letzten beiden Labels. */
  function raumVon(host) {
    const name = (host || '').replace(/^\[|\]$/g, '').replace(/:\d+$/, '').toLowerCase();
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(name) || name.includes(':')) return null;
    const teile = name.split('.').filter(Boolean);
    return teile.length < 2 ? null : teile.slice(-2).join('.');
  }
  const istHeim = (raum) => !!raum && raum.endsWith('.home');
  function appUrl(app, raum) {
    const sub = istHeim(raum) ? (app.subHeim || app.sub) : app.sub;
    return sub ? `https://${sub}.${raum}` : `https://${raum}`;
  }

  function svg(name, groesse) {
    const pfad = SYMBOLE[name];
    if (!pfad) return '';
    return `<svg width="${groesse}" height="${groesse}" viewBox="0 0 24 24" fill="none" ` +
      `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ` +
      `aria-hidden="true">${pfad}</svg>`;
  }

  function knoten(tag, klasse, text) {
    const k = document.createElement(tag);
    if (klasse) k.className = klasse;
    if (text != null) k.textContent = text;
    return k;
  }

  class SagantaKopf extends HTMLElement {
    static get observedAttributes() { return ['app', 'titel']; }

    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._draussen = (e) => {
        if (this._tafel && !this._tafel.hidden && !e.composedPath().includes(this)) this._zu();
      };
      this._taste = (e) => { if (e.key === 'Escape') this._zu(); };
    }

    connectedCallback() {
      this._zeichne();
      document.addEventListener('click', this._draussen);
      document.addEventListener('keydown', this._taste);
    }

    disconnectedCallback() {
      document.removeEventListener('click', this._draussen);
      document.removeEventListener('keydown', this._taste);
    }

    attributeChangedCallback() { if (this.isConnected) this._zeichne(); }

    _zu() {
      if (!this._tafel) return;
      this._tafel.hidden = true;
      this._knopf.setAttribute('aria-expanded', 'false');
    }

    _zeichne() {
      const id = this.getAttribute('app') || '';
      const app = APPS.find((a) => a.id === id);
      const raum = raumVon(window.location.host);
      const shell = APPS.find((a) => a.id === 'shell');
      const wurzel = this.shadowRoot;
      wurzel.textContent = '';
      const stil = document.createElement('style');
      stil.textContent = STIL;
      wurzel.append(stil);

      const zeile = knoten('div', 'zeile');
      const links = knoten('div', 'links');
      const rechts = knoten('div', 'rechts');
      rechts.append(document.createElement('slot'));
      rechts.firstChild.name = 'aktionen';

      this._tafel = null;
      if (raum) {
        const wechsler = knoten('div', 'wechsler');
        const knopf = knoten('button', 'knopf');
        knopf.type = 'button';
        knopf.setAttribute('aria-haspopup', 'menu');
        knopf.setAttribute('aria-expanded', 'false');
        knopf.setAttribute('aria-label', 'App-Wechsler');
        knopf.title = 'Apps';
        knopf.innerHTML = `<span>${svg('layout-grid', 18)}</span>`;
        const tafel = knoten('div', 'tafel');
        tafel.hidden = true;
        tafel.setAttribute('role', 'menu');
        tafel.append(knoten('div', 'tafel-kopf', 'Saganta-Apps'));
        const raster = knoten('div', 'raster');
        for (const a of APPS.filter((x) => istHeim(raum) || !x.nurHeim)) {
          const ziel = knoten('a');
          ziel.href = appUrl(a, raum);
          ziel.title = a.beschreibung;
          ziel.setAttribute('role', 'menuitem');
          if (a.id === id) ziel.setAttribute('aria-current', 'page');
          ziel.innerHTML = svg(a.icon, 20);
          ziel.append(knoten('span', null, a.name));
          raster.append(ziel);
        }
        tafel.append(raster);
        knopf.addEventListener('click', () => {
          tafel.hidden = !tafel.hidden;
          knopf.setAttribute('aria-expanded', String(!tafel.hidden));
        });
        wechsler.append(knopf, tafel);
        links.append(wechsler);
        this._tafel = tafel;
        this._knopf = knopf;
      }

      const marke = knoten(raum ? 'a' : 'span', 'marke');
      if (raum) {
        marke.href = appUrl(shell, raum);
        marke.setAttribute('aria-label', 'Zurück zur Saganta-Übersicht');
      }
      marke.append(knoten('span', 'wort', 'Saganta'), knoten('span', 'trenner', '/'));
      if (app) {
        const sinnbild = knoten('span', 'sinnbild');
        sinnbild.innerHTML = svg(app.icon, 17);
        marke.append(sinnbild);
      }
      marke.append(knoten('span', 'app', this.getAttribute('titel') || (app ? app.name : id)));
      links.append(marke);

      zeile.append(links, rechts);
      const band = knoten('div', 'band');
      band.setAttribute('aria-hidden', 'true');
      // Ohne bekannte App die durchgehende Linie, wie `signaturFuer` in apps.ts.
      band.style.backgroundImage = app ? app.signatur : 'linear-gradient(currentColor, currentColor)';
      wurzel.append(zeile, band);
    }
  }

  customElements.define('saganta-kopf', SagantaKopf);
})();
"""


def quellen() -> tuple[str, str, str]:
    return (KATALOG.read_text(encoding="utf-8"), SYMBOLE.read_text(encoding="utf-8"),
            nachtstudie.QUELLE.read_text(encoding="utf-8"))


def pruefe(soll: str) -> list[tuple[str, str, str]]:
    """(Ziel, Stufe, Satz) je Befund; leer heisst alles in Ordnung."""
    funde = []
    for ziel, (ordner, einstieg, muster, typ) in sorted(ZIELE.items()):
        for datei, inhalt in [("saganta-kopf.js", soll)] + ([("saganta-kopf.d.ts", DEKLARATION)] if typ else []):
            kopie = ordner / datei
            if not kopie.exists():
                funde.append((ziel, "vorhanden", f"{kopie} fehlt"))
            elif kopie.read_text(encoding="utf-8") != inhalt:
                funde.append((ziel, "aktuell", f"{kopie} weicht von der Quelle ab"))
        if not einstieg.exists():
            funde.append((ziel, "eingebunden", f"Einstiegsdatei {einstieg} fehlt"))
        elif not re.search(muster, einstieg.read_text(encoding="utf-8")):
            funde.append((ziel, "eingebunden", f"{einstieg.name} laedt saganta-kopf.js nicht"))
    return funde


def schreibe(soll: str) -> None:
    for ziel, (ordner, _, _, typ) in sorted(ZIELE.items()):
        (ordner / "saganta-kopf.js").write_text(soll, encoding="utf-8")
        if typ:
            (ordner / "saganta-kopf.d.ts").write_text(DEKLARATION, encoding="utf-8")
        print(f"geschrieben: {ziel} -> {ordner}/saganta-kopf.js")


def selbsttest() -> int:
    global ZIELE
    katalog, symbole, theme = quellen()
    soll = erzeuge(katalog, symbole, theme)
    apps = lies_katalog(katalog)
    faelle = [
        ("Katalog hat Uebersicht und Lager", {"shell", "lager"} <= {a["id"] for a in apps}),
        ("jede Signatur ist ein Gradient", all("gradient(" in a["signatur"] for a in apps)),
        ("Befehlspalette unter der Liste wird nicht gelesen", "nav-downloads" not in {a["id"] for a in apps}),
        ("Kalender kennt seinen Heimnamen", any(a["id"] == "calendar" and a.get("subHeim") == "calendar" for a in apps)),
        ("Akzent ist accent-400", "#dd9c3f" in soll),
        ("kein Platzhalter bleibt stehen", "__APPS__" not in soll and "__TEXT__" not in soll),
    ]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        ein = d / "main.tsx"
        ein.write_text("import './saganta-kopf.js';\n")
        (d / "saganta-kopf.js").write_text(soll)
        (d / "saganta-kopf.d.ts").write_text(DEKLARATION)
        alt, ZIELE = ZIELE, {"probe": (d, ein, r"import\s+['\"]\./saganta-kopf(\.js)?['\"]", True)}
        try:
            faelle.append(("saubere Kopie ergibt keinen Fund", pruefe(soll) == []))
            (d / "saganta-kopf.js").write_text(soll.replace("Saganta-Apps", "Apps"))
            faelle.append(("geaenderte Kopie wird erkannt", [f[1] for f in pruefe(soll)] == ["aktuell"]))
            (d / "saganta-kopf.js").write_text(soll)
            ein.write_text("// nichts\n")
            faelle.append(("fehlende Einbindung wird erkannt", [f[1] for f in pruefe(soll)] == ["eingebunden"]))
            (d / "saganta-kopf.d.ts").unlink()
            ein.write_text("import './saganta-kopf';\n")
            faelle.append(("fehlende Deklaration wird erkannt", [f[1] for f in pruefe(soll)] == ["vorhanden"]))
        finally:
            ZIELE = alt
    try:
        erzeuge("export const SAGANTA_APPS = [\n];\n", symbole, theme)
        laut = False
    except ValueError:
        laut = True
    faelle.append(("leerer Katalog scheitert laut", laut))
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
    soll = erzeuge(*quellen())
    if a.schreiben:
        schreibe(soll)
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
