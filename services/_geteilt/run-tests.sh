#!/usr/bin/env bash
# Testlauf der geteilten Schicht.
#
# Gelaufen wird in einem beliebigen Dienst-Image, denn dort ist `saganta_dienst`
# so installiert, wie es im Betrieb vorliegt. Das ist Absicht: ein Testlauf
# gegen den Quellbaum wuerde beweisen, dass die Datei stimmt, nicht dass der
# Dienst sie hat. Genau diese Luecke war am 30.08.2026 der Fehler.
#
# Erwartung: "Ran 43 tests ... OK". Laeuft eine kleinere Zahl durch, wurde ein
# Modul still uebersprungen, das ist nicht als gruen zu verbuchen.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-saganta-notizen-api}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt. Erst bauen:"
  echo "  cd ../../infra && docker compose -f docker-compose.yml -f docker-compose.override.lan.yml build notizen-api"
  exit 1
fi

# --user 0:0 nur fuer den Testlauf: die Testdateien tragen im Quellbaum 660,
# der Dienst-Nutzer 10001 koennte sie sonst nicht lesen. Der Container ist ein
# Wegwerfstueck, die Rechte im Baum bleiben unangetastet.
exec docker run --rm --user 0:0 \
  -v "$(pwd)/tests":/geteilt-tests:ro \
  -e ALLOW_INSECURE_SECRETS=1 \
  --entrypoint sh "$IMAGE" \
  -c 'pip install -q httpx >/dev/null 2>&1; cd /geteilt-tests && python -m unittest discover -s . -t . -v '"$*"
