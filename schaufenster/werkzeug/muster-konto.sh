#!/usr/bin/env bash
# Ein Wegwerf-Konto "Familie Muster" fuer die Bilder auf saganta.de.
#
# WARUM ES DAS GIBT: Die Seite zeigt jede App mit einem Bild der echten
# Oberflaeche (Entscheid 2026-10-30). Echte Konten scheiden aus, die
# Inhalte sind privat. Eine zweite Instanz waere sauberer, haengt aber an sechs
# Diensten aus anderen Repos (docs/SELBSTHOSTEN_BEFUND.md). Also ein eigenes
# Konto im laufenden System, dessen Daten je Mandant getrennt liegen
# (docs/MANDANTEN_BEFUND.md, belegt je Dienst), und das danach vollstaendig
# wieder verschwindet.
#
# Die Registrierung ist zu (`disableSignUp`, seit 2026-09-05) und bleibt es.
# Das Konto entsteht direkt in der Auth-Datenbank, der Passwort-Hash aber von
# better-auth selbst (`better-auth/crypto` im laufenden Container). Ein selbst
# gebauter Hash saehe richtig aus und liesse sich nie anmelden.
#
# Das Passwort steht nur in $GEHEIM (Rechte 600) und nie in der Ausgabe.
#
# Loeschen faellt ausschliesslich auf DIESE Adresse. Die Kennung wird aus
# der Datenbank ueber die feste Adresse gelesen, nie von aussen angenommen:
# ein vertippter Sub in einem Loeschwerkzeug trifft im schlimmsten Fall den
# Owner, und an dessen Kalender haengt die Weckkette der Wohnung.
#
# Aufruf:
#   bash muster-konto.sh --status
#   bash muster-konto.sh --anlegen
#   bash muster-konto.sh --loeschen      # Daten in allen Diensten, dann Konto
set -euo pipefail

ADRESSE="familie.muster@example.org"
NAME="Familie Muster"
GEHEIM="${MUSTER_GEHEIM:-$HOME/.config/saganta-schaufenster/muster-passwort}"
WURZEL="$(cd "$(dirname "$0")/../.." && pwd)"

sql() {
  docker exec -i saganta-auth-db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -q' <<<"$1"
}

kennung() {
  sql "select id from \"user\" where email = '$ADRESSE';"
}

status() {
  local sub
  sub=$(kennung)
  if [[ -z $sub ]]; then
    echo "kein Muster-Konto vorhanden"
    return 0
  fi
  echo "Muster-Konto vorhanden: $sub"
  sql "select 'Sitzungen: ' || count(*) from session where \"userId\" = '$sub';"
  [[ -f $GEHEIM ]] && echo "Passwort-Datei: $GEHEIM" || echo "Passwort-Datei fehlt"
}

anlegen() {
  if [[ -n $(kennung) ]]; then
    echo "Muster-Konto existiert schon" >&2
    status
    return 0
  fi
  mkdir -p "$(dirname "$GEHEIM")"
  ( umask 077; python3 -c 'import secrets;print(secrets.token_urlsafe(24))' >"$GEHEIM" )
  local hash sub konto
  hash=$(docker exec -i saganta-auth node --input-type=module -e '
    import { hashPassword } from "better-auth/crypto";
    let pw = ""; for await (const c of process.stdin) pw += c;
    console.log(await hashPassword(pw.trim()));' <"$GEHEIM")
  [[ $hash == *:* ]] || { echo "FEHLER: kein Hash von better-auth" >&2; exit 1; }
  sub=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')
  konto=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')
  sql "begin;
insert into \"user\" (id, name, email, \"emailVerified\") values ('$sub', '$NAME', '$ADRESSE', true);
insert into account (id, \"accountId\", \"providerId\", \"userId\", password, \"updatedAt\")
  values ('$konto', '$sub', 'credential', '$sub', '$hash', now());
commit;"
  echo "angelegt: $sub ($ADRESSE)"
}

loeschen() {
  local sub
  sub=$(kennung)
  if [[ -z $sub ]]; then
    echo "kein Muster-Konto vorhanden, nichts zu tun"
    return 0
  fi
  echo "== Daten in den Diensten (konto-loeschen.py)"
  python3 "$WURZEL/scripts/konto-loeschen.py" --sub "$sub" --loeschen
  echo "== Kalender (eigener Loeschweg, siehe konto-loeschen.py Punkt 2)"
  docker exec -i -w /app kalender python - "$sub" <<'PY'
import sys
from backend.account import delete_account_data
from backend.database import SessionLocal
sub = sys.argv[1]
with SessionLocal() as db:
    print(delete_account_data(db, sub))
PY
  echo "== Anmeldung"
  sql "begin;
delete from session where \"userId\" = '$sub';
delete from account where \"userId\" = '$sub';
delete from \"user\" where id = '$sub' and email = '$ADRESSE';
commit;"
  rm -f "$GEHEIM"
  echo "geloescht: $sub"
}

case "${1:-}" in
  --status) status ;;
  --anlegen) anlegen ;;
  --loeschen) loeschen ;;
  *) sed -n '2,30p' "$0"; exit 2 ;;
esac
