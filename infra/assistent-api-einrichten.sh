#!/usr/bin/env bash
# assistent-api-einrichten.sh: richtet den Saganta Assistenten ein (KI-Chat
# Stufe 3, zuerst MealPrep), in einem Lauf und ohne ein Geheimnis auszugeben.
#
#   1. services/assistent-api/.env anlegen. `JWT_SECRET` ist KEIN neues
#      Geheimnis, sondern das `SAGANTA_BACKEND_SECRET` der BFFs: mit ihm prueft
#      der Dienst die Token der Apps und stempelt die kurzen Token fuer
#      MealPrep. Neu gewuerfelt antwortete er auf alles mit 401 (Bauart wie
#      kontakte-env-anlegen.sh).
#   2. Gateway-Key `saganta-assistent-api` ausstellen (llm-gateway/provision-keys.sh,
#      braucht dessen Master-Key wie jeder Aufruf dort).
#   3. Key mit key-einsetzen.py in die .env setzen, ohne ihn anzuzeigen, und
#      die .env in den SOPS-Vault legen.
#   4. Dienst starten und pruefen, dass er ein Modell hat.
#
# Bestehende .env bleibt unangetastet; ein zweiter Lauf ist harmlos.
set -euo pipefail

cd "$(dirname "$0")/.."
WURZEL="$(pwd)"
GATEWAY="$HOME/docker/llm-gateway"

ENV_DATEI="$WURZEL/services/assistent-api/.env"
QUELLE_SECRET="$WURZEL/apps/notizen/.env"    # SAGANTA_BACKEND_SECRET, ALLOWED_SUBS
VAULT_ZIEL="$WURZEL/infra/secrets/vault/assistent-api.env.enc"

fehler() { echo "FEHLER: $*" >&2; exit 1; }

[ -r "$QUELLE_SECRET" ] || fehler "Quelldatei nicht lesbar: $QUELLE_SECRET"

hol() {
  local schluessel="$1" datei="$2" zeile
  zeile="$(grep -m1 "^${schluessel}=" "$datei" || true)"
  [ -n "$zeile" ] || fehler "$schluessel fehlt in $datei"
  printf '%s\n' "$zeile"
}

echo "== 1/4 .env"
umask 077
if [ -e "$ENV_DATEI" ]; then
  echo "bleibt: services/assistent-api/.env (existiert bereits)"
else
  GEHEIM_ZEILE="$(hol SAGANTA_BACKEND_SECRET "$QUELLE_SECRET")"
  SUBS_ZEILE="$(hol ALLOWED_SUBS "$QUELLE_SECRET")"
  {
    echo "# Angelegt von infra/assistent-api-einrichten.sh, Geheimnis UEBERNOMMEN."
    printf 'JWT_SECRET=%s\n' "${GEHEIM_ZEILE#SAGANTA_BACKEND_SECRET=}"
    echo "JWT_ALGORITHM=HS256"
    printf '%s\n' "$SUBS_ZEILE"
    echo "LLM_GATEWAY_URL=http://192.0.2.10:8128"
    echo "LLM_MODEL=homelab-fast"
    echo "MEALPREP_URL=http://mealprep:8000"
  } > "$ENV_DATEI"
  chmod 600 "$ENV_DATEI"
  echo "angelegt: services/assistent-api/.env"
fi
sed 's/=.*/=…/' "$ENV_DATEI" | grep -v '^#' | sed 's/^/    /'

echo "== 2/4 Gateway-Key"
if grep -q '^LLM_GATEWAY_KEY=.' "$ENV_DATEI"; then
  echo "bleibt: LLM_GATEWAY_KEY ist schon gesetzt"
else
  (cd "$GATEWAY" && ./provision-keys.sh)
  echo "== 3/4 Key einsetzen"
  (cd "$GATEWAY" && python3 scripts/key-einsetzen.py saganta-assistent-api "$ENV_DATEI" \
      --sops-ziel "$VAULT_ZIEL" --aufraeumen)
fi

echo "== 4/4 Start"
cd "$WURZEL/infra"
docker compose -f docker-compose.yml -f docker-compose.override.lan.yml up -d --build --force-recreate assistent-api
for _ in $(seq 1 20); do
  stand="$(docker inspect --format '{{.State.Health.Status}}' saganta-assistent-api 2>/dev/null || true)"
  [ "$stand" = healthy ] && break
  sleep 3
done
[ "$stand" = healthy ] || fehler "saganta-assistent-api ist nicht healthy ($stand)"
docker exec saganta-assistent-api python -c \
  "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/healthz')); print('Modell konfiguriert:', d['modell']); raise SystemExit(0 if d['modell'] else 1)" \
  || fehler "Dienst laeuft, hat aber keinen Gateway-Key"
echo "== DNS"
# Idempotent: steht der Eintrag schon so drin, startet AdGuard nicht neu. Sonst
# kostet es ein kurzes Ausfallfenster des LAN-DNS (docker/adguard/rewrite-setzen.sh).
bash "$HOME/docker/adguard/rewrite-setzen.sh" --setzen assistent-api.home.arpa --antwort 192.0.2.10
echo "OK: Assistent laeuft. Die MealPrep-App fragt ihn ueber https://assistent-api.home.arpa/."
