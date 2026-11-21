"""Grundlagen: Notizbuecher, Notizen, Suche, Tags, und die Mandantengrenze."""


def test_notizbuch_und_notiz_anlegen(client, kopf):
    buch = client.post("/api/notizbuecher", json={"name": "Haushalt"}, headers=kopf)
    assert buch.status_code == 201, buch.text
    buch_id = buch.json()["id"]

    notiz = client.post(
        "/api/notizen",
        json={
            "titel": "Heizung ablesen",
            "inhalt": "# Zaehlerstand\n\nKueche: 4711",
            "notizbuch_id": buch_id,
            "tags": ["Wohnung", "  ablesen "],
        },
        headers=kopf,
    )
    assert notiz.status_code == 201, notiz.text
    daten = notiz.json()
    assert daten["titel"] == "Heizung ablesen"
    # Tags werden normalisiert: klein, ohne Randleerzeichen
    assert daten["tags"] == ["wohnung", "ablesen"]

    liste = client.get("/api/notizbuecher", headers=kopf).json()
    assert liste[0]["anzahl_notizen"] == 1


def test_doppelter_notizbuchname_wird_abgelehnt(client, kopf):
    client.post("/api/notizbuecher", json={"name": "Arbeit"}, headers=kopf)
    zweit = client.post("/api/notizbuecher", json={"name": "Arbeit"}, headers=kopf)
    assert zweit.status_code == 409


def test_fremde_notiz_ist_unsichtbar(client, kopf, kopf_zwei):
    notiz = client.post(
        "/api/notizen", json={"titel": "Privat", "inhalt": "geheim"}, headers=kopf
    ).json()

    # Weder lesen ...
    assert client.get(f"/api/notizen/{notiz['id']}", headers=kopf_zwei).status_code == 404
    # ... noch aendern, loeschen oder in der Liste sehen.
    assert (
        client.patch(
            f"/api/notizen/{notiz['id']}", json={"titel": "gekapert"}, headers=kopf_zwei
        ).status_code
        == 404
    )
    assert client.delete(f"/api/notizen/{notiz['id']}", headers=kopf_zwei).status_code == 404
    assert client.get("/api/notizen", headers=kopf_zwei).json() == []


def test_fremdes_notizbuch_kann_nicht_belegt_werden(client, kopf, kopf_zwei):
    buch = client.post("/api/notizbuecher", json={"name": "Fremd"}, headers=kopf).json()
    antwort = client.post(
        "/api/notizen", json={"titel": "x", "notizbuch_id": buch["id"]}, headers=kopf_zwei
    )
    assert antwort.status_code == 400


def test_ohne_token_kein_zugriff(client):
    assert client.get("/api/notizen").status_code == 401
    assert client.get("/api/notizen", headers={"Authorization": "Bearer murks"}).status_code == 401


def test_volltextsuche_findet_und_sortiert(client, kopf):
    client.post(
        "/api/notizen",
        json={"titel": "Rechnung Stadtwerke", "inhalt": "Strom und Wasser, faellig im Maerz"},
        headers=kopf,
    )
    client.post(
        "/api/notizen", json={"titel": "Einkauf", "inhalt": "Milch, Brot, Butter"}, headers=kopf
    )

    treffer = client.get("/api/notizen", params={"q": "strom"}, headers=kopf).json()
    assert len(treffer) == 1
    assert treffer[0]["titel"] == "Rechnung Stadtwerke"

    # Praefix-Suche auf dem letzten Wort, man tippt ja noch.
    assert len(client.get("/api/notizen", params={"q": "rechn"}, headers=kopf).json()) == 1
    # Zwei Woerter sind ein UND, kein ODER.
    assert client.get("/api/notizen", params={"q": "strom milch"}, headers=kopf).json() == []


def test_suche_bleibt_in_der_eigenen_spur(client, kopf, kopf_zwei):
    client.post(
        "/api/notizen", json={"titel": "Codewort Nordwind", "inhalt": "streng"}, headers=kopf
    )
    assert client.get("/api/notizen", params={"q": "nordwind"}, headers=kopf_zwei).json() == []


