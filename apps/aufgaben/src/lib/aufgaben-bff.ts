/**
 * Zugriff auf den Kalender-BFF, der die Aufgaben fuehrt.
 *
 * ★ **Diese App hat bewusst keine eigene Datenbank.** Aufgaben, Tagesziele und
 * Projekte liegen in derselben Engine wie die Termine (`kalender:8085`), und
 * das ist der Punkt: eine Aufgabe mit Zeitfenster IST ein Termin, und die
 * Tagesplanung des Kalenders greift auf denselben Bestand zu. Eine zweite
 * Aufgaben-Datenbank waere ein Datenduplikat mit zwei Wahrheiten, und die
 * Verknuepfung Aufgabe/Termin muesste dann ueber die App-Grenze gehen, statt
 * eine Fremdschluesselbeziehung zu sein.
 *
 * Ausgelagert wurde also die **Oberflaeche**, nicht die Daten. Der Kalender
 * zeigt seither nur noch, was heute ansteht; alles Verwaltende liegt hier.
 */
import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

/** Aufgabe (native Todo). Felder defensiv optional: nicht hier versioniert. */
export interface Aufgabe {
  id: string;
  title: string;
  description?: string | null;
  /** niedrig | mittel | hoch | dringend */
  priority: string;
  due_date?: string | null;
  due_time?: string | null;
  completed: boolean;
  completed_at?: string | null;
  /** open | done | cancelled */
  status?: string;
  estimated_minutes?: number | null;
  /** pool = planbar, fixed = fest gesetzt */
  scheduling_mode?: string;
  planned_date?: string | null;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  earliest_start_date?: string | null;
  /** hoch | mittel | niedrig */
  energy_required?: string | null;
  project_id?: string | null;
  goal_id?: string | null;
  recurrence?: string | null;
  /** Wie oft die Aufgabe schon verschoben wurde. Traegt die Verfall-Warnung. */
  defer_count?: number;
  last_deferred_at?: string | null;
  defer_reason?: string | null;
}

/** Tagesziel (native DailyGoal, A/B/C). */
export interface Ziel {
  id: string;
  title: string;
  description?: string | null;
  date: string;
  /** A | B | C */
  priority: string;
  /** open | achieved | abandoned */
  status: string;
  estimated_minutes?: number | null;
}

/** Projekt. Gemeinsamer Bestand mit ProjectDeck. */
export interface Projekt {
  id: string;
  name: string;
  color?: string | null;
  icon?: string | null;
  status?: string;
  slug?: string | null;
}

/** Ein Termin, soweit die Aufgabenliste ihn braucht (belegte Zeit). */
export interface Termin {
  id: string;
  title: string;
  start_at?: string;
  end_at?: string;
  start?: string;
  end?: string;
  all_day?: boolean;
  calendar_id?: string;
}

/**
 * Ergebnis von „Tag planen".
 *
 * `commit=false` ist eine Vorschau und aendert nichts; `commit=true` schreibt
 * die Zeitfenster. Genau diese Zweistufigkeit traegt die Rueckfrage, die diese
 * App dem Vorschlags-Stapel vorzieht.
 */
export interface Planung {
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

/** Tageskapazitaet aus dem Check-in. Entscheidet, wie viel geplant wird. */
export interface Kapazitaet {
  date: string;
  day_type: string;
  level: 'geladen' | 'normal' | 'geschont' | 'erschöpft';
  score: number;
  factor: number;
  cap_minutes: number;
  allow_physical: boolean;
  max_task_energy: string;
  has_checkin: boolean;
  strain: number;
  strain_level: string;
  reason: string;
}

/** Eine chronisch aufgeschobene Aufgabe. */
export interface Liegengeblieben {
  todo_id: string;
  title: string;
  defer_count: number;
  due_date: string | null;
}

/** Tagesbild des Sekretaers, soweit diese App es braucht. */
export interface Tagesbild {
  date?: string;
  day_type?: string;
  capacity?: Kapazitaet;
  has_checkin?: boolean;
  free_minutes?: number;
  next_free?: string | null;
  backlog?: Liegengeblieben[];
}

export const KALENDER_BFF_AUDIENCE = 'kalender-bff';

export function bffToken(user: SagantaUser, secret: string): string {
  return issueBackendToken({ user, secret, audience: KALENDER_BFF_AUDIENCE, ttlSeconds: 60 });
}

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) {
    throw new Error(
      'SAGANTA_BACKEND_SECRET ist nicht gesetzt, das Backend-Token kann nicht signiert werden.',
    );
  }
  return secret;
}

export async function bffFetch<T>(
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
  // 204 (z. B. DELETE) hat keinen Body, res.json() wuerde werfen.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Zugriffs-Kontext einer Action. `null`, solange kein Nutzer oder keine Adresse. */
export function bffCtx(locals: App.Locals): { base: string; token: string } | null {
  if (!locals.user || !env.KALENDER_BFF_BASE_URL) return null;
  return { base: env.KALENDER_BFF_BASE_URL, token: bffToken(locals.user, backendSecret()) };
}
