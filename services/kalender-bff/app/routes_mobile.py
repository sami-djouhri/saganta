"""Routen, die die native Kalender-App braucht: Bootstrap, Tagestyp, Konto, Feed-Token.

Diese vier fehlten im BFF und waren der Grund, warum die App sich weiterhin mit
ihrem eigenen Kalender-Passwort anmelden musste statt mit dem Saganta-Konto.
``/api/mobile/bootstrap`` ist dabei der Haupt-Datenabruf: ein Aufruf, der der App
alles für den Startbildschirm liefert.

★ **Der Feed-Token ist der heikle Teil dieser Datei.** Siehe Kommentar dort.
"""
from datetime import date as _date

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .config import settings
from .upstream import upstream

router = APIRouter()

_DATE = r"^\d{4}-\d{2}-\d{2}$"
# Der native Kalender verlangt exakt dieses Wort (backend/account.py).
_LOESCH_BESTAETIGUNG = "KONTO LOESCHEN"


def _tag(iso: str) -> _date:
    """``YYYY-MM-DD`` → date. Das Muster ``_DATE`` hat die Form bereits geprüft,
    einen unmöglichen Tag (2026-02-30) fängt erst ``fromisoformat`` ab."""
    try:
        return _date.fromisoformat(iso)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Kein gültiges Datum: {iso}") from e


@router.get("/api/mobile/bootstrap")
async def bootstrap(
    me: Me = CurrentUser,
    start: str = Query(..., pattern=_DATE),
    end: str = Query(..., pattern=_DATE),
) -> dict:
    """Startbildschirm-Daten der App in einem Aufruf (Zeitfenster ``start``…``end``).

    ★ Diese Route reichte bis 2026-08-24 einen Parameter ``date`` durch, den es
    stromaufwärts nicht gibt: der native ``/api/mobile/bootstrap`` verlangt
    ``start`` UND ``end`` (beide required, siehe dessen OpenAPI). Sie antwortete
    deshalb **immer** 422, mit ``date`` genauso wie ohne, weil in beiden Fällen
    die zwei Pflichtparameter fehlten. Gemessen am 2026-08-24 mit gültigem Token:
    ``{"detail":"kalender error: … missing … query.start"}``.

    Aufgefallen ist das nie, weil die native App weiterhin direkt am Kalender
    hängt und den BFF-Weg noch nicht geht, die Route wurde für den geplanten
    Umstieg vorgebaut und dabei kein einziges Mal aufgerufen. Sie ist zugleich der
    Haupt-Datenabruf des Startbildschirms: Der Umstieg wäre unmittelbar an ihr
    gescheitert. Der Parameter heisst jetzt so wie stromaufwärts; die App sendet
    bereits ``start``/``end`` (``KalenderRepository.bootstrap``).
    """
    if end < start:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "end muss auf oder nach start liegen."
        )
    # Fenstergrenze wie stromaufwärts (dort 120 Tage), hier gespiegelt, damit ein
    # zu grosser Bereich als klare Meldung zurückkommt statt als weitergereichter
    # Upstream-Fehler, dessen Ursache im Aufrufer liegt.
    if (_tag(end) - _tag(start)).days > 120:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Zeitraum darf 120 Tage nicht überschreiten."
        )
    r = await upstream("GET", "/api/mobile/bootstrap", params={"start": start, "end": end})
    return r.json() if r.content else {}


# ── Tagestyp ─────────────────────────────────────────────────────────────
class DayTypeIn(BaseModel):
    """Tagestyp setzen.

    ⚠️ Das ist der Wert, aus dem die Weckzeit folgt: Home Assistant pollt ihn und
    schaltet danach das Morgenlicht (05:35 Arbeit / 06:06 Schule / 08:00 frei).
    Die erlaubten Werte sind bewusst hier aufgezählt statt durchgereicht, ein
    Tippfehler soll mit 422 scheitern und nicht als unbekannter Typ im Kalender
    landen, wo er stillschweigend als „frei" gälte.
    """
    date: str = Field(..., pattern=_DATE)
    day_type: str = Field(..., pattern=r"^(arbeit|schule|urlaub|krank|frei)$")


