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
import { unteraufgabenNach } from '$lib/ordnen';
import { weitereAus, zuordnungAus } from '$lib/zuordnung';
import {
  alsPlanung,
  dienstCtx,
  dienstFetch,
  energieZumDienst,
  type DienstAufgabe,
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

const TAGESZEITEN = ['morgens', 'mittags', 'nachmittags', 'abends'];

/**
 * Wann die Aufgabe liegen darf (seit 2026-11-11): Tageszeit und EIN
 * Zeitfenster. Tage ohne Uhrzeit heissen ganztags, eine Uhrzeit ohne Tage
 * heisst jeden Tag. Liefert `undefined`, wenn die Aufgabe mehrere Fenster hat,
 * die dieses Formular nicht zeigt: dann bleiben sie unangetastet.
 */
function wannFelder(fd: FormData): { tageszeit: string | null; zeitfenster?: unknown } | { fehler: string } {
  const tz = optional(fd, 'tageszeit');
  const tageszeit = tz && TAGESZEITEN.includes(tz) ? tz : null;
  if (String(fd.get('fenster_mehrere') ?? '') === '1') return { tageszeit };
  const tage = [...new Set(fd.getAll('fenster_tag').map(Number))].filter((t) => t >= 0 && t <= 6).sort();
  const von = optional(fd, 'fenster_von');
  const bis = optional(fd, 'fenster_bis');
  if (tage.length === 0 && !von && !bis) return { tageszeit, zeitfenster: null };
  const fenster = {
    tage: tage.length ? tage : [0, 1, 2, 3, 4, 5, 6],
    von: von ?? '00:00',
    bis: bis ?? '23:59',
  };
  if (fenster.bis <= fenster.von) return { fehler: 'Zeitfenster: „bis“ muss nach „von“ liegen.' };
  return { tageszeit, zeitfenster: [fenster] };
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
    const zuordnung = zuordnungAus(optional(fd, 'zuordnung'));
    if (!zuordnung) return fail(400, { fehler: 'Unbekannte Zuordnung.' });
    if (zuordnung.projekt) koerper.projekt = zuordnung.projekt;
    if (zuordnung.liste_id) koerper.liste_id = zuordnung.liste_id;
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
    const turnus = optional(fd, 'turnus');
    const turnusTage = turnus ? Number(turnus) : null;
    if (turnusTage !== null && !(Number.isInteger(turnusTage) && turnusTage >= 1 && turnusTage <= 730))
      return fail(400, { fehler: 'Wiederholen: ganze Tage zwischen 1 und 730.' });
    const wann = wannFelder(fd);
    if ('fehler' in wann) return fail(400, { fehler: wann.fehler });
    // Plantag: ein geaenderter Tag nimmt die alte Uhrzeit mit weg, sie galt
    // fuer den alten Tag (wie beim Verschieben, nur ohne Zaehler: das hier ist
    // Planen, nicht Schieben).
    const tag = optional(fd, 'tag');
    const tagFelder = tag !== optional(fd, 'tag_alt') ? { tag, start: null, ende: null } : {};
    // Zuordnung nur bei einer Aenderung schicken: fehlt die Projektliste (ProjectDeck
    // nicht erreichbar), zeigt die Auswahl „nicht zugeordnet", und ein blindes `null`
    // loeste die Aufgabe beim Speichern aus ihrem Projekt. Bei einer Aenderung
    // gehen Projekt UND Liste mit, sonst bliebe das alte stehen (422 am Dienst).
    const wert = optional(fd, 'zuordnung');
    const zuordnung = zuordnungAus(wert);
    if (!zuordnung) return fail(400, { fehler: 'Unbekannte Zuordnung.' });
    const zuordnungFelder = wert !== optional(fd, 'zuordnung_alt') ? zuordnung : {};
    const weitere = weitereAus(
      fd.getAll('weitere_projekt').map(String),
      optional(fd, 'weitere_alt'),
      zuordnung.projekt,
    );
    if ('fehler' in weitere) return fail(400, { fehler: weitere.fehler });
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
          turnus_tage: turnusTage,
          ...wann,
          ...tagFelder,
          ...zuordnungFelder,
          ...weitere,
        },
      });
      return { gespeichert: true };
    } catch (err) {
      return fail(502, { fehler: String(err) });
    }
  },

  /**
   * Ein Griff an der Checkliste: anlegen, umschalten, entfernen (seit 13.11.,
   * die App hatte sie seit dem 07.11.). Gelesen wird der frische Stand vom
   * Dienst, nicht der aus dem Formular: zwei offene Fenster ueberschrieben sich
   * sonst gegenseitig die Haken. Der Dienst kennt nur die ganze Liste (PUT).
   */
  unteraufgabe: async ({ locals, fetch, request }) => {
    const ctx = dienstCtx(locals);
    if (!ctx) return fail(401, { fehler: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const art = String(fd.get('art') ?? '');
    if (!id) return fail(400, { fehler: 'id fehlt' });
    const griff =
      art === 'anlegen'
        ? ({ art, text: String(fd.get('text') ?? '') } as const)
        : art === 'umschalten' || art === 'entfernen'
          ? ({ art, index: Number(fd.get('index')) } as const)
          : null;
    if (!griff || ('index' in griff && !Number.isInteger(griff.index))) {
      return fail(400, { fehler: 'Unbekannter Griff an der Checkliste.' });
    }
    try {
      const frisch = await dienstFetch<DienstAufgabe>(ctx, `/api/aufgaben/${encodeURIComponent(id)}`, fetch);
      await dienstFetch(ctx, `/api/aufgaben/${encodeURIComponent(id)}`, fetch, {
        method: 'PUT',
        json: { unteraufgaben: unteraufgabenNach(frisch.unteraufgaben, griff) },
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
