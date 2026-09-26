"""Routen-Tests des BFF gegen einen nachgebauten Kalender.

**Warum das hier fehlte und warum es zaehlt.** Der BFF hatte 44 Routen und
genau einen Test, den fuer die HMAC-Signatur. Die Routen selbst waren
ungetestet, und das ist nicht theoretisch geblieben: ``/api/mobile/bootstrap``
reichte einen Parameter ``date`` durch, den es stromaufwaerts nie gab (der
native Dienst verlangt ``start`` UND ``end``). Die Route antwortete deshalb
**immer** 422, vom Tag ihrer Entstehung an, unbemerkt, weil sie fuer einen
noch nicht vollzogenen Umstieg vorgebaut und nie aufgerufen wurde.

**Der Kalender wird nachgebaut, nicht gemockt.** Ein Mock haette genau die
Fehlerklasse verdeckt, um die es geht: welche Parameter kommen tatsaechlich
stromaufwaerts an. Der Doppelgaenger hier verlangt dieselben Pflichtparameter
wie das Original und meldet fehlende mit 422, damit faellt ein erfundener
Parameter im Test auf und nicht im Betrieb.

Lauf: ``python -m pytest tests/ -q`` (oder ``python -m unittest discover -s tests``).
"""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# Vor dem App-Import setzen: config.py liest beim Import und bricht bei
# unsicheren Vorgabe-Geheimnissen ab.
os.environ.setdefault("JWT_SECRET", "test-secret-nur-fuer-den-testlauf")
os.environ.setdefault("ALLOWED_SUBS", "owner-sub")
os.environ.setdefault("KALENDER_OWNER_SUB", "owner-sub")
os.environ.setdefault("KALENDER_FEED_TOKEN", "test-feed-token")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402


GESEHEN: list[tuple[str, str, dict]] = []      # (Methode, Pfad, Abfrageparameter)


