"""Erfundene Daten fuer medien. Kein Titel, kein Name hier stammt aus dem echten Bestand.

WIE. Wie `werkzeug/probe-instanz.sh`, nur ohne dessen Probe: eine Wegwerf-Instanz
aus dem Repo mit Temp-SQLite, Pruef-Vault aus `tests/test_werke.py`, Bestand aus
`tests/mappe.py` und die kiwix-Attrappe. Der echte Bestand (Volume `medien-data`)
und der Medien-Vault sind von hier nicht erreichbar.

Die Testdaten tragen bekannte Film- und Personennamen. Regel fuer
medien: auch Titel sind tabu, im Bild stehen nur Fantasie-Titel. Jede Antwort
geht deshalb durch `UMBENENNEN` (Hin- und Rueckweg), und `pruefen()` meldet,
wenn ein Name aus der Liste doch durchkommt.
"""
import atexit
import gzip
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from probe import Antwort  # noqa: E402

DOCKER = Path(__file__).resolve().parents[4]
REPO = DOCKER / "medien"
WURZELN = [("/statisch/", REPO / "app/static")]

UMBENENNEN = [
    ("Pirates of the Caribbean: The Curse of the Black Pearl", "The Lantern Isles"),
    ("Pirates of the Caribbean - Fluch der Karibik", "Die Laterneninseln - Erster Teil"),
    ("Pirates des Caraibes", "Les Îles aux Lanternes"),
    ("Fluch der Karibik", "Die Laterneninseln"),
    ("Two and a Half Men", "Die Leuchtturmwärter"),
    ("Fantastic Four", "Die Gläsernen Vier"),
    ("Red Dawn", "Rotes Moor"),
    ("Getaway", "Fernweh-Express"),
    ("Doctor Who", "Die Uhrmacherin"),
    ("Keinohrhasen", "Mondscheinkaninchen"),
    ("Zweiohrküken", "Sternschnuppenküken"),
    ("Breaking Bad", "Kreidezeit"),
    ("Heat", "Nebelhafen"),
    ("Michael Mann", "Ilse Beispiel"),
    ("Al Pacino", "Otto Muster"),
    ("Robert De Niro", "Hanna Probe"),
    ("Gore Verbinski", "Karl Erfunden"),
    ("Johnny Depp", "Lena Fiktiv"),
    ("Bryan Cranston", "Paul Platzhalter"),
    ("Tobi", "Bernd Beispiel"),
]


def _ersetzen(text, paare):
    for alt, neu in paare:
        for a, n in ((alt, neu), (alt.replace(" ", "_"), neu.replace(" ", "_")),
                     (urllib.parse.quote(alt), urllib.parse.quote(neu))):
            text = re.sub(rf"(?<![\w]){re.escape(a)}(?![\w])", n, text)
    return text


def hin(text):
    return _ersetzen(text, UMBENENNEN)


def zurueck(text):
    return _ersetzen(text, [(n, a) for a, n in UMBENENNEN])


def _freier_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_ordner = Path(tempfile.mkdtemp(prefix="medien-sichtprobe-"))
(_ordner / "bilder").mkdir()
PORT, KIWIX = _freier_port(), _freier_port()
PY = str(REPO / ".venv/bin/python")
_prozesse = []
atexit.register(lambda: [p.kill() for p in _prozesse])

