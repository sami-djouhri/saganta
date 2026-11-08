import { fail } from '@sveltejs/kit';
import type { Kontakt } from '$lib/typen';
import { dienst, dienstCtx, ursache } from '$lib/server/dienst';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const ctx = dienstCtx(locals);
  const geloescht = url.searchParams.get('geloescht');
  if (!ctx) return { kontakte: [] as Kontakt[], geloescht, fehler: 'Der Kontakte-Dienst ist nicht eingerichtet.' };
  try {
    return { kontakte: await dienst<Kontakt[]>(ctx, '/api/papierkorb', fetch), geloescht, fehler: null };
  } catch (err) {
    return { kontakte: [] as Kontakt[], geloescht, fehler: ursache(err) };
  }
};

export const actions: Actions = {
  wiederherstellen: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const id = String((await request.formData()).get('id') ?? '');
    try {
      const k = await dienst<Kontakt>(ctx, `/api/papierkorb/${encodeURIComponent(id)}/wiederherstellen`, fetch, { method: 'POST' });
      return { zurueck: k.name };
    } catch (err) {
      return fail(502, { fehler: ursache(err) });
    }
  },
  endgueltig: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const id = String((await request.formData()).get('id') ?? '');
    try {
      await dienst(ctx, `/api/papierkorb/${encodeURIComponent(id)}`, fetch, { method: 'DELETE' });
      return { weg: true };
    } catch (err) {
      return fail(502, { fehler: ursache(err) });
    }
  },
};
