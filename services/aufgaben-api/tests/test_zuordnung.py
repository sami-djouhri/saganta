"""Projekt oder Liste, Bedingungen, Herkunft und was der Planer daraus macht.

Sechste Fragerunde (04.11.), `docs/RICHTUNG.md`.
"""
import pytest
from sqlalchemy import create_engine, inspect, text

from test_kalender import kal  # noqa: F401  (Fixture)


def _neu(client, kopf, status=201, **felder):
    antwort = client.post("/api/aufgaben", json={"titel": "Reifen wechseln", **felder}, headers=kopf)
    assert antwort.status_code == status, antwort.text
    return antwort.json()


def _listen(client, kopf):
    return client.get("/api/listen", headers=kopf).json()


# --- Projekt oder Liste ---------------------------------------------------


def test_startlisten_beim_ersten_abruf_in_der_entschiedenen_reihenfolge(client, kopf):
    namen = [l["name"] for l in _listen(client, kopf)]
    assert namen == ["Arbeit", "Homelab", "Finanzen & Verträge", "Wohnung & Haushalt", "Grow",
                     "Gesundheit & Körper", "Erledigungen draußen"]
    assert len(_listen(client, kopf)) == 7, "ein zweiter Abruf legt nichts doppelt an"


def test_alle_listen_aufgeloest_kommen_nicht_wieder(client, kopf):
    for l in _listen(client, kopf):
        assert client.delete(f"/api/listen/{l['id']}", headers=kopf).status_code == 204
    assert _listen(client, kopf) == []


def test_liste_anlegen_umbenennen_aufloesen_laesst_die_aufgaben_stehen(client, kopf):
    neu = client.post("/api/listen", json={"name": "Garten"}, headers=kopf).json()
    assert neu["position"] > max(l["position"] for l in _listen(client, kopf) if l["id"] != neu["id"])
    a = _neu(client, kopf, liste_id=neu["id"])
    assert next(l for l in _listen(client, kopf) if l["id"] == neu["id"])["offen"] == 1
    assert client.put(f"/api/listen/{neu['id']}", json={"name": "Balkon"}, headers=kopf).json()["name"] == "Balkon"
    client.delete(f"/api/listen/{neu['id']}", headers=kopf)
    b = client.get(f"/api/aufgaben/{a['id']}", headers=kopf).json()
    assert b["liste_id"] is None, "nach dem Aufloesen steht sie unter Nicht zugeordnet"


def test_projekt_und_liste_zugleich_wird_abgelehnt(client, kopf):
    liste = _listen(client, kopf)[0]
    _neu(client, kopf, status=422, projekt="saganta-aufgaben", liste_id=liste["id"])
    a = _neu(client, kopf, projekt="saganta-aufgaben")
    assert client.put(f"/api/aufgaben/{a['id']}", json={"liste_id": liste["id"]}, headers=kopf).status_code == 422
    umgezogen = client.put(f"/api/aufgaben/{a['id']}", json={"projekt": None, "liste_id": liste["id"]}, headers=kopf)
    assert umgezogen.status_code == 200, "in einem Aufruf von Projekt zu Liste ist erlaubt"


def test_filter_nach_projekt_und_liste(client, kopf):
    liste = _listen(client, kopf)[1]
    p = _neu(client, kopf, projekt="gartiko")
    l = _neu(client, kopf, liste_id=liste["id"])
    _neu(client, kopf)
    assert [x["id"] for x in client.get("/api/aufgaben?projekt=gartiko", headers=kopf).json()] == [p["id"]]
    assert [x["id"] for x in client.get(f"/api/aufgaben?liste_id={liste['id']}", headers=kopf).json()] == [l["id"]]


def test_zaehlung_je_projekt(client, kopf, kopf_zwei):
    _neu(client, kopf, projekt="gartiko")
    erledigt = _neu(client, kopf, projekt="gartiko")
    client.post(f"/api/aufgaben/{erledigt['id']}/erledigt", headers=kopf)
    _neu(client, kopf_zwei, projekt="gartiko")
    assert client.get("/api/projekte/zaehlung", headers=kopf).json() == {
        "gartiko": {"offen": 1, "erledigt": 1, "hoch": 0}}


