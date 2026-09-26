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
  type KalenderGoal,
  type KalenderProject,
  type KalenderTodo,
  type PlanResult,
  type ReviewableActivity,
  type ReviewableResponse,
  type Tagesdecke,
  type UpcomingResponse,
} from '$lib/kalender-bff';
import { weekGridDays } from '$lib/cal';
import type { Actions, PageServerLoad } from './$types';

const ALLOWED_DAYS = [7, 14, 30] as const;

interface CaptureSuggestion {
  type: 'event' | 'todo';
  title: string;
  date: string | null;
  start_time: string | null;
  end_time: string | null;
  confidence?: string;
  source?: string;
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

  // Heute in Haus-Zeitzone (Tagesziele + Default-Datum neuer Einträge). en-CA → YYYY-MM-DD.
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(new Date());

  // Ansicht: Agenda (Liste) / Monat (6×7-Grid) / Woche (Stunden-Grid).
  // Monat via ?month=YYYY-MM, Woche via ?week=YYYY-MM-DD (Anker) navigierbar.
  // Standard = Monat: der Kalender-Eindruck steht sofort. Agenda/Woche via ?view=.
  const viewParam = url.searchParams.get('view');
  const view = viewParam === 'list' ? 'list' : viewParam === 'week' ? 'week' : 'month';
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

  if (locals.user && env.KALENDER_BFF_BASE_URL) {
    const token = kalenderBffToken(locals.user, backendSecret());
    const baseUrl = env.KALENDER_BFF_BASE_URL;

    let eventsPath: string;
    if (view === 'month') {
      const rng = monthRange(month);
      eventsPath = `/api/events/range?start=${rng.start}&end=${rng.end}`;
    } else if (view === 'week') {
      const wd = weekGridDays(week);
      eventsPath = `/api/events/range?start=${wd[0]}&end=${wd[6]}`;
    } else {
      eventsPath = `/api/events/upcoming?days=${days}&limit=200`;
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
    ] = await Promise.allSettled([
      kalenderBffFetch<UpcomingResponse>(baseUrl, eventsPath, token, fetch),
      kalenderBffFetch<KalenderCalendar[]>(baseUrl, '/api/events/calendars', token, fetch),
      // ★ Nur noch fuer die Zaehlung auf der Kachel: verwaltet werden Aufgaben
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
    ]);

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
      // ★ Beide Listen überlappen: eine Sitzung von heute Abend steht in
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
  }

  return {
    tagesdecke,
    deckeTag,
    upcoming,
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

export const actions: Actions = {
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
   * ★ Kein CRUD, sondern der Eingriff in den Automatismus: `dismissed` gibt den
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
    if (!['accepted', 'dismissed', 'cancelled', 'start_early'].includes(aktion)) {
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
    try {
      await kalenderBffFetch(ctx.base, '/api/events', ctx.token, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          calendar_id,
          title,
          location: String(fd.get('location') ?? '').trim() || null,
          activity_type: activityType || null,
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
   * ★ Bis 2026-08-25 kannte diese Action nur „ganze Reihe". Ein Klick auf das ✕
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
