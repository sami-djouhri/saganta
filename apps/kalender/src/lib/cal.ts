// Geteilte, zeitzonen-sichere Kalender-Helfer für alle Ansichten (Agenda, Monat,
// Woche). Die Logik ist bewusst 1:1 aus der früheren +page.svelte übernommen:
// sie war über Monate gehärtet gegen SSR/Client-Hydration-Mismatches (der
// SSR-Node-Container läuft auf UTC, der Browser auf Europe/Berlin) und gegen
// Svelte-5 `each_key_duplicate`-Crashes bei doppelten Event-IDs.
import type { KalenderEvent } from '$lib/kalender-bff';

export const BERLIN = 'Europe/Berlin';

// Feste Kalender-Palette (Fallback, wenn der Upstream keine Farbe liefert).
export const PALETTE = [
  '#5d7eff',
  '#c8884a',
  '#3ec98a',
  '#e0639a',
  '#9b6dff',
  '#48b7d4',
  '#d4b748',
  '#d4685d',
];
export const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

// Day-Type-Kalender (Arbeit/Schule/Urlaub/Krank) sind Tagestyp-KONTEXT, keine
// Termine. Als Ganztages-Events würden sie fast jeden Tag zumüllen, sie werden
// aus der Terminliste genommen und pro Tag als Badge/Tönung gezeigt. Feiertage
// sind zwar auch ein Day-Type, aber gewollter Inhalt → bleiben als Termin.
export const DAYTYPE_LABEL: Record<string, string> = {
  arbeit: 'Arbeit',
  schule: 'Schule',
  urlaub: 'Urlaub',
  krank: 'Krank',
};

// Dezente Tönungsfarben je Tagestyp (als rgba, damit Tailwind-Purge sie nicht
// entfernt und die Töne präzise zum warmen „Nachtstudie"-Theme passen).
export const DAYTYPE_TINT: Record<string, string> = {
  arbeit: 'rgba(93, 126, 255, 0.10)',
  schule: 'rgba(155, 109, 255, 0.12)',
  urlaub: 'rgba(62, 201, 138, 0.13)',
  krank: 'rgba(212, 104, 93, 0.13)',
};
export const DAYTYPE_DOT: Record<string, string> = {
  arbeit: '#5d7eff',
  schule: '#9b6dff',
  urlaub: '#3ec98a',
  krank: '#d4685d',
};

// Kategorie-Marker (Aktivitäts-/Vorschlags-Icons): bewusst Emoji für Wärme.
// Zentral, damit Sidebar, Feedback, Insights und Modal EINEN Satz teilen
// (war vorher 4× als lokales Objekt dupliziert). `icon()`-Helfer mit Fallback.
/**
 * Symbol je Aktivitaetsart. Namen aus der Icon-Registry in `@saganta/ui`.
 *
 * ★ Standen bis 2026-09-13 als Emojis hier (📚 🏋️ 📖 🎯 🛒 🛋️). Drei Gruende
 * fuer den Wechsel, und alle drei sind Anzeigefehler, keine Geschmacksfrage:
 * ein Emoji rendert je Betriebssystem anders (auf dem Pi teils gar nicht), es
 * erbt die Textfarbe nicht und steht damit neben eingefaerbtem Text falsch, und
 * es laesst sich nicht auf die Zeilenhoehe ausrichten. Owner-Vorgabe ausserdem:
 * Icons statt Emojis.
 */
export const ACTIVITY_ICON: Record<string, string> = {
  lernen: 'graduation-cap',
  sport: 'dumbbell',
  lesen: 'book',
  hobby: 'sparkles',
  einkauf: 'shopping-cart',
  erholung: 'armchair',
  todo: 'square-check',
  sonstige: 'circle',
};
export function activityIcon(kind: string | null | undefined): string {
  return ACTIVITY_ICON[kind ?? 'sonstige'] ?? 'circle';
}

export function dayTypeOf(ev: KalenderEvent): string | null {
  const m = /^daytype-([a-z]+)-/.exec(ev.calendar_id ?? '');
  return m ? (DAYTYPE_LABEL[m[1]!] ?? null) : null;
}
export function dayTypeKeyOf(ev: KalenderEvent): string | null {
  const m = /^daytype-([a-z]+)-/.exec(ev.calendar_id ?? '');
  return m && DAYTYPE_LABEL[m[1]!] ? m[1]! : null;
}
export function isContextDaytypeCal(id: string): boolean {
  return /^daytype-(arbeit|schule|urlaub|krank)-/.test(id);
}
export function isHolidayEvent(ev: KalenderEvent): boolean {
  return /^daytype-feiertag-/.test(ev.calendar_id ?? '');
}
export function isBirthdayEvent(ev: KalenderEvent): boolean {
  return /^system-geburtstage/.test(ev.calendar_id ?? '');
}

