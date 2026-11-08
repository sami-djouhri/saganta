import { fail, redirect } from '@sveltejs/kit';
import type { Anstehend, Kontakt } from '$lib/typen';
import { dienst, dienstCtx, ursache } from '$lib/server/dienst';
import type { Actions, PageServerLoad } from './$types';

// Suche und Gruppenfilter leben im Browser: eine Sicht auf dieselbe Liste,
// die bei einem Haushalt in die Hunderte, nicht in die Tausende geht.
export const load: PageServerLoad = async ({ locals, fetch }) => {
  const ctx = dienstCtx(locals);
  const leer = {
    kontakte: [] as Kontakt[],
    anstehend: [] as Anstehend[],
    gruppen: [] as string[],
    kalenderAktuell: true,
    fehler: null as string | null,
  };
  if (!ctx) return { ...leer, fehler: 'Der Kontakte-Dienst ist nicht eingerichtet.' };
  try {
    const [liste, anstehend, gruppen] = await Promise.all([
      dienst<{ kontakte: Kontakt[]; kalender_aktuell: boolean }>(ctx, '/api/kontakte', fetch),
      dienst<Anstehend[]>(ctx, '/api/anstehend?tage=30', fetch),
      dienst<string[]>(ctx, '/api/gruppen', fetch),
    ]);
    return { ...leer, kontakte: liste.kontakte, kalenderAktuell: liste.kalender_aktuell, anstehend, gruppen };
  } catch (err) {
    return { ...leer, fehler: ursache(err) };
  }
};

export const actions: Actions = {
  /** Erstbestand aus dem Kalender uebernehmen (idempotent am Dienst). */
  umzug: async ({ locals, fetch }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    try {
      const erg = await dienst<{ gefunden: number; uebernommen: number; schon_da: number }>(
        ctx, '/api/umzug/kalender', fetch, { method: 'POST' });
      return { umzug: erg };
    } catch (err) {
      return fail(502, { fehler: ursache(err) });
    }
  },

  abgleich: async ({ locals, fetch }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    try {
      await dienst(ctx, '/api/abgleich', fetch, { method: 'POST' });
    } catch (err) {
      return fail(502, { fehler: ursache(err) });
    }
    redirect(303, '/');
  },
};
