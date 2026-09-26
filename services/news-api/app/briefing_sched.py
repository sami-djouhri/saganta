"""Per-User-Scheduler für die Briefing-Generierung.

Jede Minute wird geprüft, welche aktivierten Profile für HEUTE „fällig" sind
(ihre `delivery_time` (Berlin-Ortszeit) ist erreicht und es existiert noch kein
Briefing für den Tag) → genau dann wird generiert + (bei audio_enabled) vertont +
der Webhook gefeuert. So landet das Briefing zur Wunschzeit im Homelab statt in
einem globalen Nachtlauf.

Robustheit:
- Idempotent pro (sub, Tag): existiert das UserBriefing schon, wird kein zweites erzeugt.
- **Fehlendes Audio wird nachgezogen, statt den Tag als erledigt zu betrachten.**
  Der Lesepfad (`GET /today`) erzeugt das Briefing bei Bedarf selbst, aber bewusst
  nur den Text: Audio ist CPU-schwer und niemand soll im Request darauf warten.
  Wer die Seite vor seiner Wunschzeit öffnet, hatte damit ein Briefing ohne Audio,
  und der Scheduler sprang für diesen Tag komplett aus: kein Audio, kein Webhook,
  ausgerechnet am Morgen. „Fällig" heisst deshalb nicht „es existiert etwas",
  sondern „das, was zur Wunschzeit da sein soll, ist da".
- Catch-up: war der Dienst zur Wunschzeit aus, wird beim nächsten Tick nachgeholt
  (die tageszeit-abhängige Begrüßung passt sich an).
- Generierung ist synchron/CPU-schwer (TTS) → im Thread, blockiert den Event-Loop
  (Feed-Poller) nicht. Ein langsamer User hält höchstens den nächsten Tick auf.
- Tägliche Retention-Bereinigung um 03:00 Berlin.
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

from .briefing_models import BriefingProfile, UserBriefing
from .config import settings
from .db import SessionLocal
from .errors import describe
from .services import briefing_service

log = structlog.get_logger()

BERLIN = ZoneInfo("Europe/Berlin")

# Beobachtbarkeit (sched-status-Endpoint). In-Process, überlebt keinen Restart.
_state: dict[str, object] = {
    "last_tick_at": None,
    "last_generated": [],       # subs, die beim letzten Tick erzeugt wurden
    "last_audio_retried": [],   # subs, deren fehlendes Audio nachgezogen wurde
    "last_audio_deferred": [],  # subs, deren Audio wegen des Deckels wartet
    "generated_today": 0,
    "last_error": None,
    "ticks": 0,
}


def _parse_hhmm(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        h, m = value.split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
    except (ValueError, AttributeError):
        pass
    return None


def status() -> dict[str, object]:
    return {**_state, "mode": "per-user-delivery-time", "retention_days": settings.briefing_retention_days}


def _tick() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(BERLIN)
        today = now.date()
        now_min = now.hour * 60 + now.minute

        # Retention einmal täglich (03:00), vor der Morgen-Generierung.
        if now.hour == 3 and now.minute == 0:
            briefing_service.cleanup(db)

        profiles = db.query(BriefingProfile).filter(BriefingProfile.enabled.is_(True)).all()
        generated: list[str] = []
        audio_nachgezogen: list[str] = []
        audio_verschoben: list[str] = []
        # Deckel fuer die Sprachsynthese in DIESEM Durchlauf (s. config).
        audio_uebrig = max(0, settings.briefing_audio_max_per_tick)
        for prof in profiles:
            hm = _parse_hhmm(prof.delivery_time) or (6, 30)  # Fallback-Wunschzeit
            if now_min < hm[0] * 60 + hm[1]:
                continue  # heute noch nicht fällig
            already = (
                db.query(UserBriefing)
                .filter(UserBriefing.sub == prof.sub, UserBriefing.briefing_date == today)
                .one_or_none()
            )
            if already:
                # Existiert, aber ohne das gewünschte Audio (typisch: der Nutzer hat die
                # Seite vor seiner Wunschzeit geöffnet, der Lesepfad erzeugte nur Text).
                # Dann fehlt genau das Stück, für das es den Scheduler gibt → nachziehen.
                if briefing_service.audio_erlaubt(prof) and not already.audio_path:
                    if not audio_uebrig:
                        # Kein Verlust: der naechste Tick ist in einer Minute und
                        # findet denselben Zustand vor, "Briefing da, Audio fehlt".
                        audio_verschoben.append(prof.sub)
                        continue
                    try:
                        if briefing_service.render_audio(db, prof.sub, today):
                            audio_nachgezogen.append(prof.sub)
                            audio_uebrig -= 1
                    except Exception as exc:
                        db.rollback()
                        log.error("briefing.audio.retry.error", sub=prof.sub, error=describe(exc))
                continue  # Text steht schon, kein zweiter Aufbau
            try:
                # Reicht der Deckel nicht mehr, bekommt dieser Nutzer erst einmal
                # nur den Text. Das ist der Teil, auf den es ankommt, wenn jemand
                # um 06:30 die Seite oeffnet; die Sprachfassung holt der naechste
                # Tick nach.
                # Der Tarif entscheidet mit, damit der knappe Deckel nicht von
                # Sprachfassungen aufgebraucht wird, die ohnehin nicht erzeugt werden.
                will_audio = briefing_service.audio_erlaubt(prof)
                mit_audio = will_audio and audio_uebrig > 0
                if will_audio and not mit_audio:
                    audio_verschoben.append(prof.sub)
                briefing_service.generate_for_sub(
                    db, prof.sub, today, force=True, with_audio=mit_audio
                )
                if mit_audio:
                    audio_uebrig -= 1
                generated.append(prof.sub)
            except Exception as exc:  # ein User darf den Tick nicht killen
                db.rollback()
                log.error("briefing.gen.error", sub=prof.sub, error=describe(exc))

        _state["last_tick_at"] = now.isoformat()
        _state["last_generated"] = generated
        _state["last_audio_retried"] = audio_nachgezogen
        _state["last_audio_deferred"] = audio_verschoben
        _state["generated_today"] = int(_state["generated_today"] or 0) + len(generated)
        _state["ticks"] = int(_state["ticks"] or 0) + 1
        _state["last_error"] = None
        if generated:
            log.info("briefing.sched.generated", count=len(generated))
        if audio_nachgezogen:
            log.info("briefing.sched.audio_retried", count=len(audio_nachgezogen))
        if audio_verschoben:
            # Sichtbar machen, dass gedeckelt wurde. Ein stiller Deckel sieht im
            # Betrieb aus wie ein Dienst, der manche Nutzer einfach vergisst.
            log.info(
                "briefing.sched.audio_deferred",
                count=len(audio_verschoben),
                deckel=settings.briefing_audio_max_per_tick,
            )
    finally:
        db.close()


async def briefing_loop() -> None:
    log.info("briefing.sched.start", mode="per-user-delivery-time")
    while True:
        try:
            await asyncio.to_thread(_tick)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # Loop-Backstop
            _state["last_error"] = describe(exc)
            log.error("briefing.sched.error", error=describe(exc))
        await asyncio.sleep(60)
