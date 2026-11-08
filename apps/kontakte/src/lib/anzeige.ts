/** Kleine Anzeigehilfen, im Browser und im Test benutzbar. */

const MONATE = ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sep.', 'Okt.', 'Nov.', 'Dez.'];

/** `2026-03-10` → `10. März 1995`. Ungueltiges bleibt, wie es kam. */
export function datumLang(iso: string | null): string {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])}. ${MONATE[Number(m[2]) - 1] ?? m[2]} ${m[1]}`;
}

/** `heute`, `morgen`, `in 3 Tagen`. */
export function abstand(tage: number): string {
  if (tage === 0) return 'heute';
  if (tage === 1) return 'morgen';
  return `in ${tage} Tagen`;
}

/** Was am Tag passiert: „wird 31“, „5. Hochzeitstag“. */
export function anlass(a: { art: string; bezeichnung: string; zahl: number }): string {
  if (a.art === 'geburtstag') return a.zahl > 0 ? `wird ${a.zahl}` : 'Geburtstag';
  return a.zahl > 0 ? `${a.zahl}. ${a.bezeichnung}` : a.bezeichnung;
}

/** Anfangsbuchstaben fuer das runde Zeichen vor dem Namen. */
export function kuerzel(name: string): string {
  const teile = name.trim().split(/\s+/).filter(Boolean);
  const erst = teile[0]?.[0] ?? '?';
  const letzt = teile.length > 1 ? (teile[teile.length - 1]?.[0] ?? '') : '';
  return (erst + letzt).toUpperCase();
}

/**
 * Farbe einer Gruppe: farbige Kategorien statt einer App-Farbe (Entscheid
 * 06.11.). Aus dem Namen errechnet, damit dieselbe Gruppe ueberall dieselbe
 * Farbe hat, ohne dass sie irgendwo gespeichert werden muss.
 */
const GRUPPEN_TOENE = [205, 150, 30, 280, 340, 95, 15, 250];

export function gruppenTon(gruppe: string): number {
  let h = 0;
  for (const z of gruppe.toLowerCase()) h = (h * 31 + z.charCodeAt(0)) >>> 0;
  return GRUPPEN_TOENE[h % GRUPPEN_TOENE.length] ?? 205;
}

export function gruppenStil(gruppe: string): string {
  const ton = gruppenTon(gruppe);
  return `color: hsl(${ton} 70% 72%); background: hsl(${ton} 45% 22% / 0.55); border-color: hsl(${ton} 45% 40% / 0.6);`;
}

/** `tel:`-Adresse aus einer frei getippten Nummer. */
export function telAdresse(nummer: string): string {
  return `tel:${nummer.replace(/[^\d+]/g, '')}`;
}
