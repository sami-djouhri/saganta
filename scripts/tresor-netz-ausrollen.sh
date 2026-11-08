#!/usr/bin/env bash
# Netztrennung Stufe 1 ausrollen: saganta-auth-db nur noch in saganta-tresor-net.
#
# WOZU: Die Benutzerdatenbank (Passwort-Hashes aller Konten) hing bis 2026-11-07
# in cc-core, neben mosquitto, host-junior, brain-bus und rund 35 weiteren
# Containern. Gerufen wird sie von genau einem Dienst, saganta-auth. Entschieden
# am 2026-10-10, Messung in docs/CC_CORE_AUSZUG_MESSUNG_2026-10-09.md.
#
# ✅ Ausgerollt am 2026-11-07. Seither ist `--pruefen` der Gebrauch: misst nur
# den Nachher-Stand (Netze, Erreichbarkeit, Sperre, Route, Protokoll) und
# aendert nichts. Exit 1, wenn die Trennung nicht mehr steht.
#
# WAS ES OHNE SCHALTER TUT: misst vorher, erstellt die zwei Container neu (gleiche Images,
# kein Build, keine Nachbarn), wartet auf healthy, misst nachher und sagt, ob
# die Trennung steht. Die eigentliche Anmeldeprobe ist danach ein Login an
# https://shell.home.arpa, von Hand.
#
# ⚠️ Faellt saganta-auth aus, kann sich an KEINER Saganta-App jemand anmelden.
# Deshalb im Tagesfenster, und der Rueckweg steht bereit:
#   bash scripts/tresor-netz-ausrollen.sh --zurueck
# haengt die Datenbank sofort wieder in cc-core (ohne Neustart). Das meldet
# der docker-network-watcher als VIOLATION: die Zeile
# `host:saganta-auth-db:cc-core` ist seit dem Ausrollen aus seiner
# whitelist.txt entfernt, damit ein Wiedereinhaengen nicht still bleibt. Danach in
# infra/docker-compose.yml die zwei networks-Zeilen zuruecknehmen, sonst holt
# das naechste `up` die Trennung wieder.
set -uo pipefail

cd "$(dirname "$0")/../infra" || exit 1

if [ "${1:-}" = "--zurueck" ]; then
  docker network connect cc-core saganta-auth-db && echo "saganta-auth-db haengt wieder in cc-core."
  exit $?
fi

fehler=0
ok()   { echo "  ok    $*"; }
nein() { echo "  FEHLER $*"; fehler=1; }

# Vom Frontend aus, wie im Betrieb: die Shell ruft auth per Container-Name in
# cc-core. Bewusst die Shell: alle anderen Oberflaechen laufen auf Abruf ueber
# den wake-gateway und stehen meist auf "Created" oder "Exited" (die erste
# Fassung probte am Kalender und brach deshalb schon beim Vorher ab).
app_zu_auth() {
  docker exec saganta-shell node -e 'fetch("http://saganta-auth:3000/healthz").then(r=>console.log(r.status)).catch(e=>console.log(e.cause?.code||e.message))' 2>&1
}
# TCP-Verbindung zu 5432 aus einem Container; Ausgabe "offen" oder der Fehlercode.
tcp_zur_db() {
  docker exec "$1" node -e 'const s=require("net").connect(5432,"saganta-auth-db",()=>{console.log("offen");s.end()});s.on("error",e=>console.log(e.code));setTimeout(()=>{console.log("TIMEOUT");process.exit()},4000).unref()' 2>&1
}

if [ "${1:-}" != "--pruefen" ]; then
echo "== Vorher"
[ "$(app_zu_auth)" = "200" ] && ok "App -> auth /healthz 200" || nein "App -> auth: $(app_zu_auth)"
[ "$(tcp_zur_db saganta-auth)" = "offen" ] && ok "auth -> auth-db:5432" || nein "auth -> auth-db: $(tcp_zur_db saganta-auth)"
if [ "$fehler" -ne 0 ]; then
  echo "Schon vorher nicht in Ordnung, ich aendere nichts."; exit 1
fi
docker compose config 2>/dev/null | grep -q "name: saganta-tresor-net" \
  || { echo "infra/docker-compose.yml kennt saganta-tresor-net nicht (git pull?)."; exit 1; }

echo "== Neu erstellen (nur saganta-auth-db und saganta-auth)"
docker compose up -d --no-deps --no-build saganta-auth-db saganta-auth || exit 1

echo "== Warten auf healthy"
for c in saganta-auth-db saganta-auth; do
  for _ in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null)" = "healthy" ] && break
    sleep 3
  done
  s=$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null)
  [ "$s" = "healthy" ] && ok "$c healthy" || nein "$c ist $s"
done

fi

echo "== Nachher"
netze=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' saganta-auth-db)
[ "$netze" = "saganta-tresor-net " ] && ok "auth-db nur in saganta-tresor-net" || nein "auth-db haengt in: $netze"
[ "$(app_zu_auth)" = "200" ] && ok "App -> auth /healthz 200" || nein "App -> auth: $(app_zu_auth)"
[ "$(tcp_zur_db saganta-auth)" = "offen" ] && ok "auth -> auth-db:5432" || nein "auth -> auth-db: $(tcp_zur_db saganta-auth)"
r=$(tcp_zur_db saganta-shell)
[ "$r" != "offen" ] && ok "App -> auth-db gesperrt ($r)" || nein "App erreicht auth-db noch"
docker exec saganta-auth-db ip route 2>/dev/null | grep -q '^default' \
  && nein "auth-db hat eine Vorgabe-Route nach draussen" || ok "auth-db ohne Vorgabe-Route"
if docker logs --since 2m saganta-auth 2>&1 | grep -qiE 'ECONNREFUSED|ENOTFOUND|EAI_AGAIN|connect.*timeout'; then
  nein "Verbindungsfehler im Protokoll von saganta-auth (docker logs --since 2m saganta-auth)"
else
  ok "keine Verbindungsfehler im Protokoll von saganta-auth"
fi

echo
if [ "$fehler" -eq 0 ]; then
  echo "Trennung steht. Jetzt an https://shell.home.arpa anmelden (Anmeldeprobe)."
  echo "Geht das nicht: bash scripts/tresor-netz-ausrollen.sh --zurueck"
else
  echo "Nicht in Ordnung. Rueckweg: bash scripts/tresor-netz-ausrollen.sh --zurueck"
  exit 1
fi
