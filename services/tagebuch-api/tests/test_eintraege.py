from datetime import date, timedelta

import pytest


def _eintrag(text: str = "Y2hpZmZyYXQ=") -> dict:
    return {"chiffrat": text, "iv": "aXYtd2VydA==", "schluessel_version": 1}


@pytest.fixture(autouse=True)
def tresore_angelegt(client, kopf, kopf_zwei, tresor_daten):
    """Beide Nutzer dieser Datei haben einen Tresor, bevor sie schreiben.

    Seit dem 2026-10-16 lehnt ``PUT /api/eintraege/<tag>`` ohne Tresor mit
    409 ab. Vorher nahm er alles an, und gemessen entstand dabei
    ``eintraege: 1, tresore: 0``: ein Chiffrat, zu dem kein Schluessel
    existiert, also dauerhaft unlesbar und mit HTTP 200 bestaetigt.

    Diese Vorbereitung ist deshalb keine Umgehung des neuen Riegels, sondern die
    Nachbildung des echten Ablaufs -- ein Browser kann ohne entsperrten Tresor
    gar nicht verschluesseln. Der Riegel selbst wird unten mit einem **dritten**
    Nutzer geprueft, der bewusst keinen hat.
    """
    for k in (kopf, kopf_zwei):
        client.put("/api/tresor", json=tresor_daten, headers=k)


def test_anlegen_und_lesen(client, kopf):
    antwort = client.put("/api/eintraege/2026-09-06", json=_eintrag(), headers=kopf)
    assert antwort.status_code == 200
    assert antwort.json()["chiffrat"] == "Y2hpZmZyYXQ="

    gelesen = client.get("/api/eintraege/2026-09-06", headers=kopf)
    assert gelesen.status_code == 200
    assert gelesen.json()["datum"] == "2026-09-06"


def test_ein_tag_ein_eintrag(client, kopf):
    """Zweimal derselbe Tag ueberschreibt, statt eine zweite Zeile anzulegen."""
    client.put("/api/eintraege/2026-09-06", json=_eintrag("ZXJzdA=="), headers=kopf)
    client.put("/api/eintraege/2026-09-06", json=_eintrag("endlZXQ="), headers=kopf)

    liste = client.get(
        "/api/eintraege", params={"von": "2026-09-01", "bis": "2026-09-30"}, headers=kopf
    )
    assert len(liste.json()) == 1
    assert liste.json()[0]["chiffrat"] == "endlZXQ="


def test_fehlender_tag_ist_404(client, kopf):
    assert client.get("/api/eintraege/2026-01-01", headers=kopf).status_code == 404


def test_loeschen(client, kopf):
    client.put("/api/eintraege/2026-09-06", json=_eintrag(), headers=kopf)
    assert client.delete("/api/eintraege/2026-09-06", headers=kopf).status_code == 204
    assert client.get("/api/eintraege/2026-09-06", headers=kopf).status_code == 404


def test_ohne_token_kein_zugriff(client):
    assert client.get("/api/eintraege/2026-09-06").status_code == 401
    assert client.put("/api/eintraege/2026-09-06", json=_eintrag()).status_code == 401


class TestMandantentrennung:
    """Der wichtigste Block: fremde Eintraege sind unsichtbar und unantastbar."""

    def test_fremder_eintrag_ist_unsichtbar(self, client, kopf, kopf_zwei):
        client.put("/api/eintraege/2026-09-06", json=_eintrag("Z2VoZWlt"), headers=kopf)

        assert client.get("/api/eintraege/2026-09-06", headers=kopf_zwei).status_code == 404
        liste = client.get(
            "/api/eintraege",
            params={"von": "2026-01-01", "bis": "2026-12-31"},
            headers=kopf_zwei,
        )
        assert liste.json() == []
        assert client.get("/api/eintraege/tage", params={"jahr": 2026}, headers=kopf_zwei).json() == []

    def test_fremder_schreibt_nicht_in_meinen_tag(self, client, kopf, kopf_zwei):
        client.put("/api/eintraege/2026-09-06", json=_eintrag("bWVpbnM="), headers=kopf)
        client.put("/api/eintraege/2026-09-06", json=_eintrag("c2VpbnM="), headers=kopf_zwei)

        meins = client.get("/api/eintraege/2026-09-06", headers=kopf)
        assert meins.json()["chiffrat"] == "bWVpbnM="

    def test_fremder_loescht_meinen_tag_nicht(self, client, kopf, kopf_zwei):
        client.put("/api/eintraege/2026-09-06", json=_eintrag(), headers=kopf)
        assert client.delete("/api/eintraege/2026-09-06", headers=kopf_zwei).status_code == 404
        assert client.get("/api/eintraege/2026-09-06", headers=kopf).status_code == 200


class TestUebersicht:
    def test_uebersicht_kollidiert_nicht_mit_datum(self, client, kopf):
        """Haelt die Routen-Reihenfolge fest.

        Stuende "/{datum}" vor "/tage", laese FastAPI das Wort "tage" als Datum
        und antwortete 422. Beim Lesen des Codes faellt das nicht auf, beim
        Benutzen sofort: die Datumsleiste bliebe leer.
        """
        antwort = client.get("/api/eintraege/tage", params={"jahr": 2026}, headers=kopf)
        assert antwort.status_code == 200
        assert antwort.json() == []

    def test_uebersicht_zeigt_tage_ohne_inhalt(self, client, kopf):
        client.put("/api/eintraege/2026-09-06", json=_eintrag("ZWlucw=="), headers=kopf)
        client.put("/api/eintraege/2026-09-07", json=_eintrag("enp6enp6enp6eg=="), headers=kopf)

        tage = client.get("/api/eintraege/tage", params={"jahr": 2026}, headers=kopf).json()
        assert [t["datum"] for t in tage] == ["2026-09-06", "2026-09-07"]
        # Laenge ja, Inhalt nein.
        assert tage[1]["zeichen"] > tage[0]["zeichen"]
        assert "chiffrat" not in tage[0]

    def test_uebersicht_trennt_die_jahre(self, client, kopf):
        client.put("/api/eintraege/2025-12-31", json=_eintrag(), headers=kopf)
        client.put("/api/eintraege/2026-01-01", json=_eintrag(), headers=kopf)

        assert len(client.get("/api/eintraege/tage", params={"jahr": 2026}, headers=kopf).json()) == 1


