"""KI-Chat Stufe 2: aus Modell-Aktionen werden Vorschlagskarten.

Nachgebaut sind beide Gegenstellen: der Kalender (Bootstrap, Freitext-Regeln)
und das Modell. Geprueft wird, was der Dienst daraus macht: Kurzkennungen
werden aufgeloest, unbekannte verworfen, Tag und Uhrzeit kommen aus den
Regeln und nicht aus dem Modell, und geschrieben wird nichts.
"""
import json
import os
import threading
import unittest
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("JWT_SECRET", "test-secret-nur-fuer-den-testlauf")
os.environ.setdefault("ALLOWED_SUBS", "owner-sub")
os.environ.setdefault("KALENDER_TENANT_SECRET", "test-tenant-geheimnis")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

HEUTE = date.today()
MORGEN = HEUTE + timedelta(days=1)
GESCHRIEBEN: list[tuple[str, str]] = []
MODELL_ANTWORT: dict = {}
MODELL_ANFRAGEN: list[dict] = []
FREI_GEFRAGT: list[str] = []


def _iso(tag: date, uhr: str) -> str:
    return f"{tag.isoformat()}T{uhr}:00"


class Nachbau(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _senden(self, code, rumpf):
        roh = json.dumps(rumpf).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):  # noqa: N802
        pfad = urlparse(self.path).path
        if pfad == "/api/auth/gate-login":
            return self._senden(200, {"ok": True})
        if pfad == "/api/mobile/bootstrap":
            return self._senden(200, {
                "calendars": [{"id": "kal-termine", "name": "Termine"}],
                "events": [
                    {"id": "kino", "calendar_id": "kal-termine", "title": "Kino mit Tim",
                     "start": _iso(HEUTE, "19:00"), "end": _iso(HEUTE, "22:30"), "all_day": False},
                    {"id": "chor::" + MORGEN.isoformat(), "calendar_id": "kal-termine", "title": "Chor",
                     "start": _iso(MORGEN, "18:00"), "end": _iso(MORGEN, "19:00"), "all_day": False,
                     "recurrence_rule": "FREQ=WEEKLY"},
                    {"id": "arbeit-1", "calendar_id": "daytype-arbeit-0000", "title": "Arbeit",
                     "start": _iso(MORGEN, "07:00"), "end": _iso(MORGEN, "16:00"), "all_day": False},
                ],
                "sessions": [{"id": "sess-1", "habit_name": "Gitarre", "status": "accepted",
                              "start": _iso(HEUTE, "16:30"), "end": _iso(HEUTE, "18:00")}],
                "todos": [{"id": "todo-1", "title": "Steuererklaerung", "completed": False,
                           "due_date": "2026-12-10"}],
            })
        if pfad == "/api/schedule/free-slots":
            # Wie das Original: Datum ist Pflicht, Zeiten tragen die Zone.
            tag = parse_qs(urlparse(self.path).query).get("date", [None])[0]
            if not tag:
                return self._senden(422, {"detail": "date fehlt"})
            FREI_GEFRAGT.append(tag)
            return self._senden(200, {"date": tag, "free_slots": [
                {"start": f"{tag}T09:00:00+01:00", "end": f"{tag}T09:45:00+01:00", "minutes": 45},
                {"start": f"{tag}T17:00:00+01:00", "end": f"{tag}T22:00:00+01:00", "minutes": 300},
            ]})
        return self._senden(404, {"detail": "unbekannt"})

    def do_POST(self):  # noqa: N802
        pfad = urlparse(self.path).path
        rumpf = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if pfad == "/v1/chat/completions":
            MODELL_ANFRAGEN.append(rumpf)
            return self._senden(200, {"choices": [{"message": {"content": json.dumps(MODELL_ANTWORT)}}]})
        if pfad == "/api/capture":
            # Ein Bruchteil der echten Regeln, genug fuer die Faelle unten.
            text = rumpf["text"].lower()
            tag = MORGEN.isoformat() if "morgen" in text else (HEUTE.isoformat() if "heute" in text else None)
            uhr = "15:00" if "15 uhr" in text else None
            dauer = 120 if "2 stunden" in text else (60 if "1h" in text else None)
            vorschlaege = []
            if dauer and not uhr:
                vorschlaege = [{"date": tag or HEUTE.isoformat(), "start_time": s, "end_time": e}
                               for s, e in (("09:00", "11:00"), ("14:00", "16:00"), ("19:00", "21:00"))]
            return self._senden(200, {"type": "event", "title": "", "date": tag, "start_time": uhr,
                                      "end_time": None, "dauer_min": dauer, "vorschlaege": vorschlaege})
        GESCHRIEBEN.append(("POST", pfad))
        return self._senden(200, {"ok": True})

    def do_PUT(self):  # noqa: N802
        GESCHRIEBEN.append(("PUT", urlparse(self.path).path))
        return self._senden(200, {})

    def do_DELETE(self):  # noqa: N802
        GESCHRIEBEN.append(("DELETE", urlparse(self.path).path))
        self.send_response(204)
        self.end_headers()


