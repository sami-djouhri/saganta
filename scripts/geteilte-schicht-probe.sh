#!/usr/bin/env bash
# Prueft, ob die geteilte Schicht (services/_geteilt) in den LAUFENDEN Diensten
# ankommt, und zwar in drei Stufen: vorhanden, aktuell, wirksam.
#
# WARUM DREI STUFEN: Der Vorgaenger dieses Skripts (zugriffslog-abgleich.sh)
# verglich die Quellbaeume miteinander und meldete acht Mal "gleich". Das war
# richtig und trotzdem wertlos. Am 30.08.2026 lag der Health-Filter seit drei
# Tagen in allen acht Baeumen und wirkte in genau einem Dienst, weil nur der
# seither neu gebaut worden war. Der Abgleich hatte die Frage gar nicht gestellt,
# auf die es ankam: nicht "steht es im Baum", sondern "hat es der laufende
# Prozess".
#
# Stufe 1 vorhanden: ist saganta_dienst im Container installiert.
# Stufe 2 aktuell:   stimmen die installierten Module mit dem Quellbaum ueberein
#                    (ein Dienst, der seit der letzten Aenderung nicht neu gebaut
#                    wurde, faellt genau hier auf).
# Stufe 3 wirksam:   schreibt der Dienst noch erfolgreiche Health-Abrufe ins
#                    Zugriffsprotokoll. Das ist die Wirkung, nicht die Absicht.
#
# Rueckgabe: 0 = alles sauber, 1 = veraltet/unwirksam, 2 = fehlt ganz.
set -uo pipefail
cd "$(dirname "$0")/.."

QUELLE="services/_geteilt/saganta_dienst"
declare -A CONTAINER=(
  [shell-api]=saganta-shell-api
  [news-api]=saganta-news-api
  [notizen-api]=saganta-notizen-api
  [projectdeck-api]=saganta-projectdeck-api
  [assets-api]=saganta-assets-api
  [mail-api]=saganta-mail-api
  [kalender-bff]=saganta-kalender-bff
  [auth-proxy]=saganta-auth-proxy
)

if [[ ! -d "$QUELLE" ]]; then
  echo "FEHLER: Quelle $QUELLE fehlt."
  exit 2
fi

# Erwartete Pruefsumme: alle Modul-Dateien der Quelle, sortiert, als eine Summe.
erwartet="$(find "$QUELLE" -name '*.py' -type f -printf '%f\n' -exec cat {} + \
            | md5sum | cut -c1-12)"
echo "Quellstand $QUELLE: $erwartet"
echo

fehlt=0
veraltet=0
unwirksam=0

for d in $(printf '%s\n' "${!CONTAINER[@]}" | sort); do
  c="${CONTAINER[$d]}"
  printf '%-17s ' "$d"

  if ! docker inspect "$c" >/dev/null 2>&1; then
    echo "Container $c gibt es nicht"
    fehlt=1; continue
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$c")" != "true" ]]; then
    echo "Container laeuft nicht"
    fehlt=1; continue
  fi

  # Stufe 1+2 in einem Griff: im laufenden Container dieselbe Summe bilden.
  ist="$(docker exec "$c" sh -c '
    p=$(python -c "import saganta_dienst,os;print(os.path.dirname(saganta_dienst.__file__))" 2>/dev/null) || exit 3
    find "$p" -name "*.py" -type f -printf "%f\n" -exec cat {} + | md5sum | cut -c1-12
  ' 2>/dev/null)"
  rc=$?

  if [[ $rc -ne 0 || -z "$ist" ]]; then
    echo "saganta_dienst NICHT INSTALLIERT"
    fehlt=1; continue
  fi
  if [[ "$ist" != "$erwartet" ]]; then
    echo "VERALTET (im Dienst $ist, im Baum $erwartet) -> neu bauen"
    veraltet=1; continue
  fi

  printf 'aktuell'

  # Stufe 3: wirkt der Filter. Docker prueft alle 30 s; in 10 Minuten Protokoll
  # muessten ohne Filter rund 20 Zeilen stehen. Eine einzige reicht als Beleg,
  # dass er nicht greift.
  laut="$(docker logs --since 10m "$c" 2>&1 \
          | grep -cE '"(GET|HEAD) /(healthz|health)[^"]*" 2[0-9][0-9]' || true)"
  if [[ "$laut" -gt 0 ]]; then
    printf ', aber Filter UNWIRKSAM (%s Health-Zeilen in 10 min)\n' "$laut"
    unwirksam=1
  else
    printf ', Filter wirkt\n'
  fi
done

echo
[[ $fehlt -eq 1 ]] && { echo "Ergebnis: mindestens ein Dienst hat die geteilte Schicht nicht."; exit 2; }
[[ $veraltet -eq 1 || $unwirksam -eq 1 ]] && { echo "Ergebnis: veralteter oder unwirksamer Stand, siehe oben."; exit 1; }
echo "Ergebnis: alle ${#CONTAINER[@]} Dienste tragen den aktuellen Stand, Filter wirkt ueberall."
exit 0
