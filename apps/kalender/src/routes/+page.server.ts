import { env } from '$env/dynamic/private';
import { fail } from '@sveltejs/kit';
import {
  backendSecret,
  kalenderBffFetch,
  kalenderBffToken,
  type ActivityInsight,
  type AssistantToday,
  type HabitProgress,
  type HabitSession,
  type InsightsResponse,
  type KalenderCalendar,
  type KalenderEvent,
  type KalenderGoal,
  type KalenderProject,
  type KalenderTodo,
  type PlanResult,
  type ReviewableActivity,
  type ReviewableResponse,
  type Tagesdecke,
  type UpcomingResponse,
  type Konflikt,
  type KonfliktVorschlag,
  type KonfliktWeg,
} from '$lib/kalender-bff';
import { notizDazuAusFormular, notizenZu, type NotizKurz } from '@saganta/notizen-anschluss';
import { notizAnschluss, terminKennung } from '$lib/server/notizen';
import {
  AUFGABEN_FARBE,
  AUFGABEN_KALENDER,
  aufgabeAlsTermin,
  startOf,
  weekGridDays,
  type GeplanteAufgabe,
} from '$lib/cal';
import type { Beleg, LaufenderTimer } from '$lib/handzeit';
import type { Actions, PageServerLoad } from './$types';
import { ausDeck, projektBaum, type BaumZeile } from '@saganta/ui';
import { ladeDeckProjekte } from '$lib/server/projekte';
import { projektFeld } from '$lib/projektfeld';

const ALLOWED_DAYS = [7, 14, 30] as const;

interface CaptureSuggestion {
  type: 'event' | 'todo';
  title: string;
  date: string | null;
  start_time: string | null;
  end_time: string | null;
  confidence?: string;
  source?: string;
  /** Seit 2026-11-01: Dauer auch ohne Uhrzeit („morgen 2h Keller"). */
  dauer_min?: number | null;
  ort?: string | null;
  /** Seit 2026-11-07: RRULE, z. B. FREQ=WEEKLY;BYDAY=MO. */
  wiederholung?: string | null;
  /** Bis zu drei freie Zeiten für einen Block ohne Uhrzeit. */
  vorschlaege?: { date: string; start_time: string; end_time: string; abschnitt: string }[];
}

