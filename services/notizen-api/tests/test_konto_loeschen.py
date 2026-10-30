"""Auskunft und Loeschung des eigenen Bestands.

Zwei Dinge werden hier geprueft, und sie haben verschiedene Lebensdauern:

* **Der Abdeckungs-Riegel** gilt fuer alle kuenftigen Tabellen dieses Dienstes.
  Er ist der Grund, warum dieser Test auch dann wertvoll ist, wenn niemand den
  Loeschweg anfasst: wer eine Tabelle mit ``owner_sub`` hinzufuegt und den Plan
  vergisst, bekommt hier rot.
* **Der Durchstich** prueft den heutigen Weg einmal von aussen, ueber HTTP, mit
  Anhang, Freigabe und Volltextindex, samt Gegenprobe auf einen zweiten Nutzer.
"""

import io

from saganta_dienst import loeschen
from sqlalchemy import text

from app.db import Base, engine
from app.konto import PLAN

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_der_loeschplan_deckt_alle_tabellen_ab():
    """Der Riegel. Schlaegt an, sobald eine Tabelle aus dem Loeschweg faellt.

    Er braucht keine Daten: der Befund soll vor den Daten da sein. Wird er rot,
    ist die Antwort nicht "Test anpassen", sondern ein Schritt in ``konto.py``
    oder ein ausdrueckliches ``gemeinsam``.
    """
    assert loeschen.abdeckung_pruefen(PLAN, Base.metadata) == []


def test_bestand_zeigt_an_ohne_zu_loeschen(client, kopf):
    client.post("/api/notizen", json={"titel": "bleibt"}, headers=kopf)

    antwort = client.get("/api/konto/bestand", headers=kopf)
    assert antwort.status_code == 200, antwort.text
    bericht = antwort.json()
    assert bericht["trockenlauf"] is True
    assert bericht["zeilen"]["notizen"] == 1
    assert bericht["luecken"] == []

    # Und sie ist wirklich noch da.
    assert len(client.get("/api/notizen", headers=kopf).json()) == 1


def test_ohne_bestaetigung_wird_nicht_geloescht(client, kopf):
    client.post("/api/notizen", json={"titel": "bleibt"}, headers=kopf)

    assert client.post("/api/konto/loeschen", json={}, headers=kopf).status_code == 400
    assert client.post(
        "/api/konto/loeschen", json={"confirm": "ja"}, headers=kopf
    ).status_code == 400
    assert len(client.get("/api/notizen", headers=kopf).json()) == 1


def test_durchstich_alles_faellt(client, kopf):
    notiz = client.post(
        "/api/notizen", json={"titel": "Geheimwort", "inhalt": "Kennsatz"}, headers=kopf
    ).json()
    buch = client.post("/api/notizbuecher", json={"name": "Buch"}, headers=kopf)
    assert buch.status_code == 201, buch.text
    anhang = client.post(
        f"/api/notizen/{notiz['id']}/anhaenge",
        files={"datei": ("bild.png", io.BytesIO(PNG), "image/png")},
        headers=kopf,
    )
    assert anhang.status_code == 201, anhang.text

    antwort = client.post(
        "/api/konto/loeschen", json={"confirm": "KONTO LOESCHEN"}, headers=kopf
    )
    assert antwort.status_code == 200, antwort.text
    bericht = antwort.json()
    assert bericht["sauber"] is True, bericht
    assert bericht["zeilen"]["notizen"] == 1
    assert bericht["zeilen"]["anhaenge"] == 1
    assert bericht["zeilen"]["notizbuecher"] == 1
    assert bericht["reste"] == {}

    assert client.get("/api/notizen", headers=kopf).json() == []
    assert client.get("/api/notizbuecher", headers=kopf).json() == []


def test_der_volltextindex_behaelt_den_klartext_nicht(client, kopf):
    """Die Stelle, die ein Loeschweg am leichtesten uebersieht.

    Eine external-content-FTS5 haelt Titel, Inhalt und Tags im Klartext in einer
    eigenen Tabelle. Loescht man nur die Zeile, bleibt der Text im Index stehen,
    und die Suche findet ihn weiter. Hier haengt er am Trigger ``notizen_fts_del``.
    """
    client.post(
        "/api/notizen",
        json={"titel": "Unverwechselbarwort", "inhalt": "Vertraulicher Satz"},
        headers=kopf,
    )
    with engine.connect() as conn:
        vorher = conn.execute(
            text("SELECT count(*) FROM notizen_fts WHERE notizen_fts MATCH 'Unverwechselbarwort'")
        ).scalar()
    assert vorher == 1, "Vorbedingung: der Index kennt das Wort"

    client.post("/api/konto/loeschen", json={"confirm": "KONTO LOESCHEN"}, headers=kopf)

    with engine.connect() as conn:
        nachher = conn.execute(
            text("SELECT count(*) FROM notizen_fts WHERE notizen_fts MATCH 'Unverwechselbarwort'")
        ).scalar()
    assert nachher == 0, "Der Klartext steht noch im Volltextindex"


def test_die_anhangdatei_verschwindet_von_der_platte(client, kopf):
    """Die Metadatenzeile zu loeschen und die Datei liegenzulassen waere Augenwischerei."""
    from pathlib import Path

    from app.config import settings

    notiz = client.post("/api/notizen", json={"titel": "mit Anhang"}, headers=kopf).json()
    client.post(
        f"/api/notizen/{notiz['id']}/anhaenge",
        files={"datei": ("bild.png", io.BytesIO(PNG), "image/png")},
        headers=kopf,
    )
    dateien = list(Path(settings.anhang_verzeichnis).glob("*"))
    assert len(dateien) == 1, "Vorbedingung: die Datei liegt in der Ablage"

    antwort = client.post(
        "/api/konto/loeschen", json={"confirm": "KONTO LOESCHEN"}, headers=kopf
    )
    assert antwort.status_code == 200, antwort.text
    assert list(Path(settings.anhang_verzeichnis).glob("*")) == []


def test_gegenprobe_der_zweite_nutzer_behaelt_alles(client, kopf, kopf_zwei):
    """Die Haelfte des Beweises, die man leicht weglaesst.

    Ohne sie waere ein Loeschweg, der schlicht alle Tabellen leert, ebenfalls
    gruen.
    """
    client.post("/api/notizen", json={"titel": "meins"}, headers=kopf)
    client.post("/api/notizbuecher", json={"name": "mein Buch"}, headers=kopf)
    notiz_zwei = client.post("/api/notizen", json={"titel": "fremd"}, headers=kopf_zwei).json()
    client.post(
        f"/api/notizen/{notiz_zwei['id']}/anhaenge",
        files={"datei": ("bild.png", io.BytesIO(PNG), "image/png")},
        headers=kopf_zwei,
    )
    client.post("/api/notizbuecher", json={"name": "fremdes Buch"}, headers=kopf_zwei)

    client.post("/api/konto/loeschen", json={"confirm": "KONTO LOESCHEN"}, headers=kopf)

    assert len(client.get("/api/notizen", headers=kopf_zwei).json()) == 1
    assert len(client.get("/api/notizbuecher", headers=kopf_zwei).json()) == 1
    from pathlib import Path

    from app.config import settings

    assert len(list(Path(settings.anhang_verzeichnis).glob("*"))) == 1


def test_ohne_token_geht_nichts(client):
    assert client.get("/api/konto/bestand").status_code == 401
    assert client.post(
        "/api/konto/loeschen", json={"confirm": "KONTO LOESCHEN"}
    ).status_code == 401
