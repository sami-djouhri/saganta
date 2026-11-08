"""Soll-Zustand eines Containers aus der control-map, fuer die Konto-Werkzeuge.

Die drei Werkzeuge (konto-loeschen, loeschwege-abgleichen, verwaiste-mandanten)
fragen in jeden Dienst hinein. Ein Dienst, der nicht laeuft, ist dabei zweierlei:
bewusst aus (stillgelegt, on-demand, Tresor zu) oder ausgefallen. Fuer die
Messung ist beides gleich, sein Bestand ist ungeprueft. Fuer eine Wache nicht:
der erste Fall ist der Normalfall und darf nicht jeden Morgen melden, der
zweite ist ein Befund.

Die Unterscheidung kommt aus `control-map/services.yaml` (`expected_state`),
nicht aus einer Liste hier. Eine zweite Liste wuerde genau dann luegen, wenn ein
Dienst stillgelegt oder wieder geweckt wird.
"""
from __future__ import annotations

import pathlib
import subprocess

SERVICES_YAML = pathlib.Path.home() / "control-map" / "services.yaml"

# Zustaende, in denen "laeuft nicht" der gewollte Fall ist.
RUHEND = {"stopped", "manual", "migrated", "planned", "exited"}

_cache: dict[str, str] | None = None


def _soll_tabelle() -> dict[str, str]:
    global _cache
    if _cache is None:
        _cache = {}
        try:
            import yaml
            eintraege = yaml.safe_load(SERVICES_YAML.read_text(encoding="utf-8")) or []
            if isinstance(eintraege, dict):
                eintraege = eintraege.get("services") or []
            for e in eintraege:
                if isinstance(e, dict) and e.get("host") == "host" and e.get("container"):
                    _cache[str(e["container"])] = str(e.get("expected_state") or "")
        except Exception:
            # Ohne control-map gilt jeder nicht laufende Dienst als Befund. Das
            # ist die strengere Seite und meldet lieber zu viel als zu wenig.
            _cache = {}
    return _cache


def laeuft(container: str) -> bool:
    try:
        lauf = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return False
    return lauf.returncode == 0 and lauf.stdout.strip() == "true"


def ruht(container: str) -> str | None:
    """Den Soll-Zustand nennen, wenn der Container laut control-map aus sein darf."""
    zustand = _soll_tabelle().get(container, "")
    return zustand if zustand in RUHEND else None
