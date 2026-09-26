"""TTS-Rendering des Sprech-Textes → Audiodatei (WAV, optional MP3 via ffmpeg).

Spricht denselben Coqui-XTTS-Endpunkt an wie das alte briefing_lib.py:
`POST {tts_url}/api/tts` (form: text/language/speaker) → WAV-Bytes, 503 = tts_busy.

XTTS läuft CPU-only (~44 s/Chunk, Memory feedback_local_cpu_llm_latency) → wird nur
vom nächtlichen Scheduler gestaffelt aufgerufen, nie synchron im Request-Pfad.
Soft-Fail: kein tts_url oder Fehler → (None, None), Briefing bleibt textlich nutzbar.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import time
import wave

import httpx
import structlog

from ..config import settings

log = structlog.get_logger()


def available() -> bool:
    return bool(settings.tts_url)


def _split(text: str, max_chars: int = 480) -> list[str]:
    chunks: list[str] = []
    cur = ""
    for raw in text.replace("\n", " ").split(". "):
        s = raw.strip()
        if not s:
            continue
        if not s.endswith("."):
            s += "."
        if len(cur) + len(s) + 1 > max_chars and cur:
            chunks.append(cur.strip())
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur.strip())
    return chunks or [text[:max_chars]]


def _synth_chunk(text: str, speaker: str, language: str) -> bytes | None:
    url = settings.tts_url.rstrip("/") + "/api/tts"
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=settings.tts_timeout) as client:
                resp = client.post(
                    url,
                    data={"text": text, "language": language, "speaker": speaker},
                    # tts-gateway-Job-Bus: Briefing ist Batch -> niedrigste Prio, damit
                    # interaktive Voice (host-router/HA-Assist) an der Chunk-Grenze ueberholt.
                    headers={"Connection": "close", "X-TTS-Priority": "batch"},
                )
            if resp.status_code == 503 and "tts_busy" in (resp.text or ""):
                log.warning("tts.busy", attempt=attempt)
                time.sleep(5)
                continue
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            log.warning("tts.chunk.error", attempt=attempt, error=str(exc)[:200])
            time.sleep(3)
    return None


def _concat_wavs(wavs: list[bytes]) -> bytes | None:
    frames_params = None
    out = io.BytesIO()
    writer: wave.Wave_write | None = None
    try:
        for raw in wavs:
            with wave.open(io.BytesIO(raw), "rb") as w:
                if writer is None:
                    frames_params = w.getparams()
                    writer = wave.open(out, "wb")
                    writer.setparams(frames_params)
                writer.writeframes(w.readframes(w.getnframes()))
        if writer is None:
            return None
        writer.close()
        return out.getvalue()
    except Exception as exc:
        log.warning("tts.concat.error", error=str(exc)[:200])
        return None


def _to_mp3(wav_bytes: bytes) -> bytes | None:
    """Transkodiert WAV→MP3, falls ffmpeg im Image vorhanden ist (sonst None)."""
    if not shutil.which("ffmpeg"):
        return None
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-codec:a", "libmp3lame", "-qscale:a", "5", "-f", "mp3", "pipe:1"],
            input=wav_bytes, capture_output=True, timeout=120,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        log.warning("tts.mp3.ffmpeg_failed", err=proc.stderr[:200].decode("utf-8", "ignore"))
    except Exception as exc:
        log.warning("tts.mp3.error", error=str(exc)[:200])
    return None


def render(sub: str, briefing_date: str, spoken_text: str, voice: str = "") -> tuple[str | None, str | None]:
    """Rendert den Sprech-Text. Gibt (dateipfad, mime) oder (None, None) zurück."""
    if not available() or not spoken_text.strip():
        return None, None

    speaker = voice or settings.tts_speaker
    chunks = _split(spoken_text)
    wavs: list[bytes] = []
    for ch in chunks:
        raw = _synth_chunk(ch, speaker, settings.tts_language)
        if raw is None:
            log.warning("tts.render.aborted", sub=sub, done=len(wavs), total=len(chunks))
            return None, None
        wavs.append(raw)

    merged = _concat_wavs(wavs) if len(wavs) > 1 else wavs[0]
    if not merged:
        return None, None

    user_dir = os.path.join(settings.audio_dir, sub)
    os.makedirs(user_dir, exist_ok=True)

    mp3 = _to_mp3(merged)
    if mp3:
        path = os.path.join(user_dir, f"{briefing_date}.mp3")
        with open(path, "wb") as f:
            f.write(mp3)
        return path, "audio/mpeg"

    path = os.path.join(user_dir, f"{briefing_date}.wav")
    with open(path, "wb") as f:
        f.write(merged)
    return path, "audio/wav"
