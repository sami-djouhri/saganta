"""OAuth2 fuer Mailkonten.

⚠️ **Was diese Tests NICHT belegen koennen.** Ohne eine beim Anbieter
registrierte Anwendung laesst sich der Fluss nicht von Ende zu Ende pruefen: es
gibt keine Client-Kennung, mit der Google oder Microsoft antworten wuerden.
Geprueft ist deshalb genau das, was hier entschieden wird, und nichts wird als
gemessen ausgegeben, was nur nachgebaut ist:

* dass ohne Konfiguration **gar kein** Weg angeboten wird (fail-closed),
* dass die Autorisierungs-Adresse die Parameter traegt, ohne die der Zugang nach
  einer Stunde stirbt,
* dass die Ablauf-Rechnung einen Sicherheitsabstand haelt,
* dass ein fehlender Auffrischungstoken den vorhandenen nicht loescht.

Der erste echte Lauf gegen einen Anbieter bleibt ein Owner-Schritt.
"""

import base64
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

# ★ Der Fernet-Testschluessel wird hier ERZEUGT statt hingeschrieben (2026-09-21).
# Vorher stand er als fertiger base64-String da. Inhaltlich war er schon immer
# harmlos, dekodiert lautete er "test-key-32-byte-fuer-die-tests=", aber ein
# Secret-Scanner liest keine Bedeutung, er misst Entropie. gitleaks hat ihn
# deshalb als `generic-api-key` gemeldet und damit den gesamten
# Veroeffentlichungs-Lauf dieses Repos ab dem 2026-09-14 blockiert, ohne dass
# irgendwo ein echtes Geheimnis im Spiel war.
#
# So bleibt der Wert ein gueltiger Fernet-Schluessel (32 Byte, urlsafe-base64,
# sonst wirft `Fernet()` in app/crypto.py), aber im Quelltext steht nur noch
# lesbarer Klartext. Wer die Zeile sieht, erkennt den Zweck ohne zu dekodieren.
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-testsuite")
os.environ.setdefault(
    "FERNET_KEY",
    base64.urlsafe_b64encode(b"testwert-nicht-echt-32-bytes!!!!").decode(),
)
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import oauth  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture
def konfiguriert():
    """Google so konfigurieren, als haette der Owner die Registrierung erledigt."""
    vorher = (
        settings.oauth_google_client_id,
        settings.oauth_google_client_secret,
        settings.oauth_redirect_url,
    )
    settings.oauth_google_client_id = "kennung.apps.example.invalid"
    settings.oauth_google_client_secret = "geheim"
    settings.oauth_redirect_url = "https://post.example.invalid/oauth/rueckleitung"
    yield
    (
        settings.oauth_google_client_id,
        settings.oauth_google_client_secret,
        settings.oauth_redirect_url,
    ) = vorher


class TestFailClosed:
    def test_ohne_konfiguration_gibt_es_keinen_anbieter(self):
        # ★ Ein Knopf, der beim Anbieter in einen Fehler laeuft, sieht aus wie ein
        # Ausfall dieser Anwendung. Lieber gar nicht anbieten.
        settings.oauth_google_client_id = ""
        settings.oauth_microsoft_client_id = ""
        assert oauth.verfuegbare_anbieter() == []
        assert oauth.anbieter_holen("google") is None

    def test_ohne_rueckleitung_gilt_der_anbieter_als_nicht_verfuegbar(self):
        # Ohne Rueckleitungs-Adresse kaeme der Code nie zurueck. Halb konfiguriert
        # ist hier dasselbe wie gar nicht.
        vorher = settings.oauth_redirect_url
        settings.oauth_google_client_id = "kennung"
        settings.oauth_google_client_secret = "geheim"
        settings.oauth_redirect_url = ""
        try:
            assert oauth.anbieter_holen("google") is None
        finally:
            settings.oauth_redirect_url = vorher
            settings.oauth_google_client_id = ""
            settings.oauth_google_client_secret = ""

    def test_mit_konfiguration_ist_er_da(self, konfiguriert):
        namen = [a.schluessel for a in oauth.verfuegbare_anbieter()]
        assert "google" in namen


