import { error, fail, redirect } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import type { Notiz, NotizKurz, Notizbuch } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');

  const suche = url.searchParams.get('q')?.trim() ?? '';
  const notizbuch = url.searchParams.get('buch');
  const tag = url.searchParams.get('tag');
  const archivierte = url.searchParams.get('archiv') === '1';

  const frage = new URLSearchParams();
  if (suche) frage.set('q', suche);
  if (notizbuch) frage.set('notizbuch_id', notizbuch);
  if (tag) frage.set('tag', tag);
  if (archivierte) frage.set('archivierte', 'true');

  // Nebeneinander, aber einzeln bewertet: eine leere Tag-Liste darf die
  // Notizliste nicht mitreissen.
  const [notizen, notizbuecher, tags] = await Promise.all([
    api<NotizKurz[]>(user, `/api/notizen?${frage}`, fetch).catch((e) => {
      if (e instanceof ApiFehler) error(e.status >= 500 ? 502 : e.status, e.detail);
      throw e;
    }),
    api<Notizbuch[]>(user, '/api/notizbuecher', fetch).catch(() => [] as Notizbuch[]),
    api<string[]>(user, '/api/notizen/tags', fetch).catch(() => [] as string[]),
  ]);

  return { notizen, notizbuecher, tags, suche, notizbuch, tag, archivierte };
};

export const actions: Actions = {
  anlegen: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const buch = felder.get('notizbuch_id');
    try {
      const notiz = await api<Notiz>(user, '/api/notizen', fetch, {
        method: 'POST',
        body: JSON.stringify({
          titel: String(felder.get('titel') ?? '').trim(),
          inhalt: '',
          notizbuch_id: buch ? Number(buch) : null,
        }),
      });
      redirect(303, `/notiz/${notiz.id}`);
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
  },

  notizbuchAnlegen: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const name = String(felder.get('name') ?? '').trim();
    if (!name) return fail(400, { fehler: 'Name fehlt' });
    try {
      await api(user, '/api/notizbuecher', fetch, {
        method: 'POST',
        body: JSON.stringify({ name }),
      });
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
    return { ok: true };
  },

  notizbuchLoeschen: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const id = Number(felder.get('id'));
    if (!id) return fail(400, { fehler: 'Kein Notizbuch angegeben' });
    try {
      await api(user, `/api/notizbuecher/${id}`, fetch, { method: 'DELETE' });
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
    return { ok: true };
  },
};
