"""Tests der Loesch-Mechanik.

Der Schwerpunkt liegt auf den beiden Pruefungen, die den Wert dieses Moduls
ausmachen, und jede von ihnen hat hier eine **Positivkontrolle**: ein Fall, in
dem sie rot werden MUSS. Eine Pruefung, die nie anschlaegt, ist von einer, die
nicht laeuft, nicht zu unterscheiden.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from saganta_dienst import loeschen


def _speicher_engine():
    """Eine In-Memory-Datenbank, die alle Verbindungen teilen.

    ⚠️ Ohne ``StaticPool`` bekommt jede neue Verbindung ihre **eigene** leere
    Datenbank. Das faellt nicht auf, solange ein Test dieselbe Session
    durchhaelt, und schlaegt zu, sobald eine Route ihre Session per Dependency
    frisch oeffnet: "no such table".
    """
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

from saganta_dienst import loeschen


def _schema() -> MetaData:
    """Ein Schema, das jede Lage einmal enthaelt, die in der Suite vorkommt."""
    md = MetaData()
    Table(
        "buecher", md,
        Column("id", Integer, primary_key=True),
        Column("owner_sub", String(128)),
        Column("name", String(80)),
    )
    Table(
        "notizen", md,
        Column("id", Integer, primary_key=True),
        Column("owner_sub", String(128)),
        Column("buch_id", Integer, ForeignKey("buecher.id", ondelete="SET NULL")),
        Column("titel", String(80)),
    )
    # Kind per CASCADE: faellt mit der Notiz, braucht keinen eigenen Schritt.
    Table(
        "anhaenge", md,
        Column("id", Integer, primary_key=True),
        Column("notiz_id", Integer, ForeignKey("notizen.id", ondelete="CASCADE")),
        Column("ablage", String(80)),
    )
    # Enkel per CASCADE: prueft den transitiven Abschluss.
    Table(
        "anhang_vorschauen", md,
        Column("id", Integer, primary_key=True),
        Column("anhang_id", Integer, ForeignKey("anhaenge.id", ondelete="CASCADE")),
    )
    # Gemeinsamer Bestand ohne Mandanten und ohne Eltern.
    Table(
        "feiertage", md,
        Column("id", Integer, primary_key=True),
        Column("datum", String(10)),
    )
    return md


def _plan_vollstaendig() -> loeschen.Plan:
    return loeschen.Plan(
        dienst="test",
        schritte=(
            loeschen.eigene("notizen"),
            loeschen.eigene("buecher"),
        ),
        gemeinsam=frozenset({"feiertage"}),
    )


class TestAbdeckung(unittest.TestCase):
    """abdeckung_pruefen: leitet das Soll aus den Modellen ab, nicht aus einer Liste."""

    def setUp(self) -> None:
        self.md = _schema()

    def test_vollstaendiger_plan_hat_keine_luecke(self):
        self.assertEqual(loeschen.abdeckung_pruefen(_plan_vollstaendig(), self.md), [])

    def test_cascade_kind_braucht_keinen_schritt(self):
        """anhaenge haengt per CASCADE an notizen und ist damit bedacht."""
        befunde = loeschen.abdeckung_pruefen(_plan_vollstaendig(), self.md)
        self.assertNotIn("anhaenge", " ".join(befunde))

    def test_cascade_wird_transitiv_aufgeloest(self):
        """anhang_vorschauen haengt an anhaenge, das an notizen haengt: zwei Glieder."""
        befunde = loeschen.abdeckung_pruefen(_plan_vollstaendig(), self.md)
        self.assertNotIn("anhang_vorschauen", " ".join(befunde))

    # --- Positivkontrollen: hier MUSS die Pruefung anschlagen ---

    def test_positivkontrolle_vergessene_mandantentabelle(self):
        """Der Fall, fuer den es die Pruefung gibt: eine neue Tabelle mit owner_sub.

        Sie traegt keine Zeile. Genau deshalb ist dieser Test der Beweis: ein
        Loeschlauf haette hier Erfolg gemeldet.
        """
        Table(
            "neue_funktion", self.md,
            Column("id", Integer, primary_key=True),
            Column("owner_sub", String(128)),
        )
        befunde = loeschen.abdeckung_pruefen(_plan_vollstaendig(), self.md)
        self.assertEqual(len(befunde), 1, befunde)
        self.assertIn("neue_funktion", befunde[0])
        self.assertIn("owner_sub", befunde[0])

    def test_positivkontrolle_abweichender_spaltenname(self):
        """Ein Pruefer, der nur `owner_sub` kennt, findet `sub` nicht."""
        Table(
            "fremd_benannt", self.md,
            Column("id", Integer, primary_key=True),
            Column("sub", String(128)),
        )
        befunde = loeschen.abdeckung_pruefen(_plan_vollstaendig(), self.md)
        self.assertTrue(any("fremd_benannt" in b for b in befunde), befunde)

    def test_positivkontrolle_kind_ohne_cascade(self):
        """NO-ACTION-Kind: faellt nicht mit und wuerde das Loeschen der Eltern brechen."""
        Table(
            "lose_zeilen", self.md,
            Column("id", Integer, primary_key=True),
            Column("notiz_id", Integer, ForeignKey("notizen.id")),
        )
        befunde = loeschen.abdeckung_pruefen(_plan_vollstaendig(), self.md)
        treffer = [b for b in befunde if "lose_zeilen" in b]
        self.assertEqual(len(treffer), 1, befunde)
        self.assertIn("CASCADE", treffer[0])

    def test_positivkontrolle_unerklaerter_stammbestand(self):
        """Gemeinsamer Bestand muss ausgesprochen sein, nicht angenommen."""
        plan = loeschen.Plan(dienst="test", schritte=(loeschen.eigene("notizen"),
                                                      loeschen.eigene("buecher")))
        befunde = loeschen.abdeckung_pruefen(plan, self.md)
        self.assertTrue(any("feiertage" in b and "gemeinsam" in b for b in befunde), befunde)

    def test_positivkontrolle_leere_metadaten_brechen_laut(self):
        """Blinde Pruefung ist schlimmer als keine, denn sie meldet "sauber".

        ``Base.metadata`` fuellt sich erst mit dem ``models``-Import. Fehlt der,
        findet die Abdeckungspruefung nichts, die Restsuche findet nichts, und
        ein Lauf gegen eine volle Datenbank meldet Erfolg.
        """
        from sqlalchemy import MetaData as LeereMetadaten

        with self.assertRaises(RuntimeError) as gefangen:
            loeschen.abdeckung_pruefen(_plan_vollstaendig(), LeereMetadaten())
        self.assertIn("models", str(gefangen.exception))

    def test_per_trigger_gilt_als_bedacht(self):
        """Eine FTS-Tabelle liegt nicht in den Metadaten, aber sie muss erklaert sein."""
        plan = loeschen.Plan(
            dienst="test",
            schritte=(loeschen.eigene("notizen"), loeschen.eigene("buecher")),
            gemeinsam=frozenset({"feiertage"}),
            per_trigger=frozenset({"notizen_fts"}),
        )
        self.assertEqual(loeschen.abdeckung_pruefen(plan, self.md), [])


class TestAusfuehren(unittest.TestCase):
    """ausfuehren: loescht genau einen Mandanten, berichtet, und prueft sich selbst."""

    def setUp(self) -> None:
        self.md = _schema()
        self.engine = _speicher_engine()

        @event.listens_for(self.engine, "connect")
        def _fk_an(conn, _rec):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        self.md.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.execute(text(
            "INSERT INTO buecher (id, owner_sub, name) VALUES "
            "(1,'ich','mein Buch'), (2,'andere','fremdes Buch')"))
        self.db.execute(text(
            "INSERT INTO notizen (id, owner_sub, buch_id, titel) VALUES "
            "(1,'ich',1,'meine A'), (2,'ich',1,'meine B'), (3,'andere',2,'fremde')"))
        self.db.execute(text(
            "INSERT INTO anhaenge (id, notiz_id, ablage) VALUES "
            "(1,1,'a.png'), (2,3,'fremd.png')"))
        self.db.execute(text("INSERT INTO feiertage (id, datum) VALUES (1,'2026-01-01')"))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def _zahl(self, sql: str) -> int:
        return int(self.db.execute(text(sql)).scalar() or 0)

    def test_loescht_den_eigenen_bestand(self):
        bericht = loeschen.ausfuehren(self.db, _plan_vollstaendig(), self.md, "ich")
        self.assertEqual(bericht.zeilen["notizen"], 2)
        self.assertEqual(bericht.zeilen["buecher"], 1)
        self.assertTrue(bericht.sauber, bericht.als_dict())
        self.assertEqual(self._zahl("SELECT count(*) FROM notizen WHERE owner_sub='ich'"), 0)

    def test_gegenprobe_fremder_bestand_bleibt(self):
        """Die Haelfte des Beweises, die man leicht weglaesst."""
        loeschen.ausfuehren(self.db, _plan_vollstaendig(), self.md, "ich")
        self.assertEqual(self._zahl("SELECT count(*) FROM notizen WHERE owner_sub='andere'"), 1)
        self.assertEqual(self._zahl("SELECT count(*) FROM buecher WHERE owner_sub='andere'"), 1)
        self.assertEqual(self._zahl("SELECT count(*) FROM anhaenge WHERE notiz_id=3"), 1)

    def test_cascade_raeumt_die_kinder_mit(self):
        loeschen.ausfuehren(self.db, _plan_vollstaendig(), self.md, "ich")
        self.assertEqual(self._zahl("SELECT count(*) FROM anhaenge WHERE notiz_id=1"), 0)

    def test_gemeinsamer_bestand_bleibt(self):
        loeschen.ausfuehren(self.db, _plan_vollstaendig(), self.md, "ich")
        self.assertEqual(self._zahl("SELECT count(*) FROM feiertage"), 1)

    def test_trockenlauf_zaehlt_und_loescht_nicht(self):
        bericht = loeschen.ausfuehren(self.db, _plan_vollstaendig(), self.md, "ich",
                                      trockenlauf=True)
        self.assertEqual(bericht.zeilen["notizen"], 2)
        self.assertTrue(bericht.trockenlauf)
        self.assertEqual(bericht.reste, {})
        self.assertEqual(self._zahl("SELECT count(*) FROM notizen WHERE owner_sub='ich'"), 2)

    def test_unbekannter_mandant_ist_kein_fehler(self):
        bericht = loeschen.ausfuehren(self.db, _plan_vollstaendig(), self.md, "gibt-es-nicht")
        self.assertEqual(bericht.summe, 0)
        self.assertTrue(bericht.sauber)

    # --- Positivkontrolle der Restsuche ---

    def test_positivkontrolle_schritt_verfehlt_seine_tabelle(self):
        """Ein Plan, dessen Bedingung nie greift, meldet 0 und sieht sauber aus.

        Ohne Restsuche waere dieser Lauf von einem erfolgreichen nicht zu
        unterscheiden: 0 geloeschte Zeilen liest sich wie "war nichts da".
        Mit ihr bricht er, und der Bestand ist noch vollstaendig da.
        """
        plan = loeschen.Plan(
            dienst="test",
            # Falsche Spalte: `name` statt `owner_sub`. Trifft nie.
            schritte=(loeschen.eigene("notizen", spalte="titel"),
                      loeschen.eigene("buecher", spalte="name")),
            gemeinsam=frozenset({"feiertage"}),
        )
        bericht = loeschen.ausfuehren(self.db, plan, self.md, "ich")
        self.assertFalse(bericht.sauber)
        self.assertIn("notizen.owner_sub", bericht.reste)
        self.assertEqual(bericht.reste["notizen.owner_sub"], 2)
        # Zurueckgerollt: ein halb geloeschtes Konto ist schlimmer als ein ganzes.
        self.assertEqual(self._zahl("SELECT count(*) FROM notizen WHERE owner_sub='ich'"), 2)

    def _plan_mit_dateien(self, verzeichnis: Path) -> loeschen.Plan:
        """Ein Plan, dessen Dateiliste aus der Datenbank kommt, wie im echten Dienst."""

        def sammeln(db, sub):
            namen = db.execute(
                text("SELECT ablage FROM anhaenge a JOIN notizen n ON n.id = a.notiz_id "
                     "WHERE n.owner_sub = :sub"),
                {"sub": sub},
            ).scalars().all()
            return [verzeichnis / name for name in namen]

        return loeschen.Plan(
            dienst="test",
            schritte=(loeschen.eigene("notizen"), loeschen.eigene("buecher")),
            gemeinsam=frozenset({"feiertage"}),
            dateien=sammeln,
        )

    def test_dateien_des_mandanten_fallen_mit(self):
        with TemporaryDirectory() as d:
            ablage = Path(d)
            (ablage / "a.png").write_bytes(b"x")
            (ablage / "fremd.png").write_bytes(b"x")
            bericht = loeschen.ausfuehren(self.db, self._plan_mit_dateien(ablage),
                                          self.md, "ich")
            self.assertTrue(bericht.sauber, bericht.als_dict())
            self.assertFalse((ablage / "a.png").exists())
            # Gegenprobe: die Datei des anderen Mandanten bleibt.
            self.assertTrue((ablage / "fremd.png").exists())

    def test_positivkontrolle_pfade_werden_vor_den_schritten_gesammelt(self):
        """Der Riss, den ein nachgelagerter Haken hinterlassen wuerde.

        Die Zeile, die den Dateinamen nennt, faellt per CASCADE mit der Notiz.
        Wer erst loescht und dann nach Pfaden sucht, findet keine, meldet
        trotzdem Erfolg, und die Datei liegt fuer immer in der Ablage. Dieser
        Test schlaegt genau dann fehl, wenn die Reihenfolge gedreht wird.
        """
        with TemporaryDirectory() as d:
            ablage = Path(d)
            (ablage / "a.png").write_bytes(b"x")
            bericht = loeschen.ausfuehren(self.db, self._plan_mit_dateien(ablage),
                                          self.md, "ich")
            self.assertTrue(any("1 Datei(en)/Ordner" in z and "geloescht" in z
                                for z in bericht.nebenwirkungen), bericht.nebenwirkungen)

    def test_rueckrollen_laesst_die_dateien_liegen(self):
        """Die andere Haelfte: kein Dateiverlust bei gescheitertem Lauf.

        Eine Datenbankzeile ohne ihre Datei ist ein Defekt, den niemand mehr
        reparieren kann. Eine Datei ohne Zeile kostet nur Platz.
        """
        with TemporaryDirectory() as d:
            ablage = Path(d)
            (ablage / "a.png").write_bytes(b"x")

            def sammeln(db, sub):
                return [ablage / "a.png"]

            plan = loeschen.Plan(
                dienst="test",
                # Verfehlt ihre Tabellen: die Restsuche rollt zurueck.
                schritte=(loeschen.eigene("notizen", spalte="titel"),
                          loeschen.eigene("buecher", spalte="name")),
                gemeinsam=frozenset({"feiertage"}),
                dateien=sammeln,
            )
            bericht = loeschen.ausfuehren(self.db, plan, self.md, "ich")
            self.assertFalse(bericht.sauber)
            self.assertTrue((ablage / "a.png").exists())
            self.assertTrue(any("unberuehrt" in z for z in bericht.nebenwirkungen),
                            bericht.nebenwirkungen)

    def test_trockenlauf_laesst_dateien_liegen(self):
        with TemporaryDirectory() as d:
            ablage = Path(d)
            (ablage / "a.png").write_bytes(b"x")
            bericht = loeschen.ausfuehren(self.db, self._plan_mit_dateien(ablage),
                                          self.md, "ich", trockenlauf=True)
            self.assertTrue((ablage / "a.png").exists())
            self.assertTrue(any("waeren zu loeschen" in z for z in bericht.nebenwirkungen))

    def test_ueber_loescht_kind_ohne_cascade(self):
        """`ueber(...)` greift ein NO-ACTION-Kind, bevor die Eltern fallen."""
        self.md = _schema()
        Table(
            "lose_zeilen", self.md,
            Column("id", Integer, primary_key=True),
            Column("notiz_id", Integer, ForeignKey("notizen.id")),
        )
        engine = _speicher_engine()

        @event.listens_for(engine, "connect")
        def _fk_an(conn, _rec):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        self.md.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.execute(text("INSERT INTO notizen (id, owner_sub, titel) VALUES (1,'ich','A')"))
        db.execute(text("INSERT INTO lose_zeilen (id, notiz_id) VALUES (1,1)"))
        db.commit()
        plan = loeschen.Plan(
            dienst="test",
            schritte=(
                loeschen.ueber("lose_zeilen", "notiz_id", "notizen", "id"),
                loeschen.eigene("notizen"),
                loeschen.eigene("buecher"),
            ),
            gemeinsam=frozenset({"feiertage"}),
        )
        self.assertEqual(loeschen.abdeckung_pruefen(plan, self.md), [])
        bericht = loeschen.ausfuehren(db, plan, self.md, "ich")
        self.assertTrue(bericht.sauber, bericht.als_dict())
        self.assertEqual(bericht.zeilen["lose_zeilen"], 1)
        db.close()


class TestLiveTabellen(unittest.TestCase):
    """ungedeckte_live_tabellen: fragt die Datenbank, nicht die Modelle.

    Der Grund fuer diese Pruefung ist ein gemessener Fehlstand: der
    ``briefkasten`` behielt nach einem als "sauber" gemeldeten Loeschlauf das
    **Embedding des geloeschten Briefs** in einer ``vec0``-Virtualtabelle. Die
    stand in keinem Modell, also war sie fuer ``abdeckung_pruefen`` unsichtbar.
    """

    def setUp(self) -> None:
        self.md = _schema()
        self.engine = _speicher_engine()

        @event.listens_for(self.engine, "connect")
        def _fk_an(conn, _rec):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        self.md.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.db.close()

    def test_reine_modelltabellen_ergeben_keinen_befund(self):
        self.assertEqual(
            loeschen.ungedeckte_live_tabellen(_plan_vollstaendig(), self.db, self.md), [])

    def test_positivkontrolle_tabelle_per_rohem_sql(self):
        """Eine Tabelle, die kein Modell kennt, muss auffallen."""
        self.db.execute(text("CREATE TABLE schattenbestand (id INTEGER PRIMARY KEY, inhalt TEXT)"))
        self.db.commit()
        befunde = loeschen.ungedeckte_live_tabellen(_plan_vollstaendig(), self.db, self.md)
        self.assertEqual(len(befunde), 1, befunde)
        self.assertIn("schattenbestand", befunde[0])

    def test_cascade_kante_in_der_datenbank_deckt_ab(self):
        """Kein Fehlalarm bei einer per-SQL-Tabelle mit ON DELETE CASCADE.

        Genau hier schlug die erste Fassung falsch an (``paperless_import_map``).
        Eine Pruefung, die bei jedem sauberen Fall meldet, wird ignoriert.
        """
        self.db.execute(text(
            "CREATE TABLE anhang_sql (id INTEGER PRIMARY KEY, notiz_id INTEGER "
            "REFERENCES notizen(id) ON DELETE CASCADE)"))
        self.db.commit()
        self.assertEqual(
            loeschen.ungedeckte_live_tabellen(_plan_vollstaendig(), self.db, self.md), [])

    def test_positivkontrolle_kante_ohne_cascade_faellt_auf(self):
        """Dieselbe Tabelle ohne CASCADE muss gemeldet werden."""
        self.db.execute(text(
            "CREATE TABLE anhang_lose (id INTEGER PRIMARY KEY, notiz_id INTEGER "
            "REFERENCES notizen(id))"))
        self.db.commit()
        befunde = loeschen.ungedeckte_live_tabellen(_plan_vollstaendig(), self.db, self.md)
        self.assertTrue(any("anhang_lose" in b for b in befunde), befunde)

    def test_schattentabellen_einer_erklaerten_virtualtabelle_sind_bedacht(self):
        """FTS5 legt vier Begleittabellen an. Sie gehoeren ihrem Elternteil."""
        self.db.execute(text(
            "CREATE VIRTUAL TABLE notizen_fts USING fts5(titel, content='notizen', "
            "content_rowid='id')"))
        self.db.commit()
        plan = loeschen.Plan(
            dienst="test",
            schritte=(loeschen.eigene("notizen"), loeschen.eigene("buecher")),
            gemeinsam=frozenset({"feiertage"}),
            per_trigger=frozenset({"notizen_fts"}),
        )
        self.assertEqual(loeschen.ungedeckte_live_tabellen(plan, self.db, self.md), [])

    def test_positivkontrolle_unerklaerte_virtualtabelle(self):
        """Dieselbe FTS, aber nicht erklaert: muss auffallen, samt Schatten."""
        self.db.execute(text(
            "CREATE VIRTUAL TABLE notizen_fts USING fts5(titel, content='notizen', "
            "content_rowid='id')"))
        self.db.commit()
        befunde = loeschen.ungedeckte_live_tabellen(_plan_vollstaendig(), self.db, self.md)
        self.assertTrue(any("notizen_fts" in b and "Virtualtabelle" in b for b in befunde),
                        befunde)

    def test_wird_beim_lauf_wirklich_gerufen(self):
        """Eine Pruefung, die nur als Funktion existiert, prueft nichts."""
        self.db.execute(text("CREATE TABLE schattenbestand (id INTEGER PRIMARY KEY)"))
        self.db.commit()
        bericht = loeschen.ausfuehren(self.db, _plan_vollstaendig(), self.md, "ich",
                                      trockenlauf=True)
        self.assertTrue(any("schattenbestand" in l for l in bericht.luecken),
                        bericht.luecken)
        self.assertFalse(bericht.sauber)


class TestRouter(unittest.TestCase):
    """Die geteilten Konto-Routen, verdrahtet wie in einem echten Dienst."""

    def setUp(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        self.md = _schema()
        self.engine = _speicher_engine()

        @event.listens_for(self.engine, "connect")
        def _fk_an(conn, _rec):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        self.md.create_all(self.engine)
        Sitzung = sessionmaker(bind=self.engine)
        with Sitzung() as db:
            db.execute(text(
                "INSERT INTO notizen (id, owner_sub, titel) VALUES (1,'ich','A'), (2,'ich','B')"))
            db.commit()

        def hole_db():
            db = Sitzung()
            try:
                yield db
            finally:
                db.close()

        class FalscherNutzer:
            sub = "ich"

        app = FastAPI()
        app.include_router(
            loeschen.baue_router(_plan_vollstaendig(), self.md, hole_db, lambda: FalscherNutzer()),
            prefix="/api/konto",
        )
        self.client = TestClient(app)

    def test_bestand_zaehlt_und_loescht_nicht(self):
        antwort = self.client.get("/api/konto/bestand")
        self.assertEqual(antwort.status_code, 200, antwort.text)
        self.assertEqual(antwort.json()["zeilen"]["notizen"], 2)
        self.assertTrue(antwort.json()["trockenlauf"])

    def test_positivkontrolle_der_rumpf_wird_gelesen(self):
        """Die Falle, die diesen Test rechtfertigt.

        ``Loeschauftrag`` muss auf Modulebene stehen. Wandert die Klasse in die
        Fabrik zurueck, loest FastAPI die Annotation nicht auf, deutet sie als
        Query-Parameter und antwortet 422. Der Dienst sieht gesund aus, und kein
        Konto laesst sich mehr loeschen.
        """
        antwort = self.client.post("/api/konto/loeschen", json={"confirm": "KONTO LOESCHEN"})
        self.assertNotEqual(antwort.status_code, 422, "Der Rumpf wurde als Query gedeutet")
        self.assertEqual(antwort.status_code, 200, antwort.text)
        self.assertTrue(antwort.json()["sauber"])

    def test_ohne_bestaetigung_400(self):
        antwort = self.client.post("/api/konto/loeschen", json={})
        self.assertEqual(antwort.status_code, 400)
        self.assertEqual(self.client.get("/api/konto/bestand").json()["zeilen"]["notizen"], 2)


class TestBestaetigung(unittest.TestCase):
    def test_wortlaut_zaehlt(self):
        self.assertTrue(loeschen.bestaetigt("KONTO LOESCHEN"))
        self.assertTrue(loeschen.bestaetigt("  konto loeschen  "))
        self.assertFalse(loeschen.bestaetigt(""))
        self.assertFalse(loeschen.bestaetigt(None))
        self.assertFalse(loeschen.bestaetigt("ja"))
        self.assertFalse(loeschen.bestaetigt("KONTO LÖSCHEN"))


class TestDateien(unittest.TestCase):
    def test_entfernt_und_berichtet(self):
        with TemporaryDirectory() as d:
            da = Path(d) / "da.png"
            da.write_bytes(b"x")
            weg = Path(d) / "weg.png"
            zeilen, fehler = loeschen.dateien_entfernen([da, weg], trockenlauf=False)
            self.assertFalse(da.exists())
            self.assertEqual(fehler, [])
            self.assertTrue(any("1 Datei(en)/Ordner" in z and "geloescht" in z for z in zeilen))
            self.assertTrue(any("lagen nicht mehr" in z for z in zeilen))

    def test_trockenlauf_laesst_die_datei_liegen(self):
        with TemporaryDirectory() as d:
            da = Path(d) / "da.png"
            da.write_bytes(b"x")
            zeilen, fehler = loeschen.dateien_entfernen([da], trockenlauf=True)
            self.assertTrue(da.exists())
            self.assertEqual(fehler, [])
            self.assertTrue(any("waeren zu loeschen" in z for z in zeilen))

    def test_verzeichnis_faellt_mit_inhalt(self):
        """news legt je Mandant einen Ordner mit Sprachausgaben an."""
        with TemporaryDirectory() as d:
            ordner = Path(d) / "ein-sub"
            ordner.mkdir()
            (ordner / "2026-10-01.mp3").write_bytes(b"x")
            zeilen, fehler = loeschen.dateien_entfernen([ordner], trockenlauf=False)
            self.assertFalse(ordner.exists())
            self.assertEqual(fehler, [])
            self.assertTrue(any("geloescht" in z for z in zeilen))

    def test_positivkontrolle_fehlschlag_wird_gemeldet(self):
        """Ein nicht entfernbarer Pfad darf nicht als Erfolg durchgehen.

        Sonst meldet der Lauf ein geloeschtes Konto, und die Inhalte liegen
        weiter auf der Platte.
        """
        with TemporaryDirectory() as d:
            schreibgeschuetzt = Path(d) / "fest"
            schreibgeschuetzt.mkdir()
            (schreibgeschuetzt / "drin.mp3").write_bytes(b"x")
            schreibgeschuetzt.chmod(0o500)
            try:
                zeilen, fehler = loeschen.dateien_entfernen(
                    [schreibgeschuetzt / "drin.mp3"], trockenlauf=False)
                # Als root ist auch ein 0500-Verzeichnis beschreibbar. Dann gibt
                # es nichts zu pruefen, und ein erzwungener Fehlschlag waere
                # eine Behauptung ueber den Testlauf, nicht ueber den Code.
                if not fehler:
                    self.skipTest("Lauf hat Schreibrecht trotz 0500 (root)")
                self.assertTrue(any("Permission denied" in f or "denied" in f.lower()
                                    for f in fehler), fehler)
            finally:
                schreibgeschuetzt.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
