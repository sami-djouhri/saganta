#!/usr/bin/env python3
"""Prueft das Schaufenster gegen die Suite, die es beschreibt.

Warum es das gibt: die oeffentliche Seite nennt die Apps beim Namen und ihre
Anzahl als Wort. Beides ist dieselbe Information wie der App-Katalog in
`packages/ui/src/apps.ts`, nur abgeschrieben. Eine abgeschriebene Liste neben
einer gepflegten Liste veraltet in beide Richtungen, und auf einer oeffentlichen
Seite sieht das Ergebnis wie ein geprueftes Soll aus.

Dazu macht `datenschutz.html` vier Zusagen (keine Cookies, keine Drittinhalte,
keine Schriften von Dritten, keine Zugriffsprotokolle). Drei davon lassen sich am
Dateibestand messen, die vierte an der Caddy-Konfiguration auf netcup. Eine
Datenschutzerklaerung, die geprueft wird, ist etwas anderes als eine, die
behauptet.

Aufruf:
    python3 abgleich.py              # alles, was ohne Netz geht
    python3 abgleich.py --netcup     # dazu Caddy-Logging und die Mailadressen

Rueckgabe 0, wenn nichts zu meckern ist, sonst 1. `deploy.sh` ruft es vorher und
liefert nicht aus, wenn es 1 meldet.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
OEFFENTLICH = HIER / "oeffentlich"
KATALOG = HIER.parent / "packages" / "ui" / "src" / "apps.ts"
TOKENS = HIER.parent / "packages" / "design-tokens" / "src" / "theme.css"

# Die Uebersicht ist die Huelle und keine App mit eigenem Zweck. Sie steht im
# Katalog, weil das Launchpad eine Kachel fuer sich selbst braucht; auf einer
# oeffentlichen Seite waere sie eine zwoelfte Zeile ohne Inhalt.
KEINE_APP = {"shell"}

ZAHLWORT = {
    1: "eine", 2: "zwei", 3: "drei", 4: "vier", 5: "fuenf", 6: "sechs",
    7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwoelf",
    13: "dreizehn", 14: "vierzehn", 15: "fuenfzehn", 16: "sechzehn",
    17: "siebzehn", 18: "achtzehn", 19: "neunzehn", 20: "zwanzig",
}
# Umlaute kommen im Dokument ausgeschrieben vor, in dieser Tabelle nicht.
UMSCHRIFT = {"fuenf": "fünf", "zwoelf": "zwölf", "fuenfzehn": "fünfzehn"}

# Fremde Adressen, die bewusst verlinkt sind. Alles andere ist ein Fund: der
# Datenschutztext sagt "keine eingebetteten Inhalte" zu.
ERLAUBTE_FREMDE = {
    "https://www.gnu.org/licenses/agpl-3.0.html",  # die Lizenz, auf die sich die Seite beruft
    "https://djouhri.de",                           # der Anbieter, im Impressum
    "https://djouhri.de/projekte/saganta",          # die Fallstudie, seit 2026-10-30
    "https://github.com/sami-djouhri/saganta",      # der Quelltext, oeffentlich seit September
    "https://saganta.de/",                          # die eigene Adresse in og:url
}

# Woerter, die auf das abgeschaffte SaaS-Modell zeigen. Standen alle in
# `apps/shell/src/routes/preise`, und genau von dort stammt der Text dieser Seite
# NICHT. Der Entscheid vom 2026-10-21 hat das Produkt abgeschafft, nicht nur den
# Zugang.
VERBOTENE_WOERTER = [
    "Tarif", "Abo", "monatlich kündigen", "Preise", "kostenlos testen",
    "Registrieren", "Jetzt starten",
]

# Als Codepoint und nicht als Zeichen. Diese Datei laeuft selbst durch den
# PreToolUse-Hook, der den langen Gedankenstrich ueberall ablehnt, auch in einer
# Pruefliste, die ihn finden soll. Das ist kein Umweg um die Regel, sondern die
# einzige Art, einen Pruefer fuer sie zu schreiben.
LANGER_STRICH = chr(0x2014)

fundstellen: list[str] = []
hinweise: list[str] = []


def fund(datei: str, text: str) -> None:
    """Etwas, das die Auslieferung aufhaelt."""
    fundstellen.append(f"{datei}: {text}")


def hinweis(datei: str, text: str) -> None:
    """Etwas, das jemand wissen sollte, ohne dass die Seite deshalb falsch ist.

    Die Trennung ist Absicht. Ein fehlendes Impressum macht die Seite
    rechtswidrig, eine um eine Stufe verschobene Goldfarbe nicht. Haette beides
    dasselbe Gewicht, wuerde das eine irgendwann als Rauschen mitgelesen.
    """
    hinweise.append(f"{datei}: {text}")


def katalog_apps() -> list[tuple[str, str]]:
    """Die Apps aus `packages/ui/src/apps.ts`, ohne die Uebersicht.

    Gelesen und nicht importiert: das Skript soll ohne Node laufen. Das Muster
    greift die beiden Felder, die unmittelbar aufeinander folgen; gingen sie
    einmal auseinander, waere die Liste kuerzer und der Mengenvergleich unten
    schlaegt an, statt still weniger zu pruefen.
    """
    if not KATALOG.exists():
        print(f"FEHLT: {KATALOG}", file=sys.stderr)
        sys.exit(2)
    quelle = KATALOG.read_text(encoding="utf-8")
    paare = re.findall(r"id:\s*'([^']+)',\s*\n\s*name:\s*'([^']+)'", quelle)
    apps = [(i, n) for i, n in paare if i not in KEINE_APP]
    if not apps:
        print("Der App-Katalog ergab null Apps. Das ist kein Befund, sondern ein "
              "kaputtes Muster in dieser Datei.", file=sys.stderr)
        sys.exit(2)
    return apps


def inhalt_apps() -> list[dict]:
    """Die App-Seiten aus `quelle/inhalt.py`."""
    sys.path.insert(0, str(HIER / "quelle"))
    import inhalt  # noqa: E402
    return inhalt.APPS


def pruefe_seiten(apps: list[tuple[str, str]], seiten: list[dict],
                  wurzel: Path = OEFFENTLICH) -> None:
    """Jede App hat eine Seite und ein Bild, in beide Richtungen.

    Seit dem 2026-10-30 stellt die Seite jede App einzeln vor, mit einem Bild
    der echten Oberflaeche (Entscheid: "erst alles fertig, dann in einem
    Schritt live"). Ein fehlendes Bild ist deshalb ein Fund und kein Hinweis:
    eine App-Seite ohne Bild ist genau der halbe Stand, der nicht ausgeliefert
    werden sollte.
    """
    soll = {i: n for i, n in apps}
    ist = {a["id"]: a["name"] for a in seiten}
    for i in sorted(soll.keys() - ist.keys()):
        fund("quelle/inhalt.py", f"App '{soll[i]}' ({i}) steht im Katalog, hat aber keine Seite")
    for i in sorted(ist.keys() - soll.keys()):
        fund("quelle/inhalt.py", f"App '{ist[i]}' ({i}) hat eine Seite, steht aber nicht im Katalog")
    for i in sorted(soll.keys() & ist.keys()):
        if soll[i] != ist[i]:
            fund("quelle/inhalt.py", f"'{i}' heisst im Katalog '{soll[i]}', hier '{ist[i]}'")

    for a in seiten:
        if not (wurzel / f"{a['seite']}.html").exists():
            fund(f"{a['seite']}.html", "fehlt, bauen.py laufen lassen")
    for name in ["uebersicht"] + [a["seite"] for a in seiten]:
        if not (wurzel / "bilder" / f"{name}.webp").exists():
            fund(f"bilder/{name}.webp", "fehlt. Ohne Bild wird die Seite nicht ausgeliefert")


def pruefe_gebaut() -> None:
    """`oeffentlich/` muss dem Stand von `quelle/` entsprechen.

    Sonst liegt eine Hand-Aenderung an einer erzeugten Datei vor, die der
    naechste Bau ueberschreibt, oder eine Aenderung an der Quelle, die nie
    gebaut wurde. Beides sieht in der Vorschau richtig aus.
    """
    p = subprocess.run([sys.executable, str(HIER / "bauen.py"), "--pruefen"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        for zeile in (p.stdout + p.stderr).strip().splitlines() or ["Abbruch ohne Ausgabe"]:
            fund("bauen.py", zeile)


def pruefe_apps(html: str, apps: list[tuple[str, str]], datei: str = "index.html") -> None:
    """Mengenvergleich in beide Richtungen, plus die Anzahl als Wort."""
    genannt = re.findall(r'<span class="name">([^<]+)</span>', html)
    if datei != "index.html":
        genannt = []  # die Liste steht nur auf der Startseite
    soll = {n for _, n in apps}
    ist = set(genannt)

    for fehlt in sorted(soll - ist) if datei == "index.html" else []:
        fund("index.html", f"App '{fehlt}' steht im Katalog, aber nicht auf der Seite")
    for zuviel in sorted(ist - soll):
        fund("index.html", f"App '{zuviel}' steht auf der Seite, aber nicht im Katalog")
    if len(genannt) != len(set(genannt)):
        fund("index.html", "eine App ist doppelt aufgefuehrt")

    # Die Anzahl als Wort. Geprueft wird jede Stelle, an der ein Zahlwort oder
    # eine Ziffer vor "Apps" steht, auch mit einem Wort dazwischen
    # ("sieben weitere Apps"): genau so entsteht eine zweite Rechnung, die
    # getrennt falsch werden kann.
    n = len(apps)
    richtig = {ZAHLWORT.get(n, ""), UMSCHRIFT.get(ZAHLWORT.get(n, ""), ""), str(n)}
    richtig = {w.lower() for w in richtig if w}
    alle_zahlwoerter = {w.lower() for w in ZAHLWORT.values()} | {
        v.lower() for v in UMSCHRIFT.values()
    }

    for treffer in re.finditer(r"\b([A-Za-zÄÖÜäöü]+|\d+)\s+(?:\w+\s+)?[Aa]pps\b", html):
        wort = treffer.group(1).lower()
        if wort not in alle_zahlwoerter and not wort.isdigit():
            continue  # "die uebrigen Apps", "weitere Apps": keine Zahl, kein Risiko
        if wort not in richtig:
            fund(datei,
                 f"die Seite sagt '{treffer.group(0).strip()}', der Katalog hat {n} Apps")


def pruefe_platzhalter(dateien: list[Path]) -> None:
    """Eine Seite ohne Anschrift darf nicht oeffentlich stehen (§ 5 DDG).

    Die Sperre liegt hier und nicht als Satz in einer Anleitung: ein Hinweis,
    den jemand befolgen muss, ist keine Zusicherung.
    """
    for d in dateien:
        text = d.read_text(encoding="utf-8")
        treffer = text.count("PLATZHALTER")
        if treffer:
            fund(d.name, f"{treffer} Platzhalter. Pflichtangaben fehlen, "
                         "die Seite darf so nicht ausgeliefert werden")


def pruefe_fremde_inhalte(dateien: list[Path]) -> None:
    """Die Zusage 'keine Drittinhalte, keine fremden Schriften' nachmessen."""
    for d in dateien:
        text = d.read_text(encoding="utf-8")
        for adresse in re.findall(r'(?:href|src)="(https?://[^"]+)"', text):
            if adresse not in ERLAUBTE_FREMDE:
                fund(d.name, f"fremde Adresse '{adresse}' widerspricht der Zusage "
                             "in datenschutz.html")
        if re.search(r"fonts\.(googleapis|gstatic)\.com", text):
            fund(d.name, "Schrift von Google Fonts, datenschutz.html sagt das Gegenteil zu")
        if re.search(r"<script", text, re.IGNORECASE):
            fund(d.name, "ein script-Element. Die Seite braucht kein JavaScript, "
                         "und ohne JavaScript kann sie auch keines nachladen")
        if "document.cookie" in text or "Set-Cookie" in text:
            fund(d.name, "setzt ein Cookie, datenschutz.html sagt 'keine Cookies' zu")
        # Die restlichen Zusagen des Datenschutztextes, Element fuer Element.
        # `<form>` steht hier, weil "kein Kontaktformular" sonst eine Aussage
        # waere, die niemand nachhaelt: ein spaeter eingefuegtes Formular macht
        # die Erklaerung falsch, ohne dass irgendwo etwas rot wird.
        for element, zusage in (
            ("form", "kein Anmelde- und kein Kontaktformular"),
            ("iframe", "keine eingebetteten Inhalte"),
            ("video", "keine Videos"),
            ("embed", "keine eingebetteten Inhalte"),
            ("object", "keine eingebetteten Inhalte"),
        ):
            if re.search(rf"<{element}[\s>]", text, re.IGNORECASE):
                fund(d.name, f"ein {element}-Element. datenschutz.html sagt "
                             f"'{zusage}' zu")


def pruefe_verbotene_woerter(dateien: list[Path]) -> None:
    """Reste des abgeschafften SaaS-Modells."""
    for d in dateien:
        text = d.read_text(encoding="utf-8")
        for wort in VERBOTENE_WOERTER:
            if re.search(rf"\b{re.escape(wort)}", text):
                fund(d.name, f"'{wort}' zeigt auf das Produkt, das am 2026-10-21 "
                             "abgeschafft wurde")
        for pfad in ("/login", "/preise", "/forgot", "/reset"):
            if f'"{pfad}' in text:
                fund(d.name, f"Verweis auf {pfad}. Auf dieser Domain antwortet "
                             "darauf niemand mehr")


def pruefe_farben(stil: Path) -> None:
    """Vergleicht die uebernommenen Farben mit `packages/design-tokens`.

    `stil.css` traegt die Werte als Kopie, weil die Tokens eine
    Tailwind-Theme-Datei sind und einen Build braeuchten. Eine Kopie driftet, und
    hier ist sie noch am Tag ihrer Entstehung gedriftet: eine parallele Sitzung
    verschob `--dunkel-akzent` um eine Stufe, waehrend diese Seite entstand.

    Das ist ein Hinweis und kein Fund: die Seite ist mit der aelteren Goldstufe
    nicht falsch, nur nicht mehr deckungsgleich mit der Suite. Wer sie angleicht,
    aendert die sechs Zeilen in `stil.css` von Hand.
    """
    if not TOKENS.exists():
        hinweis("stil.css", f"{TOKENS.name} nicht gefunden, die Farbdeckung ist ungeprueft")
        return

    quelle = TOKENS.read_text(encoding="utf-8")
    soll: dict[str, str] = {}
    for praefix in ("hell", "dunkel"):
        for name, wert in re.findall(rf"--{praefix}-([a-z-]+):\s*([0-9]+ [0-9]+ [0-9]+);", quelle):
            soll[f"{praefix}/{name}"] = wert
    for name, wert in re.findall(r"--color-(accent-\d+):\s*(#[0-9a-fA-F]{6});", quelle):
        soll[f"marke/{name}"] = wert.lower()

    text = stil.read_text(encoding="utf-8")
    # Der Block fuer das helle Theme steht in einer Media-Query, der dunkle
    # davor in `:root`. Getrennt wird an der Query, nicht an der Reihenfolge der
    # Eigenschaften: sonst entscheidet die Zeilennummer ueber die Bedeutung.
    teile = text.split("@media (prefers-color-scheme: light)")
    blocks = {"dunkel": teile[0], "hell": teile[1] if len(teile) > 1 else ""}

    geprueft = 0
    for praefix, block in blocks.items():
        for name, wert in re.findall(r"--([a-z-]+):\s*rgb\(([0-9]+ [0-9]+ [0-9]+)\);", block):
            schluessel = f"{praefix}/{name}"
            if schluessel not in soll:
                continue  # eigene Variable ohne Gegenstueck, etwa --marke
            geprueft += 1
            if soll[schluessel] != wert:
                hinweis("stil.css", f"--{name} ({praefix}) steht auf '{wert}', die Tokens "
                                    f"sagen '{soll[schluessel]}'")

    for wert in re.findall(r"--marke:\s*(#[0-9a-fA-F]{6});", text):
        geprueft += 1
        if soll.get("marke/accent-400") != wert.lower():
            hinweis("stil.css", f"--marke steht auf '{wert}', --color-accent-400 "
                                f"sagt '{soll.get('marke/accent-400')}'")

    if geprueft == 0:
        hinweis("stil.css", "null Farben abgeglichen. Das ist kein gutes Zeichen, "
                            "sondern ein Muster, das nichts mehr trifft")
        return

    # Verglichen wird gegen den ARBEITSBAUM. Traegt der uncommittete
    # Aenderungen, stammt eine Abweichung womoeglich aus einer fremden Sitzung,
    # die noch laeuft, und nicht aus einem Versaeumnis hier. Der Unterschied
    # entscheidet, ob jemand handeln muss, und gehoert deshalb in die Meldung.
    if any("stil.css: --" in h for h in hinweise):
        p = subprocess.run(
            ["git", "-C", str(HIER.parent), "diff", "--quiet", "--", str(TOKENS)],
            capture_output=True,
        )
        if p.returncode == 1:
            hinweis("stil.css", "die Abweichungen oben stehen gegen einen "
                                "theme.css-Stand, der noch nicht committet ist. "
                                "Erst angleichen, wenn der Nachbar fertig ist")


def pruefe_inline_stile(dateien: list[Path]) -> None:
    """Inline-Stile wirken unter der CSP des Caddy-Blocks nicht.

    `caddy-block.conf` setzt `style-src 'self'` ohne `unsafe-inline`. Ein
    `style`-Attribut im Markup wird dann vom Browser verworfen, und zwar ohne
    Fehlermeldung und ohne Spur in der Seite: der Abstand fehlt einfach. Beim
    Bauen dieser Seite standen genau zwei solche Attribute drin, geschrieben
    bevor die CSP dazukam.
    """
    for d in dateien:
        text = d.read_text(encoding="utf-8")
        treffer = re.findall(r'<[^>]*\sstyle="[^"]*"', text)
        for t in treffer:
            kurz = t[:60].replace("\n", " ")
            fund(d.name, f"Inline-Stil '{kurz}' wirkt unter der CSP nicht, "
                         "gehoert nach stil.css")


def pruefe_langer_strich(dateien: list[Path]) -> None:
    """Regel: kein langer Gedankenstrich, nirgendwo, auch in Kommentaren."""
    for d in dateien:
        text = d.read_text(encoding="utf-8")
        for zeichen, name in ((LANGER_STRICH, "einen langen Gedankenstrich"),
                              ("&mdash;", "die HTML-Entitaet dafuer")):
            if zeichen in text:
                fund(d.name, f"enthaelt {name}")


def pruefe_netcup() -> None:
    """Die zwei Zusagen, die nur am Wirt zu messen sind."""
    def ssh(befehl: str) -> tuple[int, str]:
        p = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "netcup", befehl],
            capture_output=True, text=True,
        )
        return p.returncode, p.stdout.strip()

    # Zugriffsprotokolle: Caddy schreibt sie nur mit ausdruecklicher
    # `log`-Direktive. Der Datenschutztext sagt zu, dass keine entstehen.
    rc, aus = ssh("grep -c '^[[:space:]]*log' /etc/caddy/Caddyfile || true")
    if rc != 0:
        fund("netcup", "Caddyfile nicht lesbar, die Log-Zusage ist damit ungeprueft")
    elif aus.isdigit() and int(aus) > 0:
        fund("netcup", f"{aus} log-Direktiven im Caddyfile. datenschutz.html sagt "
                       "'keine Zugriffsprotokolle' zu")

    # Jede genannte Mailadresse muss es geben. Eine Kontaktadresse im Impressum,
    # die bouncet, erfuellt § 5 DDG nicht.
    genannt = set()
    for d in sorted(OEFFENTLICH.glob("*.html")):
        genannt |= set(re.findall(r"mailto:([^\"']+@saganta\.de)", d.read_text(encoding="utf-8")))
    if genannt:
        rc, aus = ssh(
            "cd /opt/mailcow-dockerized && "
            "P=$(grep -h '^DBPASS=' mailcow.conf | cut -d= -f2) && "
            "U=$(grep -h '^DBUSER=' mailcow.conf | cut -d= -f2) && "
            "N=$(grep -h '^DBNAME=' mailcow.conf | cut -d= -f2) && "
            "docker exec mailcowdockerized-mysql-mailcow-1 mysql -u\"$U\" -p\"$P\" \"$N\" "
            "-N -e 'SELECT username FROM mailbox; SELECT address FROM alias;' 2>/dev/null"
        )
        if rc != 0 or not aus:
            fund("netcup", "Mailcow nicht abfragbar, die Adressen sind ungeprueft")
        else:
            vorhanden = {z.strip() for z in aus.splitlines() if z.strip()}
            for adresse in sorted(genannt):
                if adresse not in vorhanden:
                    fund("netcup", f"'{adresse}' steht auf der Seite, aber nicht in "
                                   "Mailcow. Eine Kontaktadresse, die bouncet, "
                                   "erfuellt § 5 DDG nicht")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--netcup", action="store_true",
                   help="dazu Caddy-Logging und die Mailadressen am Wirt pruefen")
    args = p.parse_args()

    if not OEFFENTLICH.is_dir():
        print(f"FEHLT: {OEFFENTLICH}", file=sys.stderr)
        return 2

    html = sorted(OEFFENTLICH.glob("*.html"))
    alle = html + sorted(OEFFENTLICH.glob("*.css"))
    index = (OEFFENTLICH / "index.html").read_text(encoding="utf-8")

    apps = katalog_apps()
    pruefe_apps(index, apps)
    for d in html:
        if d.name != "index.html":
            pruefe_apps(d.read_text(encoding="utf-8"), apps, d.name)
    pruefe_seiten(apps, inhalt_apps())
    pruefe_gebaut()
    pruefe_platzhalter(html)
    pruefe_fremde_inhalte(html)
    pruefe_verbotene_woerter(html)
    pruefe_inline_stile(html)
    pruefe_farben(OEFFENTLICH / "stil.css")
    pruefe_langer_strich(alle)
    if args.netcup:
        pruefe_netcup()

    print(f"Katalog: {len(apps)} Apps ({', '.join(n for _, n in apps)})")
    print(f"Geprueft: {len(alle)} Dateien" + (" plus netcup" if args.netcup else ""))

    if hinweise:
        print(f"\n{len(hinweise)} Hinweis(e), die nichts aufhalten:")
        for h in hinweise:
            print(f"  . {h}")

    if not fundstellen:
        print("\nKeine Funde." if hinweise else "Keine Funde.")
        return 0
    print(f"\n{len(fundstellen)} Fund(e):")
    for f in fundstellen:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
