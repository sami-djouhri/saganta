"""Tarife: fail-closed an jeder Stelle, an der etwas fehlen kann.

Der teure Fehler bei einem Tarif-System ist nicht, dass ein zahlender Kunde
etwas nicht bekommt (das meldet er). Es ist, dass ein Gratis-Konto etwas
bekommt, das Geld kostet, denn das meldet niemand. Deshalb pruefen diese Tests
vor allem die Wege, auf denen ein Wert fehlen, leer oder falsch sein kann.
"""
import unittest

from fastapi import HTTPException

from saganta_dienst import tarife


class NormalisierenTest(unittest.TestCase):
    def test_bekannte_tarife_bleiben(self):
        self.assertEqual(tarife.normalisiere("free"), "free")
        self.assertEqual(tarife.normalisiere("pro"), "pro")

    def test_alles_andere_wird_free(self):
        """★ Die eine Stelle, an der ein Tippfehler teuer werden koennte."""
        for wert in (None, "", "  ", "PRO", "Pro", "premium", "pro ", "enterprise", "0", "1"):
            with self.subTest(wert=wert):
                self.assertEqual(tarife.normalisiere(wert), "free")


class MerkmaleTest(unittest.TestCase):
    def test_free_hat_kein_audio(self):
        """Die Sprachsynthese ist der teure Teil, nicht die redigierte Fassung."""
        self.assertFalse(tarife.hat("free", "briefing.audio"))
        self.assertTrue(tarife.hat("pro", "briefing.audio"))

    def test_unbekanntes_merkmal_ist_zu(self):
        """Ein Tippfehler im Merkmalsnamen soll schliessen, nicht oeffnen."""
        self.assertFalse(tarife.hat("pro", "briefing.gibtsnicht"))
        self.assertFalse(tarife.hat("free", "briefing.gibtsnicht"))

    def test_jeder_tarif_kennt_dieselben_merkmale(self):
        """Sonst faellt ein Merkmal fuer einen Tarif still auf den Default.

        Ein neues Merkmal, das nur bei PRO eingetragen wird, wuerde bei FREE
        ueber `.get(..., False)` als „nicht enthalten" gelesen. Das waere hier
        zufaellig richtig und beim naechsten Merkmal, das FREE haben soll,
        zufaellig falsch.
        """
        self.assertEqual(
            set(tarife.MERKMALE["free"]),
            set(tarife.MERKMALE["pro"]),
        )

    def test_ist_pro(self):
        self.assertTrue(tarife.ist_pro("pro"))
        for wert in (None, "free", "PRO", "unsinn"):
            with self.subTest(wert=wert):
                self.assertFalse(tarife.ist_pro(wert))


class VerlangeTest(unittest.TestCase):
    def test_pro_kommt_durch(self):
        tarife.verlange("pro", "briefing.audio")  # darf nicht werfen

    def test_free_bekommt_402_nicht_403(self):
        """★ 402 und 403 sind verschiedene Aussagen.

        403 heisst „du darfst hier nicht her" (Owner-Gate), 402 heisst „dein
        Tarif reicht dafuer nicht". Nur auf das Zweite ist ein Hinweis auf Pro
        die richtige Antwort; wuerde beides 403, koennte die Oberflaeche sie
        nicht auseinanderhalten.
        """
        with self.assertRaises(HTTPException) as f:
            tarife.verlange("free", "briefing.audio")
        self.assertEqual(f.exception.status_code, 402)

    def test_fehlender_tarif_wird_abgelehnt(self):
        with self.assertRaises(HTTPException) as f:
            tarife.verlange(None, "briefing.audio")
        self.assertEqual(f.exception.status_code, 402)

    def test_eigener_hinweis_erreicht_den_aufrufer(self):
        with self.assertRaises(HTTPException) as f:
            tarife.verlange("free", "briefing.audio", "Sprachfassung gibt es mit Pro.")
        self.assertIn("Sprachfassung", str(f.exception.detail))


class LaengeStutzenTest(unittest.TestCase):
    def test_free_wird_auf_mittel_gestutzt(self):
        self.assertEqual(tarife.stutze_laenge("free", "lang"), "mittel")

    def test_free_darf_kuerzer(self):
        self.assertEqual(tarife.stutze_laenge("free", "kurz"), "kurz")

    def test_pro_darf_lang(self):
        self.assertEqual(tarife.stutze_laenge("pro", "lang"), "lang")

    def test_unsinnige_laenge_wird_mittel(self):
        self.assertEqual(tarife.stutze_laenge("pro", "episch"), "mittel")
        self.assertEqual(tarife.stutze_laenge("free", ""), "mittel")

    def test_fehlender_tarif_stutzt_wie_free(self):
        self.assertEqual(tarife.stutze_laenge(None, "lang"), "mittel")


class TarifImTokenTest(unittest.TestCase):
    """Der Weg, auf dem der Tarif tatsaechlich ankommt: als Claim im JWT."""

    def test_me_ohne_claim_ist_free(self):
        from saganta_dienst.auth import Me

        self.assertEqual(Me(sub="x").plan, "free")

    def test_me_nimmt_den_claim_an(self):
        from saganta_dienst.auth import Me

        self.assertEqual(Me(sub="x", plan="pro").plan, "pro")


if __name__ == "__main__":
    unittest.main()
