"""Gliederung, beteiligte Kontakte und die Projektakte (2026-11-15).

Die Akte ist die eine Antwort auf „was gehoert zu diesem Projekt": offene
Aufgaben (mit ihren Notizen), Termine und Fristen als eine Zeitleiste,
beteiligte Kontakte, Budget und Notizen. Ein Oberprojekt zeigt dabei alles,
was an ihm selbst und an seinen Nachfahren haengt (Entscheid U4),
gruppiert ueber das Feld ``projekt`` jedes Eintrags.

Web, App und Werkzeuge lesen dieselbe Route; es gibt keine zweite Sicht.
"""
from __future__ import annotations

from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import aufgaben_dienst, gliederung, nachbarn
from .auth import CurrentUser, Me
from .db import get_db
from .models import Project, ProjectKontakt, ProjectMilestone
from .schemas import ElternIn, KontaktVerweisIn, KontaktVerweisPatch, ProjectOut
from .util import today

router = APIRouter()

#: So weit zurueck und voraus reicht die Zeitleiste.
TAGE_ZURUECK = 30
TAGE_VORAUS = 365


def _eigenes(db: Session, me: Me, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p or p.owner != me.sub:
        raise HTTPException(404, "project not found")
    return p


def _kurz(p: Project) -> dict:
    return {"id": p.id, "slug": p.slug, "name": p.name, "status": p.status}


def mit_gliederung(db: Session, me: Me, projekte: list[Project]) -> dict[int, dict[str, list[int]]]:
    """Direkte Eltern und Kinder je Projekt, fuer ``ProjectOut``."""
    eltern, kinder = gliederung.eltern_und_kinder(db, me.sub)
    return {p.id: {"eltern_ids": sorted(eltern.get(p.id, [])),
                   "kinder_ids": sorted(kinder.get(p.id, []))} for p in projekte}


# ---------- Gliederung ----------
@router.put("/projects/{project_id}/eltern", response_model=ProjectOut)
def eltern_setzen(project_id: int, rumpf: ElternIn, me: Me = CurrentUser,
                  db: Session = Depends(get_db)) -> ProjectOut:
    """Ersetzt die Oberprojekte. Leere Liste = steht oben (kein Oberprojekt)."""
    p = _eigenes(db, me, project_id)
    gliederung.eltern_setzen(db, p, rumpf.eltern_ids)
    db.commit()
    db.refresh(p)
    return ProjectOut.model_validate(p).model_copy(update=mit_gliederung(db, me, [p])[p.id])


@router.get("/projects/by-slug/{slug}/teilbaum")
def teilbaum(slug: str, me: Me = CurrentUser, db: Session = Depends(get_db)) -> dict:
    """Slug und alle Nachfahren-Slugs, fuer die Filter in Aufgaben und Notizen (U7)."""
    p = db.query(Project).filter(Project.owner == me.sub, Project.slug == slug).one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    _, kinder = gliederung.eltern_und_kinder(db, me.sub)
    ids = gliederung.nachfahren(kinder, p.id)
    namen = {q.id: q for q in db.query(Project).filter(Project.id.in_(ids))} if ids else {}
    return {"slug": p.slug, "slugs": [p.slug] + [namen[i].slug for i in ids if i in namen]}


# ---------- Kontakte ----------
def _kontakt_zeile(me: Me, v: ProjectKontakt, projekt: Project, cache: dict) -> dict:
    if v.kontakt_id not in cache:
        cache[v.kontakt_id] = nachbarn.kontakt(me, v.kontakt_id)
    k = cache[v.kontakt_id]
    zeile = {"verweis_id": v.id, "kontakt_id": v.kontakt_id, "rolle": v.rolle,
             "projekt": projekt.slug, "projekt_name": projekt.name,
             "name": None, "telefon": None, "email": None, "fehlt": False, "unbekannt": False}
    if k is False:
        zeile["fehlt"] = True
    elif k is None:
        zeile["unbekannt"] = True
    else:
        zeile.update(name=k.get("name"), telefon=k.get("telefon"), email=k.get("email"))
    return zeile


@router.get("/projects/{project_id}/kontakte")
def kontakte_liste(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[dict]:
    p = _eigenes(db, me, project_id)
    cache: dict = {}
    return [_kontakt_zeile(me, v, p, cache) for v in sorted(p.kontakte, key=lambda v: v.id)]


@router.post("/projects/{project_id}/kontakte", status_code=201)
def kontakt_anheften(project_id: int, rumpf: KontaktVerweisIn, me: Me = CurrentUser,
                     db: Session = Depends(get_db)) -> dict:
    p = _eigenes(db, me, project_id)
    k = nachbarn.kontakt(me, rumpf.kontakt_id)
    if k is False:
        raise HTTPException(404, "Kontakt nicht gefunden")
    if k is None:
        raise HTTPException(503, "Kontakte-Dienst nicht erreichbar")
    if any(v.kontakt_id == rumpf.kontakt_id for v in p.kontakte):
        raise HTTPException(409, "Kontakt steht schon am Projekt")
    v = ProjectKontakt(project_id=p.id, kontakt_id=rumpf.kontakt_id,
                       rolle=(rumpf.rolle or "").strip() or None)
    db.add(v)
    db.commit()
    db.refresh(v)
    return _kontakt_zeile(me, v, p, {rumpf.kontakt_id: k})


@router.patch("/projects/{project_id}/kontakte/{verweis_id}")
def kontakt_rolle(project_id: int, verweis_id: int, rumpf: KontaktVerweisPatch,
                  me: Me = CurrentUser, db: Session = Depends(get_db)) -> dict:
    p = _eigenes(db, me, project_id)
    v = next((v for v in p.kontakte if v.id == verweis_id), None)
    if v is None:
        raise HTTPException(404, "Verweis nicht gefunden")
    v.rolle = (rumpf.rolle or "").strip() or None
    db.commit()
    return _kontakt_zeile(me, v, p, {})


@router.delete("/projects/{project_id}/kontakte/{verweis_id}", status_code=204)
def kontakt_loesen(project_id: int, verweis_id: int, me: Me = CurrentUser,
                   db: Session = Depends(get_db)) -> Response:
    p = _eigenes(db, me, project_id)
    v = next((v for v in p.kontakte if v.id == verweis_id), None)
    if v is None:
        raise HTTPException(404, "Verweis nicht gefunden")
    db.delete(v)
    db.commit()
    return Response(status_code=204)


@router.get("/kontakte-auswahl")
def kontakte_auswahl(suche: str | None = Query(None, max_length=100), me: Me = CurrentUser) -> list[dict]:
    """Kontakte aus Saganta Kontakte zum Anheften (Kennung, Name, Gruppe)."""
    liste = nachbarn.kontakte_suche(me, suche)
    if liste is None:
        raise HTTPException(503, "Kontakte-Dienst nicht erreichbar")
    return liste


@router.get("/kontakte/{kontakt_id}/projekte")
def projekte_eines_kontakts(kontakt_id: str, me: Me = CurrentUser,
                            db: Session = Depends(get_db)) -> list[dict]:
    """Rueckverweis fuer Saganta Kontakte: an welchen Projekten steht dieser Kontakt."""
    zeilen = db.execute(
        select(ProjectKontakt, Project).join(Project, Project.id == ProjectKontakt.project_id)
        .where(Project.owner == me.sub, ProjectKontakt.kontakt_id == kontakt_id)
        .order_by(Project.name)
    ).all()
    return [{**_kurz(p), "rolle": v.rolle} for v, p in zeilen]


# ---------- Akte ----------
def _frist(art: str, datum, titel: str, projekt: str, ref: str | None = None, **mehr) -> dict:
    return {"art": art, "datum": str(datum), "uhrzeit": None, "ende": None,
            "titel": titel, "projekt": projekt, "ref": ref, **mehr}


@router.get("/projects/{project_id}/akte")
def akte(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> dict:
    p = _eigenes(db, me, project_id)
    eltern, kinder = gliederung.eltern_und_kinder(db, me.sub)
    unten_ids = gliederung.nachfahren(kinder, p.id)
    alle_ids = [p.id] + unten_ids
    projekte = {q.id: q for q in db.query(Project).filter(Project.id.in_(alle_ids + list(
        gliederung.pfad_zur_wurzel(eltern, p.id)) + eltern.get(p.id, [])))}
    im_teil = [projekte[i] for i in alle_ids if i in projekte]
    slugs = [q.slug for q in im_teil]
    nach_slug = {q.slug: q for q in im_teil}
    heute = today()

    # Aufgaben aller Projekte im Teilbaum (Zuhause oder angeheftet), in einem Aufruf.
    try:
        offen = aufgaben_dienst.aufruf(me, "GET", "/api/aufgaben",
                                       params={"projekt": ",".join(slugs)}) or []
        aufgaben_fehlen = False
    except (aufgaben_dienst.AufgabenNichtErreichbar, httpx.HTTPStatusError):
        offen, aufgaben_fehlen = [], True

    notiz_je_aufgabe = nachbarn.notizen_zu(me, "aufgabe", [a["id"] for a in offen])
    for a in offen:
        a["notizen"] = (notiz_je_aufgabe or {}).get(a["id"], [])

    # Zeitleiste: Fristen der Aufgaben, Meilensteine, Projektdaten, Termine.
    zeitleiste: list[dict] = []
    for a in offen:
        if a.get("faellig"):
            zeitleiste.append(_frist("frist", a["faellig"], a["titel"], a.get("projekt") or p.slug,
                                     a["id"], prioritaet=a.get("prioritaet")))
        geplant = a.get("start") or a.get("tag")
        if geplant:
            # Eingeplante Arbeit an einer Aufgabe (Tag oder Uhrzeit aus „Tag planen").
            zeitleiste.append({
                "art": "geplant", "datum": str(geplant)[:10],
                "uhrzeit": str(a["start"])[11:16] if a.get("start") else None,
                "ende": str(a["ende"])[11:16] if a.get("ende") else None,
                "titel": a["titel"], "projekt": a.get("projekt") or p.slug, "ref": a["id"]})
    meilensteine = db.query(ProjectMilestone).filter(
        ProjectMilestone.project_id.in_(alle_ids), ProjectMilestone.target_date.is_not(None),
        ProjectMilestone.status != "done").all()
    for m in meilensteine:
        zeitleiste.append(_frist("meilenstein", m.target_date, m.title,
                                 projekte[m.project_id].slug, str(m.id)))
    for q in im_teil:
        for feld, art, titel in (("deadline_date", "projektfrist", "Frist"),
                                 ("public_target_date", "projektfrist", "Veröffentlichung"),
                                 ("sunset_date", "projektfrist", "Abschalten"),
                                 ("review_date", "durchsicht", "Durchsicht")):
            wert = getattr(q, feld)
            if wert:
                zeitleiste.append(_frist(art, wert, f"{titel}: {q.name}", q.slug))
    termine = nachbarn.termine(me, slugs, str(heute - timedelta(days=TAGE_ZURUECK)),
                               str(heute + timedelta(days=TAGE_VORAUS)))
    for t in termine or []:
        start = str(t.get("start") or t.get("start_at") or "")
        ende = str(t.get("end") or t.get("end_at") or "")
        ganztags = bool(t.get("all_day"))
        zeitleiste.append({
            "art": "termin", "datum": start[:10],
            "uhrzeit": None if ganztags or len(start) < 16 else start[11:16],
            "ende": None if ganztags or len(ende) < 16 else ende[11:16],
            "titel": t.get("title") or "", "projekt": t.get("projekt") or p.slug,
            "ref": t.get("id"), "ort": t.get("location")})
    zeitleiste.sort(key=lambda z: (z["datum"], z["uhrzeit"] or ""))

    # Kontakte aller Projekte im Teilbaum.
    cache: dict = {}
    verweise = db.query(ProjectKontakt).filter(ProjectKontakt.project_id.in_(alle_ids)).all()
    kontakte = [_kontakt_zeile(me, v, projekte[v.project_id], cache) for v in verweise]
    kontakte.sort(key=lambda k: ((k["name"] or "").lower(), k["projekt"]))

    # Budget: Summe ueber den Teilbaum, dazu je Projekt.
    je_budget = nachbarn.budgets(me)
    budget = {"verfuegbar": je_budget is not None, "gesamt": None, "je": {}, "letzte": []}
    if je_budget is not None:
        je = {s: je_budget[s] for s in slugs if s in je_budget}
        summe = {k: sum(e.get(k) or 0 for e in je.values())
                 for k in ("ausgaben_cent", "einnahmen_cent", "anzahl_buchungen")}
        budgets_da = [e["budget_cent"] for e in je.values() if e.get("budget_cent") is not None]
        summe["budget_cent"] = sum(budgets_da) if budgets_da else None
        summe["rest_cent"] = (summe["budget_cent"] - summe["ausgaben_cent"]
                              if summe["budget_cent"] is not None else None)
        budget.update(gesamt=summe, je=je)
        stand = nachbarn.budget_stand(me, p.slug)
        if stand:
            budget["letzte"] = stand.get("letzte") or []

    # Notizen der Projekte selbst (am Slug).
    notiz_je_projekt = nachbarn.notizen_zu(me, "projekt", slugs)
    notizen = []
    for s in slugs:
        for n in (notiz_je_projekt or {}).get(s, []):
            notizen.append({**n, "projekt": s})

    # Kacheln der direkten Unterprojekte, je mit Summe ueber ihren Teilbaum.
    direkte = sorted((k for k in kinder.get(p.id, []) if k in projekte), key=lambda i: projekte[i].name.lower())
    teilbaum = {kid: [kid] + gliederung.nachfahren(kinder, kid) for kid in direkte}
    teil_slugs_je = {kid: {projekte[i].slug for i in teil if i in projekte} for kid, teil in teilbaum.items()}
    zaehlung = aufgaben_dienst.zaehlung_gruppen(
        me, {projekte[kid].slug: sorted(s) for kid, s in teil_slugs_je.items()}) or {}
    kachel = []
    for kid in direkte:
        teil, teil_slugs = teilbaum[kid], teil_slugs_je[kid]
        z = {k: zaehlung.get(projekte[kid].slug, {}).get(k, 0)
             for k in ("offen", "hoch", "ueberfaellig", "erledigt_7")}
        naechste = min((e["datum"] for e in zeitleiste
                        if e["projekt"] in teil_slugs and e["datum"] >= str(heute)), default=None)
        kachel.append({**_kurz(projekte[kid]), **z, "naechstes_datum": naechste,
                       "unterprojekte": len(teil) - 1})

    gl = mit_gliederung(db, me, [p])[p.id]
    return {
        "projekt": ProjectOut.model_validate(p).model_copy(update=gl).model_dump(mode="json"),
        "pfad": [_kurz(projekte[i]) for i in gliederung.pfad_zur_wurzel(eltern, p.id) if i in projekte],
        "eltern": [_kurz(projekte[i]) for i in sorted(eltern.get(p.id, [])) if i in projekte],
        "kinder": kachel,
        "projekte": {q.slug: {"id": q.id, "name": q.name} for q in im_teil},
        "aufgaben": offen,
        "aufgaben_fehlen": aufgaben_fehlen,
        "zeitleiste": zeitleiste,
        "termine_fehlen": termine is None,
        "kontakte": kontakte,
        "budget": budget,
        "notizen": notizen,
        "notizen_fehlen": notiz_je_projekt is None,
    }
