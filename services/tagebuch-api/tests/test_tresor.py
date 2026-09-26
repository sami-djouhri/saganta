def test_ohne_tresor_ist_404(client, kopf):
    """404 heisst hier "noch nicht eingerichtet", nicht "kaputt"."""
    assert client.get("/api/tresor", headers=kopf).status_code == 404


def test_einrichten_und_lesen(client, kopf, tresor_daten):
    angelegt = client.put("/api/tresor", json=tresor_daten, headers=kopf)
    assert angelegt.status_code == 201

    gelesen = client.get("/api/tresor", headers=kopf).json()
    for feld, wert in tresor_daten.items():
        assert gelesen[feld] == wert


def test_zweites_einrichten_wird_abgelehnt(client, kopf, tresor_daten):
    """★ Der Test, der Jahre schuetzt.

    Wuerde ein zweites Einrichten den Tresor ersetzen, haenge jeder vorhandene
    Eintrag an einem Datenschluessel, den es danach nirgends mehr gibt. Alles
    waere unlesbar, ohne dass eine einzige Zeile in ``eintraege`` angefasst
    wurde. Deshalb 409 statt Ueberschreiben.
    """
    client.put("/api/tresor", json=tresor_daten, headers=kopf)

    zweiter = dict(tresor_daten, wrap_passphrase="ZWluIGFuZGVyZXIgc2NobHVlc3NlbA==")
    antwort = client.put("/api/tresor", json=zweiter, headers=kopf)
    assert antwort.status_code == 409

    # Und der erste steht unveraendert.
    assert client.get("/api/tresor", headers=kopf).json()["wrap_passphrase"] == (
        tresor_daten["wrap_passphrase"]
    )


class TestPassphraseWechsel:
    def test_wechsel_ersetzt_nur_den_passphrase_zweig(self, client, kopf, tresor_daten):
        client.put("/api/tresor", json=tresor_daten, headers=kopf)

        neu = {
            "kdf": "PBKDF2-SHA256",
            "kdf_iterationen": 400_000,
            "salz_passphrase": "bmV1ZXMtc2Fseg==",
            "wrap_passphrase": "bmV1LXZlcnBhY2t0",
            "wrap_passphrase_iv": "bmV1ZXItaXY=",
        }
        antwort = client.post("/api/tresor/passphrase", json=neu, headers=kopf)
        assert antwort.status_code == 200

        danach = client.get("/api/tresor", headers=kopf).json()
        assert danach["wrap_passphrase"] == "bmV1LXZlcnBhY2t0"
        assert danach["kdf_iterationen"] == 400_000
        # ★ Der ausgedruckte Notfallzettel bleibt gueltig. Genau das ist der
        # Grund, warum der Wechsel eine eigene Route hat und nicht PUT ist.
        assert danach["wrap_wiederherstellung"] == tresor_daten["wrap_wiederherstellung"]
        assert danach["salz_wiederherstellung"] == tresor_daten["salz_wiederherstellung"]

    def test_wechsel_ohne_tresor_ist_404(self, client, kopf):
        neu = {
            "kdf_iterationen": 310_000,
            "salz_passphrase": "eA==",
            "wrap_passphrase": "eA==",
            "wrap_passphrase_iv": "eA==",
        }
        assert client.post("/api/tresor/passphrase", json=neu, headers=kopf).status_code == 404


class TestGrenzen:
    def test_zu_wenige_runden_werden_abgelehnt(self, client, kopf, tresor_daten):
        """Der Server kann die Ableitung nicht nachrechnen, aber Unsinn ablehnen.

        Ein veraenderter Browser koennte die Rundenzahl auf 1 setzen; das
        Chiffrat saehe unveraendert aus, und die Passphrase waere in Minuten
        durchprobiert. Die Untergrenze ist die OWASP-Empfehlung.
        """
        schwach = dict(tresor_daten, kdf_iterationen=1000)
        assert client.put("/api/tresor", json=schwach, headers=kopf).status_code == 422

    def test_fehlender_wiederherstellungszweig_wird_abgelehnt(self, client, kopf, tresor_daten):
        """Ohne zweiten Weg gaebe es keinen Weg zurueck, und niemand merkte es,
        bis die Passphrase weg ist."""
        ohne = {k: v for k, v in tresor_daten.items() if not k.endswith("wiederherstellung")}
        assert client.put("/api/tresor", json=ohne, headers=kopf).status_code == 422


def test_fremder_tresor_ist_unsichtbar(client, kopf, kopf_zwei, tresor_daten):
    client.put("/api/tresor", json=tresor_daten, headers=kopf)
    assert client.get("/api/tresor", headers=kopf_zwei).status_code == 404


def test_ohne_token_kein_tresor(client, tresor_daten):
    assert client.get("/api/tresor").status_code == 401
    assert client.put("/api/tresor", json=tresor_daten).status_code == 401
