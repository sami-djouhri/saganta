FROM python:3.12-slim AS base
# Sicherheitsstand des Basis-Image nachziehen. Ein Upstream-Image friert die Paketstaende
# vom Tag seines Baus ein, Debian-security ist regelmaessig weiter, und ein `--pull` holt
# nur ein neueres Bild derselben Verspaetung: gemessen am 2026-09-13 trug das aktuelle
# python:3.13-slim aus der Registry dieselben drei perl-CVEs wie das monatealte lokale.
# `upgrade`, nicht `dist-upgrade`: letzteres darf Pakete entfernen, um Konflikte zu loesen.
RUN apt-get update \
 && apt-get -y upgrade \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg: transkodiert die XTTS-WAVs zu MP3 (Podcast-Enclosures mögen MP3).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -u 10001 -m -d /home/appuser appuser \
 && mkdir -p /data && chown appuser:appuser /data

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# Geteilte Bausteine (services/_geteilt) als zweiter Build-Kontext. Jeder Dienst
# baut aus seinem eigenen Verzeichnis, ein COPY ../_geteilt gibt es nicht.
# --no-deps ist Absicht: fastapi/pydantic/python-jose stehen bereits im
# pyproject dieses Dienstes, dort bleibt die Versionswahrheit.
COPY --from=geteilt . /geteilt
RUN pip install --no-deps /geteilt && chmod -R a+rX /geteilt

COPY app ./app
# Bytecode im Image ablegen. python:*-slim kommt OHNE .pyc der Standardbibliothek,
# PYTHONDONTWRITEBYTECODE verhindert, dass pip sie nebenbei erzeugt, und zur
# Laufzeit ist das rootfs read-only: jeder Python-Start (Dienst UND jeder
# Healthcheck alle 30 s) kompilierte urllib/http/email/re aus dem Quelltext neu.
# Gemessen 2026-10-31: 423 ms CPU je Healthcheck gegen ~150 ms bei Images mit .pyc.
# compileall schreibt explizit und ist von PYTHONDONTWRITEBYTECODE unberuehrt.
RUN python -m compileall -q "$(python -c 'import sysconfig;print(sysconfig.get_path("stdlib"))')" /geteilt /app
# Neu hinzugefügte Quelldateien können restriktive Host-Mode-Bits tragen (0600) →
# non-root appuser könnte sie sonst nicht importieren. Welt-lesbar erzwingen.
RUN chmod -R a+rX /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
