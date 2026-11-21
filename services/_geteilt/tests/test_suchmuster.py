"""LIKE-Platzhalter aus der Eingabe wirken nicht mehr (`saganta_dienst.suchmuster`)."""
import unittest

from sqlalchemy import Column, Integer, String, create_engine, func, select, text
from sqlalchemy.orm import Session, declarative_base

from saganta_dienst.suchmuster import ESCAPE, enthaelt

Basis = declarative_base()


class Zeile(Basis):
    __tablename__ = "zeile"
    id = Column(Integer, primary_key=True)
    text = Column(String)


class Suchmuster(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Basis.metadata.create_all(self.engine)
        with Session(self.engine) as s:
            s.add_all([Zeile(text=t) for t in ("Rabatt 100% bis Freitag", "1000 Euro", "a_b", "axb", "c:\\pfad")])
            s.commit()

    def _orm(self, eingabe):
        with Session(self.engine) as s:
            return sorted(s.scalars(select(Zeile.text).where(
                func.lower(Zeile.text).like(enthaelt(eingabe.lower()), escape=ESCAPE))))

    def _sql(self, eingabe):
        with self.engine.connect() as c:
            return sorted(r[0] for r in c.execute(
                text("SELECT text FROM zeile WHERE lower(text) LIKE :m ESCAPE '\\'"), {"m": enthaelt(eingabe.lower())}))

    def test_prozent_und_unterstrich_sind_zeichen(self):
        for weg in (self._orm, self._sql):
            self.assertEqual(weg("100%"), ["Rabatt 100% bis Freitag"])
            self.assertEqual(weg("_"), ["a_b"])
            self.assertEqual(weg("\\"), ["c:\\pfad"])
            self.assertEqual(weg("EURO"), ["1000 Euro"])
