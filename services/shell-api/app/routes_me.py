from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .auth import CurrentUser
from .db import get_db
from .models import UserSettings
from .registry import apps_fuer
from .schemas import AppEntry, Me, SettingsOut, SettingsPatch

router = APIRouter()


@router.get("/me", response_model=Me)
def me(user: Me = CurrentUser) -> Me:
    return user


@router.get("/apps", response_model=list[AppEntry])
def list_apps(
    user: Me = CurrentUser,
    db: Session = Depends(get_db),
    raum: str | None = Query(
        default=None,
        max_length=253,
        description=(
            "Host der Anfrage im Frontend (z. B. `home.arpa`). Die Kachel-Adressen "
            "entstehen darin, damit ein Klick nicht aus dem Raum herausfuehrt, in dem "
            "der Nutzer gerade angemeldet ist. Ohne Angabe gilt der oeffentliche Raum."
        ),
    ),
) -> list[AppEntry]:
    s = db.get(UserSettings, user.sub)
    apps = apps_fuer(raum)
    if s and s.pinned_apps:
        pinned_set = set(s.pinned_apps)
        apps.sort(key=lambda a: (0 if a.id in pinned_set else 1, a.name))
    return apps


@router.get("/settings", response_model=SettingsOut)
def get_settings(user: Me = CurrentUser, db: Session = Depends(get_db)) -> SettingsOut:
    s = db.get(UserSettings, user.sub)
    if not s:
        return SettingsOut(theme="dark", locale="de-DE", pinned_apps=[])
    return SettingsOut(theme=s.theme, locale=s.locale, pinned_apps=s.pinned_apps or [])


@router.patch("/settings", response_model=SettingsOut)
def patch_settings(
    patch: SettingsPatch,
    user: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> SettingsOut:
    s = db.get(UserSettings, user.sub) or UserSettings(sub=user.sub)
    if patch.theme is not None:
        s.theme = patch.theme
    if patch.locale is not None:
        s.locale = patch.locale
    if patch.pinned_apps is not None:
        s.pinned_apps = patch.pinned_apps
    db.add(s)
    db.commit()
    db.refresh(s)
    return SettingsOut(theme=s.theme, locale=s.locale, pinned_apps=s.pinned_apps or [])
