"""Anhaenge (inklusive der Frage, was ueberhaupt hochgeladen werden darf)
und die Verknuepfung zu Terminen, Aufgaben, Projekten, Kontakten und Briefen."""

import io

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"x" * 64


def datei(name, inhalt, typ="application/octet-stream"):
    return {"datei": (name, io.BytesIO(inhalt), typ)}


def neue_notiz(client, kopf, **felder):
    return client.post("/api/notizen", json={"titel": "Notiz", **felder}, headers=kopf).json()


# --- Anhaenge ------------------------------------------------------------


def test_bild_und_pdf_gehen_durch(client, kopf):
    notiz = neue_notiz(client, kopf)
    for name, roh, erwartet in (("bild.png", PNG, "image/png"), ("brief.pdf", PDF, "application/pdf")):
        antwort = client.post(
            f"/api/notizen/{notiz['id']}/anhaenge", files=datei(name, roh), headers=kopf
        )
        assert antwort.status_code == 201, antwort.text
        assert antwort.json()["mime"] == erwartet


def test_svg_wird_abgelehnt(client, kopf):
    """SVG sieht aus wie ein Bild, ist aber ein Dokument mit Skriptfaehigkeit."""
    notiz = neue_notiz(client, kopf)
    antwort = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge",
        files=datei("bild.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', "image/svg+xml"),
        headers=kopf,
    )
    # Als Text erkannt (kein Bild-Magic), und Text wird nie als Seite
    # ausgeliefert, sondern als Download.
    assert antwort.status_code == 201
    assert antwort.json()["mime"].startswith("text/")


def test_typ_wird_am_inhalt_gemessen_nicht_am_namen(client, kopf):
    notiz = neue_notiz(client, kopf)
    antwort = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge",
        files=datei("harmlos.png", b"\x00\x01\x02\xff\xfe", "image/png"),
        headers=kopf,
    )
    # Weder gueltiges Bild noch dekodierbarer Text → abgelehnt, trotz .png und
    # trotz passend behauptetem Content-Type.
    assert antwort.status_code == 415


def test_leere_datei_wird_abgelehnt(client, kopf):
    notiz = neue_notiz(client, kopf)
    antwort = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge", files=datei("leer.txt", b""), headers=kopf
    )
    assert antwort.status_code == 400


def test_zu_grosse_datei_wird_abgelehnt_und_hinterlaesst_nichts(client, kopf, monkeypatch):
    from pathlib import Path

    from app import ablage
    from app.config import settings

    monkeypatch.setattr(settings, "anhang_max_bytes", 1024)
    notiz = neue_notiz(client, kopf)
    antwort = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge",
        files=datei("gross.png", PNG + b"y" * 4096),
        headers=kopf,
    )
    assert antwort.status_code == 413
    # Die halb geschriebene Datei muss weg sein, sonst waechst die Ablage bei
    # jedem abgelehnten Versuch weiter.
    assert list(Path(ablage.verzeichnis()).glob("*")) == []


def test_anhang_kommt_als_download_nicht_als_seite(client, kopf):
    notiz = neue_notiz(client, kopf)
    anhang = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge", files=datei("bild.png", PNG), headers=kopf
    ).json()
    antwort = client.get(f"/api/notizen/{notiz['id']}/anhaenge/{anhang['id']}", headers=kopf)
    assert antwort.status_code == 200
    assert antwort.headers["content-disposition"].startswith("attachment")
    assert antwort.headers["x-content-type-options"] == "nosniff"


def test_fremder_anhang_bleibt_verschlossen(client, kopf, kopf_zwei):
    notiz = neue_notiz(client, kopf)
    anhang = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge", files=datei("bild.png", PNG), headers=kopf
    ).json()
    assert (
        client.get(
            f"/api/notizen/{notiz['id']}/anhaenge/{anhang['id']}", headers=kopf_zwei
        ).status_code
        == 404
    )


