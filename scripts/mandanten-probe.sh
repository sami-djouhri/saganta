#!/usr/bin/env bash
# Misst, ob die Saganta-Backends unter dem Zugangsgate mehrere Nutzer tragen.
#
# WARUM ES DAS GIBT: Saganta soll Multi-User werden, laeuft aber faktisch als
# Ein-Nutzer-Suite. Fuenf der sieben Backends lassen per ALLOWED_SUBS nur den
# Sub des Owners durch, ein neu registriertes Konto bekommt dort ueberall 403.
# Das ist eine bewusste Bremse. Sie verdeckt aber die Frage dahinter: traegt die
# Datenschicht darunter ueberhaupt mehrere Nutzer? Solange das Gate zu ist,
# beantwortet das niemand, und beim Oeffnen faellt es auf einmal auf.
#
#   Gate zu + Daten gescoped       = Bremse, jederzeit loesbar
#   Gate zu + Daten nicht gescoped = das Gate ist der einzige Schutz. Oeffnen
#                                    zeigt fremden Nutzern die Daten des Owners.
#
# ★ WIE ERKANNT WIRD, UND WARUM NICHT AM NAMEN: Die erste Fassung dieser Probe
# suchte eine Spalte aus der Liste owner_sub/sub/user_sub. Sie meldete daraufhin
# alle neun projectdeck-Tabellen als ungeschuetzt, obwohl der Dienst sauber
# trennt: seine Mandantenspalte heisst schlicht `owner`, und die Kindtabellen
# haengen per Fremdschluessel daran. Ein Pruefer, der Eigenschaften am Namen
# erkennt, findet genau das nicht, was anders benannt ist.
# Deshalb jetzt zwei Wege, und beide werden im Klartext ausgewiesen:
#   1. Fremdschluesselketten werden verfolgt. Haengt eine Tabelle an einer
#      Tabelle mit Mandantenspalte, ist sie ueber diese gescoped.
#   2. Fuer Wurzeltabellen wird eine breitere Namensliste benutzt UND die
#      erkannte Spalte mit ausgegeben, damit eine falsche Zuordnung auffaellt
#      statt still durchzugehen.
#
# ★ Was diese Probe NICHT beweist: dass der Code die Spalte auch benutzt. Eine
# Tabelle mit `owner_sub` und einer Abfrage ohne Filter sieht hier gesund aus.
# Der Verhaltensnachweis dazu ist scripts/zweiter-nutzer-probe.sh.
#
# Rueckgabe: 0 = nichts Unerwartetes, 1 = Tabelle ohne erkennbaren Mandanten
# ausserhalb der begruendeten Ausnahmen, 2 = ein Dienst antwortet nicht.
set -uo pipefail

DIENSTE=(
  "notizen-api:saganta-notizen-api"
  "projectdeck-api:saganta-projectdeck-api"
  "assets-api:saganta-assets-api"
  "news-api:saganta-news-api"
  "mail-api:saganta-mail-api"
  "shell-api:saganta-shell-api"
)

# Tabellen ohne eigene Mandantenspalte und ohne Fremdschluessel dorthin, die
# trotzdem in Ordnung sind. Jede Zeile braucht einen Grund, sonst waechst hier
# eine stille Ausnahmeliste, die den Zweck der Probe aushoehlt.
AUSNAHMEN=(
  "notizen-api/notizen_fts=Suchindex, jede Abfrage joint auf notizen.owner_sub (suche.py)"
  "notizen-api/notizen_fts_config=interne FTS5-Tabelle"
  "notizen-api/notizen_fts_data=interne FTS5-Tabelle"
  "notizen-api/notizen_fts_docsize=interne FTS5-Tabelle"
  "notizen-api/notizen_fts_idx=interne FTS5-Tabelle"
  "news-api/feed_items=Nachrichten sind fuer alle dieselben, das Persoenliche liegt in user_item_state"
  "news-api/feed_sources=Quellenliste ist gemeinsam"
)

grund_fuer() {
  for eintrag in "${AUSNAHMEN[@]}"; do
    [[ "${eintrag%%=*}" == "$1" ]] && { echo "${eintrag#*=}"; return 0; }
  done
  return 1
}

fehler=0
offen=()

for eintrag in "${DIENSTE[@]}"; do
  dienst="${eintrag%%:*}"
  container="${eintrag#*:}"
  echo "== $dienst"

  docker inspect "$container" >/dev/null 2>&1 || { echo "   FEHLER: Container $container gibt es nicht"; exit 2; }

  gate="$(docker exec "$container" python -c "