def test_suche_vertraegt_sonderzeichen(client, kopf):
    """Eingaben wie ``"`` oder ``OR`` duerfen die Abfragesprache nicht steuern."""
    client.post("/api/notizen", json={"titel": "Test", "inhalt": "harmlos"}, headers=kopf)
    for eingabe in ['"', 'a" OR "b', "*", "-notiz", "AND", "NEAR("]:
        antwort = client.get("/api/notizen", params={"q": eingabe}, headers=kopf)
        assert antwort.status_code == 200, f"{eingabe} → {antwort.text}"


def test_suche_findet_geaenderten_text_nicht_mehr_unter_dem_alten(client, kopf):
    notiz = client.post(
        "/api/notizen", json={"titel": "Alt", "inhalt": "Blaubeere"}, headers=kopf
    ).json()
    client.patch(f"/api/notizen/{notiz['id']}", json={"inhalt": "Himbeere"}, headers=kopf)
    assert client.get("/api/notizen", params={"q": "blaubeere"}, headers=kopf).json() == []
    assert len(client.get("/api/notizen", params={"q": "himbeere"}, headers=kopf).json()) == 1


def test_geloeschte_notiz_verschwindet_aus_der_suche(client, kopf):
    notiz = client.post(
        "/api/notizen", json={"titel": "Weg", "inhalt": "Sonnenblume"}, headers=kopf
    ).json()
    client.delete(f"/api/notizen/{notiz['id']}", headers=kopf)
    assert client.get("/api/notizen", params={"q": "sonnenblume"}, headers=kopf).json() == []


def test_tag_filter_trifft_nur_ganze_tags(client, kopf):
    client.post("/api/notizen", json={"titel": "A", "tags": ["haus"]}, headers=kopf)
    client.post("/api/notizen", json={"titel": "B", "tags": ["hausrat"]}, headers=kopf)
    treffer = client.get("/api/notizen", params={"tag": "haus"}, headers=kopf).json()
    assert [t["titel"] for t in treffer] == ["A"]


def test_tagliste_sammelt_alle(client, kopf):
    client.post("/api/notizen", json={"titel": "A", "tags": ["b", "a"]}, headers=kopf)
    client.post("/api/notizen", json={"titel": "B", "tags": ["a", "c"]}, headers=kopf)
    assert client.get("/api/notizen/tags", headers=kopf).json() == ["a", "b", "c"]


def test_notizbuch_loeschen_behaelt_die_notizen(client, kopf):
    buch = client.post("/api/notizbuecher", json={"name": "Temporaer"}, headers=kopf).json()
    notiz = client.post(
        "/api/notizen", json={"titel": "Bleibt", "notizbuch_id": buch["id"]}, headers=kopf
    ).json()
    assert client.delete(f"/api/notizbuecher/{buch['id']}", headers=kopf).status_code == 204
    danach = client.get(f"/api/notizen/{notiz['id']}", headers=kopf).json()
    assert danach["notizbuch_id"] is None


def test_notiz_aus_dem_notizbuch_loesen(client, kopf):
    buch = client.post("/api/notizbuecher", json={"name": "Irgendwo"}, headers=kopf).json()
    notiz = client.post(
        "/api/notizen", json={"titel": "X", "notizbuch_id": buch["id"]}, headers=kopf
    ).json()
    # Ohne das ausdrueckliche Flag laesst sich „kein Notizbuch" nicht ausdruecken:
    # None im Patch heisst „nicht angefasst".
    gleich = client.patch(
        f"/api/notizen/{notiz['id']}", json={"notizbuch_id": None}, headers=kopf
    ).json()
    assert gleich["notizbuch_id"] == buch["id"]
    geloest = client.patch(
        f"/api/notizen/{notiz['id']}", json={"notizbuch_loesen": True}, headers=kopf
    ).json()
    assert geloest["notizbuch_id"] is None


