#!/usr/bin/env python3
"""Zeigt die Signaturlinien aller Apps nebeneinander.

WOZU: Jede App traegt unter ihrer Kopfleiste ein 2-px-Band mit eigenem
Strichrhythmus (`signatur` in `packages/ui/src/apps.ts`). Ob zwoelf solche
Rhythmen nebeneinander wirklich unterscheidbar sind, laesst sich am Quelltext
nicht beurteilen -- und einzeln betrachtet sieht jeder von ihnen richtig aus.
Die Baender einer App zu sehen, hiesse sich anzumelden und durchzuklicken.

Diese Probe liest die Muster aus dem Katalog (also aus der einen Quelle, nicht
aus einer Kopie), legt sie untereinander und fotografiert sie in allen drei
Erscheinungsbildern. Was hier gleich aussieht, ist gleich.

Aufruf:  scripts/signatur-probe.py [zielordner]
Ergebnis: <ziel>/signaturen-<theme>.png
"""
import pathlib
import re
import shutil
import subprocess
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
KATALOG = WURZEL / "packages/ui/src/apps.ts"
CHROME = pathlib.Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux/chrome"


def muster_lesen():
    """(Kennung, Name, CSS-Wert) je App, in Katalogreihenfolge."""
    text = KATALOG.read_text(encoding="utf-8")
    durchgehend = re.search(
        r"SIGNATUR_DURCHGEHEND\s*=\s*'([^']+)'", text).group(1)
    eintraege = []
    for block in re.finditer(r"\{\n\s*id: '([a-z]+)',([\s\S]*?)\n  \}", text):
        kennung, rumpf = block.group(1), block.group(2)
        name = re.search(r"name: '([^']*)'", rumpf)
        wert = re.search(r"signatur: (?:'([^']*)'|(SIGNATUR_DURCHGEHEND))", rumpf)
        if not (name and wert):
            continue
        eintraege.append((kennung, name.group(1),
                          wert.group(1) or durchgehend))
    return eintraege


def seite(eintraege, theme):
    zeilen = []
    for kennung, name, wert in eintraege:
        zeilen.append(
            f'<div class="zeile"><div class="etikett">{name}'
            f'<span class="kennung">{kennung}</span></div>'
            f'<div class="band" style="background-image:{wert}"></div></div>')
    return f"""<!doctype html>
<html lang="de" data-theme="{theme}"><head><meta charset="utf-8">
<style>
  :root {{ --grund:#161310; --schrift:#f3ede2; --strich:#7c7264; }}
  [data-theme=light] {{ --grund:#f5f0e8; --schrift:#1a140c; --strich:#7c7264; }}
  [data-theme=hc] {{ --grund:#000; --schrift:#fff; --strich:#ff0; }}
  body {{ margin:0; padding:28px 32px; background:var(--grund); color:var(--schrift);
         font-family: ui-sans-serif, system-ui, sans-serif; }}
  h1 {{ font-size:15px; font-weight:600; margin:0 0 4px; }}
  p.hinweis {{ font-size:12px; opacity:.7; margin:0 0 22px; }}
  .zeile {{ margin-bottom:18px; }}
  .etikett {{ display:flex; gap:8px; align-items:baseline; font-size:12px; margin-bottom:5px; }}
  .kennung {{ opacity:.5; font-family: ui-monospace, monospace; font-size:10px; }}
  .band {{ height:2px; width:100%; color:var(--strich); }}
</style></head><body>
<h1>Signaturlinien der Saganta-Apps &mdash; {theme}</h1>
<p class="hinweis">Gelesen aus packages/ui/src/apps.ts. Zwei Baender, die hier
gleich aussehen, sind in der Oberflaeche nicht zu unterscheiden.</p>
{chr(10).join(zeilen)}
</body></html>"""


def main():
    ziel = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/signatur-probe")
    ziel.mkdir(parents=True, exist_ok=True)
    eintraege = muster_lesen()
    if not eintraege:
        print("FEHLER: keine Signaturen im Katalog gefunden.", file=sys.stderr)
        return 2
    print(f"{len(eintraege)} Signaturen gelesen: "
          f"{', '.join(k for k, _, _ in eintraege)}")

    doppelt = {}
    for kennung, _, wert in eintraege:
        doppelt.setdefault(wert, []).append(kennung)
    kollisionen = [v for v in doppelt.values() if len(v) > 1]
    for k in kollisionen:
        print(f"  BEFUND: gleiches Muster fuer {', '.join(k)}")

    if not CHROME.exists() and not shutil.which("chromium"):
        print(f"Kein Chromium unter {CHROME}; nur die HTML-Dateien geschrieben.")

    for theme in ("dark", "light", "hc"):
        html = ziel / f"signaturen-{theme}.html"
        html.write_text(seite(eintraege, theme), encoding="utf-8")
        if CHROME.exists():
            subprocess.run(
                [str(CHROME), "--headless", "--no-sandbox", "--disable-gpu",
                 "--disable-dev-shm-usage", "--hide-scrollbars",
                 "--virtual-time-budget=3000",
                 f"--screenshot={ziel}/signaturen-{theme}.png",
                 "--window-size=760,700", f"file://{html}"],
                capture_output=True)
            print(f"  {ziel}/signaturen-{theme}.png")
    return 1 if kollisionen else 0


if __name__ == "__main__":
    sys.exit(main())
