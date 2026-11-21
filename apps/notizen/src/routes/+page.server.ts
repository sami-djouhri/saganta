import { error, fail, redirect } from '@sveltejs/kit';
import { ApiFehler, api } from '$lib/notizen-api';
import {
  SAMMEL_AKTIONEN,
  SAMMEL_HOECHSTENS,
  ausgewaehlteIds,
  sammelAufrufe,
  sammelMeldung,
  VERBINDEN_HOECHSTENS,
  verbindenMeldung,
  type SammelAktion,
} from '$lib/sammel';
import type { Notiz, NotizKurz, Notizbuch } from '$lib/types';
import { ausDeck, projektBaum, teilbaumSlugs, type BaumZeile } from '@saganta/ui';
import { istSlug, notizenDesProjekts } from '$lib/projektfilter';
import { HAT_FILTER, OHNE_BUCH, SORTIERUNGEN, type HatFilter } from '$lib/filter';
import { ladeDeckProjekte } from '$lib/server/projekte';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, url, fetch }) => {
  const user = locals.user;
  if (!user) redirect(303, '/');

  const suche = url.searchParams.get('q')?.trim() ?? '';
  const notizbuch = url.searchParams.get('buch');
  // Mehrere Tags kommagetrennt, alle muessen passen (seit 2026-11-21).
  const gewaehlteTags = (url.searchParams.get('tag') ?? '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
  const hat = (url.searchParams.get('hat') ?? '')
    .split(',')
    .filter((h): h is HatFilter => (HAT_FILTER as readonly string[]).includes(h));
  const sortierung = SORTIERUNGEN.find((x) => x.wert === url.searchParams.get('sort'))?.wert ?? '';
  const archivierte = url.searchParams.get('archiv') === '1';
  // Projektfilter (seit 2026-11-15): ein Oberprojekt schliesst seine
  // Unterprojekte ein, `nur=1` engt auf das Projekt selbst ein (U7).
  const projektRoh = url.searchParams.get('projekt')?.trim() ?? '';
  const projekt = istSlug(projektRoh) ? projektRoh : '';
  const nurDieses = url.searchParams.get('nur') === '1';

  const frage = new URLSearchParams();
  if (suche) frage.set('q', suche);
  if (notizbuch === OHNE_BUCH) frage.set('ohne_notizbuch', 'true');
  else if (notizbuch) frage.set('notizbuch_id', notizbuch);
  if (gewaehlteTags.length) frage.set('tag', gewaehlteTags.join(','));
  if (hat.length) frage.set('hat', hat.join(','));
  if (sortierung) frage.set('sortierung', sortierung);
  if (archivierte) frage.set('archivierte', 'true');

  const fehlerZu502 = (e: unknown) => {
    if (e instanceof ApiFehler) error(e.status >= 500 ? 502 : e.status, e.detail);
    throw e;
  };

  // Die Projekte zuerst: der Teilbaum entscheidet, welche Slugs gefragt werden.
  const deck = await ladeDeckProjekte(user, fetch);
  const slugs = projekt ? (nurDieses ? [projekt] : teilbaumSlugs(projekt, deck.map(ausDeck))) : [];

  // Nebeneinander, aber einzeln bewertet: eine leere Tag-Liste darf die
  // Notizliste nicht mitreissen.
  const ladeNotizen = async (): Promise<NotizKurz[]> => {
    if (!projekt) return api<NotizKurz[]>(user, `/api/notizen?${frage}`, fetch).catch(fehlerZu502);
    // Archivierte kennt die Sammelroute nicht; der Filter zeigt die laufenden.
    // Alle uebrigen Filter samt Reihenfolge wendet der Dienst an; hier wird nur
    // mit den Notizen des Projekts geschnitten (eine Stelle fuer die Filter).
    const breit = new URLSearchParams(frage);
    breit.set('limit', '500');
    const [nach, gefiltert] = await Promise.all([
      api<Record<string, NotizKurz[]>>(
        user,
        `/api/notizen/verknuepft?typ=projekt&refs=${encodeURIComponent(slugs.slice(0, 200).join(','))}`,
        fetch,
      ),
      api<NotizKurz[]>(user, `/api/notizen?${breit}`, fetch),
    ]).catch(fehlerZu502);
    return notizenDesProjekts(nach, { treffer: gefiltert.map((n) => n.id) });
  };

  const [notizen, notizbuecher, tags] = await Promise.all([
    ladeNotizen(),
    api<Notizbuch[]>(user, '/api/notizbuecher', fetch).catch(() => [] as Notizbuch[]),
    api<string[]>(user, '/api/notizen/tags', fetch).catch(() => [] as string[]),
  ]);

  // Auswahl: laufende Projekte eingerueckt; das gewaehlte bleibt sichtbar,
  // auch wenn es archiviert ist.
  const sichtbar = deck.filter((p) => !['archived', 'shutdown'].includes(p.status ?? '') || p.slug === projekt);
  const projekte: BaumZeile[] = projektBaum(sichtbar.map(ausDeck));
  const projektName = deck.find((p) => p.slug === projekt)?.name ?? projekt;

  return {
    notizen,
    notizbuecher,
    tags,
    suche,
    notizbuch,
    gewaehlteTags,
    hat,
    sortierung,
    archivierte,
    projekt,
    projektName,
    nurDieses,
    unterprojekte: Math.max(0, (projekt ? teilbaumSlugs(projekt, deck.map(ausDeck)).length : 1) - 1),
    projekte,
  };
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
          notizbuch_id: buch && buch !== OHNE_BUCH ? Number(buch) : null,
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

  /**
   * Die gewählten Notizen miteinander verbinden, jede mit jeder. Anders als die
   * übrigen Sammelaktionen ein einziger Aufruf: eine Verbindung betrifft zwei
   * Notizen zugleich, und der Dienst legt alle Paare in einer Transaktion an.
   */
  verbinden: async ({ locals, request, fetch }) => {
    const user = locals.user;
    if (!user) return fail(401, { fehler: 'Nicht angemeldet' });
    const ids = ausgewaehlteIds((await request.formData()).getAll('id'));
    if (ids.length < 2) return fail(400, { fehler: 'Zum Verbinden mindestens zwei Notizen wählen' });
    if (ids.length > VERBINDEN_HOECHSTENS) {
      return fail(400, { fehler: `Höchstens ${VERBINDEN_HOECHSTENS} Notizen auf einmal verbinden` });
    }
    try {
      const r = await api<{ neu: number; vorhanden: number }>(user, '/api/notizen/verbinden', fetch, {
        method: 'POST',
        body: JSON.stringify({ ids }),
      });
      return { sammelMeldung: verbindenMeldung(ids.length, r.neu) };
    } catch (e) {
      if (e instanceof ApiFehler) return fail(e.status, { fehler: e.detail });
      throw e;
    }
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
