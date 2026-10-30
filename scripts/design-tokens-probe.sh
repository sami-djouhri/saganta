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
  # `aufgaben` und `tagebuch` fehlten hier bis 2026-09-27. Beide binden das
  # Token-Paket ein, wurden also nie geprueft, und die Probe meldete trotzdem
  # „Bestanden" -- dieselbe Sorte Wegsehen, gegen die sie gebaut wurde.
  #
  # `mail` ist am 2026-10-24 hier ausgetragen, und der Weg dorthin ist der
  # Grund fuer die drei Wachen unten. `apps/mail/` wurde am 2026-10-03 per
  # Entscheid entfernt (siehe `infra/docker-compose.yml`), sein
  # `src/` existiert nicht mehr. Die Probe meldete trotzdem „ok, alle 16
  # benutzten Marken-Klassen sind im CSS" und zaehlte die App in das
  # „Bestanden (10 Apps geprueft)" mit hinein. Beides war leer:
  #   - die 16 Klassen kamen aus `packages/ui/src`, das immer mitgescannt wird,
  #     nicht aus der App (die hat kein Markup mehr),
  #   - geprueft wurde gegen ein liegengebliebenes CSS vom 27.09., vier Wochen
  #     alt, das noch den alten kollidierenden Warnwert trug.
  # Eine geloeschte App als bestanden zu melden ist schlimmer als sie nicht zu
  # pruefen, weil die Zahl 10 nach Deckung aussieht.
  APPS=(assets aufgaben kalender news notizen post projectdeck shell tagebuch)
fi

# Marken-Namensraeume: das sind die, die es ohne Definition nicht gibt. Tailwinds
# eigene Farben (slate, emerald) sind immer da und deshalb nicht Gegenstand.
# Beim Erweitern der Palette HIER nachziehen. Ein fehlender Name heisst nicht,
# dass die Probe meckert, sondern dass sie wegsieht und trotzdem gruen meldet.
MARKE='(accent|warm|akzent|kupfer|surface|surface-2|text|muted|border|border-stark|erfolg|info|warnung|fehler)'
PRAEFIX='(bg|text|border|ring|from|to|divide|outline|decoration|shadow|accent)'
# Eigene Utilities ohne Theme-Namensraum, die per @utility entstehen muessen.
EIGEN='duration-fast duration-base duration-slow ease-saganta'

gesamt_fehler=0
gebaut=0

