import { env } from '$env/dynamic/private';
import { fail, redirect } from '@sveltejs/kit';
import { backendSecret, kalenderBffFetch, kalenderBffToken } from '$lib/kalender-bff';
import type { Actions, PageServerLoad } from './$types';

/**
 * Orte: Zuhause, Arbeit, Schule, Einkauf (seit 2026-11-01).
 *
 * Aus ihnen rechnet der native Kalender Arbeitsweg, Heimweg und die Wege zu
 * Terminen. Nach jeder Änderung wird neu geplant (`/api/places/wege/planen`),
 * sonst wirkte ein Umzug erst am nächsten Morgen und nur für Arbeit und Heimweg.
 */
export interface Ort {
  id: string;
  name: string;
  kind: 'zuhause' | 'arbeit' | 'schule' | 'einkauf' | 'sonstiges';
  address: string | null;
  lat: number | null;
  lon: number | null;
}

export interface WegePlan {
  hinwege: number;
  heimwege: number;
  terminwege: number;
  fehler: number;
  nahverkehr_gestoert: boolean;
}

const ARTEN = ['zuhause', 'arbeit', 'schule', 'einkauf', 'sonstiges'];

function ctx(locals: App.Locals): { base: string; token: string } | null {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) return null;
  return { base: env.KALENDER_BFF_BASE_URL, token: kalenderBffToken(locals.user, backendSecret()) };
}

/**
 * Die Meldung des nativen Dienstes statt der ganzen Fehlerkette.
 *
 * Sie kommt doppelt verpackt an: `kalender-bff 409 …: {"detail":"kalender
 * error: {\"detail\":\"„Daheim“ ist bereits als Zuhause eingetragen…\"}"}`.
 */
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

async function wegePlanen(c: { base: string; token: string }, fetcher: typeof fetch): Promise<WegePlan | null> {
  try {
    return await kalenderBffFetch<WegePlan>(c.base, '/api/places/wege/planen?tage=7', c.token, fetcher, {
      method: 'POST',
    });
  } catch {
    return null;
  }
}

export const load: PageServerLoad = async ({ locals, fetch }) => {
  const c = ctx(locals);
  if (!c) redirect(303, '/');
  let orte: Ort[] = [];
  let fehler: string | null = null;
  try {
    orte = await kalenderBffFetch<Ort[]>(c.base, '/api/places', c.token, fetch);
  } catch (err) {
    fehler = fehlerText(err);
  }
  return { orte, fehler };
};

export const actions: Actions = {
  speichern: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const kind = String(fd.get('kind') ?? 'sonstiges');
    const name = String(fd.get('name') ?? '').trim();
    const address = String(fd.get('address') ?? '').trim() || null;
    const zahl = (k: string) => {
      const v = String(fd.get(k) ?? '');
      return v === '' ? null : Number(v);
    };
    // Lage nur, wenn sie zur Adresse gehört (aus einem Vorschlag gewählt).
    const lat = address ? zahl('lat') : null;
    const lon = address ? zahl('lon') : null;
    if (!name) return fail(400, { fehler: 'Name fehlt.' });
    if (!ARTEN.includes(kind)) return fail(400, { fehler: 'Unbekannte Art.' });
    try {
      await kalenderBffFetch(c.base, id ? `/api/places/${encodeURIComponent(id)}` : '/api/places', c.token, fetch, {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, kind, address, lat, lon }),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { gespeichert: name, plan: await wegePlanen(c, fetch) };
  },

  loeschen: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const id = String((await request.formData()).get('id') ?? '');
    if (!id) return fail(400, { fehler: 'Ort fehlt.' });
    try {
      await kalenderBffFetch(c.base, `/api/places/${encodeURIComponent(id)}`, c.token, fetch, { method: 'DELETE' });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { geloescht: true, plan: await wegePlanen(c, fetch) };
  },
};