def test_zaehlung_hoch_nur_offene(client, kopf):
    _neu(client, kopf, projekt="gartiko", prioritaet="hoch")
    _neu(client, kopf, projekt="gartiko", prioritaet="hoch")
    _neu(client, kopf, projekt="gartiko", prioritaet="niedrig")
    erledigt = _neu(client, kopf, projekt="gartiko", prioritaet="hoch")
    client.post(f"/api/aufgaben/{erledigt['id']}/erledigt", headers=kopf)
    assert client.get("/api/projekte/zaehlung", headers=kopf).json() == {
        "gartiko": {"offen": 3, "erledigt": 1, "hoch": 2}}


def test_projekt_loesen_laesst_aufgaben_stehen_und_trifft_kein_fremdkonto(client, kopf, kopf_zwei):
    a = _neu(client, kopf, projekt="altprojekt")
    fremd = _neu(client, kopf_zwei, projekt="altprojekt")
    antwort = client.post("/api/projekte/altprojekt/loesen", headers=kopf).json()
    assert antwort == {"geloest": 1}
    assert client.get(f"/api/aufgaben/{a['id']}", headers=kopf).json()["projekt"] is None
    assert client.get(f"/api/aufgaben/{fremd['id']}", headers=kopf_zwei).json()["projekt"] == "altprojekt"


# --- Wo, wartet -----------------------------------------------------------


def test_kein_feld_wer(client, kopf):
    """Eine Aufgabe hat kein Feld fuer eine Zustaendigkeit."""
    assert "wer" not in _neu(client, kopf)


def test_bestimmter_ort_braucht_einen_namen_und_andere_orte_keinen(client, kopf):
    _neu(client, kopf, status=422, wo="ort")
    a = _neu(client, kopf, wo="ort", ort_name="Gym")
    b = client.put(f"/api/aufgaben/{a['id']}", json={"wo": "telefon"}, headers=kopf).json()
    assert b["wo"] == "telefon" and b["ort_name"] is None


def test_wartet_mit_grund_bis_er_geleert_wird(client, kopf):
    a = _neu(client, kopf, wartet_grund="Antwort vom Vermieter")
    assert a["wartet"]
    assert not client.put(f"/api/aufgaben/{a['id']}", json={"wartet_grund": None}, headers=kopf).json()["wartet"]


def test_wartet_bis_datum_und_danach_nicht_mehr(client, kopf):
    assert _neu(client, kopf, wartet_bis="2099-01-01", wartet_grund="erst dann")["wartet"]
    assert not _neu(client, kopf, wartet_bis="2020-01-01", wartet_grund="vorbei")["wartet"]


def test_wartet_auf_aufgabe_bis_die_erledigt_oder_geloescht_ist(client, kopf):
    vorher = _neu(client, kopf, titel="Angebot einholen")
    danach = _neu(client, kopf, titel="Auftrag erteilen", wartet_auf_id=vorher["id"])
    assert danach["wartet"]
    client.post(f"/api/aufgaben/{vorher['id']}/erledigt", headers=kopf)
    assert not client.get(f"/api/aufgaben/{danach['id']}", headers=kopf).json()["wartet"]
    client.post(f"/api/aufgaben/{vorher['id']}/offen", headers=kopf)
    client.delete(f"/api/aufgaben/{vorher['id']}", headers=kopf)
    b = client.get(f"/api/aufgaben/{danach['id']}", headers=kopf).json()
    assert b["wartet_auf_id"] is None and not b["wartet"]


def test_auf_sich_selbst_warten_wird_abgelehnt(client, kopf):
    a = _neu(client, kopf)
    assert client.put(f"/api/aufgaben/{a['id']}", json={"wartet_auf_id": a["id"]}, headers=kopf).status_code == 422


def test_zeitfenster_wird_geprueft(client, kopf):
    gut = _neu(client, kopf, zeitfenster=[{"tage": [4, 0, 0], "von": "08:00", "bis": "12:00"}], tageszeit="morgens")
    assert gut["zeitfenster"] == [{"tage": [0, 4], "von": "08:00", "bis": "12:00"}]
    _neu(client, kopf, status=422, zeitfenster=[{"tage": [7], "von": "08:00", "bis": "12:00"}])
    _neu(client, kopf, status=422, zeitfenster=[{"tage": [1], "von": "12:00", "bis": "08:00"}])
    _neu(client, kopf, status=422, zeitfenster=[{"tage": [1], "von": "8 Uhr", "bis": "12:00"}])
    _neu(client, kopf, status=422, tageszeit="nachts")
    b = client.put(f"/api/aufgaben/{gut['id']}", json={"zeitfenster": None}, headers=kopf).json()
    assert b["zeitfenster"] is None and b["tageszeit"] == "morgens"


