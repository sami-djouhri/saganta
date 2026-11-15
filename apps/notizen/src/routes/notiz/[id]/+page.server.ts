import { error, fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { issueBackendToken } from '@saganta/auth';
import { freigabeBasis } from '$lib/meta';
import { ApiFehler, api, backendSecret } from '$lib/notizen-api';
import type { Notiz, Notizbuch, Stand, StandKurz } from '$lib/types';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, params, url, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');

  try {
    // Ein angesehener früherer Stand steht in der Adresse (?stand=<id>), damit
    // die Ansicht ohne eigene Datenroute auskommt und Zurück im Browser wirkt.
    const standId = Number(url.searchParams.get('stand')) || null;
    const [notiz, notizbuecher, staende, stand] = await Promise.all([
      api<Notiz>(user, `/api/notizen/${params.id}`, fetch),
      api<Notizbuch[]>(user, '/api/notizbuecher', fetch).catch(() => [] as Notizbuch[]),
      // Fehlt die Liste, fehlt nur dieser Abschnitt, nicht die Notiz.
      api<StandKurz[]>(user, `/api/notizen/${params.id}/staende`, fetch).catch(() => null),
      standId
        ? api<Stand>(user, `/api/notizen/${params.id}/staende/${standId}`, fetch).catch(() => null)
        : Promise.resolve(null),
    ]);
    // Die Basis der Kurzadressen kommt vom Server: `location` gibt es beim
    // ersten Rendern noch nicht, und ein Feld, das erst nach dem Laden seinen
    // Inhalt bekommt, sieht aus wie ein Fehler.
    return {
      notiz,
      notizbuecher,
      staende,
      stand,
      freigabeBasis: freigabeBasis(url.origin),
      // Ohne Adresse des Aufgaben-Dienstes kein Knopf, statt eines Knopfes, der scheitert.
      kannAufgabe: Boolean(env.AUFGABEN_API_BASE_URL),
    };
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

  /**
   * „Aufgabe zu dieser Notiz" (Wunschliste 06.11., in der App seit 0.3.0): eine
   * Aufgabe mit dem Titel der Notiz im Aufgaben-Dienst, dann die Verknüpfung
   * Typ `aufgabe` hierher. Gleicher Weg wie `aufgabeZuNotiz` in der App.
   */
  aufgabeDazu: async ({ locals, params, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const basis = (env.AUFGABEN_API_BASE_URL ?? '').replace(/\/$/, '');
    if (!basis) return fail(503, { fehler: 'Aufgaben-Dienst nicht eingerichtet' });
    try {
      const notiz = await api<Notiz>(user, `/api/notizen/${params.id}`, fetch);
      const titel = notiz.titel.trim() || 'Aufgabe zur Notiz';
      const token = issueBackendToken({
        user,
        secret: backendSecret(),
        audience: 'aufgaben-api',
        ttlSeconds: 60,
      });
      const res = await fetch(`${basis}/api/aufgaben`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ titel: titel.slice(0, 500), notiz: `Zur Notiz „${titel}“` }),
      });
      if (!res.ok) return fail(502, { fehler: `Aufgabe nicht angelegt (Aufgaben-Dienst ${res.status})` });
      const aufgabe = (await res.json()) as { id: string; titel: string };
      await api(user, `/api/notizen/${params.id}/verknuepfungen`, fetch, {
        method: 'POST',
        body: JSON.stringify({ typ: 'aufgabe', ref: aufgabe.id, label: aufgabe.titel }),
      });
      return { ok: true, hinweis: `Aufgabe „${aufgabe.titel}“ angelegt und verbunden.` };
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
  },

  standWiederherstellen: async ({ locals, params, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const id = Number((await request.formData()).get('id'));
    if (!id) return fail(400, { fehler: 'Kein Stand gewählt' });
    try {
      await api(user, `/api/notizen/${params.id}/staende/${id}/wiederherstellen`, fetch, {
        method: 'POST',
      });
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
    // Zurück auf die Notiz ohne ?stand: der eben zurückgeholte Stand ist jetzt der aktuelle.
    redirect(303, `/notiz/${params.id}`);
  },

  freigabeWiderrufen: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const felder = await request.formData();
    const id = Number(felder.get('id'));
    return mitApi(() => api(user, `/api/freigaben/${id}`, fetch, { method: 'DELETE' }));
  },
};
