from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import Me, verify_jwt
from .db import get_db
from .helfer import notizbuch_aus
from .models import Notiz, Notizbuch
from .schemas import NotizbuchAn, NotizbuchAus

router = APIRouter()


@router.get("", response_model=list[NotizbuchAus])
def liste(
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[NotizbuchAus]:
    buecher = db.scalars(
        select(Notizbuch)
        .where(Notizbuch.owner_sub == me.sub)
        .order_by(Notizbuch.sortierung, Notizbuch.name)
    ).all()
    zaehler = dict(
        db.execute(
            select(Notiz.notizbuch_id, func.count())
            .where(Notiz.owner_sub == me.sub, Notiz.archiviert.is_(False))
            .group_by(Notiz.notizbuch_id)
        ).all()
    )
    return [notizbuch_aus(b, zaehler.get(b.id, 0)) for b in buecher]


@router.post("", response_model=NotizbuchAus, status_code=status.HTTP_201_CREATED)
def anlegen(
    daten: NotizbuchAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> NotizbuchAus:
    buch = Notizbuch(
        owner_sub=me.sub,
        name=daten.name.strip(),
        farbe=daten.farbe,
        sortierung=daten.sortierung,
    )
    db.add(buch)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ein Notizbuch mit diesem Namen existiert bereits."
        ) from None
    db.refresh(buch)
    return notizbuch_aus(buch)


@router.put("/{buch_id}", response_model=NotizbuchAus)
def aendern(
    buch_id: int,
    daten: NotizbuchAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> NotizbuchAus:
    buch = db.scalar(
        select(Notizbuch).where(Notizbuch.id == buch_id, Notizbuch.owner_sub == me.sub)
    )
    if buch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notizbuch nicht gefunden")
    buch.name = daten.name.strip()
    buch.farbe = daten.farbe
    buch.sortierung = daten.sortierung
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ein Notizbuch mit diesem Namen existiert bereits."
        ) from None
    db.refresh(buch)
    return notizbuch_aus(buch)


@router.delete("/{buch_id}", status_code=status.HTTP_204_NO_CONTENT)
def loeschen(
    buch_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> None:
    """Notizbuch entfernen, die Notizen darin bleiben.

    Ein Ordner ist eine Einsortierung, kein Behaelter: wer ihn wegraeumt, will
    Ordnung aendern und nicht Inhalte verlieren. Die Notizen landen wieder in
    „Ohne Notizbuch" (Fremdschluessel steht auf SET NULL).
    """
    buch = db.scalar(
        select(Notizbuch).where(Notizbuch.id == buch_id, Notizbuch.owner_sub == me.sub)
    )
    if buch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notizbuch nicht gefunden")
    db.delete(buch)
    db.commit()
