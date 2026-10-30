"""Kontakte-Proxy zum nativen Kalender (kalender:8085).

Kontakte fehlten im BFF vollständig, die native App verwaltet sie, das Saganta-
Frontend kam nicht heran. Beim Umstieg der App aufs Saganta-Konto wäre damit
Funktion verloren gegangen, deshalb hier nachgezogen.

⚠️ **Ein Kontakt ist nicht nur ein Adressbucheintrag:** Trägt er ein Geburtsdatum,
erzeugt der native Kalender daraus Termine im System-Kalender „Geburtstage", und
zwar durch **vollständige Neuerzeugung aller** Geburtstagstermine bei jeder
Kontaktänderung (`birthday_utils`). Das ist beim nativen Dienst so gewollt und
idempotent; hier ist nur wichtig zu wissen, dass ein PUT auf einen Kontakt mehr
anfasst als die eine Zeile.

Der native Kalender bleibt Datenquelle und validiert erneut; die Schemata hier
spiegeln seine Constraints (defense in depth).
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import upstream

router = APIRouter()

_DATE = r"^\d{4}-\d{2}-\d{2}$"


class ContactIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    birthday: str | None = Field(default=None, pattern=_DATE)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


class ContactPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    birthday: str | None = Field(default=None, pattern=_DATE)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)


@router.get("/api/contacts")
async def list_contacts(me: Me = CurrentUser) -> list:
    r = await upstream("GET", "/api/contacts")
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/contacts", status_code=201)
async def create_contact(data: ContactIn, me: Me = CurrentUser) -> dict:
    r = await upstream("POST", "/api/contacts", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


@router.put("/api/contacts/{contact_id}")
async def update_contact(
    contact_id: str, data: ContactPatch, me: Me = CurrentUser
) -> dict:
    r = await upstream(
        "PUT", f"/api/contacts/{contact_id}", json=data.model_dump(exclude_none=True)
    )
    return r.json() if r.content else {}


@router.delete("/api/contacts/{contact_id}", status_code=204)
async def delete_contact(contact_id: str, me: Me = CurrentUser) -> None:
    await upstream("DELETE", f"/api/contacts/{contact_id}")
