"""Die Eintraege: lesen, schreiben, loeschen.

Jede Abfrage filtert auf ``owner_sub``. Es gibt keinen Pfad ohne diesen Filter.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import Me, verify_jwt
from .db import get_db
from .models import Eintrag
from .schemas import EintragAn, EintragAus, TagAus

router = APIRouter()

#: Wie viele Tage eine einzelne Abfrage umspannen darf. Der Browser laedt
#: jahrweise nach, wenn er mehr braucht. Ohne Deckel zoege ein einziger Aufruf
#: den gesamten Bestand in eine Antwort, und das waechst mit den Jahren still.
MAX_SPANNE_TAGE = 400

#: Wie weit ein Eintrag in der Zukunft liegen darf. Ein Tag Puffer deckt die
#: Zeitzone ab (der Wirt rechnet in UTC, geschrieben wird in Berlin). Alles
#: darueber ist ein Vertipper, und ein Eintrag im Jahr 9999 zerreisst die
#: Datumsleiste, ohne dass jemand den Grund sieht.
ZUKUNFT_PUFFER_TAGE = 1
FRUEHESTES_JAHR = 1900


def _pruefe_datum(tag: date) -> None:
    if tag.year < FRUEHESTES_JAHR:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Datum liegt zu weit zurueck")
    if tag > date.today() + timedelta(days=ZUKUNFT_PUFFER_TAGE):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Datum liegt in der Zukunft")


# ★ Reihenfolge: "/tage" muss vor "/{datum}" stehen. Andersherum versucht
# FastAPI, das Wort "tage" als Datum zu lesen, und die Uebersicht antwortet mit
# 422 statt mit Daten. Der Test test_uebersicht_kollidiert_nicht_mit_datum haelt
# das fest, denn beim Lesen faellt es nicht auf.
@router.get("/tage", response_model=list[TagAus])
def uebersicht(
    jahr: int = Query(ge=FRUEHESTES_JAHR, le=2999),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[TagAus]:
    """Welche Tage etwas enthalten, ohne den Inhalt.

    Traegt die Datumsleiste. Der Rueckgabewert ist bewusst schmal: ein Datum,
    die Laenge des Chiffrats und wann zuletzt geschrieben wurde.
    """
    zeilen = db.execute(
        select(Eintrag.datum, Eintrag.chiffrat, Eintrag.geaendert_am)
        .where(
            Eintrag.owner_sub == me.sub,
            Eintrag.datum >= date(jahr, 1, 1),
            Eintrag.datum <= date(jahr, 12, 31),
        )
        .order_by(Eintrag.datum)
    ).all()
    return [
        TagAus(datum=d, zeichen=len(c or ""), geaendert_am=g) for d, c, g in zeilen
    ]


@router.get("", response_model=list[EintragAus])
def liste(
    von: date,
    bis: date,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[EintragAus]:
    """Alle Eintraege einer Spanne, mitsamt Chiffrat.

    Der Weg, auf dem die Suche im Browser an ihr Material kommt: entschluesselt
    wird dort, nicht hier.
    """
    if bis < von:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "bis liegt vor von")
    if (bis - von).days > MAX_SPANNE_TAGE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Spanne zu gross, hoechstens {MAX_SPANNE_TAGE} Tage je Abfrage",
        )
    eintraege = db.scalars(
        select(Eintrag)
        .where(Eintrag.owner_sub == me.sub, Eintrag.datum >= von, Eintrag.datum <= bis)
        .order_by(Eintrag.datum)
    ).all()
    return [EintragAus.model_validate(e) for e in eintraege]


@router.get("/{datum}", response_model=EintragAus)
def lesen(
    datum: date,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> EintragAus:
    eintrag = db.get(Eintrag, (me.sub, datum))
    if eintrag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Eintrag an diesem Tag")
    return EintragAus.model_validate(eintrag)


@router.put("/{datum}", response_model=EintragAus)
def speichern(
    datum: date,
    daten: EintragAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> EintragAus:
    """Upsert je Tag.

    Ein Tag, ein Eintrag. Wer denselben Tag erneut schickt, ueberschreibt ihn,
    denn ein Tagebuch fuehrt keine Fassungen, sondern einen Text je Tag.
    """
    _pruefe_datum(datum)
    eintrag = db.get(Eintrag, (me.sub, datum))
    if eintrag is None:
        eintrag = Eintrag(owner_sub=me.sub, datum=datum)
        db.add(eintrag)
    eintrag.chiffrat = daten.chiffrat
    eintrag.iv = daten.iv
    eintrag.schluessel_version = daten.schluessel_version
    db.commit()
    db.refresh(eintrag)
    return EintragAus.model_validate(eintrag)


@router.delete("/{datum}", status_code=status.HTTP_204_NO_CONTENT)
def loeschen(
    datum: date,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> None:
    eintrag = db.get(Eintrag, (me.sub, datum))
    if eintrag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Eintrag an diesem Tag")
    db.delete(eintrag)
    db.commit()
