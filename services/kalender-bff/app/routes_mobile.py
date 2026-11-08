"""Routen, die die native Kalender-App braucht: Bootstrap, Tagestyp, Konto, Feed-Token.

Diese vier fehlten im BFF und waren der Grund, warum die App sich weiterhin mit
ihrem eigenen Kalender-Passwort anmelden musste statt mit dem Saganta-Konto.
``/api/mobile/bootstrap`` ist dabei der Haupt-Datenabruf: ein Aufruf, der der App
alles für den Startbildschirm liefert.

**Der Feed-Token ist der heikle Teil dieser Datei.** Siehe Kommentar dort.
"""
from datetime import date as _date

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import upstream

router = APIRouter()

_DATE = r"^\d{4}-\d{2}-\d{2}$"
# HH:MM. Die eigentliche Pruefung (bis nach von, nur Arbeit/Schule) macht der
# native Dienst; hier nur die Form, damit ein Tippfehler mit 422 scheitert.
_UHRZEIT = r"^([01]\d|2[0-3]):[0-5]\d$"
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

    Diese Route reichte bis 2026-08-24 einen Parameter ``date`` durch, den es
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
    # Eigene Zeitgrenze (Befund 2026-11-03): der native Bootstrap brauchte
    # 4,7 bis 5,6 s fuer das 81-Tage-Fenster der App, die Vorgabe sind 5 s. Die
    # App bekam deshalb beim Oeffnen meist ein 502 und musste „Erneut" druecken.
    # Die Rechenzeit ist im Kalender behoben (Tagestypen in einer Abfrage); die
    # Grenze bleibt hoeher, weil der Dienst mit 0,25 CPU laeuft.
    r = await upstream(
        "GET", "/api/mobile/bootstrap", params={"start": start, "end": end}, timeout=30.0
    )
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
    half: bool = False
    #: Eigene Arbeits-/Schulzeit fuer genau diesen Tag (seit 2026-10-30). Mit
    #: Uhrzeiten wird gesetzt statt umgeschaltet.
    von: str | None = Field(None, pattern=_UHRZEIT)
    bis: str | None = Field(None, pattern=_UHRZEIT)


def _zeiten(params: dict, von: str | None, bis: str | None, namen: tuple[str, str]) -> dict:
    """Uhrzeiten nur mitschicken, wenn sie gesetzt sind: ein leerer Wert waere
    stromaufwaerts ein 400, und ohne Angabe gilt dort die Wochenvorgabe."""
    if von is not None:
        params[namen[0]] = von
    if bis is not None:
        params[namen[1]] = bis
    return params


@router.post("/api/day-type/set")
async def set_day_type(data: DayTypeIn, me: Me = CurrentUser) -> dict:
    """Tagestyp eines einzelnen Tages.

    **Hier stand bis zum 2026-10-20 ``json=data.model_dump()``, und damit kam
    stromaufwärts nichts an.** Der native ``POST /api/day-type/set`` nimmt
    ``date`` und ``type`` als **Query**-Parameter (``Query(..., alias="type")``);
    ein JSON-Rumpf erfüllt einen Pflicht-Query-Parameter nicht, der Aufruf endete
    also in 422 „Field required". Dieselbe Fehlerklasse wie beim ``date`` in
    ``/api/mobile/bootstrap`` eine Funktion weiter oben, und aus demselben Grund
    unbemerkt: die native App hing bis zum Umstieg direkt am Kalender.

    ⚠️ Der Feldname ändert sich dabei: ``day_type`` hier, ``type`` dort. Das
    bleibt so, weil ``type`` in einem Pydantic-Modell das eingebaute ``type``
    verdeckt; die Übersetzung steht an dieser einen Stelle.
    """
    r = await upstream("POST", "/api/day-type/set", params=_zeiten({
        "date": data.date,
        "type": data.day_type,
        "half": str(data.half).lower(),
    }, data.von, data.bis, ("von", "bis")))
    return r.json() if r.content else {}


