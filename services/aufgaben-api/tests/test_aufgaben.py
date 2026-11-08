"""Die Aufgaben selbst: anlegen, aendern, leeren, verschieben, Mandantengrenze."""
from conftest import token_fuer


def _neu(client, kopf, **felder):
    antwort = client.post("/api/aufgaben", json={"titel": "Reifen wechseln", **felder}, headers=kopf)
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


def test_ohne_token_kein_zugriff(client):
    assert client.get("/api/aufgaben").status_code == 401


def test_fremde_zielgruppe_wird_abgelehnt(client):
    kopf = {"Authorization": f"Bearer {token_fuer('nutzer-eins', aud='kalender-bff')}"}
    assert client.get("/api/aufgaben", headers=kopf).status_code == 401


def test_anlegen_mit_nur_titel_liegt_im_vorrat(client, kopf):
    a = _neu(client, kopf)
    assert a["prioritaet"] == "mittel"
    assert a["faellig"] is None and a["tag"] is None and a["start"] is None
    assert [x["id"] for x in client.get("/api/aufgaben", headers=kopf).json()] == [a["id"]]


def test_leerer_titel_und_vierte_prioritaet_werden_abgelehnt(client, kopf):
    assert client.post("/api/aufgaben", json={"titel": "   "}, headers=kopf).status_code == 422
    assert client.post("/api/aufgaben", json={"titel": "x", "prioritaet": "dringend"}, headers=kopf).status_code == 422


def test_null_leert_weglassen_laesst_stehen(client, kopf):
    """Der Fehler, den der kalender-bff bis zum 13.09. hatte: Leeren ging nicht."""
    a = _neu(client, kopf, faellig="2026-11-04", notiz="im Keller", dauer_min=30)
    b = client.put(f"/api/aufgaben/{a['id']}", json={"faellig": None, "prioritaet": "hoch"}, headers=kopf).json()
    assert b["faellig"] is None
    assert b["prioritaet"] == "hoch"
    assert b["notiz"] == "im Keller", "nicht geschicktes Feld darf nicht geleert werden"
    assert b["dauer_min"] == 30


def test_titel_null_wird_abgelehnt(client, kopf):
    a = _neu(client, kopf)
    assert client.put(f"/api/aufgaben/{a['id']}", json={"titel": None}, headers=kopf).status_code == 422


def test_zeit_mit_offset_wird_berliner_wanduhrzeit(client, kopf):
    a = _neu(client, kopf)
    b = client.put(f"/api/aufgaben/{a['id']}", headers=kopf, json={
        "start": "2026-11-04T15:00:00+00:00", "ende": "2026-11-04T15:30:00+00:00"}).json()
    assert b["start"].startswith("2026-11-04T16:00")


def test_abhaken_zweimal_behaelt_den_zeitpunkt(client, kopf):
    a = _neu(client, kopf)
    erst = client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf).json()
    zweit = client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf).json()
    assert erst["erledigt"] and erst["erledigt_am"] == zweit["erledigt_am"]
    assert client.get("/api/aufgaben", headers=kopf).json() == []
    assert [x["id"] for x in client.get("/api/aufgaben?erledigte=true", headers=kopf).json()] == [a["id"]]
    offen = client.post(f"/api/aufgaben/{a['id']}/offen", headers=kopf).json()
    assert not offen["erledigt"] and offen["erledigt_am"] is None


def test_verschieben_zaehlt_und_nimmt_die_zeit_weg(client, kopf):
    a = _neu(client, kopf, faellig="2026-11-03")
    client.put(f"/api/aufgaben/{a['id']}", headers=kopf, json={
        "tag": "2026-11-03", "start": "2026-11-03T16:00:00", "ende": "2026-11-03T16:30:00"})
    b = client.post(f"/api/aufgaben/{a['id']}/verschieben", json={"tag": "2026-11-04"}, headers=kopf).json()
    assert b["tag"] == "2026-11-04" and b["start"] is None and b["verschoben"] == 1
    assert b["faellig"] == "2026-11-03", "die Frist bleibt"
    c = client.post(f"/api/aufgaben/{a['id']}/verschieben", json={}, headers=kopf).json()
    assert c["tag"] is None and c["verschoben"] == 2


def test_fremde_aufgabe_ist_unsichtbar(client, kopf, kopf_zwei):
    a = _neu(client, kopf)
    assert client.get("/api/aufgaben", headers=kopf_zwei).json() == []
    for methode, pfad in (("get", ""), ("delete", ""), ("post", "/erledigt")):
        antwort = getattr(client, methode)(f"/api/aufgaben/{a['id']}{pfad}", headers=kopf_zwei)
        assert antwort.status_code == 404, (methode, pfad)
    assert client.put(f"/api/aufgaben/{a['id']}", json={"titel": "x"}, headers=kopf_zwei).status_code == 404


def test_loeschen(client, kopf):
    a = _neu(client, kopf)
    assert client.delete(f"/api/aufgaben/{a['id']}", headers=kopf).status_code == 204
    assert client.delete(f"/api/aufgaben/{a['id']}", headers=kopf).status_code == 404
