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

/**
 * Der Wohnort unter dem Adressfeld: wie genau er gefunden wurde und der Weg
 * auf die Karte. `null`, wenn es nichts zu sagen gibt (keine Adresse).
 */
export function ortHinweis(k: {
  adresse: string | null;
  lat: number | null;
  lon: number | null;
  ort_stand: string | null;
  ort_genauigkeit: string | null;
}): { text: string; karte: string | null } | null {
  if (k.lat !== null && k.lon !== null) {
    const zoom = k.ort_genauigkeit === 'ort' ? 13 : k.ort_genauigkeit === 'strasse' ? 16 : 18;
    const text =
      k.ort_genauigkeit === 'hand' ? 'Punkt von Hand gesetzt'
      : k.ort_genauigkeit === 'strasse' ? 'Auf der Karte: nur die Straße, die Hausnummer kennt die Adresssuche nicht'
      : k.ort_genauigkeit === 'ort' ? 'Auf der Karte: nur der Ort, Straße nicht gefunden'
      : 'Auf der Karte';
    return {
      text,
      karte: `https://karten.home.arpa/#${zoom}/${k.lat.toFixed(5)}/${k.lon.toFixed(5)}`,
    };
  }
  if (!k.adresse) return null;
  if (k.ort_stand === 'nicht_gefunden') {
    return { text: 'Nicht auf der Karte: die Adresssuche kennt diese Adresse nicht (Form „Straße Nr, PLZ Ort“ hilft)', karte: null };
  }
  return { text: 'Wird gleich auf der Karte gesucht', karte: null };
}