_prozesse.append(subprocess.Popen([PY, "werkzeug/kiwix-attrappe.py", str(KIWIX)], cwd=REPO,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
_umgebung = dict(os.environ, MEDIEN_KIWIX_URL=f"http://127.0.0.1:{KIWIX}",
                 MEDIEN_WERKE_DATEI=str(_ordner / "werke.sqlite"), MEDIEN_WIKI_ORDNER=str(_ordner / "wiki"),
                 MEDIEN_DATENBANK_URL=f"sqlite:///{_ordner}/probe.db", MEDIEN_TRUSTED_PROXIES="127.0.0.0/8",
                 MEDIEN_API_KEY="probe-wegwerf", MEDIEN_BILDER=str(_ordner / "bilder"), MEDIEN_ABGLEICH="0",
                 WERKE_ZIEL=str(_ordner / "werke.sqlite"))
subprocess.run([PY, "-c", """
import gzip, os, sys, tempfile
sys.path.insert(0, ".")
from tests.test_werke import DATEIEN
quelle = tempfile.mkdtemp()
for name, zeilen in DATEIEN.items():
    with gzip.open(os.path.join(quelle, name), "wt", encoding="utf-8") as f:
        f.writelines("\\t".join(z) + "\\n" for z in zeilen)
import app.werke as werke
werke.QUELLE = quelle
werke.bauen(os.environ["WERKE_ZIEL"], eigene=set(), melde=lambda _t: None)
"""], cwd=REPO, env=_umgebung, check=True, stdout=subprocess.DEVNULL)
_prozesse.append(subprocess.Popen([str(REPO / ".venv/bin/uvicorn"), "app.main:app", "--host", "127.0.0.1",
                                   "--port", str(PORT)], cwd=REPO, env=_umgebung,
                                  stdout=subprocess.DEVNULL, stderr=open(_ordner / "log", "w")))


def _rufen(methode, pfad, body=None, typ="application/json"):
    anfrage = urllib.request.Request(f"http://127.0.0.1:{PORT}{pfad}", data=body, method=methode,
                                     headers={"Remote-User": "erika.beispiel", "Content-Type": typ})
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
    raise SystemExit(f"medien-Wegwerfinstanz kam nicht hoch, Protokoll {_ordner}/log")
# Bestand erst nach dem Start: die Instanz legt die Tabellen an (wie probe-instanz.sh).
subprocess.run([PY, "-c", "import sys; sys.path.insert(0, '.'); from app.ruecksicherung import zuruecklesen; "
                "from tests import mappe; zuruecklesen(mappe.sicherung())"],
               cwd=REPO, env=_umgebung, check=True, stdout=subprocess.DEVNULL)

DURCHGEKOMMEN = set()


def api(methode, pfad, query, body):
    if pfad.startswith("/statisch/"):
        return None
    if pfad == "/sw.js":
        return Antwort(200, (REPO / "app/static/sw.js").read_bytes(), "text/javascript")
    voll = zurueck(pfad) + ("?" + urllib.parse.urlencode({k: zurueck(v) for k, v in query.items()})
                            if query else "")
    roh = None
    if body is not None:
        roh = zurueck(json.dumps(body) if not isinstance(body, str) else body).encode()
    status, daten, typ = _rufen(methode, voll, roh)
    if typ.startswith(("application/json", "text/")):
        text = hin(daten.decode("utf-8", "replace"))
        for alt, _ in UMBENENNEN:
            if re.search(rf"(?<![\w]){re.escape(alt)}(?![\w])", text):
                DURCHGEKOMMEN.add(alt)
        daten = text.encode()
    return Antwort(status, daten, typ)


def weg(hash_):
    def schritt(seite):
        seite.evaluate(f"location.hash = '{hash_}'")
        seite.wait_for_timeout(900)
    return schritt


SEITEN = [{"name": "start", "pfad": "/", "warten": 900}] + [
    {"name": n.replace("/", "-"), "pfad": "/", "schritte": [weg(n)]}
    for n in ["kaufen/fehlt", "kaufen/soll", "kaufen/bewerten", "kaufen/geschmack", "verkaufen", "werke",
              "lager/bestand", "lager/sammlung", "lager/sortieren", "lager/abgleich", "sicherung",
              "werk/tt0113277"]
]

atexit.register(lambda: DURCHGEKOMMEN and print("WARNUNG echter Name im Bild:", sorted(DURCHGEKOMMEN), file=sys.stderr))