// Grob den Grid-Bereich eines Monats abdecken (± eine Woche für Rand-Wochen).
function monthRange(month: string): { start: string; end: string } {
  // `m` hatte bereits einen Rückfallwert, `y` nicht: beim Zerlegen kann beides
  // `undefined` sein. Praktisch nicht erreichbar (das Muster ist vorher geprüft),
  // aber die halbe Absicherung war irreführender als gar keine.
  const [y, m] = month.split('-').map(Number);
  const jahr = y ?? new Date().getUTCFullYear();
  const first = new Date(Date.UTC(jahr, (m ?? 1) - 1, 1));
  const last = new Date(Date.UTC(jahr, m ?? 1, 0));
  const s = new Date(first);
  s.setUTCDate(first.getUTCDate() - 7);
  const e = new Date(last);
  e.setUTCDate(last.getUTCDate() + 7);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(s), end: fmt(e) };
}

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const failures: { bff?: string } = {};
  let upcoming: UpcomingResponse | null = null;
  let calendars: KalenderCalendar[] = [];
  let todos: KalenderTodo[] = [];
  let goals: KalenderGoal[] = [];
  let projects: KalenderProject[] = [];
  let assistant: AssistantToday | null = null;
  let reviewable: ReviewableActivity[] = [];
  let insights: ActivityInsight[] = [];
  let habitProgress: HabitProgress[] = [];
  let habitSessions: HabitSession[] = [];
  let tagesdecke: Tagesdecke | null = null;
  // Zeit von Hand (seit 2026-11-08): laufender Timer, Belege und Termine von
  // heute, unabhaengig von der gezeigten Ansicht (eine fremde Woche enthaelt
  // den heutigen Tag nicht).
  let zeitTimer: LaufenderTimer | null = null;
  let zeitBelege: string[] = [];
  let termineHeute: KalenderEvent[] = [];
  let zeitFehler: string | null = null;
  // Die Notizen je Termin-Kennung, und ob die Notizen-App überhaupt geantwortet
  // hat. Der zweite Wert zählt: ohne ihn sieht ein Ausfall aus wie „keine Notiz
  // vorhanden", und das wäre eine Aussage über einen ungelesenen Bestand.
  let notizenNach: Record<string, NotizKurz[]> = {};
  let notizenStumm = false;
  // Überschneidungen im gezeigten Zeitraum (seit 2026-11-14), fail-soft.
  let konflikte: Konflikt[] = [];

  // Heute in Haus-Zeitzone (Tagesziele + Default-Datum neuer Einträge). en-CA → YYYY-MM-DD.
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(new Date());

  // Ansicht: Agenda (Liste) / Monat (6×7-Grid) / Woche (Stunden-Grid).
  // Monat via ?month=YYYY-MM, Woche via ?week=YYYY-MM-DD (Anker) navigierbar.
  // Standard = Woche (Entscheid 06.11.: „Kalender oeffnet immer in Woche",
  // wie die App seit 0.10.0). Agenda/Monat via ?view=.
  const viewParam = url.searchParams.get('view');
  const view = viewParam === 'list' ? 'list' : viewParam === 'month' ? 'month' : 'week';
  const monthParam = url.searchParams.get('month') ?? '';
  const month = /^\d{4}-\d{2}$/.test(monthParam) ? monthParam : today.slice(0, 7);
  const weekParam = url.searchParams.get('week') ?? '';
  const week = /^\d{4}-\d{2}-\d{2}$/.test(weekParam) ? weekParam : today;

  const requested = Number.parseInt(url.searchParams.get('days') ?? '14', 10);
  const days = ALLOWED_DAYS.includes(requested as (typeof ALLOWED_DAYS)[number]) ? requested : 14;

  // Kalender-Filter: leer = alle. Wird client-seitig angewandt (Events tragen
  // calendar_id), bleibt aber als URL-Param erhalten → teilbar/bookmarkbar.
  const selectedCalendar = url.searchParams.get('calendar') ?? '';

  // Cross-App-Intent: andere Saganta-Apps (Post-Fristen, News-Items) verlinken auf
  // `?capture=<text>&date=<iso>` → Quick-Capture wird vorbefüllt (kalenderCaptureUrl).
  const prefillCapture = (url.searchParams.get('capture') ?? '').slice(0, 500);
  const prefillDate = url.searchParams.get('date') ?? '';

  // Tagesdecke: welcher Tag gezeigt wird. `?decke=YYYY-MM-DD` traegt das
  // rueckwirkende Nachtragen verpasster Tage und bleibt teilbar in der Adresse.
  const deckeParam = url.searchParams.get('decke') ?? '';
  const deckeTag = /^\d{4}-\d{2}-\d{2}$/.test(deckeParam) ? deckeParam : today;

  // Projekte fuer das Feld „Projekt" und die Marke am Termin (seit 2026-11-15).
  // Nebenher und fail-soft: ohne ProjectDeck bleibt der Editor bedienbar.
  const deckLauf = locals.user ? ladeDeckProjekte(locals.user, fetch) : Promise.resolve([]);

  if (locals.user && env.KALENDER_BFF_BASE_URL) {
    const token = kalenderBffToken(locals.user, backendSecret());
    const baseUrl = env.KALENDER_BFF_BASE_URL;

    let eventsPath: string;
    // Derselbe Zeitraum fuer die geplanten Aufgaben (seit 2026-11-11).
    let aufgabenVon: string;
    let aufgabenBis: string;
    if (view === 'month') {
      const rng = monthRange(month);
      eventsPath = `/api/events/range?start=${rng.start}&end=${rng.end}`;
      [aufgabenVon, aufgabenBis] = [rng.start, rng.end];
    } else if (view === 'week') {
      const wd = weekGridDays(week);
      eventsPath = `/api/events/range?start=${wd[0]}&end=${wd[6]}`;
      [aufgabenVon, aufgabenBis] = [wd[0]!, wd[6]!];
    } else {
      eventsPath = `/api/events/upcoming?days=${days}&limit=200`;
      const bis = new Date(`${today}T12:00:00Z`);
      bis.setUTCDate(bis.getUTCDate() + days - 1);
      [aufgabenVon, aufgabenBis] = [today, bis.toISOString().slice(0, 10)];
    }

    const [
      upcomingRes,
      calendarsRes,
      todosRes,
      goalsRes,
      projectsRes,
      assistantRes,
      reviewableRes,
      insightsRes,
      habitProgressRes,
      habitSessionsRes,
      deckeRes,
      zeitRes,
      heuteRes,
      aufgabenRes,
      konflikteRes,
    ] = await Promise.allSettled([
      kalenderBffFetch<UpcomingResponse>(baseUrl, eventsPath, token, fetch),
      kalenderBffFetch<KalenderCalendar[]>(baseUrl, '/api/events/calendars', token, fetch),
      // Nur noch fuer die Zaehlung auf der Kachel: verwaltet werden Aufgaben
      // und Ziele seit 2026-09-13 in der eigenen App `aufgaben.saganta.*`, die
      // auf demselben BFF sitzt. Ein Bestand, eine Oberflaeche.
      kalenderBffFetch<KalenderTodo[]>(baseUrl, '/api/todos', token, fetch),
      kalenderBffFetch<KalenderGoal[]>(baseUrl, `/api/goals?date=${today}`, token, fetch),
      kalenderBffFetch<KalenderProject[]>(baseUrl, '/api/projects', token, fetch),
      kalenderBffFetch<AssistantToday>(baseUrl, '/api/assistant/today', token, fetch),
      // lookback=7 → auch die letzten Tage rückwirkend bewertbar (mehr Datengrundlage).
      kalenderBffFetch<ReviewableResponse>(
        baseUrl,
        `/api/feedback/reviewable?date=${today}&lookback=7`,
        token,
        fetch,
      ),
      kalenderBffFetch<InsightsResponse>(baseUrl, '/api/feedback/insights', token, fetch),
      // Gewohnheiten: Wochensoll/-ist + die vom Scheduler geplanten Sitzungen.
      // Zwei Aufrufe, weil „heute" und „kommende Tage" getrennte Routen sind;
      // zusammengeführt wird unten.
      kalenderBffFetch<HabitProgress[]>(baseUrl, '/api/habits/weekly-progress', token, fetch),
      Promise.all([
        kalenderBffFetch<HabitSession[]>(baseUrl, '/api/habits/sessions/today', token, fetch),
        kalenderBffFetch<HabitSession[]>(baseUrl, '/api/habits/sessions/upcoming?days=7', token, fetch),
      ]),
      kalenderBffFetch<Tagesdecke>(baseUrl, `/api/tagesdecke?datum=${deckeTag}`, token, fetch),
      kalenderBffFetch<{ belege?: Beleg[]; laeuft?: LaufenderTimer | null }>(
        baseUrl,
        `/api/zeit/belege?von=${today}&bis=${today}`,
        token,
        fetch,
      ),
      kalenderBffFetch<UpcomingResponse>(baseUrl, `/api/events/range?start=${today}&end=${today}`, token, fetch),
      kalenderBffFetch<GeplanteAufgabe[]>(
        baseUrl,
        `/api/aufgaben/zeitraum?von=${aufgabenVon}&bis=${aufgabenBis}`,
        token,
        fetch,
      ),
      kalenderBffFetch<{ konflikte?: Konflikt[] }>(
        baseUrl,
        `/api/planung/konflikte?von=${aufgabenVon}&bis=${aufgabenBis}`,
        token,
        fetch,
      ),
    ]);
    if (konflikteRes.status === 'fulfilled' && Array.isArray(konflikteRes.value?.konflikte)) {
      konflikte = konflikteRes.value.konflikte;
    }

    if (upcomingRes.status === 'fulfilled') {
      upcoming = upcomingRes.value;
    } else {
      failures.bff = String(upcomingRes.reason);
    }

    // Kalender-Liste ist nur Deko (Filter-Pills + Farben), ein Fehler hier
    // darf die Terminliste nicht kippen, daher kein Eintrag in `failures`.
    if (calendarsRes.status === 'fulfilled' && Array.isArray(calendarsRes.value)) {
      calendars = calendarsRes.value;
    }
    // Aufgaben & Ziele fail-soft: ein Fehler darf die Terminliste nicht kippen.
    if (todosRes.status === 'fulfilled' && Array.isArray(todosRes.value)) {
      todos = todosRes.value;
    }
    if (goalsRes.status === 'fulfilled' && Array.isArray(goalsRes.value)) {
      goals = goalsRes.value;
    }
    if (projectsRes.status === 'fulfilled' && Array.isArray(projectsRes.value)) {
      projects = projectsRes.value;
    }
    // Adaptiver Sekretär fail-soft: fehlt er, bleibt der Kalender voll nutzbar.
    if (assistantRes.status === 'fulfilled' && assistantRes.value && typeof assistantRes.value === 'object') {
      assistant = assistantRes.value;
    }
    // Bewertbare Aktivitäten fail-soft: fehlen sie, bleibt der Rest nutzbar.
    if (reviewableRes.status === 'fulfilled' && reviewableRes.value && Array.isArray(reviewableRes.value.activities)) {
      reviewable = reviewableRes.value.activities;
    }
    // Gelernte Erkenntnisse fail-soft (leer = Panel erscheint einfach nicht).
    if (insightsRes.status === 'fulfilled' && insightsRes.value && Array.isArray(insightsRes.value.insights)) {
      insights = insightsRes.value.insights;
    }
    // Gewohnheiten fail-soft wie der Rest: ein Fehler hier darf die Terminliste
    // nicht kippen.
    if (habitProgressRes.status === 'fulfilled' && Array.isArray(habitProgressRes.value)) {
      habitProgress = habitProgressRes.value;
    }
    if (habitSessionsRes.status === 'fulfilled' && Array.isArray(habitSessionsRes.value)) {
      const [heute_, kommend] = habitSessionsRes.value;
      // Beide Listen überlappen: eine Sitzung von heute Abend steht in
      // „today" UND in „upcoming". Ohne Entdopplung erschiene sie zweimal,
      // und bei einer offenen Sitzung stünden zwei Sätze Antwortknöpfe da,
      // von denen der zweite nach dem ersten Klick ins Leere ginge.
      const gesehen = new Set<string>();
      habitSessions = [...(heute_ ?? []), ...(kommend ?? [])]
        .filter((s) => s && s.id && !gesehen.has(s.id) && gesehen.add(s.id))
        .sort((a, b) => String(a.start).localeCompare(String(b.start)));
    }
    // Tagesdecke fail-soft: fehlt sie, bleibt der uebrige Kalender nutzbar.
    if (deckeRes.status === 'fulfilled' && deckeRes.value && Array.isArray(deckeRes.value.bloecke)) {
      tagesdecke = deckeRes.value;
    }

    // Zeit von Hand fail-soft, aber nicht stumm: ohne Timer-Stand liesse sich
    // ein laufender Timer nicht stoppen, und das soll man sehen.
    if (zeitRes.status === 'fulfilled' && zeitRes.value) {
      zeitTimer = zeitRes.value.laeuft ?? null;
      zeitBelege = (zeitRes.value.belege ?? []).map((b) => b.verweis);
    } else {
      zeitFehler = 'Timer und Haken sind gerade nicht erreichbar.';
    }
    if (heuteRes.status === 'fulfilled' && Array.isArray(heuteRes.value?.items)) {
      termineHeute = heuteRes.value.items;
    }

    // ── Notizen zu den angezeigten Terminen ──
    // In EINEM Aufruf für alle sichtbaren Termine, nicht je Zeile: eine
    // Monatsansicht zeigt leicht zweihundert Termine, und zweihundert Anfragen
    // wären ein Sturm auf einen Dienst, der eine Nebensache liefert.
    const kennungen = (upcoming?.items ?? []).map(terminKennung);
    const notizen = await notizenZu('termin', kennungen, notizAnschluss(locals, fetch));
    notizenNach = notizen.nach;
    notizenStumm = notizen.stumm;

    // ── Geplante Aufgaben (seit 2026-11-11) ──
    // Erst nach den Notizen: sie gehoeren zu Terminen, nicht zu Aufgaben.
    // Fail-soft: ohne Aufgaben-Dienst bleibt die Terminliste, wie sie ist.
    if (aufgabenRes.status === 'fulfilled' && Array.isArray(aufgabenRes.value)) {
      const eintraege = aufgabenRes.value
        .map(aufgabeAlsTermin)
        .filter((e): e is KalenderEvent => e !== null);
      if (eintraege.length > 0) {
        const alle = [...(upcoming?.items ?? []), ...eintraege];
        alle.sort((a, b) => startOf(a).localeCompare(startOf(b)));
        upcoming = upcoming
          ? { ...upcoming, items: alle }
          : { user: '', from: aufgabenVon, to: aufgabenBis, items: alle };
      }
      calendars = [...calendars, { id: AUFGABEN_KALENDER, name: 'Aufgaben', color: AUFGABEN_FARBE }];
    }
  }

  const deck = await deckLauf;
  // Auswahl: laufende Projekte, eingerueckt nach der Gliederung.
  const projektZeilen: BaumZeile[] = projektBaum(
    deck.filter((p) => !['archived', 'shutdown'].includes(p.status ?? '')).map(ausDeck),
  );
  // Namen fuer die Marke: alle, auch archivierte (ein alter Termin behaelt seinen Namen).
  const projektNamen: Record<string, string> = Object.fromEntries(deck.map((p) => [p.slug, p.name]));

  return {
    projektZeilen,
    projektNamen,
    zeitTimer,
    zeitBelege,
    termineHeute,
    zeitFehler,
    tagesdecke,
    deckeTag,
    upcoming,
    notizenNach,
    notizenStumm,
    konflikte,
    calendars,
    todos,
    goals,
    projects,
    assistant,
    reviewable,
    insights,
    habitProgress,
    habitSessions,
    today,
    view,
    month,
    week,
    failures,
    days,
    selectedCalendar,
    allowedDays: ALLOWED_DAYS,
    prefillCapture,
    prefillDate,
  };
};

