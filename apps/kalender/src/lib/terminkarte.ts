/**
 * Termin-Karte und Schnellgriffe (seit 2026-11-21, Owner-Wahl wie in der App):
 * Antippen zeigt zuerst, was der Termin ist, der Editor kommt auf Wunsch.
 * Gleiche Regeln wie `feature-kalender/.../domain/TerminKarte.kt`.
 */
import type { KalenderEvent } from './kalender-bff';
import { istAufgabe, startOf } from './cal';

export const WEGE_KALENDER = 'system-wege-0000-0000-000000000000';

export interface Schnellgriff {
  schluessel: 'plus15' | 'morgen' | 'woche' | 'kopie';
  text: string;
  tage: number;
  minuten: number;
}

export const SCHNELLGRIFFE: Schnellgriff[] = [
  { schluessel: 'plus15', text: '+15 min', tage: 0, minuten: 15 },
  { schluessel: 'morgen', text: 'Morgen', tage: 1, minuten: 0 },
  { schluessel: 'woche', text: 'Nächste Woche', tage: 7, minuten: 0 },
  { schluessel: 'kopie', text: 'Duplizieren', tage: 0, minuten: 0 },
];

export interface TerminRechte {
  bearbeiten: boolean;
  verschieben: boolean;
  duplizieren: boolean;
}

/** Erzeugtes (Wege, Tagestypen, Feiertage, Geburtstage, Aufgaben) ist nur zum Ansehen. */
export function terminRechte(ev: KalenderEvent): TerminRechte {
  const cid = ev.calendar_id ?? '';
  const erzeugt =
    cid === WEGE_KALENDER || /^daytype-/.test(cid) || /^system-geburtstage/.test(cid) || istAufgabe(ev);
  if (erzeugt) return { bearbeiten: false, verschieben: false, duplizieren: false };
  // Die Serie selbst (ohne Vorkommens-Kennung) verschiebt man im Editor.
  const serieSelbst = !!ev.recurrence_rule && !String(ev.id).includes('::');
  return { bearbeiten: true, verschieben: !serieSelbst, duplizieren: true };
}

export function schnellgriffe(ev: KalenderEvent): Schnellgriff[] {
  const r = terminRechte(ev);
  return SCHNELLGRIFFE.filter((g) =>
    g.schluessel === 'kopie' ? r.duplizieren : g.schluessel === 'plus15' ? r.verschieben && !ev.all_day : r.verschieben,
  );
}

/** „Sa., 21. November (heute)"; das Jahr nur, wenn es nicht das laufende ist. */
export function kartenDatum(ev: KalenderEvent, heute: string): string {
  const tag = startOf(ev).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(tag)) return '';
  const ymd = (x: string): [number, number, number] => {
    const [j = 0, m = 1, t = 1] = x.split('-').map(Number);
    return [j, m - 1, t];
  };
  const d = new Date(Date.UTC(...ymd(tag)));
  const optionen: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'long', timeZone: 'UTC' };
  if (tag.slice(0, 4) !== heute.slice(0, 4)) optionen.year = 'numeric';
  const morgen = new Date(Date.UTC(...ymd(heute)) + 864e5).toISOString().slice(0, 10);
  const relativ = tag === heute ? ' (heute)' : tag === morgen ? ' (morgen)' : '';
  return d.toLocaleDateString('de-DE', optionen) + relativ;
}

export function erinnerungText(minuten: number | null | undefined): string | null {
  if (minuten === null || minuten === undefined) return null;
  if (minuten === 0) return 'zum Beginn';
  if (minuten % 1440 === 0) return `${minuten / 1440} ${minuten === 1440 ? 'Tag' : 'Tage'} vorher`;
  if (minuten % 60 === 0) return `${minuten / 60} h vorher`;
  return `${minuten} min vorher`;
}

const ARTEN: Record<string, string> = {
  lernen: 'Lernen',
  sport: 'Sport',
  lesen: 'Lesen',
  hobby: 'Hobby',
  sonstige: 'Aktivität',
};
export function artText(art: string | null | undefined): string | null {
  return (art && ARTEN[art]) || null;
}

const TAGE: Record<string, string> = { MO: 'Mo', TU: 'Di', WE: 'Mi', TH: 'Do', FR: 'Fr', SA: 'Sa', SU: 'So' };

/** Kurzer Klartext einer RRULE („Wöchentlich am Mo, Do", „Alle 2 Wochen bis 13.11.2026"). */
export function wiederholungText(rrule: string | null | undefined): string | null {
  if (!rrule) return null;
  const teile = Object.fromEntries(
    rrule
      .replace(/^RRULE:/, '')
      .split(';')
      .map((t) => t.split('=') as [string, string]),
  );
  const n = Number(teile.INTERVAL ?? 1) || 1;
  const grund: Record<string, [string, string]> = {
    DAILY: ['Täglich', 'Tage'],
    WEEKLY: ['Wöchentlich', 'Wochen'],
    MONTHLY: ['Monatlich', 'Monate'],
    YEARLY: ['Jährlich', 'Jahre'],
  };
  const g = grund[String(teile.FREQ ?? '')];
  if (!g) return 'wiederholt sich';
  let text = n === 1 ? g[0] : `Alle ${n} ${g[1]}`;
  if (teile.BYDAY) {
    const tage = String(teile.BYDAY)
      .split(',')
      .map((t) => TAGE[t.slice(-2)] ?? t)
      .join(', ');
    text += ` am ${tage}`;
  }
  const bis = /^(\d{4})(\d{2})(\d{2})/.exec(String(teile.UNTIL ?? ''));
  if (bis) text += ` bis ${bis[3]}.${bis[2]}.${bis[1]}`;
  return text;
}
