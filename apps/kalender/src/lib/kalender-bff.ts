import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export interface KalenderEvent {
  id: string;
  title: string;
  start_at?: string;
  end_at?: string;
  start?: string;
  end?: string;
  calendar_id?: string;
  location?: string;
  description?: string;
  all_day?: boolean;
  is_recurring_instance?: boolean;
  /**
   * iCal-RRULE der Reihe, falls es eine ist.
   *
   * ★ Wird zusätzlich zu ``is_recurring_instance`` gebraucht: beim **ersten**
   * Vorkommen einer Serie ist das Flag ``false`` (Start und Ende stimmen mit dem
   * Basistermin überein). Wer die Serienerkennung allein darauf stützt, behandelt
   * ausgerechnet den ersten Termin einer Reihe wie einen Einzeltermin.
   */
  recurrence_rule?: string | null;
  /** Basis-Reihe einer virtuellen Instanz (``id`` = ``series_id::datum``). */
  series_id?: string | null;
  reminder_minutes?: number | null;
  // Markiert ein Event als flexible, bewertbare Aktivität + Kategorie fürs Lernen.
  activity_type?: string | null; // lernen | sport | lesen | hobby | sonstige | null
}

/** Feedback zu einer Aktivitäts-Instanz (die „Randnotiz nach der Aktivität"). */
export interface ActivityFeedback {
  id: string;
  energy_after: string | null; // energetisiert | ok | erschöpft
  satisfaction: string | null; // gut | mittel | schlecht
  took_place: boolean;
  note: string | null;
  updated_at: string | null;
}

/** Eine bewertbare Aktivitäts-Instanz eines Tages (aus /api/feedback/reviewable). */
export interface ReviewableActivity {
  event_id: string;
  instance_id: string;
  occurrence_date: string;
  title: string;
  activity_type: string | null;
  start: string;
  end: string;
  time_status: string; // past | running | upcoming
  feedback: ActivityFeedback | null;
}

export interface ReviewableResponse {
  date: string;
  lookback?: number;
  activities: ReviewableActivity[];
}

/** Eine gelernte Erkenntnis über eine Aktivität (aus /api/feedback/insights). */
export interface ActivityInsight {
  activity_type: string;
  label: string;
  best_bucket: string;
  best_score: number;
  worst_bucket: string;
  worst_score: number;
  count: number;
  text: string;
}

export interface InsightsResponse {
  insights: ActivityInsight[];
  preferences: Record<string, unknown>;
}

export interface UpcomingResponse {
  user: string;
  from: string;
  to: string;
  items: KalenderEvent[];
}

/**
 * Kalender-Metadaten vom Upstream. Felder defensiv optional gehalten, der
 * native kalender:8085 ist nicht hier versioniert, also nie auf eine exakte
 * Form verlassen. `name`/`title` und `color` werden best-effort genutzt.
 */
export interface KalenderCalendar {
  id: string;
  name?: string;
  title?: string;
  color?: string;
}

/** Aufgabe (native Todo). Felder defensiv optional, nicht hier versioniert. */
export interface KalenderTodo {
  id: string;
  title: string;
  description?: string | null;
  priority: string; // niedrig | mittel | hoch | dringend
  due_date?: string | null;
  due_time?: string | null;
  completed: boolean;
  status?: string;
  estimated_minutes?: number | null;
  project_id?: string | null;
}

/** Projekt (native Project): Quelle der ProjectDeck-Verknüpfung. */
export interface KalenderProject {
  id: string;
  name: string;
  color?: string;
  icon?: string | null;
  status?: string;
}

/** Tagesziel (native DailyGoal, A/B/C). */
export interface KalenderGoal {
  id: string;
  title: string;
  description?: string | null;
  date: string;
  priority: string; // A | B | C
  status: string;
  estimated_minutes?: number | null;
}

/** Tageskapazität aus dem adaptiven Sekretär (Check-in + Day-Type + Strain). */
export interface KalenderCapacity {
  date: string;
  day_type: string;
  level: 'geladen' | 'normal' | 'geschont' | 'erschöpft';
  score: number;
  factor: number;
  cap_minutes: number;
  allow_physical: boolean;
  prefer_physical: boolean;
  max_task_energy: string;
  has_checkin: boolean;
  strain: number;
  strain_level: string;
  reason: string;
  checkin?: {
    sleep_quality?: string | null;
    energy?: string | null;
    mood?: string | null;
    physical_ready?: boolean | null;
    note?: string | null;
  } | null;
}

/** Ein einzelner „Was jetzt?"-Vorschlag. */
export interface KalenderSuggestion {
  id: string;
  kind: string; // sport | hobby | lesen | einkauf | todo | erholung
  title: string;
  subtitle: string;
  reason: string;
  energy: string; // hoch | mittel | niedrig
  duration_min: number;
  score: number;
  source: string;
  action?: Record<string, unknown>;
}

