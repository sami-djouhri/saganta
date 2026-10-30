import { error, fail, redirect } from '@sveltejs/kit';
import { freigabeBasis } from '$lib/meta';
import { ApiFehler, api } from '$lib/notizen-api';
import type { Notiz, Notizbuch } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, params, url, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');

  try {
    const [notiz, notizbuecher] = await Promise.all([
      api<Notiz>(user, `/api/notizen/${params.id}`, fetch),
      api<Notizbuch[]>(user, '/api/notizbuecher', fetch).catch(() => [] as Notizbuch[]),
    ]);
    // Die Basis der Kurzadressen kommt vom Server: `location` gibt es beim
    // ersten Rendern noch nicht, und ein Feld, das erst nach dem Laden seinen
    // Inhalt bekommt, sieht aus wie ein Fehler.
    return { notiz, notizbuecher, freigabeBasis: freigabeBasis(url.origin) };
  } catch (e) {
    if (e instanceof ApiFehler) error(e.status === 404 ? 404 : 502, e.detail);
    throw e;
  }
};

/** Kürzt die Wiederholung in jeder Aktion auf eine Zeile. */
async function mitApi<T>(
  aufruf: () => Promise<T>,
): Promise<{ ok: true } | ReturnType<typeof fail>> {
  try {
    await aufruf();
    return { ok: true };
  } catch (e) {
    if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
    throw e;
  }
}

export const actions: Actions = {
  speichern: async ({ locals, params, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const buch = String(felder.get('notizbuch_id') ?? '');
    const basis = String(felder.get('basis') ?? '');
    const tags = String(felder.get('tags') ?? '')
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    return mitApi(() =>
      api(user, `/api/notizen/${params.id}`, fetch, {
        method: 'PATCH',
        body: JSON.stringify({
          titel: String(felder.get('titel') ?? ''),
          inhalt: String(felder.get('inhalt') ?? ''),
          tags,
          ...(buch ? { notizbuch_id: Number(buch) } : { notizbuch_loesen: true }),
          // Der Stand, den die Seite geladen hatte: weicht er inzwischen ab,
          // kommt 409 zurück statt eines stillen Überschreibens.
          ...(basis ? { basis_geaendert_am: basis } : {}),
        }),
      }),
    );
  },

  umschalten: async ({ locals, params, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const feld = String(felder.get('feld') ?? '');
    if (feld !== 'angeheftet' && feld !== 'archiviert') {
      return fail(400, { fehler: 'Unbekanntes Feld' });
    }
    const wert = String(felder.get('wert') ?? '') === 'true';
    return mitApi(() =>
      api(user, `/api/notizen/${params.id}`, fetch, {
        method: 'PATCH',
        body: JSON.stringify({ [feld]: wert }),
      }),
    );
  },

  loeschen: async ({ locals, params, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    try {
      await api(user, `/api/notizen/${params.id}`, fetch, { method: 'DELETE' });
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
    redirect(303, '/');
  },

  verknuepfen: async ({ locals, params, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    return mitApi(() =>
      api(user, `/api/notizen/${params.id}/verknuepfungen`, fetch, {
        method: 'POST',
        body: JSON.stringify({
          typ: String(felder.get('typ') ?? ''),
          ref: String(felder.get('ref') ?? ''),
          label: String(felder.get('label') ?? ''),
        }),
      }),
    );
  },

  entknuepfen: async ({ locals, params, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const id = Number(felder.get('id'));
    return mitApi(() =>
      api(user, `/api/notizen/${params.id}/verknuepfungen/${id}`, fetch, { method: 'DELETE' }),
    );
  },

  anhangHochladen: async ({ locals, params, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const datei = felder.get('datei');
    if (!(datei instanceof File) || datei.size === 0) {
      return fail(400, { fehler: 'Keine Datei gewählt' });
    }
    // Die Weitergabe baut eine eigene FormData: die eingehende trägt auch die
    // Feldnamen des Formulars, das Backend erwartet genau eines namens `datei`.
    const weiter = new FormData();
    weiter.append('datei', datei, datei.name);
    return mitApi(() =>
      api(user, `/api/notizen/${params.id}/anhaenge`, fetch, { method: 'POST', body: weiter }),
    );
  },

  anhangLoeschen: async ({ locals, params, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const id = Number(felder.get('id'));
    return mitApi(() =>
      api(user, `/api/notizen/${params.id}/anhaenge/${id}`, fetch, { method: 'DELETE' }),
    );
  },

  freigabeWiderrufen: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const id = Number(felder.get('id'));
    return mitApi(() => api(user, `/api/freigaben/${id}`, fetch, { method: 'DELETE' }));
  },
};