# Die Quellen, aus denen das CSS einer App entsteht. Jedes gebaute CSS muss
# JUENGER sein als die juengste davon, sonst misst die Probe einen Stand, den es
# nicht mehr gibt.
#
# Es sind ZWEI, und die zweite hat gefehlt. Zuerst stand hier allein
# `theme.css`. Am 2026-10-24 legte eine parallele Sitzung
# `packages/ui/src/components/NotizenBlock.svelte` an, das `bg-fehler` und
# `border-fehler` benutzt. Weil die Token-Datei `@source "../../ui/src/**"`
# setzt, gehoeren die geteilten Komponenten in die Erwartung JEDER App, und
# `news` und `post` waren drei Stunden aelter: die Probe meldete dort zu Recht
# "WIRKUNGSLOS: bg-fehler border-fehler", riet aber zum Falschen ("Stufe in
# theme.css ergaenzen oder Klasse im Markup aendern"). Richtig war: neu bauen.
# Eine Wache, die nur eine von zwei Quellen kennt, schickt in die falsche
# Richtung, und das ist schlechter als keine Wache, weil man ihr folgt.
TOKENQUELLE='packages/design-tokens/src/theme.css'
# Juengste Datei aus Tokens + geteilten Komponenten. `-printf` statt `ls -t`,
# damit Dateinamen mit Leerzeichen nicht die Sortierung zerlegen.
JUENGSTE=$(find "$TOKENQUELLE" packages/ui/src -type f \
  \( -name '*.css' -o -name '*.svelte' -o -name '*.ts' \) \
  -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
[ -z "$JUENGSTE" ] && JUENGSTE="$TOKENQUELLE"

for app in "${APPS[@]}"; do
  # WACHE 1: Gibt es die App ueberhaupt noch? Ohne `src/` hat sie kein
  # Markup, und die Klassenliste unten fuellt sich dann allein aus
  # `packages/ui/src`. Das Ergebnis liest sich wie eine gepruefte App.
  if [ ! -d "apps/$app/src" ]; then
    printf '%-13s FEHLER: apps/%s/src existiert nicht. Entweder ist die App entfernt\n' "$app" "$app"
    printf '%-13s        (dann hier austragen) oder der Baum ist unvollstaendig.\n' ''
    gesamt_fehler=$((gesamt_fehler + 1))
    continue
  fi

  ausgabe="apps/$app/.svelte-kit/output/client/_app/immutable/assets"
  css=$(ls "$ausgabe"/*.css 2>/dev/null | head -1)
  if [ -z "$css" ]; then
    printf '%-13s uebersprungen (nicht gebaut, `npx vite build` in apps/%s)\n' "$app" "$app"
    continue
  fi

  # WACHE 2, und sie ist die wichtigste der drei: ein CSS, das AELTER ist
  # als die Token-Quelle, beschreibt einen ueberholten Stand. Die Probe lief
  # darauf gruen und bestaetigte damit Werte, die so nicht mehr gelten -- genau
  # der Fall `mail` am 2026-10-24, vier Wochen Abstand. Diese Wache greift
  # ausserdem bei jeder kuenftigen Token-Aenderung, bei der eine App nicht neu
  # gebaut wird, und das ist der haeufigere Fall.
  if [ "$JUENGSTE" -nt "$css" ]; then
    printf '%-13s FEHLER: gebautes CSS ist aelter als %s.\n' "$app" "$JUENGSTE"
    printf '%-13s        Geprueft wuerde ein ueberholter Stand. `npx vite build` in apps/%s.\n' '' "$app"
    gesamt_fehler=$((gesamt_fehler + 1))
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

  # Schriften: jede benannte Familie braucht ein `@font-face` IM SELBEN CSS.
  #
  # Der Grund ist derselbe wie oben, nur eine Ebene tiefer: ein Schriftname
  # ohne Datei ist kein Fehler, sondern still die naechste Systemschrift. Bis
  # 2026-09-27 nannten neun von zehn Apps `Instrument Serif` und `Inter` und
  # lieferten null Schriftdateien aus; 162 Stellen mit `font-display` sahen
  # deshalb aus wie irgendeine Serife des Geraets. Geprueft wird am Bau, nicht
  # an der Konfiguration -- die war die ganze Zeit „richtig".
  # `var(--color-…)` in <style>-Bloecken. Die Klassenpruefung oben sieht die
  # nicht, sie zaehlt Tailwind-Namen im Markup.
  #
  # Ein `var(--color-warm-400, #f59e0b)` in shell/CaptchaField zeigte auf eine
  # Stufe, die es in der Palette nie gab. Das bricht nicht, es nimmt still den
  # Rueckfall -- hier Tailwinds festen Bernstein ohne Theme, 2,1:1 im hellen
  # Bild, und zwar an der Meldung „Pruefung fehlgeschlagen" auf der
  # Anmeldeseite. Genau die Sorte Fehler, gegen die diese Probe gebaut ist, nur
  # eine Schreibweise weiter. Gemessen wird gegen das gebaute CSS: Tailwind v4
  # schreibt jede @theme-Variable dort als `--color-x:` aus.
  #
  # ⚠️ Kommentare vorher entfernen. Der erste Entwurf tat das nicht und meldete
  # prompt den Namen, der in der Notiz ueber seiner eigenen Behebung stand. Eine
  # Probe, die an der Dokumentation der Fundstelle scheitert, erzieht dazu,
  # nichts mehr aufzuschreiben.
  for name in $(find "apps/$app/src" packages/ui/src -type f \
        \( -name '*.svelte' -o -name '*.css' \) -print0 2>/dev/null \
      | xargs -0 perl -0777 -pe 's{/\*.*?\*/}{}gs; s{^\s*//.*$}{}gm' 2>/dev/null \
      | grep -oE 'var\(--color-[a-z0-9-]+' | sed 's/^var(//' | sort -u); do
    grep -qF -- "$name:" "$css" || fehlend+=("undefiniert-$name")
  done

  # Alle `@font-face`-Bloecke, Anfuehrungszeichen und Leerraum entfernt, damit
  # `font-family: 'Instrument Serif'` und `font-family:"InstrumentSerif"` gleich
  # aussehen.
  faces=$(grep -o '@font-face[^}]*}' "$css" 2>/dev/null | tr -d "'\" " || true)
  for familie in 'Instrument Serif' 'Inter Variable'; do
    grep -qF -- "$familie" "$css" || continue
    kompakt=${familie// /}
    printf '%s' "$faces" | grep -qF "font-family:$kompakt" \
      || fehlend+=("Schrift-ohne-@font-face:$kompakt")
  done

  if [ ${#fehlend[@]} -eq 0 ]; then
    anzahl=$(echo "$benutzt" | grep -c . )
    printf '%-13s ok, alle %s benutzten Marken-Klassen sind im CSS\n' "$app" "$anzahl"
  else
    printf '%-13s WIRKUNGSLOS: %s\n' "$app" "${fehlend[*]}"
    gesamt_fehler=$((gesamt_fehler + ${#fehlend[@]}))
  fi
done

# ── Theme-Schalter: das HTML und der Handle muessen denselben Wert meinen ────
#
# `createBetterAuthHandle` biegt das gewaehlte Theme per `replaceAll` ins
# gerenderte HTML. Sucht es einen Wert, den kein `app.html` mehr traegt, dann
# gibt es KEINEN Fehler: die Umschaltung findet nichts und tut still nichts,
# und alle Apps bleiben in der Vorgabe haengen. Genau das waere beim Wechsel
# von `dark` auf `auto` am 2026-09-27 passiert, haette man nur eine Seite
# angefasst. Deshalb wird der Gleichstand hier gemessen und nicht zugesichert.
HANDLE_WERT=$(grep -oE "replaceAll\('data-theme=\\\\?\"([a-z]+)" \
  packages/auth/src/better-auth.ts | grep -oE '[a-z]+$' | head -1)
theme_fehler=0
if [ -z "$HANDLE_WERT" ]; then
  echo "Theme-Schalter: konnte den gesuchten Wert in better-auth.ts nicht lesen."
  theme_fehler=1
else
  for html in apps/*/src/app.html; do
    grep -qF "data-theme=\"$HANDLE_WERT\"" "$html" && continue
    echo "Theme-Schalter: $html traegt nicht data-theme=\"$HANDLE_WERT\" (Handle sucht den)."
    theme_fehler=$((theme_fehler + 1))
  done
  [ "$theme_fehler" -eq 0 ] &&
    echo "Theme-Schalter ok: alle app.html tragen data-theme=\"$HANDLE_WERT\"."
fi
gesamt_fehler=$((gesamt_fehler + theme_fehler))

echo
if [ "$gebaut" -eq 0 ]; then
  echo "Nichts geprueft: keine App war gebaut. Das ist KEIN Bestehen."
  exit 2
fi
if [ "$gesamt_fehler" -eq 0 ]; then
  # WACHE 3: „Bestanden" darf nicht dieselbe Zeile sein wie „teilweise
  # geprueft". Bis zum 2026-10-24 nannte der Bericht nur `$gebaut` und las
  # sich bei 9 von 10 genauso zuversichtlich wie bei 10 von 10. Wer die Zahl
  # nicht gegen die Liste haelt, erfaehrt nie, dass eine App fehlte.
  if [ "$gebaut" -lt "${#APPS[@]}" ]; then
    echo "Teilweise geprueft: $gebaut von ${#APPS[@]} Apps. Die uebrigen waren nicht"
    echo "gebaut und sind damit UNGEPRUEFT, nicht in Ordnung. Das ist kein Bestehen."
    exit 2
  fi
  echo "Bestanden (alle ${#APPS[@]} Apps geprueft): jede benutzte Marken-Klasse kommt im gebauten CSS an."
  exit 0
fi
echo "Durchgefallen: $gesamt_fehler Klasse(n) stehen im Markup, erzeugen aber keine Regel."
echo "Entweder die Stufe in packages/design-tokens/src/theme.css ergaenzen oder"
echo "die Klasse im Markup auf eine vorhandene aendern."
exit 1
