/**
 * Datumsrechnung, ausschliesslich auf Zeichenketten.
 *
 * ★ Hier wird bewusst kein `Date`-Objekt zum Rechnen verwendet. Ein
 * `new Date('2026-03-29')` ist UTC-Mitternacht, und beim Umstellen der
 * Sommerzeit springt eine Tagesrechnung darueber entweder um einen Tag zu weit
 * oder gar nicht. Ein Tagebuch, das an zwei Tagen im Jahr den falschen Tag
 * oeffnet, ist genau die Art Fehler, die man erst nach Monaten bemerkt.
 * Kalendertage sind hier reine Etiketten, keine Zeitpunkte.
 */

const WOCHENTAGE = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
const MONATE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
];

/** "2026-09-06" wird zu [2026, 9, 6]. Fehlt ein Teil, gilt der 1. Januar 1970,
 * damit eine kaputte Eingabe die Oberflaeche nicht zum Absturz bringt. */
function zerlegen(datum: string): [number, number, number] {
  const teile = datum.split('-').map(Number);
  return [teile[0] || 1970, teile[1] || 1, teile[2] || 1];
}

export function verschieben(datum: string, tage: number): string {
  const [j, m, t] = zerlegen(datum);
  // Date.UTC rechnet ohne Zeitzone, also ohne Sommerzeitsprung.
  const ms = Date.UTC(j, m - 1, t) + tage * 86_400_000;
  return new Date(ms).toISOString().slice(0, 10);
}

export function wochentag(datum: string): string {
  const [j, m, t] = zerlegen(datum);
  return WOCHENTAGE[new Date(Date.UTC(j, m - 1, t)).getUTCDay()] ?? '';
}

export function langformat(datum: string): string {
  const [j, m, t] = zerlegen(datum);
  return `${wochentag(datum)}, ${t}. ${MONATE[m - 1] ?? ''} ${j}`;
}

export function kurzformat(datum: string): string {
  const [, m, t] = zerlegen(datum);
  return `${t}.${m}.`;
}

/** Wie viele Tage hat dieser Monat? Schaltjahre inbegriffen. */
export function tageImMonat(jahr: number, monat: number): number {
  return new Date(Date.UTC(jahr, monat, 0)).getUTCDate();
}

/** Wochentag des Monatsersten, Montag als 0. Traegt das Monatsraster. */
export function ersterWochentag(jahr: number, monat: number): number {
  return (new Date(Date.UTC(jahr, monat - 1, 1)).getUTCDay() + 6) % 7;
}

export const MONATSNAMEN = MONATE;