const ymdFmt = new Intl.DateTimeFormat('en-CA', {
  timeZone: BERLIN,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

export function startOf(ev: KalenderEvent): string {
  return ev.start_at ?? ev.start ?? '';
}
export function endOf(ev: KalenderEvent): string {
  return ev.end_at ?? ev.end ?? '';
}

// Kalendertag (Y-M-D) in Europe/Berlin: TZ-stabil über formatToParts, unabhängig
// von der Laufzeit-Zeitzone des Prozesses.
export function localYmd(d: Date): string {
  const p = ymdFmt.formatToParts(d);
  const get = (t: string) => p.find((x) => x.type === t)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}`;
}

// Gruppierungs-Schlüssel = LOKALER Kalendertag. All-day-Events (oder reine
// Datumsstrings) ohne Zeitzonen-Umrechnung übernehmen, sonst kann UTC-Mitter-
// nacht in den Vor-/Folgetag rutschen.
export function dayKeyOf(ev: KalenderEvent): string {
  const iso = startOf(ev);
  if (!iso) return '';
  if (ev.all_day || /^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso.slice(0, 10);
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso.slice(0, 10) : localYmd(d);
}

export function endDayKey(ev: KalenderEvent): string {
  const iso = endOf(ev);
  if (!iso) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso.slice(0, 10);
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : localYmd(d);
}

// Letzter Kalendertag, den ein Event TATSÄCHLICH abdeckt. Ganztägige Events
// speichern ihr Ende uneinheitlich: native Day-Types EXKLUSIV (nächste
// Mitternacht, z. B. Urlaub 29.07 → Ende 30.07T00:00), Saganta INKLUSIV
// (23:59:59). Bei Ende exakt 00:00 (naiver String) ist es exklusiv → Vortag.
// String-basierter Mitternachts-Check, weil eine TZ-Umrechnung 00:00 verschöbe.
export function inclusiveEndKey(ev: KalenderEvent): string {
  const start = dayKeyOf(ev);
  const raw = endOf(ev);
  if (!raw) return start;
  const endKey = endDayKey(ev);
  if (!endKey || endKey <= start) return start;
  if (raw.slice(11, 16) === '00:00') {
    const prev = endDayKey(ev) ? shiftDay(endKey, -1) : start;
    return prev < start ? start : prev;
  }
  return endKey;
}

export function isMultiDay(ev: KalenderEvent): boolean {
  if (ev.all_day) return false;
  const ek = endDayKey(ev);
  return !!ek && ek !== dayKeyOf(ev);
}

export function fmtDate(iso: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('de-DE', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    timeZone: BERLIN,
  });
}

export function fmtTime(iso: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: BERLIN,
  });
}

// Zeitspalte: ganztags / "ab HH:MM" (mehrtägig) / "HH:MM–HH:MM" / "HH:MM".
export function timeCol(ev: KalenderEvent): string {
  if (ev.all_day) return 'ganztags';
  const s = fmtTime(startOf(ev));
  if (isMultiDay(ev)) return `ab ${s}`;
  const e = endOf(ev) ? fmtTime(endOf(ev)) : '';
  return e && e !== s ? `${s}–${e}` : s;
}

// Für mehrtägige getimte Events das Ende mit Datum nennen, sonst sähe
// "18:00–10:00" wie ein rückwärts laufender Slot am selben Tag aus.
export function endNote(ev: KalenderEvent): string {
  if (!isMultiDay(ev)) return '';
  const iso = endOf(ev);
  return `bis ${fmtDate(iso)} · ${fmtTime(iso)}`;
}

export function dayLabel(key: string, nowMs: number | null): string {
  if (nowMs !== null) {
    const today = localYmd(new Date(nowMs));
    const tmrw = new Date(nowMs);
    tmrw.setDate(tmrw.getDate() + 1);
    const yest = new Date(nowMs);
    yest.setDate(yest.getDate() - 1);
    if (key === today) return 'Heute';
    if (key === localYmd(tmrw)) return 'Morgen';
    if (key === localYmd(yest)) return 'Gestern';
  }
  // Mittag-UTC: liegt in jeder Zone am selben Kalendertag → kein Tag-Flip.
  return fmtDate(key + 'T12:00:00Z');
}

export function isPast(ev: KalenderEvent, nowMs: number | null): boolean {
  if (nowMs === null) return false;
  if (ev.all_day) {
    const endDay = endDayKey(ev) || dayKeyOf(ev);
    return !!endDay && endDay < localYmd(new Date(nowMs));
  }
  const ref = endOf(ev) || startOf(ev);
  const t = new Date(ref).getTime();
  return !Number.isNaN(t) && t < nowMs;
}

// Dedup gegen Svelte-5 `each_key_duplicate`: doppelte id-Keys (mehrtägige/
// wiederkehrende Events oder doppelt gelieferte Kalender) crashen die Client-
// Hydration hart. Eindeutige Keys erzwingen.
export function uniqueBy<T>(arr: readonly T[], key: (x: T) => unknown): T[] {
  const seen = new Set<unknown>();
  return arr.filter((x) => {
    const k = key(x);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

// Chronologischer Sort (gemischte Offsets …Z vs …+02:00 ordnet String-Vergleich
// falsch). Unparsebares ans Ende.
export function byStart(a: KalenderEvent, b: KalenderEvent): number {
  const ta = Date.parse(startOf(a));
  const tb = Date.parse(startOf(b));
  if (Number.isNaN(ta) || Number.isNaN(tb)) return startOf(a).localeCompare(startOf(b));
  return ta - tb;
}

// ── Monats-Grid: 42 Tage (6 Wochen) ab Montag der Woche des Monatsersten ──
export function monthGridDays(month: string): string[] {
  const [y, m] = month.split('-').map(Number);
  const first = new Date(Date.UTC(y!, (m ?? 1) - 1, 1));
  const dow = (first.getUTCDay() + 6) % 7; // Mo=0 … So=6
  const gridStart = new Date(first);
  gridStart.setUTCDate(first.getUTCDate() - dow);
  const out: string[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setUTCDate(gridStart.getUTCDate() + i);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

export function monthLabel(month: string): string {
  const [y, m] = month.split('-').map(Number);
  return new Date(Date.UTC(y!, (m ?? 1) - 1, 1)).toLocaleDateString('de-DE', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split('-').map(Number);
  const d = new Date(Date.UTC(y!, (m ?? 1) - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

// ── Wochen-Grid: 7 Tage (Mo–So) der Woche eines Anker-Datums ──
export function weekStart(dayKey: string): string {
  const [y, m, d] = dayKey.split('-').map(Number);
  const dt = new Date(Date.UTC(y!, (m ?? 1) - 1, d ?? 1));
  const dow = (dt.getUTCDay() + 6) % 7; // Mo=0
  dt.setUTCDate(dt.getUTCDate() - dow);
  return dt.toISOString().slice(0, 10);
}
export function weekGridDays(anchor: string): string[] {
  const start = weekStart(anchor);
  const [y, m, d] = start.split('-').map(Number);
  const out: string[] = [];
  for (let i = 0; i < 7; i++) {
    const dt = new Date(Date.UTC(y!, (m ?? 1) - 1, (d ?? 1) + i));
    out.push(dt.toISOString().slice(0, 10));
  }
  return out;
}
export function shiftDay(dayKey: string, delta: number): string {
  const [y, m, d] = dayKey.split('-').map(Number);
  const dt = new Date(Date.UTC(y!, (m ?? 1) - 1, (d ?? 1) + delta));
  return dt.toISOString().slice(0, 10);
}
export function weekLabel(anchor: string): string {
  const days = weekGridDays(anchor);
  const a = new Date(days[0]! + 'T12:00:00Z');
  const b = new Date(days[6]! + 'T12:00:00Z');
  const sameMonth = days[0]!.slice(0, 7) === days[6]!.slice(0, 7);
  const fa = a.toLocaleDateString('de-DE', {
    day: '2-digit',
    month: sameMonth ? undefined : 'short',
    timeZone: 'UTC',
  });
  const fb = b.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
  return `${fa} – ${fb}`;
}

// Minuten seit Mitternacht (lokal/Berlin) für einen ISO-Zeitpunkt.
export function minutesOfDay(iso: string): number {
  if (!iso) return 0;
  const hhmm = fmtTime(iso); // "HH:MM" in Berlin
  const [h, m] = hhmm.split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
}

export interface CalMeta {
  name: string;
  color: string;
}
export function buildCalMeta(
  calendars: { id: string; name?: string; title?: string; color?: string }[],
): Map<string, CalMeta> {
  const map = new Map<string, CalMeta>();
  calendars.forEach((c, i) => {
    const name = c.name ?? c.title ?? c.id;
    const color = HEX.test(c.color ?? '') ? (c.color as string) : PALETTE[i % PALETTE.length]!;
    map.set(c.id, { name, color });
  });
  return map;
}

// Farbe eines Events: Feiertag/Geburtstag bekommen semantische Töne, sonst die
// Kalenderfarbe, sonst ein neutraler Fallback.
export function eventColor(ev: KalenderEvent, calMeta: Map<string, CalMeta>): string {
  if (isHolidayEvent(ev)) return '#cf8524';
  if (isBirthdayEvent(ev)) return '#e0639a';
  const cid = ev.calendar_id;
  if (cid && calMeta.get(cid)) return calMeta.get(cid)!.color;
  return '#8a8aa0';
}
