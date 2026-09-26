"""Die Abruf-Adresse fuer eine Heim-Automation.

★★ Der Abrufweg (`/briefing/public/briefing/<token>`) gab es schon, aber er
stand in **keiner Antwort** und damit in keiner Oberflaeche: wer ihn benutzen
wollte, musste den Pfad aus dem Quelltext ablesen. Ein Weg, den nichts sichtbar
macht, wird nicht benutzt. Seit 2026-09-13 nennt `GET /delivery` ihn als
`json_url`, und diese Tests halten fest, dass er dort bleibt und auf dieselbe
Kennung zeigt wie der Podcast-Feed.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-testsuite")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.briefing_schemas import DeliveryOut  # noqa: E402


class NachbauConfig:
    """Ein DeliveryConfig, soweit die Adressbildung ihn braucht."""

    def __init__(self, feed_token: str) -> None:
        self.feed_token = feed_token
        self.webhook_url = None


def _urls(basis: str, token: str = "tok-abc-123"):
    """Beide Adressen bilden, mit `public_base_url` auf einen Testwert gesetzt."""
    from app.config import settings
    from app import routes_briefing as rb

    vorher = settings.public_base_url
    try:
        settings.public_base_url = basis
        dc = NachbauConfig(token)
        return rb._feed_url(dc), rb._json_url(dc)
    finally:
        settings.public_base_url = vorher


def test_json_adresse_zeigt_auf_dieselbe_kennung_wie_der_feed():
    feed, json_url = _urls("https://news.example.invalid")
    assert feed == "https://news.example.invalid/briefing/feed/tok-abc-123.xml"
    assert json_url == "https://news.example.invalid/briefing/json/tok-abc-123"


def test_abschliessender_schraegstrich_verdoppelt_sich_nicht():
    # Eine konfigurierte Basis mit Schraegstrich am Ende ergaebe sonst `//briefing`,
    # was manche Proxys auf einen anderen Pfad umschreiben.
    _, json_url = _urls("https://news.example.invalid/")
    assert json_url == "https://news.example.invalid/briefing/json/tok-abc-123"


def test_ohne_konfigurierte_basis_bleibt_die_adresse_leer():
    # Nicht konfiguriert heisst nicht erreichbar. Eine geratene Adresse waere ein
    # Link, den niemand aufrufen kann (dieselbe Regel wie 2026-09-12,
    # „Adressen ohne Ziel sind leer, nicht erfunden").
    feed, json_url = _urls("")
    assert feed is None
    assert json_url is None


def test_delivery_antwort_traegt_das_feld():
    # Ohne dieses Feld bliebe der Weg unsichtbar, genau wie vorher.
    aus = DeliveryOut(
        feed_url="https://x.invalid/briefing/feed/t.xml",
        json_url="https://x.invalid/briefing/json/t",
        webhook_url=None,
        webhook_configured=False,
    )
    assert aus.json_url == "https://x.invalid/briefing/json/t"


def test_json_url_ist_optional_und_faellt_auf_none():
    # Aeltere Clients schicken das Feld nicht mit; das Schema darf daran nicht
    # scheitern, sonst bricht eine Antwort an einer Zusatzangabe.
    aus = DeliveryOut(feed_url=None, webhook_url=None, webhook_configured=False)
    assert aus.json_url is None
