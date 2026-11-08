import { env } from '$env/dynamic/private';
import { fail, redirect } from '@sveltejs/kit';
import { backendSecret, kalenderBffFetch, kalenderBffToken } from '$lib/kalender-bff';
import type { Actions, PageServerLoad } from './$types';

/**
 * Gewohnheiten anlegen, aendern, pausieren, loeschen (seit 2026-11-08,
 * Gleichstand-Luecke 2). Vorher ging das nur in der App; das Web zeigte
 * Fortschritt und Sitzungen, konnte aber keine Gewohnheit anlegen.
 *
 * Geplant wird im nativen Kalender: jede Aenderung laesst dort den Scheduler
 * die Wochen neu belegen. Hier wird nur eingetragen.
 */
export interface Gewohnheit {
  id: string;
  name: string;
  color: string;
  category: string;
  target_hours_per_week: number;
  session_duration_minutes: number;
  weekday_start: string;
  weekday_end: string;
  weekend_start: string;
  weekend_end: string;
  active: boolean;
  learning_mode: boolean;
  focus_block_minutes: number;
  break_minutes: number;
}

/** Muss dem Muster in `kalender/backend/schemas.py` und im kalender-bff gleichen. */
const KATEGORIEN = ['lernen', 'lesen', 'sport', 'hobby', 'sonstige'] as const;

const UHR = /^([01]\d|2[0-3]):[0-5]\d$/;
const FARBE = /^#[0-9a-fA-F]{6}$/;

function ctx(locals: App.Locals): { base: string; token: string } | null {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) return null;
  return { base: env.KALENDER_BFF_BASE_URL, token: kalenderBffToken(locals.user, backendSecret()) };
}

/** Die Meldung des nativen Dienstes statt der ganzen Fehlerkette (wie in `konten`). */
function fehlerText(err: unknown): string {
  let rest = String(err);
  for (let i = 0; i < 3; i++) {
    const anfang = rest.indexOf('{');
    if (anfang < 0) break;
    try {
      const detail = JSON.parse(rest.slice(anfang)).detail;
      if (typeof detail !== 'string') break;
      rest = detail.replace(/^kalender error:\s*/, '');
      if (!rest.startsWith('{')) return rest;
    } catch {
      break;
    }
  }
  return 'Das hat nicht geklappt.';
}

function zahl(fd: FormData, feld: string): number {
  return Number(String(fd.get(feld) ?? '').trim().replace(',', '.'));
}

/**
 * Formular zu Rumpf. `active` und `learning_mode` gehen immer mit: ein nicht
 * angehakter Kasten fehlt im Formular ganz, und ein fehlendes Feld liesse der
 * Dienst unveraendert. So liesse sich der Lernmodus nie wieder abschalten.
 */
