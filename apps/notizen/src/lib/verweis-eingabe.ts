/**
 * Vorschläge beim Tippen von `[[` (seit 2026-11-20).
 *
 * Zwei reine Funktionen, damit Web und Test dieselbe Regel sehen: erkennen, ob
 * der Cursor gerade in einem offenen `[[…` steht, und den gewählten Titel
 * einsetzen. Die Zeichenregel ist dieselbe wie in `markdown.ts` und in der API
 * (`routes_netz.py`): kein Zeilenumbruch, keine eckige Klammer, kein `|` im Titel.
 */

export interface OffenerVerweis {
  /** Stelle des ersten `[` von `[[`. */
  start: number;
  /** Was nach `[[` bis zum Cursor steht. */
  anfrage: string;
}

/** Steht der Cursor in einem offenen `[[…`? Sonst `null`. */
export function offenerVerweis(text: string, cursor: number): OffenerVerweis | null {
  const zeilenAnfang = text.lastIndexOf('\n', cursor - 1) + 1;
  const zeile = text.slice(zeilenAnfang, cursor);
  const auf = zeile.lastIndexOf('[[');
  if (auf < 0) return null;
  const anfrage = zeile.slice(auf + 2);
  if (/[[\]|]/.test(anfrage) || anfrage.length > 300) return null;
  // In Inline-Code ist `[[x]]` Beispiel, kein Verweis: eine ungerade Zahl von
  // Backticks davor heißt, der Cursor steht im Code.
  if ((zeile.slice(0, auf).match(/`/g)?.length ?? 0) % 2 === 1) return null;
  if (codeblockOffen(text.slice(0, zeilenAnfang))) return null;
  return { start: zeilenAnfang + auf, anfrage };
}

function codeblockOffen(davor: string): boolean {
  return (davor.match(/^```/gm)?.length ?? 0) % 2 === 1;
}

/**
 * Setzt `[[titel]]` an die Stelle des offenen Verweises und gibt Text und neue
 * Cursorstelle zurück (hinter `]]`). Stehen hinter dem Cursor noch Reste eines
 * schon geschlossenen Verweises (`[[Gar|ten]]` beim Bearbeiten), werden sie
 * mit ersetzt, statt `]]` doppelt zu hinterlassen.
 */
export function verweisEinsetzen(
  text: string,
  cursor: number,
  offen: OffenerVerweis,
  titel: string,
): { text: string; cursor: number } {
  const zeilenEnde = text.indexOf('\n', cursor);
  const rest = text.slice(cursor, zeilenEnde < 0 ? text.length : zeilenEnde);
  const zu = rest.indexOf(']]');
  const bis = zu >= 0 && !/[[\]]/.test(rest.slice(0, zu)) ? cursor + zu + 2 : cursor;
  // Eine Anzeige hinter `|` bleibt erhalten, nur der Titel wechselt.
  const alt = text.slice(offen.start, bis);
  const anzeige = bis > cursor ? (alt.match(/\|([^\]]*)\]\]$/)?.[1] ?? null) : null;
  const sauber = titel.split(/\s+/).filter(Boolean).join(' ');
  const neu = anzeige !== null ? `[[${sauber}|${anzeige}]]` : `[[${sauber}]]`;
  return {
    text: text.slice(0, offen.start) + neu + text.slice(bis),
    cursor: offen.start + neu.length,
  };
}

/**
 * Pixelstelle des Cursors in einem Textfeld, relativ zu dessen Innenkante.
 *
 * Ein Textfeld verrät die Stelle nicht; der übliche Weg ist ein unsichtbarer
 * Doppelgänger mit denselben Schrift- und Umbruchregeln, in dem ein Marker an
 * der Cursorstelle steht. Nur im Browser aufrufen.
 */
export function cursorPunkt(feld: HTMLTextAreaElement, stelle: number): { x: number; y: number } {
  const stil = getComputedStyle(feld);
  const spiegel = document.createElement('div');
  for (const eigenschaft of [
    'boxSizing', 'width', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
    'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
    'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'letterSpacing', 'lineHeight',
    'textTransform', 'wordSpacing', 'tabSize',
  ] as const) {
    spiegel.style[eigenschaft] = stil[eigenschaft];
  }
  spiegel.style.position = 'absolute';
  spiegel.style.visibility = 'hidden';
  spiegel.style.whiteSpace = 'pre-wrap';
  spiegel.style.overflowWrap = 'break-word';
  spiegel.style.top = '0';
  spiegel.style.left = '-9999px';
  spiegel.textContent = feld.value.slice(0, stelle);
  const marker = document.createElement('span');
  marker.textContent = '​';
  spiegel.appendChild(marker);
  document.body.appendChild(spiegel);
  const punkt = {
    x: marker.offsetLeft - feld.scrollLeft,
    y: marker.offsetTop - feld.scrollTop + parseFloat(stil.lineHeight || '24'),
  };
  spiegel.remove();
  return punkt;
}
