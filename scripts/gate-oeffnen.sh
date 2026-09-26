#!/usr/bin/env bash
# Oeffnet oder schliesst das ALLOWED_SUBS-Gate eines Saganta-Dienstes.
#
# WOZU: 14 Stellen tragen eine Allowlist, die bis zum 2026-09-18 ueberall genau
# einen Eintrag hatte, den Owner-Sub. Ein zweites Konto war damit angemeldet und
# bekam trotzdem 403. Sie fallen einzeln, jede erst nachdem belegt ist, dass die
# Trennung ohne sie traegt (scripts/mandanten-pruefung.py + trennung-beweisen.sh).
#
# ★★ WARUM DIESES SKRIPT UND NICHT EIN sed VON HAND: der Name ALLOWED_SUBS
# bedeutet nicht ueberall dasselbe. In apps/post entscheidet er nicht, wer die
# App benutzen darf, sondern wer die Briefe des Owners sieht -- der Briefkasten
# ist single-tenant, dort gibt es kein per-Nutzer-Schema. Wer ihn dort "als
# naechstes Gate" leert, oeffnet einem Zweitkonto die Post, und zwar an einer
# Stelle, an der niemand danach sucht. Genau das waere am 2026-09-18 beinahe
# passiert. Die Bedeutung steht deshalb hier in der Tabelle, nicht in einem
# Kommentar, den man beim Tippen nicht liest: --oeffnen verweigert alles, was
# nicht `app` ist.
#
# ★ Jede Aenderung legt eine Sicherung an, und --schliessen spielt sie zurueck.
# Ein Gate ohne Rueckweg oeffnet man zoegerlicher als noetig oder mutiger als
# klug.
set -euo pipefail

WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENDUNG=".vor-gate"

# schluessel | datei (relativ zur saganta-Wurzel) | container | bedeutung
#
# bedeutung:
#   app      Wer darf die App ueberhaupt benutzen. Das ist das Gate, das faellt.
#   briefe   Wer sieht die single-tenant Briefkasten-Daten. Faellt erst, wenn
#            der briefkasten selbst nach owner_sub trennt.
#   rueckfall  Wirkt nur, solange BRIEFE_ALLOWED_SUBS fehlt (fail-closed).
ZIELE=(
  "mail-api|services/mail-api/.env|saganta-mail-api|app"
  "aufgaben|apps/aufgaben/.env|saganta-aufgaben|app"
  "fitness|apps/app-proxy/fitness.env|saganta-fitness|app"
  "lager|apps/app-proxy/lager.env|saganta-lager|app"
  "mealprep|apps/app-proxy/mealprep.env|saganta-mealprep|app"
  "kalender-bff|services/kalender-bff/.env|saganta-kalender-bff|app"
  "assets-api|services/assets-api/.env|saganta-assets-api|app"
  "news-api|services/news-api/.env|saganta-news-api|app"
  "notizen-api|services/notizen-api/.env|saganta-notizen-api|app"
  "projectdeck-api|services/projectdeck-api/.env|saganta-projectdeck-api|app"
  "tagebuch-api|services/tagebuch-api/.env|saganta-tagebuch-api|app"
  "tagebuch|apps/tagebuch/.env|saganta-tagebuch|app"
  "post|apps/post/.env|saganta-post|briefe"
  "notizen|apps/notizen/.env|saganta-notizen|rueckfall"
)

eintrag() {  # schluessel -> Zeile oder leer
  local s=$1 z
  for z in "${ZIELE[@]}"; do
    [[ ${z%%|*} == "$s" ]] && { echo "$z"; return 0; }
  done
  return 1
}

usage() {
  cat <<'EOF'
Aufrufe:
  bash scripts/gate-oeffnen.sh --status              Stand aller Gates (Datei und Container)
  bash scripts/gate-oeffnen.sh --oeffnen <dienst>    Allowlist leeren
  bash scripts/gate-oeffnen.sh --schliessen <dienst> Sicherung zurueckspielen

Vor dem Oeffnen:  python3 scripts/mandanten-pruefung.py <dienst>   muss 0 melden.
Nach dem Neustart: bash scripts/trennung-beweisen.sh <container> <aud> <pfad> '<json>'

Dienste: mail-api aufgaben fitness lager mealprep kalender-bff assets-api
         news-api notizen-api projectdeck-api tagebuch-api tagebuch post notizen
EOF
}

