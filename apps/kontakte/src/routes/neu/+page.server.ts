import { fail, redirect } from '@sveltejs/kit';
import type { Kontakt } from '$lib/typen';
import { dienst, dienstCtx, ursache } from '$lib/server/dienst';
import { kontaktAus } from '$lib/server/formular';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch }) => {
  const ctx = dienstCtx(locals);
  if (!ctx) return { gruppen: [] as string[] };
  const gruppen = await dienst<string[]>(ctx, '/api/gruppen', fetch).catch(() => [] as string[]);
  return { gruppen };
};

export const actions: Actions = {
  default: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const daten = kontaktAus(await request.formData());
    if (!daten.name) return fail(400, { fehler: 'Ein Name fehlt.' });
    let neu: Kontakt;
    try {
      neu = await dienst<Kontakt>(ctx, '/api/kontakte', fetch, { method: 'POST', json: daten });
    } catch (err) {
      return fail(502, { fehler: ursache(err) });
    }
    redirect(303, `/k/${neu.id}`);
  },
};
