#!/usr/bin/env bash
# Testlauf der Assistent-API, im Dienst-Image statt gegen den Quellbaum
# (Begruendung in services/kontakte-api/run-tests.sh).
#
# Erwartung: alle Tests aus tests/ laufen, keiner uebersprungen.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-saganta-assistent-api}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt. Erst bauen:"
  echo "  cd ../../infra && docker compose -f docker-compose.yml -f docker-compose.override.lan.yml build assistent-api"
  exit 1
fi

exec docker run --rm --user 0:0 \
  -v "$(pwd)/tests":/app/tests:ro \
  -e ALLOW_INSECURE_SECRETS=1 \
  --entrypoint sh "$IMAGE" \
  -c 'pip install -q pytest >/dev/null 2>&1; cd /app && python -m pytest tests -q '"$*"
