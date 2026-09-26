#!/usr/bin/env bash
# tagebuch-env-anlegen.sh legt die beiden .env-Dateien der Tagebuch-App an.
#
# WARUM ES DIESES SKRIPT GIBT: die Geheimnisse dieser App sind keine neuen.
# `SAGANTA_BACKEND_SECRET` ist der Schluessel, mit dem *alle* BFFs ihre
# kurzlebigen Backend-Token stempeln, und `JWT_SECRET` im Backend ist derselbe
# Wert von der anderen Seite. Wuerde man hier neu wuerfeln, antwortete das
# Backend auf jede Anfrage mit 401, und zwar erst im Betrieb, nicht beim Start.
#
# Das Skript kopiert die Werte deshalb aus bestehenden .env-Dateien und gibt sie
# NIE aus. Was auf dem Bildschirm landet, sind ausschliesslich Schluesselnamen.
#
# ★ Kein Geheimnis dieser Datei kann ein Tagebuch oeffnen. Der Schluessel dafuer
# entsteht im Browser aus der Passphrase und liegt nirgends auf dem Wirt. Wer
# `JWT_SECRET` hat, kann sich als Nutzer ausgeben und Chiffrat abholen, mehr
# nicht.
#
# Danach:
#   cd infra && docker compose -f docker-compose.yml \
#     -f docker-compose.override.lan.yml up -d --build tagebuch tagebuch-api
#
# Und einmalig in den SOPS-Vault legen (siehe die Projektregeln, Abschnitt Secrets).

set -euo pipefail

cd "$(dirname "$0")/.."
WURZEL="$(pwd)"

APP_ENV="$WURZEL/apps/tagebuch/.env"
API_ENV="$WURZEL/services/tagebuch-api/.env"
QUELLE_SECRET="$WURZEL/apps/notizen/.env"    # SAGANTA_BACKEND_SECRET, ALLOWED_SUBS

fehler() { echo "FEHLER: $*" >&2; exit 1; }

[ -r "$QUELLE_SECRET" ] || fehler "Quelldatei nicht lesbar: $QUELLE_SECRET"

# Nichts ueberschreiben. Eine bestehende .env ist der Live-Zustand; sie hier
# stillschweigend zu ersetzen waere genau der Vorfall, den die Deploy-Regeln
# dieses Projekts verhindern sollen.
for datei in "$APP_ENV" "$API_ENV"; do
  [ -e "$datei" ] && fehler "$datei existiert bereits, nichts angefasst."
done

# Wert holen, ohne ihn anzuzeigen.
hol() {
  local schluessel="$1" datei="$2" zeile
  zeile="$(grep -m1 "^${schluessel}=" "$datei" || true)"
  [ -n "$zeile" ] || fehler "$schluessel fehlt in $datei"
  printf '%s\n' "$zeile"
}

GEHEIM_ZEILE="$(hol SAGANTA_BACKEND_SECRET "$QUELLE_SECRET")"
SUBS_ZEILE="$(hol ALLOWED_SUBS "$QUELLE_SECRET")"

# Fuer das Backend heisst derselbe Wert JWT_SECRET.
JWT_ZEILE="JWT_SECRET=${GEHEIM_ZEILE#SAGANTA_BACKEND_SECRET=}"

umask 077

{
  echo "# Angelegt von infra/tagebuch-env-anlegen.sh, Geheimnisse UEBERNOMMEN,"
  echo "# nicht neu erzeugt. Siehe apps/tagebuch/README.md."
  echo "AUTH_SERVICE_URL=http://saganta-auth:3000"
  echo "AUTH_LOGIN_URL=https://saganta.de/login"
  echo "TAGEBUCH_API_BASE_URL=http://saganta-tagebuch-api:8000"
  echo "# Der Kalender liefert den Tageskontext und nimmt die drei Skalen"
  echo "# entgegen. Der Freitext geht diesen Weg nie."
  echo "KALENDER_BFF_BASE_URL=http://saganta-kalender-bff:8000"
  printf '%s\n' "$SUBS_ZEILE"
  printf '%s\n' "$GEHEIM_ZEILE"
  echo "HOST=0.0.0.0"
  echo "PORT=3000"
  echo "# Ohne diese beiden haelt adapter-node den eigenen Ursprung fuer http://"
  echo "# und lehnt jedes POST als Ursprungs-Konflikt ab."
  echo "PROTOCOL_HEADER=x-forwarded-proto"
  echo "HOST_HEADER=x-forwarded-host"
} > "$APP_ENV"

{
  echo "# Angelegt von infra/tagebuch-env-anlegen.sh."
  echo "# JWT_SECRET ist derselbe Wert wie SAGANTA_BACKEND_SECRET im BFF:"
  echo "# der stempelt, dieser Dienst prueft."
  echo "DATABASE_URL=sqlite:////data/tagebuch.db"
  printf '%s\n' "$JWT_ZEILE"
  echo "JWT_ALGORITHM=HS256"
  echo "CORS_ORIGINS=https://tagebuch.saganta.de,https://tagebuch.home.arpa"
  printf '%s\n' "$SUBS_ZEILE"
  echo "EINTRAG_MAX_CHIFFRAT_BYTES=1048576"
} > "$API_ENV"

chmod 600 "$APP_ENV" "$API_ENV"

echo "angelegt: apps/tagebuch/.env"
sed 's/=.*/=…/' "$APP_ENV" | grep -v '^#' | sed 's/^/    /'
echo "angelegt: services/tagebuch-api/.env"
sed 's/=.*/=…/' "$API_ENV" | grep -v '^#' | sed 's/^/    /'

# Gegenprobe, dass beide Seiten denselben Schluessel tragen, ohne ihn zu zeigen.
if [ "${GEHEIM_ZEILE#*=}" = "${JWT_ZEILE#*=}" ]; then
  echo "OK: BFF-Stempel und Backend-Pruefung tragen denselben Schluessel."
else
  fehler "Schluessel weichen ab, so wuerde jede Anfrage mit 401 enden."
fi

cat <<'HINWEIS'

Naechste Schritte:
  1) cd infra && docker compose -f docker-compose.yml \
       -f docker-compose.override.lan.yml up -d --build tagebuch tagebuch-api
  2) Gegenprobe, dass kein Klartext auf der Platte liegt:
       bash ../scripts/tagebuch-vertraulichkeit-pruefen.sh
  3) Beide .env in den SOPS-Vault legen (die Projektregeln, Abschnitt Secrets).
HINWEIS
