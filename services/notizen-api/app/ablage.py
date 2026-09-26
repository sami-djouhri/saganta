"""Dateiablage fuer Anhaenge.

Drei Dinge, die hier bewusst so sind:

1. **Der hochgeladene Name wird nie zum Pfad.** Gespeichert wird unter einer
   UUID; der Name lebt nur als Spalte in der Datenbank weiter. Damit ist die
   ganze Familie der Pfad-Tricks (``../``, absolute Pfade, NUL-Bytes) gar nicht
   erst anwendbar.
2. **Die Art der Datei wird am Inhalt gemessen, nicht am Namen und nicht am
   mitgeschickten Content-Type**: beides bestimmt der Absender.
3. **SVG ist nicht erlaubt.** Es sieht aus wie ein Bild, ist aber ein
   Dokumentformat mit Skriptfaehigkeit; ausgeliefert an denselben Ursprung wie
   die Anwendung waere es ein Einfallstor. Wer ein Diagramm teilen will, nimmt
   PNG.
"""

import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from .config import settings

# MIME → erwartete Anfangsbytes. Leere Liste = kein Magic-Wert pruefbar
# (dann greift die Textpruefung weiter unten).
ERLAUBTE_TYPEN: dict[str, list[bytes]] = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],
    "application/pdf": [b"%PDF-"],
    "text/plain": [],
    "text/markdown": [],
}

_LESEBLOCK = 64 * 1024

# 413 direkt als Zahl: der Name dafuer hat in Starlette gewechselt
# (REQUEST_ENTITY_TOO_LARGE -> CONTENT_TOO_LARGE), die Zahl nicht.
_ZU_GROSS = 413


def verzeichnis() -> Path:
    p = Path(settings.anhang_verzeichnis)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _typ_bestimmen(kopf: bytes, gemeldet: str | None) -> str:
    """Art der Datei am Inhalt festmachen.

    Der gemeldete Content-Type entscheidet nur dort mit, wo der Inhalt keine
    Kennung traegt (Text), und auch dann nur zwischen ``text/plain`` und
    ``text/markdown``, die sich technisch nicht unterscheiden.
    """
    for mime, magien in ERLAUBTE_TYPEN.items():
        for magie in magien:
            if kopf.startswith(magie):
                # RIFF allein ist noch kein WebP, das Format steht ab Byte 8.
                if mime == "image/webp" and kopf[8:12] != b"WEBP":
                    continue
                return mime
    try:
        kopf.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Dateityp nicht erlaubt. Moeglich sind Bilder (JPEG/PNG/GIF/WebP), PDF und Text.",
        ) from None
    return "text/markdown" if (gemeldet or "").startswith("text/markdown") else "text/plain"


async def speichern(datei: UploadFile, freier_platz: int) -> tuple[str, str, int, str]:
    """Datei pruefen und ablegen.

    Rueckgabe: ``(ablage_name, mime, groesse, sha256)``.

    Die Groesse wird beim Schreiben mitgezaehlt und nicht vorab geglaubt: ein
    ``Content-Length``-Wert ist eine Behauptung des Absenders. Reisst das Limit,
    fliegt die halbe Datei sofort wieder raus.
    """
    kopf = await datei.read(16)
    await datei.seek(0)
    mime = _typ_bestimmen(kopf, datei.content_type)

    grenze = min(settings.anhang_max_bytes, freier_platz)
    if grenze <= 0:
        raise HTTPException(
            _ZU_GROSS,
            "Speicherplatz fuer Anhaenge erschoepft. Aeltere Anhaenge loeschen.",
        )

    ablage_name = uuid.uuid4().hex
    ziel = verzeichnis() / ablage_name
    hasher = hashlib.sha256()
    groesse = 0
    try:
        with open(ziel, "wb") as fh:
            while block := await datei.read(_LESEBLOCK):
                groesse += len(block)
                if groesse > grenze:
                    raise HTTPException(
                        _ZU_GROSS,
                        f"Datei ist groesser als erlaubt ({grenze // (1024 * 1024)} MiB frei).",
                    )
                hasher.update(block)
                fh.write(block)
    except Exception:
        ziel.unlink(missing_ok=True)
        raise
    if groesse == 0:
        ziel.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Leere Datei.")
    return ablage_name, mime, groesse, hasher.hexdigest()


def pfad(ablage_name: str) -> Path:
    """Pfad einer Ablage, nur ueber den in der Datenbank gefuehrten Namen.

    Der Riegel ist Absicht und kein Misstrauen gegen die eigene Datenbank: er
    haelt die Zusicherung „hier entsteht nie ein Pfad ausserhalb des
    Ablageordners" auch dann, wenn spaeter jemand einen Namen von aussen
    hereinreicht.
    """
    if not ablage_name.isalnum():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anhang nicht gefunden")
    return verzeichnis() / ablage_name


def loeschen(ablage_name: str) -> None:
    try:
        pfad(ablage_name).unlink(missing_ok=True)
    except OSError:
        pass


def platte_frei() -> int:
    """Freier Plattenplatz im Ablageordner (Bytes)."""
    st = os.statvfs(verzeichnis())
    return st.f_bavail * st.f_frsize
