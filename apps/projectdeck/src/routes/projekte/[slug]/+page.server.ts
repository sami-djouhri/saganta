import { error, fail } from '@sveltejs/kit';
import { notizDazuAusFormular, notizenZuEinem } from '@saganta/notizen-anschluss';
import { notizAnschluss } from '$lib/server/notizen';
import { api } from '$lib/projectdeck-api';
import type {
  AISuggest,
  Asset,
  Milestone,
  Project,
  Readiness,
  Aufgabe,
  Review,
} from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

async function resolve(locals: App.Locals, fetch: typeof globalThis.fetch, slug: string) {
  return api<Project>(locals.user!, `/api/projects/by-slug/${slug}`, fetch);
}

export const load: PageServerLoad = async ({ locals, fetch, params }) => {
  if (!locals.user) throw error(401, 'no session');
  let project: Project;
  try {
    project = await resolve(locals, fetch, params.slug);
  } catch {
    throw error(404, 'Projekt nicht gefunden');
  }
  const u = locals.user;
  const base = `/api/projects/${project.id}`;
  // Aufgaben liegen im Aufgaben-Dienst; offene und erledigte sind dort zwei
  // Abfragen. Faellt der Dienst aus, bleibt die Projektansicht bedienbar und
  // sagt das, statt „Keine Aufgaben" zu behaupten.
  const aufgabenLaden = Promise.all([
    api<Aufgabe[]>(u, `${base}/aufgaben`, fetch),
    api<Aufgabe[]>(u, `${base}/aufgaben?erledigte=true`, fetch),
  ]).then(
    ([offen, erledigt]) => ({ aufgaben: [...offen, ...erledigt], aufgabenFehlen: false }),
    () => ({ aufgaben: [] as Aufgabe[], aufgabenFehlen: true }),
  );
  const [{ aufgaben, aufgabenFehlen }, assets, milestones, reviews, readiness, shutdown] = await Promise.all([
    aufgabenLaden,
    api<Asset[]>(u, `${base}/assets`, fetch),
    api<Milestone[]>(u, `${base}/milestones`, fetch),
    api<Review[]>(u, `${base}/reviews`, fetch),
    api<Readiness>(u, `${base}/readiness`, fetch),
    api<Readiness>(u, `${base}/shutdown`, fetch),
  ]);
  // Notizen zum Projekt. Fail-soft im Anschluss: faellt die notizen-api aus,
  // fehlt der Block, und die Projektansicht bleibt vollstaendig bedienbar.
  const notizen = await notizenZuEinem('projekt', project.slug, notizAnschluss(locals, fetch));
  return {
    project,
    aufgaben,
    aufgabenFehlen,
    assets,
    milestones,
    reviews,
    readiness,
    shutdown,
    notizen,
  };
};

function num(v: FormDataEntryValue | null): number | undefined {
  const n = Number(v);
  return v === null || v === '' || Number.isNaN(n) ? undefined : n;
}

