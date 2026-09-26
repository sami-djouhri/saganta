import { fail, redirect } from '@sveltejs/kit';
import { api } from '$lib/projectdeck-api';
import type { Project } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  if (!locals.user) return { projects: [] };
  const qs = new URLSearchParams();
  for (const k of ['type', 'status', 'client_id']) {
    const v = url.searchParams.get(k);
    if (v) qs.set(k, v);
  }
  const gefiltert = qs.toString() !== '';
  const projects = await api<Project[]>(
    locals.user,
    `/api/projects${gefiltert ? `?${qs}` : ''}`,
    fetch,
  );
  // Die Filterleiste nennt je Wert die Anzahl. Sobald ein Filter greift, kennt
  // `projects` nur noch die Treffer, und die Leiste zeigte neben jedem anderen
  // Eintrag eine 0. Deshalb bei aktivem Filter einmal die ganze Liste dazu;
  // ohne Filter sind beide dasselbe und es bleibt bei einem Aufruf.
  const alleProjekte = gefiltert
    ? await api<Project[]>(locals.user, '/api/projects', fetch)
    : projects;
  return {
    projects,
    alleProjekte,
    filter: {
      type: url.searchParams.get('type') ?? '',
      status: url.searchParams.get('status') ?? '',
    },
  };
};

export const actions: Actions = {
  create: async ({ request, locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'no session' });
    const form = await request.formData();
    const name = String(form.get('name') ?? '').trim();
    if (!name) return fail(400, { error: 'Name erforderlich.' });
    const body: Record<string, unknown> = {
      name,
      type: form.get('type') || 'private',
      status: form.get('status') || 'idea',
      visibility: form.get('visibility') || 'private',
      priority: Number(form.get('priority') ?? 3),
    };
    const na = String(form.get('next_action') ?? '').trim();
    if (na) body.next_action = na;
    let created: Project;
    try {
      created = await api<Project>(locals.user, '/api/projects', fetch, {
        method: 'POST',
        body: JSON.stringify(body),
      });
    } catch (err) {
      return fail(502, { error: String(err) });
    }
    redirect(303, `/projekte/${created.slug}`);
  },
};
