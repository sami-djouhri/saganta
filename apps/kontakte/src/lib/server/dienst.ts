/**
 * Der Weg zum Kontakte-Dienst (`services/kontakte-api`) und, fuer die
 * Terminsuche, zum kalender-bff. Beide mit einem 60-s-Token im Namen des
 * angemeldeten Nutzers.
 */
import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';
import type { Fundtermin } from '$lib/typen';

export const KONTAKTE_API_AUDIENCE = 'kontakte-api';

function geheimnis(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) {
    throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt, das Backend-Token kann nicht signiert werden.');
  }
  return secret;
}

function token(user: SagantaUser, audience: string): string {
  return issueBackendToken({ user, secret: geheimnis(), audience, ttlSeconds: 60 });
}

export interface Ctx {
  base: string;
  token: string;
}

/** `null`, solange kein Nutzer oder keine Adresse. */
export function dienstCtx(locals: App.Locals): Ctx | null {
  if (!locals.user || !env.KONTAKTE_API_BASE_URL) return null;
  return { base: env.KONTAKTE_API_BASE_URL, token: token(locals.user, KONTAKTE_API_AUDIENCE) };
}

export class DienstFehler extends Error {
  constructor(
    public status: number,
    public text: string,
  ) {
    super(`kontakte-api ${status}: ${text.slice(0, 200)}`);
  }
}

export async function dienst<T>(
  ctx: Ctx,
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
  if (!res.ok) throw new DienstFehler(res.status, await res.text().catch(() => ''));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Fehlertext fuer die Oberflaeche: Ursache in einem Satz. */
export function ursache(err: unknown): string {
  if (err instanceof DienstFehler) {
    if (err.status === 404) return 'Den Kontakt gibt es nicht mehr.';
    if (err.status === 422) return 'Eine Angabe passt nicht (Datum oder Länge prüfen).';
    if (err.status === 502) return 'Der Kalender antwortet gerade nicht.';
    return `Der Kontakte-Dienst meldet ${err.status}.`;
  }
  return 'Der Kontakte-Dienst ist gerade nicht erreichbar.';
}

/**
 * Termine zum Verknuepfen: ein Fenster um heute (60 Tage zurueck, 180 nach vorn),
 * gefiltert nach dem Suchwort. Dasselbe Fenster wie die Notizen-Suche.
 */
export async function termineSuchen(
  user: SagantaUser,
  suche: string,
  fetcher: typeof fetch,
): Promise<Fundtermin[]> {
  const basis = env.KALENDER_BFF_BASE_URL ?? 'http://saganta-kalender-bff:8000';
  const heute = new Date();
  const von = new Date(heute.getTime() - 60 * 86_400_000).toISOString().slice(0, 10);
  const bis = new Date(heute.getTime() + 180 * 86_400_000).toISOString().slice(0, 10);
  const res = await fetcher(`${basis}/api/events/range?start=${von}&end=${bis}&limit=800`, {
    headers: { Accept: 'application/json', Authorization: `Bearer ${token(user, 'kalender-bff')}` },
  });
  if (!res.ok) throw new Error(`kalender-bff ${res.status}`);
  const daten: unknown = await res.json();
  const liste = Array.isArray(daten)
    ? daten
    : Array.isArray((daten as { items?: unknown })?.items)
      ? ((daten as { items: unknown[] }).items)
      : [];
  const nadel = suche.trim().toLowerCase();
  return (liste as Record<string, unknown>[])
    .map((e) => ({
      ref: String(e.id ?? ''),
      label: String(e.title ?? e.titel ?? '(ohne Titel)'),
      start: typeof e.start === 'string' ? e.start : null,
    }))
    .filter((t) => t.ref && (!nadel || t.label.toLowerCase().includes(nadel)))
    .slice(0, 15);
}