def _jwt() -> str:
    import time
    from app.config import settings
    return jwt.encode({"iss": "saganta", "sub": "owner-sub", "aud": "kalender-bff", "email": "t@t.de",
                       "iat": int(time.time()), "exp": int(time.time()) + 300},
                      settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _aktion(art, ausschnitt="", titel=None, ziel_id=None, umfang=None, typ=None):
    return {"art": art, "ausschnitt": ausschnitt, "titel": titel, "ziel_id": ziel_id,
            "umfang": umfang, "typ": typ}


class AssistentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Nachbau)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        basis = f"http://127.0.0.1:{cls.server.server_port}"
        from app.config import settings
        cls.settings = settings
        cls.alt = (settings.kalender_base_url, settings.llm_gateway_url, settings.llm_model)
        settings.kalender_base_url = basis
        settings.llm_gateway_url = basis
        settings.llm_model = "homelab-smart"
        from app.main import app
        cls.klient = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.settings.kalender_base_url, cls.settings.llm_gateway_url, cls.settings.llm_model = cls.alt
        cls.server.shutdown()

    def setUp(self):
        GESCHRIEBEN.clear()
        MODELL_ANFRAGEN.clear()
        FREI_GEFRAGT.clear()

    # ── Freie Zeit (2026-11-03): der Planer rechnet, nicht das Modell ──────
    def test_freie_zeit_kommt_vom_planer_und_ersetzt_den_satz_des_modells(self):
        antwort = self._fragen({
            "antwort": "Du hast Dienstag 00:00 bis 23:00 frei.",
            "aktionen": [_aktion("freie_zeit", "morgen")],
        })
        self.assertEqual(FREI_GEFRAGT, [MORGEN.isoformat()])
        self.assertNotIn("00:00", antwort["antwort"])
        self.assertIn("09:00-09:45, 17:00-22:00 (5 h 45 min)", antwort["antwort"])
        self.assertEqual(antwort["karten"], [])
        self.assertEqual(GESCHRIEBEN, [])

    def test_mit_dauer_nur_bloecke_in_die_sie_passt(self):
        antwort = self._fragen({"antwort": "", "aktionen": [_aktion("freie_zeit", "morgen 2 Stunden")]})
        self.assertIn("2 h am Stück", antwort["antwort"])
        self.assertIn("17:00-22:00", antwort["antwort"])
        self.assertNotIn("09:00", antwort["antwort"])

    def test_ohne_zeitraum_sieben_tage(self):
        self._fragen({"antwort": "", "aktionen": [_aktion("freie_zeit", "wann hab ich Zeit")]})
        # Sortiert: die sieben Abfragen laufen parallel, ihre Reihenfolge ist zufaellig.
        self.assertEqual(sorted(FREI_GEFRAGT), [(HEUTE + timedelta(days=i)).isoformat() for i in range(7)])

    def test_kontext_aendert_sich_mit_der_uhrzeit_nur_in_der_letzten_zeile(self):
        """Daran haengt der Prompt-Cache des Modellwirts (CPU, 15 Tok/s)."""
        from app.routes_assistent import kontext_bauen
        daten = {"events": [
            {"id": "a", "calendar_id": "k", "title": "Kino", "start": _iso(HEUTE, "19:00"), "end": _iso(HEUTE, "22:00")},
            {"id": "b", "calendar_id": "k", "title": "Fern", "start": _iso(HEUTE + timedelta(days=20), "10:00"),
             "end": _iso(HEUTE + timedelta(days=20), "11:00")},
        ], "sessions": [], "todos": [{"id": "t", "title": "Steuer", "completed": False, "due_date": "2026-12-10"}]}
        frueh, zuordnung = kontext_bauen(daten, HEUTE, "08:00")
        spaet, _ = kontext_bauen(daten, HEUTE, "21:15")
        self.assertEqual(frueh.splitlines()[:-1], spaet.splitlines()[:-1])
        self.assertIn("jetzt 21:15", spaet.splitlines()[-1])
        self.assertIn("- e-1 19:00-22:00 Kino", frueh)
        self.assertIn("heute " + HEUTE.strftime("%d.%m.") + ":", frueh)
        self.assertIn("(fällig 10.12.)", frueh)
        # Jenseits von 14 Tagen steht nichts im Kontext und keine Kennung bereit.
        self.assertNotIn("Fern", frueh)
        self.assertEqual(set(zuordnung), {"e-1", "t-1"})

    def test_frage_nach_freier_zeit_wird_auch_ohne_das_modell_erkannt(self):
        """Gemessen 04.11.: das Modell nannte bei „was ist am Wochenende frei?"
        selbst Zeiten. Die Regel ersetzt dann seine Antwort durch die Rechnung."""
        antwort = self._fragen(
            {"antwort": "Am Wochenende ist von 00:00 bis 10:00 frei.", "aktionen": [_aktion("frage", "")]},
            nachricht="was ist am Wochenende frei?",
        )
        self.assertNotIn("00:00", antwort["antwort"])
        self.assertTrue(antwort["antwort"].startswith("Freie Zeit"))
        self.assertTrue(FREI_GEFRAGT)

    def test_regel_ueberstimmt_keine_echte_aktion(self):
        antwort = self._fragen(
            {"antwort": "", "aktionen": [_aktion("tagestyp_setzen", "Freitag frei", typ="frei")]},
            nachricht="ich habe Freitag frei",
        )
        self.assertEqual([k["art"] for k in antwort["karten"]], ["tagestyp_setzen"])
        self.assertEqual(FREI_GEFRAGT, [])

    def test_erkennung_freier_zeit(self):
        from app.routes_assistent import fragt_nach_freier_zeit
        for ja in ("wann habe ich diese Woche Zeit?", "was ist am Wochenende frei?",
                   "hab ich morgen 2 Stunden für Sport?", "wie viel Zeit habe ich heute noch?",
                   "ist Freitag Nachmittag frei?"):
            self.assertTrue(fragt_nach_freier_zeit(ja), ja)
        for nein in ("morgen 15 Uhr Friseur", "plane morgen 2 Stunden Zeit für Steuer ein",
                     "Steuer ist erledigt", "wann ist der Zahnarzt?", "schieb Lernen auf eine freie Zeit"):
            self.assertFalse(fragt_nach_freier_zeit(nein), nein)

    def test_zeitraum_regeln_fuer_jeden_wochentag(self):
        from app.routes_assistent import zeitraum_lesen
        montag = date(2026, 11, 2)
        for i in range(7):
            heute = montag + timedelta(days=i)
            we = zeitraum_lesen("am Wochenende", heute, None)
            self.assertTrue(all(t.weekday() >= 5 for t in we), heute)
            self.assertTrue(all(t >= heute for t in we))
            self.assertLessEqual((we[0] - heute).days, 5)
            naechstes = zeitraum_lesen("nächstes Wochenende", heute, None)
            self.assertEqual(naechstes[0].weekday(), 5, heute)
            self.assertTrue(1 <= (naechstes[0] - heute).days <= 7, heute)
            woche = zeitraum_lesen("diese Woche", heute, None)
            self.assertEqual((woche[0], woche[-1].weekday()), (heute, 6))
            naechste = zeitraum_lesen("nächste Woche", heute, None)
            self.assertEqual((naechste[0].weekday(), len(naechste)), (0, 7))
            self.assertGreater(naechste[0], heute)
        self.assertEqual(zeitraum_lesen("Freitag", montag, "2026-11-06"), [date(2026, 11, 6)])

    def _fragen(self, antwort: dict, nachricht="x", verlauf=None):
        MODELL_ANTWORT.clear()
        MODELL_ANTWORT.update(antwort)
        r = self.klient.post("/api/assistent", json={"nachricht": nachricht, "verlauf": verlauf or []},
                             headers={"Authorization": f"Bearer {_jwt()}"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_termin_ohne_uhrzeit_bekommt_drei_freie_zeiten_vom_planer(self):
        a = self._fragen({"antwort": "Mache ich.", "aktionen": [
            _aktion("termin_anlegen", "morgen 2 Stunden Steuer", titel="Steuer")]})
        karte = a["karten"][0]
        self.assertEqual(len(karte["optionen"]), 3)
        termin = karte["optionen"][1]["daten"]["termin"]
        self.assertEqual(termin["start"], _iso(MORGEN, "14:00"))
        self.assertEqual(termin["calendar_id"], "kal-termine")
        self.assertEqual(GESCHRIEBEN, [], "der Assistent darf nichts schreiben")

    def test_kurzkennung_wird_aufgeloest_und_serie_fragt_nur_diesen(self):
        a = self._fragen({"antwort": "ok", "aktionen": [_aktion("termin_loeschen", "Chor faellt aus", ziel_id="e-2")]})
        daten = a["karten"][0]["optionen"][0]["daten"]
        self.assertEqual(daten, {"termin_id": "chor::" + MORGEN.isoformat(), "umfang": "dieser"})

    def test_unbekannte_kennung_wird_verworfen(self):
        a = self._fragen({"antwort": "ok", "aktionen": [_aktion("termin_loeschen", "weg damit", ziel_id="e-99")]})
        self.assertEqual(a["karten"], [])
        self.assertIn("e-99", a["verworfen"][0]["grund"])

    def test_tagestyp_ereignisse_stehen_nicht_im_kontext(self):
        self._fragen({"antwort": "ok", "aktionen": []})
        kontext = MODELL_ANFRAGEN[0]["messages"][-1]["content"]
        self.assertIn("Kino mit Tim", kontext)
        self.assertNotIn("Arbeit", kontext)
        self.assertNotIn("kino", kontext.replace("Kino", ""), "echte Kennungen gehoeren nicht ins Modell")

    def test_verschieben_behaelt_die_dauer(self):
        a = self._fragen({"antwort": "ok", "aktionen": [
            _aktion("termin_aendern", "Kino morgen 15 Uhr", ziel_id="e-1")]})
        termin = a["karten"][0]["optionen"][0]["daten"]["termin"]
        self.assertEqual((termin["start"], termin["end"]), (_iso(MORGEN, "15:00"), _iso(MORGEN, "18:30")))

    def test_sitzung_und_aufgabe(self):
        a = self._fragen({"antwort": "ok", "aktionen": [
            _aktion("sitzung_verschieben", "Gitarre auf morgen", ziel_id="s-1"),
            _aktion("aufgabe_erledigt", "Steuer ist fertig", ziel_id="t-1")]})
        self.assertEqual(a["karten"][0]["optionen"][0]["daten"], {"sitzung_id": "sess-1", "aktion": "dismissed"})
        self.assertEqual(a["karten"][1]["optionen"][0]["daten"], {"aufgabe_id": "todo-1"})
        self.assertEqual([k["id"] for k in a["karten"]], ["k1", "k2"])

    def test_krank_morgen_traegt_hinweis_auf_den_wecker(self):
        a = self._fragen({"antwort": "Gute Besserung.", "aktionen": [
            _aktion("tagestyp_setzen", "morgen krank", typ="krank")]})
        karte = a["karten"][0]
        self.assertEqual(karte["optionen"][0]["daten"], {"von": MORGEN.isoformat(), "bis": MORGEN.isoformat(), "typ": "krank"})
        self.assertIn("Wecker", karte["hinweis"])

    def test_verlauf_geht_mit_und_reasoning_effort_auch(self):
        self._fragen({"antwort": "ok", "aktionen": []}, nachricht="lieber 15 Uhr",
                     verlauf=[{"rolle": "nutzer", "text": "morgen Steuer"}, {"rolle": "assistent", "text": "Wann?"}])
        anfrage = MODELL_ANFRAGEN[0]
        self.assertEqual([m["role"] for m in anfrage["messages"]], ["system", "user", "assistant", "user"])
        self.assertEqual(anfrage["reasoning_effort"], "low")
        self.assertEqual(anfrage["model"], "homelab-smart")

    def test_fremdes_modell_wird_nicht_gefragt(self):
        self.settings.llm_model = "homelab-large"
        try:
            r = self.klient.post("/api/assistent", json={"nachricht": "x"},
                                 headers={"Authorization": f"Bearer {_jwt()}"})
            self.assertEqual(r.status_code, 503)
            self.assertEqual(MODELL_ANFRAGEN, [])
        finally:
            self.settings.llm_model = "homelab-smart"


if __name__ == "__main__":
    unittest.main()
