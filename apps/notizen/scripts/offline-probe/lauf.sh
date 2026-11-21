#!/usr/bin/env bash
# Netzansicht und [[-Vorschlaege offline ansehen: eigener Bau, erfundene Daten,
# lokales Chromium. Bilder vom laufenden Dienst sind tabu (echte Notizen), und
# dieser Weg braucht weder Container noch Anmeldung.
# Aufruf: apps/notizen/scripts/offline-probe/lauf.sh  -> JSON auf stdout, Bilder in $PROBE_WURZEL/bilder
set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
APP="$(cd "$HIER/../.." && pwd)"
PROBE_WURZEL="${PROBE_WURZEL:-/tmp/notizen-probe}"
PORT="${PROBE_PORT:-8793}"
PLAYWRIGHT_CORE="${PLAYWRIGHT_CORE:-$(find "$HOME/.npm/_npx" -maxdepth 3 -type d -name playwright-core 2>/dev/null | head -1)}"
CHROME="${CHROME:-$(ls "$HOME"/.cache/ms-playwright/chromium-*/*/chrome 2>/dev/null | head -1)}"
[ -n "$PLAYWRIGHT_CORE" ] || { echo "playwright-core fehlt (npx playwright --version legt es an)" >&2; exit 2; }
[ -n "$CHROME" ] || { echo "Chromium fehlt unter ~/.cache/ms-playwright" >&2; exit 2; }
mkdir -p "$PROBE_WURZEL/bilder"
(cd "$APP" && npx vite build --config scripts/offline-probe/vite.config.ts --outDir "$PROBE_WURZEL/dist" --emptyOutDir >/dev/null)
python3 -I -m http.server "$PORT" --bind 127.0.0.1 --directory "$PROBE_WURZEL/dist" >/dev/null 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
sleep 1
PLAYWRIGHT_CORE="$PLAYWRIGHT_CORE" CHROME="$CHROME" PROBE_URL="http://127.0.0.1:$PORT/" \
  PROBE_BILDER="$PROBE_WURZEL/bilder" node "$HIER/probe.mjs"