class NachbauHandler(BaseHTTPRequestHandler):
    """Spiegelt die Vertragsseite des nativen Kalenders, die der BFF benutzt."""

    def log_message(self, *_):
        pass

    def _senden(self, code: int, rumpf):
        roh = json.dumps(rumpf).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def _pflicht(self, abfrage: dict, felder: tuple[str, ...]) -> bool:
        """422 bei fehlendem Pflichtparameter, wie FastAPI stromaufwaerts."""
        fehlend = [f for f in felder if f not in abfrage]
        if fehlend:
            self._senden(422, {"detail": [
                {"type": "missing", "loc": ["query", f], "msg": "Field required"}
                for f in fehlend]})
            return False
        return True

    def do_DELETE(self):  # noqa: N802
        zerlegt = urlparse(self.path)
        GESEHEN.append(("DELETE", zerlegt.path, {}))
        self.send_response(204); self.end_headers()

    def do_GET(self):  # noqa: N802
        zerlegt = urlparse(self.path)
        abfrage = {k: v[0] for k, v in parse_qs(zerlegt.query).items()}
        GESEHEN.append(("GET", zerlegt.path, abfrage))

        if zerlegt.path == "/api/auth/token-login":
            return self._senden(200, {"ok": True})
        if zerlegt.path == "/api/mobile/bootstrap":
            if not self._pflicht(abfrage, ("start", "end")):
                return
            return self._senden(200, {"range": abfrage, "events": [], "todos": [],
                                      "habits": [], "sessions": []})
        if zerlegt.path == "/api/events":
            if not self._pflicht(abfrage, ("start", "end")):
                return
            return self._senden(200, [{"id": "e1", "title": "Termin",
                                       "start_at": "2026-08-25T09:00:00"}])
        if zerlegt.path == "/api/habits/weekly-progress":
            return self._senden(200, [{"habit_id": "h1", "name": "Lernen",
                                       "target_hours": 6.0, "completed_hours": 2.0}])
        if zerlegt.path == "/api/habits/sessions/today":
            return self._senden(200, [{"id": "s1", "status": "pending"}])
        if zerlegt.path == "/api/habits/sessions/upcoming":
            return self._senden(200, [])
        if zerlegt.path == "/api/todos":
            return self._senden(200, [])
        if zerlegt.path == "/api/feed-token":
            return self._senden(200, {"feed_token": "geheim-des-owners"})
        if zerlegt.path == "/api/tagesdecke":
            if not self._pflicht(abfrage, ("datum",)):
                return
            return self._senden(200, {
                "datum": abfrage["datum"], "wach_minuten": 960,
                "verplant_minuten": 960, "offen_minuten": 0,
                "bloecke": [{"id": "b1", "art": "erholung", "titel": "Freie Zeit"}],
            })
        if zerlegt.path == "/api/tagesdecke/arten":
            return self._senden(200, {"arten": [
                {"schluessel": "fix", "name": "Termin", "gespiegelt": True},
                {"schluessel": "erholung", "name": "Erholung", "gespiegelt": False},
            ]})
        if zerlegt.path == "/api/tagesdecke/abgleich":
            if not self._pflicht(abfrage, ("datum",)):
                return
            return self._senden(200, {"datum": abfrage["datum"], "hat_messungen": False})
        if zerlegt.path == "/api/tagesdecke/rueckblick":
            if not self._pflicht(abfrage, ("von", "bis")):
                return
            return self._senden(200, {"von": abfrage["von"], "bis": abfrage["bis"], "tage": 1})
        return self._senden(404, {"detail": "unbekannt"})

    def do_PATCH(self):  # noqa: N802
        zerlegt = urlparse(self.path)
        laenge = int(self.headers.get("Content-Length", 0))
        rumpf = json.loads(self.rfile.read(laenge) or b"{}")
        GESEHEN.append(("PATCH", zerlegt.path, rumpf))
        return self._senden(200, {"id": zerlegt.path.rsplit("/", 1)[-1], **rumpf})

    def do_PUT(self):  # noqa: N802
        zerlegt = urlparse(self.path)
        laenge = int(self.headers.get("Content-Length", 0))
        rumpf = json.loads(self.rfile.read(laenge) or b"{}")
        GESEHEN.append(("PUT", zerlegt.path, rumpf))
        return self._senden(200, {"id": zerlegt.path.rsplit("/", 1)[-1], **rumpf})

    def do_POST(self):  # noqa: N802
        zerlegt = urlparse(self.path)
        laenge = int(self.headers.get("Content-Length", 0))
        rumpf = json.loads(self.rfile.read(laenge) or b"{}")
        GESEHEN.append(("POST", zerlegt.path, rumpf))
        if zerlegt.path.startswith("/api/habits/sessions/"):
            return self._senden(200, {"ok": True, "action": rumpf.get("action")})
        if zerlegt.path.endswith("/truncate"):
            # Der native Dienst antwortet 204 ohne Rumpf.
            self.send_response(204); self.end_headers(); return
        return self._senden(200, {"ok": True})


def _jwt(sub: str = "owner-sub", aud: str = "kalender-bff", iss: str = "saganta") -> str:
    import time
    from app.config import settings
    return jwt.encode({"iss": iss, "sub": sub, "aud": aud, "email": "t@t.de",
                       "iat": int(time.time()), "exp": int(time.time()) + 300},
                      settings.jwt_secret, algorithm=settings.jwt_algorithm)


class BffRoutenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), NachbauHandler)
        cls.faden = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.faden.start()
        os.environ["KALENDER_BASE_URL"] = f"http://127.0.0.1:{cls.server.server_port}"

        from app.config import settings
        settings.kalender_base_url = os.environ["KALENDER_BASE_URL"]
        from app.main import app
        cls.klient = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        GESEHEN.clear()
        self.kopf = {"Authorization": f"Bearer {_jwt()}"}

    def _abfrage_an(self, pfad: str) -> dict:
        for methode, p, daten in GESEHEN:
            if p == pfad:
                return daten
        self.fail(f"Kein Aufruf an {pfad}. Gesehen: {[(m, p) for m, p, _ in GESEHEN]}")

    # ── Der Fehler, der diese Datei ausgeloest hat ────────────────────────
    def test_bootstrap_reicht_start_und_ende_durch(self):
        """★★ Regression: die Route schickte ``date`` statt ``start``/``end``.

        Stromaufwaerts gibt es kein ``date``, die Route antwortete deshalb in
        JEDER Variante 422, mit Parameter wie ohne. Der Test prueft nicht nur
        den Statuscode, sondern **was tatsaechlich stromaufwaerts ankam**: ein
        200 allein waere auch mit einem grosszuegigen Doppelgaenger erreichbar.
        """
        antwort = self.klient.get(
            "/api/mobile/bootstrap?start=2026-08-25&end=2026-08-31", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)
        angekommen = self._abfrage_an("/api/mobile/bootstrap")
        self.assertEqual(angekommen, {"start": "2026-08-25", "end": "2026-08-31"})
        self.assertNotIn("date", angekommen)

    def test_bootstrap_ohne_parameter_ist_422(self):
        self.assertEqual(
            self.klient.get("/api/mobile/bootstrap", headers=self.kopf).status_code, 422)

    def test_bootstrap_verdrehter_zeitraum_wird_hier_abgefangen(self):
        antwort = self.klient.get(
            "/api/mobile/bootstrap?start=2026-08-31&end=2026-08-24", headers=self.kopf)
        self.assertEqual(antwort.status_code, 400)
        self.assertEqual(GESEHEN, [], "Der Fehler haette den Kalender nicht erreichen duerfen")

    def test_bootstrap_zu_grosser_zeitraum_wird_hier_abgefangen(self):
        antwort = self.klient.get(
            "/api/mobile/bootstrap?start=2026-01-01&end=2026-12-31", headers=self.kopf)
        self.assertEqual(antwort.status_code, 400)
        self.assertIn("120", antwort.json()["detail"])

    def test_bootstrap_unmoegliches_datum(self):
        antwort = self.klient.get(
            "/api/mobile/bootstrap?start=2026-02-30&end=2026-03-01", headers=self.kopf)
        self.assertEqual(antwort.status_code, 400)

    # ── Auth-Riegel ───────────────────────────────────────────────────────
    def test_ohne_token_kein_zugriff(self):
        # 401, nicht 422. Bis zum 02.09.2026 stand hier 422, weil dieser Dienst
        # den Authorization-Kopf als Pflichtfeld deklarierte (`Header(...)`) und
        # FastAPI ein fehlendes Pflichtfeld als Validierungsfehler meldet. Zwei
        # der acht Backends machten es schon damals richtig; der Unterschied war
        # niemandem aufgefallen, weil jeder Dienst seine eigene Kopie der
        # Auth-Grenze hatte. Seit die Pruefung geteilt ist, antworten alle acht
        # gleich: fehlender Kopf ist keine kaputte Anfrage, sondern eine
        # unangemeldete.
        self.assertEqual(self.klient.get("/api/todos").status_code, 401)

    def test_falsche_audience_wird_abgelehnt(self):
        antwort = self.klient.get(
            "/api/todos", headers={"Authorization": f"Bearer {_jwt(aud='news-api')}"})
        self.assertEqual(antwort.status_code, 401)

    def test_fremder_aussteller_wird_abgelehnt(self):
        antwort = self.klient.get(
            "/api/todos", headers={"Authorization": f"Bearer {_jwt(iss='woanders')}"})
        self.assertEqual(antwort.status_code, 401)

    def test_fremder_sub_wird_abgelehnt(self):
        """Owner-Gate: der Kalender ist nicht nutzer-isoliert, also darf nur der
        freigeschaltete ``sub`` durch."""
        antwort = self.klient.get(
            "/api/todos", headers={"Authorization": f"Bearer {_jwt(sub='fremder')}"})
        self.assertEqual(antwort.status_code, 403)

    def test_feed_token_nur_fuer_den_owner(self):
        """★ Wer den Feed-Token hat, ist Owner des Kalenders, er oeffnet ueber
        ``token-login`` alles. Der eigene Riegel muss unabhaengig vom Owner-Gate
        greifen, sonst waere er eine Mine fuer den ersten Fremdnutzer."""
        from app.config import settings
        alt = settings.allowed_subs
        settings.allowed_subs = ["owner-sub", "gast-sub"]
        try:
            antwort = self.klient.get(
                "/api/feed-token", headers={"Authorization": f"Bearer {_jwt(sub='gast-sub')}"})
            self.assertEqual(antwort.status_code, 403)
            self.assertEqual(
                self.klient.get("/api/feed-token", headers=self.kopf).status_code, 200)
        finally:
            settings.allowed_subs = alt

    # ── Gewohnheiten (Frontend haengt jetzt daran) ─────────────────────────
    def test_wochenfortschritt(self):
        antwort = self.klient.get("/api/habits/weekly-progress", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(antwort.json()[0]["name"], "Lernen")

    def test_sitzungsaktion_reicht_die_aktion_durch(self):
        antwort = self.klient.post("/api/habits/sessions/s1/action",
                                   json={"action": "dismissed"}, headers=self.kopf)
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self._abfrage_an("/api/habits/sessions/s1/action"),
                         {"action": "dismissed"})

    def test_unbekannte_sitzungsaktion_scheitert_hier(self):
        """422 im BFF statt eines weitergereichten Upstream-Fehlers, dessen
        Ursache im Aufrufer liegt."""
        antwort = self.klient.post("/api/habits/sessions/s1/action",
                                   json={"action": "vielleicht"}, headers=self.kopf)
        self.assertEqual(antwort.status_code, 422)
        self.assertEqual(GESEHEN, [])

    # ── Termine ───────────────────────────────────────────────────────────
    def test_range_setzt_das_fenster_stromaufwaerts(self):
        """Ohne Fenster expandiert der native Dienst keine Serien, dann fehlten
        genau die wiederkehrenden Termine."""
        antwort = self.klient.get(
            "/api/events/range?start=2026-08-25&end=2026-08-31", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200)
        angekommen = self._abfrage_an("/api/events")
        self.assertEqual(angekommen["start"], "2026-08-25")
        self.assertTrue(angekommen["end"].startswith("2026-08-31"))

    # ── Serien: einzelnes Vorkommen / ab Datum beenden ────────────────────
    def test_einzelnes_vorkommen_absagen(self):
        antwort = self.klient.delete(
            "/api/events/serie-1/instances/2026-08-26", headers=self.kopf)
        self.assertEqual(antwort.status_code, 204, antwort.text)
        pfade = [p for m, p, _ in GESEHEN if m == "DELETE"]
        self.assertIn("/api/events/serie-1/instances/2026-08-26", pfade)

    def test_instanz_id_darf_mitkommen(self):
        """Der Client hat oft nur die Instanz-ID (``basis::datum``) zur Hand:
        der native Dienst löst sie selbst auf."""
        antwort = self.klient.delete(
            "/api/events/serie-1::2026-08-26/instances/2026-08-26", headers=self.kopf)
        self.assertEqual(antwort.status_code, 204, antwort.text)

    def test_unsinniges_datum_erreicht_den_kalender_nicht(self):
        for murks in ("26-08-2026", "morgen", "2026-8-6"):
            with self.subTest(murks=murks):
                antwort = self.klient.delete(
                    f"/api/events/serie-1/instances/{murks}", headers=self.kopf)
                self.assertEqual(antwort.status_code, 422)
        self.assertEqual(GESEHEN, [])

    def test_serie_ab_datum_beenden(self):
        antwort = self.klient.post(
            "/api/events/serie-1/truncate?occ_date=2026-09-01", headers=self.kopf)
        self.assertEqual(antwort.status_code, 204, antwort.text)
        pfade = [p for m, p, _ in GESEHEN if m == "POST"]
        self.assertIn("/api/events/serie-1/truncate", pfade)

    def test_truncate_ohne_datum_scheitert(self):
        self.assertEqual(
            self.klient.post("/api/events/serie-1/truncate", headers=self.kopf).status_code,
            422)

    def test_tagestyp_nur_erlaubte_werte(self):
        """⚠️ Aus diesem Wert folgt die Weckzeit. Ein Tippfehler soll hier
        scheitern und nicht als unbekannter Typ im Kalender landen."""
        gut = self.klient.post("/api/day-type/set",
                               json={"date": "2026-08-25", "day_type": "arbeit"},
                               headers=self.kopf)
        self.assertEqual(gut.status_code, 200)
        schlecht = self.klient.post("/api/day-type/set",
                                    json={"date": "2026-08-25", "day_type": "arbait"},
                                    headers=self.kopf)
        self.assertEqual(schlecht.status_code, 422)

    def test_health_braucht_keine_anmeldung(self):
        for pfad in ("/health", "/healthz", "/health/ready"):
            self.assertEqual(self.klient.get(pfad).status_code, 200, pfad)

    # ── Aufgaben: die drei Luecken vom 2026-09-13 ────────────────────────
    #
    # Alle drei fielen auf, als die Aufgaben-App aus dem Kalender ausgelagert
    # wurde. Keine davon hat je einen Fehler gemeldet.

    def test_leeren_eines_feldes_kommt_als_null_an(self):
        """★★ Regression: mit ``exclude_none`` liess sich ein Feld NIE leeren.

        Wer ein Faelligkeitsdatum entfernen wollte, schickte ``due_date: null``,
        der BFF liess es weg, der native Kalender sah kein Feld und behielt den
        alten Wert. Die Oberflaeche meldete Erfolg, das Datum blieb stehen.
        """
        antwort = self.klient.put(
            "/api/todos/t1", json={"title": "Neu", "due_date": None}, headers=self.kopf
        )
        self.assertEqual(antwort.status_code, 200, antwort.text)
        hoch = self._abfrage_an("/api/todos/t1")
        self.assertIn("due_date", hoch, "due_date wurde verschluckt statt geleert")
        self.assertIsNone(hoch["due_date"])

    def test_nicht_geschicktes_feld_bleibt_weg(self):
        """Die Gegenprobe: ``exclude_unset`` darf nicht alles durchreichen.

        Ein Feld, das der Aufrufer gar nicht genannt hat, soll unangetastet
        bleiben und nicht als ``null`` hochwandern, sonst leert jedes Speichern
        alles, was das Formular nicht kennt.
        """
        self.klient.put("/api/todos/t2", json={"title": "Nur Titel"}, headers=self.kopf)
        hoch = self._abfrage_an("/api/todos/t2")
        self.assertEqual(hoch, {"title": "Nur Titel"})

    def test_energiebedarf_ist_englisch(self):
        """⚠️ Der Sprachmix des Bestands: ``priority`` deutsch, ``energy`` englisch.

        Ein deutscher Wert soll hier scheitern und nicht oben als 422 ohne
        erkennbaren Bezug.
        """
        gut = self.klient.put(
            "/api/todos/t3", json={"energy_required": "high"}, headers=self.kopf
        )
        self.assertEqual(gut.status_code, 200, gut.text)
        schlecht = self.klient.put(
            "/api/todos/t4", json={"energy_required": "hoch"}, headers=self.kopf
        )
        self.assertEqual(schlecht.status_code, 422)

    def test_aufschieben_geht_ueber_planned_date(self):
        """★ Die Route fehlte ganz, obwohl die Engine sie seit jeher hat.

        ⚠️ Der native Endpunkt kennt kein ``due_date``. Wer es schickt, bekommt
        keinen Fehler, sondern eine Aufgabe im Pool: „auf morgen verschoben"
        hiesse in Wahrheit „ins Unbestimmte".
        """
        antwort = self.klient.post(
            "/api/todos/t5/defer",
            json={"planned_date": "2026-09-14", "reason": "heute keine Zeit"},
            headers=self.kopf,
        )
        self.assertEqual(antwort.status_code, 200, antwort.text)
        hoch = self._abfrage_an("/api/todos/t5/defer")
        self.assertEqual(hoch["planned_date"], "2026-09-14")
        self.assertNotIn("due_date", hoch)

    def test_aufschieben_weist_ein_unsinniges_datum_ab(self):
        antwort = self.klient.post(
            "/api/todos/t6/defer", json={"planned_date": "morgen"}, headers=self.kopf
        )
        self.assertEqual(antwort.status_code, 422)

    def test_aufschieben_ohne_datum_ist_erlaubt(self):
        """Ohne Tag geht die Aufgabe zurueck in den Pool. Das ist ein Weg, kein Fehler."""
        antwort = self.klient.post("/api/todos/t7/defer", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)

    def test_aufgaben_routen_brauchen_eine_anmeldung(self):
        for methode, pfad, rumpf in (
            ("put", "/api/todos/t1", {"title": "x"}),
            ("post", "/api/todos/t1/defer", {}),
        ):
            antwort = getattr(self.klient, methode)(pfad, json=rumpf)
            self.assertIn(antwort.status_code, (401, 403), f"{methode} {pfad}")

    # ── Tagesdecke ────────────────────────────────────────────────────────
    def test_decke_reicht_das_datum_durch(self):
        antwort = self.klient.get("/api/tagesdecke?datum=2026-09-16", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)
        self.assertEqual(self._abfrage_an("/api/tagesdecke"), {"datum": "2026-09-16"})

    def test_decke_ohne_datum_ist_422(self):
        self.assertEqual(
            self.klient.get("/api/tagesdecke", headers=self.kopf).status_code, 422)

    def test_decke_lehnt_unsinniges_datum_hier_ab(self):
        """Das Muster faengt es, bevor es den Kalender erreicht."""
        antwort = self.klient.get("/api/tagesdecke?datum=16.09.2026", headers=self.kopf)
        self.assertEqual(antwort.status_code, 422)
        self.assertEqual(GESEHEN, [], "Haette den Kalender nicht erreichen duerfen")

    def test_arten_nennen_die_gespiegelten(self):
        antwort = self.klient.get("/api/tagesdecke/arten", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)
        arten = {a["schluessel"]: a for a in antwort.json()["arten"]}
        self.assertTrue(arten["fix"]["gespiegelt"])

    def test_block_verschieben_reicht_nur_gesetzte_felder_durch(self):
        """★ `exclude_none` heisst hier „nicht anfassen", nicht „leeren".

        Bei diesem Modell ist das richtig, weil kein Feld sinnvoll leerbar ist.
        Der Test haelt fest, dass nicht gesetzte Felder auch nicht als `null`
        stromaufwaerts landen: dort wuerden sie sonst als Aenderung gelesen.
        """
        antwort = self.klient.patch(
            "/api/tagesdecke/block/b1",
            json={"start": "2026-09-16T20:00:00", "ende": "2026-09-16T21:00:00"},
            headers=self.kopf,
        )
        self.assertEqual(antwort.status_code, 200, antwort.text)
        angekommen = self._abfrage_an("/api/tagesdecke/block/b1")
        self.assertEqual(set(angekommen), {"start", "ende"})
        self.assertNotIn("titel", angekommen)

    def test_block_verschieben_ohne_aenderung_ist_400(self):
        antwort = self.klient.patch(
            "/api/tagesdecke/block/b1", json={}, headers=self.kopf)
        self.assertEqual(antwort.status_code, 400)
        self.assertEqual(GESEHEN, [])

    def test_block_mit_unbekannter_art_wird_hier_abgefangen(self):
        antwort = self.klient.patch(
            "/api/tagesdecke/block/b1", json={"art": "unfug"}, headers=self.kopf)
        self.assertEqual(antwort.status_code, 422)
        self.assertEqual(GESEHEN, [])

    def test_block_verwerfen_ist_kein_loeschen(self):
        """Vorgabe ist `endgueltig=false`: Verworfenes bleibt das Lernsignal."""
        antwort = self.klient.delete("/api/tagesdecke/block/b1", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)

    def test_rueckblick_reicht_beide_grenzen_durch(self):
        antwort = self.klient.get(
            "/api/tagesdecke/rueckblick?von=2026-09-01&bis=2026-09-16", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)
        self.assertEqual(
            self._abfrage_an("/api/tagesdecke/rueckblick"),
            {"von": "2026-09-01", "bis": "2026-09-16"},
        )

    def test_zeit_eingang_ist_hier_nicht_erreichbar(self):
        """★ Der Messgeraet-Eingang wird bewusst NICHT gespiegelt.

        Er traegt einen eigenen Token und ist fuer ein Geraet gedacht. Ihn ueber
        den BFF zu oeffnen hiesse, einen zweiten Weg mit anderer
        Authentifizierung in einen Schreibpfad zu legen, der Bewegungsprofile
        entgegennimmt.
        """
        antwort = self.klient.post(
            "/api/zeit/ingest", json={"eintraege": []}, headers=self.kopf)
        self.assertEqual(antwort.status_code, 404)

    def test_decke_routen_brauchen_eine_anmeldung(self):
        for methode, pfad, rumpf in (
            ("get", "/api/tagesdecke?datum=2026-09-16", None),
            ("get", "/api/tagesdecke/arten", None),
            ("post", "/api/tagesdecke/festschreiben?datum=2026-09-16", None),
            ("patch", "/api/tagesdecke/block/b1", {"titel": "x"}),
            ("delete", "/api/tagesdecke/block/b1", None),
            ("get", "/api/tagesdecke/abgleich?datum=2026-09-16", None),
        ):
            kwargs = {"json": rumpf} if rumpf is not None else {}
            antwort = getattr(self.klient, methode)(pfad, **kwargs)
            self.assertIn(antwort.status_code, (401, 403), f"{methode} {pfad}")


if __name__ == "__main__":
    unittest.main()
