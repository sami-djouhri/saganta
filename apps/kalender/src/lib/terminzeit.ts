/**
 * Zeitrechnung fuer Editor, Ziehen und Rueckgaengig (seit 2026-11-21).
 *
 * Alle Zeiten sind naive Berliner Wanduhr (`JJJJ-MM-TTTHH:MM[:SS]`), wie der
 * Kalender sie speichert. Gerechnet wird mit `Date` in Ortszeit nur als
 * Kalenderarithmetik; ausgegeben wird immer wieder naiv.
 */
import type { KalenderEvent } from '$lib/kalender-bff';

const z = (n: number) => String(n).padStart(2, '0');

function lies(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso ?? '');
  if (!m) return null;
  return new Date(+m[1]!, +m[2]! - 1, +m[3]!, +m[4]!, +m[5]!);
}

function schreib(d: Date, sekunden: boolean): string {
  const t = `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`;
  return sekunden ? `${t}:00` : t;
}

/** Um Tage und Minuten verschoben, mit Sekunden; `null` bei unlesbarer Zeit. */
export function verschoben(iso: string | undefined, tage: number, minuten: number): string | null {
  const d = lies(iso ?? '');
  if (!d) return null;
  d.setDate(d.getDate() + tage);
  d.setMinutes(d.getMinutes() + minuten);
  return schreib(d, true);
}

/** Minuten zwischen zwei Zeiten (Ende minus Start); `null`, wenn eine fehlt. */
export function dauerMinuten(start: string, ende: string): number | null {
  const a = lies(start);
  const b = lies(ende);
  if (!a || !b) return null;
  return Math.round((b.getTime() - a.getTime()) / 60000);
}

/**
 * Das Ende, wenn der Start im Editor geaendert wird: es wandert mit und haelt
 * die bisherige Dauer. War die Dauer nicht positiv (Ende vor Start), gilt eine
 * Stunde. Ausgabe im Format des Feldes `datetime-local` (ohne Sekunden).
 */
export function endeWandertMit(alterStart: string, neuerStart: string, altesEnde: string): string {
  const dauer = dauerMinuten(alterStart, altesEnde);
  const neu = lies(neuerStart);
  if (!neu) return altesEnde;
  neu.setMinutes(neu.getMinutes() + (dauer !== null && dauer > 0 ? dauer : 60));
  return schreib(neu, false);
}

/** Ende = Start + Minuten (Dauer-Knoepfe), Format `datetime-local`. */
export function endeNachDauer(start: string, minuten: number): string | null {
  const d = lies(start);
  if (!d) return null;
  d.setMinutes(d.getMinutes() + minuten);
  return schreib(d, false);
}

/** Dauer lesbar: 45 min, 1 h, 1 h 30. */
export const dauerText = (m: number): string =>
  m % 60 === 0 ? `${m / 60} h` : m > 60 ? `${Math.floor(m / 60)} h ${m % 60}` : `${m} min`;

/** Die Kurzwahl der Dauer im Editor, Raster 15 min (Owner-Wahl). */
export const DAUER_KNOEPFE = [15, 30, 60, 90] as const;

/** Die Erinnerungen zur Wahl im Editor, in Minuten vor Beginn (`null` = keine). */
export const ERINNERUNGEN: { minuten: number | null; text: string }[] = [
  { minuten: null, text: 'keine' },
  { minuten: 0, text: 'zu Beginn' },
  { minuten: 10, text: '10 min vorher' },
  { minuten: 30, text: '30 min vorher' },
  { minuten: 60, text: '1 Stunde vorher' },
  { minuten: 120, text: '2 Stunden vorher' },
  { minuten: 1440, text: '1 Tag vorher' },
];

const startVon = (ev: KalenderEvent) => ev.start_at ?? ev.start ?? '';
const endeVon = (ev: KalenderEvent) => ev.end_at ?? ev.end ?? '';

/** Gehoert der Termin zu einer Reihe (Vorkommen oder die Reihe selbst)? */
export function istSerie(ev: KalenderEvent): boolean {
  return String(ev.id).includes('::') || !!ev.recurrence_rule || !!ev.is_recurring_instance;
}

/** Eine Aktion an `+page.server.ts`, die eine andere zuruecknimmt. */
export interface Rueckweg {
  text: string;
  action: string;
  felder: Record<string, string>;
}

/**
 * Rueckweg fuer Verschieben, Laenge ziehen und die Schnellgriffe: die alten
 * Zeiten zurueck. Bei einer Reihe keiner: dort entsteht beim Verschieben eine
 * Ausnahme plus Einzeltermin, und ein halbes Zuruecknehmen waere schlimmer als
 * keines.
 */
export function rueckwegZeit(ev: KalenderEvent, text: string): Rueckweg | null {
  if (istSerie(ev)) return null;
  const start = verschoben(startVon(ev), 0, 0);
  const end = verschoben(endeVon(ev), 0, 0);
  if (!start || !end) return null;
  return { text, action: 'eventVerschieben', felder: { id: ev.id, start, end } };
}

/**
 * Rueckweg fuer das Loeschen eines Einzeltermins: neu anlegen mit denselben
 * Feldern. Bei einer Reihe keiner (eine Ausnahme laesst sich ueber den BFF
 * nicht zuruecknehmen).
 */
export function rueckwegLoeschen(ev: KalenderEvent): Rueckweg | null {
  if (istSerie(ev)) return null;
  const start = verschoben(startVon(ev), 0, 0);
  const end = verschoben(endeVon(ev), 0, 0);
  if (!start || !end || !ev.calendar_id) return null;
  const termin = {
    calendar_id: ev.calendar_id,
    title: ev.title,
    start,
    end,
    all_day: !!ev.all_day,
    location: ev.location || null,
    description: ev.description || null,
    reminder_minutes: ev.reminder_minutes ?? null,
    activity_type: ev.activity_type || null,
    projekt: ev.projekt || null,
  };
  return { text: `„${ev.title}“ gelöscht`, action: 'eventWiederherstellen', felder: { termin: JSON.stringify(termin) } };
}