function bffCtx(locals: App.Locals): { base: string; token: string } | null {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) return null;
  return { base: env.KALENDER_BFF_BASE_URL, token: kalenderBffToken(locals.user, backendSecret()) };
}

// Naive Start/End aus dem Formular (datetime-local bzw. Datum bei ganztags).
// Bewusst OHNE UTC-Umrechnung, der native Kalender speichert naive = Berlin.
function eventTimes(
  fd: FormData,
): { start: string; end: string; all_day: boolean } | { error: string } {
  const allDay = fd.get('all_day') === 'on' || fd.get('all_day') === 'true';
  if (allDay) {
    const date = String(fd.get('start') ?? '').slice(0, 10);
    if (date.length < 10) return { error: 'Datum fehlt.' };
    return { start: `${date}T00:00:00`, end: `${date}T23:59:59`, all_day: true };
  }
  const norm = (v: string) => (v.length === 16 ? `${v}:00` : v); // datetime-local → +ss
  const start = norm(String(fd.get('start') ?? ''));
  const end = norm(String(fd.get('end') ?? ''));
  if (start.length < 19 || end.length < 19) return { error: 'Start und Ende angeben.' };
  if (start >= end) return { error: 'Start muss vor Ende liegen.' };
  return { start, end, all_day: false };
}

