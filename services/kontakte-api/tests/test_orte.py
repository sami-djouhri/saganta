"""Wohnort auf der Karte: Aufloesung ueber die Adresssuche und die Route /api/orte.

Die Adresssuche ist nachgebaut, mit erfundenen Orten und Strassen.
"""
import pytest

from app import orte
from app.config import settings

ORTE = {"musterstadt": [{"id": 1, "name": "Musterstadt", "lat": 50.0, "lon": 7.0, "plz": "12345"}],
        "neudorf": [{"id": 2, "name": "Neudorf", "lat": 52.0, "lon": 9.0, "plz": "99887"},
                    {"id": 3, "name": "Neudorf", "lat": 48.0, "lon": 11.0, "plz": "12399"}]}
STRASSEN = {(1, "probeweg"): [{"id": 10, "name": "Probeweg", "lat": 50.01, "lon": 7.01, "ort": "Musterstadt"}],
            (1, "beispielstrasse"): [{"id": 11, "name": "Beispielstraße", "lat": 50.02, "lon": 7.02,
                                      "ort": "Musterstadt"}]}
NUMMERN = {10: [{"nummer": "5", "lat": 50.015, "lon": 7.015},
                {"nummer": "50", "lat": 50.016, "lon": 7.016},
                {"nummer": "5a", "lat": 50.017, "lon": 7.017}]}


class Adresssuche:
    def __init__(self):
        self.aufrufe = []
        self.weg = False
        self.suche = {"treffer": [], "ort": None}

    def __call__(self, pfad, **p):
        self.aufrufe.append((pfad, p))
        if self.weg:
            raise orte.NichtErreichbar("ConnectError")
        # Wie ``_grund`` im echten Dienst: klein, ß als ss, str. als strasse.
        q = str(p.get("q", "")).casefold().replace("ß", "ss").replace("str.", "strasse")
        if pfad == "/orte":
            return ORTE.get(q, [])
        if pfad == "/strassen":
            return STRASSEN.get((p["ort"], q), [])
        if pfad == "/nummern":
            return [h for h in NUMMERN.get(p["strasse"], []) if h["nummer"].startswith(q)]
        if pfad == "/suche":
            return self.suche
        raise AssertionError(pfad)


@pytest.fixture
def suche(monkeypatch):
    s = Adresssuche()
    monkeypatch.setattr(orte, "_hol", s)
    monkeypatch.setattr(settings, "adresssuche_url", "http://adresssuche.invalid")
    return s


@pytest.fixture
def kal(monkeypatch):
    from app import kalender
    monkeypatch.setattr(kalender, "aufruf", lambda *a, **k: None)


def test_hausnummer_genau(suche):
    f = orte.aufloesen("Probeweg 5, 12345 Musterstadt")
    assert (f.lat, f.lon, f.genauigkeit) == (50.015, 7.015, "adresse")


def test_hausnummer_mit_leerzeichen_und_land(suche):
    f = orte.aufloesen("Probeweg 5 a, 12345 Musterstadt, Deutschland")
    assert (f.lat, f.genauigkeit) == (50.017, "adresse")


def test_strasse_ohne_passende_nummer(suche):
    f = orte.aufloesen("Probeweg 77, Musterstadt")
    assert (f.lat, f.genauigkeit) == (50.01, "strasse")


def test_str_abkuerzung(suche):
    f = orte.aufloesen("Beispielstr. 3, Musterstadt")
    assert f.genauigkeit == "strasse" and f.lat == 50.02


def test_unbekannte_strasse_faellt_auf_ort(suche):
    f = orte.aufloesen("Gibtsnichtweg 1, Musterstadt")
    assert (f.lat, f.genauigkeit) == (50.0, "ort")


def test_plz_entscheidet_zwischen_gleichnamigen(suche):
    assert orte.aufloesen("Irgendwo 1, 12399 Neudorf").lat == 48.0
    assert orte.aufloesen("Irgendwo 1, 99887 Neudorf").lat == 52.0


def test_freie_suche_nur_im_erkannten_ort(suche):
    # Ein Treffer aus einer anderen Stadt darf nicht als Wohnort gelten.
    suche.suche = {"ort": {"id": 1, "name": "Musterstadt"}, "treffer": [
        {"typ": "adresse", "name": "Probeweg 5", "ort": "Anderswo", "lat": 1.0, "lon": 1.0},
        {"typ": "adresse", "name": "Probeweg 5", "ort": "Musterstadt", "lat": 2.0, "lon": 2.0},
    ]}
    f = orte.aufloesen("Probeweg 5 Musterstadt")
    assert (f.lat, f.genauigkeit) == (2.0, "adresse")
    suche.suche["treffer"] = suche.suche["treffer"][:1]
    assert orte.aufloesen("Probeweg 5 Musterstadt") is None


def test_ortsname_allein_ist_der_ort(suche):
    suche.suche = {"ort": None, "treffer": [
        {"typ": "strasse", "name": "Musterstadt", "ort": "Anderswo", "lat": 1.0, "lon": 1.0},
        {"typ": "ort", "name": "Musterstadt", "lat": 50.0, "lon": 7.0},
    ]}
    f = orte.aufloesen("Musterstadt")
    assert (f.lat, f.genauigkeit) == (50.0, "ort")