def test_archivierte_erscheinen_nur_auf_wunsch(client, kopf):
    notiz = client.post("/api/notizen", json={"titel": "Alt"}, headers=kopf).json()
    client.patch(f"/api/notizen/{notiz['id']}", json={"archiviert": True}, headers=kopf)
    assert client.get("/api/notizen", headers=kopf).json() == []
    assert len(client.get("/api/notizen", params={"archivierte": True}, headers=kopf).json()) == 1


def test_speichern_mit_veraltetem_stand_wird_abgewiesen(client, kopf):
    notiz = client.post("/api/notizen", json={"titel": "Plan", "inhalt": "a"}, headers=kopf).json()
    # Das zweite Geraet speichert zuerst ...
    zwischen = client.patch(f"/api/notizen/{notiz['id']}", json={"inhalt": "b"}, headers=kopf)
    assert zwischen.status_code == 200
    # ... das erste kennt noch den alten Stand und darf nicht still gewinnen.
    antwort = client.patch(
        f"/api/notizen/{notiz['id']}",
        json={"inhalt": "c", "basis_geaendert_am": notiz["geaendert_am"]},
        headers=kopf,
    )
    assert antwort.status_code == 409
    danach = client.get(f"/api/notizen/{notiz['id']}", headers=kopf).json()
    assert danach["inhalt"] == "b"


def test_speichern_mit_aktuellem_stand_geht_durch(client, kopf):
    notiz = client.post("/api/notizen", json={"titel": "Plan", "inhalt": "a"}, headers=kopf).json()
    antwort = client.patch(
        f"/api/notizen/{notiz['id']}",
        json={"inhalt": "neu", "basis_geaendert_am": notiz["geaendert_am"]},
        headers=kopf,
    )
    assert antwort.status_code == 200
    assert antwort.json()["inhalt"] == "neu"


def test_stand_mit_zeitzone_wird_verstanden(client, kopf):
    # Ein Client darf den Stempel als UTC mit Z-Endung zurueckgeben; der
    # Bestand liegt naiv, verglichen wird trotzdem derselbe Zeitpunkt.
    notiz = client.post("/api/notizen", json={"titel": "Zeit", "inhalt": "a"}, headers=kopf).json()
    antwort = client.patch(
        f"/api/notizen/{notiz['id']}",
        json={"inhalt": "b", "basis_geaendert_am": notiz["geaendert_am"] + "Z"},
        headers=kopf,
    )
    assert antwort.status_code == 200


def test_speichern_ohne_stand_bleibt_letzter_gewinnt(client, kopf):
    # Aeltere Clients (die Android-App) senden das Feld nicht; fuer sie
    # aendert sich nichts.
    notiz = client.post("/api/notizen", json={"titel": "Alt", "inhalt": "a"}, headers=kopf).json()
    client.patch(f"/api/notizen/{notiz['id']}", json={"inhalt": "b"}, headers=kopf)
    antwort = client.patch(f"/api/notizen/{notiz['id']}", json={"inhalt": "c"}, headers=kopf)
    assert antwort.status_code == 200
    assert antwort.json()["inhalt"] == "c"


def test_like_weg_nimmt_platzhalter_woertlich(client, kopf, monkeypatch):
    """Ohne FTS sucht der LIKE-Weg; ``_`` und ``%`` aus der Eingabe sind dort Zeichen."""
    from app import db

    monkeypatch.setattr(db, "FTS_AKTIV", False)
    client.post("/api/notizen", json={"titel": "Rabatt", "inhalt": "100% sicher"}, headers=kopf)
    client.post("/api/notizen", json={"titel": "Ohne", "inhalt": "1000 Stueck"}, headers=kopf)
    client.post("/api/notizen", json={"titel": "Zeichen", "inhalt": "a_b"}, headers=kopf)
    titel = lambda q: sorted(  # noqa: E731
        n["titel"] for n in client.get("/api/notizen", params={"q": q}, headers=kopf).json()
    )
    assert titel("100%") == ["Rabatt"]
    assert titel("_") == ["Zeichen"]


# --- Filter (seit 2026-11-21) -------------------------------------------


