from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from . import aufgaben_dienst
from .auth import CurrentUser, Me
from .db import get_db
from .enums import PUBLIC_READINESS_ITEMS, SHUTDOWN_CHECKLIST_ITEMS
from .models import (
    Project,
    ProjectAsset,
    ProjectMilestone,
    ProjectReview,
    PublicReadiness,
    ShutdownChecklist,
)
from .schemas import (
    AssetIn,
    AssetOut,
    MilestoneIn,
    MilestoneOut,
    MilestonePatch,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    ReadinessOut,
    ReadinessPatch,
    ReviewIn,
    ReviewOut,
    ShutdownOut,
    ShutdownPatch,
)
from .util import slugify, today

router = APIRouter()


def _owned_project(db: Session, me: Me, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p or p.owner != me.sub:
        raise HTTPException(404, "project not found")
    return p


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    i = 2
    while db.query(Project).filter(Project.slug == slug).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


# ---------- Projects ----------
@router.get("", response_model=list[ProjectOut])
def list_projects(
    me: Me = CurrentUser,
    type: str | None = Query(None),
    status: str | None = Query(None),
    client_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    q = db.query(Project).filter(Project.owner == me.sub)
    if type:
        q = q.filter(Project.type == type)
    if status:
        q = q.filter(Project.status == status)
    if client_id:
        q = q.filter(Project.client_id == client_id)
    projekte = q.order_by(Project.priority.asc(), Project.updated_at.desc()).all()

    # Offene Aufgaben je Projekt in EINEM Aufruf am Aufgaben-Dienst.
    # Fehlt die Antwort, bleibt der Zaehler 0. Das ist hier vertretbar:
    # er ist eine Anzeige an der Kachel, kein Urteil wie ein Befund.
    je_slug = (aufgaben_dienst.zaehlung(me) or {}) if projekte else {}
    return [
        ProjectOut.model_validate(p).model_copy(update={
            "open_tasks": je_slug.get(p.slug, {}).get("offen", 0),
            "open_high": je_slug.get(p.slug, {}).get("hoch", 0),
        })
        for p in projekte
    ]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> Project:
    data = payload.model_dump()
    base_slug = slugify(data.pop("slug") or data["name"])
    p = Project(owner=me.sub, slug=_unique_slug(db, base_slug), **data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/by-slug/{slug}", response_model=ProjectOut)
def get_by_slug(slug: str, me: Me = CurrentUser, db: Session = Depends(get_db)) -> Project:
    p = db.query(Project).filter(Project.owner == me.sub, Project.slug == slug).one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    return p


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> Project:
    return _owned_project(db, me, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: int, payload: ProjectPatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> Project:
    p = _owned_project(db, me, project_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> None:
    p = _owned_project(db, me, project_id)
    # Zuerst die Aufgaben loesen, dann das Projekt loeschen: ein frei
    # gewordener Slug wird wieder vergeben, und ein neues Projekt erbte
    # sonst die Aufgaben des alten. Antwortet der Dienst nicht, bleibt das
    # Projekt stehen (503), statt Aufgaben mit einem toten Bezug zu hinterlassen.
    _durch(me, "POST", f"/api/projekte/{p.slug}/loesen")
    db.delete(p)
    db.commit()


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> Project:
    p = _owned_project(db, me, project_id)
    p.status = "archived"
    db.commit()
    db.refresh(p)
    return p


# ---------- Aufgaben (im Aufgaben-Dienst) ----------
#
# Sechste Fragerunde (04.11.): das ProjectDeck zeigt die Aufgaben eines
# Projekts, legt an und hakt ab, ohne eigene Kopie. Diese Routen reichen an
# `aufgaben-api` durch und antworten in dessen Form (Kennung ist eine UUID).
# Das Projekt setzt dieser Dienst selbst; `projekt` und `liste_id` aus dem
# Rumpf werden verworfen, umgehaengt wird in der App Saganta Aufgaben.

_NICHT_DURCHREICHEN = {"projekt", "liste_id"}


def _durch(me: Me, methode: str, pfad: str, **kw):
    try:
        return aufgaben_dienst.aufruf(me, methode, pfad, **kw)
    except aufgaben_dienst.AufgabenNichtErreichbar as exc:
        raise HTTPException(503, "Aufgaben-Dienst nicht erreichbar") from exc
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", "Aufgaben-Dienst lehnte ab")
        except ValueError:
            detail = "Aufgaben-Dienst lehnte ab"
        raise HTTPException(exc.response.status_code, detail) from exc


def _aufgabe_im_projekt(me: Me, p: Project, aufgabe_id: str) -> dict:
    """404, wenn die Aufgabe nicht zu diesem Projekt gehoert (auch fremde)."""
    aufgabe = _durch(me, "GET", f"/api/aufgaben/{aufgabe_id}")
    if aufgabe.get("projekt") != p.slug:
        raise HTTPException(404, "Aufgabe nicht gefunden")
    return aufgabe


@router.get("/{project_id}/aufgaben/alt/{alte_id}")
def aufgabe_nach_alter_kennung(
    project_id: int, alte_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> dict:
    """Die Aufgabe, die beim Umzug aus ``project_tasks`` Zeile ``alte_id`` wurde.

    Fuer die App: ihre Offline-Warteschlange kann Haken aus 0.8.x mit der
    alten Zahl-Kennung halten. Statt sie zu verwerfen, loest sie die Kennung
    hier ueber ``herkunft = projectdeck:<id>`` auf (Entscheid 05.11.).
    """
    p = _owned_project(db, me, project_id)
    treffer = _durch(me, "GET", "/api/aufgaben", params={"herkunft": f"projectdeck:{alte_id}"}) or []
    treffer = [a for a in treffer if a.get("projekt") == p.slug]
    if not treffer:
        raise HTTPException(404, "Aufgabe nicht gefunden")
    return treffer[0]


@router.get("/{project_id}/aufgaben")
def aufgaben_liste(
    project_id: int,
    erledigte: bool = Query(False),
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> list[dict]:
    p = _owned_project(db, me, project_id)
    return _durch(me, "GET", "/api/aufgaben", params={"projekt": p.slug, "erledigte": erledigte})


@router.post("/{project_id}/aufgaben", status_code=201)
def aufgabe_anlegen(
    project_id: int,
    rumpf: dict = Body(...),
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    p = _owned_project(db, me, project_id)
    daten = {k: v for k, v in rumpf.items() if k not in _NICHT_DURCHREICHEN}
    return _durch(me, "POST", "/api/aufgaben", json={**daten, "projekt": p.slug})


@router.put("/{project_id}/aufgaben/{aufgabe_id}")
def aufgabe_aendern(
    project_id: int,
    aufgabe_id: str,
    rumpf: dict = Body(...),
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    p = _owned_project(db, me, project_id)
    _aufgabe_im_projekt(me, p, aufgabe_id)
    daten = {k: v for k, v in rumpf.items() if k not in _NICHT_DURCHREICHEN}
    return _durch(me, "PUT", f"/api/aufgaben/{aufgabe_id}", json=daten)


@router.post("/{project_id}/aufgaben/{aufgabe_id}/erledigt")
def aufgabe_abhaken(
    project_id: int, aufgabe_id: str, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> dict:
    p = _owned_project(db, me, project_id)
    _aufgabe_im_projekt(me, p, aufgabe_id)
    return _durch(me, "POST", f"/api/aufgaben/{aufgabe_id}/erledigt")


@router.post("/{project_id}/aufgaben/{aufgabe_id}/offen")
def aufgabe_aufmachen(
    project_id: int, aufgabe_id: str, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> dict:
    p = _owned_project(db, me, project_id)
    _aufgabe_im_projekt(me, p, aufgabe_id)
    return _durch(me, "POST", f"/api/aufgaben/{aufgabe_id}/offen")


@router.delete("/{project_id}/aufgaben/{aufgabe_id}", status_code=204)
def aufgabe_loeschen(
    project_id: int, aufgabe_id: str, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> Response:
    p = _owned_project(db, me, project_id)
    _aufgabe_im_projekt(me, p, aufgabe_id)
    _durch(me, "DELETE", f"/api/aufgaben/{aufgabe_id}")
    return Response(status_code=204)


# ---------- Assets ----------
@router.get("/{project_id}/assets", response_model=list[AssetOut])
def list_assets(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectAsset]:
    _owned_project(db, me, project_id)
    return db.query(ProjectAsset).filter(ProjectAsset.project_id == project_id).all()


@router.post("/{project_id}/assets", response_model=AssetOut, status_code=201)
def create_asset(
    project_id: int, payload: AssetIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProjectAsset:
    _owned_project(db, me, project_id)
    a = ProjectAsset(project_id=project_id, **payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{project_id}/assets/{asset_id}", status_code=204)
def delete_asset(
    project_id: int, asset_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> None:
    _owned_project(db, me, project_id)
    a = db.get(ProjectAsset, asset_id)
    if not a or a.project_id != project_id:
        raise HTTPException(404, "asset not found")
    db.delete(a)
    db.commit()


# ---------- Milestones ----------
@router.get("/{project_id}/milestones", response_model=list[MilestoneOut])
def list_milestones(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectMilestone]:
    _owned_project(db, me, project_id)
    return (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.target_date.asc().nullslast())
        .all()
    )


@router.post("/{project_id}/milestones", response_model=MilestoneOut, status_code=201)
def create_milestone(
    project_id: int, payload: MilestoneIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProjectMilestone:
    _owned_project(db, me, project_id)
    m = ProjectMilestone(project_id=project_id, **payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=MilestoneOut)
def patch_milestone(
    project_id: int,
    milestone_id: int,
    payload: MilestonePatch,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> ProjectMilestone:
    """Einen Meilenstein aendern.

    Es gab bis zum 2026-10-16 nur GET, POST und DELETE. Ein Meilenstein war
    damit eine Einbahnstrasse: ``status`` blieb fuer immer ``open``, auch wenn er
    erreicht war, und ``description`` liess sich nach dem Anlegen nicht mehr
    setzen. Wer etwas aendern wollte, musste loeschen und neu anlegen -- und
    damit das Anlege-Datum verlieren.

    Das war nicht nur unbequem: der Deadline-Center zaehlt seit demselben Tag
    ueberfaellige Meilensteine, und ohne einen Weg, einen als erreicht zu
    markieren, wuerde diese Zahl nur steigen. Eine Warnung, die man nicht
    abstellen kann, wird ignoriert.

    Gleiches Muster wie ``patch_task`` darueber, inklusive ``exclude_unset``:
    ein nicht mitgeschicktes Feld bleibt, wie es war, statt auf ``None``
    zurueckzufallen.
    """
    _owned_project(db, me, project_id)
    m = db.get(ProjectMilestone, milestone_id)
    if not m or m.project_id != project_id:
        raise HTTPException(404, "milestone not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{project_id}/milestones/{milestone_id}", status_code=204)
def delete_milestone(
    project_id: int, milestone_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> None:
    _owned_project(db, me, project_id)
    m = db.get(ProjectMilestone, milestone_id)
    if not m or m.project_id != project_id:
        raise HTTPException(404, "milestone not found")
    db.delete(m)
    db.commit()


# ---------- Reviews ----------
@router.get("/{project_id}/reviews", response_model=list[ReviewOut])
def list_reviews(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectReview]:
    _owned_project(db, me, project_id)
    return (
        db.query(ProjectReview)
        .filter(ProjectReview.project_id == project_id)
        .order_by(ProjectReview.review_date.desc())
        .all()
    )


@router.post("/{project_id}/reviews", response_model=ReviewOut, status_code=201)
def create_review(
    project_id: int, payload: ReviewIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProjectReview:
    p = _owned_project(db, me, project_id)
    data = payload.model_dump()
    data["review_date"] = data.get("review_date") or today()
    r = ProjectReview(project_id=project_id, **data)
    db.add(r)
    # Entscheidung auf das Projekt anwenden.
    if r.new_status:
        p.status = r.new_status
    if r.new_priority:
        p.priority = r.new_priority
    if r.new_weekly_budget_minutes is not None:
        p.weekly_time_budget_minutes = r.new_weekly_budget_minutes
    if r.next_action:
        p.next_action = r.next_action
    p.last_reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(r)
    return r


# ---------- Public Readiness ----------
def _readiness_out(pr: PublicReadiness | None, project_id: int) -> ReadinessOut:
    items = dict(pr.items) if pr and pr.items else {}
    # alle bekannten Items sicherstellen
    for key in PUBLIC_READINESS_ITEMS:
        items.setdefault(key, {"done": False, "note": None})
    completed = sum(1 for v in items.values() if v.get("done"))
    return ReadinessOut(
        project_id=project_id, items=items, completed=completed, total=len(PUBLIC_READINESS_ITEMS)
    )


@router.get("/{project_id}/readiness", response_model=ReadinessOut)
def get_readiness(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> ReadinessOut:
    _owned_project(db, me, project_id)
    pr = db.query(PublicReadiness).filter(PublicReadiness.project_id == project_id).one_or_none()
    return _readiness_out(pr, project_id)


@router.put("/{project_id}/readiness", response_model=ReadinessOut)
def put_readiness(
    project_id: int, payload: ReadinessPatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ReadinessOut:
    _owned_project(db, me, project_id)
    pr = db.query(PublicReadiness).filter(PublicReadiness.project_id == project_id).one_or_none()
    if not pr:
        pr = PublicReadiness(project_id=project_id, items={})
        db.add(pr)
    merged = dict(pr.items or {})
    for key, item in payload.items.items():
        merged[key] = item.model_dump()
    pr.items = merged
    db.commit()
    db.refresh(pr)
    return _readiness_out(pr, project_id)


# ---------- Shutdown-Checkliste ----------
def _shutdown_out(sc: ShutdownChecklist | None, project_id: int) -> ShutdownOut:
    items = dict(sc.items) if sc and sc.items else {}
    for key in SHUTDOWN_CHECKLIST_ITEMS:
        items.setdefault(key, {"done": False, "note": None})
    completed = sum(1 for v in items.values() if v.get("done"))
    return ShutdownOut(
        project_id=project_id, items=items, completed=completed, total=len(SHUTDOWN_CHECKLIST_ITEMS)
    )


@router.get("/{project_id}/shutdown", response_model=ShutdownOut)
def get_shutdown(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> ShutdownOut:
    _owned_project(db, me, project_id)
    sc = db.query(ShutdownChecklist).filter(ShutdownChecklist.project_id == project_id).one_or_none()
    return _shutdown_out(sc, project_id)


@router.put("/{project_id}/shutdown", response_model=ShutdownOut)
def put_shutdown(
    project_id: int, payload: ShutdownPatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ShutdownOut:
    _owned_project(db, me, project_id)
    sc = db.query(ShutdownChecklist).filter(ShutdownChecklist.project_id == project_id).one_or_none()
    if not sc:
        sc = ShutdownChecklist(project_id=project_id, items={})
        db.add(sc)
    merged = dict(sc.items or {})
    for key, item in payload.items.items():
        merged[key] = item.model_dump()
    sc.items = merged
    db.commit()
    db.refresh(sc)
    return _shutdown_out(sc, project_id)
