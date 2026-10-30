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
# Ohne Geheimnis antwortet der BFF seit dem 2026-10-16 mit 503, weil die
# Anmeldung am nativen Dienst (`gate-login`) an der Signatur haengt. Vorher
# genuegte KALENDER_FEED_TOKEN, und genau das war der Fehler: dieser Token
# gehoert dem Owner.
os.environ.setdefault("KALENDER_TENANT_SECRET", "test-tenant-geheimnis")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402


GESEHEN: list[tuple[str, str, dict]] = []      # (Methode, Pfad, Abfrageparameter)
#: (Pfad, X-Saganta-Sub, hat_signatur) je Aufruf. Beantwortet die Frage, in
#: wessen Namen der BFF stromaufwaerts gesprochen hat -- bis zum 2026-10-16 war
#: das immer der Owner, egal welcher Mandant anfragte.
MANDANTEN: list[tuple[str, str | None, bool]] = []
#: Laesst die Gateway-Attrappe eine leere Antwort geben. Ein Thinking-Modell
#: tut das bei knappem Token-Budget, und zwar mit HTTP 200.
LEERE_LLM_ANTWORT = False


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
        MANDANTEN.append((
            zerlegt.path,
            self.headers.get("X-Saganta-Sub"),
            bool(self.headers.get("X-Saganta-Sub-Sig")),
        ))

        if zerlegt.path == "/api/auth/gate-login":
            # Der echte Dienst prueft hier die Signatur und stellt eine Sitzung
            # fuer GENAU diesen Mandanten aus. Der Nachbau merkt sich, welchen
            # Mandanten er gesehen hat, damit die Tests unten pruefen koennen,
            # dass es nicht der Owner ist.
            if not self.headers.get("X-Saganta-Sub-Sig"):
                return self._senden(401, {"detail": "Mandant oder Signatur fehlt"})
            return self._senden(200, {"ok": True})
        if zerlegt.path == "/api/auth/token-login":
            # Darf nicht mehr benutzt werden: der Token darin gehoert dem Owner.
            return self._senden(410, {"detail": "token-login ist nicht der BFF-Weg"})
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
        if zerlegt.path == "/api/day-type/urlaub-bilanz":
            if not self._pflicht(abfrage, ("jahr",)):
                return
            return self._senden(200, {"jahr": int(abfrage["jahr"]), "ganze_tage": 3,
                                      "halbe_tage": 1, "verbraucht": 3.5,
                                      "tage": ["2026-07-01"]})
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

    #: Pfad -> Pflicht-QUERY-Parameter des nativen Dienstes bei POST.
    #:
    #: Diese Tabelle fehlte bis zum 2026-10-20, und ihr Fehlen hat genau die
    #: Fehlerklasse durchgelassen, gegen die dieser Nachbau gebaut wurde: ``do_GET``
    #: prueft Pflichtparameter, ``do_POST`` nahm alles an und antwortete 200. Der
    #: BFF schickte ``/api/day-type/set`` mit einem JSON-Rumpf, waehrend der native
    #: Dienst ``date`` und ``type`` im Query verlangt -- stromaufwaerts also 422 bei
    #: jedem Aufruf, hier gruen. Ein Doppelgaenger, der nachsichtiger ist als das
    #: Original, prueft den Vertrag nicht, sondern bestaetigt ihn.
    POST_PFLICHT = {
        "/api/day-type/set": ("date", "type"),
        "/api/day-type/set-range": ("von", "bis", "type"),
    }

    def do_POST(self):  # noqa: N802
        zerlegt = urlparse(self.path)
        abfrage = {k: v[0] for k, v in parse_qs(zerlegt.query).items()}
        laenge = int(self.headers.get("Content-Length", 0))
        rumpf = json.loads(self.rfile.read(laenge) or b"{}")
        # Beides festhalten: bei diesen Routen traegt der Query die Bedeutung.
        GESEHEN.append(("POST", zerlegt.path, rumpf or abfrage))
        if zerlegt.path in self.POST_PFLICHT:
            if not self._pflicht(abfrage, self.POST_PFLICHT[zerlegt.path]):
                return
            if zerlegt.path == "/api/day-type/set":
                return self._senden(200, {"date": abfrage["date"], "type": abfrage["type"]})
            return self._senden(200, {
                "von": abfrage["von"], "bis": abfrage["bis"], "type": abfrage["type"],
                "gesetzt": [abfrage["von"]], "uebersprungen": [], "wochen_neu_geplant": 1,
            })
        if zerlegt.path == "/v1/chat/completions":
            # Steht hier, weil der Chat-Endpunkt ZWEI Gegenstellen hat: den
            # Kalender und das Modell. Ein Nachbau, der nur eine kennt, prueft
            # die Haelfte.
            if LEERE_LLM_ANTWORT:
                return self._senden(200, {"choices": [{"message": {"content": "  "}}]})
            return self._senden(200, {"choices": [{"message": {
                "content": "Am Donnerstag ab 14:00 sind zwei Stunden frei."}}]})
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
        """Regression: die Route schickte ``date`` statt ``start``/``end``.

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

    def test_feed_token_kommt_jetzt_jedem_mandanten_zu(self):
        """Der Owner-Riegel ist am 2026-10-16 entfallen, nicht aufgeweicht.

        Er war noetig, solange der native Endpunkt JEDEM denselben Token gab.
        Seit dem 2026-09-27 hat dort jeder Mandant seinen eigenen; am laufenden
        Dienst belegt (zwei Subs, zwei Token; Gast-Token bekommt auf Ebene 1,
        der Weckkette, 403).
        """
        from app.config import settings
        alt = settings.allowed_subs
        settings.allowed_subs = ["owner-sub", "gast-sub"]
        try:
            for sub in ("owner-sub", "gast-sub"):
                antwort = self.klient.get(
                    "/api/feed-token",
                    headers={"Authorization": f"Bearer {_jwt(sub=sub)}"})
                self.assertEqual(antwort.status_code, 200, f"{sub}: {antwort.text}")
        finally:
            settings.allowed_subs = alt

    def test_upstream_spricht_im_namen_des_anfragenden_mandanten(self):
        """Die eigentliche Zusicherung hinter dem entfallenen Riegel.

        Bis zum 2026-10-16 meldete sich der Upstream-Client per
        ``token-login?token=<Owner-Feed-Token>`` an. Die Sitzung gehoerte damit
        dem Owner, in jedem Aufruf jedes Mandanten, und genau eine native Route
        liest diese Identitaet als Wert statt nur als Schranke: ``feed-token``.
        Gemessen bekam ein fremdes Pruefkonto dort den Token des Owners.

        Geprueft wird deshalb nicht die Antwort, sondern **mit welchem Mandanten
        der BFF stromaufwaerts angemeldet hat**. Eine Zusicherung ueber die
        Antwort allein waere hier blind: der Nachbau liefert ohnehin, was man ihm
        sagt.
        """
        from app.config import settings
        alt = settings.allowed_subs
        settings.allowed_subs = ["owner-sub", "gast-sub"]
        try:
            for sub in ("owner-sub", "gast-sub"):
                MANDANTEN.clear()
                self.klient.get("/api/feed-token",
                                headers={"Authorization": f"Bearer {_jwt(sub=sub)}"})
                anmeldungen = [m for m in MANDANTEN if m[0] == "/api/auth/gate-login"]
                self.assertEqual(len(anmeldungen), 1, MANDANTEN)
                self.assertEqual(anmeldungen[0][1], sub)
                self.assertTrue(anmeldungen[0][2], "Signatur fehlt")
                # Der alte Weg darf nicht mehr vorkommen.
                self.assertEqual(
                    [m for m in MANDANTEN if m[0] == "/api/auth/token-login"], [])
        finally:
            settings.allowed_subs = alt

    def test_ohne_mandanten_geheimnis_kein_upstream_aufruf(self):
        """Fail-closed statt headerlos: headerlos faellt stromaufwaerts auf den Owner."""
        from app.config import settings
        alt = settings.kalender_tenant_secret
        settings.kalender_tenant_secret = ""
        MANDANTEN.clear()
        try:
            antwort = self.klient.get("/api/feed-token", headers=self.kopf)
            self.assertEqual(antwort.status_code, 503, antwort.text)
            self.assertIn("KALENDER_TENANT_SECRET", antwort.text)
            self.assertEqual(MANDANTEN, [])
        finally:
            settings.kalender_tenant_secret = alt

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

    def test_tagestyp_kommt_als_query_an_nicht_als_rumpf(self):
        """Der Regressionstest zum Befund vom 2026-10-20.

        Der native Dienst verlangt ``date`` und ``type`` im Query. Ein JSON-Rumpf
        laesst beide fehlen, und das endet stromaufwaerts in 422 -- hier sichtbar,
        seit der Nachbau bei POST dieselben Pflichtparameter prueft wie bei GET.
        """
        antwort = self.klient.post(
            "/api/day-type/set",
            json={"date": "2026-08-25", "day_type": "arbeit"},
            headers=self.kopf,
        )
        self.assertEqual(antwort.status_code, 200, antwort.text)
        gesehen = [a for m, p, a in GESEHEN if m == "POST" and p == "/api/day-type/set"]
        self.assertTrue(gesehen, "kein Aufruf stromaufwaerts angekommen")
        self.assertEqual(gesehen[-1]["date"], "2026-08-25")
        self.assertEqual(gesehen[-1]["type"], "arbeit")

    def test_zeitraum_wird_als_zeitraum_durchgereicht(self):
        antwort = self.klient.post(
            "/api/day-type/set-range",
            json={"von": "2026-08-24", "bis": "2026-09-04", "day_type": "urlaub"},
            headers=self.kopf,
        )
        self.assertEqual(antwort.status_code, 200, antwort.text)
        gesehen = [a for m, p, a in GESEHEN if p == "/api/day-type/set-range"][-1]
        self.assertEqual(gesehen["von"], "2026-08-24")
        self.assertEqual(gesehen["bis"], "2026-09-04")
        self.assertEqual(gesehen["type"], "urlaub")
        self.assertEqual(gesehen["nur_wochentage"], "true")

    def test_arbeitszeit_eines_tages_kommt_als_query_an(self):
        """Seit 2026-10-30: eigene Uhrzeit je Tag, stromaufwaerts als Query."""
        antwort = self.klient.post(
            "/api/day-type/set",
            json={"date": "2026-08-25", "day_type": "arbeit", "von": "09:30", "bis": "18:00"},
            headers=self.kopf,
        )
        self.assertEqual(antwort.status_code, 200, antwort.text)
        gesehen = [a for m, p, a in GESEHEN if m == "POST" and p == "/api/day-type/set"][-1]
        self.assertEqual((gesehen["von"], gesehen["bis"]), ("09:30", "18:00"))

    def test_ohne_uhrzeit_geht_keine_leere_uhrzeit_mit(self):
        """Ein leeres ``von`` waere stromaufwaerts ein 400; ohne Angabe gilt dort die Vorgabe."""
        self.klient.post("/api/day-type/set",
                         json={"date": "2026-08-25", "day_type": "arbeit"}, headers=self.kopf)
        gesehen = [a for m, p, a in GESEHEN if m == "POST" and p == "/api/day-type/set"][-1]
        self.assertNotIn("von", gesehen)
        self.assertNotIn("bis", gesehen)

    def test_zeitraum_reicht_die_uhrzeit_unter_eigenem_namen_durch(self):
        """``von``/``bis`` sind beim Zeitraum die Daten, die Uhrzeit heisst stromaufwaerts ``von_zeit``."""
        self.klient.post("/api/day-type/set-range", json={
            "von": "2026-08-24", "bis": "2026-08-28", "day_type": "arbeit",
            "von_zeit": "06:00", "bis_zeit": "14:30"}, headers=self.kopf)
        gesehen = [a for m, p, a in GESEHEN if p == "/api/day-type/set-range"][-1]
        self.assertEqual((gesehen["von_zeit"], gesehen["bis_zeit"]), ("06:00", "14:30"))
        self.assertEqual(gesehen["von"], "2026-08-24")

    def test_kaputte_uhrzeit_erreicht_den_kalender_nicht(self):
        vorher = len(GESEHEN)
        antwort = self.klient.post("/api/day-type/set", json={
            "date": "2026-08-25", "day_type": "arbeit", "von": "9 Uhr", "bis": "18:00"},
            headers=self.kopf)
        self.assertEqual(antwort.status_code, 422)
        self.assertEqual(len(GESEHEN), vorher)

    def test_wochenvorgabe_geht_als_rumpf_durch(self):
        antwort = self.klient.put("/api/day-type/arbeitszeiten", json={
            "arbeit": [{"wochentag": 0, "von": "06:00", "bis": "14:30"}]}, headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)
        gesehen = [a for m, p, a in GESEHEN if m == "PUT" and p == "/api/day-type/arbeitszeiten"][-1]
        # Ein fehlender Typ bleibt stromaufwaerts unveraendert, darf also nicht als null mitgehen.
        self.assertEqual(gesehen, {"arbeit": [{"wochentag": 0, "von": "06:00", "bis": "14:30"}]})

    def test_zeitraum_verkehrt_herum_erreicht_den_kalender_nicht(self):
        vorher = len(GESEHEN)
        antwort = self.klient.post(
            "/api/day-type/set-range",
            json={"von": "2026-09-04", "bis": "2026-08-24", "day_type": "urlaub"},
            headers=self.kopf,
        )
        self.assertEqual(antwort.status_code, 400)
        self.assertEqual(
            [p for _, p, _ in GESEHEN[vorher:] if p == "/api/day-type/set-range"], []
        )

    def test_zeitraum_nur_erlaubte_werte(self):
        antwort = self.klient.post(
            "/api/day-type/set-range",
            json={"von": "2026-08-24", "bis": "2026-08-28", "day_type": "arbait"},
            headers=self.kopf,
        )
        self.assertEqual(antwort.status_code, 422)

    def test_urlaubsbilanz_nennt_kein_jahreskontingent(self):
        """Der Dienst zaehlt, was verbraucht ist. Wie viel zusteht, weiss er nicht."""
        antwort = self.klient.get("/api/day-type/urlaub-bilanz?jahr=2026", headers=self.kopf)
        self.assertEqual(antwort.status_code, 200, antwort.text)
        self.assertEqual(antwort.json()["verbraucht"], 3.5)
        self.assertNotIn("anspruch", antwort.json())

    def test_health_braucht_keine_anmeldung(self):
        for pfad in ("/health", "/healthz", "/health/ready"):
            self.assertEqual(self.klient.get(pfad).status_code, 200, pfad)

    # ── Aufgaben: die drei Luecken vom 2026-09-13 ────────────────────────
    #
    # Alle drei fielen auf, als die Aufgaben-App aus dem Kalender ausgelagert
    # wurde. Keine davon hat je einen Fehler gemeldet.

    def test_leeren_eines_feldes_kommt_als_null_an(self):
        """Regression: mit ``exclude_none`` liess sich ein Feld NIE leeren.

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
        """Die Route fehlte ganz, obwohl die Engine sie seit jeher hat.

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
        """`exclude_none` heisst hier „nicht anfassen", nicht „leeren".

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
        """Der Messgeraet-Eingang wird bewusst NICHT gespiegelt.

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


class ChatTest(unittest.TestCase):
    """POST /api/chat: Fragen an den Kalender, beantwortet im Haus.

    Prueft ausdruecklich auch, WO die Parameter ankommen und WELCHES Modell
    gewaehlt wird. Dass der Kontext ueber den Query des bootstrap geholt wird
    und nicht als Rumpf, ist genau die Fehlerklasse, an der
    ``/api/day-type/set`` ein Jahr lang still scheiterte.
    """

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), NachbauHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.basis = f"http://127.0.0.1:{cls.server.server_port}"
        os.environ["KALENDER_BASE_URL"] = cls.basis
        from app.config import settings
        from app.main import app
        settings.kalender_base_url = cls.basis
        cls.settings = settings
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        GESEHEN.clear()
        self.alt = (self.settings.llm_gateway_url, self.settings.llm_model)
        self.settings.llm_gateway_url = self.basis
        self.settings.llm_model = "homelab-fast"

    def tearDown(self):
        self.settings.llm_gateway_url, self.settings.llm_model = self.alt
        global LEERE_LLM_ANTWORT
        LEERE_LLM_ANTWORT = False

    def _kopf(self):
        return {"Authorization": f"Bearer {_jwt()}"}

    def test_antwortet_mit_text_aus_dem_haus(self):
        r = self.client.post("/api/chat", json={"frage": "Wann habe ich Zeit?"},
                             headers=self._kopf())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("Donnerstag", r.json()["antwort"])
        self.assertEqual(r.json()["modell"], "homelab-fast")

    def test_kontext_kommt_ueber_den_query_des_bootstrap(self):
        self.client.post("/api/chat", json={"frage": "Wann?"}, headers=self._kopf())
        rufe = [g for g in GESEHEN if g[1] == "/api/mobile/bootstrap"]
        self.assertEqual(len(rufe), 1, f"bootstrap-Aufrufe: {rufe}")
        _, _, abfrage = rufe[0]
        # Beide Pflichtparameter, und zwar im QUERY. Als Rumpf geschickt waere
        # die Antwort ein 422 gewesen, und der Endpunkt haette nie getragen.
        self.assertIn("start", abfrage)
        self.assertIn("end", abfrage)

    def test_ohne_gateway_kommt_503(self):
        self.settings.llm_gateway_url = ""
        r = self.client.post("/api/chat", json={"frage": "Wann?"}, headers=self._kopf())
        self.assertEqual(r.status_code, 503, r.text)

    def test_fremdes_modell_wird_abgelehnt(self):
        # Der Riegel, der die Termine im Haus haelt: ein Alias, der nicht
        # nachweislich hier endet, darf nicht benutzt werden.
        self.settings.llm_model = "claude-3-5-sonnet"
        r = self.client.post("/api/chat", json={"frage": "Wann?"}, headers=self._kopf())
        self.assertEqual(r.status_code, 503, r.text)
        self.assertNotIn("/v1/chat/completions", [g[1] for g in GESEHEN])

    def test_leere_modellantwort_ist_kein_erfolg(self):
        global LEERE_LLM_ANTWORT
        LEERE_LLM_ANTWORT = True
        r = self.client.post("/api/chat", json={"frage": "Wann?"}, headers=self._kopf())
        self.assertEqual(r.status_code, 502, r.text)

    def test_ohne_anmeldung_kein_zugang(self):
        r = self.client.post("/api/chat", json={"frage": "Wann?"})
        self.assertIn(r.status_code, (401, 403), r.text)