def test_anhang_loeschen_raeumt_die_ablage(client, kopf):
    from pathlib import Path

    from app import ablage

    notiz = neue_notiz(client, kopf)
    anhang = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge", files=datei("bild.png", PNG), headers=kopf
    ).json()
    assert len(list(Path(ablage.verzeichnis()).glob("*"))) == 1
    client.delete(f"/api/notizen/{notiz['id']}/anhaenge/{anhang['id']}", headers=kopf)
    assert list(Path(ablage.verzeichnis()).glob("*")) == []


def test_notiz_loeschen_raeumt_die_anhaenge_mit(client, kopf):
    from pathlib import Path

    from app import ablage

    notiz = neue_notiz(client, kopf)
    client.post(f"/api/notizen/{notiz['id']}/anhaenge", files=datei("a.png", PNG), headers=kopf)
    client.post(f"/api/notizen/{notiz['id']}/anhaenge", files=datei("b.pdf", PDF), headers=kopf)
    client.delete(f"/api/notizen/{notiz['id']}", headers=kopf)
    assert list(Path(ablage.verzeichnis()).glob("*")) == []


# --- Anhaenge am oeffentlichen Link -------------------------------------


def test_geteilter_anhang_braucht_den_schein(client, kopf):
    notiz = neue_notiz(client, kopf)
    anhang = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge", files=datei("bild.png", PNG), headers=kopf
    ).json()
    f = client.post(f"/api/freigaben/notizen/{notiz['id']}", json={}, headers=kopf).json()

    # Ohne Oeffnen kein Zugriff, sonst waere der Anhang die Hintertuer, die
    # weder Zaehler noch Passwort noch Ablauf kennt.
    ohne = client.get(f"/oeffentlich/{f['merkmal']}/anhang/{anhang['id']}")
    assert ohne.status_code == 401

    geoeffnet = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").json()
    assert geoeffnet["anhang_schein"]
    mit = client.get(
        f"/oeffentlich/{f['merkmal']}/anhang/{anhang['id']}",
        params={"schein": geoeffnet["anhang_schein"]},
    )
    assert mit.status_code == 200
    assert mit.content == PNG


def test_schein_gilt_nicht_fuer_eine_andere_freigabe(client, kopf):
    notiz_a = neue_notiz(client, kopf, titel="A")
    notiz_b = neue_notiz(client, kopf, titel="B")
    anhang_b = client.post(
        f"/api/notizen/{notiz_b['id']}/anhaenge", files=datei("b.png", PNG), headers=kopf
    ).json()
    client.post(f"/api/notizen/{notiz_a['id']}/anhaenge", files=datei("a.png", PNG), headers=kopf)

    f_a = client.post(f"/api/freigaben/notizen/{notiz_a['id']}", json={}, headers=kopf).json()
    f_b = client.post(f"/api/freigaben/notizen/{notiz_b['id']}", json={}, headers=kopf).json()
    schein_a = client.post(f"/oeffentlich/{f_a['merkmal']}/oeffnen").json()["anhang_schein"]

    quer = client.get(
        f"/oeffentlich/{f_b['merkmal']}/anhang/{anhang_b['id']}", params={"schein": schein_a}
    )
    assert quer.status_code == 401


def test_freigabe_ohne_anhaenge_gibt_keine_dateien_heraus(client, kopf):
    notiz = neue_notiz(client, kopf)
    anhang = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge", files=datei("bild.png", PNG), headers=kopf
    ).json()
    f = client.post(
        f"/api/freigaben/notizen/{notiz['id']}", json={"mit_anhaengen": False}, headers=kopf
    ).json()
    geoeffnet = client.post(f"/oeffentlich/{f['merkmal']}/oeffnen").json()
    assert geoeffnet["anhaenge"] == []
    assert geoeffnet["anhang_schein"] is None
    assert client.get(f"/oeffentlich/{f['merkmal']}/anhang/{anhang['id']}").status_code == 404


