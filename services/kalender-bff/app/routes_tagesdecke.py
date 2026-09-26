"""Tagesdecke-Proxy zum nativen Kalender (kalender:8085).

Die Decke überzieht den wachen Tag lückenlos: jede Minute zwischen Aufstehen und
Schlafengehen trägt einen Namen, Erholung eingeschlossen. Der native Kalender
bleibt Engine und Datenquelle, dieser BFF ist Auth-Bridge und Validierung.

★ Der Zeit-Eingang (`/api/zeit/ingest`) wird hier **nicht** durchgereicht. Er
trägt einen eigenen Token und ist für ein Messgerät gedacht, nicht für eine
angemeldete Browser-Sitzung. Ihn über den BFF zu spiegeln hieße, einen zweiten
Weg in einen Schreibpfad zu öffnen, der Bewegungsprofile entgegennimmt, und zwar
einen mit anderer Authentifizierung als der, für die er entworfen wurde.
"""
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import authed_kalender_client

router = APIRouter()

_DATE = r"^\d{4}-\d{2}-\d{2}$"
_ARTEN = r"^(fix|gewohnheit|ziel|aufgabe|training|erholung|grundlast|puffer|schlaf)$"


async def _upstream(
    method: str, path: str, *, params: dict | None = None, json: dict | None = None
) -> httpx.Response:
    async with authed_kalender_client() as client:
        try:
            r = await client.request(method, path, params=params, json=json)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    return r


@router.get("/api/tagesdecke")
async def decke(me: Me = CurrentUser, datum: str = Query(..., pattern=_DATE)) -> dict:
    """Die lückenlose Decke eines Tages."""
    r = await _upstream("GET", "/api/tagesdecke", params={"datum": datum})
    return r.json() if r.content else {}


@router.get("/api/tagesdecke/arten")
async def arten(me: Me = CurrentUser) -> dict:
    """Vokabular der Blöcke inklusive `gespiegelt` (siehe Oberfläche)."""
    r = await _upstream("GET", "/api/tagesdecke/arten")
    return r.json() if r.content else {}


@router.post("/api/tagesdecke/festschreiben")
async def festschreiben(me: Me = CurrentUser, datum: str = Query(..., pattern=_DATE)) -> dict:
    """Den Tag zum Protokoll machen, damit er korrigiert werden kann."""
    r = await _upstream("POST", "/api/tagesdecke/festschreiben", params={"datum": datum})
    return r.json() if r.content else {}


class BlockAenderung(BaseModel):
    """Eine Korrektur am Block. Nicht gesetzte Felder bleiben unverändert.

    ⚠️ Gesendet wird mit `exclude_none`, `null` heißt hier also ausdrücklich
    „nicht anfassen" und nicht „leeren". Das ist bei diesem Modell richtig, weil
    kein Feld sinnvoll leerbar ist: ein Block ohne Titel oder ohne Zeit gibt es
    nicht. Bei einem Modell mit leerbaren Feldern wäre es falsch, und genau daran
    ist die Aufgaben-App am 2026-09-13 aufgelaufen.
    """

    start: str | None = None
    ende: str | None = None
    titel: str | None = Field(default=None, min_length=1, max_length=300)
    art: str | None = Field(default=None, pattern=_ARTEN)
    status: Literal["geplant", "bestaetigt", "verworfen"] | None = None


@router.patch("/api/tagesdecke/block/{block_id}")
async def block_aendern(
    block_id: str, data: BlockAenderung, me: Me = CurrentUser
) -> dict:
    """Block verschieben, umbenennen, umwidmen oder verwerfen (Ziehen und Fallenlassen)."""
    nutzlast = data.model_dump(exclude_none=True)
    if not nutzlast:
        raise HTTPException(400, "Keine Änderung angegeben")
    r = await _upstream("PATCH", f"/api/tagesdecke/block/{block_id}", json=nutzlast)
    return r.json() if r.content else {}


class BlockNeu(BaseModel):
    datum: str = Field(..., pattern=_DATE)
    start: str
    ende: str
    art: str = Field(..., pattern=_ARTEN)
    titel: str = Field(..., min_length=1, max_length=300)
    begruendung: str | None = Field(default=None, max_length=300)


@router.post("/api/tagesdecke/block")
async def block_anlegen(data: BlockNeu, me: Me = CurrentUser) -> dict:
    """Einen Block selbst setzen, etwa das, was man stattdessen getan hat."""
    r = await _upstream("POST", "/api/tagesdecke/block", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


@router.delete("/api/tagesdecke/block/{block_id}")
async def block_verwerfen(
    block_id: str, me: Me = CurrentUser, endgueltig: bool = Query(False)
) -> dict:
    """Block aus dem Tag nehmen.

    Vorgabe ist `verworfen` und kein Löschen: was regelmäßig geplant wird und nie
    stattfindet, ist das aussagekräftigste Signal der Decke.
    """
    r = await _upstream(
        "DELETE", f"/api/tagesdecke/block/{block_id}", params={"endgueltig": endgueltig}
    )
    return r.json() if r.content else {}


class NeueOrdnung(BaseModel):
    datum: str = Field(..., pattern=_DATE)
    reihenfolge: list[str] = Field(..., min_length=1, max_length=200)


@router.post("/api/tagesdecke/neu-ordnen")
async def neu_ordnen(data: NeueOrdnung, me: Me = CurrentUser) -> dict:
    """Blöcke eines Tages umsortieren (ein Aufruf, nicht viele).

    Die Decke ist lückenlos: ein verschobener Block verschiebt alles dahinter.
    Als Folge einzelner Verschiebungen könnte der Lauf mittendrin abbrechen und
    einen Tag mit Löchern hinterlassen.
    """
    r = await _upstream("POST", "/api/tagesdecke/neu-ordnen", json=data.model_dump())
    return r.json() if r.content else {}


@router.get("/api/tagesdecke/abgleich")
async def abgleich(me: Me = CurrentUser, datum: str = Query(..., pattern=_DATE)) -> dict:
    """Soll gegen Ist für einen Tag (braucht Messdaten von einem Gerät)."""
    r = await _upstream("GET", "/api/tagesdecke/abgleich", params={"datum": datum})
    return r.json() if r.content else {}


@router.get("/api/tagesdecke/rueckblick")
async def rueckblick(
    me: Me = CurrentUser,
    von: str = Query(..., pattern=_DATE),
    bis: str = Query(..., pattern=_DATE),
) -> dict:
    """Wofür die Zeit über mehrere Tage ging, und was regelmäßig ausfällt."""
    r = await _upstream("GET", "/api/tagesdecke/rueckblick", params={"von": von, "bis": bis})
    return r.json() if r.content else {}
