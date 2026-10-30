import { error, fail, redirect } from '@sveltejs/kit';
import { freigabeBasis } from '$lib/meta';
import { ApiFehler, api } from '$lib/notizen-api';
import type { Freigabe } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');
  try {
    const freigaben = await api<Freigabe[]>(user, '/api/freigaben', fetch);
    return { freigaben, freigabeBasis: freigabeBasis(url.origin) };
  } catch (e) {
    if (e instanceof ApiFehler) error(502, e.detail);
    throw e;
  }
};

export const actions: Actions = {
  widerrufen: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const id = Number((await request.formData()).get('id'));
    try {
      await api(user, `/api/freigaben/${id}`, fetch, { method: 'DELETE' });
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
    return { ok: true };
  },
};
