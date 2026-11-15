import { error, fail, redirect } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import {
  SAMMEL_AKTIONEN,
  SAMMEL_HOECHSTENS,
  ausgewaehlteIds,
  sammelAufrufe,
  sammelMeldung,
  type SammelAktion,
} from '$lib/sammel';
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

  notizbuchAendern: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const id = Number(felder.get('id'));
    const name = String(felder.get('name') ?? '').trim();
    if (!id || !name) return fail(400, { fehler: 'Name fehlt' });
    const farbe = String(felder.get('farbe') ?? '') || null;
    try {
      // PUT ersetzt alle Felder: die Sortierung kommt deshalb unverändert mit,
      // sonst fiele jedes umbenannte Notizbuch auf 0 zurück.
      await api(user, `/api/notizbuecher/${id}`, fetch, {
        method: 'PUT',
        body: JSON.stringify({ name, farbe, sortierung: Number(felder.get('sortierung')) || 0 }),
      });
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
    return { ok: true };
  },

  sammel: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const aktion = String(felder.get('aktion') ?? '') as SammelAktion;
    if (!SAMMEL_AKTIONEN.includes(aktion)) return fail(400, { fehler: 'Unbekannte Aktion' });
    const ids = ausgewaehlteIds(felder.getAll('id'));
    if (!ids.length) return fail(400, { fehler: 'Keine Notiz ausgewählt' });
    if (ids.length > SAMMEL_HOECHSTENS) return fail(400, { fehler: 'Zu viele auf einmal' });
    let gelungen = 0;
    let fehler = 0;
    // Nacheinander, nicht parallel: der Dienst schreibt in eine SQLite-Datei,
    // und hundert gleichzeitige Schreiber warteten nur aufeinander.
    for (const a of sammelAufrufe(aktion, ids, String(felder.get('buch') ?? ''))) {
      try {
        await api(user, a.pfad, fetch, {
          method: a.methode,
          ...(a.rumpf ? { body: JSON.stringify(a.rumpf) } : {}),
        });
        gelungen++;
      } catch (e) {
        if (!(e instanceof ApiFehler)) throw e;
        fehler++;
      }
    }
    return { sammelMeldung: sammelMeldung(aktion, gelungen, fehler), papierkorb: aktion === 'loeschen' };
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