def test_strasse_ohne_erkannten_ort_gilt_nicht(suche):
    suche.suche = {"ort": None, "treffer": [
        {"typ": "adresse", "name": "Probeweg 5", "ort": "Irgendwo", "lat": 1.0, "lon": 1.0}]}
    assert orte.aufloesen("Probeweg 5") is None


def test_nichts_gefunden(suche):
    assert orte.aufloesen("Nirgendwo") is None


def test_weg_wirft(suche):
    suche.weg = True
    with pytest.raises(orte.NichtErreichbar):
        orte.aufloesen("Probeweg 5, Musterstadt")


def test_fehlertext_traegt_keine_adresse(monkeypatch):
    monkeypatch.setattr(settings, "adresssuche_url", "http://127.0.0.1:9")
    with pytest.raises(orte.NichtErreichbar) as e:
        orte._hol("/suche", q="Geheimweg 7")
    assert "Geheimweg" not in str(e.value) and "Geheimweg" not in repr(e.value)


# --- ueber die Routen -------------------------------------------------------

def test_anlegen_sucht_ort_und_karte_zeigt_ihn(kal, suche, client, kopf, kopf_zwei):
    k = client.post("/api/kontakte", json={"name": "Erika Probe", "adresse": "Probeweg 5, Musterstadt",
                                           "gruppe": "Freunde"}, headers=kopf).json()
    assert (k["lat"], k["ort_stand"], k["ort_genauigkeit"]) == (50.015, "gefunden", "adresse")
    client.post("/api/kontakte", json={"name": "Ohne Adresse"}, headers=kopf)
    r = client.get("/api/orte", headers=kopf).json()
    assert [o["name"] for o in r["orte"]] == ["Erika Probe"]
    assert set(r["orte"][0]) == {"id", "name", "adresse", "gruppe", "lat", "lon", "ort_genauigkeit"}
    assert client.get("/api/orte", headers=kopf_zwei).json()["orte"] == []


def test_adresse_aendern_sucht_neu_mitschicken_nicht(kal, suche, client, kopf):
    k = client.post("/api/kontakte", json={"name": "A", "adresse": "Probeweg 5, Musterstadt"},
                    headers=kopf).json()
    k = client.patch(f"/api/kontakte/{k['id']}", json={"lat": 40.0, "lon": 8.0}, headers=kopf).json()
    assert (k["lat"], k["ort_stand"]) == (40.0, "hand")
    vorher = len(suche.aufrufe)
    # Unveraenderte Adresse mitgeschickt (so speichert die App): Handpunkt bleibt.
    k = client.patch(f"/api/kontakte/{k['id']}", json={"adresse": "Probeweg 5, Musterstadt", "name": "A"},
                     headers=kopf).json()
    assert (k["lat"], k["ort_stand"]) == (40.0, "hand") and len(suche.aufrufe) == vorher
    # Neue Adresse: neu gesucht.
    k = client.patch(f"/api/kontakte/{k['id']}", json={"adresse": "Beispielstraße 1, Musterstadt"},
                     headers=kopf).json()
    assert (k["lat"], k["ort_stand"], k["ort_genauigkeit"]) == (50.02, "gefunden", "strasse")
    # Adresse geleert: kein Punkt mehr.
    k = client.patch(f"/api/kontakte/{k['id']}", json={"adresse": None}, headers=kopf).json()
    assert k["lat"] is None and k["ort_stand"] is None


def test_halber_handpunkt_abgelehnt(kal, suche, client, kopf):
    k = client.post("/api/kontakte", json={"name": "A"}, headers=kopf).json()
    assert client.patch(f"/api/kontakte/{k['id']}", json={"lat": 1.0}, headers=kopf).status_code == 422
    assert client.post("/api/kontakte", json={"name": "B", "lon": 1.0}, headers=kopf).status_code == 422


def test_suche_weg_dann_nachgezogen(kal, suche, client, kopf):
    suche.weg = True
    k = client.post("/api/kontakte", json={"name": "A", "adresse": "Probeweg 5, Musterstadt"},
                    headers=kopf)
    assert k.status_code == 201 and k.json()["ort_stand"] is None
    assert client.get("/api/orte", headers=kopf).json()["offen"] == 1
    from app.db import SessionLocal
    db = SessionLocal()
    assert orte.nachziehen(db)["unerreicht"] == 1
    suche.weg = False
    assert orte.nachziehen(db) == {"gefunden": 1, "nicht_gefunden": 0, "unerreicht": 0}
    db.close()
    r = client.get("/api/orte", headers=kopf).json()
    assert len(r["orte"]) == 1 and r["offen"] == 0


def test_nicht_gefunden_wird_gezaehlt(kal, suche, client, kopf):
    client.post("/api/kontakte", json={"name": "A", "adresse": "Nirgendwo"}, headers=kopf)
    r = client.get("/api/orte", headers=kopf).json()
    assert r["orte"] == [] and r["nicht_gefunden"] == 1