def test_verschluesselte_freigabe_nimmt_keine_anhaenge_mit(client, kopf):
    """Sie laegen unverschluesselt in der Ablage, das waere ein Loch in genau
    der Zusicherung, fuer die man diesen Modus waehlt."""
    import base64

    notiz = neue_notiz(client, kopf)
    client.post(f"/api/notizen/{notiz['id']}/anhaenge", files=datei("bild.png", PNG), headers=kopf)
    f = client.post(
        f"/api/freigaben/notizen/{notiz['id']}",
        json={
            "modus": "chiffriert",
            "chiffrat": base64.b64encode(b"geheim").decode(),
            "iv": base64.b64encode(b"123456789012").decode(),
            "schluessel_quelle": "fragment",
            "mit_anhaengen": True,
        },
        headers=kopf,
    ).json()
    assert f["mit_anhaengen"] is False


# --- Verknuepfungen ------------------------------------------------------


def test_verknuepfen_und_rueckwaerts_finden(client, kopf):
    notiz = neue_notiz(client, kopf, titel="Vorbereitung Elterngespraech")
    v = client.post(
        f"/api/notizen/{notiz['id']}/verknuepfungen",
        json={"typ": "termin", "ref": "5f3c-abc", "label": "Elterngespraech Di 14:00"},
        headers=kopf,
    )
    assert v.status_code == 201, v.text

    # Der Weg, auf dem der Kalender „welche Notizen haengen an diesem Termin?"
    # beantwortet bekommt.
    treffer = client.get(
        "/api/notizen", params={"verknuepft": "termin:5f3c-abc"}, headers=kopf
    ).json()
    assert [t["titel"] for t in treffer] == ["Vorbereitung Elterngespraech"]


def test_alle_vier_quellen_sind_verknuepfbar(client, kopf):
    notiz = neue_notiz(client, kopf)
    for typ, ref in (
        ("termin", "t1"),
        ("aufgabe", "a1"),
        ("ziel", "z1"),
        ("projekt", "saganta"),
        ("kontakt", "k1"),
        ("brief", "b1"),
    ):
        antwort = client.post(
            f"/api/notizen/{notiz['id']}/verknuepfungen",
            json={"typ": typ, "ref": ref, "label": typ},
            headers=kopf,
        )
        assert antwort.status_code == 201, f"{typ}: {antwort.text}"
    assert len(client.get(f"/api/notizen/{notiz['id']}", headers=kopf).json()["verknuepfungen"]) == 6


def test_unbekannter_typ_wird_abgelehnt(client, kopf):
    notiz = neue_notiz(client, kopf)
    antwort = client.post(
        f"/api/notizen/{notiz['id']}/verknuepfungen",
        json={"typ": "raumschiff", "ref": "x"},
        headers=kopf,
    )
    assert antwort.status_code == 422


def test_doppelt_verknuepfen_bleibt_eine_verknuepfung(client, kopf):
    notiz = neue_notiz(client, kopf)
    wunsch = {"typ": "termin", "ref": "gleich", "label": "X"}
    erste = client.post(f"/api/notizen/{notiz['id']}/verknuepfungen", json=wunsch, headers=kopf)
    zweite = client.post(f"/api/notizen/{notiz['id']}/verknuepfungen", json=wunsch, headers=kopf)
    assert zweite.status_code == 201
    assert erste.json()["id"] == zweite.json()["id"]


def test_rueckwaertssuche_bleibt_mandantenrein(client, kopf, kopf_zwei):
    notiz = neue_notiz(client, kopf)
    client.post(
        f"/api/notizen/{notiz['id']}/verknuepfungen",
        json={"typ": "termin", "ref": "geteilt"},
        headers=kopf,
    )
    assert (
        client.get("/api/notizen", params={"verknuepft": "termin:geteilt"}, headers=kopf_zwei).json()
        == []
    )


def test_verknuepfung_loesen(client, kopf):
    notiz = neue_notiz(client, kopf)
    v = client.post(
        f"/api/notizen/{notiz['id']}/verknuepfungen",
        json={"typ": "projekt", "ref": "saganta"},
        headers=kopf,
    ).json()
    assert (
        client.delete(
            f"/api/notizen/{notiz['id']}/verknuepfungen/{v['id']}", headers=kopf
        ).status_code
        == 204
    )
    assert client.get(f"/api/notizen/{notiz['id']}", headers=kopf).json()["verknuepfungen"] == []


