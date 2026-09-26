"""Zwei Nutzer, ein Dienst: sieht jeder nur seins?

Bis zum 30.08.2026 sah hier jeder zugelassene Nutzer dasselbe Inventar. Das fiel
nicht auf, weil ALLOWED_SUBS nur einen Sub durchliess, und es waere genau in dem
Moment aufgefallen, in dem jemand das Gate oeffnet, um Saganta multiuser zu
machen. Diese Tests pruefen die Trennung am Verhalten der API und nicht daran,
ob im Quelltext ein Filter steht.

Die Tests fahren gegen eine eigene SQLite-Datei und lassen das Gate absichtlich
offen (ALLOWED_SUBS leer), denn geprueft werden soll die Schicht darunter.
"""
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="assets-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ALLOWED_SUBS"] = ""
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-pruefung")

import time  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

ANNA = "sub-anna"
BERND = "sub-bernd"


def kopf(sub: str) -> dict:
    token = jwt.encode(
        {"sub": sub, "iss": "saganta", "aud": "assets-api", "exp": int(time.time()) + 300},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


class TestTrennung(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.c = TestClient(app)

    def _anlegen(self, sub: str, name: str) -> int:
        r = self.c.post("/api/assets", json={"name": name}, headers=kopf(sub))
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def test_liste_zeigt_nur_eigene(self):
        self._anlegen(ANNA, "Annas Kamera")
        self._anlegen(BERND, "Bernds Bohrmaschine")
        namen_anna = [a["name"] for a in self.c.get("/api/assets", headers=kopf(ANNA)).json()]
        namen_bernd = [a["name"] for a in self.c.get("/api/assets", headers=kopf(BERND)).json()]
        self.assertIn("Annas Kamera", namen_anna)
        self.assertNotIn("Bernds Bohrmaschine", namen_anna)
        self.assertIn("Bernds Bohrmaschine", namen_bernd)
        self.assertNotIn("Annas Kamera", namen_bernd)

    def test_fremdes_asset_ist_nicht_abrufbar(self):
        fremd = self._anlegen(ANNA, "Annas Objektiv")
        r = self.c.get(f"/api/assets/{fremd}", headers=kopf(BERND))
        self.assertEqual(r.status_code, 404, "fremde Zeile darf nicht lesbar sein")

    def test_fremdes_asset_ist_nicht_aenderbar(self):
        fremd = self._anlegen(ANNA, "Annas Stativ")
        r = self.c.patch(f"/api/assets/{fremd}", json={"notes": "gekapert"}, headers=kopf(BERND))
        self.assertEqual(r.status_code, 404)
        # Gegenprobe: der Besitzer kommt weiterhin heran und die Notiz steht nicht drin.
        eigen = self.c.get(f"/api/assets/{fremd}", headers=kopf(ANNA)).json()
        self.assertIsNone(eigen["notes"])

    def test_fremdes_asset_ist_nicht_loeschbar(self):
        fremd = self._anlegen(ANNA, "Annas Blitz")
        self.assertEqual(self.c.delete(f"/api/assets/{fremd}", headers=kopf(BERND)).status_code, 404)
        self.assertEqual(self.c.get(f"/api/assets/{fremd}", headers=kopf(ANNA)).status_code, 200)

    def test_empfehlungen_bleiben_getrennt(self):
        """Der zweite Lesepfad neben der Liste. Er hatte denselben Fehler."""
        r = self.c.post(
            "/api/assets",
            json={"name": "Teures Objektiv", "purchase_price_eur": 900, "usage_status": "unused"},
            headers=kopf(ANNA),
        )
        self.assertEqual(r.status_code, 201, r.text)
        self.c.patch(
            f"/api/assets/{r.json()['id']}", json={"market_value_eur": 800}, headers=kopf(ANNA)
        )
        namen = [a["name"] for a in self.c.get("/api/assets/recommendations", headers=kopf(BERND)).json()]
        self.assertNotIn("Teures Objektiv", namen)

    def test_gleicher_spiegel_zweimal_kollidiert_nicht(self):
        """Zwei Nutzer duerfen dieselbe Lager-Kennung spiegeln.

        Der eindeutige Schluessel lief frueher ueber (source, source_id) allein.
        Zwei Nutzer mit demselben Element haetten sich eine Zeile geteilt, und der
        Sync des einen haette die Werte des anderen ueberschrieben, ohne Fehler.
        """
        from app.db import SessionLocal
        from app.models import Asset

        db = SessionLocal()
        try:
            db.add(Asset(owner_sub=ANNA, source="lager-electronics", source_id="42", name="Laptop"))
            db.add(Asset(owner_sub=BERND, source="lager-electronics", source_id="42", name="Laptop"))
            db.commit()
        finally:
            db.close()


class TestMigration(unittest.TestCase):
    """Der Umstieg einer bestehenden Datenbank ohne owner_sub.

    ★ Jeder Fall laeuft in einem eigenen Prozess. Der erste Anlauf lud stattdessen
    `app.db` im laufenden Testprozess neu und zog damit den anderen Tests ihre
    Datenbank unter den Fuessen weg: drei Fehler, die nach kaputter Migration
    aussahen und nur kaputte Testfuehrung waren. Ein eigener Prozess ist zugleich
    naeher am Ernstfall, denn genau so laeuft die Migration live, beim Start des
    Dienstes gegen eine vorhandene Datei.
    """

    def _alte_tabelle(self, pfad: str, zeilen: int, mit_zeitstempel: bool = True) -> None:
        import sqlite3

        con = sqlite3.connect(pfad)
        con.execute(
            "CREATE TABLE assets (id INTEGER PRIMARY KEY, source VARCHAR(50), "
            "source_id VARCHAR(100), name VARCHAR(200), category VARCHAR(100), "
            "location VARCHAR(100), usage_status VARCHAR(50), purchase_date DATE, "
            "purchase_price_eur FLOAT, market_value_eur FLOAT, market_value_at DATETIME, "
            "notes VARCHAR(500), created_at DATETIME, updated_at DATETIME)"
        )
        # ★ Die Indizes gehoeren zum Nachbau dazu. Ohne sie war dieser Aufbau
        # nicht originalgetreu, die Tests waren gruen, und live brach die
        # Migration ab: SQLite nimmt beim Umbenennen einer Tabelle die Indizes
        # mit, ihre Namen bleiben aber vergeben, und das Neuanlegen kollidiert.
        con.execute("CREATE INDEX ix_assets_source ON assets (source)")
        con.execute("CREATE INDEX ix_assets_usage_status ON assets (usage_status)")
        for i in range(zeilen):
            if mit_zeitstempel:
                con.execute(
                    "INSERT INTO assets (source, source_id, name, usage_status, created_at, "
                    "updated_at) VALUES (?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                    ("saganta", str(i), f"Altbestand {i}", "reserve"),
                )
            else:
                con.execute(
                    "INSERT INTO assets (source, source_id, name, usage_status) VALUES (?,?,?,?)",
                    ("saganta", str(i), f"Altbestand {i}", "reserve"),
                )
        con.commit()
        con.close()

    def _migrieren(self, zeilen: int, allowed: list[str], backfill: str = "",
                   mit_zeitstempel: bool = True):
        """Startet die Migration in einem eigenen Prozess gegen eine frische Datei.

        Rueckgabe: (Rueckgabecode, Ausgabe, Datenbankpfad).
        """
        import subprocess
        import sys

        pfad = f"{tempfile.mkdtemp(prefix='assets-mig-')}/alt.db"
        self._alte_tabelle(pfad, zeilen, mit_zeitstempel)
        umgebung = {
            **os.environ,
            "DATABASE_URL": f"sqlite:///{pfad}",
            "ALLOWED_SUBS": ",".join(allowed),
            "ASSETS_BACKFILL_SUB": backfill,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        skript = (
            "from app.db import init_db, engine\n"
            "from sqlalchemy import inspect, text\n"
            "init_db()\n"
            "with engine.connect() as c:\n"
            "    n = c.execute(text('select count(*) from assets')).scalar()\n"
            "    b = c.execute(text('select distinct owner_sub from assets')).scalars().all()\n"
            "print('SPALTEN', sorted(s['name'] for s in inspect(engine).get_columns('assets')))\n"
            "print('INDIZES', sorted(i['name'] for i in inspect(engine).get_indexes('assets')))\n"
            "print('TABELLEN', sorted(inspect(engine).get_table_names()))\n"
            "print('ZEILEN', n)\n"
            "print('BESITZER', b)\n"
        )
        fertig = subprocess.run(
            [sys.executable, "-c", skript],
            capture_output=True, text=True, env=umgebung, cwd="/src" if os.path.isdir("/src") else None,
        )
        return fertig.returncode, fertig.stdout + fertig.stderr, pfad

    def test_bestand_bekommt_den_einzigen_zugelassenen_sub(self):
        rc, ausgabe, _ = self._migrieren(3, [ANNA])
        self.assertEqual(rc, 0, ausgabe)
        self.assertIn("ZEILEN 3", ausgabe, "keine Zeile darf beim Umbau verloren gehen")
        self.assertIn(f"BESITZER ['{ANNA}']", ausgabe)
        self.assertIn("'owner_sub'", ausgabe)

    def test_ohne_eindeutigen_besitzer_bricht_der_start_ab(self):
        """Fail-closed statt raten.

        Zwei zugelassene Subs und Daten ohne Besitzer: jede Zuordnung waere eine
        Behauptung. Ein Abbruch ist hier die ehrlichere Antwort als eine
        Migration, die gelungen aussieht und fremdes Inventar verschenkt.
        """
        rc, ausgabe, _ = self._migrieren(2, [ANNA, BERND])
        self.assertNotEqual(rc, 0, "der Start haette abbrechen muessen")
        self.assertIn("kein eindeutiger Besitzer", ausgabe)

    def test_ausdruecklicher_besitzer_loest_die_mehrdeutigkeit(self):
        rc, ausgabe, _ = self._migrieren(2, [ANNA, BERND], backfill=BERND)
        self.assertEqual(rc, 0, ausgabe)
        self.assertIn(f"BESITZER ['{BERND}']", ausgabe)

    def test_leere_tabelle_braucht_keinen_besitzer(self):
        rc, ausgabe, _ = self._migrieren(0, [ANNA, BERND])
        self.assertEqual(rc, 0, ausgabe)
        self.assertIn("'owner_sub'", ausgabe)

    def test_indizes_stehen_nach_der_umstellung(self):
        """Live am 30.08. genau hier gescheitert.

        SQLite nimmt Indizes beim Umbenennen mit. Ihre Namen bleiben belegt, das
        Neuanlegen kollidiert, der Dienst kommt nicht hoch. Und nach einem solchen
        Abbruch legt create_all an der dann vorhandenen Tabelle keine Indizes mehr
        an: der Dienst laeuft, wird aber mit jeder Zeile langsamer.
        """
        rc, ausgabe, _ = self._migrieren(3, [ANNA])
        self.assertEqual(rc, 0, ausgabe)
        self.assertIn("ix_assets_source", ausgabe)
        self.assertIn("ix_assets_usage_status", ausgabe)

    def test_alte_tabelle_bleibt_nicht_liegen(self):
        rc, ausgabe, _ = self._migrieren(3, [ANNA])
        self.assertEqual(rc, 0, ausgabe)
        self.assertNotIn("assets_vor_mandanten", ausgabe)

    def test_zeile_ohne_zeitstempel_haelt_die_migration_nicht_auf(self):
        """Gefunden beim Schreiben dieser Tests.

        Die Zeitstempel sind im neuen Schema NOT NULL. Eine Altzeile ohne sie
        liess die Migration mit IntegrityError abbrechen, und weil sie beim Start
        laeuft, waere daraus eine Neustartschleife geworden statt einer Fehlermeldung,
        die jemand liest.
        """
        rc, ausgabe, _ = self._migrieren(2, [ANNA], mit_zeitstempel=False)
        self.assertEqual(rc, 0, ausgabe)
        self.assertIn("ZEILEN 2", ausgabe)


if __name__ == "__main__":
    unittest.main()
