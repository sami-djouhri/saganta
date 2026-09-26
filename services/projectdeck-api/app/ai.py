"""Optionaler KI-Layer.

Grundprinzip: Jede Funktion baut zuerst auf rules.py / deadline_risk.py auf und
liefert die Regel-Begründung mit. Der LLM (Default node2-Gemma, alltag-Pfad) wird
nur genutzt, wenn `llm_enabled` und nur, um die Regel-Findings in Klartext zu
verdichten, nie für undurchsichtige Auto-Planung. Bei LLM-Ausfall greift immer
der erklärbare Regel-Fallback.
"""

import httpx
import structlog

from .config import settings
from .deadline_risk import compute_risk
from .enums import ProjectStatus
from .models import Project
from .rules import evaluate_project
from .schemas import AISuggestOut
from .util import today

log = structlog.get_logger()


async def _llm_condense(prompt: str) -> str | None:
    """Best-effort LLM-Aufruf (OpenAI-kompatibles Chat-API von node2-Gemma)."""
    # Eingeschaltet ohne Adresse ist dasselbe wie ausgeschaltet. Ohne diese
    # Bedingung scheiterte der Aufruf bei jedem Bericht neu und hinterliesse je
    # eine Protokollzeile, von der niemand etwas hat: der Layer ist best effort
    # und sein Ausfall aendert die Antwort nicht.
    if not settings.llm_enabled or not settings.llm_base_url:
        return None
    try:
        async with httpx.AsyncClient(
            base_url=settings.llm_base_url, timeout=settings.llm_timeout_seconds
        ) as client:
            r = await client.post(
                "/v1/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Du bist ein nüchterner Projekt-Portfolio-Assistent. "
                                "Fasse die gegebenen Fakten in 2-3 Sätzen Deutsch zusammen. "
                                "Erfinde nichts dazu."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 220,
                },
            )
            if r.status_code < 400:
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError) as e:
        log.warning("ai.llm.failed", error=str(e))
    return None


async def _wrap(kind: str, reasoning: list[str], default_summary: str, data: dict) -> AISuggestOut:
    summary = default_summary
    source = "rules"
    if settings.llm_enabled and reasoning:
        prompt = f"{default_summary}\n\nFakten:\n- " + "\n- ".join(reasoning)
        condensed = await _llm_condense(prompt)
        if condensed:
            summary = condensed
            source = "llm"
    return AISuggestOut(
        kind=kind, source=source, summary=summary, reasoning=reasoning, data=data
    )


async def suggest_shutdown(project: Project) -> AISuggestOut:
    reasoning: list[str] = []
    if project.sunset_date:
        days = (project.sunset_date - today()).days
        reasoning.append(f"Sunset-Date in {days} Tagen ({project.sunset_date}).")
    if project.status in {ProjectStatus.MAINTENANCE, ProjectStatus.FROZEN}:
        reasoning.append(f"Status ist '{project.status}'.")
    if project.weekly_time_budget_minutes == 0:
        reasoning.append("Kein Wochen-Zeitbudget: bekommt faktisch keine Zeit mehr.")
    open_tasks = [t for t in project.tasks if t.status != "done"]
    if not open_tasks:
        reasoning.append("Keine offenen Tasks: nichts mehr zu tun.")
    recommend = len(reasoning) >= 2
    default = (
        "Abschaltung empfohlen: prüfe den Shutdown-Assistenten."
        if recommend
        else "Aktuell keine starke Abschalt-Indikation."
    )
    return await _wrap("shutdown", reasoning, default, {"recommend_shutdown": recommend})


async def suggest_deadline_plan(project: Project) -> AISuggestOut:
    risk = compute_risk(project)
    reasoning = [
        f"Risk-Level: {risk.risk_level}.",
        f"Verbleibende planbare Minuten: {risk.total_remaining_minutes}.",
    ]
    if risk.days_until_deadline is not None:
        reasoning.append(f"Tage bis Deadline: {risk.days_until_deadline}.")
    if not risk.has_schedulable_tasks:
        reasoning.append("Keine planbaren Tasks: zuerst Arbeitspakete definieren.")
    default = f"Deadline-Druck {risk.risk_level}: " + (
        "Rückwärtsplanung dringend." if risk.risk_level in {"critical", "impossible", "overdue"}
        else "im grünen Bereich."
    )
    return await _wrap("deadline_plan", reasoning, default, risk.model_dump(mode="json"))


async def review_summary(project: Project) -> AISuggestOut:
    findings = evaluate_project(project)
    reasoning = [f"[{f.rule_id}] {f.message}" for f in findings]
    if not reasoning:
        reasoning = ["Keine offenen Regel-Befunde."]
    default = (
        f"{len(findings)} offene Befunde: Review-Entscheidung treffen."
        if findings
        else "Projekt ist in Ordnung: Review kann kurz ausfallen."
    )
    return await _wrap(
        "review_summary",
        reasoning,
        default,
        {"findings": [f.model_dump() for f in findings]},
    )
