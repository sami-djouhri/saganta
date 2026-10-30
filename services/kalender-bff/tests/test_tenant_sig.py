"""Interop-Test: erzeugen die Kalender-Absender die Signatur, die der Prüfer will?

**Warum ein fest eingebrannter Vektor und kein Vergleich mit dem echten Prüfer:**
Prüfer (``kalender/backend/tenant_auth.py``) und Absender liegen in zwei getrennten
Repos. Ein Test, der den Prüfer importiert, liefe nur auf einem Host, auf dem
zufällig beide Bäume liegen, und wäre anderswo still grün, weil er die Datei nicht
findet. Stattdessen prüfen **beide Seiten gegen denselben bekannten Vektor**
(``kalender/tests/test_tenant_header_auth.py`` enthält denselben). Ändert eine Seite
die Formel, bricht ihr eigener Test, nicht erst der Betrieb.

Deckt zusätzlich den Ausrollpfad ab: **ohne Geheimnis darf keine Signatur entstehen.**
Nur so lassen sich Absender und Prüfer nacheinander ausrollen, statt im selben
Moment umschalten zu müssen.
"""

import hashlib
import hmac
import unittest

# Gemeinsamer Vektor beider Repos, NICHT ändern, ohne die Gegenseite mitzuziehen.
VEKTOR_SECRET = "saganta-kalender-interop-testvektor"
VEKTOR_SUB = "test-sub-0123456789"
VEKTOR_SIG = "93c03830288e7ce029d000f0ac8da629d8e6f45e7b1d1d17a6a253719abab49a"

SIG_HEADER = "X-Saganta-Sub-Sig"
SUB_HEADER = "X-Saganta-Sub"


def _signatur(secret: str, sub: str) -> str:
    return hmac.new(secret.encode("utf-8"), sub.encode("utf-8"), hashlib.sha256).hexdigest()


class TestInteropVektor(unittest.TestCase):
    def test_vektor_ist_die_erwartete_formel(self):
        """Der Vektor selbst: schlägt an, wenn jemand die Formel austauscht."""
        self.assertEqual(_signatur(VEKTOR_SECRET, VEKTOR_SUB), VEKTOR_SIG)

    def test_signatur_haengt_am_sub(self):
        """Eine abgefangene Signatur darf nicht auf einen fremden sub passen."""
        self.assertNotEqual(_signatur(VEKTOR_SECRET, "fremder-sub"), VEKTOR_SIG)

    def test_signatur_haengt_am_geheimnis(self):
        self.assertNotEqual(_signatur("anderes-geheimnis", VEKTOR_SUB), VEKTOR_SIG)


class TestAbsender(unittest.TestCase):
    """Der echte Absender dieses Dienstes gegen den Vektor."""

    def _tenant_headers(self, secret: str, sub):
        from app import tenant_sig

        original = tenant_sig.settings.kalender_tenant_secret
        tenant_sig.settings.kalender_tenant_secret = secret
        try:
            return tenant_sig.tenant_headers(sub)
        finally:
            tenant_sig.settings.kalender_tenant_secret = original

    def test_signiert_nach_vektor(self):
        h = self._tenant_headers(VEKTOR_SECRET, VEKTOR_SUB)
        self.assertEqual(h[SUB_HEADER], VEKTOR_SUB)
        self.assertEqual(h[SIG_HEADER], VEKTOR_SIG)

    def test_ohne_geheimnis_keine_signatur(self):
        """Ausrollbarkeit: Absender darf vor dem Prüfer live gehen."""
        h = self._tenant_headers("", VEKTOR_SUB)
        self.assertEqual(h, {SUB_HEADER: VEKTOR_SUB})
        self.assertNotIn(SIG_HEADER, h)

    def test_ohne_sub_gar_keine_header(self):
        """Der headerlose CORE-Pfad (HA/iCal) muss headerlos bleiben."""
        self.assertEqual(self._tenant_headers(VEKTOR_SECRET, None), {})


if __name__ == "__main__":
    unittest.main()
