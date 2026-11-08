import { env } from '$env/dynamic/private';
import { fail, redirect } from '@sveltejs/kit';
import { backendSecret, kalenderBffFetch, kalenderBffToken } from '$lib/kalender-bff';
import type { Actions, PageServerLoad } from './$types';

/**
 * Urlaub und Zeitkonto (seit 2026-11-07, Entscheide vom 06.11.).
 *
 * Gerechnet wird im nativen Kalender (`backend/urlaub_zeitkonto.py`), hier wird
 * nur angezeigt und eingetragen. So zeigen diese Seite, die App und das native
 * Frontend dieselbe Zahl.
 */
export interface Uebertrag {
  tage: number;
  verfall: string;
  genutzt: number;
  offen: number;
  verfallen: number;
}

export interface Bilanz {
  jahr: number;
  verbraucht: number;
  genommen: number | null;
  geplant: number | null;
  anspruch: number | null;
  rest_nach_plan: number | null;
  uebertrag: Uebertrag | null;
}

export interface Eintrag {
  datum: string;
  tagestyp: string;
  art: 'arbeit' | 'ausgleich' | 'krank_frueher';
  von?: string;
  bis?: string;
  ist: number;
  soll: number;
  abweichung: number;
  notiz?: string;
}

export interface Stunde {
  fach: string;
  von: string;
  bis: string;
}

export interface Stundenplan {
  stunden: Record<string, Stunde[]>;
  ausfall: Record<string, string[]>;
}

export interface Zeitkonto {
  plan: Record<string, { soll: number; pause: number }>;
  saldo: number;
  eintraege: Eintrag[];
}

const ARTEN = ['arbeit', 'ausgleich', 'krank_frueher'];
const TAGESTYPEN = ['urlaub', 'krank', 'arbeit', 'schule', 'frei'];
const UHR = /^([01]\d|2[0-3]):[0-5]\d$/;
const DATUM = /^\d{4}-\d{2}-\d{2}$/;

function ctx(locals: App.Locals): { base: string; token: string } | null {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) return null;
  return { base: env.KALENDER_BFF_BASE_URL, token: kalenderBffToken(locals.user, backendSecret()) };
}

/** Die Meldung des nativen Dienstes statt der ganzen Fehlerkette (wie in `orte`). */
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

/** „8:00", „5:30", „8" oder „5,5" zu Minuten. */
function minuten(text: string): number | null {
  const t = text.trim();
  const m = /^(\d{1,2}):([0-5]\d)$/.exec(t);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  const d = Number(t.replace(',', '.'));
  return t !== '' && Number.isFinite(d) ? Math.round(d * 60) : null;
}

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const c = ctx(locals);
  if (!c) redirect(303, '/');
  const jahr = Number(url.searchParams.get('jahr')) || new Date().getFullYear();
  let bilanz: Bilanz | null = null;
  let konto: Zeitkonto | null = null;
  let plan: Stundenplan | null = null;
  let fehler: string | null = null;
  const tag = DATUM.test(url.searchParams.get('tag') ?? '') ? url.searchParams.get('tag')! : null;
  try {
    [bilanz, konto, plan] = await Promise.all([
      kalenderBffFetch<Bilanz>(c.base, `/api/day-type/urlaub-bilanz?jahr=${jahr}`, c.token, fetch),
      kalenderBffFetch<Zeitkonto>(c.base, '/api/day-type/zeitkonto', c.token, fetch),
      kalenderBffFetch<Stundenplan>(c.base, '/api/day-type/stundenplan', c.token, fetch),
    ]);
  } catch (err) {
    fehler = fehlerText(err);
  }
  return { jahr, bilanz, konto, plan, tag, fehler };
};

