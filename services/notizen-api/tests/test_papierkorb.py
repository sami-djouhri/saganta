"""Papierkorb: geloeschte Notizen 30 Tage zurueckholen (seit 2026-11-07)."""
from datetime import timedelta


def _notiz(client, kopf, titel="Einkauf", **extra):
    r = client.post("/api/notizen", json={"titel": titel, "inhalt": "Milch, Brot", **extra}, headers=kopf)
    assert r.status_code == 201, r.text
    return r.json()


def test_loeschen_landet_im_papierkorb_und_kommt_zurueck(client, kopf):
    n = _notiz(client, kopf, tags=["haus"],
               verknuepfung={"typ": "termin", "ref": "t-1", "label": "Zahnarzt"})
    assert client.delete(f"/api/notizen/{n['id']}", headers=kopf).status_code == 204
    # Aus Liste und Suche verschwunden.
    assert client.get("/api/notizen", headers=kopf).json() == []
    assert client.get("/api/notizen?q=Milch", headers=kopf).json() == []
    korb = client.get("/api/notizen/papierkorb/liste", headers=kopf).json()
    assert [k["titel"] for k in korb] == ["Einkauf"]
    zurueck = client.post(f"/api/notizen/papierkorb/{korb[0]['id']}/wiederherstellen", headers=kopf)
    assert zurueck.status_code == 200, zurueck.text
    assert zurueck.json()["inhalt"] == "Milch, Brot"
    # Mit Verknuepfung und wieder suchbar, Papierkorb leer.
    assert [x["id"] for x in client.get("/api/notizen?verknuepft=termin:t-1", headers=kopf).json()] == [zurueck.json()["id"]]
    assert len(client.get("/api/notizen?q=Milch", headers=kopf).json()) == 1
    assert client.get("/api/notizen/papierkorb/liste", headers=kopf).json() == []


def test_papierkorb_ist_mandantengetrennt(client, kopf, kopf_zwei):
    n = _notiz(client, kopf)
    client.delete(f"/api/notizen/{n['id']}", headers=kopf)
    assert client.get("/api/notizen/papierkorb/liste", headers=kopf_zwei).json() == []
    eintrag = client.get("/api/notizen/papierkorb/liste", headers=kopf).json()[0]
    r = client.post(f"/api/notizen/papierkorb/{eintrag['id']}/wiederherstellen", headers=kopf_zwei)
    assert r.status_code == 404


def test_nach_dreissig_tagen_endgueltig_weg(client, kopf):
    from app.db import SessionLocal
    from app.models import Papierkorb
    from app.util import jetzt

    n = _notiz(client, kopf)
    client.delete(f"/api/notizen/{n['id']}", headers=kopf)
    with SessionLocal() as db:
        z = db.query(Papierkorb).one()
        z.geloescht_am = jetzt() - timedelta(days=31)
        db.commit()
    assert client.get("/api/notizen/papierkorb/liste", headers=kopf).json() == []
