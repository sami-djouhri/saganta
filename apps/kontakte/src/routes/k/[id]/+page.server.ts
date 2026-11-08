import { error, fail, redirect } from '@sveltejs/kit';
import { notizDazuAusFormular, notizenZuEinem } from '@saganta/notizen-anschluss';
import type { Fundtermin, Kontakt, TerminVerweis } from '$lib/typen';
import { DienstFehler, dienst, dienstCtx, termineSuchen, ursache } from '$lib/server/dienst';
import { kontaktAus } from '$lib/server/formular';
import { notizAnschluss } from '$lib/server/notizen';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch, params, url }) => {
  const ctx = dienstCtx(locals);
  if (!ctx || !locals.user) error(401, 'nicht angemeldet');
  let kontakt: Kontakt;
  try {
    kontakt = await dienst<Kontakt>(ctx, `/api/kontakte/${encodeURIComponent(params.id)}`, fetch);
  } catch (err) {
    if (err instanceof DienstFehler && err.status === 404) error(404, 'Den Kontakt gibt es nicht.');
    error(502, ursache(err));
  }
  const terminsuche = url.searchParams.get('terminsuche');
  const [gruppen, notizen, funde] = await Promise.all([
    dienst<string[]>(ctx, '/api/gruppen', fetch).catch(() => [] as string[]),
    notizenZuEinem('kontakt', kontakt.id, notizAnschluss(locals, fetch)),
    terminsuche !== null
      ? termineSuchen(locals.user, terminsuche, fetch).then(
          (t) => ({ treffer: t, stumm: false }),
          () => ({ treffer: [] as Fundtermin[], stumm: true }),
        )
      : Promise.resolve(null),
  ]);
  return { kontakt, gruppen, notizen, terminsuche, funde };
};

async function termineSetzen(
  locals: App.Locals,
  fetcher: typeof fetch,
  id: string,
  aendern: (alt: TerminVerweis[]) => TerminVerweis[],
) {
  const ctx = dienstCtx(locals);
  if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
  try {
    const k = await dienst<Kontakt>(ctx, `/api/kontakte/${encodeURIComponent(id)}`, fetcher);
    await dienst(ctx, `/api/kontakte/${encodeURIComponent(id)}`, fetcher, {
      method: 'PATCH',
      json: { termine: aendern(k.termine) },
    });
  } catch (err) {
    return fail(502, { fehler: ursache(err) });
  }
  redirect(303, `/k/${id}`);
}

export const actions: Actions = {
  speichern: async ({ locals, fetch, request, params }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const daten = kontaktAus(await request.formData());
    if (!daten.name) return fail(400, { fehler: 'Ein Name fehlt.' });
    try {
      await dienst(ctx, `/api/kontakte/${encodeURIComponent(params.id)}`, fetch, {
        method: 'PATCH',
        json: daten,
      });
    } catch (err) {
      return fail(502, { fehler: ursache(err) });
    }
    return { gespeichert: true };
  },

  loeschen: async ({ locals, fetch, params }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    try {
      await dienst(ctx, `/api/kontakte/${encodeURIComponent(params.id)}`, fetch, { method: 'DELETE' });
    } catch (err) {
      return fail(502, { fehler: ursache(err) });
    }
    redirect(303, `/papierkorb?geloescht=${encodeURIComponent(params.id)}`);
  },

  terminVerknuepfen: async ({ locals, fetch, request, params }) => {
    const fd = await request.formData();
    const neu: TerminVerweis = {
      ref: String(fd.get('ref') ?? ''),
      label: String(fd.get('label') ?? '').slice(0, 300),
      start: String(fd.get('start') ?? '') || null,
    };
    if (!neu.ref) return fail(400, { fehler: 'Kein Termin gewählt.' });
    return termineSetzen(locals, fetch, params.id, (alt) =>
      alt.some((t) => t.ref === neu.ref) ? alt : [...alt, neu],
    );
  },

  terminLoesen: async ({ locals, fetch, request, params }) => {
    const ref = String((await request.formData()).get('ref') ?? '');
    return termineSetzen(locals, fetch, params.id, (alt) => alt.filter((t) => t.ref !== ref));
  },

  notizDazu: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { fehler: 'nicht angemeldet' });
    const erg = await notizDazuAusFormular(await request.formData(), notizAnschluss(locals, fetch));
    if (!erg.ok) return fail(400, { notizFehler: erg.fehler });
    return { notiz: erg.notiz };
  },
};
