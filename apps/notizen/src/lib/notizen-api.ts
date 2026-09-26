import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export const NOTIZEN_API_AUDIENCE = 'notizen-api';

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) {
    throw new Error(
      'SAGANTA_BACKEND_SECRET ist nicht gesetzt: Backend-Token kann nicht signiert werden.',
    );
  }
  return secret;
}

export function apiToken(user: SagantaUser): string {
  return issueBackendToken({
    user,
    secret: backendSecret(),
    audience: NOTIZEN_API_AUDIENCE,
    ttlSeconds: 60,
  });
}

export function apiBase(): string {
  return (env.NOTIZEN_API_BASE_URL ?? 'http://saganta-notizen-api:8000').replace(/\/$/, '');
}

/**
 * Fehler mit dem Statuscode des Backends, die Oberfläche kann daran
 * unterscheiden, ob etwas fehlt (404), zu groß ist (413) oder der Dienst
 * hakt (5xx). Ein pauschales `Error` würde all das zu „geht nicht" einebnen.
 */
export class ApiFehler extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail || `notizen-api ${status}`);
    this.name = 'ApiFehler';
  }
}

async function auswerten<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const roh = await res.text().catch(() => '');
    let detail = roh.slice(0, 400);
    try {
      const daten = JSON.parse(roh) as { detail?: unknown };
      if (typeof daten.detail === 'string') detail = daten.detail;
    } catch {
      /* Klartext-Antwort */
    }
    throw new ApiFehler(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function api<T>(
  user: SagantaUser,
  pfad: string,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetcher(`${apiBase()}${pfad}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${apiToken(user)}`,
      Accept: 'application/json',
      ...(init.body && !(init.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...(init.headers ?? {}),
    },
  });
  return auswerten<T>(res);
}

/** Rohantwort durchreichen, für Dateien, die nicht durch JSON sollen. */
export async function apiRoh(
  user: SagantaUser,
  pfad: string,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<Response> {
  return fetcher(`${apiBase()}${pfad}`, {
    ...init,
    headers: { Authorization: `Bearer ${apiToken(user)}`, ...(init.headers ?? {}) },
  });
}

/**
 * Der öffentliche Pfad, ohne Nutzer, ohne Token.
 *
 * Auch er läuft über den BFF: das Backend ist nur im internen Netz erreichbar,
 * und das soll so bleiben. Der BFF ist hier reiner Durchreicher und fügt
 * nichts hinzu: insbesondere keinen Hinweis darauf, wer die Notiz angelegt hat.
 */
export async function oeffentlich<T>(
  pfad: string,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetcher(`${apiBase()}/oeffentlich${pfad}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers ?? {}),
    },
  });
  return auswerten<T>(res);
}
