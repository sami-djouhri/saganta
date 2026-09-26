#!/usr/bin/env bash
# Testlauf der Tagebuch-API.
#
# Gelaufen wird im Dienst-Image, nicht gegen den Quellbaum. Das ist Absicht und
# stammt aus derselben Erfahrung wie services/_geteilt/run-tests.sh: ein Lauf
# gegen den Quellbaum beweist, dass die Dateien stimmen, nicht dass der Dienst
# sie hat. Am 30.08.2026 lag ein Filter in acht Baeumen und wirkte in einem.
#
# Erwartung: "36 passed". Laeuft eine kleinere Zahl durch, wurde ein Modul still
# uebersprungen, und das ist nicht als gruen zu verbuchen.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-saganta-tagebuch-api}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt. Erst bauen:"
  echo "  cd ../../infra && docker compose -f docker-compose.yml -f docker-compose.override.lan.yml build tagebuch-api"
  exit 1
fi

# --user 0:0 nur fuer den Testlauf: die Testdateien tragen im Quellbaum 660,
# der Dienst-Nutzer 10001 koennte sie sonst nicht lesen. Der Container ist ein
# Wegwerfstueck, die Rechte im Baum bleiben unangetastet.
exec docker run --rm --user 0:0 \
  -v "$(pwd)/tests":/app/tests:ro \
  -e ALLOW_INSECURE_SECRETS=1 \
  --entrypoint sh "$IMAGE" \
  -c 'pip install -q pytest httpx >/dev/null 2>&1; cd /app && python -m pytest tests -q '"$*"
