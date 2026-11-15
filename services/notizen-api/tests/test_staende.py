"""Fruehere Staende: die letzten fuenf je Notiz (seit 2026-11-14)."""
from datetime import timedelta


def _notiz(client, kopf, inhalt="Fassung 0"):
    r = client.post("/api/notizen", json={"titel": "Plan", "inhalt": inhalt, "tags": ["haus"]}, headers=kopf)
    assert r.status_code == 201, r.text
    return r.json()


def _altern(notiz_id, minuten=11):
    """Den gespeicherten Stand altern lassen, als ruhe er seit `minuten`."""
    from app.db import SessionLocal
    from app.models import Notiz
    from app.util import jetzt
    from sqlalchemy import update

    with SessionLocal() as db:
        # update() statt Attribut setzen: onupdate=jetzt wuerde den Stempel sonst gleich neu setzen.
        db.execute(update(Notiz).where(Notiz.id == notiz_id)
                   .values(geaendert_am=jetzt() - timedelta(minutes=minuten)))
        db.commit()


def _speichern(client, kopf, nid, inhalt):
    r = client.patch(f"/api/notizen/{nid}", json={"inhalt": inhalt}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()


def test_aenderung_legt_den_alten_stand_ab(client, kopf):
    n = _notiz(client, kopf)
    _altern(n["id"])
    _speichern(client, kopf, n["id"], "Fassung 1")
    liste = client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()
    assert [s["zeichen"] for s in liste] == [len("Fassung 0")]
    assert "inhalt" not in liste[0]
    einzeln = client.get(f"/api/notizen/{n['id']}/staende/{liste[0]['id']}", headers=kopf).json()
    assert einzeln["inhalt"] == "Fassung 0" and einzeln["tags"] == ["haus"]


def test_schnelles_nachspeichern_frisst_den_stand_davor_nicht(client, kopf):
    n = _notiz(client, kopf)
    _altern(n["id"])
    for i in range(1, 12):
        _speichern(client, kopf, n["id"], f"Fassung {i}")
    liste = client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()
    assert len(liste) == 1
    assert client.get(f"/api/notizen/{n['id']}/staende/{liste[0]['id']}", headers=kopf).json()["inhalt"] == "Fassung 0"


def test_hoechstens_fuenf_und_die_juengsten_bleiben(client, kopf):
    n = _notiz(client, kopf)
    for i in range(1, 8):
        _altern(n["id"])
        _speichern(client, kopf, n["id"], f"Fassung {i}")
    liste = client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()
    inhalte = [client.get(f"/api/notizen/{n['id']}/staende/{s['id']}", headers=kopf).json()["inhalt"] for s in liste]
    assert inhalte == ["Fassung 6", "Fassung 5", "Fassung 4", "Fassung 3", "Fassung 2"]


def test_nur_anheften_legt_keinen_stand_ab(client, kopf):
    n = _notiz(client, kopf)
    _altern(n["id"])
    client.patch(f"/api/notizen/{n['id']}", json={"angeheftet": True}, headers=kopf)
    client.patch(f"/api/notizen/{n['id']}", json={"inhalt": "Fassung 0", "titel": "Plan"}, headers=kopf)
    assert client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json() == []


def test_wiederherstellen_ist_selbst_ruecknehmbar(client, kopf):
    n = _notiz(client, kopf)
    _altern(n["id"])
    _speichern(client, kopf, n["id"], "versehentlich geleert")
    sid = client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()[0]["id"]
    r = client.post(f"/api/notizen/{n['id']}/staende/{sid}/wiederherstellen", headers=kopf)
    assert r.status_code == 200, r.text
    assert r.json()["inhalt"] == "Fassung 0"
    # Der ueberschriebene Stand liegt jetzt oben, sofort, ohne Ruhezeit.
    oben = client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()[0]
    assert client.get(f"/api/notizen/{n['id']}/staende/{oben['id']}", headers=kopf).json()["inhalt"] == "versehentlich geleert"
    # Suche findet den zurueckgeholten Text (FTS-Trigger feuert auch hier).
    assert len(client.get("/api/notizen?q=Fassung", headers=kopf).json()) == 1


def test_den_aeltesten_von_fuenf_wiederherstellen(client, kopf):
    """Das Ablegen beim Wiederherstellen raeumt den aeltesten ab, also genau den, der zurueck soll."""
    n = _notiz(client, kopf)
    for i in range(1, 6):
        _altern(n["id"])
        _speichern(client, kopf, n["id"], f"Fassung {i}")
    liste = client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()
    assert len(liste) == 5
    r = client.post(f"/api/notizen/{n['id']}/staende/{liste[-1]['id']}/wiederherstellen", headers=kopf)
    assert r.status_code == 200, r.text
    assert r.json()["inhalt"] == "Fassung 0"
    assert len(client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()) == 5


def test_staende_sind_mandantengetrennt(client, kopf, kopf_zwei):
    n = _notiz(client, kopf)
    _altern(n["id"])
    _speichern(client, kopf, n["id"], "Fassung 1")
    sid = client.get(f"/api/notizen/{n['id']}/staende", headers=kopf).json()[0]["id"]
    assert client.get(f"/api/notizen/{n['id']}/staende", headers=kopf_zwei).status_code == 404
    assert client.get(f"/api/notizen/{n['id']}/staende/{sid}", headers=kopf_zwei).status_code == 404
    assert client.post(f"/api/notizen/{n['id']}/staende/{sid}/wiederherstellen", headers=kopf_zwei).status_code == 404


def test_loeschen_nimmt_die_staende_mit(client, kopf):
    from app.db import SessionLocal
    from app.models import NotizStand

    n = _notiz(client, kopf)
    _altern(n["id"])
    _speichern(client, kopf, n["id"], "Fassung 1")
    client.delete(f"/api/notizen/{n['id']}", headers=kopf)
    with SessionLocal() as db:
        assert db.query(NotizStand).count() == 0
