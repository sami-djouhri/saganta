#!/usr/bin/env bash
# Rollt die Mandanten-Geheimnisse fuer lager, mealprep und fitness aus.
#
# WOZU: Die drei nativen Dienste uebernahmen den `X-Saganta-Sub`-Header bis zum
# 2026-09-05 ungeprueft (Audit-Befund FCS-01). Die Mandantentrennung hing daran,
# dass nur der app-proxy sie erreicht. Wer :8095/:8096/:8094 direkt anspricht,
# konnte sich als beliebiger Mandant ausgeben, und das ORM-Scoping glaubt ihm.
# Mit einem Geheimnis schickt jeder Absender zusaetzlich `X-Saganta-Sub-Sig`,
# gebunden an genau seinen `sub`.
#
# ★ DREI GEHEIMNISSE, NICHT EINES. Anders als beim Kalender bekommt jeder
# Dienst sein eigenes: wer das Lager lesen darf, soll damit nicht automatisch
# Mahlzeiten und Training lesen duerfen. Der Preis ist, dass mealprep das
# Geheimnis des Lagers kennen muss, weil es dorthin spricht. Signaturen gelten
# immer fuer den Empfaenger.
#
# ★★ DER SCHLUESSELNAME UNTERSCHEIDET SICH JE SEITE. Der Empfaenger liest
# `<DIENST>_TENANT_SECRET`, der app-proxy liest schlicht `TENANT_SECRET` (er
# laeuft dreimal mit je eigener .env). Ein Skript, das ueberall denselben Namen
# schreibt, waere hier still wirkungslos: der Wert stuende da, gelesen wuerde er
# nie.
#
# WARUM EIN SKRIPT UND NICHT VON HAND: sieben .env-Eintraege in sechs Dateien
# muessen paarweise zusammenpassen. Ein Tippfehler sperrt genau einen Weg aus,
# und zwar erst beim Scharfschalten, also zeitversetzt zur Ursache.
#
# REIHENFOLGE (das Skript erzwingt sie):
#   1. Dieses Skript setzt die Geheimnisse, ENFORCE bleibt 0.
#   2. Die betroffenen Dienste neu bauen. Absender signieren, Pruefer beobachten.
#   3. Beobachten (--pruefen). Wer meldet sich unsigniert? Das sind Absender,
#      die noch fehlen.
#   4. Erst wenn ueber Tage nichts Unsigniertes mehr kommt: ENFORCE=1.
#
# Ohne Geheimnis verhaelt sich alles exakt wie vorher. Schritt 1 und 2 sind fuer
# sich verhaltensneutral und jederzeit gefahrlos.
#
# ⚠️ Headerlose Aufrufer (life-ops /api/critical, assets-api) sind in ALLEN
# Zustaenden unberuehrt. Sie laufen weiter auf DEFAULT_OWNER_SUB.
set -euo pipefail

DOCKER=/home/user/docker
PROXY="$DOCKER/saganta/apps/app-proxy"

# Je Zeile: <Geheimnis-Gruppe>|<Datei>|<Schluesselname in dieser Datei>|<Rolle>
PAARE=(
  "lager|$DOCKER/lager/.env|LAGER_TENANT_SECRET|Pruefer"
  "lager|$PROXY/lager.env|TENANT_SECRET|Absender app-proxy"
  "lager|$DOCKER/mealprep/.env|LAGER_TENANT_SECRET|Absender mealprep->lager"
  "mealprep|$DOCKER/mealprep/.env|MEALPREP_TENANT_SECRET|Pruefer"
  "mealprep|$PROXY/mealprep.env|TENANT_SECRET|Absender app-proxy"
  "fitness|$DOCKER/fitness/.env|FITNESS_TENANT_SECRET|Pruefer"
  "fitness|$PROXY/fitness.env|TENANT_SECRET|Absender app-proxy"
)
GRUPPEN=(lager mealprep fitness)

usage() {
  cat <<'EOF'
Aufrufe:
  bash scripts/tenant-geheimnisse-tracking-apps.sh --setzen   Drei Geheimnisse erzeugen und eintragen
  bash scripts/tenant-geheimnisse-tracking-apps.sh --status   Zeigen, wer welchen Fingerabdruck traegt
  bash scripts/tenant-geheimnisse-tracking-apps.sh --pruefen   Beobachtungsphase auswerten
EOF
}

fingerabdruck() {  # Datei, Schluessel. Nie den Wert selbst zeigen.
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sha256sum | cut -c1-12
}

