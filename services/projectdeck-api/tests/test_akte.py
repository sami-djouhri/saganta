"""Gliederung, Kontakte und Projektakte (2026-11-15, Entscheide U1 bis U8, P1 bis P4)."""

import unittest

from app import nachbarn

from tests.test_api import client

KONTAKTE = {"k-1": {"id": "k-1", "name": "Erika Muster", "telefon": "0000", "email": "erika@example.invalid"}}
TERMINE: list[dict] = []
BUDGETS: dict = {}


def _kontakt(me, kid):
    return KONTAKTE.get(kid, False)


def _termine(me, slugs, von, bis):
    return [t for t in TERMINE if t["projekt"] in slugs]


nachbarn.kontakt = _kontakt
nachbarn.termine = _termine
nachbarn.notizen_zu = lambda me, typ, refs: {}
nachbarn.kontakte_suche = lambda me, suche: [{"id": k, "name": v["name"], "gruppe": None} for k, v in KONTAKTE.items()]
nachbarn.budgets = lambda me: {s: b for s, b in BUDGETS.items()}
nachbarn.budget_stand = lambda me, slug: {"letzte": []}


def _neu(name, **mehr):
    r = client.post("/api/projects", json={"name": name, **mehr})
    assert r.status_code == 201, r.text
    return r.json()


class TestGliederung(unittest.TestCase):
    def test_unterprojekt_mit_zwei_eltern(self):
        bots = _neu("Akte Bots")
        gartiko = _neu("Akte Gartiko")
        bot = _neu("Akte Gartiko Bot", eltern_ids=[bots["id"], gartiko["id"]])
        self.assertEqual(bot["eltern_ids"], sorted([bots["id"], gartiko["id"]]))
        self.assertIn(bot["id"], client.get(f"/api/projects/{bots['id']}").json()["kinder_ids"])
        self.assertIn(bot["id"], client.get(f"/api/projects/{gartiko['id']}").json()["kinder_ids"])
        liste = {p["id"]: p for p in client.get("/api/projects").json()}
        self.assertEqual(liste[bot["id"]]["eltern_ids"], sorted([bots["id"], gartiko["id"]]))

    def test_kein_kreis_und_nicht_unter_sich_selbst(self):
        oben = _neu("Akte Oben")
        mitte = _neu("Akte Mitte", eltern_ids=[oben["id"]])
        unten = _neu("Akte Unten", eltern_ids=[mitte["id"]])
        r = client.put(f"/api/projects/{oben['id']}/eltern", json={"eltern_ids": [unten["id"]]})
        self.assertEqual(r.status_code, 422)
        r = client.put(f"/api/projects/{oben['id']}/eltern", json={"eltern_ids": [oben["id"]]})
        self.assertEqual(r.status_code, 422)
        r = client.put(f"/api/projects/{unten['id']}/eltern", json={"eltern_ids": []})
        self.assertEqual(r.json()["eltern_ids"], [])

    def test_teilbaum_slugs(self):
        oben = _neu("Akte Gaming")
        dash = _neu("Akte Dashboard", eltern_ids=[oben["id"]])
        _neu("Akte Dashboard Web", eltern_ids=[dash["id"]])
        r = client.get(f"/api/projects/by-slug/{oben['slug']}/teilbaum").json()
        self.assertEqual(r["slugs"], [oben["slug"], dash["slug"], "akte-dashboard-web"])


class TestKontakte(unittest.TestCase):
    def test_anheften_rolle_rueckverweis_loesen(self):
        p = _neu("Akte Kunde")
        r = client.post(f"/api/projects/{p['id']}/kontakte", json={"kontakt_id": "k-1", "rolle": "Kundin"})
        self.assertEqual(r.status_code, 201, r.text)
        v = r.json()
        self.assertEqual((v["name"], v["rolle"]), ("Erika Muster", "Kundin"))
        self.assertEqual(client.post(f"/api/projects/{p['id']}/kontakte", json={"kontakt_id": "k-1"}).status_code, 409)
        self.assertEqual(client.post(f"/api/projects/{p['id']}/kontakte", json={"kontakt_id": "gibtsnicht"}).status_code, 404)
        rueck = client.get("/api/kontakte/k-1/projekte").json()
        self.assertIn(p["slug"], [x["slug"] for x in rueck])
        client.patch(f"/api/projects/{p['id']}/kontakte/{v['verweis_id']}", json={"rolle": "Lieferantin"})
        self.assertEqual(client.get(f"/api/projects/{p['id']}/kontakte").json()[0]["rolle"], "Lieferantin")
        self.assertEqual(client.delete(f"/api/projects/{p['id']}/kontakte/{v['verweis_id']}").status_code, 204)
        self.assertEqual(client.get(f"/api/projects/{p['id']}/kontakte").json(), [])
        self.assertEqual(client.get("/api/kontakte-auswahl").json()[0]["name"], "Erika Muster")


