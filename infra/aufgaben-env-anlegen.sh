#!/usr/bin/env bash
# aufgaben-env-anlegen.sh: legt die .env der Aufgaben-App an.
#
# WARUM ES DIESES SKRIPT GIBT: das Geheimnis dieser App ist kein neues.
# `SAGANTA_BACKEND_SECRET` ist der Schluessel, mit dem *alle* BFFs ihre
# kurzlebigen Backend-Token stempeln. Wuerde man hier neu wuerfeln, antwortete
# der kalender-bff auf jede Anfrage mit 401, und zwar erst im Betrieb, nicht
# beim Start: der Container waere gruen und die App leer.
#
# Das Skript kopiert den Wert deshalb aus einer bestehenden .env und gibt ihn
# NIE aus. Was auf dem Bildschirm landet, sind ausschliesslich Schluesselnamen.
#
# ★ Die App hat **kein eigenes Backend und kein Volume**: Aufgaben, Ziele und
# Projekte liegen in der einen Kalender-Engine, die Notiz-Verknuepfung in der
# notizen-api. Deshalb gibt es hier nur eine Datei, nicht zwei.
#
# Danach:
#   cd infra && docker compose -f docker-compose.yml \
#     -f docker-compose.override.lan.yml up -d --build aufgaben
#
# Und einmalig in den SOPS-Vault legen (siehe die Projektregeln, Abschnitt Secrets).

set -euo pipefail

cd "$(dirname "$0")/.."
WURZEL="$(pwd)"

APP_ENV="$WURZEL/apps/aufgaben/.env"
QUELLE_SECRET="$WURZEL/apps/notizen/.env"   # SAGANTA_BACKEND_SECRET, ALLOWED_SUBS

fehler() { echo "FEHLER: $*" >&2; exit 1; }

[ -r "$QUELLE_SECRET" ] || fehler "Quelldatei nicht lesbar: $QUELLE_SECRET"

# Nichts ueberschreiben. Eine bestehende .env ist der Live-Zustand; sie hier
# stillschweigend zu ersetzen waere genau der Vorfall, den die Deploy-Regeln
# dieses Projekts verhindern sollen.
[ -e "$APP_ENV" ] && fehler "$APP_ENV existiert bereits, nichts angefasst."

# Wert holen, ohne ihn anzuzeigen.
hol() {
  local schluessel="$1" datei="$2" zeile
  zeile="$(grep -m1 "^${schluessel}=" "$datei" || true)"
  [ -n "$zeile" ] || fehler "$schluessel fehlt in $datei"
  printf '%s\n' "$zeile"
}

GEHEIM_ZEILE="$(hol SAGANTA_BACKEND_SECRET "$QUELLE_SECRET")"
SUBS_ZEILE="$(hol ALLOWED_SUBS "$QUELLE_SECRET")"

umask 077

{
  echo "# Angelegt von infra/aufgaben-env-anlegen.sh. Geheimnis UEBERNOMMEN,"
  echo "# nicht neu erzeugt. Siehe apps/aufgaben/README.md."
  echo "AUTH_SERVICE_URL=http://saganta-auth:3000"
  echo "AUTH_LOGIN_URL=https://saganta.de/login"
  echo "# Die Datenquellen. Beide haengen mit dieser App in cc-core."
  echo "KALENDER_BFF_BASE_URL=http://saganta-kalender-bff:8000"
  echo "NOTIZEN_API_BASE_URL=http://saganta-notizen-api:8000"
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

echo "angelegt: apps/aufgaben/.env"
sed 's/=.*/=…/' "$APP_ENV" | grep -v '^#' | sed 's/^/    /'

cat <<'HINWEIS'

Naechste Schritte:
  1) cd infra && docker compose -f docker-compose.yml \
       -f docker-compose.override.lan.yml up -d --build aufgaben
  2) Rauchtest:  bash ../scripts/aufgaben-rauchtest.sh
  3) .env in den SOPS-Vault legen (die Projektregeln, Abschnitt Secrets).

Damit die App erreichbar ist, braucht sie ausserdem DREI Eintraege ausserhalb
dieses Repos (sonst ist sie nur halb da, siehe die Projektregeln):
  - server_name aufgaben.home.arpa im dev-portal-Vhost
  - DNS-Rewrite in AdGuard (docker/adguard/rewrite-setzen.sh)
  - ui_url in der control-map fuers Launchpad
HINWEIS
