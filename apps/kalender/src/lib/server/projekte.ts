/**
 * Die Projekte des ProjectDecks fuer das Feld „Projekt" am Termin (seit 2026-11-15).
 *
 * Fail-soft: ohne Antwort eine leere Liste. Der Editor bleibt dann bedienbar,
 * ein vorhandener Bezug bleibt stehen (er wird nur bei einer Aenderung geschickt).
 */
import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';
import type { DeckProjektRoh } from '@saganta/ui';

export async function ladeDeckProjekte(user: SagantaUser, fetcher: typeof fetch): Promise<DeckProjektRoh[]> {
  const secret = env.SAGANTA_BACKEND_SECRET;
  const basis = env.PROJECTDECK_API_BASE_URL;
  if (!secret || !basis) return [];
  const token = issueBackendToken({ user, secret, audience: 'projectdeck-api', ttlSeconds: 60 });
  try {
    const res = await fetcher(`${basis.replace(/\/$/, '')}/api/projects`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    });
    if (!res.ok) {
      console.warn(`Projekte nicht abrufbar: ProjectDeck antwortet ${res.status}`);
      return [];
    }
    const roh = (await res.json()) as unknown;
    return Array.isArray(roh)
      ? (roh as DeckProjektRoh[]).filter((p) => typeof p?.slug === 'string' && typeof p?.id === 'number')
      : [];
  } catch (err) {
    console.warn(`Projekte nicht abrufbar: ${String(err)}`);
    return [];
  }
}
