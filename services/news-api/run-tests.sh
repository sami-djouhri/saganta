#!/usr/bin/env bash
# Testlauf der news-api im Dienst-Image (gleiches Muster wie services/kalender-bff).
#
# WARUM NICHT EINFACH `pytest` IM REPO-ORDNER: `.env` liegt hier und ist ein
# Secret (0600, dem Container-Nutzer 10001 bewusst verschlossen). `config.py`
# liest es beim Import über pydantic-settings, im gemounteten Repo-Ordner
# scheitert schon der Import mit „Permission denied: '.env'". Deshalb: NUR
# `tests/` dazumounten, den Anwendungscode aus dem Image nehmen.
#
# Erwartung: „Ran 6 tests ... OK". Läuft eine kleinere Zahl durch, wurde ein
# Modul still übersprungen, nicht als „gruen" verbuchen.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-saganta-news-api}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt. Erst bauen:"
  echo "  cd ../../infra && docker compose -f docker-compose.yml -f docker-compose.override.lan.yml build news-api"
  exit 1
fi

# ★ Die Testdateien müssen für uid 10001 lesbar sein. Neue Dateien bekommen in
# diesem Baum 660, dann findet unittest das Paket nicht und meldet lediglich
# „Start directory is not importable", was nach einem Pfadfehler aussieht.
find tests -type f -exec chmod a+r {} + 2>/dev/null || true
chmod a+rx tests 2>/dev/null || true

# Geheimnisse als Testwerte: config.py ist fail-closed und bricht beim Import ab,
# wenn jwt_secret noch der unsichere Default ist. Der Wert hier ist erfunden, für
# einen Testlauf niemals das echte Secret aus der .env durchreichen.
exec docker run --rm \
  -v "$(pwd)/tests":/app/tests:ro \
  -e DATABASE_URL=sqlite:// \
  -e JWT_SECRET=test-secret-nur-fuer-den-testlauf \
  --entrypoint sh "$IMAGE" \
  -c 'cd /app && python -m unittest discover -s tests -t /app '"$*"