function rumpf(fd: FormData): { daten: Record<string, unknown> } | { fehler: string } {
  const name = String(fd.get('name') ?? '').trim();
  if (!name) return { fehler: 'Name fehlt.' };
  const color = String(fd.get('color') ?? '#4a9eff');
  if (!FARBE.test(color)) return { fehler: 'Farbe ungültig.' };
  const category = String(fd.get('category') ?? 'sonstige');
  if (!(KATEGORIEN as readonly string[]).includes(category)) return { fehler: 'Unbekannte Art.' };
  const ziel = zahl(fd, 'target_hours_per_week');
  if (!(ziel > 0 && ziel <= 80)) return { fehler: 'Wochenziel zwischen 0 und 80 Stunden.' };
  const dauer = Math.round(zahl(fd, 'session_duration_minutes'));
  if (!(dauer >= 15 && dauer <= 480)) return { fehler: 'Sitzung zwischen 15 und 480 Minuten.' };

  const zeiten = {
    weekday_start: String(fd.get('weekday_start') ?? ''),
    weekday_end: String(fd.get('weekday_end') ?? ''),
    weekend_start: String(fd.get('weekend_start') ?? ''),
    weekend_end: String(fd.get('weekend_end') ?? ''),
  };
  if (!Object.values(zeiten).every((w) => UHR.test(w))) return { fehler: 'Uhrzeit fehlt.' };
  // HH:MM vergleicht sich als Text richtig.
  if (zeiten.weekday_end <= zeiten.weekday_start) return { fehler: 'Werktags endet das Fenster vor dem Anfang.' };
  if (zeiten.weekend_end <= zeiten.weekend_start) return { fehler: 'Am Wochenende endet das Fenster vor dem Anfang.' };

  const lernmodus = fd.get('learning_mode') === 'on';
  const daten: Record<string, unknown> = {
    name,
    color,
    category,
    target_hours_per_week: ziel,
    session_duration_minutes: dauer,
    ...zeiten,
    learning_mode: lernmodus,
  };
  if (lernmodus) {
    const fokus = Math.round(zahl(fd, 'focus_block_minutes'));
    const pause = Math.round(zahl(fd, 'break_minutes'));
    if (!(fokus >= 5 && fokus <= 120)) return { fehler: 'Fokusblock zwischen 5 und 120 Minuten.' };
    if (!(pause >= 1 && pause <= 30)) return { fehler: 'Pause zwischen 1 und 30 Minuten.' };
    daten.focus_block_minutes = fokus;
    daten.break_minutes = pause;
  }
  return { daten };
}

export const load: PageServerLoad = async ({ locals, fetch }) => {
  const c = ctx(locals);
  if (!c) redirect(303, '/');
  let gewohnheiten: Gewohnheit[] = [];
  let fehler: string | null = null;
  try {
    gewohnheiten = await kalenderBffFetch<Gewohnheit[]>(c.base, '/api/habits', c.token, fetch);
  } catch (err) {
    fehler = fehlerText(err);
  }
  // Aktive zuerst, dann nach Name: pausierte stehen unten und stoeren nicht.
  gewohnheiten.sort((a, b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name, 'de'));
  return { gewohnheiten, fehler };
};

export const actions: Actions = {
  anlegen: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet', id: '' });
    const r = rumpf(await request.formData());
    if ('fehler' in r) return fail(400, { fehler: r.fehler, id: 'neu' });
    try {
      await kalenderBffFetch(c.base, '/api/habits', c.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(r.daten),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err), id: 'neu' });
    }
    return { gespeichert: String(r.daten.name), id: '' };
  },

  aendern: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet', id: '' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'Kennung fehlt.', id: '' });
    const r = rumpf(fd);
    if ('fehler' in r) return fail(400, { fehler: r.fehler, id });
    try {
      await kalenderBffFetch(c.base, `/api/habits/${encodeURIComponent(id)}`, c.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(r.daten),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err), id });
    }
    return { gespeichert: String(r.daten.name), id: '' };
  },

  /** Pausieren statt Loeschen: der Scheduler plant nichts mehr, die erledigten Sitzungen bleiben. */
  pausieren: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet', id: '' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'Kennung fehlt.', id: '' });
    const aktiv = fd.get('aktiv') === '1';
    try {
      await kalenderBffFetch(c.base, `/api/habits/${encodeURIComponent(id)}`, c.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: aktiv }),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err), id });
    }
    return { gespeichert: aktiv ? 'Fortgesetzt' : 'Pausiert', id: '' };
  },

  /** Loescht auch alle vergangenen Sitzungen (CASCADE im Dienst), deshalb fragt die Seite vorher. */
  loeschen: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet', id: '' });
    const id = String((await request.formData()).get('id') ?? '');
    if (!id) return fail(400, { fehler: 'Kennung fehlt.', id: '' });
    try {
      await kalenderBffFetch(c.base, `/api/habits/${encodeURIComponent(id)}`, c.token, fetch, {
        method: 'DELETE',
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err), id });
    }
    return { gespeichert: 'Gelöscht', id: '' };
  },
};