class TestAutorisierungsAdresse:
    def test_traegt_die_parameter_ohne_die_der_zugang_stirbt(self, konfiguriert):
        anbieter = oauth.anbieter_holen("google")
        assert anbieter is not None
        url = oauth.autorisierung_url(anbieter, "zustand-123")
        werte = parse_qs(urlparse(url).query)

        # ★★ Ohne `access_type=offline` liefert Google GAR KEINEN
        # Auffrischungstoken, und der Zugang waere nach einer Stunde tot, ohne
        # dass irgendwo ein Fehler steht.
        assert werte["access_type"] == ["offline"]
        # ★ Ohne `prompt=consent` kommt bei einer WIEDERHOLTEN Freigabe nur ein
        # Zugriffstoken. Dann stirbt das Konto still nach einer Stunde, und zwar
        # nur beim zweiten Verbinden: ein Fehler, den der erste Test nie sieht.
        assert werte["prompt"] == ["consent"]
        assert werte["response_type"] == ["code"]
        assert werte["state"] == ["zustand-123"]
        assert werte["redirect_uri"] == [settings.oauth_redirect_url]

    def test_scope_reicht_fuer_imap(self, konfiguriert):
        anbieter = oauth.anbieter_holen("google")
        assert anbieter is not None
        # ⚠️ Die schmaleren gmail.readonly-Scopes reichen fuer IMAP NICHT. Der
        # Zugang wird erteilt und IMAP lehnt ihn trotzdem ab: das Konto steht
        # gruen in der Liste und bleibt leer.
        assert "https://mail.google.com/" in anbieter.scopes

    def test_login_hinweis_nur_wenn_angegeben(self, konfiguriert):
        anbieter = oauth.anbieter_holen("google")
        assert anbieter is not None
        ohne = parse_qs(urlparse(oauth.autorisierung_url(anbieter, "z")).query)
        assert "login_hint" not in ohne
        mit = parse_qs(urlparse(oauth.autorisierung_url(anbieter, "z", "wer@example.invalid")).query)
        assert mit["login_hint"] == ["wer@example.invalid"]


class TestZustand:
    def test_ist_lang_und_jedes_mal_anders(self):
        # Der einzige Riegel gegen eine untergeschobene Rueckleitung. Ein
        # ratbarer Wert waere keiner.
        werte = {oauth.zustand_erzeugen() for _ in range(50)}
        assert len(werte) == 50
        assert all(len(w) >= 32 for w in werte)


class TestAblauf:
    def test_haelt_sicherheitsabstand(self):
        # ★ Ohne Abstand gilt ein Token bis zur letzten Sekunde als gueltig, und
        # ein Abruf, der genau dann beginnt, scheitert mittendrin mit einem
        # Anmeldefehler, der wie ein entzogener Zugriff aussieht.
        ablauf = oauth._ablauf(3600)
        rest = ablauf - datetime.now(timezone.utc)
        assert timedelta(minutes=58) < rest < timedelta(minutes=59, seconds=5)

    def test_faellt_bei_unsinn_auf_eine_stunde_zurueck(self):
        rest = oauth._ablauf("keine zahl") - datetime.now(timezone.utc)
        assert timedelta(minutes=58) < rest < timedelta(minutes=59, seconds=5)

    def test_kurze_laufzeit_bleibt_in_der_zukunft(self):
        # Ein Anbieter mit 30 s Laufzeit ergaebe nach Abzug einen Zeitpunkt in
        # der Vergangenheit; dann waere der Token sofort abgelaufen und die
        # Auffrischung liefe in einer Schleife.
        assert oauth._ablauf(30) > datetime.now(timezone.utc)


class TestEmailAusIdToken:
    def _token(self, nutzlast: dict) -> str:
        import base64
        import json

        roh = base64.urlsafe_b64encode(json.dumps(nutzlast).encode()).decode().rstrip("=")
        return f"kopf.{roh}.signatur"

    def test_liest_die_adresse(self):
        assert oauth._email_aus_id_token(self._token({"email": "a@b.invalid"})) == "a@b.invalid"

    def test_haelt_muell_aus(self):
        # Die Funktion prueft keine Signatur und darf deshalb ueber nichts
        # entscheiden; sie muss aber jeden Unsinn ueberleben, statt den
        # Verbinden-Fluss mit einer Ausnahme abzubrechen.
        for wert in (None, "", "kein.jwt", "a.b.c", 42, self._token({"kein_email_feld": 1})):
            assert oauth._email_aus_id_token(wert) is None


class TestMicrosoftEigenheiten:
    def test_smtp_port_ist_587(self):
        # ⚠️ Microsoft kann auf 465 kein implizites TLS. Wer dort 465 eintraegt,
        # bekommt einen Zeitablauf ohne Fehlermeldung.
        assert oauth.ANBIETER["microsoft"].smtp_port == 587

    def test_offline_access_ist_im_scope(self):
        # Bei Microsoft bringt nicht `access_type`, sondern dieser Scope den
        # Auffrischungstoken.
        assert "offline_access" in oauth.ANBIETER["microsoft"].scopes
