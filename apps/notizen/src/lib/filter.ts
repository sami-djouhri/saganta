/**
 * Filter der Notizliste (seit 2026-11-21). Gefiltert wird im Dienst
 * (`/api/notizen`), hier stehen nur die Wörter und ihre Beschriftungen,
 * damit Adresse, Server und Oberfläche dieselben kennen.
 */

/** Wert von `?buch=` für Notizen ohne Notizbuch. */
export const OHNE_BUCH = 'ohne';

export const HAT_FILTER = [
  'aufgabe',
  'termin',
  'projekt',
  'kontakt',
  'anhang',
  'freigabe',
  'verweis',
  'angeheftet',
] as const;
export type HatFilter = (typeof HAT_FILTER)[number];

export const HAT_BESCHRIFTUNG: Record<HatFilter, string> = {
  aufgabe: 'Aufgabe',
  termin: 'Termin',
  projekt: 'Projekt',
  kontakt: 'Kontakt',
  anhang: 'Anhang',
  freigabe: 'Geteilt',
  verweis: 'Verweise',
  angeheftet: 'Angeheftet',
};

export const SORTIERUNGEN = [
  { wert: '', name: 'Zuletzt geändert' },
  { wert: 'erstellt', name: 'Neu angelegt' },
  { wert: 'titel', name: 'Titel A-Z' },
] as const;

/** Ein Wort in einer kommagetrennten Liste an- oder abschalten; leer wird `null`. */
export function umschalten(liste: readonly string[], wert: string): string | null {
  const neu = liste.includes(wert) ? liste.filter((x) => x !== wert) : [...liste, wert];
  return neu.length ? neu.join(',') : null;
}
