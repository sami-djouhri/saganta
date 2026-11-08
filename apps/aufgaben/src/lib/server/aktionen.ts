/**
 * Die Aktionen der Aufgaben-App, einmal fuer alle vier Seiten.
 *
 * SvelteKit verlangt `actions` je `+page.server.ts`. Ohne ein geteiltes Modul
 * waere derselbe Block viermal kopiert, und beim naechsten Feld haette eine der
 * Kopien es nicht. Jede Seite exportiert `actions = aufgabenAktionen`.
 */
import { fail, type Actions } from '@sveltejs/kit';
import { notizDazuAusFormular } from '@saganta/notizen-anschluss';
import { bffCtx, bffFetch, type Planung } from '$lib/aufgaben-bff';
import {
  alsPlanung,
  dienstCtx,
  dienstFetch,
  energieZumDienst,
  type DienstPlan,
} from '$lib/server/aufgaben-dienst';
import { notizAnschluss } from '$lib/server/notizen';

/**
 * Prioritaet in drei Worten (Festlegung fuer den Aufgaben-Dienst). Ein altes
 * Formular mit „dringend" wird zu „hoch", statt am Dienst mit 422 zu scheitern.
 */
function prioritaet(fd: FormData): 'hoch' | 'mittel' | 'niedrig' {
  const wert = String(fd.get('prioritaet') ?? 'mittel');
  if (wert === 'dringend' || wert === 'hoch') return 'hoch';
  return wert === 'niedrig' ? 'niedrig' : 'mittel';
}

/** Leere Formularwerte werden zu `null`, nicht zu `""`. */
function optional(fd: FormData, feld: string): string | null {
  const wert = String(fd.get(feld) ?? '').trim();
  return wert || null;
}

export const aufgabenAktionen: Actions = {
  /**
   * Tag planen. `festlegen=false` ist eine Vorschau und aendert nichts.
   *
   * Das ist der Kern dieser App: **erst rechnen, dann fragen.** Seit dem
   * 2026-11-03 fragt der Aufgaben-Dienst den Planer des Kalenders und haelt die
   * Zeiten selbst fest; der Kalender bekommt keine Kopie der Aufgaben.
   */
  planen: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const datum = String(fd.get('datum') ?? '').trim();
    const festlegen = String(fd.get('festlegen') ?? '') === 'true';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datum)) return fail(400, { fehler: 'Datum fehlt' });
    try {
      const plan = await dienstFetch<DienstPlan>(ctx, '/api/planen', fetch, {
        method: 'POST',
        json: { datum, festlegen },
      });
      return { plan: alsPlanung(plan) as Planung, festgelegt: festlegen };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  anlegen: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const titel = String(fd.get('titel') ?? '').trim();
    if (!titel) return fail(400, { fehler: 'Ein Titel fehlt.' });
    const koerper: Record<string, unknown> = { titel, prioritaet: prioritaet(fd) };
    const faellig = optional(fd, 'faellig');
    if (faellig) koerper.faellig = faellig;
    const dauer = optional(fd, 'dauer');
    if (dauer) koerper.dauer_min = Number(dauer);
    try {
      await dienstFetch(ctx, '/api/aufgaben', fetch, { method: 'POST', json: koerper });
      return { angelegt: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  umschalten: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'id fehlt' });
    const erledigt = String(fd.get('erledigt') ?? '') === 'true';
    try {
      await dienstFetch(ctx, `/api/aufgaben/${encodeURIComponent(id)}/${erledigt ? 'offen' : 'erledigt'}`, fetch, {
        method: 'POST',
      });
      return { ok: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  speichern: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const titel = String(fd.get('titel') ?? '').trim();
    if (!id) return fail(400, { fehler: 'id fehlt' });
    if (!titel) return fail(400, { fehler: 'Ein Titel fehlt.' });
    const dauer = optional(fd, 'dauer');
    try {
      await dienstFetch(ctx, `/api/aufgaben/${encodeURIComponent(id)}`, fetch, {
        method: 'PUT',
        // Leeres Feld heisst hier ausdruecklich „entfernen", deshalb `null`
        // statt Auslassen: ein weggelassenes Feld laesst den alten Wert stehen.
        json: {
          titel,
          notiz: optional(fd, 'beschreibung'),
          prioritaet: prioritaet(fd),
          faellig: optional(fd, 'faellig'),
          dauer_min: dauer ? Number(dauer) : null,
          energie: energieZumDienst(optional(fd, 'energie')),
        },
      });
      return { gespeichert: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  /**
   * Verschieben ueber den eigenen Weg des Dienstes, nicht ueber ein stilles
   * Aendern des Tages. Der Unterschied ist der Zaehler: daraus entsteht
   * „bleibt liegen". Wer den Tag direkt setzt, verschiebt beliebig oft, ohne
   * dass es je auffaellt.
   */
  verschieben: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const datum = String(fd.get('datum') ?? '').trim();
    if (!id) return fail(400, { fehler: 'id fehlt' });
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datum)) return fail(400, { fehler: 'Datum fehlt' });
    try {
      await dienstFetch(ctx, `/api/aufgaben/${encodeURIComponent(id)}/verschieben`, fetch, {
        method: 'POST',
        json: { tag: datum },
      });
      return { verschoben: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  loeschen: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'id fehlt' });
    try {
      await dienstFetch(ctx, `/api/aufgaben/${encodeURIComponent(id)}`, fetch, { method: 'DELETE' });
      return { geloescht: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  /**
   * Notiz zur Aufgabe: neu anlegen oder eine vorhandene anhaengen.
   *
   * **Eine Aktion, nicht zwei.** Beides endet in derselben Verknuepfung,
   * und die Unterscheidung trifft `notizDazuAusFormular` am Feld `notiz`.
   * Zwei Aktionen hiessen zwei Fehlerbilder und zwei Stellen, an denen beim
   * naechsten Feld eine vergessen wird.
   */
  notizDazu: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { fehler: 'nicht angemeldet' });
    const erg = await notizDazuAusFormular(
      await request.formData(),
      notizAnschluss(locals, fetch),
    );
    if (!erg.ok) return fail(400, { notizFehler: erg.fehler });
    return { notiz: erg.notiz };
  },

  zielAnlegen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const titel = String(fd.get('titel') ?? '').trim();
    const datum = String(fd.get('datum') ?? '').trim();
    if (!titel) return fail(400, { fehler: 'Ein Titel fehlt.' });
    if (!datum) return fail(400, { fehler: 'Datum fehlt.' });
    try {
      await bffFetch(ctx.base, '/api/goals', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: titel, date: datum, priority: String(fd.get('prio') ?? 'B') }),
      });
      return { zielOk: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  /** Ziel erreicht bzw. wieder offen, wie der Haken in der App (Gleichstand 2026-11-07). */
  zielUmschalten: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'id fehlt' });
    const status = fd.get('erreicht') === '1' ? 'planned' : 'achieved';
    try {
      await bffFetch(ctx.base, `/api/goals/${id}`, ctx.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      return { zielOk: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  zielLoeschen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'id fehlt' });
    try {
      await bffFetch(ctx.base, `/api/goals/${id}`, ctx.token, fetch, { method: 'DELETE' });
      return { zielOk: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },
};
