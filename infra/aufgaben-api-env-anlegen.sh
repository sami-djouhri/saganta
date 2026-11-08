#!/usr/bin/env bash
# aufgaben-api-env-anlegen.sh legt die .env des Aufgaben-Dienstes an.
#
# Bauart wie tagebuch-env-anlegen.sh und aus demselben Grund: das Geheimnis ist
# kein neues. `JWT_SECRET` ist derselbe Wert wie `SAGANTA_BACKEND_SECRET` in den
# BFFs; mit ihm prueft dieser Dienst eingehende Token und stempelt die kurzen
# Token fuer den kalender-bff. Neu gewuerfelt antwortete er auf alles mit 401.
#
# Das Skript kopiert den Wert und gibt ihn NIE aus.
#
# Danach:
#   cd infra && docker compose -f docker-compose.yml \
#     -f docker-compose.override.lan.yml up -d --build aufgaben-api

set -euo pipefail

cd "$(dirname "$0")/.."
WURZEL="$(pwd)"

API_ENV="$WURZEL/services/aufgaben-api/.env"
QUELLE_SECRET="$WURZEL/apps/notizen/.env"    # SAGANTA_BACKEND_SECRET, ALLOWED_SUBS

fehler() { echo "FEHLER: $*" >&2; exit 1; }

[ -r "$QUELLE_SECRET" ] || fehler "Quelldatei nicht lesbar: $QUELLE_SECRET"
[ -e "$API_ENV" ] && fehler "$API_ENV existiert bereits, nichts angefasst."

hol() {
  local schluessel="$1" datei="$2" zeile
  zeile="$(grep -m1 "^${schluessel}=" "$datei" || true)"
  [ -n "$zeile" ] || fehler "$schluessel fehlt in $datei"
  printf '%s\n' "$zeile"
}

GEHEIM_ZEILE="$(hol SAGANTA_BACKEND_SECRET "$QUELLE_SECRET")"
SUBS_ZEILE="$(hol ALLOWED_SUBS "$QUELLE_SECRET")"
JWT_ZEILE="JWT_SECRET=${GEHEIM_ZEILE#SAGANTA_BACKEND_SECRET=}"

umask 077
{
  echo "# Angelegt von infra/aufgaben-api-env-anlegen.sh, Geheimnis UEBERNOMMEN."
  echo "DATABASE_URL=sqlite:////data/aufgaben.db"
  printf '%s\n' "$JWT_ZEILE"
  echo "JWT_ALGORITHM=HS256"
  echo "CORS_ORIGINS=https://aufgaben.home.arpa"
  printf '%s\n' "$SUBS_ZEILE"
  echo "KALENDER_BFF_URL=http://saganta-kalender-bff:8000"
} > "$API_ENV"
chmod 600 "$API_ENV"

echo "angelegt: services/aufgaben-api/.env"
sed 's/=.*/=…/' "$API_ENV" | grep -v '^#' | sed 's/^/    /'
if [ "${GEHEIM_ZEILE#*=}" = "${JWT_ZEILE#*=}" ]; then
  echo "OK: BFF-Stempel und Dienst-Pruefung tragen denselben Schluessel."
else
  fehler "Schluessel weichen ab, so wuerde jede Anfrage mit 401 enden."
fi
echo "Danach einmalig in den SOPS-Vault legen (die Projektregeln, Abschnitt Secrets)."
