#!/usr/bin/env bash
# Backend-Tests aller Dienste gegen den QUELLBAUM, je Dienst in einer eigenen venv.
#
# Laeuft in der CI (`.gitea/workflows/ci.yml`, Vorlage in
# interne Notiz, ZIELBILD 46 B1) und genauso von Hand:
#
#   bash scripts/ci-tests.sh                  # alle Dienste mit tests/
#   bash scripts/ci-tests.sh aufgaben-api     # nur dieser
#
# Gegenstueck zu `tests-im-image.sh`, nicht Ersatz: jenes prueft das GEBAUTE Image (was
# laeuft), dieses den Stand im Repo (was als naechstes gebaut wird), und braucht dafuer
# kein Docker. Abhaengigkeiten kommen aus dem pyproject des Dienstes samt `dev`-Extra;
# `saganta_dienst` wie im Dockerfile ohne eigene Abhaengigkeiten aus services/_geteilt.
#
# Mindestzahl je Dienst: weniger gelaufene Tests als dort genannt ist rot, auch wenn
#   alle gruen sind. Fehlt eine Testabhaengigkeit, laesst pytest ganze Module still aus.
#   Die Zahlen sind Untergrenzen, gemessen beim Einrichten; wer Tests hinzufuegt, darf
#   sie heben, wer welche loescht, muss sie senken und das im Commit begruenden.
set -uo pipefail

WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"

# Gemessen 2026-11-21 mit genau diesem Ablauf (python:3.12-slim, ohne .env; seit B2 3.13).
declare -A MINDEST=(
  [_geteilt]=88
  [assistent-api]=32
  [aufgaben-api]=78
  [kalender-bff]=136
  [kontakte-api]=34
  [mail-api]=16
  [news-api]=99
  [notizen-api]=120
  [projectdeck-api]=71
  [shell-api]=33
  [tagebuch-api]=41
)

ZIELE=("$@")
if [ ${#ZIELE[@]} -eq 0 ]; then
  for d in "$WURZEL"/services/*/; do
    [ -d "$d/tests" ] && ZIELE+=("$(basename "$d")")
  done
fi

# Ein Dienst mit tests/, der in MINDEST fehlt, waere ohne Untergrenze gruen.
for z in "${ZIELE[@]}"; do
  if [ -z "${MINDEST[$z]:-}" ]; then
    echo "FEHLER: $z hat tests/, aber keine Mindestzahl in ci-tests.sh" >&2
    exit 1
  fi
done

abhaengigkeiten() {
  "$PY" - "$1" <<'PY'
import sys, tomllib
p = tomllib.load(open(sys.argv[1] + "/pyproject.toml", "rb"))["project"]
print("\n".join(p.get("dependencies", []) + p.get("optional-dependencies", {}).get("dev", [])))
PY
}

FEHLER=0
BERICHT=()
for dienst in "${ZIELE[@]}"; do
  pfad="$WURZEL/services/$dienst"
  venv="${TMPDIR:-/tmp}/saganta-ci-venv-$dienst"
  echo "== $dienst"
  rm -rf "$venv"
  "$PY" -m venv "$venv"
  pip=("$venv/bin/python" -m pip install -q --disable-pip-version-check)
  if ! { abhaengigkeiten "$pfad" > "$venv/anforderungen.txt" \
         && "${pip[@]}" -r "$venv/anforderungen.txt" pytest httpx pytest-asyncio \
         && "${pip[@]}" --no-deps "$WURZEL/services/_geteilt"; } > "$venv/pip.log" 2>&1; then
    tail -20 "$venv/pip.log" | sed 's/^/   /'
    BERICHT+=("$dienst  ROT  Installation gescheitert")
    FEHLER=1
    continue
  fi

  # _geteilt testet mit unittest (run-tests.sh), alle anderen mit pytest.
  if [ "$dienst" = "_geteilt" ]; then
    lauf=(sh -c 'cd tests && "$0" -m unittest discover -s . -t . 2>&1' "$venv/bin/python")
  else
    lauf=("$venv/bin/python" -m pytest tests/ -q -p no:cacheprovider)
  fi
  ausgabe="$(cd "$pfad" && ALLOW_INSECURE_SECRETS=1 \
    JWT_SECRET=test-geheimnis-nur-fuer-den-testlauf "${lauf[@]}" 2>&1)"
  rc=$?
  gelaufen="$(printf '%s\n' "$ausgabe" | "$PY" -c '
import re, sys
text = sys.stdin.read()
m = re.findall(r"^Ran (\d+) tests?", text, re.M)
if m:
    print(m[-1])
else:
    zeilen = [z for z in text.splitlines() if re.search(r"\d+ (passed|failed)", z)]
    print(sum(int(z) for z in re.findall(r"(\d+) (?:passed|failed|errors?|skipped|xfailed|xpassed)", zeilen[-1])) if zeilen else 0)
')"
  letzte="$(printf '%s\n' "$ausgabe" | grep -E 'passed|failed|^Ran |^OK|^FAILED' | tail -1)"
  if [ "$rc" -ne 0 ]; then
    printf '%s\n' "$ausgabe" | tail -30 | sed 's/^/   /'
    BERICHT+=("$dienst  ROT  ${letzte:-kein Ergebnis}")
    FEHLER=1
  elif [ "$gelaufen" -lt "${MINDEST[$dienst]}" ]; then
    BERICHT+=("$dienst  ROT  nur $gelaufen Tests, mindestens ${MINDEST[$dienst]}")
    FEHLER=1
  else
    BERICHT+=("$dienst  gruen  $gelaufen Tests (mindestens ${MINDEST[$dienst]})")
  fi
  echo "   ${letzte:-?}"
  rm -rf "$venv"
done

echo
echo "Zusammenfassung:"
for z in "${BERICHT[@]}"; do echo "  $z"; done
exit "$FEHLER"
