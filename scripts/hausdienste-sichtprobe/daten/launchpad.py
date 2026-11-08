"""Erfundene Daten fuer launchpad. Keine Kachel hier stammt aus der echten control-map."""
from pathlib import Path

DOCKER = Path(__file__).resolve().parents[4]
WURZELN = [("/", DOCKER / "launchpad/static")]

GLYPHEN = ["kalender", "liste", "heft", "essen", "kiste", "zeitung", "brief", "kurve",
           "lupe", "buch", "film", "note", "bild", "schloss", "puls", "server", None]
WIRTE = ["host", "node1", "node2", "jetson", "netcup"]
GRUPPEN = ["Alltag", "Medien", "Wissen", "Zuhause", "Öffentliche Seiten", "Betrieb", "Stillgelegt"]


def kacheln():
    apps = []
    beschreibungen = ["Termine und Tagestyp", "Vorräte, Kisten und Standorte im ganzen Haus",
                      "Rezepte", "Beispielbeschreibung mit einem recht langen Nebensatz, der abgeschnitten wird"]
    for i in range(30):
        gruppe = GRUPPEN[i % 6]
        scope = "public" if gruppe == "Öffentliche Seiten" else ("wireguard" if i == 7 else "lan")
        apps.append({
            "id": f"dienst-{i}", "title": f"Beispieldienst {i}" if i % 4 else f"Langer Beispielname Nummer {i}",
            "desc": beschreibungen[i % 4], "group": gruppe, "host": WIRTE[i % 5], "scope": scope,
            "href": f"https://dienst{i}.beispiel.invalid/", "glyph": GLYPHEN[i % len(GLYPHEN)],
            "ondemand": i % 7 == 3, "expected_state": "manual" if i == 10 else "",
        })
    for i in range(2):
        apps.append({"id": f"alt-{i}", "title": f"Alter Laden {i}", "desc": "stillgelegter Beispielshop",
                     "group": "Stillgelegt", "host": "node1", "scope": "lan", "passiv": True,
                     "href": f"https://alt{i}.beispiel.invalid/", "glyph": "kiste",
                     "expected_state": "stopped",
                     "anleitung": ["Compose-Ordner öffnen", "Dienst starten", "zwei Minuten warten"]})
    return {"quelle": "control-map/services.yaml (Feld ui_url)", "gruppen": GRUPPEN,
            "eingeklappt": ["Betrieb", "Stillgelegt"], "apps": apps, "anzahl": len(apps)}


def status():
    urteile = {}
    for i in range(30):
        t = "ok"
        if i in (5, 17):
            t = "schlecht"
        elif i % 7 == 3:
            t = "wach" if i == 3 else "warn"
        elif i == 10:
            t = "warn"
        urteile[f"dienst-{i}"] = {"ton": t, "text": "Beispielzustand"}
    for i in range(2):
        urteile[f"alt-{i}"] = {"ton": "warn", "text": "bewusst aus"}
    return {"wirte": {"host": True, "node1": True, "node2": False}, "urteile": urteile,
            "leitung": True, "alter_s": 12, "verweise_alter_s": 300}


def api(methode, pfad, query, body):
    if pfad == "/api/kacheln":
        return kacheln()
    if pfad == "/api/status":
        return status()
    if pfad == "/icons/index.json":
        return {}
    if pfad == "/gast":
        return None
    return None


def oeffnen(seite):
    seite.click("button.kachel.passiv", force=True) if seite.locator("button.kachel.passiv").count() else None


def stillgelegt(seite):
    seite.click("text=Stillgelegt")
    seite.wait_for_timeout(300)
    seite.click("button.kachel.passiv")


SEITEN = [
    {"name": "start", "pfad": "/", "warten": 900},
    {"name": "suche-leer", "pfad": "/", "schritte": [lambda s: s.fill("#suchfeld", "gibtesnicht")]},
    {"name": "anleitung", "pfad": "/", "schritte": [stillgelegt]},
]
