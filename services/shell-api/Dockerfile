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
# Gemessen 2026-10-31 an notizen-api: 12 auf 5 ms/s CPU im Leerlauf.
# compileall schreibt explizit und ist von PYTHONDONTWRITEBYTECODE unberuehrt.
RUN python -m compileall -q "$(python -c 'import sysconfig;print(sysconfig.get_path("stdlib"))')" /geteilt /app
# Rechte im Quellbaum wandern durch COPY ins Image: eine ACL gibt neuen
# Dateien dort 660, und der Dienst laeuft als appuser. Ohne diese Zeile
# stirbt er beim Import an der eigenen Anwendung. Grosses X setzt das
# Ausfuehrrecht nur bei Verzeichnissen.
RUN chmod -R a+rX /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
