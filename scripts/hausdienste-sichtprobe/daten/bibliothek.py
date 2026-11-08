"""Erfundene Daten fuer bibliothek. Kein Titel, kein Verfasser und kein Profil stammt aus dem Bestand.

Die Seiten sind Jinja-Vorlagen; sie werden hier mit erfundenem Kontext gerendert.
Der Band im Leser ist ein kleines, hier gebautes EPUB mit erfundenem Text.
"""
import io
import zipfile
from pathlib import Path

import sys

try:
    import jinja2
except ImportError:  # das medien-venv hat kein jinja2, das System schon
    sys.path.append("/usr/lib/python3/dist-packages")
    import jinja2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

DOCKER = Path(__file__).resolve().parents[4]
WURZEL = DOCKER / "bibliothek"
WURZELN = [("/static/", WURZEL / "static")]

UMGEBUNG = jinja2.Environment(loader=jinja2.FileSystemLoader(str(WURZEL / "vorlagen")),
                              autoescape=True)

BAENDCHEN = [
    {"name": "Krapprot", "schluessel": "krapp", "ton": "#A8243A"},
    {"name": "Indigo", "schluessel": "indigo", "ton": "#2D4A7C"},
    {"name": "Moos", "schluessel": "moos", "ton": "#3F6B45"},
]
PROFIL = {"id": "11111111-1111-4111-8111-111111111111", "name": "Beispielleser",
          "baendchen": "indigo", "ton": "#2D4A7C", "einstellungen": {}}
PROFILE = [PROFIL, {"id": "22222222-2222-4222-8222-222222222222", "name": "Zweites Profil",
                    "baendchen": "moos", "ton": "#3F6B45", "einstellungen": {}}]

UUID = "aaaaaaaa-0000-4000-8000-{:012d}"


def band(i):
    return {"id": UUID.format(i), "titel": f"Erfundener Roman Nummer {i} mit einem etwas längeren Titel"
            if i % 3 == 0 else f"Beispielband {i}", "autoren": f"Erika Muster{i % 4}",
            "reihe": "Beispielreihe" if i % 5 == 0 else None, "reihe_nr": 2 if i % 5 == 0 else None,
            "umschlag": False, "format": "EPUB", "fortschritt": 0.4 if i == 2 else (0.97 if i == 4 else 0)}


def einstieg():
    return {
        "abteilungen": [{"id": f"ab{i}", "name": n, "baende": 10 + i} for i, n in
                        enumerate(["Romane", "Geschichte", "Naturkunde", "Lyrik", "Reisen"])],
        "umfaenge": [{"schluessel": "kurz", "name": "Ein Abend", "baende": 30, "minuten_bis": 180},
                     {"schluessel": "mittel", "name": "Ein Wochenende", "baende": 40, "minuten_bis": 600},
                     {"schluessel": "lang", "name": "Länger", "baende": 20, "minuten_bis": None}],
        "verfasser": [{"id": f"v{i}", "name": f"Erika Muster{i}", "baende": 3} for i in range(6)],
        "verfasser_gesamt": 40,
        "reihen": [{"id": "r1", "name": "Beispielreihe", "vorhanden": 2, "soll": 5}],
        "sprachen": [{"sprache": "deu", "name": "Deutsch", "baende": 90}],
        "buchstaben": [{"buchstabe": b, "baende": 4} for b in "ABCDEFGHIKLMNOPRSTUVWZ"],
        "vorschlag": {"band": band(7), "grund": "Aus derselben Abteilung wie dein letzter Band."},
    }


def epub():
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/inhalt.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>""")
        z.writestr("OEBPS/inhalt.opf", """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">beispiel</dc:identifier>
<dc:title>Beispielband</dc:title><dc:language>de</dc:language></metadata>
<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="k1" href="k1.xhtml" media-type="application/xhtml+xml"/></manifest>
<spine><itemref idref="k1"/></spine></package>""")
        z.writestr("OEBPS/nav.xhtml", """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Inhalt</title></head>
<body><nav epub:type="toc"><ol><li><a href="k1.xhtml">Erstes Kapitel</a></li></ol></nav></body></html>""")
        absatz = ("Dies ist ein erfundener Absatz für die Sichtprobe. Er erzählt nichts, er füllt nur "
                  "die Seite, damit Satz, Ränder und Leisten zu sehen sind. ") * 4
        z.writestr("OEBPS/k1.xhtml", f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Erstes Kapitel</title></head>
<body><h1>Erstes Kapitel</h1>{''.join(f'<p>{absatz}</p>' for _ in range(12))}</body></html>""")
    return puffer.getvalue()


