#!/usr/bin/env bash
# Traegt die Owner-Kennung dort ein, wo sie gebraucht wird.
#
# WOZU: Bis zum 2026-09-05 stand die better-auth-Kennung eines konkreten
# Menschen als Vorbelegung im Quelltext von lager, mealprep, fitness, kalender
# und der Shell. Sie gehoert nicht in ein Repo, das veroeffentlicht werden soll,
# und ein Selbsthoster hat ohnehin eine andere. Seither ist sie Konfiguration.
#
# ★ Die Kennung wird aus der Auth-Datenbank GELESEN, nicht getippt. Eine von
# Hand abgeschriebene Kennung ist der wahrscheinlichste Fehler an dieser Stelle,
# und er faellt nicht auf: der Dienst laeuft, zeigt nur keine Daten mehr.
#
# WAS OHNE DIESEN EINTRAG PASSIERT: lager, mealprep und fitness leiten den
# Mandanten beim Start aus ihren eigenen Daten ab, solange dort genau einer
# vorkommt (app/mandant_ableiten.py). Der Betrieb bricht also nicht. Aber die
# Ableitung ist eine Notmassnahme, kein Zustand: sie protokolliert bei jedem
# Start eine Warnung und versagt, sobald ein zweiter Mandant dazukommt.
#
# ⚠️ kalender ist seit dem 2026-09-06 dabei, mit zwei Eigenheiten. Erstens liegt
# sein Wert in `.env.tenant`, nicht in der `.env`: host-router bindet
# `../kalender/.env` komplett als env_file ein, alles darin landet also in einem
# fremden Prozess. Zweitens haengt dort die HA-Weckkette am headerlosen Pfad, der
# Neustart gehoert deshalb ins Deploy-Fenster 09:00-20:00 und braucht die
# Gegenprobe aus die Projektregeln (day-type/today und /tomorrow vorher und
# nachher vergleichen). Die anderen vier Ziele vertragen einen Neustart jederzeit.
set -euo pipefail

DOCKER=/home/user/docker
SCHLUESSEL=DEFAULT_OWNER_SUB

# Datei : Schluesselname in dieser Datei
ZIELE=(
  "$DOCKER/lager/.env|DEFAULT_OWNER_SUB"
  "$DOCKER/mealprep/.env|DEFAULT_OWNER_SUB"
  "$DOCKER/fitness/.env|DEFAULT_OWNER_SUB"
  "$DOCKER/kalender/.env.tenant|DEFAULT_OWNER_SUB"
  "$DOCKER/saganta/apps/shell/.env|OWNER_SUB"
)

usage() {
  cat <<'EOF'
Aufrufe:
  bash scripts/owner-kennung-eintragen.sh --konten     Konten aus der Auth-DB zeigen
  bash scripts/owner-kennung-eintragen.sh --setzen <mail>   Kennung dieses Kontos eintragen
  bash scripts/owner-kennung-eintragen.sh --status     Zeigen, wer die Kennung traegt
EOF
}

konten() {
  echo "Konten in der Saganta-Auth-Datenbank:"
  docker exec saganta-auth-db sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -F"  " \
      -c "select email, id from \"user\" order by \"createdAt\";"' | sed 's/^/  /'
  echo
  echo 'Dann: bash scripts/owner-kennung-eintragen.sh --setzen <mail>'
}

kennung_zu() {  # E-Mail -> better-auth user.id
  docker exec saganta-auth-db sh -lc \
    "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -t -A -c \"select id from \\\"user\\\" where email = '$1';\"" \
    | tr -d '\r\n'
}

status() {
  for z in "${ZIELE[@]}"; do
    IFS='|' read -r datei schluessel <<<"$z"
    kurz=${datei#"$DOCKER"/}
    if [[ ! -f $datei ]]; then
      printf '  %-42s %-18s FEHLT (Datei existiert nicht)\n' "$kurz" "$schluessel"
    elif grep -q "^${schluessel}=." "$datei" 2>/dev/null; then
      wert=$(grep "^${schluessel}=" "$datei" | head -1 | cut -d= -f2-)
      printf '  %-42s %-18s %s\n' "$kurz" "$schluessel" "${wert:0:12}..."
    else
      printf '  %-42s %-18s fehlt\n' "$kurz" "$schluessel"
    fi
  done
  echo
  echo "Die Kennung ist kein Geheimnis (sie steht in jedem JWT), deshalb wird sie"
  echo "hier gekuerzt angezeigt statt nur als Pruefsumme."
}

setzen() {
  local mail=${1:-}
  [[ -n $mail ]] || { echo "FEHLER: E-Mail fehlt. Erst --konten." >&2; exit 1; }

  local kennung
  kennung=$(kennung_zu "$mail")
  [[ -n $kennung ]] || { echo "FEHLER: Kein Konto mit der E-Mail '$mail'." >&2; exit 1; }
  echo "Konto '$mail' -> ${kennung:0:12}..."
  echo

  for z in "${ZIELE[@]}"; do
    IFS='|' read -r datei _ <<<"$z"
    [[ -f $datei ]] || { echo "FEHLER: $datei existiert nicht. Abgebrochen, nichts geaendert." >&2; exit 1; }
  done

  for z in "${ZIELE[@]}"; do
    IFS='|' read -r datei schluessel <<<"$z"
    cp -p "$datei" "$datei.vor-owner-kennung"
    # Vorhandene Zeile ersetzen statt anhaengen: zwei Zeilen mit demselben
    # Schluessel sind je nach Leser die erste oder die letzte, und welche gilt,
    # sieht man der Datei nicht an.
    if grep -q "^${schluessel}=" "$datei"; then
      sed -i "s|^${schluessel}=.*|${schluessel}=${kennung}|" "$datei"
    else
      [[ -s $datei && $(tail -c1 "$datei" | wc -l) -eq 0 ]] && printf '\n' >> "$datei"
      printf '%s=%s\n' "$schluessel" "$kennung" >> "$datei"
    fi
  done

  echo "Eingetragen (Sicherungen: *.vor-owner-kennung):"
  status
  cat <<'EOF'

Naechster Schritt:

  cd /home/user/docker/lager    && docker compose up -d --build
  cd /home/user/docker/mealprep && docker compose up -d --build
  cd /home/user/docker/fitness  && docker compose up -d --build

  # ⚠️ Nur zwischen 09:00 und 20:00, und day-type/today plus /tomorrow vorher
  # und nachher vergleichen. Daran haengt das 05:35-Weckfenster.
  cd /home/user/docker/kalender && docker compose up -d --build
  cd /home/user/docker/saganta/infra && docker compose \
    -f docker-compose.yml -f docker-compose.override.lan.yml \
    up -d --build --force-recreate saganta-shell

Danach darf in den Protokollen keine Ableitungs-Warnung mehr stehen:
  docker logs lager --since 5m 2>&1 | grep DEFAULT_OWNER_SUB
EOF
}

case "${1:-}" in
  --konten) konten ;;
  --setzen) setzen "${2:-}" ;;
  --status) status ;;
  *) usage; exit 1 ;;
esac
