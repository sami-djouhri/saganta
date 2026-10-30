"""Das SSO-Gate: wen laesst es durch, und was gibt es weiter.

Das Gate beantwortete bis 2026-09-27 nur, OB jemand angemeldet ist. Dahinter
meldete ein statischer Auto-Login-Token jeden Aufrufer als **Owner** an. Gemessen
am selben Tag: `ALLOWED_SUBS` ist fuer diesen Dienst nicht gesetzt, also offen,
und in der Anmelde-Datenbank liegen neben dem Owner zwei weitere Konten. Beide
haetten ueber `mail.saganta.*` das Postfach des Owners geoeffnet, mit HTTP 200
und ohne Spur.

Geprueft wird hier der neue Anteil, also die Entscheidung des Gates. Die
Sitzungspruefung selbst macht better-auth und bleibt unveraendert; sie wird
deshalb ersetzt (`get-session` liefert im Test eine feste Antwort).

Der Ende-zu-Ende-Durchgang mit echtem Browser-Cookie gehoert nicht hierher und
laesst sich auch nicht nachbauen: better-auth **signiert** das Sitzungs-Cookie,
und die Signatur kommt nicht aus der Datenbank. Eine von Hand eingetragene
Sitzung ergibt deshalb ein Cookie, das `get-session` mit `null` beantwortet
(am 2026-09-27 gemessen, beide plausiblen Signaturformen probiert). Wer den
ganzen Weg messen will, braucht eine echte Anmeldung im Browser.
"""

import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.routes_gate import ZIEL_HEADER, router

OWNER = "owner-sub-eins"
GAST = "gast-sub-zwei"
GEHEIMNIS_KALENDER = "0123456789abcdef0123456789abcdef"
GEHEIMNIS_POSTFACH = "fedcba9876543210fedcba9876543210"

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class _Antwort:
    """Minimale Nachbildung dessen, was urlopen als Kontextmanager liefert."""

    def __init__(self, nutzlast):
        self._daten = json.dumps(nutzlast).encode()

    def read(self):
        return self._daten

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _ruf(sub, ziel=None):
    kopf = {"Cookie": "saganta.session_token=egal"}
    if ziel is not None:
        kopf[ZIEL_HEADER] = ziel
    with patch("app.routes_gate.urllib.request.urlopen", return_value=_Antwort({"user": {"id": sub}})):
        return client.get("/auth/check", headers=kopf)


def _mit_konfig(**werte):
    """Setzt Konfigwerte fuer einen Test und nimmt sie zurueck.

    Bewusst nicht auf Modulebene: eine Zuweisung dort trifft alle anderen
    Testmodule, und `settings` ist ein geteiltes Objekt.
    """

    class Umschalter:
        def __enter__(self):
            self.vorher = {k: getattr(settings, k) for k in werte}
            for k, v in werte.items():
                setattr(settings, k, v)
            return self

        def __exit__(self, *_):
            for k, v in self.vorher.items():
                setattr(settings, k, v)
            return False

    return Umschalter()


def _grund(**werte):
    basis = {
        "owner_sub": OWNER,
        "ziele_mit_mandanten": ["kalender"],
        "kalender_tenant_secret": GEHEIMNIS_KALENDER,
        "postfach_tenant_secret": GEHEIMNIS_POSTFACH,
        "allowed_subs": [],
    }
    basis.update(werte)
    return _mit_konfig(**basis)


# --- Wer darf ueberhaupt durch --------------------------------------------


def test_ohne_cookie_401():
    assert client.get("/auth/check").status_code == 401


def test_gast_auf_getrenntes_ziel_darf():
    with _grund():
        r = _ruf(GAST, "kalender")
    assert r.status_code == 204, r.text


def test_gast_auf_ungetrenntes_ziel_verboten():
    """Die Luecke, die das hier schliesst: vorher waere daraus ein 204 geworden."""
    with _grund():
        for ziel in ("postfach", "nachrichten"):
            r = _ruf(GAST, ziel)
            assert r.status_code == 403, f"{ziel}: {r.status_code}"


def test_owner_darf_ueberall():
    with _grund():
        for ziel in ("kalender", "postfach", "nachrichten"):
            assert _ruf(OWNER, ziel).status_code == 204, ziel


def test_unbekanntes_ziel_gilt_als_ungetrennt():
    """Wer am neuen Vhost den Ziel-Header vergisst, sperrt Fremde aus.

    Der umgekehrte Aufbau (Sperrliste) haette bei einem vergessenen Header
    freien Durchgang ergeben, und niemand haette es gemerkt.
    """
    with _grund():
        assert _ruf(GAST, "etwas-neues").status_code == 403
        assert _ruf(GAST, None).status_code == 403
        # Der Owner kommt auch ohne Ziel-Angabe durch.
        assert _ruf(OWNER, None).status_code == 204


def test_ohne_owner_kommt_niemand_auf_ungetrennte_ziele():
    """Fail-closed: eine fehlende Owner-Kennung sperrt, statt zu oeffnen."""
    with _grund(owner_sub=""):
        assert _ruf(OWNER, "postfach").status_code == 403
        assert _ruf(GAST, "postfach").status_code == 403
        # Das getrennte Ziel bleibt erreichbar, es braucht keinen Owner-Vergleich.
        assert _ruf(GAST, "kalender").status_code == 204


def test_allowlist_wirkt_weiter():
    with _grund(allowed_subs=[OWNER]):
        assert _ruf(OWNER, "kalender").status_code == 204
        assert _ruf(GAST, "kalender").status_code == 403


# --- Was das Gate weitergibt ----------------------------------------------


def test_signatur_haengt_am_mandanten_und_am_ziel():
    import hashlib
    import hmac

    def erwartet(sub, geheimnis):
        return hmac.new(geheimnis.encode(), sub.encode(), hashlib.sha256).hexdigest()

    with _grund():
        r = _ruf(GAST, "kalender")
        assert r.headers["x-saganta-sub"] == GAST
        assert r.headers["x-saganta-sub-sig"] == erwartet(GAST, GEHEIMNIS_KALENDER)

        # Dasselbe Konto, anderes Ziel: andere Signatur. Eine abgefangene
        # Signatur gilt damit nicht beim Nachbardienst.
        r2 = _ruf(OWNER, "postfach")
        assert r2.headers["x-saganta-sub-sig"] == erwartet(OWNER, GEHEIMNIS_POSTFACH)
        assert r2.headers["x-saganta-sub-sig"] != erwartet(OWNER, GEHEIMNIS_KALENDER)


def test_ohne_geheimnis_keine_header():
    """Kein halber Zustand: fehlt das Geheimnis, bleibt es beim reinen Ja."""
    with _grund(kalender_tenant_secret=""):
        r = _ruf(GAST, "kalender")
        assert r.status_code == 204
        assert "x-saganta-sub" not in r.headers
        assert "x-saganta-sub-sig" not in r.headers
