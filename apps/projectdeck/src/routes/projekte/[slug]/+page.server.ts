import { error, fail } from '@sveltejs/kit';
import { api } from '$lib/projectdeck-api';
import type {
  AISuggest,
  Asset,
  Milestone,
  Project,
  Readiness,
  Review,
  Task,
  TimeBlock,
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
  const [tasks, assets, milestones, reviews, readiness, shutdown, timeBlocks] = await Promise.all([
    api<Task[]>(u, `${base}/tasks`, fetch),
    api<Asset[]>(u, `${base}/assets`, fetch),
    api<Milestone[]>(u, `${base}/milestones`, fetch),
    api<Review[]>(u, `${base}/reviews`, fetch),
    api<Readiness>(u, `${base}/readiness`, fetch),
    api<Readiness>(u, `${base}/shutdown`, fetch),
    api<TimeBlock[]>(u, `/api/projects/${project.id}/time-blocks`, fetch).catch(() => []),
  ]);
  return { project, tasks, assets, milestones, reviews, readiness, shutdown, timeBlocks };
};

function num(v: FormDataEntryValue | null): number | undefined {
  const n = Number(v);
  return v === null || v === '' || Number.isNaN(n) ? undefined : n;
}

export const actions: Actions = {
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
    const title = String(f.get('title') ?? '').trim();
    if (!title) return fail(400, { error: 'Titel fehlt' });
    await api(locals.user!, `/api/projects/${p.id}/tasks`, fetch, {
      method: 'POST',
      body: JSON.stringify({
        title,
        estimated_minutes: num(f.get('estimated_minutes')),
        priority: num(f.get('priority')) ?? 3,
        can_schedule: f.get('can_schedule') === 'on',
        deadline: f.get('deadline') || null,
      }),
    });
    return { ok: true };
  },

  taskStatus: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    await api(locals.user!, `/api/projects/${p.id}/tasks/${f.get('id')}`, fetch, {
      method: 'PATCH',
      body: JSON.stringify({ status: f.get('status') }),
    });
    return { ok: true };
  },

  deleteTask: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    await api(locals.user!, `/api/projects/${p.id}/tasks/${f.get('id')}`, fetch, {
      method: 'DELETE',
    });
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

  plan: async ({ locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    try {
      const res = await api<{ detail: string; scheduled_blocks?: number }>(
        locals.user!,
        `/api/projects/${p.id}/plan`,
        fetch,
        { method: 'POST' },
      );
      return { ok: true, planResult: res.detail, planScheduled: res.scheduled_blocks ?? 0 };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  worklog: async ({ request, locals, fetch, params }) => {
    const p = await resolve(locals, fetch, params.slug);
    const f = await request.formData();
    const actual = num(f.get('actual_minutes'));
    if (actual === undefined || actual < 0) return fail(400, { error: 'Minuten fehlen' });
    const body: Record<string, unknown> = {
      actual_minutes: actual,
      completed: f.get('completed') === 'on',
    };
    const cev = String(f.get('calendar_event_id') ?? '').trim();
    const tid = num(f.get('task_id'));
    if (cev) body.calendar_event_id = cev;
    if (tid !== undefined) body.task_id = tid;
    try {
      await api(locals.user!, `/api/projects/${p.id}/worklog`, fetch, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      return { ok: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
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
