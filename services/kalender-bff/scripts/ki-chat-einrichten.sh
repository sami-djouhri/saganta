#!/usr/bin/env bash
# KI-Chat Stufe 1 in einem Befehl: Gateway-Key einsetzen, kalender-bff neu
# erzeugen, Modelle messen. Der Key wird nirgends ausgegeben
# (llm-gateway/scripts/key-einsetzen.py).
#
#   bash ~/docker/saganta/services/kalender-bff/scripts/ki-chat-einrichten.sh
#   bash …/ki-chat-einrichten.sh --nur-messen    # Key steht schon, nur messen
#
# Plan und Vertrag: ../ASSISTENT_VERTRAG.md, interne Notiz.
set -euo pipefail
SAGANTA="$HOME/docker/saganta"
BFF="$SAGANTA/services/kalender-bff"

if [[ "${1:-}" != "--nur-messen" ]]; then
  echo "== 1/3 Key einsetzen"
  python3 "$HOME/docker/llm-gateway/scripts/key-einsetzen.py" saganta-kalender-bff "$BFF/.env" \
    --setze LLM_GATEWAY_URL=http://192.0.2.10:8128 \
    --setze LLM_MODEL=homelab-smart \
    --sops-ziel "$SAGANTA/infra/secrets/vault/kalender-bff.env.enc" \
    --aufraeumen

  echo "== 2/3 kalender-bff neu erzeugen"
  # --force-recreate, sonst bleibt der Container mit der alten Umgebung stehen.
  (cd "$SAGANTA/infra" && docker compose -f docker-compose.yml -f docker-compose.override.lan.yml \
    up -d --force-recreate kalender-bff)
  for _ in $(seq 1 30); do
    [[ "$(docker inspect --format '{{.State.Health.Status}}' saganta-kalender-bff 2>/dev/null)" == healthy ]] && break
    sleep 2
  done
  echo "   Zustand: $(docker inspect --format '{{.State.Health.Status}}' saganta-kalender-bff)"
fi

echo "== 3/3 Modelle messen"
docker exec -i saganta-kalender-bff python - < "$BFF/scripts/assistent-messen.py"
