/**
 * Der Weg zum Aufgaben-Dienst (`services/aufgaben-api`, seit 2026-11-03).
 *
 * Bis zum 03.11. lagen die Aufgaben im Kalender (`/api/todos` am
 * kalender-bff). Seit dem eigenen Dienst gehoeren sie dorthin; Tagesziele und
 * Tageskapazitaet bleiben im Kalender und kommen weiter ueber den BFF.
 *
 * Die Oberflaeche dieser App spricht weiter ihr bisheriges Format (`Aufgabe` in
 * `aufgaben-bff.ts`). Uebersetzt wird HIER und nirgends sonst: eine zweite
 * Uebersetzung in einer Komponente waere die Stelle, an der beim naechsten Feld
 * eine Seite das alte Wort liest.
 */
import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';
import { backendSecret, type Aufgabe, type Planung } from '$lib/aufgaben-bff';

export const AUFGABEN_API_AUDIENCE = 'aufgaben-api';

/** So liefert der Dienst eine Aufgabe. */
export interface DienstAufgabe {
  id: string;
  titel: string;
  notiz: string | null;
  prioritaet: 'hoch' | 'mittel' | 'niedrig';
  faellig: string | null;
  tag: string | null;
  termin_id: string | null;
  start: string | null;
  ende: string | null;
  dauer_min: number | null;
  energie: 'niedrig' | 'mittel' | 'hoch' | null;
  erledigt: boolean;
  erledigt_am: string | null;
  verschoben: number;
}

export interface DienstPlan {
  datum: string;
  festgelegt: boolean;
  minuten: number;
  vorschlaege: { aufgabe_id: string; titel: string; start: string; ende: string; minuten: number; grund: string | null }[];
  zurueck: { aufgabe_id: string; titel: string; grund: string }[];
  ohne_fenster: string[];
}

/** ⚠️ Der Dienst sagt Energie deutsch, die Oberflaeche (vom Kalender her) englisch. */
const ENERGIE_ZU_OBERFLAECHE = { niedrig: 'low', mittel: 'medium', hoch: 'high' } as const;
const ENERGIE_ZUM_DIENST: Record<string, 'niedrig' | 'mittel' | 'hoch'> = {
  low: 'niedrig',
  medium: 'mittel',
  high: 'hoch',
};

export function energieZumDienst(wert: string | null): 'niedrig' | 'mittel' | 'hoch' | null {
  return wert ? (ENERGIE_ZUM_DIENST[wert] ?? null) : null;
}

export function alsAufgabe(d: DienstAufgabe): Aufgabe {
  return {
    id: d.id,
    title: d.titel,
    description: d.notiz,
    priority: d.prioritaet,
    due_date: d.faellig,
    completed: d.erledigt,
    completed_at: d.erledigt_am,
    status: d.erledigt ? 'done' : 'open',
    estimated_minutes: d.dauer_min,
    planned_date: d.tag,
    scheduled_start: d.start,
    scheduled_end: d.ende,
    energy_required: d.energie ? ENERGIE_ZU_OBERFLAECHE[d.energie] : null,
    project_id: null,
    defer_count: d.verschoben,
  };
}

/** Der Plan im Format, das `Tagesplan.svelte` kennt. */
export function alsPlanung(p: DienstPlan): Planung {
  return {
    date: p.datum,
    committed: p.festgelegt,
    planned_minutes: p.minuten,
    suggestions: p.vorschlaege.map((v) => ({
      todo_id: v.aufgabe_id,
      title: v.titel,
      start: v.start,
      end: v.ende,
      minutes: v.minuten,
      reason: v.grund,
    })),
    deferred: [
      ...p.zurueck.map((z) => ({
        todo_id: z.aufgabe_id,
        title: z.titel,
        reason: z.grund === 'energie' ? 'zu anstrengend für heute' : z.grund === 'kapazitaet' ? 'der Tag ist voll genug' : z.grund,
      })),
      // Der Planer nennt diese nicht; ohne die Zeile saehe ein voller Tag aus
      // wie ein leerer Vorrat.
      // Eigene Kennung je Zeile: `Tagesplan.svelte` schluesselt nach todo_id.
      ...p.ohne_fenster.map((titel, i) => ({ todo_id: `ohne-fenster-${i}`, title: titel, reason: 'kein freies Fenster lang genug' })),
    ],
  };
}

export function aufgabenToken(user: SagantaUser): string {
  return issueBackendToken({ user, secret: backendSecret(), audience: AUFGABEN_API_AUDIENCE, ttlSeconds: 60 });
}

/** Zugriffs-Kontext. `null`, solange kein Nutzer oder keine Adresse. */
export function dienstCtx(locals: App.Locals): { base: string; token: string } | null {
  if (!locals.user || !env.AUFGABEN_API_BASE_URL) return null;
  return { base: env.AUFGABEN_API_BASE_URL, token: aufgabenToken(locals.user) };
}

export async function dienstFetch<T>(
  ctx: { base: string; token: string },
  pfad: string,
  fetcher: typeof fetch,
  init: { method?: string; json?: unknown } = {},
): Promise<T> {
  const res = await fetcher(`${ctx.base.replace(/\/$/, '')}${pfad}`, {
    method: init.method ?? 'GET',
    headers: {
      Authorization: `Bearer ${ctx.token}`,
      Accept: 'application/json',
      ...(init.json !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: init.json !== undefined ? JSON.stringify(init.json) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`aufgaben-api ${res.status}: ${text.slice(0, 200)}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