status() {
  printf '  %-17s %-10s %-9s %-9s %s\n' DIENST BEDEUTUNG DATEI CONTAINER SICHERUNG
  local z schluessel rel container bedeutung datei wert live sich
  for z in "${ZIELE[@]}"; do
    IFS='|' read -r schluessel rel container bedeutung <<<"$z"
    datei="$WURZEL/$rel"
    if [[ ! -f $datei ]]; then
      printf '  %-17s %-10s %-9s %-9s %s\n' "$schluessel" "$bedeutung" FEHLT - -
      continue
    fi
    wert=$(grep -m1 '^ALLOWED_SUBS=' "$datei" 2>/dev/null | cut -d= -f2- || true)
    [[ -n $wert ]] && wert=zu || wert=offen
    # ★ Die Datei ist nicht der Betrieb. Bis zum Neustart traegt der Container
    # noch den alten Wert, und genau dieser Unterschied erklaert ein 403, das
    # nach der Aenderung "eigentlich weg sein muesste".
    if live=$(docker exec "$container" printenv ALLOWED_SUBS 2>/dev/null); then
      [[ -n $live ]] && live=zu || live=offen
    elif docker ps -a --format '{{.Names}}' | grep -qx "$container"; then
      live="(ALLOWED_SUBS nicht gesetzt)"
      live=offen
    else
      live="-"
    fi
    sich=$([[ -f "$datei$ENDUNG" ]] && echo ja || echo -)
    printf '  %-17s %-10s %-9s %-9s %s\n' "$schluessel" "$bedeutung" "$wert" "$live" "$sich"
  done
  cat <<'EOF'

"zu" = Allowlist gesetzt, nur die gelisteten Subs kommen durch.
Weichen DATEI und CONTAINER ab, fehlt der Neustart -- es gilt der Container.
EOF
}

oeffnen() {
  local schluessel=${1:-} z rel container bedeutung datei
  z=$(eintrag "$schluessel") || { echo "FEHLER: Dienst '$schluessel' ist nicht bekannt." >&2; usage >&2; exit 1; }
  IFS='|' read -r _ rel container bedeutung <<<"$z"
  datei="$WURZEL/$rel"
  [[ -f $datei ]] || { echo "FEHLER: $rel existiert nicht." >&2; exit 1; }

  if [[ $bedeutung == briefe ]]; then
    cat >&2 <<EOF
ABGELEHNT: Bei '$schluessel' entscheidet ALLOWED_SUBS nicht ueber die App,
sondern darueber, wer die Briefe des Owners sieht. Der briefkasten ist
single-tenant: seine interne API liest mit einem statischen Token ueber alle
Nutzer hinweg. Diese Zeile zu leeren gibt jedem angemeldeten Konto die Post des
Owners.

Dieses Gate faellt erst, wenn der briefkasten selbst nach owner_sub trennt.
Siehe docs/MANDANTEN_BEFUND.md.
EOF
    exit 2
  fi
  if [[ $bedeutung == rueckfall ]]; then
    cat >&2 <<EOF
ABGELEHNT: Bei '$schluessel' ist ALLOWED_SUBS nur noch der fail-closed-Rueckfall
fuer BRIEFE_ALLOWED_SUBS (siehe src/lib/quellen.ts, darfBriefeSehen). Die App
selbst gatet hier nicht. Leeren wuerde nichts oeffnen, solange
BRIEFE_ALLOWED_SUBS steht -- und alles, sobald jemand die vergisst.
EOF
    exit 2
  fi

  if ! grep -q '^ALLOWED_SUBS=.' "$datei"; then
    echo "Nichts zu tun: '$schluessel' ist bereits offen."
    exit 0
  fi

  cp -p "$datei" "$datei$ENDUNG"
  sed -i 's|^ALLOWED_SUBS=.*|ALLOWED_SUBS=|' "$datei"
  echo "'$schluessel' geoeffnet. Sicherung: $rel$ENDUNG"
  echo
  cat <<EOF
Naechste Schritte:

  cd $WURZEL/infra && docker compose \\
    -f docker-compose.yml -f docker-compose.override.lan.yml \\
    up -d --force-recreate <compose-key>

Dann belegen (nicht behaupten), und erst danach als erledigt fuehren:

  bash $WURZEL/scripts/trennung-beweisen.sh $container <aud> <pfad> '<json>'

Zurueck geht es mit:  bash scripts/gate-oeffnen.sh --schliessen $schluessel
EOF
}

schliessen() {
  local schluessel=${1:-} z rel datei
  z=$(eintrag "$schluessel") || { echo "FEHLER: Dienst '$schluessel' ist nicht bekannt." >&2; exit 1; }
  IFS='|' read -r _ rel _ _ <<<"$z"
  datei="$WURZEL/$rel"
  [[ -f "$datei$ENDUNG" ]] || { echo "FEHLER: Keine Sicherung $rel$ENDUNG vorhanden." >&2; exit 1; }
  cp -p "$datei$ENDUNG" "$datei"
  echo "'$schluessel' aus der Sicherung zurueckgespielt. Container neu starten, sonst wirkt es nicht."
}

case "${1:-}" in
  --status) status ;;
  --oeffnen) oeffnen "${2:-}" ;;
  --schliessen) schliessen "${2:-}" ;;
  *) usage; exit 1 ;;
esac