status() {
  for g in "${GRUPPEN[@]}"; do
    echo "Gruppe $g:"
    for p in "${PAARE[@]}"; do
      IFS='|' read -r gruppe datei schluessel rolle <<<"$p"
      [[ $gruppe == "$g" ]] || continue
      kurz=${datei#"$DOCKER"/}
      if [[ ! -f $datei ]]; then
        printf '  %-46s %-22s FEHLT (Datei existiert nicht)\n' "$kurz" "$rolle"
      elif grep -q "^${schluessel}=." "$datei" 2>/dev/null; then
        printf '  %-46s %-22s gesetzt (%s)\n' "$kurz" "$rolle" "$(fingerabdruck "$datei" "$schluessel")"
      else
        printf '  %-46s %-22s fehlt\n' "$kurz" "$rolle"
      fi
    done
    echo
  done
  echo "Gleicher Fingerabdruck INNERHALB einer Gruppe = gleiches Geheimnis."
  echo "Weicht einer ab, bekommt genau dieser Weg beim Scharfschalten 401."
  echo "Zwischen den Gruppen MUESSEN sie sich unterscheiden, das ist der Zweck."
}

setzen() {
  for p in "${PAARE[@]}"; do
    IFS='|' read -r _ datei _ _ <<<"$p"
    [[ -f $datei ]] || { echo "FEHLER: $datei existiert nicht. Abgebrochen, nichts geaendert." >&2; exit 1; }
  done

  for p in "${PAARE[@]}"; do
    IFS='|' read -r _ datei schluessel _ <<<"$p"
    if grep -q "^${schluessel}=." "$datei" 2>/dev/null; then
      echo "$schluessel ist in ${datei#"$DOCKER"/} bereits gesetzt."
      echo
      echo "Erneutes Setzen vergibt NEUE Werte und sperrt die bereits"
      echo "umgestellten Wege aus. Bei Absicht (Rotation): erst ueberall"
      echo "TENANT_HEADER_ENFORCE=0, dann die Zeilen von Hand entfernen."
      exit 1
    fi
  done

  declare -A GEHEIM
  for g in "${GRUPPEN[@]}"; do
    GEHEIM[$g]=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
  done

  for p in "${PAARE[@]}"; do
    IFS='|' read -r gruppe datei schluessel _ <<<"$p"
    cp -p "$datei" "$datei.vor-tenant-geheimnis"
    [[ -s $datei && $(tail -c1 "$datei" | wc -l) -eq 0 ]] && printf '\n' >> "$datei"
    printf '%s=%s\n' "$schluessel" "${GEHEIM[$gruppe]}" >> "$datei"
  done
  unset GEHEIM

  echo "Drei Geheimnisse in ${#PAARE[@]} Eintraege geschrieben (Sicherungen: *.vor-tenant-geheimnis)."
  echo
  status
  cat <<'EOF'

Naechster Schritt, verhaltensneutral (ENFORCE steht ueberall auf 0):

  cd /home/user/docker/lager    && docker compose up -d --build
  cd /home/user/docker/mealprep && docker compose up -d --build
  cd /home/user/docker/fitness  && docker compose up -d --build
  cd /home/user/docker/saganta/infra && docker compose \
    -f docker-compose.yml -f docker-compose.override.lan.yml \
    up -d --build --force-recreate saganta-lager saganta-mealprep saganta-fitness

  (--force-recreate ist Pflicht: COPY-Images. Ohne das meldet compose
   "Running" und der alte Code bleibt live.)

Danach mindestens einen Tag beobachten, dann --pruefen.
EOF
}

pruefen() {
  echo "Unsignierte Mandanten-Header der letzten 24 h (Beobachtungsphase):"
  echo
  local gesamt=0
  for c in lager mealprep fitness; do
    n=$(docker logs "$c" --since 24h 2>&1 | grep -c "Mandanten-Header .* akzeptiert" || true)
    printf '  %-10s %s Meldung(en)\n' "$c" "$n"
    gesamt=$((gesamt + n))
    [[ $n -gt 0 ]] && docker logs "$c" --since 24h 2>&1 | grep "Mandanten-Header .* akzeptiert" | tail -3 | sed 's/^/      /'
  done
  echo
  if [[ $gesamt -eq 0 ]]; then
    cat <<'EOF'
Nichts Unsigniertes. ⚠️ Das allein ist noch kein Beweis: es heisst auch dann
null, wenn die Dienste gar nicht benutzt wurden oder das Geheimnis nirgends
gesetzt ist. Vor dem Scharfschalten pruefen, dass --status ueberall einen
Fingerabdruck zeigt UND die Apps in der Zeit wirklich benutzt wurden.

Scharfschalten heisst dann: TENANT_HEADER_ENFORCE=1 in die drei .env der
Pruefer (lager, mealprep, fitness), danach neu bauen.
EOF
  else
    echo "Es kommt noch Unsigniertes. Diese Absender fehlen noch, NICHT scharf schalten."
  fi
}

case "${1:-}" in
  --setzen) setzen ;;
  --status) status ;;
  --pruefen) pruefen ;;
  *) usage; exit 1 ;;
esac
