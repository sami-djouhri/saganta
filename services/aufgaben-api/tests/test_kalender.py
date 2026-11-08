"""Planen und Tag: der Weg zum Kalender, nachgebaut."""
import httpx
import pytest
from jose import jwt

from app import kalender
from app.config import settings


@pytest.fixture
def kal(monkeypatch):
    """Ersetzt den kalender-bff. Haelt fest, was ankam, samt Token."""
    gesehen = []
    antworten = {}

    def aufruf(me, methode, pfad, **kw):
        token = kalender._token(me)
        gesehen.append((methode, pfad, kw, token))
        wert = antworten.get((methode, pfad))
        if isinstance(wert, Exception):
            raise wert
        return wert(kw) if callable(wert) else wert

    monkeypatch.setattr(kalender, "aufruf", aufruf)
    return gesehen, antworten


def _neu(client, kopf, **felder):
    return client.post("/api/aufgaben", json=felder, headers=kopf).json()


def test_token_spricht_fuer_den_aufrufer(kal, client, kopf):
    gesehen, antworten = kal
    antworten[("POST", "/api/assistant/vorschlag")] = {"suggestions": [], "deferred": []}
    client.post("/api/planen", json={"datum": "2026-11-04"}, headers=kopf)
    nutzlast = jwt.decode(gesehen[0][3], settings.jwt_secret, algorithms=["HS256"], audience="kalender-bff")
    assert nutzlast["sub"] == "nutzer-eins"
    assert nutzlast["exp"] - nutzlast["iat"] <= 60


def test_planen_schickt_kandidaten_und_belegtes_und_aendert_nichts(kal, client, kopf):
    gesehen, antworten = kal
    vorrat = _neu(client, kopf, titel="Vorrat", dauer_min=30, energie="hoch", prioritaet="hoch")
    _neu(client, kopf, titel="Spaeter", tag="2026-11-09")
    fest = _neu(client, kopf, titel="Fest")
    client.put(f"/api/aufgaben/{fest['id']}", headers=kopf,
               json={"tag": "2026-11-04", "start": "2026-11-04T10:00:00", "ende": "2026-11-04T11:00:00"})
    zu_voll = _neu(client, kopf, titel="Passt nirgends", dauer_min=600)
    antworten[("POST", "/api/assistant/vorschlag")] = {
        "suggestions": [{"todo_id": vorrat["id"], "title": "Vorrat", "start": "2026-11-04T16:00:00+01:00",
                         "end": "2026-11-04T16:30:00+01:00", "minutes": 30, "reason": "nachmittags"}],
        "deferred": [],
    }
    plan = client.post("/api/planen", json={"datum": "2026-11-04"}, headers=kopf).json()
    anfrage = gesehen[-1][2]["json"]
    ids = {a["id"] for a in anfrage["aufgaben"]}
    assert vorrat["id"] in ids and zu_voll["id"] in ids
    assert fest["id"] not in ids, "was schon eine Zeit hat, ist kein Kandidat"
    assert all(a["title"] != "Spaeter" for a in anfrage["aufgaben"]), "an einen spaeteren Tag geheftet"
    assert anfrage["belegt"] == [{"start": "2026-11-04T10:00:00", "end": "2026-11-04T11:00:00"}]
    eintrag = next(a for a in anfrage["aufgaben"] if a["id"] == vorrat["id"])
    assert eintrag["energy_required"] == "high" and eintrag["priority"] == "hoch"
    assert plan["vorschlaege"][0]["start"].startswith("2026-11-04T16:00")
    assert plan["ohne_fenster"] == ["Passt nirgends"]
    assert not plan["festgelegt"]
    assert client.get(f"/api/aufgaben/{vorrat['id']}", headers=kopf).json()["start"] is None


def test_festlegen_schreibt_zeit_und_tag(kal, client, kopf):
    _, antworten = kal
    a = _neu(client, kopf, titel="A")
    antworten[("POST", "/api/assistant/vorschlag")] = {"suggestions": [
        {"todo_id": a["id"], "title": "A", "start": "2026-11-04T16:00:00+01:00",
         "end": "2026-11-04T16:30:00+01:00", "minutes": 30}], "deferred": []}
    plan = client.post("/api/planen", json={"datum": "2026-11-04", "festlegen": True}, headers=kopf).json()
    assert plan["festgelegt"]
    b = client.get(f"/api/aufgaben/{a['id']}", headers=kopf).json()
    assert b["tag"] == "2026-11-04" and b["start"].startswith("2026-11-04T16:00")


def test_fremde_kennung_im_vorschlag_wird_nicht_uebernommen(kal, client, kopf):
    """Der Kalender darf nie eine Aufgabe festlegen, die nicht gefragt war."""
    _, antworten = kal
    _neu(client, kopf, titel="A")
    antworten[("POST", "/api/assistant/vorschlag")] = {"suggestions": [
        {"todo_id": "fremd", "title": "X", "start": "2026-11-04T16:00:00", "end": "2026-11-04T16:30:00",
         "minutes": 30}], "deferred": []}
    plan = client.post("/api/planen", json={"datum": "2026-11-04", "festlegen": True}, headers=kopf).json()
    assert plan["vorschlaege"] == []


def test_planen_ohne_kalender_ist_503(kal, client, kopf):
    _, antworten = kal
    antworten[("POST", "/api/assistant/vorschlag")] = kalender.KalenderNichtErreichbar("weg")
    assert client.post("/api/planen", json={"datum": "2026-11-04"}, headers=kopf).status_code == 503


def test_tag_ohne_kalender_bleibt_benutzbar(kal, client, kopf):
    _, antworten = kal
    antworten[("GET", "/api/goals")] = kalender.KalenderNichtErreichbar("weg")
    tag = client.get("/api/tag?datum=2026-11-04", headers=kopf).json()
    assert tag["kalender_erreichbar"] is False and tag["ziele"] == []


def test_tag_reicht_ziele_durch(kal, client, kopf):
    _, antworten = kal
    antworten[("GET", "/api/goals")] = [{"id": "g1", "title": "Laufen", "priority": "A", "status": "planned"}]
    tag = client.get("/api/tag?datum=2026-11-04", headers=kopf).json()
    assert tag["ziele"] == [{"id": "g1", "titel": "Laufen", "prioritaet": "A", "status": "planned"}]


def test_ziel_abhaken_geht_als_status_an_den_kalender(kal, client, kopf):
    gesehen, antworten = kal
    antworten[("PUT", "/api/goals/g1")] = {"id": "g1", "title": "Laufen", "priority": "A", "status": "achieved"}
    z = client.put("/api/ziele/g1", json={"status": "achieved"}, headers=kopf).json()
    assert z["status"] == "achieved"
    assert gesehen[-1][2]["json"] == {"status": "achieved"}


def test_geloeschtes_ziel_bleibt_404(kal, client, kopf):
    _, antworten = kal
    antworten[("DELETE", "/api/goals/g9")] = httpx.HTTPStatusError(
        "404", request=httpx.Request("DELETE", "http://x"), response=httpx.Response(404))
    assert client.delete("/api/ziele/g9", headers=kopf).status_code == 404
