"""Erfundene Daten fuer finanzen. Kein Betrag, kein Konto, kein Name hier stammt aus dem echten Buch.

WARUM EINE WEGWERF-INSTANZ. finanzen hat rund hundert API-Wege mit gerechneten
Antworten (Prognose, Langfrist, Zeitstrahl). Sie von Hand nachzubauen hiesse,
die Rechnung zu erfinden. Stattdessen startet dieses Modul den Dienst aus dem
Repo mit einer Temp-SQLite, befuellt ihn ueber die API mit offensichtlich
fiktiven Werten (Rezept aus interne Notiz) und reicht jede
Anfrage dorthin weiter. Die echte Datenbank liegt im Volume `finanzen-data`
und ist von hier nicht erreichbar; der Schluessel ist ein Wegwerfwert.
"""
import atexit
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

DOCKER = Path(__file__).resolve().parents[4]
REPO = DOCKER / "finanzen"
WURZELN = [("/statisch/", REPO / "app/static")]
SCHLUESSEL = "probe-wegwerf"


def _freier_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = _freier_port()
_ordner = tempfile.mkdtemp(prefix="finanzen-sichtprobe-")
_umgebung = dict(os.environ, FINANZEN_DATENBANK_URL=f"sqlite:///{_ordner}/probe.db",
                 FINANZEN_API_KEY=SCHLUESSEL, FINANZEN_KURS_ABRUF="0",
                 FINANZEN_TRUSTED_PROXIES="", FINANZEN_PAPERLESS_URL="")
_dienst = subprocess.Popen([str(REPO / ".venv/bin/uvicorn"), "app.main:app", "--host", "127.0.0.1",
                            "--port", str(PORT)], cwd=REPO, env=_umgebung,
                           stdout=subprocess.DEVNULL, stderr=open(f"{_ordner}/log", "w"))
atexit.register(_dienst.kill)


