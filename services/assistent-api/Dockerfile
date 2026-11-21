FROM python:3.13-slim AS base
# Sicherheitsstand des Basis-Image nachziehen, Begruendung wie in
# services/kontakte-api/Dockerfile (ein `--pull` holt nur ein neueres Bild
# derselben Verspaetung). `upgrade`, nicht `dist-upgrade`.
RUN apt-get update \
 && apt-get -y upgrade \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd -u 10001 -m -d /home/appuser appuser

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# Geteilte Bausteine (services/_geteilt) als zweiter Build-Kontext, --no-deps
# wie bei den Schwestern: die Versionswahrheit steht im pyproject hier.
COPY --from=geteilt . /geteilt
RUN pip install --no-deps /geteilt && chmod -R a+rX /geteilt

# Rechte im Image setzen, nicht beim Kopieren (`COPY --chmod` wirkt nicht,
# gemessen 30.08.2026 an notizen-api).
COPY app ./app
# Bytecode im Image: das rootfs ist zur Laufzeit read-only (siehe kontakte-api).
RUN python -m compileall -q "$(python -c 'import sysconfig;print(sysconfig.get_path("stdlib"))')" /geteilt /app
RUN chmod -R a+rX /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
