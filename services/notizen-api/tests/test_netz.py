"""Verweise zwischen Notizen: verbunden und [[Titel]] (seit 2026-11-20)."""
from app.routes_netz import text_verweise


def _notiz(client, kopf, titel, inhalt=""):
    r = client.post("/api/notizen", json={"titel": titel, "inhalt": inhalt}, headers=kopf)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _netz(client, kopf, nid):
    r = client.get(f"/api/notizen/{nid}/netz", headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()


def test_text_verweise_lesen():
    text = "Siehe [[Garten]] und [[garten]], [[Keller|den Keller]].\n`[[nicht]]`\n```\n[[auch nicht]]\n```\n[[  Dach  ]]"
    assert text_verweise(text) == ["Garten", "Keller", "Dach"]
    assert text_verweise("[[]] [[a\nb]] [[x[y]]") == []


def test_mehrere_auf_einmal_verbinden_jede_mit_jeder(client, kopf):
    a, b, c = (_notiz(client, kopf, t) for t in ("A", "B", "C"))
    r = client.post("/api/notizen/verbinden", json={"ids": [a, b, c]}, headers=kopf)
    assert r.json() == {"neu": 3, "vorhanden": 0}
    assert {n["id"] for n in _netz(client, kopf, a)["verbunden"]} == {b, c}
    assert {n["id"] for n in _netz(client, kopf, c)["verbunden"]} == {a, b}
    # Ein zweiter Aufruf legt nichts doppelt an.
    r = client.post("/api/notizen/verbinden", json={"ids": [c, a, b, a]}, headers=kopf)
    assert r.json() == {"neu": 0, "vorhanden": 3}


def test_verbinden_ganz_oder_gar_nicht(client, kopf, kopf_zwei):
    a, b = _notiz(client, kopf, "A"), _notiz(client, kopf, "B")
    fremd = _notiz(client, kopf_zwei, "Fremd")
    r = client.post("/api/notizen/verbinden", json={"ids": [a, b, fremd]}, headers=kopf)
    assert r.status_code == 404
    assert _netz(client, kopf, a)["verbunden"] == []
    assert client.post("/api/notizen/verbinden", json={"ids": [a, a]}, headers=kopf).status_code == 400


def test_einzeln_verbinden_und_loesen(client, kopf, kopf_zwei):
    a, b = _notiz(client, kopf, "A"), _notiz(client, kopf, "B")
    r = client.post(f"/api/notizen/{a}/verbunden", json={"mit": b}, headers=kopf)
    assert r.status_code == 201 and [n["titel"] for n in r.json()] == ["B"]
    assert client.post(f"/api/notizen/{a}/verbunden", json={"mit": a}, headers=kopf).status_code == 400
    # Ein fremdes Konto kann die Verbindung weder lesen noch loesen.
    assert client.get(f"/api/notizen/{a}/netz", headers=kopf_zwei).status_code == 404
    assert client.delete(f"/api/notizen/{b}/verbunden/{a}", headers=kopf_zwei).status_code == 404
    # Loesen geht von beiden Seiten aus.
    assert client.delete(f"/api/notizen/{b}/verbunden/{a}", headers=kopf).status_code == 204
    assert _netz(client, kopf, a)["verbunden"] == []
    assert client.delete(f"/api/notizen/{b}/verbunden/{a}", headers=kopf).status_code == 404


def test_loeschen_nimmt_verbindung_mit_papierkorb_bringt_sie_zurueck(client, kopf):
    a, b, c = (_notiz(client, kopf, t) for t in ("A", "B", "C"))
    client.post("/api/notizen/verbinden", json={"ids": [a, b, c]}, headers=kopf)
    assert client.delete(f"/api/notizen/{a}", headers=kopf).status_code == 204
    assert {n["id"] for n in _netz(client, kopf, b)["verbunden"]} == {c}
    # C verschwindet endgueltig, bevor A zurueckkommt: nur B wird wieder verbunden.
    client.delete(f"/api/notizen/{c}", headers=kopf)
    eintraege = client.get("/api/notizen/papierkorb/liste", headers=kopf).json()
    a_eintrag = next(e for e in eintraege if e["titel"] == "A")
    neu = client.post(f"/api/notizen/papierkorb/{a_eintrag['id']}/wiederherstellen", headers=kopf).json()
    assert [n["id"] for n in _netz(client, kopf, neu["id"])["verbunden"]] == [b]


def test_text_verweis_hin_und_zurueck(client, kopf):
    garten = _notiz(client, kopf, "Garten")
    plan = _notiz(client, kopf, "Plan", "Erst [[garten]], dann [[Dach]].")
    netz = _netz(client, kopf, plan)
    assert netz["verweist_auf"] == [{"text": "garten", "id": garten}, {"text": "Dach", "id": None}]
    assert [n["id"] for n in _netz(client, kopf, garten)["erwaehnt_in"]] == [plan]
    # Wird das Ziel angelegt, loest der Verweis ohne Zutun auf.
    dach = _notiz(client, kopf, "Dach")
    assert _netz(client, kopf, plan)["verweist_auf"][1]["id"] == dach


def test_text_verweis_bleibt_im_eigenen_konto(client, kopf, kopf_zwei):
    _notiz(client, kopf_zwei, "Garten")
    plan = _notiz(client, kopf, "Plan", "[[Garten]]")
    assert _netz(client, kopf, plan)["verweist_auf"] == [{"text": "Garten", "id": None}]
    eigener = _notiz(client, kopf_zwei, "Spiegel", "[[Plan]]")
    assert _netz(client, kopf, plan)["erwaehnt_in"] == []
    assert _netz(client, kopf_zwei, eigener)["verweist_auf"] == [{"text": "Plan", "id": None}]


def test_gleiche_titel_der_zuletzt_geaenderte_gewinnt(client, kopf):
    alt = _notiz(client, kopf, "Garten")
    neu = _notiz(client, kopf, "Garten")
    plan = _notiz(client, kopf, "Plan", "[[Garten]]")
    assert _netz(client, kopf, plan)["verweist_auf"][0]["id"] == neu
    # Erwaehnt wird nur die Notiz, auf die der Link fuehrt.
    assert _netz(client, kopf, alt)["erwaehnt_in"] == []
    assert [n["id"] for n in _netz(client, kopf, neu)["erwaehnt_in"]] == [plan]


def test_titel_vorschlaege_vorne_vor_mitte_und_umlaute(client, kopf, kopf_zwei):
    _notiz(client, kopf, "Gartenplan")
    _notiz(client, kopf, "Ärger mit dem Garten")
    _notiz(client, kopf, "Garten")
    _notiz(client, kopf, "garten")  # gleichnamig: zeigt sich einmal
    _notiz(client, kopf, "Keller")
    _notiz(client, kopf_zwei, "Garten fremd")
    r = client.get("/api/notizen/titel", params={"q": "gar"}, headers=kopf)
    assert r.status_code == 200, r.text
    titel = [t["titel"] for t in r.json()]
    assert titel[:2] == ["garten", "Gartenplan"]
    assert titel[2:] == ["Ärger mit dem Garten"]
    r = client.get("/api/notizen/titel", params={"q": "ärg"}, headers=kopf)
    assert [t["titel"] for t in r.json()] == ["Ärger mit dem Garten"]
    # Ohne Eingabe die zuletzt geaenderten, mit Grenze.
    r = client.get("/api/notizen/titel", params={"limit": 2}, headers=kopf)
    assert len(r.json()) == 2


def test_gesamtnetz_kanten_eine_je_paar(client, kopf, kopf_zwei):
    a = _notiz(client, kopf, "A", "siehe [[B]] und [[Fehlt]]")
    b = _notiz(client, kopf, "B", "zurueck zu [[A]]")
    c = _notiz(client, kopf, "C", "[[A]]")
    d = _notiz(client, kopf, "D")
    client.post("/api/notizen/verbinden", json={"ids": [a, c]}, headers=kopf)
    _notiz(client, kopf_zwei, "Fremd", "[[A]]")
    r = client.get("/api/notizen/netz", headers=kopf)
    assert r.status_code == 200, r.text
    netz = r.json()
    kanten = {(min(k["a"], k["b"]), max(k["a"], k["b"])): k["art"] for k in netz["kanten"]}
    # A-B per Text (beide Richtungen, eine Linie), A-C von Hand gewinnt gegen Text.
    assert kanten == {(min(a, b), max(a, b)): "text", (min(a, c), max(a, c)): "verbunden"}
    knoten = {k["id"]: k for k in netz["knoten"]}
    assert set(knoten) == {a, b, c, d}
    assert knoten[a]["grad"] == 2 and knoten[d]["grad"] == 0
    assert knoten[a]["offene_verweise"] == 1


def test_gesamtnetz_ohne_archivierte(client, kopf):
    a = _notiz(client, kopf, "A", "[[B]]")
    b = _notiz(client, kopf, "B")
    client.patch(f"/api/notizen/{b}", json={"archiviert": True}, headers=kopf)
    netz = client.get("/api/notizen/netz", headers=kopf).json()
    assert {k["id"] for k in netz["knoten"]} == {a} and netz["kanten"] == []
    netz = client.get("/api/notizen/netz", params={"archivierte": "true"}, headers=kopf).json()
    assert len(netz["kanten"]) == 1
