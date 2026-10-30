#!/usr/bin/env bash
# Laesst die Tests eines Dienstes im GEBAUTEN Image laufen.
#
# **Der Befund, der dieses Skript ausgeloest hat** (2026-10-16): 32
# Python-Testdateien mit 356 Testfunktionen, dazu 13 TS-Testdateien, und keine
# Moeglichkeit, sie auszufuehren. Weder `.github` noch `.gitea`-Workflow, pytest
# nicht auf dem Wirt und nicht in den Images. Die `die Projektregeln` stuetzt
# sich an mehreren Stellen auf Tests als Riegel ("wird
# `tests/test_konto_loeschplan.py` rot"), und dieser Riegel war nicht
# nachpruefbar. Ein Riegel, den niemand zuziehen kann, ist eine Behauptung.
#
# Lauffaehig sind sie trotzdem, es brauchte nur drei Handgriffe, die man jedes
# Mal neu herausfinden musste. Genau die stehen hier:
#
#  1. **Als root laufen.** Der Quellbaum traegt eine ACL, die neuen Dateien 660
#     gibt; die Images laufen als `appuser` (uid 10001) und koennen das
#     eingehaengte `tests/` nicht lesen. Der Fehler dabei lautet "Start
#     directory is not importable" und sieht wie ein Paketproblem aus, nicht
#     wie ein Rechteproblem.
#  2. **pytest und httpx nachinstallieren.** Beide stehen im `dev`-Extra des
#     pyproject, aber die Images installieren nur `.` ohne Extra -- richtig fuer
#     ein Laufzeit-Image. `httpx` ist dabei nicht optional: ohne es verweigert
#     `fastapi.testclient` den Import, und zwar mit einer Meldung ueber
#     starlette, die den Blick in die falsche Richtung lenkt.
#  3. **`ALLOW_INSECURE_SECRETS=1` und ein JWT_SECRET setzen.** Die `config.py`
#     bricht beim Import gegen Vorgabe-Geheimnisse ab (Fail-Fast, 2026-06-28).
#     Ohne diese beiden scheitert schon das Einlesen des Moduls.
#
# ⚠️ Es wird das **Image** getestet, also der Code, der auch laeuft, mit dem
# `tests/`-Verzeichnis frisch vom Wirt eingehaengt. Das ist Absicht: so prueft
# ein Lauf nach einem Build genau das, was ausgerollt wurde. Wer eine Aenderung
# an `app/` testen will, baut vorher neu.
#
#   bash scripts/tests-im-image.sh                 # alle Dienste mit tests/
#   bash scripts/tests-im-image.sh projectdeck-api # nur dieser
#   bash scripts/tests-im-image.sh --bauen         # vorher jeden neu bauen
set -uo pipefail

WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(-f "$WURZEL/infra/docker-compose.yml" -f "$WURZEL/infra/docker-compose.override.lan.yml")

BAUEN=0
ZIELE=()
for arg in "$@"; do
  case "$arg" in
    --bauen) BAUEN=1 ;;
    -h|--help) sed -n '2,40p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) ZIELE+=("$arg") ;;
  esac
done

# Ohne Angabe: jeder Dienst, der ein tests/ hat.
if [ ${#ZIELE[@]} -eq 0 ]; then
  for d in "$WURZEL"/services/*/; do
    name="$(basename "$d")"
    [ "$name" = "_geteilt" ] && continue
    [ -d "$d/tests" ] && ZIELE+=("$name")
  done
fi

# Der Image-Name haengt am Compose-Projektnamen und am Service-Key, und die
# weichen voneinander ab (shell-api heisst als Service `saganta-shell-api` und
# als Image `saganta-saganta-shell-api`). Statt das zu raten, wird der
# laufende Container gefragt; nur wenn es keinen gibt, wird geraten.
image_fuer() {
  local dienst="$1" ermittelt
  ermittelt="$(docker inspect "saganta-$dienst" --format '{{.Config.Image}}' 2>/dev/null)"
  if [ -n "$ermittelt" ]; then echo "$ermittelt"; return; fi
  echo "saganta-$dienst"
}

GESAMT_FEHLER=0
BERICHT=()
for dienst in "${ZIELE[@]}"; do
  pfad="$WURZEL/services/$dienst"
  if [ ! -d "$pfad/tests" ]; then
    echo "== $dienst: kein tests/, uebersprungen"
    BERICHT+=("$dienst  --  kein tests/")
    continue
  fi

  if [ "$BAUEN" = 1 ]; then
    echo "== $dienst: baue"
    # Der Compose-Service-Key ist nicht immer der Verzeichnisname.
    schluessel="$(docker inspect "saganta-$dienst" \
      --format '{{index .Config.Labels "com.docker.compose.service"}}' 2>/dev/null)"
    docker compose "${COMPOSE[@]}" build "${schluessel:-$dienst}" >/dev/null 2>&1 \
      || { echo "   Bau fehlgeschlagen"; BERICHT+=("$dienst  --  Bau fehlgeschlagen"); GESAMT_FEHLER=1; continue; }
  fi

  image="$(image_fuer "$dienst")"
  echo "== $dienst  (Image $image)"
  ausgabe="$(docker run --rm --user root \
    -v "$pfad/tests:/app/tests:ro" -w /app \
    -e ALLOW_INSECURE_SECRETS=1 \
    -e JWT_SECRET=test-geheimnis-nur-fuer-den-testlauf \
    --entrypoint sh "$image" -c \
    'pip install -q pytest httpx >/dev/null 2>&1; python -m pytest tests/ -q 2>&1' 2>&1)"
  rc=$?
  letzte="$(printf '%s\n' "$ausgabe" | grep -E '^[0-9]+ (passed|failed)|passed|failed|error' | tail -1)"
  if [ "$rc" -ne 0 ]; then
    GESAMT_FEHLER=1
    printf '%s\n' "$ausgabe" | tail -25 | sed 's/^/   /'
    BERICHT+=("$dienst  ROT  ${letzte:-kein Ergebnis}")
  else
    echo "   ${letzte:-ok}"
    BERICHT+=("$dienst  gruen  ${letzte:-ok}")
  fi
done

echo
echo "Zusammenfassung:"
for z in "${BERICHT[@]}"; do echo "  $z"; done
if [ "$GESAMT_FEHLER" -ne 0 ]; then
  echo
  echo "Mindestens ein Dienst ist rot. Die Antwort darauf ist nie 'Test anpassen',"
  echo "sondern ein Schritt im Code oder eine ausdrueckliche Begruendung."
fi
exit "$GESAMT_FEHLER"
