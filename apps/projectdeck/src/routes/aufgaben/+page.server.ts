import { fail } from '@sveltejs/kit';
import { api } from '$lib/projectdeck-api';
import type { AufgabeUebersicht } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

// Seit dem Umzug (Nov. 2026) aus dem Aufgaben-Dienst. Geoeffnet wird eine
// Aufgabe in Saganta Aufgaben (Entscheid 05.11.); hier wird nur gesehen
// und abgehakt.
export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) return { aufgaben: [] as AufgabeUebersicht[], fehlt: false };
  try {
    const aufgaben = await api<AufgabeUebersicht[]>(locals.user, '/api/aufgaben', fetch);
    return { aufgaben, fehlt: false };
  } catch {
    return { aufgaben: [] as AufgabeUebersicht[], fehlt: true };
  }
};

export const actions: Actions = {
  abhaken: async ({ request, locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const f = await request.formData();
    try {
      await api(locals.user, `/api/projects/${f.get('project_id')}/aufgaben/${f.get('id')}/erledigt`, fetch, {
        method: 'POST',
      });
    } catch (err) {
      return fail(502, { error: String(err) });
    }
    return { ok: true };
  },
};
