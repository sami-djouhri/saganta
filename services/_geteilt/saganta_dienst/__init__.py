"""Bausteine, die alle Saganta-Backends teilen.

Eingebunden wird das Paket ueber einen zweiten Build-Kontext (``geteilt`` in
``infra/docker-compose.yml``), nicht ueber einen Pfad im Quellbaum: jeder Dienst
baut aus seinem eigenen Verzeichnis, ein ``COPY ../_geteilt`` gibt es nicht.

Ob es in einem laufenden Dienst wirklich ankommt, beantwortet
``scripts/geteilte-schicht-probe.sh`` am Image, nicht am Quellbaum.
"""

from . import auth, tarife, zugriffslog

__all__ = ["auth", "tarife", "zugriffslog"]
