"""Kleinteiliges, das mehrere Module brauchen.

**Zeitkonvention:** Dieser Dienst rechnet intern in *naivem UTC*. Grund: an
Freigaben haengen Ablaufzeiten, und die muessen auch dann noch stimmen, wenn
Sommerzeit umspringt, eine Berlin-lokale Ablaufzeit springt mit. SQLite gibt
``DateTime(timezone=True)`` ohnehin ohne Zeitzone zurueck, ein aware/naiv-Mix
waere also nur eine Falle. Umgerechnet wird erst in der Anzeige.

Das weicht bewusst von der Kalender-Konvention (naive datetimes = Berlin) ab:
dort geht es um Termine, die *lokal* gemeint sind, hier um Fristen, die absolut
gemeint sind.
"""

import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import UTC, datetime

# Laenge des Freigabe-Merkmals in Zufallsbytes. 16 Bytes = 128 bit Entropie,
# als base64url 22 Zeichen: kurz genug fuer n.saganta.de/<merkmal>, weit
# jenseits von Durchprobieren.
_MERKMAL_BYTES = 16


def jetzt() -> datetime:
    """Aktueller Zeitpunkt als naives UTC (siehe Modul-Kopf)."""
    return datetime.now(UTC).replace(tzinfo=None)


def neues_merkmal() -> str:
    """Unratbares Merkmal fuer eine Freigabe-Adresse."""
    return secrets.token_urlsafe(_MERKMAL_BYTES)


def passwort_hash(passwort: str, salz: bytes | None = None) -> tuple[str, str]:
    """scrypt-Hash fuer ein Freigabe-Passwort (nur Modus ``offen``).

    Im Modus ``chiffriert`` kommt das Passwort nie hier an, dort leitet der
    Browser daraus den Schluessel ab, der Server sieht weder Passwort noch Text.

    Rueckgabe: (hash_hex, salz_hex).
    """
    salz = salz or secrets.token_bytes(16)
    roh = hashlib.scrypt(passwort.encode("utf-8"), salt=salz, n=2**14, r=8, p=1, dklen=32)
    return roh.hex(), salz.hex()


def passwort_stimmt(passwort: str, hash_hex: str, salz_hex: str) -> bool:
    versuch, _ = passwort_hash(passwort, bytes.fromhex(salz_hex))
    return hmac.compare_digest(versuch, hash_hex)


def tags_normalisieren(roh: list[str] | None) -> str:
    """Tags als kleingeschriebene, entdoppelte, kommagetrennte Liste.

    Gespeichert wird ein String, weil Tags hier ein Suchmerkmal sind und keine
    eigene Entitaet, die Volltextsuche indiziert sie mit. Eine eigene Tabelle
    kaeme erst dann in Frage, wenn Tags Eigenschaften bekommen (Farbe, Regeln).
    """
    if not roh:
        return ""
    gesehen: list[str] = []
    for t in roh:
        sauber = re.sub(r"[,\s]+", "-", unicodedata.normalize("NFC", t).strip().lower())
        sauber = sauber.strip("-")[:40]
        if sauber and sauber not in gesehen:
            gesehen.append(sauber)
    return ",".join(gesehen[:20])


def tags_lesen(gespeichert: str | None) -> list[str]:
    return [t for t in (gespeichert or "").split(",") if t]


def dateiname_saeubern(name: str) -> str:
    """Dateinamen auf etwas reduzieren, das gefahrlos in einem Header steht.

    Der Name wird nie als Pfad benutzt (die Ablage laeuft ueber eine eigene
    UUID), aber er landet in ``Content-Disposition``, dort haben Zeilenumbrueche
    und Anfuehrungszeichen nichts verloren.
    """
    name = unicodedata.normalize("NFC", name).replace("\\", "/").split("/")[-1]
    name = re.sub(r'[\x00-\x1f"\\]', "", name).strip()
    return name[:200] or "datei"
