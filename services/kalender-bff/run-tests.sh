#!/usr/bin/env bash
# Testlauf des kalender-bff im Dienst-Image.
#
# WARUM NICHT EINFACH `pytest` IM REPO-ORDNER: zwei Stolpersteine, die beide
# als unverständlicher Fehler auftreten statt als Hinweis.
#
#   1. `.env` liegt hier und ist ein Secret (0600, dem Container-Nutzer 10001
#      bewusst verschlossen). `config.py` liest es beim Import über
#      pydantic-settings, im gemounteten Repo-Ordner scheitert schon der
#      Import mit „Permission denied: '.env'".
#   2. Der Anwendungscode steckt bereits im Image (COPY). Ihn zusätzlich zu
#      mounten bringt nur die Repo-Rechte mit, und die sind hier teils 660,
#      was derselbe Nutzer ebenfalls nicht lesen kann.
#
# Deshalb: NUR `tests/` dazumounten, den Rest aus dem Image nehmen. Die
# Geheimnisse kommen als Testwerte über die Umgebung.
#
# Erwartung: „Ran 22 tests ... OK". Laeuft eine kleinere Zahl durch, wurde ein
# Modul still uebersprungen, nicht als „gruen" verbuchen.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-saganta-kalender-bff}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt. Erst bauen:"
  echo "  cd ../../infra && docker compose -f docker-compose.yml -f docker-compose.override.lan.yml build kalender-bff"
  exit 1
fi

# ★ Die Testdateien müssen für uid 10001 lesbar sein. Neue Dateien bekommen in
# diesem Baum 660, dann findet unittest das Paket nicht und meldet lediglich
# „Start directory is not importable", was nach einem Pfadfehler aussieht.
find tests -type f -exec chmod a+r {} + 2>/dev/null || true
chmod a+rx tests 2>/dev/null || true

exec docker run --rm \
  -v "$(pwd)/tests":/app/tests:ro \
  -e JWT_SECRET=test-secret-nur-fuer-den-testlauf \
  -e ALLOWED_SUBS=owner-sub \
  -e KALENDER_OWNER_SUB=owner-sub \
  -e KALENDER_FEED_TOKEN=test-feed-token \
  --entrypoint sh "$IMAGE" \
  -c 'cd /app && python -m unittest discover -s tests -t /app '"$*"