def api(methode, pfad, query, body):
    if pfad == "/":
        return UMGEBUNG.get_template("regal.html").render(
            profil=None if query.get("ohne") else PROFIL, profile=PROFILE, baendchen=BAENDCHEN,
            bestand={"baende": 96}, portal_url="https://wissen.beispiel.invalid", stoerung=None)
    if pfad.startswith("/buch/"):
        b = band(3)
        profil = PROFIL
        if query.get("papier"):  # ein frueher gespeichertes Papier, etwa ein helles
            profil = dict(PROFIL, einstellungen={"papier": query["papier"]})
        return UMGEBUNG.get_template("leser.html").render(
            profil=profil, baendchen=BAENDCHEN, band=b,
            stand={"ort": None, "kapitel": "Erstes Kapitel", "zuletzt": 1, "wann": "gestern",
                   "fortschritt": 0.2, "spannen": []} if query.get("stand") else None,
            stelle=None, vorraetig=False)
    if pfad == "/api/regal":
        if query.get("q") == "gibtesnicht":
            return {"gesamt": 0, "baende": []}
        return {"gesamt": 96, "baende": [band(i) for i in range(24)]}
    if pfad == "/api/stellen":
        if query.get("q") == "gibtesnicht":
            return {"treffer": [], "stellen_index": {"rueckstand": 3, "aktive_ausgaben": 96}}
        return {"treffer": [{"id": UUID.format(1), "titel": "Beispielband 1", "autoren": "Erika Muster1",
                             "stelle": {"ort": "epubcfi(/6/2)", "kapitel": "Zweites Kapitel",
                                        "schnipsel": "ein erfundener Satz mit «Beispiel» darin"}}]}
    if pfad == "/api/einstieg":
        return einstieg()
    if pfad == "/api/leseliste":
        return {"baende": [dict(band(2), stand={"kapitel": "Drittes Kapitel", "fortschritt": 0.4,
                                                 "wann": "vor 3 Tagen"})]}
    if pfad == "/api/profile" and methode == "GET":
        return {"profile": [dict(p, offen=1) for p in PROFILE], "baendchen": BAENDCHEN, "aktiv": PROFIL}
    if pfad == "/api/wecken":
        return {"ok": True}
    if pfad == "/api/geraete":
        return {"geraete": [{"id": "g1", "name": "Beispieltablet", "zuletzt": None, "downloads": 2,
                             "widerrufen": None}]}
    if pfad == "/api/dienste":
        return {"vorlesen": {"bereit": True}}
    if pfad.startswith("/api/marken/"):
        return []
    if pfad.startswith("/api/stand/"):
        return {"ok": True}
    if pfad.startswith("/api/profile/"):
        return {"ok": True}
    if pfad.startswith("/datei/"):
        return Antwort(200, epub(), "application/epub+zip")
    if pfad.startswith("/umschlag/"):
        return Antwort(404, b"", "image/webp")
    if pfad == "/sw.js":
        return Antwort(200, b"", "text/javascript")
    if pfad == "/manifest.webmanifest":
        return Antwort(200, (WURZEL / "static/manifest.webmanifest").read_bytes(), "application/manifest+json")
    return None


def suchen(text):
    def schritt(seite):
        seite.fill("#suchfeld", text)
        seite.wait_for_timeout(700)
    return schritt


def aufschlagen(seite):
    # Der Leser schlaegt von selbst auf (buchOeffnen am Ende von leser.js).
    seite.wait_for_timeout(2500)


def satz(seite):
    aufschlagen(seite)
    seite.click("#knopf-satz")
    seite.wait_for_timeout(500)


SEITEN = [
    {"name": "regal", "pfad": "/", "warten": 800},
    {"name": "suche-leer", "pfad": "/", "schritte": [suchen("gibtesnicht")]},
    {"name": "suche", "pfad": "/", "schritte": [suchen("Beispiel")]},
    {"name": "profilwahl", "pfad": "/?ohne=1", "warten": 800},
    {"name": "geraete", "pfad": "/", "schritte": [lambda s: s.click("#profil-knopf"),
                                                   lambda s: s.click("#geraete-knopf")]},
    {"name": "leser", "pfad": "/buch/" + UUID.format(3), "schritte": [aufschlagen]},
    {"name": "leser-satz", "pfad": "/buch/" + UUID.format(3), "schritte": [satz]},
    {"name": "leser-schwarz", "pfad": "/buch/" + UUID.format(3),
     "schritte": [aufschlagen, lambda s: s.click("#knopf-nacht")]},
    {"name": "leser-alt-hell", "pfad": "/buch/" + UUID.format(3) + "?papier=abend", "schritte": [aufschlagen]},
]
