"""``POST /api/assistent``: ein Eingang fuer alle Apps.

Vertrag wie im Kalender (``kalender-bff/ASSISTENT_VERTRAG.md``): die App
schickt Nachricht und Verlauf bis zum Schliessen, zurueck kommen ein Satz,
Vorschlagskarten und die verworfenen Wuensche mit Grund. Hier wird nichts
gespeichert und nichts geschrieben.

Welche App gemeint ist, sagt das Feld ``app``; jede bringt ihr Werkzeug mit
(``werkzeuge/<app>.py``). Der Kalender laeuft bis zu seinem Umzug weiter ueber
den kalender-bff.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import modell
from .auth import AktuellerNutzer, Me, token_fuer
from .config import settings
from .werkzeuge import mealprep

router = APIRouter()

WARTEZEIT_S = 30.0


class Zeile(BaseModel):
    rolle: str = Field(..., pattern=r"^(nutzer|assistent)$")
    text: str = Field(..., max_length=2000)


class AssistentIn(BaseModel):
    nachricht: str = Field(..., min_length=1, max_length=1000)
    #: Verlauf nur bis zum Schliessen des Blatts, gekappt gegen ein volles Fenster.
    verlauf: list[Zeile] = Field(default_factory=list, max_length=20)
    app: str = Field(..., pattern=r"^mealprep$")


def holer(me: Me, basis: str, zielgruppe: str):
    """GET an eine App im Namen des Aufrufers, mit frisch gestempeltem Token."""

    async def holen(pfad: str, **kw: Any) -> Any:
        try:
            async with httpx.AsyncClient(base_url=basis, timeout=WARTEZEIT_S) as klient:
                r = await klient.get(pfad, headers={"Authorization": f"Bearer {token_fuer(me, zielgruppe)}"}, **kw)
        except httpx.HTTPError as e:
            raise mealprep.AbrufFehler(f"nicht erreichbar ({type(e).__name__})") from e
        if r.status_code >= 400:
            raise mealprep.AbrufFehler(f"HTTP {r.status_code}")
        return r.json() if r.content else None

    return holen


@router.post("/api/assistent")
async def assistent(data: AssistentIn, me: Me = AktuellerNutzer) -> dict:
    name = modell.modell()
    verlauf = [(z.rolle, z.text) for z in data.verlauf]

    async def frage(kontext: str) -> dict:
        return await modell.fragen(name, mealprep.SYSTEM, mealprep.SCHEMA, "mealprep_aktionen",
                                   verlauf, kontext, data.nachricht)

    holen = holer(me, settings.mealprep_url, mealprep.ZIELGRUPPE)
    try:
        ergebnis = await mealprep.beantworten(
            holen, _date.today(), datetime.now().strftime("%H:%M"), data.nachricht, frage,
            frueher=[z.text for z in data.verlauf if z.rolle == "nutzer"],
        )
    except mealprep.AbrufFehler as e:
        raise HTTPException(502, f"MealPrep: {e}") from e
    return {**ergebnis, "modell": name}
