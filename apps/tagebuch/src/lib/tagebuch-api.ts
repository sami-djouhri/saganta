/**
 * Zugang zu den beiden Backends, ausschliesslich serverseitig.
 *
 * ★ Das ist die Stelle, an der die Vertraulichkeit dieses Entwurfs hängt, und
 * zwar an dem, was hier *nicht* passiert: dieser Server sieht Chiffrat und
 * reicht Chiffrat weiter. Er entschlüsselt nichts, er protokolliert nichts von
 * dem, was durchläuft, und er kennt keinen Schlüssel. Wer hier künftig etwas
 * einbaut, das in einen Eintrag hineinsieht, hebt die Zusicherung der ganzen
 * App auf, ohne dass ein Test rot wird.
 *
 * Zwei Ziele, mit klarer Aufgabenteilung:
 *
 * - `api()` spricht mit `tagebuch-api` und transportiert Chiffrat.
 * - `kalender()` spricht mit `kalender-bff` und transportiert **nur Zahlen**:
 *   den Tageskontext herein, die drei Skalen hinaus. Der Freitext geht diesen
 *   Weg nie.
 */

import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export const TAGEBUCH_API_AUDIENCE = 'tagebuch-api';
export const KALENDER_BFF_AUDIENCE = 'kalender-bff';

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) {
    throw new Error(
      'SAGANTA_BACKEND_SECRET ist nicht gesetzt, Backend-Token kann nicht signiert werden.',
    );
  }
  return secret;
}

function token(user: SagantaUser, audience: string): string {
  return issueBackendToken({ user, secret: backendSecret(), audience, ttlSeconds: 60 });
}

export function apiBase(): string {
  return (env.TAGEBUCH_API_BASE_URL ?? 'http://saganta-tagebuch-api:8000').replace(/\/$/, '');
}

export function kalenderBase(): string {
  return (env.KALENDER_BFF_BASE_URL ?? 'http://saganta-kalender-bff:8000').replace(/\/$/, '');
}

/**
 * Fehler mit dem Statuscode des Backends. Die Oberfläche kann daran
 * unterscheiden, ob etwas fehlt (404), zu groß ist (422) oder der Dienst hakt
 * (5xx). Ein pauschales `Error` würde all das zu "geht nicht" einebnen, und
 * gerade 404 heisst hier etwas Harmloses: noch nichts geschrieben.
 */
export class ApiFehler extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail || `tagebuch-api ${status}`);
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
      Authorization: `Bearer ${token(user, TAGEBUCH_API_AUDIENCE)}`,
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers ?? {}),
    },
  });
  return auswerten<T>(res);
}

/**
 * Der Weg zum Kalender.
 *
 * Bewusst eine eigene Funktion statt eines Parameters an `api()`: die beiden
 * Ziele haben verschiedene Zielgruppen im Token und verschiedene
 * Zuständigkeiten. Eine gemeinsame Funktion mit einem Schalter wäre die
 * Einladung, versehentlich einen Eintrag dorthin zu schicken.
 */
export async function kalender<T>(
  user: SagantaUser,
  pfad: string,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetcher(`${kalenderBase()}${pfad}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token(user, KALENDER_BFF_AUDIENCE)}`,
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers ?? {}),
    },
  });
  return auswerten<T>(res);
}

// --- Formen, die über die Leitung gehen ------------------------------------

export interface TresorPaketeAus {
  kdf: string;
  kdf_iterationen: number;
  salz_passphrase: string;
  wrap_passphrase: string;
  wrap_passphrase_iv: string;
  salz_wiederherstellung: string;
  wrap_wiederherstellung: string;
  wrap_wiederherstellung_iv: string;
}

export interface EintragAus {
  datum: string;
  chiffrat: string;
  iv: string;
  schluessel_version: number;
  erstellt_am: string;
  geaendert_am: string;
}

export interface TagAus {
  datum: string;
  zeichen: number;
  geaendert_am: string;
}
