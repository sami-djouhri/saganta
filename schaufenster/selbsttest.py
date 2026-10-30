#!/usr/bin/env python3
"""Prueft, ob `abgleich.py` ueberhaupt anschlaegt.

Ein Pruefer, der immer gruen meldet, sieht genauso aus wie einer, der nichts zu
meckern hat. Deshalb bekommt hier jede Pruefung einen Fall, den sie finden MUSS,
und einen, bei dem sie schweigen muss. Faellt eine Zeile aus `abgleich.py` weg,
wird hier genau ein Fall rot, statt dass die Auslieferung still durchlaeuft.

Reine Standardbibliothek, laeuft auf dem Wirt ohne pytest:
    python3 selbsttest.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import abgleich

APPS = [("a", "Kalender"), ("b", "Notizen"), ("c", "Post")]

faelle = 0
fehler: list[str] = []


def laeuft(name: str, fn, erwartet_fund: bool) -> None:
    """Fuehrt eine Pruefung aus und vergleicht mit der Erwartung."""
    global faelle
    faelle += 1
    abgleich.fundstellen.clear()
    fn()
    hat_fund = bool(abgleich.fundstellen)
    if hat_fund != erwartet_fund:
        soll = "einen Fund" if erwartet_fund else "Schweigen"
        ist = f"{len(abgleich.fundstellen)} Fund(e)" if hat_fund else "Schweigen"
        fehler.append(f"{name}: erwartet {soll}, bekommen {ist}")


def laeuft_hinweis(name: str, fn, erwartet_hinweis: bool) -> None:
    """Dasselbe fuer die Meldungen, die nichts aufhalten."""
    global faelle
    faelle += 1
    abgleich.hinweise.clear()
    abgleich.fundstellen.clear()
    fn()
    hat = bool(abgleich.hinweise)
    if hat != erwartet_hinweis:
        soll = "einen Hinweis" if erwartet_hinweis else "Schweigen"
        ist = f"{len(abgleich.hinweise)} Hinweis(e)" if hat else "Schweigen"
        fehler.append(f"{name}: erwartet {soll}, bekommen {ist}")
    if abgleich.fundstellen:
        fehler.append(f"{name}: hat einen FUND erzeugt, darf aber nur hinweisen")


def mit_datei(inhalt: str, endung: str = ".html"):
    """Schreibt einen Text in eine Wegwerfdatei und gibt sie als Liste zurueck."""
    d = Path(tempfile.mkdtemp()) / f"index{endung}"
    d.write_text(inhalt, encoding="utf-8")
    return [d]


def zeile(name: str) -> str:
    return f'<li><span class="name">{name}</span><span class="was">x</span></li>'


# --- App-Seiten und Bilder (seit 2026-10-30) ---------------------------------


def mit_seiten(namen: list[str], bilder: list[str]) -> Path:
    w = Path(tempfile.mkdtemp())
    (w / "bilder").mkdir()
    for n in namen:
        (w / f"{n}.html").write_text("x", encoding="utf-8")
    for b in bilder:
        (w / "bilder" / f"{b}.webp").write_bytes(b"x")
    return w


SEITEN = [{"id": i, "name": n, "seite": n.lower()} for i, n in APPS]
ALLE = [s["seite"] for s in SEITEN]

laeuft("Seiten und Bilder vollstaendig",
       lambda: abgleich.pruefe_seiten(APPS, SEITEN, mit_seiten(ALLE, ALLE + ["uebersicht"])),
       False)
laeuft("ein App-Bild fehlt",
       lambda: abgleich.pruefe_seiten(APPS, SEITEN, mit_seiten(ALLE, ALLE[1:] + ["uebersicht"])),
       True)
laeuft("das Bild der Uebersicht fehlt",
       lambda: abgleich.pruefe_seiten(APPS, SEITEN, mit_seiten(ALLE, ALLE)),
       True)
laeuft("eine App-Seite fehlt",
       lambda: abgleich.pruefe_seiten(APPS, SEITEN, mit_seiten(ALLE[1:], ALLE + ["uebersicht"])),
       True)
laeuft("App im Katalog ohne Seite",
       lambda: abgleich.pruefe_seiten(APPS, SEITEN[1:], mit_seiten(ALLE, ALLE + ["uebersicht"])),
       True)
laeuft("Seite ohne App im Katalog",
       lambda: abgleich.pruefe_seiten(APPS[1:], SEITEN, mit_seiten(ALLE, ALLE + ["uebersicht"])),
       True)
laeuft("Name weicht vom Katalog ab",
       lambda: abgleich.pruefe_seiten(
           APPS, [dict(SEITEN[0], name="Termine")] + SEITEN[1:],
           mit_seiten(ALLE, ALLE + ["uebersicht"])),
       True)
laeuft("Zaehlstand auf einer Unterseite",
       lambda: abgleich.pruefe_apps("Vier der Apps gibt es auch so.", APPS, "telefon.html"),
       True)
laeuft("Unterseite ohne Zahl",
       lambda: abgleich.pruefe_apps("Kalender und Notizen gibt es auch so.", APPS, "telefon.html"),
       False)


# --- App-Deckung und Anzahl ------------------------------------------------

vollstaendig = "Drei Apps. " + "".join(zeile(n) for _, n in APPS)

laeuft("Deckung vollstaendig", lambda: abgleich.pruefe_apps(vollstaendig, APPS), False)
laeuft(
    "App fehlt auf der Seite",
    lambda: abgleich.pruefe_apps("Drei Apps. " + zeile("Kalender") + zeile("Notizen"), APPS),
    True,
)
laeuft(
    "App zuviel auf der Seite",
    lambda: abgleich.pruefe_apps(vollstaendig + zeile("Wetter"), APPS),
    True,
)
laeuft(
    "App doppelt",
    lambda: abgleich.pruefe_apps(vollstaendig + zeile("Post"), APPS),
    True,
)
laeuft(
    "Anzahl als Wort falsch",
    lambda: abgleich.pruefe_apps("Vier Apps. " + "".join(zeile(n) for _, n in APPS), APPS),
    True,
)
laeuft(
    "Anzahl als Ziffer falsch",
    lambda: abgleich.pruefe_apps("12 Apps. " + "".join(zeile(n) for _, n in APPS), APPS),
    True,
)
# Die Falle, wegen der der Anriss umformuliert wurde: eine zweite Rechnung mit
# einem Wort zwischen Zahl und Hauptwort. "sieben weitere Apps" neben drei
# aufgefuehrten ist falsch, und ein Muster ohne das Zwischenwort uebersieht es.
laeuft(
    "zweite Rechnung im Fliesstext",
    lambda: abgleich.pruefe_apps(
        "Drei Apps. Kalender und sieben weitere Apps. " + "".join(zeile(n) for _, n in APPS),
        APPS,
    ),
    True,
)
laeuft(
    "Zahlwort mit Umlaut richtig",
    lambda: abgleich.pruefe_apps(
        "Zwölf Apps. " + "".join(zeile(f"A{i}") for i in range(12)),
        [(f"id{i}", f"A{i}") for i in range(12)],
    ),
    False,
)
laeuft(
    "kein Zahlwort vor Apps ist in Ordnung",
    lambda: abgleich.pruefe_apps(
        "Die übrigen Apps. " + "".join(zeile(n) for _, n in APPS), APPS
    ),
    False,
)

# --- Platzhalter ----------------------------------------------------------

laeuft("ohne Platzhalter", lambda: abgleich.pruefe_platzhalter(mit_datei("<p>Musterstr. 1</p>")), False)
laeuft(
    "mit Platzhalter",
    lambda: abgleich.pruefe_platzhalter(mit_datei("<p>PLATZHALTER: Strasse</p>")),
    True,
)

# --- Fremde Inhalte -------------------------------------------------------

laeuft(
    "nur erlaubte fremde Adresse",
    lambda: abgleich.pruefe_fremde_inhalte(
        mit_datei('<a href="https://djouhri.de">x</a><a href="impressum.html">y</a>')
    ),
    False,
)
laeuft(
    "fremde Adresse",
    lambda: abgleich.pruefe_fremde_inhalte(mit_datei('<img src="https://example.org/a.png">')),
    True,
)
laeuft(
    "Google Fonts",
    lambda: abgleich.pruefe_fremde_inhalte(
        mit_datei('<link href="https://fonts.googleapis.com/css?family=Inter">')
    ),
    True,
)
laeuft(
    "script-Element",
    lambda: abgleich.pruefe_fremde_inhalte(mit_datei("<script>var a=1</script>")),
    True,
)
laeuft(
    "Cookie",
    lambda: abgleich.pruefe_fremde_inhalte(mit_datei("<p>document.cookie</p>")),
    True,
)
laeuft(
    "Formular",
    lambda: abgleich.pruefe_fremde_inhalte(mit_datei('<form action="/x"><input></form>')),
    True,
)
laeuft(
    "iframe",
    lambda: abgleich.pruefe_fremde_inhalte(mit_datei("<iframe></iframe>")),
    True,
)
# Das Wort "form" im Fliesstext darf nicht anschlagen. Ein Muster ohne die
# Zeichenklasse dahinter faengt jedes "<formular" und jedes "<format".
laeuft(
    "das Wort Formular im Text ist kein Element",
    lambda: abgleich.pruefe_fremde_inhalte(mit_datei("<p>kein Kontaktformular</p>")),
    False,
)

# --- Reste des abgeschafften Produkts -------------------------------------

laeuft(
    "ohne Produktreste",
    lambda: abgleich.pruefe_verbotene_woerter(mit_datei("<p>Lizenz auf Anfrage</p>")),
    False,
)
laeuft(
    "Tarif erwaehnt",
    lambda: abgleich.pruefe_verbotene_woerter(mit_datei("<p>Im Tarif Unlimited</p>")),
    True,
)
laeuft(
    "Verweis auf /login",
    lambda: abgleich.pruefe_verbotene_woerter(mit_datei('<a href="/login">Anmelden</a>')),
    True,
)

# --- Inline-Stile ---------------------------------------------------------

laeuft(
    "ohne Inline-Stil",
    lambda: abgleich.pruefe_inline_stile(mit_datei('<p class="leise">x</p>')),
    False,
)
laeuft(
    "mit Inline-Stil",
    lambda: abgleich.pruefe_inline_stile(mit_datei('<p style="margin-top: 1rem">x</p>')),
    True,
)
# Das SVG im Seitenkopf traegt Praesentationsattribute (fill, stroke). Die sind
# keine Inline-Stile und von der CSP nicht betroffen; wer sie mitfaengt, erzeugt
# auf jeder Seite einen Fund und macht die Pruefung unbrauchbar.
laeuft(
    "SVG-Attribute sind kein Inline-Stil",
    lambda: abgleich.pruefe_inline_stile(
        mit_datei('<svg><circle cx="69" cy="27" r="6" fill="currentColor" /></svg>')
    ),
    False,
)

# --- Langer Gedankenstrich ------------------------------------------------

laeuft(
    "ohne langen Strich",
    lambda: abgleich.pruefe_langer_strich(mit_datei("<p>eins, zwei: drei</p>")),
    False,
)
laeuft(
    "mit langem Strich",
    lambda: abgleich.pruefe_langer_strich(mit_datei(f"<p>eins {chr(0x2014)} zwei</p>")),
    True,
)
laeuft(
    "mit HTML-Entitaet dafuer",
    lambda: abgleich.pruefe_langer_strich(mit_datei("<p>eins &mdash; zwei</p>")),
    True,
)

# --- Farbdeckung gegen die Design-Tokens ----------------------------------

TOKEN_TEXT = """
:root {
  --hell-surface: 245 240 232;
  --dunkel-surface: 22 19 15;
  --dunkel-akzent: 229 180 103;
  --color-accent-400: #dd9c3f;
}
"""


def mit_tokens(stil_text: str, token_text: str = TOKEN_TEXT):
    """Schreibt Tokens und Stylesheet in ein Wegwerfverzeichnis und zeigt
    `abgleich.TOKENS` darauf. Die Funktion liest den Pfad aus dem Modul, also
    muss er hier gesetzt werden und nicht als Argument wandern."""
    ordner = Path(tempfile.mkdtemp())
    tokens = ordner / "theme.css"
    tokens.write_text(token_text, encoding="utf-8")
    stil = ordner / "stil.css"
    stil.write_text(stil_text, encoding="utf-8")
    abgleich.TOKENS = tokens
    return stil


DECKEND = """
:root {
  --surface: rgb(22 19 15);
  --akzent: rgb(229 180 103);
  --marke: #dd9c3f;
}
@media (prefers-color-scheme: light) {
  :root {
    --surface: rgb(245 240 232);
  }
}
"""

laeuft_hinweis(
    "Farben deckungsgleich",
    lambda: abgleich.pruefe_farben(mit_tokens(DECKEND)),
    False,
)
laeuft_hinweis(
    "eine Farbe verschoben",
    lambda: abgleich.pruefe_farben(
        mit_tokens(DECKEND.replace("rgb(229 180 103)", "rgb(221 154 60)"))
    ),
    True,
)
# Das helle Theme steht in der Media-Query. Wer am falschen Ort vergleicht,
# haelt den hellen Grund fuer den dunklen und meldet jede Seite als abweichend.
laeuft_hinweis(
    "helles Theme wird gegen die hellen Tokens geprueft",
    lambda: abgleich.pruefe_farben(
        mit_tokens(DECKEND.replace("--surface: rgb(245 240 232)", "--surface: rgb(1 2 3)"))
    ),
    True,
)
# Ein Muster, das nichts mehr trifft, ist gefaehrlicher als eine Abweichung:
# es meldet Deckung, weil es nichts gefunden hat.
laeuft_hinweis(
    "null Treffer meldet sich selbst",
    lambda: abgleich.pruefe_farben(mit_tokens(":root { color: red; }")),
    True,
)

# --- Ergebnis -------------------------------------------------------------

print(f"{faelle} Faelle geprueft")
if fehler:
    print(f"\n{len(fehler)} davon falsch:")
    for f in fehler:
        print(f"  - {f}")
    sys.exit(1)
print("Alle Pruefungen schlagen an, wenn sie sollen, und schweigen, wenn sie sollen.")