def test_unteraufgaben_eine_ebene(client, kopf):
    """Owner 2026-11-06: Checkliste in der Aufgabe, Fortschritt in der Zeile."""
    a = _neu(client, kopf, unteraufgaben=[{"text": "Angebot holen"}, {"text": "Termin machen", "erledigt": True}])
    assert a["unteraufgaben"] == [{"text": "Angebot holen", "erledigt": False},
                                  {"text": "Termin machen", "erledigt": True}]
    b = client.put(f"/api/aufgaben/{a['id']}", json={"unteraufgaben": [{"text": "Angebot holen", "erledigt": True}]},
                   headers=kopf).json()
    assert b["unteraufgaben"] == [{"text": "Angebot holen", "erledigt": True}]
    # Nicht geschickt bleibt, null leert.
    assert client.put(f"/api/aufgaben/{a['id']}", json={"titel": "Dach"}, headers=kopf).json()["unteraufgaben"]
    assert client.put(f"/api/aufgaben/{a['id']}", json={"unteraufgaben": None}, headers=kopf).json()["unteraufgaben"] is None
    _neu(client, kopf, status=422, unteraufgaben=[{"text": ""}])
    _neu(client, kopf, status=422, unteraufgaben=[{"text": "x", "tief": [{"text": "y"}]}])


# --- Herkunft (Umzug) -----------------------------------------------------


def test_herkunft_ist_eindeutig_und_findet_offen_wie_erledigt(client, kopf):
    a = _neu(client, kopf, herkunft="projectdeck:7", projekt="gartiko")
    _neu(client, kopf, status=409, herkunft="projectdeck:7")
    client.post(f"/api/aufgaben/{a['id']}/erledigt", headers=kopf)
    gefunden = client.get("/api/aufgaben?herkunft=projectdeck:7", headers=kopf).json()
    assert [x["id"] for x in gefunden] == [a["id"]]


def test_erledigt_anlegen_fuer_den_verlauf(client, kopf):
    a = _neu(client, kopf, herkunft="projectdeck:8", erledigt_am="2026-10-01T10:00:00+00:00")
    assert a["erledigt"] and a["erledigt_am"].startswith("2026-10-01T12:00")
    assert client.get("/api/aufgaben", headers=kopf).json() == []


# --- Mandantengrenze ------------------------------------------------------


def test_fremde_liste_fremde_aufgabe_fremde_herkunft(client, kopf, kopf_zwei):
    fremde_liste = _listen(client, kopf_zwei)[0]
    fremde = _neu(client, kopf_zwei, herkunft="projectdeck:1")
    _neu(client, kopf, status=422, liste_id=fremde_liste["id"])
    _neu(client, kopf, status=422, wartet_auf_id=fremde["id"])
    assert client.put(f"/api/listen/{fremde_liste['id']}", json={"name": "x"}, headers=kopf).status_code == 404
    assert client.delete(f"/api/listen/{fremde_liste['id']}", headers=kopf).status_code == 404
    assert client.get("/api/aufgaben?herkunft=projectdeck:1", headers=kopf).json() == []
    eigene = _neu(client, kopf, herkunft="projectdeck:1")
    assert eigene["herkunft"] == "projectdeck:1", "dieselbe Herkunft in zwei Konten ist kein Widerspruch"
    assert len(_listen(client, kopf_zwei)) == 7


# --- Planer ---------------------------------------------------------------


def _plan(client, kopf, kal, datum="2026-11-04", **antwort):
    gesehen, antworten = kal
    antworten[("POST", "/api/assistant/vorschlag")] = {"suggestions": [], "deferred": [], **antwort}
    plan = client.post("/api/planen", json={"datum": datum}, headers=kopf).json()
    return plan, gesehen[-1][2]["json"]


