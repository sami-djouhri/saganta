#!/usr/bin/env bash
# notizen-env-anlegen.sh: legt die beiden .env-Dateien der Notizen-App an.
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
# Danach:
#   cd infra && docker compose -f docker-compose.yml \
#     -f docker-compose.override.lan.yml up -d --build notizen notizen-api
#
# Und einmalig in den SOPS-Vault legen (siehe die Projektregeln, Abschnitt Secrets).

set -euo pipefail

cd "$(dirname "$0")/.."
WURZEL="$(pwd)"

APP_ENV="$WURZEL/apps/notizen/.env"
API_ENV="$WURZEL/services/notizen-api/.env"
QUELLE_APP="$WURZEL/apps/post/.env"              # BRIEFKASTEN_*, ALLOWED_SUBS
QUELLE_SECRET="$WURZEL/apps/projectdeck/.env"    # SAGANTA_BACKEND_SECRET

fehler() { echo "FEHLER: $*" >&2; exit 1; }

for datei in "$QUELLE_APP" "$QUELLE_SECRET"; do
  [ -r "$datei" ] || fehler "Quelldatei nicht lesbar: $datei"
done

# Nichts ueberschreiben. Eine bestehende .env ist der Live-Zustand; sie hier
# stillschweigend zu ersetzen waere genau der Vorfall, den die Deploy-Regeln
# dieses Projekts verhindern sollen.
for datei in "$APP_ENV" "$API_ENV"; do
  [ -e "$datei" ] && fehler "$datei existiert bereits: nichts angefasst."
done

# Wert holen, ohne ihn anzuzeigen.
hol() {
  local schluessel="$1" datei="$2" zeile
  zeile="$(grep -m1 "^${schluessel}=" "$datei" || true)"
  [ -n "$zeile" ] || fehler "$schluessel fehlt in $datei"
  printf '%s\n' "$zeile"
}

GEHEIM_ZEILE="$(hol SAGANTA_BACKEND_SECRET "$QUELLE_SECRET")"
BRIEF_ZEILE="$(hol BRIEFKASTEN_INTERNAL_TOKEN "$QUELLE_APP")"
SUBS_ZEILE="$(hol ALLOWED_SUBS "$QUELLE_APP")"

# Für das Backend heisst derselbe Wert JWT_SECRET.
JWT_ZEILE="JWT_SECRET=${GEHEIM_ZEILE#SAGANTA_BACKEND_SECRET=}"

umask 077

{
  echo "# Angelegt von infra/notizen-env-anlegen.sh: Geheimnisse UEBERNOMMEN,"
  echo "# nicht neu erzeugt. Siehe apps/notizen/README.md."
  echo "AUTH_SERVICE_URL=http://saganta-auth:3000"
  echo "AUTH_LOGIN_URL=https://saganta.de/login"
  echo "NOTIZEN_API_BASE_URL=http://saganta-notizen-api:8000"
  echo "KALENDER_BFF_BASE_URL=http://saganta-kalender-bff:8000"
  echo "PROJECTDECK_API_BASE_URL=http://saganta-projectdeck-api:8000"
  echo "BRIEFKASTEN_BASE_URL=http://briefkasten:8000"
  printf '%s\n' "$BRIEF_ZEILE"
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
  echo "# Angelegt von infra/notizen-env-anlegen.sh."
  echo "# JWT_SECRET ist derselbe Wert wie SAGANTA_BACKEND_SECRET im BFF:"
  echo "# der stempelt, dieser Dienst prueft."
  echo "DATABASE_URL=sqlite:////data/notizen.db"
  echo "ANHANG_VERZEICHNIS=/data/anhaenge"
  printf '%s\n' "$JWT_ZEILE"
  echo "JWT_ALGORITHM=HS256"
  # Nur Adressen, hinter denen ein Vhost dieser Installation steht. Eine
  # Kurz-Domaene (PUBLIC_NOTIZEN_KURZ_BASIS, siehe unten) traegt hier nach, wer
  # eine betreibt: als Vorbelegung waere sie in jeder anderen Installation ein
  # erlaubter Ursprung, den es dort nicht gibt.
  echo "CORS_ORIGINS=https://notizen.saganta.de,https://notizen.home.arpa"
  printf '%s\n' "$SUBS_ZEILE"
  echo "ANHANG_MAX_BYTES=20971520"
  echo "ANHANG_QUOTE_BYTES=524288000"
  echo "FREIGABE_MAX_TAGE=365"
} > "$API_ENV"

chmod 600 "$APP_ENV" "$API_ENV"

echo "angelegt: apps/notizen/.env"
sed 's/=.*/=…/' "$APP_ENV" | grep -v '^#' | sed 's/^/    /'
echo "angelegt: services/notizen-api/.env"
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
       -f docker-compose.override.lan.yml up -d --build notizen notizen-api
  2) Rauchtest, falls vorhanden:  bash ../scripts/notizen-rauchtest.sh
     (legt eine Notiz an, teilt sie einmalig, prueft den zweiten Versuch und
     raeumt auf. Er misst gegen die Vhosts dieser einen Installation und geht
     deshalb nicht mit der Veroeffentlichung.)
  3) Beide .env in den SOPS-Vault legen (die Projektregeln, Abschnitt Secrets).

Optional, wer eine Kurz-Domaene fuer geteilte Notizen betreibt:

  echo 'PUBLIC_NOTIZEN_KURZ_BASIS=https://n.saganta.de' >> apps/notizen/.env

Ohne diese Zeile zeigen geteilte Links auf den eigenen Ursprung plus /n, was
diese App selbst bedient. Sie steht mit Absicht NICHT in der angelegten Datei:
sie setzt einen zusaetzlichen Vhost voraus, und eine Installation, die ihn
nicht hat, bekaeme sonst Links, die niemand aufrufen kann.
HINWEIS
