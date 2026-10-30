"""Das Briefing-MP3 muss unabhaengig vom TTS-Backend hoerbar laut sein.

Kokoro liefert rund 10 dB leiser als das vorherige XTTS (gemessen RMS 0,044
gegen 0,142). Der USB-Lautsprecher an host spielt mit festen 15 %, und das
Briefing lief dort wochenlang fehlerfrei durch, ohne dass es jemand hoerte.

Geprueft wird deshalb am Ergebnis und nicht am Befehl: ein leiser Sinuston
geht hinein, das dekodierte MP3 muss deutlich lauter herauskommen, ohne zu
uebersteuern, und mit der Abtastrate der Quelle (loudnorm gibt sonst 192 kHz aus).
"""
import io
import math
import os
import shutil
import struct
import subprocess
import unittest
import wave

os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-pruefung")

from app.services.briefing_tts import _to_mp3  # noqa: E402

RATE = 24000


def _leises_wav(sekunden: float = 4.0, pegel: float = 0.03) -> bytes:
    n = int(RATE * sekunden)
    frames = b"".join(
        struct.pack("<h", int(pegel * 32767 * math.sin(2 * math.pi * 220 * i / RATE)))
        for i in range(n)
    )
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    return out.getvalue()


def _dekodieren(mp3: bytes) -> tuple[int, list[int]]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-f", "wav", "pipe:1"],
        input=mp3, capture_output=True, check=True,
    )
    with wave.open(io.BytesIO(proc.stdout), "rb") as w:
        rate = w.getframerate()
        roh = w.readframes(w.getnframes())
    proben = list(struct.unpack(f"<{len(roh) // 2}h", roh))
    return rate, proben


def _rms(proben: list[int]) -> float:
    return math.sqrt(sum(p * p for p in proben) / len(proben)) / 32768


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg fehlt")
class Lautheit(unittest.TestCase):
    def test_leise_quelle_wird_angehoben(self):
        quelle = _leises_wav()
        mp3 = _to_mp3(quelle)
        self.assertIsNotNone(mp3)
        rate, proben = _dekodieren(mp3)
        self.assertEqual(rate, RATE)
        with wave.open(io.BytesIO(quelle), "rb") as w:
            roh = w.readframes(w.getnframes())
        rms_quelle = _rms(list(struct.unpack(f"<{len(roh) // 2}h", roh)))
        self.assertLess(rms_quelle, 0.03)  # die Quelle ist wirklich leise
        self.assertGreater(_rms(proben), 3 * rms_quelle)
        self.assertLess(max(abs(p) for p in proben) / 32768, 0.99)


if __name__ == "__main__":
    unittest.main()