/**
 * Erinnerung aus dem Editor (seit 2026-11-21): Minuten vor Beginn, leer = keine.
 * Beim Aendern heisst „keine" -1, weil der BFF ``null`` als „unveraendert" liest.
 */
function erinnerungFeld(fd: FormData, aendern: boolean): { reminder_minutes?: number | null } | { fehler: string } {
  const roh = fd.get('reminder_minutes');
  if (roh === null) return {};
  const text = String(roh).trim();
  if (text === '') return aendern ? { reminder_minutes: -1 } : {};
  const n = Number(text);
  if (!Number.isInteger(n) || n < 0 || n > 10080) return { fehler: 'Erinnerung unlesbar.' };
  return { reminder_minutes: n };
}

export const actions: Actions = {
  /**
   * Notiz zum Termin: neu anlegen oder eine vorhandene anhängen.
   *
   * Der Knopf sitzt am Termin und nicht in den Notizen, weil genau das der
   * Grund war, warum die Verknüpfungen seit ihrem Bau null Mal benutzt wurden:
   * niemand sitzt in den Notizen und sucht einen Termin.
   *
   * Die ganze Prüfung liegt in `notizDazuAusFormular`, damit Kalender,
   * Aufgaben und ProjectDeck nicht drei verschiedene Fehlerbilder bekommen.
   */
  notizDazu: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'nicht angemeldet' });
    const erg = await notizDazuAusFormular(await request.formData(), notizAnschluss(locals, fetch));
    if (!erg.ok) return fail(400, { notizFehler: erg.fehler });
    return { notiz: erg.notiz };
  },

  // ── Tagesdecke ──
  // Den Tag festhalten, damit er korrigierbar wird. Danach ändert ein später
  // verschobener Termin ihn nicht mehr: ein gelebter Tag ist ein Protokoll.
  deckeFestschreiben: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const datum = String(fd.get('datum') ?? '').slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datum)) return fail(400, { error: 'Datum fehlt.' });
    try {
      await kalenderBffFetch(
        ctx.base,
        `/api/tagesdecke/festschreiben?datum=${datum}`,
        ctx.token,
        fetch,
        { method: 'POST' },
      );
      return { deckeOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Neue Reihenfolge nach dem Ziehen. Ein Aufruf für den ganzen Tag: die Decke
  // ist lückenlos, ein verschobener Block verschiebt alles dahinter. Als Folge
  // einzelner Aufrufe könnte der Lauf mittendrin abbrechen und Löcher
  // hinterlassen, und die Lückenlosigkeit ist die Zusage der Decke.
  deckeNeuOrdnen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const datum = String(fd.get('datum') ?? '').slice(0, 10);
    const roh = String(fd.get('reihenfolge') ?? '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datum)) return fail(400, { error: 'Datum fehlt.' });
    const reihenfolge = roh.split(',').filter(Boolean);
    if (reihenfolge.length === 0) return fail(400, { error: 'Keine Reihenfolge übergeben.' });
    try {
      await kalenderBffFetch(ctx.base, '/api/tagesdecke/neu-ordnen', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ datum, reihenfolge }),
      });
      return { deckeOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Herausgezogen heißt „hat nicht stattgefunden", nicht „löschen". Der Block
  // bleibt als Zeile: was regelmäßig geplant wird und nie geschieht, ist das
  // aussagekräftigste Signal, das dieser Kalender erzeugt.
  deckeBlockVerwerfen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const blockId = String(fd.get('block_id') ?? '').trim();
    if (!blockId) return fail(400, { error: 'Block fehlt.' });
    try {
      await kalenderBffFetch(
        ctx.base,
        `/api/tagesdecke/block/${encodeURIComponent(blockId)}`,
        ctx.token,
        fetch,
        { method: 'DELETE' },
      );
      return { deckeOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Einen Block selbst setzen, etwa das, was man stattdessen getan hat.
  deckeBlockAnlegen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const datum = String(fd.get('datum') ?? '').slice(0, 10);
    const titel = String(fd.get('titel') ?? '').trim().slice(0, 300);
    const art = String(fd.get('art') ?? '').trim();
    const zeiten = eventTimes(fd);
    if ('error' in zeiten) return fail(400, { error: zeiten.error });
    if (!/^\d{4}-\d{2}-\d{2}$/.test(datum)) return fail(400, { error: 'Datum fehlt.' });
    if (!titel) return fail(400, { error: 'Titel fehlt.' });
    try {
      await kalenderBffFetch(ctx.base, '/api/tagesdecke/block', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ datum, start: zeiten.start, ende: zeiten.end, art, titel }),
      });
      return { deckeOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // ── Morgen-Check-in (adaptiver Sekretär) ──
  // Setzt Schlaf/Energie/Stimmung/körperlich → Kapazität + Vorschläge passen sich an.
  checkin: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const body: Record<string, unknown> = {};
    const pick = (k: string) => {
      const v = String(fd.get(k) ?? '').trim();
      if (v) body[k] = v;
    };
    pick('sleep_quality');
    pick('energy');
    pick('mood');
    const phys = String(fd.get('physical_ready') ?? '').trim();
    if (phys === 'true' || phys === 'false') body.physical_ready = phys === 'true';
    const note = String(fd.get('note') ?? '').trim();
    if (note) body.note = note.slice(0, 1000);
    try {
      await kalenderBffFetch(ctx.base, '/api/assistant/checkin', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return { checkinOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // ── Aktivitäts-Feedback (Randnotiz nach der Aktivität) ──
  // Rating (energy_after/satisfaction) + optionale Notiz zu einer vergangenen
  // Aktivitäts-Instanz → speist Vorschläge/Planung.
  activityFeedback: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const event_id = String(fd.get('event_id') ?? '').trim();
    if (!event_id) return fail(400, { error: 'event_id fehlt' });
    const body: Record<string, unknown> = { event_id };
    const occ = String(fd.get('occurrence_date') ?? '').trim();
    if (occ) body.occurrence_date = occ;
    const energy = String(fd.get('energy_after') ?? '').trim();
    if (energy) body.energy_after = energy;
    const sat = String(fd.get('satisfaction') ?? '').trim();
    if (sat) body.satisfaction = sat;
    if (String(fd.get('took_place') ?? '').trim() === 'false') body.took_place = false;
    const note = String(fd.get('note') ?? '').trim();
    if (note) body.note = note.slice(0, 2000);
    try {
      await kalenderBffFetch(ctx.base, '/api/feedback', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return { feedbackOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // ── „Plane meinen Tag" (aktive, präferenz-bewusste Tagesplanung) ──
  // commit=false → Vorschau (Slots + Begründung je Aufgabe); commit=true → verbindlich
  // einplanen (reversibel, nur Pool-Todos). Zweistufig wie QuickCapture (Vorschau → Bestätigen).
  planDay: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const date = String(fd.get('date') ?? '').trim();
    const commit = String(fd.get('commit') ?? '').trim() === 'true';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return fail(400, { error: 'Datum fehlt' });
    try {
      const plan = await kalenderBffFetch<PlanResult>(ctx.base, '/api/assistant/plan-day', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date, commit }),
      });
      return { plan, planCommitted: commit };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Freitext parsen → Vorschlag (legt nichts an).
  captureParse: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const text = String(fd.get('text') ?? '').trim();
    if (!text) return fail(400, { error: 'Bitte etwas eingeben.' });
    try {
      const suggestion = await kalenderBffFetch<CaptureSuggestion>(
        ctx.base,
        '/api/capture',
        ctx.token,
        fetch,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, allow_llm: false }),
        },
      );
      return { parsed: suggestion };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // Bestätigten Vorschlag verbindlich anlegen.
  captureCommit: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const body = {
      type: String(fd.get('type') ?? 'event'),
      title: String(fd.get('title') ?? '').trim(),
      date: String(fd.get('date') ?? '') || null,
      start_time: String(fd.get('start_time') ?? '') || null,
      end_time: String(fd.get('end_time') ?? '') || null,
      dauer_min: Number(fd.get('dauer_min') ?? '') || null,
      wiederholung: String(fd.get('wiederholung') ?? '') || null,
    };
    if (!body.title) return fail(400, { error: 'Titel fehlt.' });
    try {
      const created = await kalenderBffFetch<{ type: string; title: string }>(
        ctx.base,
        '/api/capture/commit',
        ctx.token,
        fetch,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
      );
      return { committed: created };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /**
   * Antwort auf einen Sitzungsvorschlag des Habit-Schedulers.
   *
   * Kein CRUD, sondern der Eingriff in den Automatismus: `dismissed` gibt den
   * Slot frei, worauf der native Scheduler in derselben Woche selbständig einen
   * Ersatz sucht. Bis diese Action existierte, gab es in Saganta keinen Weg,
   * einen Vorschlag zu beantworten, er lief stumm aus.
   *
   * Die vier erlaubten Werte stehen hier ausdrücklich statt durchgereicht: ein
   * Tippfehler soll hier scheitern und nicht als unbekannte Aktion beim BFF
   * ankommen, wo die Ursache schwerer zu sehen wäre.
   */
  sitzungAktion: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const aktion = String(fd.get('aktion') ?? '');
    if (!id) return fail(400, { error: 'id fehlt' });
    if (!['accepted', 'dismissed', 'cancelled', 'start_early', 'nicht_gemacht'].includes(aktion)) {
      return fail(400, { error: `unbekannte Aktion: ${aktion}` });
    }
    try {
      await kalenderBffFetch(ctx.base, `/api/habits/sessions/${id}/action`, ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: aktion }),
      });
      return { habitOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // ── Zeit von Hand (seit 2026-11-08, wie die App) ──
  zeitStart: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const titel = String(fd.get('titel') ?? '').trim().slice(0, 300);
    const bezugTyp = String(fd.get('bezug_typ') ?? '');
    const bezugId = String(fd.get('bezug_id') ?? '');
    if (!titel) return fail(400, { error: 'Titel fehlt.' });
    if (!['event', 'session'].includes(bezugTyp) || !bezugId) return fail(400, { error: 'Bezug fehlt.' });
    try {
      await kalenderBffFetch(ctx.base, '/api/zeit/timer/start', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titel, bezug_typ: bezugTyp, bezug_id: bezugId }),
      });
      return { zeitOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  zeitStopp: async ({ locals, fetch }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    try {
      await kalenderBffFetch(ctx.base, '/api/zeit/timer/stopp', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      return { zeitOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /** Nachtraeglich abhaken. Ein Ende in der Zukunft lehnt der Dienst ab; die Seite prueft das vorher. */
  zeitHaken: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const titel = String(fd.get('titel') ?? '').trim().slice(0, 300);
    const bezugTyp = String(fd.get('bezug_typ') ?? '');
    const bezugId = String(fd.get('bezug_id') ?? '');
    const start = String(fd.get('start') ?? '');
    const ende = String(fd.get('ende') ?? '');
    const zeit = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
    if (!titel) return fail(400, { error: 'Titel fehlt.' });
    if (!['event', 'session'].includes(bezugTyp) || !bezugId) return fail(400, { error: 'Bezug fehlt.' });
    if (!zeit.test(start) || !zeit.test(ende) || ende <= start) return fail(400, { error: 'Zeiten prüfen.' });
    try {
      await kalenderBffFetch(ctx.base, '/api/zeit/haken', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titel, start, ende, bezug_typ: bezugTyp, bezug_id: bezugId }),
      });
      return { zeitOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /** Zeit fuer eine Gewohnheit ohne geplante Sitzung (seit 2026-11-13). */
  zeitNachtragen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const habitId = String(fd.get('habit_id') ?? '').trim();
    const start = String(fd.get('start') ?? '');
    const ende = String(fd.get('ende') ?? '');
    const zeit = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
    if (!habitId) return fail(400, { error: 'Gewohnheit fehlt.' });
    if (!zeit.test(start) || !zeit.test(ende) || ende <= start) return fail(400, { error: 'Zeiten prüfen.' });
    try {
      await kalenderBffFetch(ctx.base, '/api/zeit/nachtragen', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ habit_id: habitId, start, ende }),
      });
      return { zeitOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // ── Termine (Events) ──
  eventCreate: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const title = String(fd.get('title') ?? '').trim();
    const calendar_id = String(fd.get('calendar_id') ?? '').trim();
    if (!title) return fail(400, { error: 'Titel fehlt.' });
    if (!calendar_id) return fail(400, { error: 'Kalender fehlt.' });
    const times = eventTimes(fd);
    if ('error' in times) return fail(400, { error: times.error });
    const activityType = String(fd.get('activity_type') ?? '').trim();
    const projekt = projektFeld(String(fd.get('projekt') ?? ''), null, false);
    if ('fehler' in projekt) return fail(400, { error: projekt.fehler });
    const erinnerung = erinnerungFeld(fd, false);
    if ('fehler' in erinnerung) return fail(400, { error: erinnerung.fehler });
    try {
      await kalenderBffFetch(ctx.base, '/api/events', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          calendar_id,
          title,
          location: String(fd.get('location') ?? '').trim() || null,
          activity_type: activityType || null,
          ...projekt,
          ...erinnerung,
          ...times,
        }),
      });
      return { eventOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  eventUpdate: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    const title = String(fd.get('title') ?? '').trim();
    if (!id) return fail(400, { error: 'id fehlt' });
    if (!title) return fail(400, { error: 'Titel fehlt.' });
    const times = eventTimes(fd);
    if ('error' in times) return fail(400, { error: times.error });
    const body: Record<string, unknown> = {
      title,
      location: String(fd.get('location') ?? '').trim() || null,
      ...times,
      // "" → null entfernt die Aktivitäts-Markierung; sonst die gewählte Kategorie.
      activity_type: String(fd.get('activity_type') ?? '').trim() || null,
    };
    const calendar_id = String(fd.get('calendar_id') ?? '').trim();
    if (calendar_id) body.calendar_id = calendar_id;
    // Projekt nur bei einer Aenderung: fehlte die Projektliste, zeigte das Feld
    // „kein Projekt", und ein blindes Leeren loeste den Bezug still.
    const altRoh = fd.get('projekt_alt');
    const projekt = projektFeld(String(fd.get('projekt') ?? ''), altRoh === null ? null : String(altRoh), true);
    if ('fehler' in projekt) return fail(400, { error: projekt.fehler });
    Object.assign(body, projekt);
    const erinnerung = erinnerungFeld(fd, true);
    if ('fehler' in erinnerung) return fail(400, { error: erinnerung.fehler });
    Object.assign(body, erinnerung);
    try {
      await kalenderBffFetch(ctx.base, `/api/events/${id}`, ctx.token, fetch, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return { eventOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /**
   * Termin löschen, bei einer Serie mit Wahl, was genau entfällt.
   *
   * Bis 2026-08-25 kannte diese Action nur „ganze Reihe". Ein Klick auf das ✕
   * neben einem einzelnen Serientermin löschte damit **die komplette Serie, ohne
   * Rückfrage**. Wer einen Termin absagen wollte, verlor die Reihe. Die Engine
   * kann Einzelabsage (EXDATE) und Abbruch ab Datum (UNTIL) seit jeher; es
   * reichte nur kein Client durch.
   *
   * `modus`:
   *   `serie`: ganze Reihe bzw. Einzeltermin (Bestandsverhalten, Vorgabe)
   *   `vorkommen`: nur dieses eine Datum
   *   `ab_hier`: dieses und alle folgenden
   */
  /**
   * Termin per Ziehen in der Woche verschieben (seit 2026-11-07). Nur Beginn
   * und Ende gehen hinaus, der bff nimmt Teilaenderungen (`EventPatch`).
   *
   * Ein Serien-Vorkommen (`basis::datum`) geht seit 2026-11-14 ueber
   * `/api/planung/konflikt/loesen`: EXDATE an der Serie plus Einzeltermin zur
   * neuen Zeit, die Reihe bleibt fuer alle anderen Wochen stehen. Vorher war
   * Ziehen fuer Serien gesperrt, und Lagerlogistik, Filmabend und jede andere
   * Wiederholung liess sich in der Woche nicht anfassen.
   */
  eventVerschieben: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    // datetime-local liefert ohne Sekunden, das Ziehen mit: beides annehmen.
    const mitSekunden = (t: string) => (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(t) ? `${t}:00` : t);
    const start = mitSekunden(String(fd.get('start') ?? ''));
    const end = mitSekunden(String(fd.get('end') ?? ''));
    const iso = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/;
    if (!id) return fail(400, { error: 'id fehlt' });
    if (!iso.test(start) || !iso.test(end) || start >= end) return fail(400, { error: 'Zeit unlesbar.' });
    try {
      if (id.includes('::')) {
        await kalenderBffFetch(ctx.base, '/api/planung/konflikt/loesen', ctx.token, fetch, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ art: 'termin', id, aktion: 'verschieben', start, ende: end }),
        });
      } else {
        await kalenderBffFetch(ctx.base, `/api/events/${encodeURIComponent(id)}`, ctx.token, fetch, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ start, end }),
        });
      }
      return { eventOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /**
   * „Rueckgaengig" nach dem Loeschen eines Einzeltermins (seit 2026-11-21): legt
   * ihn mit denselben Feldern neu an. Der Termin bekommt dabei eine neue Kennung;
   * Notizen, die am alten hingen, haengen nicht mehr daran.
   */
  eventWiederherstellen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    let t: Record<string, unknown>;
    try {
      t = JSON.parse(String(fd.get('termin') ?? ''));
    } catch {
      return fail(400, { error: 'Termin unlesbar.' });
    }
    const iso = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/;
    if (typeof t?.title !== 'string' || !t.title || typeof t.calendar_id !== 'string'
      || !iso.test(String(t.start)) || !iso.test(String(t.end))) {
      return fail(400, { error: 'Termin unvollständig.' });
    }
    const erlaubt = ['calendar_id', 'title', 'start', 'end', 'all_day', 'location', 'description',
      'reminder_minutes', 'activity_type', 'projekt'];
    const rumpf = Object.fromEntries(Object.entries(t).filter(([k, v]) => erlaubt.includes(k) && v !== null && v !== ''));
    try {
      await kalenderBffFetch(ctx.base, '/api/events', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rumpf),
      });
      return { eventOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /** Wege fuer ein ueberlappendes Paar, gerechnet im nativen Dienst. */
  konfliktVorschlag: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    let paar: unknown;
    try {
      paar = JSON.parse(String(fd.get('paar') ?? ''));
    } catch {
      return fail(400, { error: 'Paar unlesbar.' });
    }
    try {
      const antwort = await kalenderBffFetch<KonfliktVorschlag & { optionen?: { aktion: string; start?: string; ende?: string }[] }>(
        ctx.base,
        '/api/planung/konflikt/vorschlag',
        ctx.token,
        fetch,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(paar) },
      );
      // Ein aelterer Dienst kennt `wege` nicht und liefert nur `optionen` fuer
      // den Weichenden: daraus dieselbe Form bauen, damit die Knoepfe da sind.
      if (!Array.isArray(antwort.wege) && antwort.weicht) {
        const w = antwort.weicht;
        antwort.wege = (antwort.optionen ?? []).map((o) => ({
          aktion: o.aktion as KonfliktWeg['aktion'],
          ziel: { art: w.art, id: w.id, titel: w.titel },
          start: o.start,
          ende: o.ende,
          text: o.aktion === 'aussetzen' ? `„${w.titel}“ diesmal aussetzen` : `„${w.titel}“ auf ${(o.start ?? '').slice(11, 16)} verschieben`,
        }));
      }
      return { vorschlag: antwort };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /** Einen Weg ausfuehren: verschieben, kuerzen, aussetzen, loeschen. */
  konfliktLoesen: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const art = String(fd.get('art') ?? '');
    const id = String(fd.get('id') ?? '');
    const aktion = String(fd.get('aktion') ?? '');
    const start = String(fd.get('start') ?? '');
    const ende = String(fd.get('ende') ?? '');
    if (!['termin', 'sitzung'].includes(art) || !id) return fail(400, { error: 'Ziel fehlt.' });
    if (!['verschieben', 'kuerzen', 'aussetzen', 'loeschen'].includes(aktion)) {
      return fail(400, { error: `unbekannte Aktion: ${aktion}` });
    }
    const rumpf: Record<string, string> = { art, id, aktion };
    if (start) rumpf.start = start;
    if (ende) rumpf.ende = ende;
    try {
      await kalenderBffFetch(ctx.base, '/api/planung/konflikt/loesen', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rumpf),
      });
      return { eventOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  eventDelete: async ({ locals, fetch, request }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const fd = await request.formData();
    const id = String(fd.get('id') ?? '');
    if (!id) return fail(400, { error: 'id fehlt' });
    const modus = String(fd.get('modus') ?? 'serie');
    if (!['serie', 'vorkommen', 'ab_hier'].includes(modus)) {
      return fail(400, { error: `unbekannter Modus: ${modus}` });
    }

    // Instanz-IDs tragen die Form `basis::JJJJ-MM-TT`. Für die feinen Wege wird
    // das Datum gebraucht; fehlt es, ist die Anfrage nicht ausführbar, dann
    // lieber ablehnen als auf „ganze Serie" zurückfallen, denn das wäre genau
    // die stille Eskalation, die hier abgestellt werden soll.
    const tag = id.includes('::') ? id.split('::')[1]!.slice(0, 10) : String(fd.get('tag') ?? '');
    if (modus !== 'serie' && !/^\d{4}-\d{2}-\d{2}$/.test(tag)) {
      return fail(400, { error: 'Datum des Vorkommens fehlt' });
    }

    const pfad =
      modus === 'vorkommen'
        ? `/api/events/${id}/instances/${tag}`
        : modus === 'ab_hier'
          ? `/api/events/${id}/truncate?occ_date=${tag}`
          : `/api/events/${id}`;
    const methode = modus === 'ab_hier' ? 'POST' : 'DELETE';
    try {
      await kalenderBffFetch(ctx.base, pfad, ctx.token, fetch, { method: methode });
      return { eventOk: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  // ── Feierabend heute ──
  // Sagt die heute noch offene Routine ab (EXDATE), stellt den Sekretär auf
  // „schonen" und verplant das Abgesagte in freie Slots der Folgetage. „Heute"
  // + „jetzt" hier in Berlin-Zeit via Intl bestimmen (der Node-Prozess läuft auf
  // UTC, hat aber ICU-TZ-Daten) und an den BFF geben.
  feierabend: async ({ locals, fetch }) => {
    const ctx = bffCtx(locals);
    if (!ctx) return fail(401, { error: 'nicht angemeldet' });
    const now = new Date();
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(now);
    const hm = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/Berlin',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(now);
    const [h, m] = hm.split(':');
    const nowMinutes = (Number.parseInt(h ?? '0', 10) || 0) * 60 + (Number.parseInt(m ?? '0', 10) || 0);
    try {
      const res = await kalenderBffFetch<{ date: string; cancelled: unknown[]; planned: unknown[] }>(
        ctx.base,
        '/api/feierabend',
        ctx.token,
        fetch,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ date: today, now_minutes: nowMinutes, replan: true, checkin: true }),
        },
      );
      return { feierabend: res };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },
};
