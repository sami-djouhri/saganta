import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export const PROJECTDECK_API_AUDIENCE = 'projectdeck-api';

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt: Backend-Token kann nicht signiert werden.');
  return secret;
}

export function apiToken(user: SagantaUser, secret: string): string {
  return issueBackendToken({
    user,
    secret,
    audience: PROJECTDECK_API_AUDIENCE,
    ttlSeconds: 60,
  });
}

export function apiBase(): string {
  return env.PROJECTDECK_API_BASE_URL ?? 'http://saganta-projectdeck-api:8000';
}

export async function api<T>(
  user: SagantaUser,
  path: string,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<T> {
  const token = apiToken(user, backendSecret());
  const res = await fetcher(`${apiBase().replace(/\/$/, '')}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`projectdeck-api ${res.status}: ${body.slice(0, 300)}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