class TestAkte(unittest.TestCase):
    def test_oberprojekt_sammelt_alles_darunter(self):
        medien = _neu("Akte Medien", deadline_date="2027-01-31")
        jelly = _neu("Akte Jellyfin", eltern_ids=[medien["id"]])
        tresor = _neu("Akte Tresor", eltern_ids=[medien["id"]])
        # Ein Projekt unter zwei Kindern desselben Dachs zaehlt nur einmal.
        geteilt = _neu("Akte Geteilt", eltern_ids=[jelly["id"], tresor["id"]])
        client.post(f"/api/projects/{jelly['id']}/aufgaben", json={"titel": "Plugin pruefen", "faellig": "2027-01-10"})
        client.post(f"/api/projects/{geteilt['id']}/aufgaben", json={"titel": "Geteilte Aufgabe", "tag": "2027-03-01"})
        client.post(f"/api/projects/{medien['id']}/aufgaben", json={"titel": "Uebergreifend"})
        client.post(f"/api/projects/{tresor['id']}/milestones", json={"title": "Tresor-Zentrale", "target_date": "2027-02-01"})
        client.post(f"/api/projects/{tresor['id']}/kontakte", json={"kontakt_id": "k-1", "rolle": "Helferin"})
        TERMINE.append({"id": "t1", "title": "Abnahme", "start": "2027-01-05T10:00:00",
                        "end": "2027-01-05T11:00:00", "projekt": jelly["slug"]})
        BUDGETS[jelly["slug"]] = {"projekt": jelly["slug"], "budget_cent": 10000, "ausgaben_cent": 2500,
                                  "einnahmen_cent": 0, "rest_cent": 7500, "anzahl_buchungen": 2}
        BUDGETS[tresor["slug"]] = {"projekt": tresor["slug"], "budget_cent": None, "ausgaben_cent": 1000,
                                   "einnahmen_cent": 0, "rest_cent": None, "anzahl_buchungen": 1}

        a = client.get(f"/api/projects/{medien['id']}/akte").json()
        titel = sorted(x["titel"] for x in a["aufgaben"])
        self.assertEqual(titel, ["Geteilte Aufgabe", "Plugin pruefen", "Uebergreifend"])
        arten = [(z["art"], z["titel"]) for z in a["zeitleiste"]]
        self.assertEqual(arten, [("termin", "Abnahme"), ("frist", "Plugin pruefen"),
                                 ("projektfrist", "Frist: Akte Medien"), ("meilenstein", "Tresor-Zentrale"),
                                 ("geplant", "Geteilte Aufgabe")])
        self.assertEqual(a["zeitleiste"][0]["uhrzeit"], "10:00")
        self.assertEqual([k["projekt"] for k in a["kontakte"]], [tresor["slug"]])
        self.assertEqual(a["budget"]["gesamt"]["ausgaben_cent"], 3500)
        self.assertEqual(a["budget"]["gesamt"]["budget_cent"], 10000)
        kacheln = {k["slug"]: k for k in a["kinder"]}
        self.assertEqual(set(kacheln), {jelly["slug"], tresor["slug"]})
        self.assertEqual(kacheln[jelly["slug"]]["offen"], 2)  # eigene + geteilte
        self.assertEqual(kacheln[jelly["slug"]]["naechstes_datum"] >= "2027-01-05", True)

        unten = client.get(f"/api/projects/{geteilt['id']}/akte").json()
        self.assertEqual(len(unten["eltern"]), 2)
        self.assertEqual(unten["pfad"][0]["slug"], medien["slug"])

    def test_angeheftete_aufgabe_zaehlt_im_teilbaum_einmal(self):
        """Haengt eine Aufgabe in Kind und Enkel, zaehlt die Kachel des Kinds sie einmal."""
        from app import aufgaben_dienst
        dach = _neu("Akte Zaehl Dach")
        kind = _neu("Akte Zaehl Kind", eltern_ids=[dach["id"]])
        enkel = _neu("Akte Zaehl Enkel", eltern_ids=[kind["id"]])
        r = client.post(f"/api/projects/{enkel['id']}/aufgaben", json={"titel": "Doppelt angeheftet"})
        aufgaben_dienst.aufruf.aufgaben[r.json()["id"]]["weitere_projekte"] = [kind["slug"]]
        a = client.get(f"/api/projects/{dach['id']}/akte").json()
        self.assertEqual({k["slug"]: k["offen"] for k in a["kinder"]}, {kind["slug"]: 1})
        liste = {p["slug"]: p for p in client.get("/api/projects").json()}
        self.assertEqual(liste[kind["slug"]]["open_tasks"], 1)  # angeheftet, wie in der Akte
        self.assertEqual(liste[enkel["slug"]]["open_tasks"], 1)

    def test_ausfall_wird_gesagt_nicht_verschwiegen(self):
        p = _neu("Akte Ausfall")
        alt = nachbarn.termine
        nachbarn.termine = lambda *a: None
        try:
            a = client.get(f"/api/projects/{p['id']}/akte").json()
        finally:
            nachbarn.termine = alt
        self.assertTrue(a["termine_fehlen"])


if __name__ == "__main__":
    unittest.main()