export const actions: Actions = {
  /**
   * Notiz zum Projekt: neu anlegen oder eine vorhandene anhaengen.
   *
   * Der Knopf sitzt am Projekt und nicht in den Notizen, weil genau das der
   * Grund war, warum die Verknuepfungen seit ihrem Bau null Mal benutzt wurden.
   * `ref` ist der **Slug**, siehe `lib/server/notizen.ts`.
   */
  notizDazu: async ({ request, locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const erg = await notizDazuAusFormular(await request.formData(), notizAnschluss(locals, fetch));
    if (!erg.ok) return fail(400, { notizFehler: erg.fehler });
    return { notiz: erg.notiz };
  },

  updateProject: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    const body: Record<string, unknown> = {};
    for (const [k, v] of f.entries()) {
      if (v === '') continue;
      if (k === '_has_auto_schedule' || k === 'can_auto_schedule') continue; // s.u. separat
      if (['priority', 'weekly_time_budget_minutes', 'review_interval_days'].includes(k))
        body[k] = Number(v);
      else body[k] = v;
    }
    // can_auto_schedule ist eine Checkbox, "nicht gesendet" ist mehrdeutig (unchecked
    // ODER Feld gar nicht im Formular: eingeklapptes "Erweitert" bzw. eines der anderen
    // updateProject-Teilformulare). Nur setzen, wenn der Marker beweist, dass die Checkbox
    // im Formular war, sonst schalteten Teil-Speicherungen can_auto_schedule still auf false.
    if (f.has('_has_auto_schedule')) {
      body.can_auto_schedule = f.get('can_auto_schedule') === 'on';
    }
    try {
      await api(locals.user!, `/api/projects/${p.id}`, fetch, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
    } catch (err) {
      return fail(502, { error: String(err) });
    }
    return { ok: true };
  },

  addTask: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    const titel = String(f.get('titel') ?? '').trim();
    if (!titel) return fail(400, { error: 'Titel fehlt' });
    const prioritaet = String(f.get('prioritaet') ?? 'mittel');
    try {
      await api(locals.user!, `/api/projects/${p.id}/aufgaben`, fetch, {
        method: 'POST',
        body: JSON.stringify({
          titel,
          dauer_min: num(f.get('dauer_min')),
          prioritaet: ['hoch', 'mittel', 'niedrig'].includes(prioritaet) ? prioritaet : 'mittel',
          faellig: f.get('faellig') || null,
        }),
      });
    } catch (err) {
      return fail(502, { error: String(err) });
    }
    return { ok: true };
  },

  taskStatus: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    const ziel = f.get('erledigt') === 'ja' ? 'erledigt' : 'offen';
    try {
      await api(locals.user!, `/api/projects/${p.id}/aufgaben/${f.get('id')}/${ziel}`, fetch, {
        method: 'POST',
      });
    } catch (err) {
      return fail(502, { error: String(err) });
    }
    return { ok: true };
  },

  deleteTask: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    try {
      await api(locals.user!, `/api/projects/${p.id}/aufgaben/${f.get('id')}`, fetch, {
        method: 'DELETE',
      });
    } catch (err) {
      return fail(502, { error: String(err) });
    }
    return { ok: true };
  },

  addAsset: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    await api(locals.user!, `/api/projects/${p.id}/assets`, fetch, {
      method: 'POST',
      body: JSON.stringify({
        type: f.get('type') || 'link',
        label: String(f.get('label') ?? '').trim() || 'Asset',
        value: String(f.get('value') ?? '').trim(),
        url: f.get('url') || null,
      }),
    });
    return { ok: true };
  },

  deleteAsset: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    await api(locals.user!, `/api/projects/${p.id}/assets/${f.get('id')}`, fetch, {
      method: 'DELETE',
    });
    return { ok: true };
  },

  addMilestone: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    await api(locals.user!, `/api/projects/${p.id}/milestones`, fetch, {
      method: 'POST',
      body: JSON.stringify({
        title: String(f.get('title') ?? '').trim() || 'Milestone',
        target_date: f.get('target_date') || null,
      }),
    });
    return { ok: true };
  },

  // Erreicht-Markieren und Loeschen fehlten bis zum 2026-10-16 vollstaendig.
  // Ein Meilenstein war damit eine Einbahnstrasse: `status` blieb fuer immer
  // `open`, DELETE gab es nur im Backend. Seit derselben Runde zaehlt das
  // Deadline-Center ueberfaellige Meilensteine -- eine Warnung, die man nicht
  // abstellen kann, wird ignoriert.
  toggleMilestone: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    // Der Knopf schickt den GEWUENSCHTEN Zustand mit, nicht den aktuellen:
    // sonst entscheidet die Reihenfolge zweier Klicks, was am Ende steht.
    const ziel = String(f.get('status') ?? 'erreicht');
    await api(locals.user!, `/api/projects/${p.id}/milestones/${f.get('id')}`, fetch, {
      method: 'PATCH',
      body: JSON.stringify({ status: ziel }),
    });
    return { ok: true };
  },

  deleteMilestone: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    await api(locals.user!, `/api/projects/${p.id}/milestones/${f.get('id')}`, fetch, {
      method: 'DELETE',
    });
    return { ok: true };
  },

  addReview: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    await api(locals.user!, `/api/projects/${p.id}/reviews`, fetch, {
      method: 'POST',
      body: JSON.stringify({
        decision: String(f.get('decision') ?? 'keep_active'),
        notes: f.get('notes') || null,
        next_action: f.get('next_action') || null,
        new_status: f.get('new_status') || null,
        new_priority: num(f.get('new_priority')) ?? null,
      }),
    });
    return { ok: true };
  },

  saveReadiness: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    const items: Record<string, { done: boolean; note: string | null }> = {};
    for (const key of f.getAll('item_key') as string[]) {
      items[key] = { done: f.get(`done_${key}`) === 'on', note: null };
    }
    await api(locals.user!, `/api/projects/${p.id}/readiness`, fetch, {
      method: 'PUT',
      body: JSON.stringify({ items }),
    });
    return { ok: true };
  },

  saveShutdown: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    const items: Record<string, { done: boolean; note: string | null }> = {};
    for (const key of f.getAll('item_key') as string[]) {
      items[key] = { done: f.get(`done_${key}`) === 'on', note: null };
    }
    await api(locals.user!, `/api/projects/${p.id}/shutdown`, fetch, {
      method: 'PUT',
      body: JSON.stringify({ items }),
    });
    return { ok: true };
  },

  ai: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    const kind = String(f.get('kind') ?? 'review');
    const path =
      kind === 'shutdown'
        ? 'ai/shutdown'
        : kind === 'deadline'
          ? 'ai/deadline-plan'
          : 'ai/review';
    try {
      const res = await api<AISuggest>(locals.user!, `/api/projects/${p.id}/${path}`, fetch);
      return { ok: true, ai: res };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },
};
