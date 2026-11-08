"""Saganta Kontakte: Bestand, Papierkorb, Tage, Kalender-Spiegel und Umzug."""
from datetime import date, timedelta

import pytest

from app import kalender
from app.models import AbgleichOffen
from app.tage import jahrestag_kennung


@pytest.fixture
def kal(monkeypatch):
    """Ersetzt den kalender-bff. Haelt fest, was ankam."""
    gesehen: list[tuple[str, str, str, object]] = []
    antworten: dict = {}

    def aufruf(me, methode, pfad, **kw):
        gesehen.append((me.sub, methode, pfad, kw.get("json")))
        antwort = antworten.get((methode, pfad))
        if isinstance(antwort, Exception):
            raise antwort
        return antwort

    monkeypatch.setattr(kalender, "aufruf", aufruf)
    return gesehen, antworten


def _abgleiche(gesehen):
    return [j["eintraege"] for _, m, p, j in gesehen if (m, p) == ("PUT", "/api/contacts/abgleich")]


def test_anlegen_lesen_aendern(kal, client, kopf):
    r = client.post("/api/kontakte", json={"name": " Anna ", "telefon": "0151 123", "email": "",
                                          "gruppe": "Familie"}, headers=kopf)
    assert r.status_code == 201, r.text
    k = r.json()
    assert k["name"] == "Anna" and k["email"] is None and k["jahrestage"] == []
    r = client.patch(f"/api/kontakte/{k['id']}", json={"adresse": "Hauptstr. 1"}, headers=kopf)
    assert r.json()["adresse"] == "Hauptstr. 1" and r.json()["telefon"] == "0151 123"
    # Ohne Geburtstag und Jahrestag hat der Kalender nichts zu erfahren.
    assert _abgleiche(kal[0]) == []


def test_leerer_name_abgelehnt(kal, client, kopf):
    assert client.post("/api/kontakte", json={"name": "  "}, headers=kopf).status_code == 422
    k = client.post("/api/kontakte", json={"name": "B"}, headers=kopf).json()
    assert client.patch(f"/api/kontakte/{k['id']}", json={"name": None}, headers=kopf).status_code == 422


def test_mandanten_getrennt(kal, client, kopf, kopf_zwei):
    k = client.post("/api/kontakte", json={"name": "Geheim"}, headers=kopf).json()
    assert client.get("/api/kontakte", headers=kopf_zwei).json()["kontakte"] == []
    assert client.get(f"/api/kontakte/{k['id']}", headers=kopf_zwei).status_code == 404
    assert client.patch(f"/api/kontakte/{k['id']}", json={"name": "x"}, headers=kopf_zwei).status_code == 404
    assert client.delete(f"/api/kontakte/{k['id']}", headers=kopf_zwei).status_code == 404


def test_suche_und_gruppen(kal, client, kopf):
    client.post("/api/kontakte", json={"name": "Anna", "gruppe": "Familie"}, headers=kopf)
    client.post("/api/kontakte", json={"name": "Bert", "email": "bert@example.invalid",
                                      "gruppe": "Arbeit"}, headers=kopf)
    client.post("/api/kontakte", json={"name": "cem"}, headers=kopf)
    namen = [k["name"] for k in client.get("/api/kontakte", headers=kopf).json()["kontakte"]]
    assert namen == ["Anna", "Bert", "cem"]  # ohne Ruecksicht auf Gross/Klein
    assert [k["name"] for k in client.get("/api/kontakte?suche=EXAMPLE", headers=kopf).json()["kontakte"]] == ["Bert"]
    assert [k["name"] for k in client.get("/api/kontakte?gruppe=Familie", headers=kopf).json()["kontakte"]] == ["Anna"]
    assert client.get("/api/gruppen", headers=kopf).json() == ["Arbeit", "Familie"]


def test_geburtstag_und_jahrestag_gehen_in_den_kalender(kal, client, kopf):
    gesehen, _ = kal
    k = client.post("/api/kontakte", json={
        "name": "Anna", "geburtstag": "1995-03-10",
        "jahrestage": [{"bezeichnung": "Hochzeitstag", "datum": "2020-06-20"}],
    }, headers=kopf).json()
    letzte = _abgleiche(gesehen)[-1]
    assert letzte == [
        {"id": k["id"], "name": "Anna", "birthday": "1995-03-10", "art": "geburtstag"},
        {"id": jahrestag_kennung(k["id"], "Hochzeitstag", "2020-06-20"),
         "name": "Hochzeitstag Anna", "birthday": "2020-06-20", "art": "jahrestag"},
    ]
    # Eine Notiz aendert nichts am Kalender.
    vorher = len(_abgleiche(gesehen))
    client.patch(f"/api/kontakte/{k['id']}", json={"notiz": "mag Tee"}, headers=kopf)
    assert len(_abgleiche(gesehen)) == vorher
    # Loeschen nimmt beide Tage aus dem Kalender.
    client.delete(f"/api/kontakte/{k['id']}", headers=kopf)
    assert _abgleiche(gesehen)[-1] == []