class DayTypeRangeIn(BaseModel):
    """Tagestyp für einen ganzen Zeitraum.

    Der Anlass ist eine Frage: Urlaub und Arbeitszeiten waren nur Tag für
    Tag einzutragen, drei Wochen Urlaub also einundzwanzig Aufrufe über eine
    Mobilverbindung.

    ``frei`` ist hier erlaubt und bedeutet **leeren**; der Einzel-Endpunkt
    stromaufwärts kennt das nicht, weil er umschaltet.
    """
    von: str = Field(..., pattern=_DATE)
    bis: str = Field(..., pattern=_DATE)
    day_type: str = Field(..., pattern=r"^(arbeit|schule|urlaub|krank|frei)$")
    half: bool = False
    nur_wochentage: bool = True
    #: Arbeits-/Schulzeit fuer jeden Tag des Zeitraums. Stromaufwaerts heissen
    #: sie ``von_zeit``/``bis_zeit``, weil ``von``/``bis`` dort die Daten sind.
    von_zeit: str | None = Field(None, pattern=_UHRZEIT)
    bis_zeit: str | None = Field(None, pattern=_UHRZEIT)


@router.post("/api/day-type/set-range")
async def set_day_type_range(data: DayTypeRangeIn, me: Me = CurrentUser) -> dict:
    if data.bis < data.von:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bis muss auf oder nach von liegen.")
    if (_tag(data.bis) - _tag(data.von)).days > 366:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Zeitraum darf 366 Tage nicht überschreiten."
        )
    r = await upstream("POST", "/api/day-type/set-range", params=_zeiten({
        "von": data.von,
        "bis": data.bis,
        "type": data.day_type,
        "half": str(data.half).lower(),
        "nur_wochentage": str(data.nur_wochentage).lower(),
    }, data.von_zeit, data.bis_zeit, ("von_zeit", "bis_zeit")))
    return r.json() if r.content else {}


@router.get("/api/day-type/week-schedule")
async def wochenplan(me: Me = CurrentUser, week_start: str = Query(..., pattern=_DATE)) -> list:
    """Sieben Tage ab ``week_start``: Tagestyp, Aufstehen, Bett und Arbeits-/Schulblock.

    Seit 2026-11-07 fuer den Nachtmodus des Saganta Launchers: die Kalender-App
    holt den Plan nach jedem Abgleich und reicht ihn auf dem Telefon weiter. Die
    Aufstehzeit je Tagestyp steht nur im nativen Dienst (``sleep_schedule``);
    hier wird sie nicht nachgebaut, damit es eine Quelle bleibt.
    """
    _tag(week_start)
    r = await upstream("GET", "/api/day-type/week-schedule", params={"week_start": week_start})
    return r.json() if r.content else []


@router.get("/api/day-type/urlaub-bilanz")
async def urlaub_bilanz(me: Me = CurrentUser, jahr: int = Query(...)) -> dict:
    """Urlaubskonto eines Jahres: genommen, geplant, Rest, Vorjahresrest.

    Anspruch und Verfall liegen seit dem 2026-11-07 im nativen Dienst
    (`/urlaub-einstellung`), damit App und Web dieselbe Zahl zeigen.
    """
    r = await upstream("GET", "/api/day-type/urlaub-bilanz", params={"jahr": str(jahr)})
    return r.json() if r.content else {}


@router.get("/api/day-type/urlaub-einstellung")
async def urlaub_einstellung(me: Me = CurrentUser) -> dict:
    r = await upstream("GET", "/api/day-type/urlaub-einstellung")
    return r.json() if r.content else {}


