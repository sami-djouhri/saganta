"""Erfundene Daten fuer wissen. Kein Titel hier stammt aus dem echten Bestand."""
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

DOCKER = Path(__file__).resolve().parents[4]
WURZELN = [("/", DOCKER / "wissen/static")]


def treffer(n):
    quellen = ["kiwix", "books", "anleitungen", "lernen", "obsidian-memory", "orte"]
    return [{"source": quellen[i % len(quellen)], "type": "artikel",
             "title": f"Beispielartikel {i + 1}: Entkalken mit Zitronensäure und Essig im Vergleich",
             "url": f"/beispiel/{i}" if i % 3 else None,
             "snippet": "Erfundener Auszug. Zitronensäure löst Kalk schonender als Essig, "
                        "riecht nicht und greift Dichtungen weniger an. Einwirken lassen, ausspülen.",
             "extra": {"book": "Haushalt von A bis Z"} if i == 1 else {}} for i in range(n)]


def sse(*ereignisse):
    return "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in ereignisse)


def api(methode, pfad, query, body):
    if pfad == "/api/sources":
        return {"available": ["kiwix", "books", "anleitungen", "lernen", "obsidian-memory", "orte"]}
    if pfad == "/api/modell":
        return {"modell": "Beispielmodell-4B-Q4_K_M.gguf"}
    if pfad == "/api/bibliothek/regal":
        return {"gesamt": 1234, "basis": "https://bibliothek.beispiel.invalid"}
    if pfad == "/api/aufwecken":
        return {"ok": True}
    if pfad == "/api/bookmarks" and methode == "GET":
        return [dict(t, id=i + 1) for i, t in enumerate(treffer(3))]
    if pfad == "/api/bookmarks":
        return {"id": 99}
    if pfad == "/api/antwort/stream":
        t = treffer(9)
        text = ("Am einfachsten mit Zitronensäure [1]: zwei Esslöffel in Wasser lösen, aufkochen, "
                "eine halbe Stunde stehen lassen und gründlich spülen [2]. Essig wirkt auch, "
                "riecht aber länger nach [3].")
        body = sse(("treffer", {"results": t}),
                   ("begriff", {"begriff": "Entkalken", "definition": {
                       "titel": "Entkalken", "text": "Entfernen von Kalkablagerungen aus Geräten und Leitungen.",
                       "source": "kiwix", "url": "/beispiel/def"}}),
                   ("belege", {"belege": t[:3]}),
                   ("token", {"text": text}),
                   ("antwort", {"text_geprueft": text, "status": "ok"}))
        return Antwort(200, body.encode(), "text/event-stream")
    if pfad.startswith("/api/crosscheck"):
        return {"bewertung": "stimmig", "widersprueche": []}
    return None


def suchen(seite):
    seite.fill("#q", "Wie entkalke ich den Wasserkocher?")
    seite.press("#q", "Enter")
    seite.wait_for_timeout(800)


SEITEN = [
    {"name": "start", "pfad": "/"},
    {"name": "antwort", "pfad": "/", "schritte": [suchen]},
    {"name": "merkliste", "pfad": "/", "schritte": [lambda s: s.click("[data-tab=marks]")]},
]
