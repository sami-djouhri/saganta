/**
 * Die Projekte des ProjectDecks fuer den Projektfilter (seit 2026-11-15).
 *
 * Fail-soft: ohne Antwort eine leere Liste, dann fehlt nur der Filter. Die
 * Verknuepfungen selbst tragen den Slug und bleiben lesbar.
 */
import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';
import type { DeckProjektRoh } from '@saganta/ui';

export async function ladeDeckProjekte(user: SagantaUser, fetcher: typeof fetch): Promise<DeckProjektRoh[]> {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) return [];
  const basis = (env.PROJECTDECK_API_BASE_URL ?? 'http://saganta-projectdeck-api:8000').replace(/\/$/, '');
  const token = issueBackendToken({ user, secret, audience: 'projectdeck-api', ttlSeconds: 60 });
  try {
    const res = await fetcher(`${basis}/api/projects`, {
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