from app.config import settings
subs = getattr(settings, 'allowed_subs', [])
print(len(subs) if subs else 0)
" 2>/dev/null)" || gate="?"
  if [[ "$gate" == "0" ]]; then
    echo "   Gate: offen fuer jeden angemeldeten Nutzer (ALLOWED_SUBS leer)"
  else
    echo "   Gate: nur $gate Sub(s) zugelassen (ALLOWED_SUBS gesetzt)"
  fi

  ausgabe="$(docker exec "$container" python -c "
from sqlalchemy import inspect, text
from app.db import engine

# Breit gefasst. Die Liste ist ein Vorschlag, keine Wahrheit: welche Spalte
# erkannt wurde, steht in der Ausgabe und laesst sich damit widerlegen.
KANDIDATEN = ('owner_sub', 'owner', 'sub', 'user_sub', 'besitzer_sub', 'besitzer', 'user_id')

insp = inspect(engine)
tabellen = sorted(insp.get_table_names())
if not tabellen:
    print('LEER')

spalten = {t: [s['name'] for s in insp.get_columns(t)] for t in tabellen}

def eigener_schluessel(t):
    for k in KANDIDATEN:
        if k in spalten[t]:
            return k
    return None

def ueber_fremdschluessel(t, gesehen=None):
    '''Folgt den Fremdschluesseln bis zu einer Tabelle mit Mandantenspalte.'''
    gesehen = gesehen or set()
    if t in gesehen:
        return None
    gesehen.add(t)
    for fk in insp.get_foreign_keys(t):
        ziel = fk.get('referred_table')
        if not ziel or ziel not in spalten:
            continue
        k = eigener_schluessel(ziel)
        if k:
            return f'{ziel}.{k}'
        weiter = ueber_fremdschluessel(ziel, gesehen)
        if weiter:
            return weiter
    return None

with engine.connect() as conn:
    for t in tabellen:
        zeilen = conn.execute(text(f'select count(*) from \"{t}\"')).scalar()
        k = eigener_schluessel(t)
        if k:
            leer = conn.execute(text(f'select count(*) from \"{t}\" where {k} is null')).scalar()
            subs = conn.execute(text(f'select count(distinct {k}) from \"{t}\"')).scalar()
            print(f'EIGEN\t{t}\t{zeilen}\t{k}\t{subs}\t{leer}')
            continue
        ueber = ueber_fremdschluessel(t)
        if ueber:
            print(f'FK\t{t}\t{zeilen}\t{ueber}')
        else:
            print(f'OHNE\t{t}\t{zeilen}')
" 2>/dev/null)" || { echo "   FEHLER: Abfrage im Container fehlgeschlagen"; exit 2; }

  if [[ "$ausgabe" == "LEER" || -z "$ausgabe" ]]; then
    echo "   keine eigenen Tabellen (zustandsloser Proxy)"
    echo
    continue
  fi

  while IFS=$'\t' read -r art tabelle zeilen feld subs leer; do
    [[ -z "${art:-}" ]] && continue
    case "$art" in
      EIGEN)
        hinweis=""
        if [[ "${leer:-0}" != "0" ]]; then
          hinweis="   ACHTUNG: $leer Zeile(n) ohne Mandant, die sieht jeder"
          fehler=1
        fi
        printf '   %-24s %7s Zeilen  eigene Spalte %s: %s Sub(s)%s\n' "$tabelle" "$zeilen" "$feld" "$subs" "$hinweis"
        ;;
      FK)
        printf '   %-24s %7s Zeilen  ueber %s\n' "$tabelle" "$zeilen" "$feld"
        ;;
      OHNE)
        if grund="$(grund_fuer "$dienst/$tabelle")"; then
          printf '   %-24s %7s Zeilen  gemeinsam: %s\n' "$tabelle" "$zeilen" "$grund"
        else
          printf '   %-24s %7s Zeilen  KEIN Mandant erkennbar\n' "$tabelle" "$zeilen"
          offen+=("$dienst/$tabelle")
          fehler=1
        fi
        ;;
    esac
  done <<< "$ausgabe"
  echo
done

if ((${#offen[@]})); then
  echo "Tabellen mit eigenen Daten und ohne erkennbaren Mandanten:"
  printf '  %s\n' "${offen[@]}"
  echo
  echo "Dort ist ALLOWED_SUBS nicht Vorsicht, sondern der einzige Schutz."
fi

exit "$fehler"
