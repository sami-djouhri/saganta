import { error, fail, redirect } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import type { PapierkorbEintrag } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');
  try {
    const eintraege = await api<PapierkorbEintrag[]>(user, '/api/notizen/papierkorb/liste', fetch);
    return { eintraege };
  } catch (e) {
    if (e instanceof ApiFehler) error(502, e.detail);
    throw e;
  }
};

export const actions: Actions = {
  wiederherstellen: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const id = Number((await request.formData()).get('id'));
    let notiz: { id: number };
    try {
      notiz = await api<{ id: number }>(
        user,
        `/api/notizen/papierkorb/${id}/wiederherstellen`,
        fetch,
        { method: 'POST' },
      );
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
    // Die Notiz bekommt beim Zurueckholen eine neue Kennung: dorthin, wo sie jetzt ist.
    redirect(303, `/notiz/${notiz.id}`);
  },
};
