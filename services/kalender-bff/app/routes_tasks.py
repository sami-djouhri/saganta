"""Todos & Tagesziele-Proxy zum nativen Kalender (kalender:8085).

Bringt die Aufgaben- und Zielverwaltung des nativen Kalenders ins Saganta-
Frontend: Lesen, Anlegen, Abhaken, Löschen. Der native Kalender bleibt die
Datenquelle/Engine (Scheduling, Recurrence, Completion-Log, A/B/C-Prioritäts-
Regel): dieser BFF ist nur Auth-Bridge + schlanke Eingabevalidierung, die die
nativen Constraints spiegelt (defense in depth; der native Kalender validiert
erneut).
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import upstream as _upstream

router = APIRouter()

_PRIORITY = r"^(niedrig|mittel|hoch|dringend)$"
# ⚠️ Englisch, im Gegensatz zu _PRIORITY. So steht es im nativen Kalender
# (`backend/schemas.py: _ENERGY`); der Sprachmix stammt aus dem Bestand und wird
# hier nicht uebersetzt, sondern gespiegelt.
_ENERGY = r"^(low|medium|high)$"
_GOAL_PRIORITY = r"^[ABC]$"
_GOAL_STATUS = r"^(planned|active|achieved|partial|abandoned|missed)$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
_TIME = r"^\d{2}:\d{2}$"
_HEXFARBE = r"^#[0-9a-fA-F]{6}$"
_PROJEKT_STATUS = r"^(active|paused|completed)$"


# ── Todos (Aufgaben) ─────────────────────────────────────────────────────
class TodoIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    priority: str = Field(default="mittel", pattern=_PRIORITY)
    due_date: str | None = Field(default=None, pattern=_DATE)
    due_time: str | None = Field(default=None, pattern=_TIME)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)


@router.get("/api/todos")
async def list_todos(
    me: Me = CurrentUser,
    due_from: str | None = Query(None, pattern=_DATE),
    due_to: str | None = Query(None, pattern=_DATE),
    include_completed: bool = Query(False),
) -> list:
    params: dict[str, object] = {"include_completed": str(include_completed).lower()}
    if due_from:
        params["due_from"] = due_from
    if due_to:
        params["due_to"] = due_to
    r = await _upstream("GET", "/api/todos", params=params)
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/todos", status_code=201)
async def create_todo(data: TodoIn, me: Me = CurrentUser) -> dict:
    r = await _upstream("POST", "/api/todos", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


@router.post("/api/todos/{todo_id}/complete")
async def complete_todo(todo_id: str, me: Me = CurrentUser) -> dict:
    r = await _upstream("POST", f"/api/todos/{todo_id}/complete")
    return r.json() if r.content else {}


@router.post("/api/todos/{todo_id}/uncomplete")
async def uncomplete_todo(todo_id: str, me: Me = CurrentUser) -> dict:
    r = await _upstream("POST", f"/api/todos/{todo_id}/uncomplete")
    return r.json() if r.content else {}


class TodoPatch(BaseModel):
    """Teil-Änderung einer Aufgabe. Alle Felder optional, nur Gesetztes wandert hoch.

    Spiegelt ``TodoUpdate`` des nativen Kalenders. Bewusst NICHT vollständig: die
    **Ergebnisse** der Planung (``scheduled_start``/``scheduled_end``/
    ``scheduling_mode``/``planned_date``) gehören dem Scheduler und entstehen über
    ``/api/assistant/plan-day``. Sie hier durchzureichen hiesse, zwei Wege auf
    dieselbe Entscheidung zu haben.

    ★ ``energy_required`` ist seit 2026-09-13 dabei, und das ist kein Aufweichen
    dieser Regel, sondern ihre Anwendung: der Energiebedarf ist eine **Eigenschaft
    der Aufgabe** („diese Arbeit ist anstrengend"), die der Scheduler *liest*, um
    sie gegen die Tageskapazität zu halten. Er ist Eingabe, nicht Ausgabe. Ohne
    ihn konnte man ihn nirgends in Saganta setzen, und die kapazitätsbewusste
    Planung lief auf einem Feld, das immer leer blieb.

    ⚠️ Der native Kalender schreibt ihn **englisch** (``low|medium|high``),
    während ``priority`` deutsch ist (``niedrig|mittel|hoch``). Der Sprachmix
    steckt im Bestand; er wird hier nicht stillschweigend übersetzt, sondern
    ausdrücklich geprüft, damit ein deutscher Wert hier scheitert und nicht erst
    oben als 422 ohne erkennbaren Bezug.
    """
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    priority: str | None = Field(default=None, pattern=_PRIORITY)
    due_date: str | None = Field(default=None, pattern=_DATE)
    due_time: str | None = Field(default=None, pattern=_TIME)
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    energy_required: str | None = Field(default=None, pattern=_ENERGY)
    project_id: str | None = None
    goal_id: str | None = None
    completed: bool | None = None


@router.put("/api/todos/{todo_id}")
async def update_todo(todo_id: str, data: TodoPatch, me: Me = CurrentUser) -> dict:
    """Aufgabe ändern.

    ★★ ``exclude_unset`` statt ``exclude_none``, seit 2026-09-13. Der Unterschied
    ist nicht kosmetisch: mit ``exclude_none`` fiel jedes ``null`` aus der
    Anfrage, und damit war es über diesen Weg **unmöglich, ein Feld zu leeren**.
    Wer ein Fälligkeitsdatum entfernen wollte, schickte ``due_date: null``, der
    BFF liess es weg, der native Kalender sah kein Feld und liess den alten Wert
    stehen. Die Oberfläche meldete Erfolg, das Datum blieb. Ein stiller Fehler in
    genau der Richtung, in der man ihn am spätesten bemerkt.

    ``exclude_unset`` unterscheidet die beiden Fälle, die hier verschieden
    gemeint sind: ein **nicht geschicktes** Feld bleibt unangetastet, ein
    **ausdrücklich auf null gesetztes** wird geleert.
    """
    r = await _upstream(
        "PUT", f"/api/todos/{todo_id}", json=data.model_dump(exclude_unset=True)
    )
    return r.json() if r.content else {}


class TodoDefer(BaseModel):
    """Aufgabe aufschieben.

    ``planned_date`` ist der Tag, an den sie wandert; ohne ihn geht sie zurück in
    den Pool (so behandelt es der native Kalender).
    """

    planned_date: str | None = Field(default=None, pattern=_DATE)
    reason: str | None = Field(default=None, max_length=500)


@router.post("/api/todos/{todo_id}/defer")
async def defer_todo(todo_id: str, data: TodoDefer | None = None, me: Me = CurrentUser) -> dict:
    """Aufschieben als eigener Weg, nicht als ``PUT`` auf das Datum.

    ★ Der Unterschied ist der Zähler. ``defer`` erhöht ``defer_count`` und
    schreibt ``last_deferred_at``; daraus entsteht die Warnung „bleibt liegen",
    die der Sekretär anzeigt. Setzt man das Datum direkt, lässt sich eine Aufgabe
    beliebig oft verschieben, ohne dass es je auffällt. Die Route fehlte im BFF
    bis 2026-09-13, obwohl die Engine sie seit jeher hat; in Saganta gab es
    deshalb nur den stillen Weg.

    ⚠️ Der native Endpunkt kennt **kein** ``due_date``. Wer es mitschickt, bekommt
    keinen Fehler: Pydantic verwirft das unbekannte Feld, und weil dann auch kein
    ``planned_date`` gesetzt ist, landet die Aufgabe im Pool statt am gewünschten
    Tag. „Auf morgen verschoben" hiesse dann in Wahrheit „ins Unbestimmte".
    Deshalb ist ``planned_date`` hier der einzige Datumsweg.
    """
    payload = data.model_dump(exclude_none=True) if data else {}
    r = await _upstream("POST", f"/api/todos/{todo_id}/defer", json=payload)
    return r.json() if r.content else {}


@router.delete("/api/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: str, me: Me = CurrentUser) -> None:
    await _upstream("DELETE", f"/api/todos/{todo_id}")


# ── Tagesziele (DailyGoal, A/B/C) ────────────────────────────────────────
class GoalIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    date: str = Field(..., pattern=_DATE)
    priority: str = Field(default="B", pattern=_GOAL_PRIORITY)
    estimated_minutes: int | None = Field(default=None, ge=0, le=1440)


@router.get("/api/goals")
async def list_goals(
    me: Me = CurrentUser,
    date: str | None = Query(None, pattern=_DATE),
) -> list:
    params = {"date": date} if date else None
    r = await _upstream("GET", "/api/goals", params=params)
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/goals", status_code=201)
async def create_goal(data: GoalIn, me: Me = CurrentUser) -> dict:
    r = await _upstream("POST", "/api/goals", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


class GoalPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    date: str | None = Field(default=None, pattern=_DATE)
    priority: str | None = Field(default=None, pattern=_GOAL_PRIORITY)
    status: str | None = Field(default=None, pattern=_GOAL_STATUS)
    estimated_minutes: int | None = Field(default=None, ge=0, le=1440)
    category: str | None = Field(default=None, max_length=50)
    review_note: str | None = Field(default=None, max_length=2000)


class GoalAbandon(BaseModel):
    abandoned_reason: str | None = Field(default=None, max_length=500)


@router.put("/api/goals/{goal_id}")
async def update_goal(goal_id: str, data: GoalPatch, me: Me = CurrentUser) -> dict:
    r = await _upstream(
        "PUT", f"/api/goals/{goal_id}", json=data.model_dump(exclude_none=True)
    )
    return r.json() if r.content else {}


@router.post("/api/goals/{goal_id}/abandon")
async def abandon_goal(
    goal_id: str, data: GoalAbandon | None = None, me: Me = CurrentUser
) -> dict:
    """Ziel aufgeben: eigener Weg statt Löschen.

    Der native Kalender unterscheidet zwischen „aufgegeben" (bleibt mit Grund in
    der Historie und fliesst ins Präferenz-Lernen ein) und „gelöscht" (weg). Nur
    DELETE anzubieten hiesse, jedes nicht erreichte Ziel aus der Auswertung zu
    tilgen, dann lernt der Sekretär ausschliesslich aus Erfolgen.
    """
    payload = data.model_dump(exclude_none=True) if data else {}
    r = await _upstream("POST", f"/api/goals/{goal_id}/abandon", json=payload)
    return r.json() if r.content else {}


@router.delete("/api/goals/{goal_id}", status_code=204)
async def delete_goal(goal_id: str, me: Me = CurrentUser) -> None:
    await _upstream("DELETE", f"/api/goals/{goal_id}")


# ── Projekte ─────────────────────────────────────────────────────────────
# Für die ProjectDeck-Verknüpfung: Aufgaben tragen eine project_id (ProjectDeck
# pusht seine Tasks als Pool-Todos hierher); die Projektliste liefert Namen+Farbe
# zum Anzeigen der Herkunft.
#
# Schreibend seit 2026-08-20 (vorher nur lesend), weil die native App Projekte
# anlegen und ändern kann und sonst beim Umstieg aufs Saganta-Konto Funktion
# verloren hätte. ⚠️ ProjectDeck bleibt für seine eigenen Projekte die Quelle:
# hier angelegte sind kalender-eigene, die ProjectDeck nicht kennt.
class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    color: str = Field(default="#6c5ce7", pattern=_HEXFARBE)
    icon: str | None = Field(default=None, max_length=10)
    status: str = Field(default="active", pattern=_PROJEKT_STATUS)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    color: str | None = Field(default=None, pattern=_HEXFARBE)
    icon: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, pattern=_PROJEKT_STATUS)


@router.get("/api/projects")
async def list_projects(me: Me = CurrentUser) -> list:
    r = await _upstream("GET", "/api/projects")
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/projects", status_code=201)
async def create_project(data: ProjectIn, me: Me = CurrentUser) -> dict:
    r = await _upstream("POST", "/api/projects", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


@router.put("/api/projects/{project_id}")
async def update_project(
    project_id: str, data: ProjectPatch, me: Me = CurrentUser
) -> dict:
    r = await _upstream(
        "PUT", f"/api/projects/{project_id}", json=data.model_dump(exclude_none=True)
    )
    return r.json() if r.content else {}


@router.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, me: Me = CurrentUser) -> None:
    await _upstream("DELETE", f"/api/projects/{project_id}")