class UrlaubEinstellungIn(BaseModel):
    anspruch: float | None = Field(None, ge=0, le=100)
    verfall: str | None = Field(None, pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


@router.put("/api/day-type/urlaub-einstellung")
async def urlaub_einstellung_setzen(data: UrlaubEinstellungIn, me: Me = CurrentUser) -> dict:
    """Ein nicht geschicktes Feld bleibt; ``anspruch: null`` leert den Anspruch."""
    r = await upstream("PUT", "/api/day-type/urlaub-einstellung",
                       json=data.model_dump(exclude_unset=True))
    return r.json() if r.content else {}


# ── Stundenplan (seit 2026-11-07) ────────────────────────────────────────
@router.get("/api/day-type/stundenplan")
async def stundenplan(me: Me = CurrentUser) -> dict:
    r = await upstream("GET", "/api/day-type/stundenplan")
    return r.json() if r.content else {}


class StundeIn(BaseModel):
    fach: str = Field(..., min_length=1, max_length=60)
    von: str = Field(..., pattern=_UHRZEIT)
    bis: str = Field(..., pattern=_UHRZEIT)


class StundenplanIn(BaseModel):
    #: Wochentag "0" (Montag) bis "6"; ein nicht genannter bleibt.
    stunden: dict[str, list[StundeIn]]


@router.put("/api/day-type/stundenplan")
async def stundenplan_setzen(data: StundenplanIn, me: Me = CurrentUser) -> dict:
    r = await upstream("PUT", "/api/day-type/stundenplan", json=data.model_dump())
    return r.json() if r.content else {}


class AusfallIn(BaseModel):
    datum: _date
    von: str = Field(..., pattern=_UHRZEIT)
    ausgefallen: bool = True


@router.post("/api/day-type/stundenplan/ausfall")
async def stundenplan_ausfall(data: AusfallIn, me: Me = CurrentUser) -> dict:
    """Kuerzt an einem Schultag dessen Zeiten (nativer Dienst, `_tagestyp_setzen`)."""
    r = await upstream("POST", "/api/day-type/stundenplan/ausfall",
                       json={"datum": data.datum.isoformat(), "von": data.von, "ausgefallen": data.ausgefallen})
    return r.json() if r.content else {}


# ── Zeitkonto (seit 2026-11-07) ──────────────────────────────────────────
@router.get("/api/day-type/zeitkonto")
async def zeitkonto(me: Me = CurrentUser) -> dict:
    r = await upstream("GET", "/api/day-type/zeitkonto")
    return r.json() if r.content else {}


class ZeitkontoPlanTag(BaseModel):
    wochentag: int = Field(..., ge=0, le=6)
    soll: int | None = Field(None, ge=0, le=1440)
    pause: int | None = Field(None, ge=0, le=1440)


class ZeitkontoPlanIn(BaseModel):
    tage: list[ZeitkontoPlanTag]


@router.put("/api/day-type/zeitkonto/plan")
async def zeitkonto_plan(data: ZeitkontoPlanIn, me: Me = CurrentUser) -> dict:
    r = await upstream("PUT", "/api/day-type/zeitkonto/plan",
                       json={"tage": [t.model_dump(exclude_none=True) for t in data.tage]})
    return r.json() if r.content else {}


class ZeitkontoEintragIn(BaseModel):
    art: str = Field("arbeit", pattern=r"^(arbeit|ausgleich|krank_frueher)$")
    von: str | None = Field(None, pattern=_UHRZEIT)
    bis: str | None = Field(None, pattern=_UHRZEIT)
    ist: int | None = Field(None, ge=0, le=1440)
    notiz: str | None = Field(None, max_length=200)


@router.put("/api/day-type/zeitkonto/eintrag/{tag}")
async def zeitkonto_eintrag(tag: _date, data: ZeitkontoEintragIn, me: Me = CurrentUser) -> dict:
    r = await upstream("PUT", f"/api/day-type/zeitkonto/eintrag/{tag.isoformat()}",
                       json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


@router.delete("/api/day-type/zeitkonto/eintrag/{tag}", status_code=204)
async def zeitkonto_eintrag_loeschen(tag: _date, me: Me = CurrentUser) -> None:
    await upstream("DELETE", f"/api/day-type/zeitkonto/eintrag/{tag.isoformat()}")


@router.get("/api/day-type/arbeitszeiten")
async def arbeitszeiten(me: Me = CurrentUser) -> dict:
    """Wochenvorgabe fuer neue Arbeits- und Schultage (0 = Montag)."""
    r = await upstream("GET", "/api/day-type/arbeitszeiten")
    return r.json() if r.content else {}


class ArbeitszeitTag(BaseModel):
    wochentag: int = Field(..., ge=0, le=6)
    von: str = Field(..., pattern=_UHRZEIT)
    bis: str = Field(..., pattern=_UHRZEIT)


class ArbeitszeitenIn(BaseModel):
    """Ein fehlender Typ bleibt stromaufwaerts unveraendert, deshalb optional."""
    arbeit: list[ArbeitszeitTag] | None = None
    schule: list[ArbeitszeitTag] | None = None


@router.put("/api/day-type/arbeitszeiten")
async def arbeitszeiten_setzen(data: ArbeitszeitenIn, me: Me = CurrentUser) -> dict:
    """Wirkt nur auf Tage, die danach angelegt werden; eingetragene behalten
    ihre Uhrzeit (die liegt im Ereignis, und daraus liest Home Assistant)."""
    r = await upstream("PUT", "/api/day-type/arbeitszeiten",
                       json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


# ── Feed-Token ───────────────────────────────────────────────────────────
@router.get("/api/feed-token")
async def feed_token(me: Me = CurrentUser) -> dict:
    """Der Feed-Token **dieses** Mandanten für iCal-Abos.

    Hier stand bis zum 2026-10-16 ein eigener Owner-Riegel, und er ist
    ersatzlos entfallen. Die Begründung dafür war richtig und ist weggefallen:

    Der Feed-Token lag ausschliesslich in der bewusst nicht mandantengetrennten
    Tabelle ``Setting``, der native Endpunkt gab deshalb **jedem** denselben,
    nämlich den des Owners, und wer ihn hat, öffnet über ``token-login`` dessen
    ganzen Kalender. Ein blosser Durchreicher war also nur so lange harmlos, wie
    ``allowed_subs`` ausschliesslich den Owner enthielt.

    Der native Dienst hat das am 2026-09-27 geschlossen (``mandant_einstellungen``,
    ``feed_token_fuer``): jeder Mandant hat seinen eigenen Token, der Owner behält
    seinen in ``settings``, weil daran der Weckpfad hängt. Der Riegel hier war
    damit keine zweite Sperre mehr, sondern nur noch eine Absperrung vor einer
    reparierten Brücke -- und zwar eine, die **gar nichts** mehr durchliess:
    ``KALENDER_OWNER_SUB`` war nie gesetzt, der Endpunkt antwortete also auch dem
    Owner mit 503.

    Am laufenden Dienst belegt, bevor der Riegel fiel (2026-10-16):

    * Owner und Prüfkonto bekommen **zwei verschiedene** Token.
    * Ein Gast-Token auf Ebene 1 (``day-type/today``, die Weckkette) bekommt
      **403**, der Owner-Token 200. Die Ebene bleibt Owner-exklusiv.
    * ``token-login`` mit dem Gast-Token ergibt eine Sitzung für **den Gast**,
      nicht für den Owner.
    * ``allowed_subs`` am BFF ist leer: das äussere Gate war längst offen, der
      Zeitzünder aus dem alten Kommentar also schon ausgelöst. Allein das 503
      hielt noch, und zwar für niemandes Nutzen.

    Prüfzeile danach abgeräumt; die Mandanten-Tabelle ist wieder leer.
    """
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


# ── Jahresansicht ────────────────────────────────────────────────────────
#: Kalender, deren Ereignisse den Tag BESCHREIBEN statt ihn zu belegen. Ihr
#: Ergebnis kommt als Tagestyp vom nativen Dienst; als Termin gezaehlt waere
#: jeder Arbeitstag ein Tag „mit Termin".
_TAGESTYP_PRAEFIX = "daytype-"
_FEIERTAG_KALENDER = "daytype-feiertag-0000-0000-000000000000"


def _tage_eines_termins(ev: dict, jahr: int) -> list[str]:
    """Kalendertage, die ein Termin beruehrt, beschnitten aufs Jahr.

    Ein ganztaegiger Termin endet um 00:00 des Folgetags (exklusiv), ein
    getimter, der um Mitternacht endet, ebenso; beide zaehlen den Folgetag nicht.
    """
    try:
        anfang = _date.fromisoformat(str(ev.get("start", ""))[:10])
        ende_roh = str(ev.get("end") or ev.get("start") or "")
        ende = _date.fromisoformat(ende_roh[:10])
    except ValueError:
        return []
    if ende > anfang and ende_roh[11:19] in ("", "00:00:00"):
        ende = _date.fromordinal(ende.toordinal() - 1)
    erster = max(anfang, _date(jahr, 1, 1))
    letzter = min(ende, _date(jahr, 12, 31))
    return [
        _date.fromordinal(o).isoformat()
        for o in range(erster.toordinal(), letzter.toordinal() + 1)
    ]


@router.get("/api/jahr")
async def jahr_uebersicht(me: Me = CurrentUser, jahr: int = Query(..., ge=2000, le=2100)) -> dict:
    """Ein Jahr auf einen Blick fuer die App: Tagestyp, Feiertag und Terminzahl je Tag.

    Der Tagestyp kommt fertig vom nativen Dienst (`/api/day-type/bereich`),
    hier wird er nicht aus den Terminen abgeleitet: eine zweite Ableitung waere
    eine parallele Daytype-Logik, und die laege irgendwann daneben. Gezaehlt
    werden nur Termine ausserhalb der Tagestyp-Kalender. Gemessen 2026-11-03:
    ein Jahr sind rund 0,3 s Termine plus 0,4 s Tagestypen.
    """
    anfang = _date(jahr, 1, 1)
    tage = (_date(jahr, 12, 31) - anfang).days + 1
    typen = await upstream(
        "GET", "/api/day-type/bereich",
        params={"start": anfang.isoformat(), "tage": str(tage)}, timeout=30.0,
    )
    termine = await upstream(
        "GET", "/api/events",
        params={"start": anfang.isoformat(), "end": f"{jahr}-12-31T23:59:59"}, timeout=30.0,
    )
    zahl: dict[str, int] = {}
    feiertag: dict[str, str] = {}
    for ev in (termine.json() if termine.content else []) or []:
        kalender = str(ev.get("calendar_id") or "")
        if kalender == _FEIERTAG_KALENDER:
            for tag in _tage_eines_termins(ev, jahr):
                feiertag[tag] = str(ev.get("title") or "Feiertag")
            continue
        if kalender.startswith(_TAGESTYP_PRAEFIX):
            continue
        for tag in _tage_eines_termins(ev, jahr):
            zahl[tag] = zahl.get(tag, 0) + 1
    return {
        "jahr": jahr,
        "tage": [
            {
                "date": t["date"],
                "type": t["type"],
                "termine": zahl.get(t["date"], 0),
                "feiertag": feiertag.get(t["date"]),
            }
            for t in (typen.json() if typen.content else [])
        ],
    }


# ── Tagesreview ──────────────────────────────────────────────────────────
class ReviewIn(BaseModel):
    """Abend-Rueckblick eines Tages. Leere Felder heissen „nichts eingetragen";
    der native Dienst setzt nur, was mitkommt (`exclude_unset`)."""
    what_went_well: str | None = Field(None, max_length=4000)
    blockers: str | None = Field(None, max_length=4000)
    carry_over_to_tomorrow: str | None = Field(None, max_length=4000)
    energy_level: str | None = Field(None, pattern=r"^(low|medium|high)$")


@router.get("/api/reviews/{tag}")
async def review_lesen(tag: str = Path(..., pattern=_DATE), me: Me = CurrentUser) -> dict | None:
    _tag(tag)
    r = await upstream("GET", f"/api/reviews/{tag}")
    return r.json() if r.content else None


@router.put("/api/reviews/{tag}")
async def review_schreiben(data: ReviewIn, tag: str = Path(..., pattern=_DATE), me: Me = CurrentUser) -> dict:
    """Upsert je Datum. Alle vier Felder gehen immer mit, auch leer: die App
    zeigt das ganze Formular, und ein geleertes Feld soll leer werden, statt
    stromaufwaerts den alten Text zu behalten."""
    _tag(tag)
    r = await upstream("PUT", f"/api/reviews/{tag}", json=data.model_dump())
    return r.json() if r.content else {}