def test_kalender_weg_kontakt_bleibt_und_abgleich_wird_nachgeholt(kal, client, kopf):
    gesehen, antworten = kal
    antworten[("PUT", "/api/contacts/abgleich")] = kalender.KalenderNichtErreichbar("weg")
    r = client.post("/api/kontakte", json={"name": "Anna", "geburtstag": "1995-03-10"}, headers=kopf)
    assert r.status_code == 201
    liste = client.get("/api/kontakte", headers=kopf).json()
    assert liste["kalender_aktuell"] is False and len(liste["kontakte"]) == 1

    from app import abgleich
    from app.db import SessionLocal

    del antworten[("PUT", "/api/contacts/abgleich")]
    db = SessionLocal()
    try:
        assert abgleich.nachholen(db) == 1
        assert db.query(AbgleichOffen).count() == 0
    finally:
        db.close()
    assert client.get("/api/kontakte", headers=kopf).json()["kalender_aktuell"] is True
    assert _abgleiche(gesehen)[-1][0]["name"] == "Anna"


def test_papierkorb(kal, client, kopf):
    k = client.post("/api/kontakte", json={"name": "Anna"}, headers=kopf).json()
    assert client.delete(f"/api/kontakte/{k['id']}", headers=kopf).status_code == 204
    assert client.get("/api/kontakte", headers=kopf).json()["kontakte"] == []
    korb = client.get("/api/papierkorb", headers=kopf).json()
    assert [x["id"] for x in korb] == [k["id"]] and korb[0]["geloescht_am"]
    r = client.post(f"/api/papierkorb/{k['id']}/wiederherstellen", headers=kopf)
    assert r.status_code == 200 and r.json()["geloescht_am"] is None
    client.delete(f"/api/kontakte/{k['id']}", headers=kopf)
    assert client.delete(f"/api/papierkorb/{k['id']}", headers=kopf).status_code == 204
    assert client.get("/api/papierkorb", headers=kopf).json() == []


def test_papierkorb_leert_sich_nach_30_tagen(kal, client, kopf):
    from app.db import SessionLocal
    from app.models import Kontakt, jetzt

    k = client.post("/api/kontakte", json={"name": "Alt"}, headers=kopf).json()
    client.delete(f"/api/kontakte/{k['id']}", headers=kopf)
    db = SessionLocal()
    db.get(Kontakt, k["id"]).geloescht_am = jetzt() - timedelta(days=31)
    db.commit()
    db.close()
    assert client.get("/api/papierkorb", headers=kopf).json() == []


def test_anstehend(kal, client, kopf):
    heute = date.today()
    in_drei = heute + timedelta(days=3)
    client.post("/api/kontakte", json={"name": "Anna", "geburtstag": in_drei.replace(year=in_drei.year - 30).isoformat()}, headers=kopf)
    client.post("/api/kontakte", json={"name": "Bert", "jahrestage": [
        {"bezeichnung": "Kennenlerntag", "datum": heute.replace(year=heute.year - 2).isoformat()}]}, headers=kopf)
    client.post("/api/kontakte", json={"name": "Fern", "geburtstag": (heute + timedelta(days=40)).replace(year=1990).isoformat()}, headers=kopf)
    a = client.get("/api/anstehend?tage=30", headers=kopf).json()
    assert [(x["name"], x["art"], x["in_tagen"], x["zahl"]) for x in a] == [
        ("Bert", "jahrestag", 0, 2), ("Anna", "geburtstag", 3, 30)]


def test_umzug_aus_dem_kalender_ist_idempotent(kal, client, kopf):
    gesehen, antworten = kal
    antworten[("GET", "/api/contacts")] = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "Oma", "birthday": "1940-02-29",
         "email": None, "phone": None, "notes": None, "address": None},
        {"id": "22222222-2222-2222-2222-222222222222", "name": "Hochzeitstag X",
         "birthday": "2020-01-01", "art": "jahrestag"},
    ]
    r = client.post("/api/umzug/kalender", headers=kopf).json()
    assert r == {"gefunden": 2, "uebernommen": 1, "schon_da": 0}
    k = client.get("/api/kontakte/11111111-1111-1111-1111-111111111111", headers=kopf).json()
    assert k["herkunft"] == "kalender:11111111-1111-1111-1111-111111111111"
    assert _abgleiche(gesehen)[-1][0]["id"] == "11111111-1111-1111-1111-111111111111"
    assert client.post("/api/umzug/kalender", headers=kopf).json()["uebernommen"] == 0


def test_umzug_ohne_kalender_ist_502(kal, client, kopf):
    kal[1][("GET", "/api/contacts")] = kalender.KalenderNichtErreichbar("weg")
    assert client.post("/api/umzug/kalender", headers=kopf).status_code == 502


def test_ohne_token_401(client):
    assert client.get("/api/kontakte").status_code in (401, 403)
