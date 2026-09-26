#!/usr/bin/env bash
# Prueft, ob jede Marken-Klasse, die das Markup benutzt, im gebauten CSS auch
# wirklich als Regel ankommt.
#
# WARUM ES DIESE PROBE GIBT
# Ein unbekannter Utility-Name ist in Tailwind kein Fehler, sondern schlicht
# nichts: kein Build bricht, keine Warnung erscheint, die Klasse steht im HTML
# und wirkt nur nicht. Das ist zweimal unbemerkt passiert.
#   1) `duration-fast`, `duration-base` und `ease-saganta` standen an 171
#      Stellen im Markup. Definiert waren sie ausschliesslich in einem
#      Tailwind-v3-Preset, das bei v4 kein Build einbindet. Keine dieser 171
#      Stellen hat je eine Regel erzeugt.
#   2) `bg-warm-950` und `text-warm-200` in shell/settings zeigten auf Stufen,
#      die es in der Palette nicht gab. Die Hinweisbox blieb ohne Hintergrund
#      und ohne Textfarbe, sah wegen des vorhandenen Rahmens aber fast richtig
#      aus.
#
# Die Probe misst am GEBAUTEN CSS, nicht an der Konfiguration. Eine Prüfung, die
# nur nachsieht, ob ein Token irgendwo definiert ist, haette Fall 1 durchgelassen:
# dort war alles sauber definiert, nur eben in einer Datei, die niemand liest.
#
# Aufruf:  scripts/design-tokens-probe.sh [app ...]     (ohne Argument: alle)
# Ende:    rc=0 alles angekommen, rc=1 mindestens eine Klasse wirkungslos.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

APPS=("$@")
if [ ${#APPS[@]} -eq 0 ]; then
  APPS=(assets kalender mail news notizen post projectdeck shell)
fi

# Marken-Namensraeume: das sind die, die es ohne Definition nicht gibt. Tailwinds
# eigene Farben (slate, emerald) sind immer da und deshalb nicht Gegenstand.
# Beim Erweitern der Palette HIER nachziehen. Ein fehlender Name heisst nicht,
# dass die Probe meckert, sondern dass sie wegsieht und trotzdem gruen meldet.
MARKE='(accent|warm|surface|surface-2|text|muted|border|erfolg|info|warnung|fehler)'
PRAEFIX='(bg|text|border|ring|from|to|divide|outline|decoration|shadow|accent)'
# Eigene Utilities ohne Theme-Namensraum, die per @utility entstehen muessen.
EIGEN='duration-fast duration-base duration-slow ease-saganta'

gesamt_fehler=0
gebaut=0

for app in "${APPS[@]}"; do
  ausgabe="apps/$app/.svelte-kit/output/client/_app/immutable/assets"
  css=$(ls "$ausgabe"/*.css 2>/dev/null | head -1)
  if [ -z "$css" ]; then
    printf '%-13s uebersprungen (nicht gebaut, `npx vite build` in apps/%s)\n' "$app" "$app"
    continue
  fi
  gebaut=$((gebaut + 1))

  # Was das Markup dieser App benutzt, samt der geteilten Komponenten: die
  # werden ueber @source mitgescannt und gehoeren damit in dieselbe Rechnung.
  benutzt=$(grep -rhoE "\\b${PRAEFIX}-${MARKE}(-[a-z0-9]+)?\\b" \
    "apps/$app/src" packages/ui/src 2>/dev/null | sort -u)

  fehlend=()
  for klasse in $benutzt; do
    # Der Name muss im CSS vorkommen. Nicht auf `.name{` pruefen: wird eine
    # Klasse nur als `hover:`- oder `md:`-Variante benutzt, heisst der Selektor
    # `.hover\:name:hover` und ein Punkt-Praefix-Test meldet sie falsch als
    # fehlend. Genau daran ist der erste Entwurf dieser Probe gescheitert.
    grep -qF -- "$klasse" "$css" || fehlend+=("$klasse")
  done
  for klasse in $EIGEN; do
    grep -rqF -- "$klasse" "apps/$app/src" packages/ui/src 2>/dev/null || continue
    grep -qF -- "$klasse" "$css" || fehlend+=("$klasse")
  done

  if [ ${#fehlend[@]} -eq 0 ]; then
    anzahl=$(echo "$benutzt" | grep -c . )
    printf '%-13s ok, alle %s benutzten Marken-Klassen sind im CSS\n' "$app" "$anzahl"
  else
    printf '%-13s WIRKUNGSLOS: %s\n' "$app" "${fehlend[*]}"
    gesamt_fehler=$((gesamt_fehler + ${#fehlend[@]}))
  fi
done

echo
if [ "$gebaut" -eq 0 ]; then
  echo "Nichts geprueft: keine App war gebaut. Das ist KEIN Bestehen."
  exit 2
fi
if [ "$gesamt_fehler" -eq 0 ]; then
  echo "Bestanden ($gebaut Apps geprueft): jede benutzte Marken-Klasse kommt im gebauten CSS an."
  exit 0
fi
echo "Durchgefallen: $gesamt_fehler Klasse(n) stehen im Markup, erzeugen aber keine Regel."
echo "Entweder die Stufe in packages/design-tokens/src/theme.css ergaenzen oder"
echo "die Klasse im Markup auf eine vorhandene aendern."
exit 1