class TestTresorIstPflicht:
    """Ohne Schluessel wird kein Chiffrat angenommen.

    Gemessen am laufenden Dienst (2026-10-16, vor der Behebung): ein PUT ohne
    Tresor antwortete mit **200** und legte einen Eintrag mit
    ``schluessel_version: 1`` an, zu dem kein verpackter Schluessel existiert --
    weder unter der Passphrase noch unter dem Wiederherstellungsschluessel. In
    einer Ende-zu-Ende verschluesselten App ist das endgueltiger Verlust mit
    Erfolgsmeldung: niemand kann den Text je wieder lesen, auch der Betreiber
    nicht, und das ist hier ausdruecklich so gebaut.
    """

    def test_schreiben_ohne_tresor_wird_abgelehnt(self, client, kopf_ohne_tresor):
        antwort = client.put(
            "/api/eintraege/2026-09-06", json=_eintrag(), headers=kopf_ohne_tresor
        )
        assert antwort.status_code == 409
        assert "Tresor" in antwort.json()["detail"]

    def test_und_es_entsteht_nichts(self, client, kopf_ohne_tresor):
        """Die eigentliche Zusicherung: nicht die Antwort, sondern der Bestand."""
        client.put("/api/eintraege/2026-09-06", json=_eintrag(), headers=kopf_ohne_tresor)
        tage = client.get(
            "/api/eintraege/tage", params={"jahr": 2026}, headers=kopf_ohne_tresor
        )
        assert tage.json() == []
        # Und die Loeschvorschau sieht denselben leeren Bestand.
        bestand = client.get("/api/konto/bestand", headers=kopf_ohne_tresor).json()
        assert bestand["summe"] == 0, bestand

    def test_nach_dem_einrichten_geht_es(self, client, kopf_ohne_tresor, tresor_daten):
        """Positivkontrolle: der Riegel sperrt nicht dauerhaft aus."""
        assert client.put(
            "/api/tresor", json=tresor_daten, headers=kopf_ohne_tresor
        ).status_code == 201
        assert client.put(
            "/api/eintraege/2026-09-06", json=_eintrag(), headers=kopf_ohne_tresor
        ).status_code == 200


class TestGrenzen:
    def test_zukunft_wird_abgelehnt(self, client, kopf):
        weit = (date.today() + timedelta(days=30)).isoformat()
        assert client.put(f"/api/eintraege/{weit}", json=_eintrag(), headers=kopf).status_code == 422

    def test_heute_geht_immer(self, client, kopf):
        heute = date.today().isoformat()
        assert client.put(f"/api/eintraege/{heute}", json=_eintrag(), headers=kopf).status_code == 200

    def test_morgen_geht_noch(self, client, kopf):
        """Ein Tag Puffer fuer die Zeitzone: der Wirt rechnet UTC, geschrieben
        wird in Berlin. Ohne ihn waere ein Eintrag um 01:00 Uhr abgelehnt."""
        morgen = (date.today() + timedelta(days=1)).isoformat()
        assert client.put(f"/api/eintraege/{morgen}", json=_eintrag(), headers=kopf).status_code == 200

    def test_zu_grosse_spanne(self, client, kopf):
        antwort = client.get(
            "/api/eintraege", params={"von": "2020-01-01", "bis": "2026-12-31"}, headers=kopf
        )
        assert antwort.status_code == 422

    def test_bis_vor_von(self, client, kopf):
        antwort = client.get(
            "/api/eintraege", params={"von": "2026-09-30", "bis": "2026-09-01"}, headers=kopf
        )
        assert antwort.status_code == 422

    def test_zu_grosses_chiffrat(self, client, kopf):
        zu_viel = "A" * (1024 * 1024 + 10)
        antwort = client.put("/api/eintraege/2026-09-06", json=_eintrag(zu_viel), headers=kopf)
        assert antwort.status_code == 422


def test_unbekannte_felder_werden_nicht_gespeichert(client, kopf):
    """Kein Schleichweg fuer Klartext.

    Der Dienst kennt nur Chiffrat, Einmalwert und Fassung. Wer zusaetzlich einen
    Titel oder Text mitschickt, bekommt ihn nicht abgelegt, und die Antwort
    fuehrt ihn auch nicht. Ohne diesen Test koennte ein spaeteres
    ``model_config = ConfigDict(extra="allow")`` die Zusicherung des ganzen
    Dienstes still aufheben.
    """
    antwort = client.put(
        "/api/eintraege/2026-09-06",
        json={**_eintrag(), "titel": "Verrat", "text": "Klartext"},
        headers=kopf,
    )
    assert antwort.status_code == 200
    assert set(antwort.json()) == {
        "datum",
        "chiffrat",
        "iv",
        "schluessel_version",
        "erstellt_am",
        "geaendert_am",
    }
