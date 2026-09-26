"""Der Tresor: verpackte Schluessel holen, einrichten, Passphrase wechseln.

Nichts hier kann den Datenschluessel oeffnen. Der Dienst gibt aus, was der
Browser ihm gegeben hat, und der Browser braucht die Passphrase oder den
Wiederherstellungsschluessel, um daraus etwas zu machen.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .auth import Me, verify_jwt
from .db import get_db
from .models import Tresor
from .schemas import PassphraseAn, TresorAn, TresorAus

router = APIRouter()


@router.get("", response_model=TresorAus)
def lesen(
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> TresorAus:
    """Die verpackten Schluessel des Mandanten.

    404 heisst hier nicht "Fehler", sondern "noch nicht eingerichtet". Die
    Oberflaeche fuehrt daraufhin durch das Einrichten.
    """
    tresor = db.get(Tresor, me.sub)
    if tresor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Noch kein Tresor eingerichtet")
    return TresorAus.model_validate(tresor)


@router.put("", response_model=TresorAus, status_code=status.HTTP_201_CREATED)
def einrichten(
    daten: TresorAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> TresorAus:
    """Den Tresor genau einmal anlegen.

    ★ Ein zweites Einrichten wird abgelehnt (409), und das ist die wichtigste
    Zeile dieses Moduls. Wuerde es den bestehenden Tresor ersetzen, waere jeder
    vorhandene Eintrag mit einem Schlag unlesbar: die Eintraege haengen am alten
    Datenschluessel, und der existiert danach nirgends mehr. Ein einziger
    versehentlicher Aufruf loeschte damit Jahre, ohne eine einzige Zeile in
    ``eintraege`` anzuruehren.

    Der Weg fuer ein vergessenes Passwort ist nicht dieser hier, sondern der
    Wiederherstellungsschluessel und danach ``POST /passphrase``.
    """
    if db.get(Tresor, me.sub) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Es gibt bereits einen Tresor. Passphrase wechseln statt neu einrichten.",
        )
    tresor = Tresor(owner_sub=me.sub, **daten.model_dump())
    db.add(tresor)
    db.commit()
    db.refresh(tresor)
    return TresorAus.model_validate(tresor)


@router.post("/passphrase", response_model=TresorAus)
def passphrase_wechseln(
    daten: PassphraseAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> TresorAus:
    """Nur den Passphrase-Zweig neu verpacken.

    Der Browser hat den Datenschluessel bereits geoeffnet, sei es mit der alten
    Passphrase oder mit dem Wiederherstellungsschluessel, und schickt ihn hier
    unter der neuen Passphrase verpackt zurueck. Der Wiederherstellungs-Zweig
    bleibt unberuehrt: ein ausgedruckter Notfallzettel soll nicht stillschweigend
    ungueltig werden, weil jemand sein Passwort geaendert hat.
    """
    tresor = db.get(Tresor, me.sub)
    if tresor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Noch kein Tresor eingerichtet")
    tresor.kdf = daten.kdf
    tresor.kdf_iterationen = daten.kdf_iterationen
    tresor.salz_passphrase = daten.salz_passphrase
    tresor.wrap_passphrase = daten.wrap_passphrase
    tresor.wrap_passphrase_iv = daten.wrap_passphrase_iv
    db.commit()
    db.refresh(tresor)
    return TresorAus.model_validate(tresor)
