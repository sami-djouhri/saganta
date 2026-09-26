"""Datenmodell des Tagebuchs, bewusst arm an Klartext.

Der Dienst verwahrt Chiffrat. Er kennt genau drei Dinge im Klartext: welcher
Mandant geschrieben hat, an welchem Tag, und wie lang der Text ungefaehr war.
Alles Weitere, also Text, Stimmung, Schlagworte und Titel, steckt im Chiffrat
und wird ausschliesslich im Browser gebildet und geoeffnet.

Warum kein Titel- oder Auszugsfeld: es waere die aussagekraeftigste Zeile des
Eintrags, und sie stuende dann im Klartext in der Datenbank. Die Zusicherung
"der Server weiss nichts vom Inhalt" waere damit ausgerechnet fuer das
Interessanteste nicht wahr. Dieselbe Ueberlegung steht in ``krypto.ts`` der
Notizen-App bei ``paketSchnueren``.

Warum keine Volltextsuche: sie braeuchte Klartext. Gesucht wird im Browser
ueber die entschluesselten Eintraege.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def jetzt() -> datetime:
    return datetime.now(timezone.utc)


class Eintrag(Base):
    """Ein Tag, ein Eintrag.

    Composite-PK ``(owner_sub, datum)``, also ein Upsert je Tag. Das ist
    dieselbe Form wie ``DailyCheckIn`` und ``DailyReview`` im Kalender und der
    Grund, warum ein Tagebuch kein Notizbuch ist: es gibt keine zwei Eintraege
    zum selben Tag, und die Ordnung ist die Zeit, nicht ein Ordner.
    """

    __tablename__ = "eintraege"

    owner_sub: Mapped[str] = mapped_column(String(128), primary_key=True)
    datum: Mapped[date] = mapped_column(Date, primary_key=True)

    #: AES-GCM-Chiffrat, Base64. Enthaelt Text und Skalen als ein JSON-Paket.
    chiffrat: Mapped[str] = mapped_column(Text, nullable=False)
    #: Der zum Chiffrat gehoerende Einmalwert, Base64. Bei GCM waere ein
    #: zweites Mal derselbe kein Schoenheitsfehler, sondern der Verlust der
    #: Vertraulichkeit, deshalb liegt er je Eintrag und nicht global.
    iv: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Welche Fassung des Verfahrens den Eintrag verschlossen hat. Erlaubt
    #: spaeter einen Wechsel, ohne den Bestand auf einmal umschreiben zu muessen.
    schluessel_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=jetzt)
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=jetzt, onupdate=jetzt
    )


class Tresor(Base):
    """Die verpackten Schluessel eines Mandanten.

    Es gibt genau einen Datenschluessel (DEK) je Konto, und er liegt hier
    ausschliesslich verpackt: einmal unter der Passphrase, einmal unter dem
    Wiederherstellungsschluessel. Beide oeffnen denselben DEK.

    Das ist der Grund, warum ein Passphrasenwechsel nichts kostet: es wird nur
    das eine Paket neu verschnuert, nicht der Bestand neu verschluesselt. Und es
    ist der Grund, warum ein vergessenes Passwort nicht das Ende ist, solange
    der Wiederherstellungsschluessel existiert.

    Der Server kann aus keinem dieser Felder den DEK gewinnen. Er sieht Salz,
    Rundenzahl und zwei Chiffrate.
    """

    __tablename__ = "tresore"

    owner_sub: Mapped[str] = mapped_column(String(128), primary_key=True)

    #: Ableitungsverfahren, heute PBKDF2-SHA256. Steht als Text da, damit ein
    #: spaeterer Wechsel (etwa auf Argon2id) am Bestand erkennbar ist, statt
    #: stillschweigend anders gerechnet zu werden.
    kdf: Mapped[str] = mapped_column(String(32), nullable=False, default="PBKDF2-SHA256")
    kdf_iterationen: Mapped[int] = mapped_column(Integer, nullable=False)

    #: Passphrase-Zweig
    salz_passphrase: Mapped[str] = mapped_column(String(64), nullable=False)
    wrap_passphrase: Mapped[str] = mapped_column(Text, nullable=False)
    wrap_passphrase_iv: Mapped[str] = mapped_column(String(32), nullable=False)

    #: Wiederherstellungs-Zweig. Gleiches Verfahren, anderes Salz, anderer
    #: Einmalwert. Dasselbe Salz fuer beide Zweige waere kein sofortiger Bruch,
    #: aber es verknuepfte zwei Geheimnisse ohne Not.
    salz_wiederherstellung: Mapped[str] = mapped_column(String(64), nullable=False)
    wrap_wiederherstellung: Mapped[str] = mapped_column(Text, nullable=False)
    wrap_wiederherstellung_iv: Mapped[str] = mapped_column(String(32), nullable=False)

    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=jetzt)
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=jetzt, onupdate=jetzt
    )