def test_planer_laesst_wartende_und_unterwegs_aus(kal, client, kopf):  # noqa: F811
    du = _neu(client, kopf, titel="Meins", wo="rechner")
    _neu(client, kopf, titel="Wartet", wartet_grund="Rueckruf")
    _neu(client, kopf, titel="Wartet bis morgen", wartet_bis="2026-11-05")
    frei = _neu(client, kopf, titel="Ab heute frei", wartet_bis="2026-11-04", wo="telefon")
    _neu(client, kopf, titel="Baumarkt", wo="unterwegs")
    _neu(client, kopf, titel="Training", wo="ort", ort_name="Gym")
    plan, anfrage = _plan(client, kopf, kal)
    assert {a["id"] for a in anfrage["aufgaben"]} == {du["id"], frei["id"]}
    assert sorted(plan["ohne_fenster"]) == ["Ab heute frei", "Meins"], \
        "Wartende und Unterwegs sind keine Kandidaten, also auch nicht ohne Fenster"


def test_planer_zeitfenster_wochentag_und_uhrzeit(kal, client, kopf):  # noqa: F811
    # 2026-11-04 ist ein Mittwoch (2).
    nur_montag = _neu(client, kopf, titel="Praxis", zeitfenster=[{"tage": [0], "von": "08:00", "bis": "12:00"}])
    vormittag = _neu(client, kopf, titel="Amt", zeitfenster=[{"tage": [2], "von": "08:00", "bis": "12:00"}])
    abends = _neu(client, kopf, titel="Lesen", tageszeit="abends")
    plan, anfrage = _plan(client, kopf, kal, suggestions=[
        {"todo_id": vormittag["id"], "title": "Amt", "start": "2026-11-04T11:30:00",
         "end": "2026-11-04T12:30:00", "minutes": 60},
        {"todo_id": abends["id"], "title": "Lesen", "start": "2026-11-04T19:00:00",
         "end": "2026-11-04T19:30:00", "minutes": 30},
    ])
    assert nur_montag["id"] not in {a["id"] for a in anfrage["aufgaben"]}
    gruende = {z["aufgabe_id"]: z["grund"] for z in plan["zurueck"]}
    assert gruende == {nur_montag["id"]: "zeitfenster", vormittag["id"]: "zeitfenster"}, \
        "11:30 bis 12:30 ragt ueber das Fenster hinaus"
    assert [v["aufgabe_id"] for v in plan["vorschlaege"]] == [abends["id"]]
    assert plan["ohne_fenster"] == []


def test_planer_tageszeit_verwirft_falsche_lage(kal, client, kopf):  # noqa: F811
    morgens = _neu(client, kopf, titel="Laufen", tageszeit="morgens")
    plan, _ = _plan(client, kopf, kal, suggestions=[
        {"todo_id": morgens["id"], "title": "Laufen", "start": "2026-11-04T16:00:00",
         "end": "2026-11-04T16:30:00", "minutes": 30}])
    assert plan["vorschlaege"] == [] and plan["zurueck"][0]["grund"] == "tageszeit"


# --- Bestand vom 03.11. ---------------------------------------------------


def test_alte_tabelle_bekommt_die_neuen_spalten(tmp_path, monkeypatch):
    """create_all legt keine Spalten nach; ohne den Nachzug scheitert das erste Lesen."""
    from app import db as db_modul

    alt = create_engine(f"sqlite:///{tmp_path}/alt.db")
    with alt.begin() as conn:
        conn.execute(text(
            "CREATE TABLE aufgaben (id VARCHAR(36) PRIMARY KEY, owner_sub VARCHAR(128) NOT NULL, "
            "titel VARCHAR(500) NOT NULL, erledigt BOOLEAN NOT NULL DEFAULT 0, "
            "wer VARCHAR(10) NOT NULL DEFAULT 'du')"))
        conn.execute(text("INSERT INTO aufgaben (id, owner_sub, titel) VALUES ('a', 'x', 'alt')"))
    monkeypatch.setattr(db_modul, "engine", alt)
    db_modul._spalten_nachziehen()
    db_modul._spalten_nachziehen()  # zweimal: idempotent
    spalten = {c["name"] for c in inspect(alt).get_columns("aufgaben")}
    assert {"projekt", "liste_id", "wartet_grund", "zeitfenster", "herkunft"} <= spalten
    assert "wer" not in spalten
    with alt.connect() as conn:
        assert conn.execute(text("SELECT titel FROM aufgaben")).scalar() == "alt"
    indizes = {i["name"] for i in inspect(alt).get_indexes("aufgaben")}
    assert "uq_aufgaben_herkunft" in indizes


@pytest.mark.parametrize("pfad", ["/api/listen", "/api/projekte/zaehlung"])
def test_neue_wege_ohne_token_zu(client, pfad):
    assert client.get(pfad).status_code == 401
