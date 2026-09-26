import { fail } from '@sveltejs/kit';
import { api } from '$lib/projectdeck-api';
import type { Project, WeeklyFocus } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { projects: [], focus: null };
  const [projects, focus] = await Promise.all([
    api<Project[]>(locals.user, '/api/projects', fetch),
    api<WeeklyFocus>(locals.user, '/api/focus', fetch),
  ]);
  return { projects, focus };
};

export const actions: Actions = {
  save: async ({ request, locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'no session' });
    const f = await request.formData();
    const project_ids = (f.getAll('focus') as string[]).map(Number);
    const maintenance_project_ids = (f.getAll('maint') as string[]).map(Number);
    if (project_ids.length > 3) {
      return fail(422, { error: 'Maximal 3 Hauptfokus-Projekte pro Woche.' });
    }
    try {
      await api(locals.user, '/api/focus', fetch, {
        method: 'PUT',
        body: JSON.stringify({ project_ids, maintenance_project_ids }),
      });
    } catch (err) {
      return fail(502, { error: String(err) });
    }
    return { ok: true };
  },
};
