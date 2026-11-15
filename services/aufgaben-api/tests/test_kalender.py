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


def test_planen_schickt_das_fenster_des_tages(kal, client, kopf):
    """Der Planer bekommt das Fenster mit, statt dass sein Vorschlag verworfen wird."""
    gesehen, antworten = kal
    antworten[("POST", "/api/assistant/vorschlag")] = {"suggestions": [], "deferred": []}
    # 2026-11-12 ist ein Donnerstag (3).
    tagsueber = _neu(client, kopf, titel="Video-Ident", dauer_min=30,
                     zeitfenster=[{"tage": [0, 1, 2, 3, 4], "von": "09:00", "bis": "18:00"}])
    mittags = _neu(client, kopf, titel="Mittags", tageszeit="mittags")
    beides = _neu(client, kopf, titel="Beides", tageszeit="nachmittags",
                  zeitfenster=[{"tage": [3], "von": "09:00", "bis": "16:00"}])
    frei = _neu(client, kopf, titel="Frei")
    nur_wochenende = _neu(client, kopf, titel="Wochenende",
                          zeitfenster=[{"tage": [5, 6], "von": "10:00", "bis": "12:00"}])
    getrennt = _neu(client, kopf, titel="Getrennt", tageszeit="abends",
                    zeitfenster=[{"tage": [3], "von": "08:00", "bis": "10:00"}])
    plan = client.post("/api/planen", json={"datum": "2026-11-12"}, headers=kopf).json()
    nach_id = {a["id"]: a for a in gesehen[-1][2]["json"]["aufgaben"]}
    assert nach_id[tagsueber["id"]]["fenster"] == [{"von": "09:00", "bis": "18:00"}]
    assert nach_id[mittags["id"]]["fenster"] == [{"von": "11:00", "bis": "14:00"}]
    assert nach_id[beides["id"]]["fenster"] == [{"von": "14:00", "bis": "16:00"}], "geschnitten"
    assert "fenster" not in nach_id[frei["id"]]
    assert nur_wochenende["id"] not in nach_id and getrennt["id"] not in nach_id
    zurueck = {z["aufgabe_id"]: z["grund"] for z in plan["zurueck"]}
    assert zurueck[nur_wochenende["id"]] == "zeitfenster"
    assert zurueck[getrennt["id"]] == "zeitfenster"


def test_vorschlag_ausserhalb_des_fensters_bleibt_verworfen(kal, client, kopf):
    """Der Riegel bleibt, falls ein Kalender das Fenster nicht kennt."""
    _, antworten = kal
    a = _neu(client, kopf, titel="Tagsueber",
             zeitfenster=[{"tage": [3], "von": "09:00", "bis": "18:00"}])
    antworten[("POST", "/api/assistant/vorschlag")] = {"suggestions": [
        {"todo_id": a["id"], "title": "Tagsueber", "start": "2026-11-12T20:00:00",
         "end": "2026-11-12T20:30:00", "minutes": 30}], "deferred": []}
    plan = client.post("/api/planen", json={"datum": "2026-11-12", "festlegen": True}, headers=kopf).json()
    assert plan["vorschlaege"] == []
    assert plan["zurueck"][0]["grund"] == "zeitfenster"
    assert client.get(f"/api/aufgaben/{a['id']}", headers=kopf).json()["start"] is None


# --- Belegung an den Kalender melden (2026-11-13) --------------------------
def _belegungen(gesehen):
    return [kw["json"]["eintraege"] for m, p, kw, _ in gesehen
            if (m, p) == ("PUT", "/api/planung/belegungen/aufgaben")]


def test_zeit_setzen_meldet_die_ganze_liste(kal, client, kopf):
    gesehen, _ = kal
    a = _neu(client, kopf, titel="Video-Ident")
    assert _belegungen(gesehen) == [], "ohne Uhrzeit gibt es nichts zu melden"
    client.put(f"/api/aufgaben/{a['id']}", headers=kopf,
               json={"start": "2099-11-14T13:00:00", "ende": "2099-11-14T14:00:00"})
    assert _belegungen(gesehen)[-1] == [{"id": a["id"], "titel": "Video-Ident",
                                         "start": "2099-11-14T13:00:00",
                                         "ende": "2099-11-14T14:00:00"}]


def test_abhaken_verschieben_loeschen_nehmen_die_zeit_wieder_raus(kal, client, kopf):
    gesehen, _ = kal
    zeit = {"start": "2099-11-14T13:00:00", "ende": "2099-11-14T14:00:00"}
    for schritt in ("erledigt", "verschieben", "loeschen"):
        a = _neu(client, kopf, titel=schritt)
        client.put(f"/api/aufgaben/{a['id']}", headers=kopf, json=zeit)
        if schritt == "erledigt":
            client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
        elif schritt == "verschieben":
            client.post(f"/api/aufgaben/{a['id']}/verschieben", headers=kopf, json={"tag": None})
        else:
            client.delete(f"/api/aufgaben/{a['id']}", headers=kopf)
        assert all(e["id"] != a["id"] for e in _belegungen(gesehen)[-1]), schritt


def test_dauer_ohne_ende_und_vergangenes(kal, client, kopf):
    gesehen, _ = kal
    a = _neu(client, kopf, titel="Mit Dauer", dauer_min=45)
    client.put(f"/api/aufgaben/{a['id']}", headers=kopf, json={"start": "2099-11-14T13:00:00"})
    assert _belegungen(gesehen)[-1][0]["ende"] == "2099-11-14T13:45:00"
    b = _neu(client, kopf, titel="Vorbei")
    client.put(f"/api/aufgaben/{b['id']}", headers=kopf,
               json={"start": "2020-01-01T10:00:00", "ende": "2020-01-01T11:00:00"})
    assert all(e["id"] != b["id"] for e in _belegungen(gesehen)[-1])


def test_kalender_weg_speichern_klappt_trotzdem(kal, client, kopf):
    _, antworten = kal
    antworten[("PUT", "/api/planung/belegungen/aufgaben")] = kalender.KalenderNichtErreichbar("weg")
    a = _neu(client, kopf, titel="Trotzdem")
    r = client.put(f"/api/aufgaben/{a['id']}", headers=kopf,
                   json={"start": "2099-11-14T13:00:00", "ende": "2099-11-14T14:00:00"})
    assert r.status_code == 200