def _titel(client, kopf, **params):
    return [n["titel"] for n in client.get("/api/notizen", params=params, headers=kopf).json()]


def test_suche_haelt_den_tag_filter(client, kopf):
    """Bis 2026-11-21 fiel der Tag weg, sobald ein Suchwort dastand."""
    client.post("/api/notizen", json={"titel": "A", "inhalt": "Kiwi", "tags": ["obst"]}, headers=kopf)
    client.post("/api/notizen", json={"titel": "B", "inhalt": "Kiwi", "tags": ["vogel"]}, headers=kopf)
    assert _titel(client, kopf, q="kiwi", tag="obst") == ["A"]


def test_mehrere_tags_muessen_alle_passen(client, kopf):
    client.post("/api/notizen", json={"titel": "A", "tags": ["haus", "garten"]}, headers=kopf)
    client.post("/api/notizen", json={"titel": "B", "tags": ["haus"]}, headers=kopf)
    assert _titel(client, kopf, tag="haus,garten") == ["A"]
    assert sorted(_titel(client, kopf, tag="haus")) == ["A", "B"]


def test_tag_mit_platzhalter_zaehlt_woertlich(client, kopf):
    client.post("/api/notizen", json={"titel": "A", "tags": ["a_b"]}, headers=kopf)
    client.post("/api/notizen", json={"titel": "B", "tags": ["axb"]}, headers=kopf)
    assert _titel(client, kopf, tag="a_b") == ["A"]


def test_ohne_notizbuch(client, kopf):
    buch = client.post("/api/notizbuecher", json={"name": "Arbeit"}, headers=kopf).json()
    client.post("/api/notizen", json={"titel": "Drin", "notizbuch_id": buch["id"]}, headers=kopf)
    client.post("/api/notizen", json={"titel": "Lose"}, headers=kopf)
    assert _titel(client, kopf, ohne_notizbuch="true") == ["Lose"]


def test_hat_filter(client, kopf):
    mit_aufgabe = client.post(
        "/api/notizen",
        json={"titel": "Aufgabe", "verknuepfung": {"typ": "aufgabe", "ref": "a-1", "label": "x"}},
        headers=kopf,
    ).json()
    client.post("/api/notizen", json={"titel": "Verweis", "inhalt": "siehe [[Aufgabe]]"}, headers=kopf)
    angeheftet = client.post("/api/notizen", json={"titel": "Oben"}, headers=kopf).json()
    client.patch(f"/api/notizen/{angeheftet['id']}", json={"angeheftet": True}, headers=kopf)
    client.post("/api/notizen", json={"titel": "Nichts"}, headers=kopf)

    assert _titel(client, kopf, hat="aufgabe") == ["Aufgabe"]
    # Die Notiz mit [[ ]] und die, auf die er zeigt? Nur die Quelle: das Ziel
    # hat selbst keinen Verweis.
    assert _titel(client, kopf, hat="verweis") == ["Verweis"]
    assert _titel(client, kopf, hat="angeheftet") == ["Oben"]
    assert _titel(client, kopf, hat="aufgabe,angeheftet") == []
    client.post(f"/api/freigaben/notizen/{mit_aufgabe['id']}", json={}, headers=kopf)
    assert _titel(client, kopf, hat="freigabe") == ["Aufgabe"]


def test_unbekannter_filter_und_sortierung_werden_abgelehnt(client, kopf):
    assert client.get("/api/notizen", params={"hat": "quatsch"}, headers=kopf).status_code == 400
    assert client.get("/api/notizen", params={"sortierung": "quatsch"}, headers=kopf).status_code == 400


def test_sortierung_nach_titel_und_erstellt(client, kopf):
    for t in ["banane", "Apfel", "", "citrus"]:
        client.post("/api/notizen", json={"titel": t}, headers=kopf)
    assert _titel(client, kopf, sortierung="titel") == ["Apfel", "banane", "citrus", ""]
    assert _titel(client, kopf, sortierung="erstellt") == ["citrus", "", "Apfel", "banane"]
