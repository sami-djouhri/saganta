/**
 * Die Aktionen der Aufgaben-App, einmal fuer alle vier Seiten.
 *
 * SvelteKit verlangt `actions` je `+page.server.ts`. Ohne ein geteiltes Modul
 * waere derselbe Block viermal kopiert, und beim naechsten Feld haette eine der
 * Kopien es nicht. Jede Seite exportiert `actions = aufgabenAktionen`.
 */
import { fail, type Actions } from '@sveltejs/kit';
import { backendSecret, bffCtx, bffFetch, type Planung } from '$lib/aufgaben-bff';

/** Leere Formularwerte werden zu `null`, nicht zu `""`. */
function optional(fd: FormData, feld: string): string | null {
  const wert = String(fd.get(feld) ?? '').trim();
  return wert || null;
}

export const aufgabenAktionen: Actions = {
  /**
   * Tag planen. `festlegen=false` ist eine Vorschau und aendert nichts.
   *
   * ★ Das ist der Kern dieser App: **erst rechnen, dann fragen.** Die Engine
   * kann das seit jeher (`/api/assistant/plan-day` mit `commit`), der Weg war
   * nur hinter einem Stapel Vorschlaege versteckt, die man einzeln lesen und
   * selbst umsetzen musste. Ein Vorschlag, den man selbst abtippen muss, ist
   * keine Planung, sondern eine Erinnerung daran, dass man planen muesste.
   */
  planen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const datum = String(fd.get('datum') ?? '').trim();
    const festlegen = String(fd.get('festlegen') ?? '') === 'true';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datum)) return fail(400, { fehler: 'Datum fehlt' });
    try {
      const plan = await bffFetch<Planung>(ctx.base, '/api/assistant/plan-day', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: datum, commit: festlegen }),
      });
      return { plan, festgelegt: festlegen };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  anlegen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const titel = String(fd.get('titel') ?? '').trim();
    if (!titel) return fail(400, { fehler: 'Ein Titel fehlt.' });
    const koerper: Record<string, unknown> = {
      title: titel,
      priority: String(fd.get('prioritaet') ?? 'mittel'),
    };
    const faellig = optional(fd, 'faellig');
    if (faellig) koerper.due_date = faellig;
    const dauer = optional(fd, 'dauer');
    if (dauer) koerper.estimated_minutes = Number(dauer);
    const projekt = optional(fd, 'projekt');
    if (projekt) koerper.project_id = projekt;
    try {
      await bffFetch(ctx.base, '/api/todos', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(koerper),
      });
      return { angelegt: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  umschalten: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'id fehlt' });
    const erledigt = String(fd.get('erledigt') ?? '') === 'true';
    try {
      await bffFetch(
        ctx.base,
        `/api/todos/${id}/${erledigt ? 'uncomplete' : 'complete'}`,
        ctx.token,
        fetch,
        { method: 'POST' },
      );
      return { ok: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  speichern: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const titel = String(fd.get('titel') ?? '').trim();
    if (!id) return fail(400, { fehler: 'id fehlt' });
    if (!titel) return fail(400, { fehler: 'Ein Titel fehlt.' });
    const dauer = optional(fd, 'dauer');
    try {
      await bffFetch(ctx.base, `/api/todos/${id}`, ctx.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: titel,
          description: optional(fd, 'beschreibung'),
          priority: String(fd.get('prioritaet') ?? 'mittel'),
          // Leeres Feld heisst hier ausdruecklich „entfernen", deshalb `null`
          // statt Auslassen: ein weggelassenes Feld laesst den alten Wert stehen.
          due_date: optional(fd, 'faellig'),
          estimated_minutes: dauer ? Number(dauer) : null,
          energy_required: optional(fd, 'energie'),
          project_id: optional(fd, 'projekt'),
        }),
      });
      return { gespeichert: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  /**
   * Verschieben ueber den `defer`-Weg der Engine, nicht ueber ein stilles `PUT`
   * auf das Datum.
   *
   * ★ Der Unterschied ist der Zaehler: `defer` erhoeht `defer_count`, und daraus
   * entsteht die Warnung „bleibt liegen". Wer das Datum direkt setzt, verschiebt
   * eine Aufgabe beliebig oft, ohne dass es je auffaellt.
   */
  verschieben: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const datum = String(fd.get('datum') ?? '').trim();
    if (!id) return fail(400, { fehler: 'id fehlt' });
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datum)) return fail(400, { fehler: 'Datum fehlt' });
    try {
      // ⚠️ `planned_date`, NICHT `due_date`: der Endpunkt kennt kein due_date und
      // verwirft es stillschweigend. Ohne planned_date landet die Aufgabe dann im
      // Pool statt am gewuenschten Tag, und „auf morgen verschoben" hiesse in
      // Wahrheit „ins Unbestimmte". Der BFF prueft das ebenfalls.
      await bffFetch(ctx.base, `/api/todos/${id}/defer`, ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ planned_date: datum, reason: optional(fd, 'grund') }),
      });
      return { verschoben: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  loeschen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { fehler: 'id fehlt' });
    try {
      await bffFetch(ctx.base, `/api/todos/${id}`, ctx.token, fetch, { method: 'DELETE' });
      return { geloescht: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  notizAnhaengen: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const titel = String(fd.get('titel') ?? '');
    const notiz = Number(fd.get('notiz'));
    if (!id || !Number.isFinite(notiz)) return fail(400, { fehler: 'Angaben fehlen' });
    const { notizVerknuepfen } = await import('$lib/server/notizen');
    try {
      await notizVerknuepfen(notiz, id, titel, locals.user, backendSecret(), fetch);
      return { verknuepft: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
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
