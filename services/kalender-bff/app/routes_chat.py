"""Fragen an den eigenen Kalender, beantwortet von einem Modell im Haus.

**Der Gegenpol zur Freitext-Eingabe in der App.** Die legt Termine an und
kommt ohne Netz aus, weil ihre Regeln auf dem Geraet liegen. Dies hier ist der
andere Fall: „wann habe ich diese Woche noch zwei Stunden frei" laesst sich
nicht mit Regeln beantworten, sondern braucht ein Modell und die Daten. Also
laeuft es im Haus und nur dort, und die App sagt das, statt einen Knopf grau zu
faerben.

**Nur lesen.** Das Modell bekommt Text und gibt Text. Es legt nichts an,
aendert nichts und loescht nichts, es hat dafuer auch keinen Weg. Eine Antwort,
die danebenliegt, kostet hier nichts ausser einer weiteren Frage; ein Modell mit
Schreibrecht auf den Kalender haette Termine erfunden, an denen die Weckkette
haengt.

**Nur ein Modell im Haus.** Die Termine dieses Hauses gehen an keinen fremden
Dienst (Entscheid 2026-09-20).
Das Gateway kann auch Fremdmodelle vermitteln, deshalb steht die erlaubte Menge
hier als Liste und nicht nur als Vorgabewert: ein Tippfehler in der Umgebung
waere sonst ein stiller Abfluss.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .config import settings
from .upstream import authed_kalender_client

router = APIRouter()

# Aliase, die gemessen auf ein Modell in diesem Haus zeigen (siehe
# die Projektregeln, Abschnitt AI-Services). Wer hier einen Namen
# ergaenzt, muss belegen, dass er im Haus endet.
ERLAUBTE_MODELLE = {"homelab-fast", "homelab-smart", "homelab-large"}

_SYSTEM = (
    "Du beantwortest Fragen zum Kalender des Nutzers. Du bekommst seine Termine "
    "und Aufgaben als Liste. Antworte kurz, auf Deutsch, in hoechstens drei "
    "Saetzen. Nenne konkrete Tage und Uhrzeiten. Wenn die Daten die Frage nicht "
    "hergeben, sage das klar, statt etwas zu vermuten."
)


class FrageIn(BaseModel):
    frage: str = Field(..., min_length=1, max_length=500)
    # Wie weit nach vorn geschaut wird. Mehr Tage heisst mehr Kontext und
    # langsamere Antwort; eine Woche deckt die uebliche Frage ab.
    tage: int = Field(default=7, ge=1, le=31)


def _modell() -> str | None:
    """Das konfigurierte Modell, falls es eines im Haus ist."""
    name = (settings.llm_model or "").strip()
    return name if name in ERLAUBTE_MODELLE else None


async def _kontext(tage: int) -> tuple[str, int]:
    """Termine und Aufgaben des Fensters als Klartext fuer das Modell."""
    heute = _date.today()
    bis = heute + timedelta(days=tage)
    async with authed_kalender_client() as client:
        try:
            r = await client.get(
                "/api/mobile/bootstrap",
                params={"start": heute.isoformat(), "end": bis.isoformat()},
            )
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    daten = r.json() if r.content else {}

    zeilen: list[str] = [f"Heute ist {heute.isoformat()} ({heute.strftime('%A')})."]
    tagestypen = {t.get("date"): t.get("type") for t in daten.get("daytypes") or []}
    if tagestypen:
        zeilen.append("Tagestypen: " + ", ".join(
            f"{tag}={typ}" for tag, typ in sorted(tagestypen.items()) if typ
        ))

    termine = daten.get("events") or []
    zeilen.append(f"Termine ({len(termine)}):")
    for e in termine:
        # Bewusst nur Titel und Zeit. Beschreibung und Ort bleiben hier, auch
        # wenn das Modell im Haus laeuft: was nicht gebraucht wird, wird nicht
        # weitergereicht.
        start = str(e.get("start") or "")[:16].replace("T", " ")
        ende = str(e.get("end") or "")[11:16]
        ganztags = " (ganztaegig)" if e.get("all_day") else ""
        zeilen.append(f"- {start} bis {ende}{ganztags}: {e.get('title')}")

    aufgaben = [t for t in (daten.get("todos") or []) if not t.get("completed")]
    if aufgaben:
        zeilen.append(f"Offene Aufgaben ({len(aufgaben)}):")
        for t in aufgaben:
            frist = t.get("due_date") or "ohne Frist"
            zeilen.append(f"- {t.get('title')} ({frist})")

    return "\n".join(zeilen), len(termine)


@router.post("/api/chat")
async def frage_stellen(data: FrageIn, me: Me = CurrentUser) -> dict:
    """Eine Frage zum eigenen Kalender, beantwortet von einem Modell im Haus."""
    modell = _modell()
    if not settings.llm_gateway_url or not modell:
        # ⚠️ 503 und nicht 200 mit einem Hinweistext: ein Aufrufer, der eine
        # Antwort bekommt, kann nicht unterscheiden, ob das Modell geschwiegen
        # oder gar nicht geantwortet hat.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Kein Modell im Haus konfiguriert. Gesetzt sein muessen "
            "LLM_GATEWAY_URL und ein LLM_MODEL aus "
            f"{sorted(ERLAUBTE_MODELLE)}.",
        )

    kontext, anzahl = await _kontext(data.tage)
    nutzer = f"{kontext}\n\nFrage: {data.frage}"

    url = settings.llm_gateway_url.rstrip("/") + "/v1/chat/completions"
    kopf = {}
    if settings.llm_gateway_key:
        kopf["Authorization"] = f"Bearer {settings.llm_gateway_key}"
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            r = await client.post(
                url,
                json={
                    "model": modell,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": nutzer},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.2,
                },
                headers=kopf,
            )
        r.raise_for_status()
        inhalt = (r.json().get("choices") or [{}])[0].get("message", {}).get("content")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Modell nicht erreichbar: {str(e)[:200]}") from e

    text = inhalt.strip() if isinstance(inhalt, str) else ""
    if not text:
        # Ein leeres Ergebnis ist bei Thinking-Modellen der Normalfall eines zu
        # knappen Token-Budgets, nicht ein Fehler des Gateways. Als Erfolg
        # zurueckgegeben saehe es aus, als haette das Modell nichts zu sagen.
        raise HTTPException(502, "Das Modell hat nichts geantwortet.")

    return {"antwort": text, "modell": modell, "termine_im_kontext": anzahl}