# --- Sammel-Rueckwaertssuche ---------------------------------------------
#
# Die Route, ohne die eine Aufgabenliste je Zeile eine eigene Anfrage stellen
# muesste. Sie ist 2026-09-13 fuer die Aufgaben-App entstanden.


def _verknuepfen(client, kopf, notiz_id, typ, ref, label=""):
    antwort = client.post(
        f"/api/notizen/{notiz_id}/verknuepfungen",
        json={"typ": typ, "ref": ref, "label": label or ref},
        headers=kopf,
    )
    assert antwort.status_code == 201, antwort.text


def test_sammelsuche_ordnet_jeder_kennung_ihre_notizen_zu(client, kopf):
    eine = neue_notiz(client, kopf, titel="Angebot einholen")
    zwei = neue_notiz(client, kopf, titel="Rueckfragen notiert")
    drei = neue_notiz(client, kopf, titel="Gehoert woanders hin")
    _verknuepfen(client, kopf, eine["id"], "aufgabe", "a-1")
    _verknuepfen(client, kopf, zwei["id"], "aufgabe", "a-1")
    _verknuepfen(client, kopf, drei["id"], "aufgabe", "a-2")

    treffer = client.get(
        "/api/notizen/verknuepft", params={"typ": "aufgabe", "refs": "a-1,a-2"}, headers=kopf
    ).json()
    assert sorted(t["titel"] for t in treffer["a-1"]) == ["Angebot einholen", "Rueckfragen notiert"]
    assert [t["titel"] for t in treffer["a-2"]] == ["Gehoert woanders hin"]


def test_sammelsuche_laesst_kennungen_ohne_notiz_weg(client, kopf):
    # Ein fehlender Schluessel heisst „keine Notiz". Eine leere Liste koennte
    # auch ein verschluckter Fehler sein, deshalb gibt es sie hier nicht.
    notiz = neue_notiz(client, kopf)
    _verknuepfen(client, kopf, notiz["id"], "aufgabe", "a-1")
    treffer = client.get(
        "/api/notizen/verknuepft", params={"typ": "aufgabe", "refs": "a-1,a-ohne"}, headers=kopf
    ).json()
    assert set(treffer) == {"a-1"}


def test_sammelsuche_zeigt_keine_fremden_notizen(client, kopf, kopf_zweiter=None):
    notiz = neue_notiz(client, kopf)
    _verknuepfen(client, kopf, notiz["id"], "aufgabe", "a-1")
    from tests.conftest import token_fuer

    fremd = {"Authorization": f"Bearer {token_fuer('jemand-anderes')}"}
    treffer = client.get(
        "/api/notizen/verknuepft", params={"typ": "aufgabe", "refs": "a-1"}, headers=fremd
    ).json()
    assert treffer == {}


def test_sammelsuche_weist_unbekannten_typ_ab(client, kopf):
    antwort = client.get(
        "/api/notizen/verknuepft", params={"typ": "quatsch", "refs": "a-1"}, headers=kopf
    )
    assert antwort.status_code == 400


def test_sammelsuche_deckelt_die_anzahl(client, kopf):
    zuviele = ",".join(f"a-{i}" for i in range(201))
    antwort = client.get(
        "/api/notizen/verknuepft", params={"typ": "aufgabe", "refs": zuviele}, headers=kopf
    )
    assert antwort.status_code == 400


def test_sammelsuche_ohne_kennungen_ist_leer(client, kopf):
    antwort = client.get(
        "/api/notizen/verknuepft", params={"typ": "aufgabe", "refs": " , "}, headers=kopf
    )
    assert antwort.status_code == 200
    assert antwort.json() == {}


def test_verknuepft_route_wird_nicht_als_notiz_id_gelesen(client, kopf):
    # ⚠️ Die Reihenfolge der Routen entscheidet: stuende `/verknuepft` hinter
    # `/{notiz_id}`, landete der Aufruf dort und scheiterte an der Typpruefung.
    antwort = client.get(
        "/api/notizen/verknuepft", params={"typ": "aufgabe", "refs": "x"}, headers=kopf
    )
    assert antwort.status_code == 200, antwort.text
