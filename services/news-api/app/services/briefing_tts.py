"""TTS-Rendering des Sprech-Textes → Audiodatei (WAV, optional MP3 via ffmpeg).

Spricht `POST {tts_url}/api/tts` (form: text/language/speaker) → WAV-Bytes,
503 = tts_busy. `tts_url` zeigt auf den `tts-gateway` (host:8146), nicht
direkt auf ein Backend: der Gateway hält die Warteschlange und entscheidet,
welches Backend die Anfrage bedient.

Hinter dem Gateway steht seit dem 2026-10-11 Kokoro-82M, vorher Coqui-XTTS.
Die API ist absichtlich dieselbe geblieben, der Wirtswechsel war also kein
Vertragswechsel. Für diesen Dienst heißt das vor allem: es ist deutlich
schneller geworden (gemessen 21,5 s gegen 231,1 s für denselben Absatz), die
Staffelung über den Scheduler bleibt aber richtig, weil die Synthese weiterhin
CPU-only läuft und ein einzelner Job das Backend belegt.

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


# Ziel-Lautheit nach EBU R128, wie bei Sprach-Podcasts üblich. Ohne diesen
# Schritt hing der Pegel am Backend: Kokoro liefert gemessen RMS 0,044 gegen
# 0,142 bei XTTS (rund 10 dB leiser, Briefings vom 24.07. und 30.10.2026), und
# der USB-Lautsprecher spielt mit festen 15 %. Das Briefing lief dort jeden
# Morgen fehlerfrei durch und war trotzdem nicht zu hören.
LAUTHEIT_LUFS = -16


def _abtastrate(wav_bytes: bytes) -> int | None:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            return w.getframerate()
    except Exception:
        return None


def _to_mp3(wav_bytes: bytes) -> bytes | None:
    """Transkodiert WAV→MP3 mit Lautheitsnormalisierung, falls ffmpeg im Image
    vorhanden ist (sonst None)."""
    if not shutil.which("ffmpeg"):
        return None
    # loudnorm rechnet intern mit 192 kHz und gibt diese Rate aus, wenn man sie
    # nicht zurücksetzt; deshalb die Rate der Quelle wiederherstellen.
    rate = _abtastrate(wav_bytes) or 24000
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-af", f"loudnorm=I={LAUTHEIT_LUFS}:TP=-1.5:LRA=11", "-ar", str(rate),
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
