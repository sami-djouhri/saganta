"""Vertrag an der Schnittstelle.

Auffaellig an diesen Modellen ist, was fehlt: kein Titel, keine Stimmung, keine
Schlagworte, kein Textfeld. Der Dienst nimmt Chiffrat entgegen und gibt Chiffrat
zurueck. Was drinsteht, ist seine Sache nicht.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .config import settings


class EintragAn(BaseModel):
    """Was der Browser zum Speichern schickt."""

    chiffrat: str = Field(min_length=1, max_length=settings.eintrag_max_chiffrat_bytes)
    iv: str = Field(min_length=1, max_length=32)
    schluessel_version: int = Field(default=1, ge=1, le=999)


class EintragAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    datum: date
    chiffrat: str
    iv: str
    schluessel_version: int
    erstellt_am: datetime
    geaendert_am: datetime


class TagAus(BaseModel):
    """Ein gefuellter Tag ohne seinen Inhalt.

    Fuer die Datumsleiste: sie muss wissen, welche Tage etwas enthalten, nicht
    was. ``zeichen`` ist die Laenge des Chiffrats und damit ein grobes Mass fuer
    die Laenge des Eintrags. Es steht hier, weil die Oberflaeche lange und kurze
    Tage unterscheidbar machen soll, und es verraet nichts, was der Server nicht
    ohnehin sieht.
    """

    datum: date
    zeichen: int
    geaendert_am: datetime


class TresorAn(BaseModel):
    """Die verpackten Schluessel, wie der Browser sie beim Einrichten erzeugt."""

    kdf: str = Field(default="PBKDF2-SHA256", max_length=32)
    # Untergrenze statt freier Wahl: eine Rundenzahl, die der Browser
    # vorschlaegt, kann ein veraenderter Browser auch auf 1 setzen. Der Server
    # kann die Ableitung nicht nachrechnen, aber er kann Unsinn ablehnen.
    # 310.000 ist die OWASP-Empfehlung fuer PBKDF2-HMAC-SHA256 (Stand 2026),
    # dieselbe Zahl steht in krypto.ts der Notizen-App.
    kdf_iterationen: int = Field(ge=310_000, le=10_000_000)

    salz_passphrase: str = Field(min_length=1, max_length=64)
    wrap_passphrase: str = Field(min_length=1, max_length=settings.tresor_max_feld_bytes)
    wrap_passphrase_iv: str = Field(min_length=1, max_length=32)

    salz_wiederherstellung: str = Field(min_length=1, max_length=64)
    wrap_wiederherstellung: str = Field(min_length=1, max_length=settings.tresor_max_feld_bytes)
    wrap_wiederherstellung_iv: str = Field(min_length=1, max_length=32)


class PassphraseAn(BaseModel):
    """Nur der Passphrase-Zweig, fuer den Wechsel des Passworts.

    Der Wiederherstellungs-Zweig bleibt dabei unberuehrt. Wer die Passphrase
    wechselt, soll nicht nebenbei seinen ausgedruckten Notfallzettel entwerten,
    ohne es zu merken.
    """

    kdf: str = Field(default="PBKDF2-SHA256", max_length=32)
    kdf_iterationen: int = Field(ge=310_000, le=10_000_000)
    salz_passphrase: str = Field(min_length=1, max_length=64)
    wrap_passphrase: str = Field(min_length=1, max_length=settings.tresor_max_feld_bytes)
    wrap_passphrase_iv: str = Field(min_length=1, max_length=32)


class TresorAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kdf: str
    kdf_iterationen: int
    salz_passphrase: str
    wrap_passphrase: str
    wrap_passphrase_iv: str
    salz_wiederherstellung: str
    wrap_wiederherstellung: str
    wrap_wiederherstellung_iv: str
    erstellt_am: datetime
    geaendert_am: datetime