@router.post("/api/day-type/set")
async def set_day_type(data: DayTypeIn, me: Me = CurrentUser) -> dict:
    r = await upstream("POST", "/api/day-type/set", json=data.model_dump())
    return r.json() if r.content else {}


# ── Feed-Token ───────────────────────────────────────────────────────────
@router.get("/api/feed-token")
async def feed_token(me: Me = CurrentUser) -> dict:
    """Feed-Token für iCal-Abos, **nur für den Owner**.

    ★★ Warum hier ein eigener Riegel steht, obwohl der BFF bereits ein Owner-Gate
    (``allowed_subs``) hat:

    Der Feed-Token liegt im nativen Kalender in der Tabelle ``Setting``, und die ist
    **bewusst nicht mandantengetrennt** (sie hält auch das Passwort; tenantisiert
    bräche sie die CORE-Auth). Der native Endpunkt liefert deshalb JEDEM Aufrufer
    denselben Token, den des Owners. Und wer diesen Token hat, ist Owner: er öffnet
    ``/api/auth/token-login`` und damit den ganzen Kalender, und im nginx dient er
    als Auto-Login-Ticket.

    Ein blosser Durchreicher wäre also so lange harmlos, wie ``allowed_subs``
    ausschliesslich den Owner enthält, eine Konfigurationszeile, die niemand als
    sicherheitskritisch erkennt. Da „Saganta multiuser-first" erklärtes Ziel ist,
    wäre das eine Mine mit Zeitzünder: Sobald der erste Fremdnutzer freigeschaltet
    wird, bekäme er über diesen Endpunkt Owner-Rechte am Kalender.

    Deshalb: fail-closed gegen einen ausdrücklich konfigurierten Owner-``sub``. Ist
    ``kalender_owner_sub`` nicht gesetzt, antwortet die Route 503 statt zu raten.
    """
    owner = settings.kalender_owner_sub
    if not owner:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Feed-Token nicht verfügbar: KALENDER_OWNER_SUB ist nicht konfiguriert.",
        )
    if me.sub != owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Der Feed-Token gehört dem Kalender-Eigentümer und ist nicht mandantenbezogen.",
        )
    r = await upstream("GET", "/api/feed-token")
    return r.json() if r.content else {}


# ── Konto (DSGVO) ────────────────────────────────────────────────────────
@router.get("/api/account/summary")
async def account_summary(me: Me = CurrentUser) -> dict:
    """Was ist über mich gespeichert (Transparenz)."""
    r = await upstream("GET", "/api/account/summary")
    return r.json() if r.content else {}


@router.get("/api/account/export")
async def account_export(me: Me = CurrentUser) -> dict:
    """Vollständiger Datenexport (Art. 20 DSGVO)."""
    r = await upstream("GET", "/api/account/export")
    return r.json() if r.content else {}


class KontoLoeschen(BaseModel):
    confirm: str


@router.post("/api/account/delete")
async def account_delete(data: KontoLoeschen, me: Me = CurrentUser) -> dict:
    """Löscht die Kalenderdaten dieses Mandanten (Art. 17 DSGVO).

    ⚠️ **Umfang:** Das löscht die Daten in DIESER Engine: Termine, Aufgaben, Ziele,
    Kontakte, Gewohnheiten, Check-ins, Aktivitätsbewertungen. Es löscht **nicht**
    das Saganta-Konto selbst (better-auth) und nicht die Daten anderer Saganta-Apps.
    Die Ausweitung auf „Konto löschen löscht alles" ist beschlossen, aber noch nicht
    gebaut; bis dahin darf die App hier nicht „Saganta-Konto löschen" beschriften,
    sonst verspricht sie mehr, als geschieht.

    Die Bestätigung wird bereits hier geprüft, damit ein versehentlicher Aufruf ohne
    Bestätigungswort gar nicht erst am nativen Dienst ankommt.
    """
    if (data.confirm or "").strip().upper() != _LOESCH_BESTAETIGUNG:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f'Bestätigung erforderlich: sende confirm="{_LOESCH_BESTAETIGUNG}".',
        )
    r = await upstream("POST", "/api/account/delete", json={"confirm": data.confirm})
    return r.json() if r.content else {}
