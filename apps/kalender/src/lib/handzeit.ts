/**
 * Zeit von Hand: Starten, Stoppen, nachtraeglich abhaken (Web seit 2026-11-08,
 * Gleichstand-Luecke 6).
 *
 * Die Regeln sind eine Uebersetzung von `feature-kalender/.../domain/Handzeit.kt`
 * und `sitzungsSchritte` in `SitzungBlatt.kt`. Wer dort einen Knopf aendert,
 * aendert ihn hier mit, sonst bietet das Web etwas an, das die App nicht kennt.
 *
 * Alle Zeiten sind Berliner Wanduhr ohne Zone (`2026-11-08T14:00`). `new Date()`
 * liest so einen Text als Ortszeit des Browsers; deshalb laeuft diese Rechnung
 * nur im Browser, nie im SSR-Knoten (der laeuft auf UTC).
 */
import type { HabitSession, KalenderEvent } from './kalender-bff';

export interface LaufenderTimer {
  id: string;
  titel: string | null;
  art: string | null;
  seit: string;
  bezug_typ: string | null;
  bezug_id: string | null;
}

export interface Beleg {
  verweis: string;
  start: string;
  ende: string;
  titel?: string | null;
}

export type Schritt = 'starten' | 'stoppen' | 'erledigt';

/** So frueh vor Beginn bietet ein Termin „Starten" an. */
export const STARTEN_VORLAUF_MINUTEN = 15;

export function wanduhr(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso.slice(0, 19));
  return Number.isNaN(d.getTime()) ? null : d;
}

const z = (n: number) => String(n).padStart(2, '0');

/** Fuer `<input type="datetime-local">` und den Dienst: `2026-11-08T14:00`. */
export function minutengenau(d: Date): string {
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`;
}

export const verweisAuf = (typ: string, id: string) => `${typ}:${id}`;

export function laeuftFuer(timer: LaufenderTimer | null, typ: string, id: string): boolean {
  return timer != null && timer.bezug_typ === typ && timer.bezug_id === id;
}

const minus = (d: Date, min: number) => new Date(d.getTime() - min * 60_000);

/**
 * Knoepfe eines Termins. Ganztaegiges, Tagestypen, Feiertage und Geburtstage
 * bekommen keine; ein schon belegter Termin auch nicht. „Erledigt" schon ab
 * Beginn: wer frueher fertig ist, soll nicht bis zum geplanten Ende warten.
 */
export function terminSchritte(
  ev: KalenderEvent,
  jetzt: Date,
  belegt: boolean,
  timer: LaufenderTimer | null,
): Schritt[] {
  const cid = ev.calendar_id ?? '';
  if (ev.all_day || /^daytype-/.test(cid) || /^system-geburtstage/.test(cid)) return [];
  if (laeuftFuer(timer, 'event', ev.id)) return ['stoppen'];
  if (belegt) return [];
  const beginn = wanduhr(ev.start_at ?? ev.start);
  if (!beginn) return [];
  const ende = wanduhr(ev.end_at ?? ev.end) ?? new Date(beginn.getTime() + 3_600_000);
  const schritte: Schritt[] = [];
  if (jetzt >= minus(beginn, STARTEN_VORLAUF_MINUTEN) && jetzt < ende) schritte.push('starten');
  if (jetzt >= beginn) schritte.push('erledigt');
  return schritte;
}

/**
 * Knoepfe einer Sitzung, beschraenkt auf die Zeit-Schritte. Annehmen und
 * Verwerfen stehen schon im Block Gewohnheiten.
 *
 * Auch eine vergangene „verworfene" Sitzung ist abhakbar: der Dienst setzt
 * jede vergangene, nicht angenommene Sitzung von selbst auf verworfen, auch
 * wenn sie stattgefunden hat. Genau das soll der Haken richtigstellen.
 */
export function sitzungsSchritte(
  s: HabitSession,
  jetzt: Date,
  belegt: boolean,
  timer: LaufenderTimer | null,
): Schritt[] {
  if (laeuftFuer(timer, 'session', s.id)) return ['stoppen'];
  const beginn = wanduhr(s.start);
  const ende = wanduhr(s.end);
  const laeuft = beginn != null && ende != null && jetzt >= beginn && jetzt < ende;
  const vorbei = ende != null && jetzt >= ende;
  const abhakbar = !belegt && s.status !== 'completed' && s.status !== 'cancelled';
  if (vorbei) return abhakbar ? ['erledigt'] : [];
  if (s.status === 'pending') return ['starten'];
  if (s.status === 'accepted' && laeuft) return abhakbar ? ['starten', 'erledigt'] : ['starten'];
  if (s.status === 'accepted') return ['starten'];
  return [];
}

/**
 * Vorbelegung fuer „Erledigt": die geplante Zeit, aber nie ueber jetzt hinaus.
 * Der Dienst lehnt ein Ende in der Zukunft ab; wer um 9:40 einen Termin
 * 9:00 bis 10:00 abhakt, bekaeme mit der geplanten Zeit einen Fehler.
 */
export function hakenVorlage(start: string | undefined, ende: string | undefined, jetzt: Date) {
  const beginn = wanduhr(start) ?? minus(jetzt, 60);
  let schluss = wanduhr(ende) ?? new Date(beginn.getTime() + 3_600_000);
  if (schluss > jetzt) schluss = jetzt;
  const anfang = beginn < schluss ? beginn : minus(schluss, 30);
  return { start: minutengenau(anfang), ende: minutengenau(schluss) };
}

/** „seit 14:03 · 23 Min." */
export function laufzeitText(timer: LaufenderTimer, jetzt: Date): string {
  const seit = wanduhr(timer.seit);
  if (!seit) return 'läuft';
  const min = Math.max(1, Math.floor((jetzt.getTime() - seit.getTime()) / 60_000));
  const dauer = min < 60 ? `${min} Min.` : `${Math.floor(min / 60)} Std.${min % 60 ? ` ${min % 60} Min.` : ''}`;
  return `seit ${z(seit.getHours())}:${z(seit.getMinutes())} · ${dauer}`;
}

/** Prueft den Haken vor dem Absenden; `null` heisst in Ordnung. */
export function hakenFehler(start: string, ende: string, jetzt: Date): string | null {
  const b = wanduhr(start);
  const e = wanduhr(ende);
  if (!b) return 'Beginn fehlt.';
  if (!e) return 'Ende fehlt.';
  if (e <= b) return 'Das Ende muss nach dem Beginn liegen.';
  if (e.getTime() > jetzt.getTime() + 60_000) return 'Das Ende liegt in der Zukunft.';
  return null;
}