export interface KalenderChoice {
  prompt: string;
  context: string;
  options: KalenderSuggestion[];
}

/** Eine chronisch aufgeschobene Aufgabe (Backlog-Verfall-Warnung). */
export interface BacklogItem {
  todo_id: string;
  title: string;
  defer_count: number;
  due_date: string | null;
}

/** Ergebnis von „Plane meinen Tag" (Vorschau bei commit=false, sonst verbindlich). */
export interface PlanResult {
  date?: string;
  committed?: boolean;
  planned_minutes?: number;
  suggestions?: {
    todo_id: string;
    title: string;
    start?: string;
    end?: string;
    minutes: number;
    reason?: string | null;
  }[];
  deferred?: { todo_id: string; title: string; reason: string }[];
  free_slots?: { start: string; end: string; minutes: number }[];
}

/** Angereichertes Tagesbild (/api/assistant/today): defensiv optional. */
export interface AssistantToday {
  date?: string;
  weekday?: string;
  day_type?: string;
  capacity?: KalenderCapacity;
  has_checkin?: boolean;
  checkin?: KalenderCapacity['checkin'];
  suggestions?: KalenderSuggestion[];
  choice?: KalenderChoice | null;
  top_suggestion?: KalenderSuggestion | null;
  free_minutes?: number;
  next_free?: string | null;
  backlog?: BacklogItem[];
  progress?: {
    categories?: { category: string; done_minutes: number; target_minutes: number; pct: number }[];
    endangered_count?: number;
    endangered?: { name: string; remaining_minutes: number }[];
  };
}

/**
 * Gewohnheiten („Habits"): wiederkehrende Vorhaben mit Wochenziel, aus denen
 * der native Scheduler selbständig Sitzungen in freie Zeitfenster legt.
 *
 * ★ Das ist der Kern-Automatismus des Kalenders und war in dieser Oberfläche
 * bis 2026-08-25 **gar nicht sichtbar**: der BFF konnte die Routen seit dem
 * 20.08., das Frontend rief keine davon auf (`grep -ric habit src/` = 0). Wer
 * eine ntfy-Nachricht „Lernen 17:00–18:30" bekam und am Rechner saß, konnte
 * weder annehmen noch verwerfen, der Vorschlag lief stumm in `dismissed`,
 * sobald seine Zeit verstrich, und der Scheduler plante nach.
 */
export interface HabitProgress {
  habit_id: string;
  name: string;
  color?: string | null;
  /** Wochensoll in Stunden (Feldname je nach Backend-Fassung). */
  target_hours?: number;
  target_hours_per_week?: number;
  completed_hours?: number;
  done_hours?: number;
}

export interface HabitSession {
  id: string;
  habit_id?: string;
  habit_name?: string | null;
  habit_color?: string | null;
  start: string;
  end: string;
  /** pending → accepted → completed; dismissed/cancelled sind Absagen. */
  status: string;
}

/** Die vier Antworten, die der Scheduler versteht. */
export type SessionAction = 'accepted' | 'dismissed' | 'cancelled' | 'start_early';

export const KALENDER_BFF_AUDIENCE = 'kalender-bff';

export function kalenderBffToken(user: SagantaUser, secret: string): string {
  return issueBackendToken({
    user,
    secret,
    audience: KALENDER_BFF_AUDIENCE,
    ttlSeconds: 60,
  });
}

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt: Backend-Token kann nicht signiert werden.');
  return secret;
}

export async function kalenderBffFetch<T>(
  baseUrl: string,
  path: string,
  token: string,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetcher(`${baseUrl.replace(/\/$/, '')}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`kalender-bff ${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  // 204 (z. B. DELETE) hat keinen Body: res.json() würde werfen.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/**
 * Ein Block der Tagesdecke: ein benanntes Stück des wachen Tages.
 *
 * `id` ist `null`, solange der Tag offen ist. Die Decke wird dann bei jedem
 * Aufruf gerechnet, und ein Block ohne Kennung lässt sich folgerichtig nicht
 * verschieben oder verwerfen. Erst das Festschreiben macht aus der Rechnung
 * Zeilen.
 */
export interface TagesdeckeBlock {
  id: string | null;
  start: string;
  ende: string;
  minuten: number;
  art: string;
  titel: string;
  begruendung: string | null;
  status: string; // geplant | bestaetigt | verworfen
  herkunft_typ: string | null; // event | habit_session | todo | goal | null
}

export interface Tagesdecke {
  datum: string;
  wach_von: string;
  wach_bis: string;
  wach_minuten: number;
  verplant_minuten: number;
  offen_minuten: number;
  summe_je_art: Record<string, number>;
  bloecke: TagesdeckeBlock[];
  festgeschrieben: boolean;
  capacity?: { level?: string; reason?: string } | null;
  hinweise?: string[];
}
