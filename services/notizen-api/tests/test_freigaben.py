"""Der geteilte Link, der Teil, bei dem Fehler nach draussen wirken."""

import base64

import pytest


@pytest.fixture
def notiz(client, kopf):
    return client.post(
        "/api/notizen",
        json={"titel": "Zugangsdaten", "inhalt": "Nutzer: anna\nPasswort: hunter2"},
        headers=kopf,
    ).json()


def freigeben(client, kopf, notiz_id, **wunsch):
    antwort = client.post(f"/api/freigaben/notizen/{notiz_id}", json=wunsch, headers=kopf)
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


def test_offene_freigabe_zeigt_erst_nach_ausdruecklichem_oeffnen(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"])

    # Der Blick auf den Link verraet nichts vom Inhalt, das ist der Schutz
    # gegen Messenger-Vorschauen, die jeden Link automatisch abrufen.
    zustand = client.get(f"/oeffentlich/{f['merkmal']}").json()
    assert zustand["zustand"] == "aktiv"
    assert "hunter2" not in str(zustand)
    assert "Zugangsdaten" not in str(zustand)

    inhalt = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").json()
    assert inhalt["titel"] == "Zugangsdaten"
    assert "hunter2" in inhalt["inhalt"]


def test_ansehen_verbraucht_den_einmal_link_nicht(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"], max_abrufe=1)
    for _ in range(3):
        assert client.get(f"/oeffentlich/{f['merkmal']}").json()["zustand"] == "aktiv"
    assert client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").status_code == 200


def test_einmal_lesen_ist_beim_zweiten_mal_vorbei(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"], max_abrufe=1)
    assert client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").status_code == 200
    zweiter = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen")
    assert zweiter.status_code == 410
    assert client.get(f"/oeffentlich/{f['merkmal']}").json()["zustand"] == "verbraucht"


def test_abgelaufener_link_gibt_nichts_mehr_her(client, kopf, notiz):
    from datetime import timedelta

    from app.db import SessionLocal
    from app.models import Freigabe
    from app.util import jetzt

    f = freigeben(client, kopf, notiz["id"], ablauf_tage=1)
    with SessionLocal() as s:
        zeile = s.query(Freigabe).filter_by(merkmal=f["merkmal"]).one()
        zeile.ablauf_am = jetzt() - timedelta(minutes=1)
        s.commit()

    assert client.get(f"/oeffentlich/{f['merkmal']}").json()["zustand"] == "abgelaufen"
    assert client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").status_code == 410


def test_widerruf_zieht_den_link_zurueck(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"])
    assert client.delete(f"/api/freigaben/{f['id']}", headers=kopf).status_code == 204
    antwort = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen")
    assert antwort.status_code == 410
    # Der Unterschied zu „gibt es nicht" ist die eigentliche Auskunft.
    assert "zurueckgezogen" in antwort.json()["detail"]


def test_fremde_freigabe_kann_nicht_widerrufen_werden(client, kopf, kopf_zwei, notiz):
    f = freigeben(client, kopf, notiz["id"])
    assert client.delete(f"/api/freigaben/{f['id']}", headers=kopf_zwei).status_code == 404


def test_unbekanntes_merkmal_ist_schlicht_nicht_da(client):
    assert client.get("/oeffentlich/gibtesnicht").status_code == 404
    assert client.post("/oeffentlich/gibtesnicht/oeffnen").status_code == 404


def test_passwort_schuetzt_die_offene_freigabe(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"], passwort="Sonnenblume42")
    assert client.get(f"/oeffentlich/{f['merkmal']}").json()["braucht_passwort"] is True

    assert client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").status_code == 401
    falsch = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen", json={"passwort": "falsch"})
    assert falsch.status_code == 401

    richtig = client.post(
        f"/oeffentlich/{f['merkmal']}/oeffnen", json={"passwort": "Sonnenblume42"}
    )
    assert richtig.status_code == 200
    assert "hunter2" in richtig.json()["inhalt"]


def test_fehlversuche_sperren_die_freigabe(client, kopf, notiz):
    from app.config import settings

    f = freigeben(client, kopf, notiz["id"], passwort="Sonnenblume42")
    for _ in range(settings.freigabe_max_fehlversuche):
        client.post(f"/oeffentlich/{f['merkmal']}/oeffnen", json={"passwort": "nein"})
    # Ab jetzt hilft auch das richtige Passwort nicht mehr: Durchprobieren
    # soll sich nicht lohnen.
    danach = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen", json={"passwort": "Sonnenblume42"})
    assert danach.status_code == 410
    assert client.get(f"/oeffentlich/{f['merkmal']}").json()["zustand"] == "gesperrt"


def test_fehlversuch_verbraucht_keinen_abruf(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"], passwort="Sonnenblume42", max_abrufe=1)
    client.post(f"/oeffentlich/{f['merkmal']}/oeffnen", json={"passwort": "nein"})
    richtig = client.post(
        f"/oeffentlich/{f['merkmal']}/oeffnen", json={"passwort": "Sonnenblume42"}
    )
    assert richtig.status_code == 200


def test_offene_freigabe_folgt_der_notiz(client, kopf, notiz):
    """Modus 'offen' ist ein Fenster, kein Abzug."""
    f = freigeben(client, kopf, notiz["id"])
    client.patch(f"/api/notizen/{notiz['id']}", json={"inhalt": "neuer Stand"}, headers=kopf)
    assert client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").json()["inhalt"] == "neuer Stand"


def test_geloeschte_notiz_laesst_die_offene_freigabe_ins_leere_laufen(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"])
    client.delete(f"/api/notizen/{notiz['id']}", headers=kopf)
    assert client.get(f"/oeffentlich/{f['merkmal']}").json()["zustand"] == "quelle_weg"
    assert client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").status_code == 410


# --- Verschluesselte Freigaben ------------------------------------------


def chiffrat_wunsch(**zusatz):
    grund = {
        "modus": "chiffriert",
        "chiffrat": base64.b64encode(b"nicht-lesbar-fuer-den-server").decode(),
        "iv": base64.b64encode(b"123456789012").decode(),
        "algo": "AES-GCM-256",
        "schluessel_quelle": "fragment",
    }
    grund.update(zusatz)
    return grund


def test_verschluesselte_freigabe_reicht_das_chiffrat_durch(client, kopf, notiz):
    f = freigeben(client, kopf, notiz["id"], **chiffrat_wunsch())
    geoeffnet = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").json()
    assert geoeffnet["modus"] == "chiffriert"
    assert geoeffnet["chiffrat"] == chiffrat_wunsch()["chiffrat"]
    # Klartext taucht auf diesem Weg nirgends auf, auch nicht der Titel.
    assert geoeffnet["inhalt"] is None
    assert geoeffnet["titel"] == ""


def test_verschluesselte_freigabe_ist_ein_schnappschuss(client, kopf, notiz):
    """Der Server kann nicht nachziehen, was er nicht lesen kann."""
    f = freigeben(client, kopf, notiz["id"], **chiffrat_wunsch())
    client.patch(f"/api/notizen/{notiz['id']}", json={"inhalt": "geaendert"}, headers=kopf)
    assert client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").json()["chiffrat"] == (
        chiffrat_wunsch()["chiffrat"]
    )


def test_verbrauchtes_chiffrat_wird_geloescht(client, kopf, notiz):
    from app.db import SessionLocal
    from app.models import Freigabe

    f = freigeben(client, kopf, notiz["id"], max_abrufe=1, **chiffrat_wunsch())
    client.post(f"/oeffentlich/{f['merkmal']}/oeffnen")
    with SessionLocal() as s:
        zeile = s.query(Freigabe).filter_by(merkmal=f["merkmal"]).one()
        # „Verbraucht" heisst weg, nicht nur vermerkt: wer spaeter die Datenbank
        # liest, findet den Inhalt nicht mehr.
        assert zeile.chiffrat is None


def test_widerruf_loescht_das_chiffrat_ebenfalls(client, kopf, notiz):
    from app.db import SessionLocal
    from app.models import Freigabe

    f = freigeben(client, kopf, notiz["id"], **chiffrat_wunsch())
    client.delete(f"/api/freigaben/{f['id']}", headers=kopf)
    with SessionLocal() as s:
        assert s.query(Freigabe).filter_by(merkmal=f["merkmal"]).one().chiffrat is None


def test_unvollstaendige_verschluesselte_freigabe_wird_abgelehnt(client, kopf, notiz):
    """Ohne iv koennte niemand mehr aufschliessen, das faellt sonst erst beim
    Empfaenger auf, und dann ist der Link schon verschickt."""
    ohne_iv = chiffrat_wunsch()
    ohne_iv.pop("iv")
    assert (
        client.post(
            f"/api/freigaben/notizen/{notiz['id']}", json=ohne_iv, headers=kopf
        ).status_code
        == 400
    )


def test_passwort_darf_bei_verschluesselung_nicht_zum_server(client, kopf, notiz):
    """Sonst laege genau das Geheimnis am Server, aus dem der Schluessel entsteht."""
    antwort = client.post(
        f"/api/freigaben/notizen/{notiz['id']}",
        json=chiffrat_wunsch(passwort="Sonnenblume42"),
        headers=kopf,
    )
    assert antwort.status_code == 400
    assert "Browser" in antwort.json()["detail"]


def test_passwort_ableitung_braucht_salz_und_runden(client, kopf, notiz):
    antwort = client.post(
        f"/api/freigaben/notizen/{notiz['id']}",
        json=chiffrat_wunsch(schluessel_quelle="passwort"),
        headers=kopf,
    )
    assert antwort.status_code == 400


def test_kdf_angaben_erreichen_den_empfaenger(client, kopf, notiz):
    """Der Browser des Empfaengers braucht Salz und Rundenzahl, um denselben
    Schluessel abzuleiten, die duerfen ruhig oeffentlich sein."""
    f = freigeben(
        client,
        kopf,
        notiz["id"],
        **chiffrat_wunsch(
            schluessel_quelle="passwort",
            kdf_salz=base64.b64encode(b"salzsalzsalzsalz").decode(),
            kdf_iterationen=310000,
        ),
    )
    zustand = client.get(f"/oeffentlich/{f['merkmal']}").json()
    assert zustand["braucht_passwort"] is True
    assert zustand["kdf_iterationen"] == 310000
    assert zustand["kdf_salz"]


def test_freigabeliste_zeigt_was_draussen_ist(client, kopf, notiz):
    freigeben(client, kopf, notiz["id"])
    zweite = freigeben(client, kopf, notiz["id"], max_abrufe=1)
    client.delete(f"/api/freigaben/{zweite['id']}", headers=kopf)

    alle = client.get("/api/freigaben", headers=kopf).json()
    assert len(alle) == 2
    aktive = client.get("/api/freigaben", params={"nur_aktive": True}, headers=kopf).json()
    assert len(aktive) == 1


def test_freigabeliste_ist_mandantenrein(client, kopf, kopf_zwei, notiz):
    freigeben(client, kopf, notiz["id"])
    assert client.get("/api/freigaben", headers=kopf_zwei).json() == []


def test_fremde_notiz_kann_nicht_freigegeben_werden(client, kopf_zwei, notiz):
    assert (
        client.post(
            f"/api/freigaben/notizen/{notiz['id']}", json={}, headers=kopf_zwei
        ).status_code
        == 404
    )