export const actions: Actions = {
  /**
   * Tagestyp fuer einen Tag oder Zeitraum, wie in der App (Gleichstand
   * 2026-11-07). Ein einzelner Tag ist ein Zeitraum von einem Tag; der zaehlt
   * dann auch am Wochenende, sonst liesse sich ein Samstag nie setzen.
   * `frei` leert den Tagestyp (siehe DayTypeRangeIn im kalender-bff).
   */
  tagestyp: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const von = String(fd.get('von') ?? '');
    const bis = String(fd.get('bis') ?? '') || von;
    const typ = String(fd.get('typ') ?? '');
    if (!DATUM.test(von) || !DATUM.test(bis)) return fail(400, { fehler: 'Datum fehlt.' });
    if (bis < von) return fail(400, { fehler: 'Das Ende liegt vor dem Anfang.' });
    if (!TAGESTYPEN.includes(typ)) return fail(400, { fehler: 'Unbekannter Tagestyp.' });
    try {
      await kalenderBffFetch(c.base, '/api/day-type/set-range', c.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          von,
          bis,
          day_type: typ,
          half: fd.get('halb') === 'on',
          nur_wochentage: von !== bis && fd.get('wochenende') !== 'on',
        }),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { gespeichert: 'Tagestyp' };
  },
  anspruch: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const roh = String(fd.get('anspruch') ?? '').trim().replace(',', '.');
    const anspruch = roh === '' ? null : Number(roh);
    if (anspruch !== null && (!Number.isFinite(anspruch) || anspruch < 0 || anspruch > 100)) {
      return fail(400, { fehler: 'Anspruch zwischen 0 und 100 Tagen.' });
    }
    try {
      await kalenderBffFetch(c.base, '/api/day-type/urlaub-einstellung', c.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anspruch }),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { gespeichert: 'Anspruch' };
  },

  eintragen: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const tag = String(fd.get('tag') ?? '');
    const art = String(fd.get('art') ?? 'arbeit');
    if (!DATUM.test(tag)) return fail(400, { fehler: 'Tag fehlt.' });
    if (!ARTEN.includes(art)) return fail(400, { fehler: 'Unbekannte Art.' });
    const eingabe: Record<string, string> = { art };
    if (art === 'arbeit') {
      const von = String(fd.get('von') ?? '');
      const bis = String(fd.get('bis') ?? '');
      if (!UHR.test(von) || !UHR.test(bis) || bis <= von) return fail(400, { fehler: 'Ende muss nach Beginn liegen.' });
      eingabe.von = von;
      eingabe.bis = bis;
    }
    const notiz = String(fd.get('notiz') ?? '').trim().slice(0, 200);
    if (notiz) eingabe.notiz = notiz;
    try {
      await kalenderBffFetch(c.base, `/api/day-type/zeitkonto/eintrag/${tag}`, c.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(eingabe),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { gespeichert: 'Eintrag' };
  },

  loeschen: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const tag = String((await request.formData()).get('tag') ?? '');
    if (!DATUM.test(tag)) return fail(400, { fehler: 'Tag fehlt.' });
    try {
      await kalenderBffFetch(c.base, `/api/day-type/zeitkonto/eintrag/${tag}`, c.token, fetch, { method: 'DELETE' });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { gespeichert: 'Gelöscht' };
  },

  stundenplan: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const stunden: Record<string, Stunde[]> = {};
    for (let wt = 0; wt < 7; wt++) {
      const zeilen = String(fd.get(`tag-${wt}`) ?? '').split('\n').map((z) => z.trim()).filter(Boolean);
      stunden[String(wt)] = [];
      for (const z of zeilen) {
        // „08:00-09:30 Deutsch" (auch „8:00 - 9:30 Deutsch")
        const m = /^(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\s+(.+)$/.exec(z);
        if (!m) return fail(400, { fehler: `Zeile nicht lesbar: „${z}“. Form: 08:00-09:30 Deutsch` });
        const u = (h: string, mi: string) => `${h.padStart(2, '0')}:${mi}`;
        const [, vh = '', vm = '', bh = '', bm = '', fach = ''] = m;
        stunden[String(wt)]!.push({ von: u(vh, vm), bis: u(bh, bm), fach: fach.slice(0, 60) });
      }
    }
    try {
      await kalenderBffFetch(c.base, '/api/day-type/stundenplan', c.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stunden }),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { gespeichert: 'Stundenplan' };
  },

  ausfall: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const datum = String(fd.get('datum') ?? '');
    const von = String(fd.get('von') ?? '');
    if (!DATUM.test(datum) || !UHR.test(von)) return fail(400, { fehler: 'Stunde fehlt.' });
    try {
      const r = await kalenderBffFetch<{ zeiten: { von: string; bis: string } | null; alle_ausgefallen: boolean; schultag: boolean }>(
        c.base, '/api/day-type/stundenplan/ausfall', c.token, fetch, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ datum, von, ausgefallen: fd.get('ausgefallen') === 'true' }),
        });
      return { ausfallErgebnis: r };
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
  },

  plan: async ({ locals, fetch, request }) => {
    const c = ctx(locals);
    if (!c) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const tage = [];
    for (let wt = 0; wt < 7; wt++) {
      const soll = minuten(String(fd.get(`soll-${wt}`) ?? ''));
      const pause = Number(String(fd.get(`pause-${wt}`) ?? ''));
      if (soll === null || soll < 0 || soll > 1440 || !Number.isInteger(pause) || pause < 0 || pause > 1440) {
        return fail(400, { fehler: `Wochentag ${wt + 1}: Wert unlesbar.` });
      }
      tage.push({ wochentag: wt, soll, pause });
    }
    try {
      await kalenderBffFetch(c.base, '/api/day-type/zeitkonto/plan', c.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tage }),
      });
    } catch (err) {
      return fail(400, { fehler: fehlerText(err) });
    }
    return { gespeichert: 'Plan' };
  },
};