def _rufen(methode, pfad, body=None):
    daten = json.dumps(body).encode() if body is not None else None
    anfrage = urllib.request.Request(f"http://127.0.0.1:{PORT}{pfad}", data=daten, method=methode,
                                     headers={"X-API-Key": SCHLUESSEL, "Accept": "application/json",
                                              "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(anfrage, timeout=30) as a:
            return a.status, a.read(), a.headers.get("Content-Type", "application/json")
    except urllib.error.HTTPError as f:
        return f.code, f.read(), f.headers.get("Content-Type", "application/json")


for _ in range(240):
    try:
        if _rufen("GET", "/health")[0] == 200:
            break
    except OSError:
        pass
    time.sleep(0.25)
else:
    raise SystemExit(f"finanzen-Wegwerfinstanz kam nicht hoch, Protokoll {_ordner}/log")


def _post(pfad, body):
    status, roh, _ = _rufen("POST", pfad, body)
    if status >= 300:
        print(f"  befuellen {pfad}: {status} {roh[:160]!r}", file=sys.stderr)
        return {}
    return json.loads(roh or b"{}")


def befuellen():
    heute = date.today()
    erster = heute.replace(day=1)
    giro = _post("/api/konten", {"name": "Beispiel-Giro", "art": "giro", "eroeffnungssaldo": "1234,56",
                                  "untergrenze_cent": -50_000}).get("id")
    spar = _post("/api/konten", {"name": "Beispiel-Sparbuch", "art": "spar",
                                  "eroeffnungssaldo": "4321,00"}).get("id")
    kat = {}
    for name, art, fix in [("Wohnen", "ausgabe", True), ("Lebensmittel", "ausgabe", False),
                           ("Freizeit", "ausgabe", False), ("Mobilität", "ausgabe", False),
                           ("Gehalt", "einnahme", True)]:
        kat[name] = _post("/api/kategorien", {"name": name, "art": art, "fix": fix}).get("id")
    for name, betrag in [("Lebensmittel", "350,00"), ("Freizeit", "120,00"), ("Mobilität", "80,00")]:
        _post("/api/budgets", {"kategorie_id": kat[name], "betrag": betrag, "gueltig_ab": erster.isoformat()})
    _post("/api/dauerauftraege", {"name": "Beispielgehalt", "konto_id": giro, "art": "einnahme",
                                  "betrag": "2222,22", "kadenz": "monatlich", "start": erster.isoformat(),
                                  "kategorie_id": kat["Gehalt"]})
    _post("/api/dauerauftraege", {"name": "Miete Musterstraße 1", "konto_id": giro, "art": "ausgabe",
                                  "betrag": "777,77", "kadenz": "monatlich", "start": erster.isoformat(),
                                  "kategorie_id": kat["Wohnen"]})
    _post("/api/dauerauftraege", {"name": "Beispiel-Streamingabo mit recht langem Namen", "konto_id": giro,
                                  "art": "ausgabe", "betrag": "9,99", "kadenz": "monatlich",
                                  "start": erster.isoformat(), "kategorie_id": kat["Freizeit"]})
    zwecke = [("Supermarkt Beispiel", "Lebensmittel", "43,21"), ("Bäckerei Muster", "Lebensmittel", "6,40"),
              ("Kino Beispielstadt", "Freizeit", "24,00"), ("Tankstelle Beispiel", "Mobilität", "61,50"),
              ("Wochenmarkt", "Lebensmittel", "18,75"), ("Buchladen Muster", "Freizeit", "29,90")]
    for i in range(18):
        zweck, k, betrag = zwecke[i % len(zwecke)]
        _post("/api/buchungen", {"konto_id": giro, "art": "ausgabe", "betrag": betrag,
                                 "datum": (heute - timedelta(days=i * 3)).isoformat(),
                                 "zweck": zweck, "kategorie_id": kat[k]})
    _post("/api/buchungen", {"konto_id": giro, "art": "umbuchung", "betrag": "100,00", "gegenkonto_id": spar,
                             "datum": (heute - timedelta(days=2)).isoformat(), "zweck": "Sparen"})
    _post("/api/sparziele", {"name": "Beispielurlaub", "zielbetrag": "1500,00", "angespart": "300,00",
                             "zieldatum": (heute + timedelta(days=300)).isoformat()})
    _post("/api/sparziele", {"name": "Neues Fahrrad", "zielbetrag": "900,00"})
    _post("/api/vertraege", {"name": "Beispiel-Handyvertrag", "anbieter": "Muster Mobil GmbH",
                             "beginn": "2025-03-01", "mindestlaufzeit_monate": 24, "verlaengerung_monate": 12,
                             "frist_wert": 1, "frist_einheit": "monate"})
    _post("/api/kredite", {"name": "Beispielkredit", "art": "annuitaet", "konto_id": giro,
                           "restschuld": "3000,00", "zins_prozent": "4", "laufzeit_monate": 24,
                           "erste_rate": (erster + timedelta(days=40)).replace(day=1).isoformat()})
    _post("/api/depot/papiere", {"name": "Beispiel-Weltfonds", "symbol": "BSP.INVALID", "stueck": "12,345"})
    _post("/api/sachwerte", {"name": "Beispielauto", "anschaffung": "8000,00",
                             "angeschafft_am": "2022-01-01", "wertverlauf_prozent": "-15"})
    _post("/api/forderungen", {"schuldner": "Erika Beispiel", "betrag": "50,00",
                               "verliehen_am": (heute - timedelta(days=20)).isoformat()})
    mensch = _post("/api/beschenkte", {"name": "Max Muster", "geburtstag": "1990-06-15",
                                       "beziehung": "Freund"}).get("id")
    if mensch:
        _post("/api/anlassbudgets", {"beschenkter_id": mensch, "anlass": "geburtstag", "betrag": "25,00"})


befuellen()


def api(methode, pfad, query, body):
    if pfad.startswith("/statisch/"):
        return None
    if pfad == "/favicon.ico":
        return Antwort(204, b"", "image/x-icon")
    voll = pfad + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else "")
    if isinstance(body, str):
        body = json.loads(body) if body else None
    status, roh, typ = _rufen(methode, voll, body)
    return Antwort(status, roh, typ)


def reiter(name):
    def schritt(seite):
        seite.evaluate(f"reiterWechsel('{name}')")
        seite.wait_for_timeout(700)
    return schritt


def mehr_oeffnen(seite):
    if seite.locator("#mehr-knopf").is_visible():
        seite.click("#mehr-knopf")


SEITEN = [{"name": "lage", "pfad": "/", "warten": 1200}] + [
    {"name": n, "pfad": "/", "schritte": [reiter(n)], "warten": 900}
    for n in ["zeitstrahl", "buch", "posten", "budgets", "wuensche", "depot", "besitz",
              "langfrist", "planung", "jahr"]
] + [{"name": "mehr-blatt", "pfad": "/", "schritte": [mehr_oeffnen]}]


def mehr_zu_pruefen(seite):
    """× schliesst, Escape schliesst, der Fokus steht danach auf „Mehr“."""
    if not seite.locator("#mehr-knopf").is_visible():
        return
    seite.click("#mehr-knopf")
    seite.click("#mehr-zu")
    a = seite.evaluate("[document.getElementById('mehr-blatt').hidden, document.activeElement.id]")
    seite.click("#mehr-knopf")
    seite.keyboard.press("Escape")
    b = seite.evaluate("[document.getElementById('mehr-blatt').hidden, document.activeElement.id]")
    if a != [True, "mehr-knopf"] or b != [True, "mehr-knopf"]:
        raise AssertionError(f"Mehr-Blatt schliesst falsch: x={a} esc={b}")
    seite.click("#mehr-knopf")


SEITEN.append({"name": "mehr-zu", "pfad": "/", "schritte": [mehr_zu_pruefen]})
