#!/usr/bin/env bash
# kontakte-env-anlegen.sh: legt die beiden .env von Saganta Kontakte an,
# die des Dienstes (services/kontakte-api) und die der Web-App (apps/kontakte).
#
# Bauart wie aufgaben-env-anlegen.sh und aufgaben-api-env-anlegen.sh, aus
# demselben Grund: das Geheimnis ist kein neues. `SAGANTA_BACKEND_SECRET` der
# BFFs ist im Dienst `JWT_SECRET`; mit ihm prueft er eingehende Token und
# stempelt die kurzen Token fuer den kalender-bff. Neu gewuerfelt antwortete
# er auf alles mit 401.
#
# Das Skript kopiert den Wert und gibt ihn NIE aus. Bestehende Dateien bleiben
# unangetastet.
#
# Danach:
#   cd infra && docker compose -f docker-compose.yml \
#     -f docker-compose.override.lan.yml up -d --build kontakte-api kontakte

set -euo pipefail

cd "$(dirname "$0")/.."
WURZEL="$(pwd)"

API_ENV="$WURZEL/services/kontakte-api/.env"
APP_ENV="$WURZEL/apps/kontakte/.env"
QUELLE_SECRET="$WURZEL/apps/notizen/.env"    # SAGANTA_BACKEND_SECRET, ALLOWED_SUBS

fehler() { echo "FEHLER: $*" >&2; exit 1; }

[ -r "$QUELLE_SECRET" ] || fehler "Quelldatei nicht lesbar: $QUELLE_SECRET"

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

if [ -e "$API_ENV" ]; then
  echo "bleibt: services/kontakte-api/.env (existiert bereits)"
else
  {
    echo "# Angelegt von infra/kontakte-env-anlegen.sh, Geheimnis UEBERNOMMEN."
    echo "DATABASE_URL=sqlite:////data/kontakte.db"
    printf '%s\n' "$JWT_ZEILE"
    echo "JWT_ALGORITHM=HS256"
    echo "CORS_ORIGINS=https://kontakte.home.arpa"
    printf '%s\n' "$SUBS_ZEILE"
    echo "KALENDER_BFF_URL=http://saganta-kalender-bff:8000"
  } > "$API_ENV"
  chmod 600 "$API_ENV"
  echo "angelegt: services/kontakte-api/.env"
  sed 's/=.*/=…/' "$API_ENV" | grep -v '^#' | sed 's/^/    /'
fi

if [ -e "$APP_ENV" ]; then
  echo "bleibt: apps/kontakte/.env (existiert bereits)"
else
  {
    echo "# Angelegt von infra/kontakte-env-anlegen.sh. Geheimnis UEBERNOMMEN."
    echo "AUTH_SERVICE_URL=http://saganta-auth:3000"
    echo "KONTAKTE_API_BASE_URL=http://saganta-kontakte-api:8000"
    printf '%s\n' "$SUBS_ZEILE"
    printf '%s\n' "$GEHEIM_ZEILE"
    echo "HOST=0.0.0.0"
    echo "PORT=3000"
    echo "# Ohne diese beiden haelt adapter-node den eigenen Ursprung fuer http://"
    echo "# und lehnt jedes POST als Ursprungs-Konflikt ab."
    echo "PROTOCOL_HEADER=x-forwarded-proto"
    echo "HOST_HEADER=x-forwarded-host"
  } > "$APP_ENV"
  chmod 600 "$APP_ENV"
  echo "angelegt: apps/kontakte/.env"
  sed 's/=.*/=…/' "$APP_ENV" | grep -v '^#' | sed 's/^/    /'
fi

[ "${GEHEIM_ZEILE#*=}" = "${JWT_ZEILE#*=}" ] \
  || fehler "Schluessel weichen ab, so wuerde jede Anfrage mit 401 enden."
echo "OK: BFF-Stempel und Dienst-Pruefung tragen denselben Schluessel."
echo "Danach einmalig in den SOPS-Vault legen (die Projektregeln, Abschnitt Secrets)."
