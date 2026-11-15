"""Turnus ab Erledigung (K32) und vertrauliche Listen (K20), Entscheide 13.11."""
from datetime import date, timedelta

from app import routes


def _neu(client, kopf, **felder):
    antwort = client.post("/api/aufgaben", json={"titel": "Bad putzen", **felder}, headers=kopf)
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


def _offen(client, kopf):
    return client.get("/api/aufgaben", headers=kopf).json()


def _heute():
    return routes._berlin_jetzt().date()


def test_abhaken_legt_die_naechste_runde_an(client, kopf):
    liste = client.post("/api/listen", json={"name": "Haushalt"}, headers=kopf).json()
    a = _neu(client, kopf, turnus_tage=14, liste_id=liste["id"], dauer_min=30, tag="2026-11-10",
             faellig="2026-11-12", unteraufgaben=[{"text": "Wanne", "erledigt": True}])
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    [folge] = _offen(client, kopf)
    assert folge["id"] != a["id"]
    assert folge["titel"] == "Bad putzen" and folge["turnus_tage"] == 14
    assert folge["faellig"] == str(_heute() + timedelta(days=14)), "ab Erledigung, nicht ab Frist"
    assert folge["liste_id"] == liste["id"] and folge["dauer_min"] == 30
    assert folge["tag"] is None, "der Plantag gehoerte zur alten Runde"
    assert folge["unteraufgaben"] == [{"text": "Wanne", "erledigt": False}]
    assert folge["herkunft"] == f"turnus:{a['id']}"
    erledigte = client.get("/api/aufgaben?erledigte=true", headers=kopf).json()
    assert [x["id"] for x in erledigte] == [a["id"]], "die alte Runde bleibt als Verlauf"


def test_ohne_turnus_keine_folgeaufgabe(client, kopf):
    a = _neu(client, kopf)
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    assert _offen(client, kopf) == []


def test_zweites_abhaken_legt_keine_zweite_runde_an(client, kopf):
    a = _neu(client, kopf, turnus_tage=7)
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    assert len(_offen(client, kopf)) == 1


def test_wieder_offen_nimmt_die_unberuehrte_runde_zurueck(client, kopf):
    a = _neu(client, kopf, turnus_tage=7)
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    client.post(f"/api/aufgaben/{a['id']}/offen", headers=kopf)
    assert [x["id"] for x in _offen(client, kopf)] == [a["id"]]
    # und erneutes Abhaken legt sie wieder an
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    assert len(_offen(client, kopf)) == 1


def test_wieder_offen_laesst_eine_bearbeitete_runde_stehen(client, kopf, monkeypatch):
    a = _neu(client, kopf, turnus_tage=7)
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    [folge] = _offen(client, kopf)
    # Bearbeitet heisst: geaendert_am liegt spuerbar nach erstellt_am.
    from app.db import SessionLocal
    from app.models import Aufgabe
    from datetime import datetime, timezone
    with SessionLocal() as db:
        zeile = db.get(Aufgabe, folge["id"])
        zeile.notiz = "Fugen mit Essig"
        zeile.geaendert_am = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.commit()
    client.post(f"/api/aufgaben/{a['id']}/offen", headers=kopf)
    ids = {x["id"] for x in _offen(client, kopf)}
    assert ids == {a["id"], folge["id"]}, "eine Eingabe in der neuen Runde darf nicht verloren gehen"
    # erneutes Abhaken legt keine dritte an
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    assert [x["id"] for x in _offen(client, kopf)] == [folge["id"]]


def test_turnus_aendern_und_leeren(client, kopf):
    a = _neu(client, kopf)
    b = client.put(f"/api/aufgaben/{a['id']}", json={"turnus_tage": 30}, headers=kopf).json()
    assert b["turnus_tage"] == 30
    c = client.put(f"/api/aufgaben/{a['id']}", json={"turnus_tage": None}, headers=kopf).json()
    assert c["turnus_tage"] is None
    assert client.put(f"/api/aufgaben/{a['id']}", json={"turnus_tage": 0}, headers=kopf).status_code == 422


def test_turnus_ist_mandantengetrennt(client, kopf, kopf_zwei):
    a = _neu(client, kopf, turnus_tage=7)
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    assert _offen(client, kopf_zwei) == []


def test_liste_vertraulich_setzen(client, kopf):
    neu = client.post("/api/listen", json={"name": "Arzt", "vertraulich": True}, headers=kopf).json()
    assert neu["vertraulich"] is True
    aus = client.put(f"/api/listen/{neu['id']}", json={"vertraulich": False}, headers=kopf).json()
    assert aus["vertraulich"] is False
    namen = client.put(f"/api/listen/{neu['id']}", json={"name": "Ärzte"}, headers=kopf).json()
    assert namen["vertraulich"] is False, "Umbenennen laesst den Schalter stehen"
