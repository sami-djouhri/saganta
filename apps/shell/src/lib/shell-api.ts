import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export interface ShellApiSettings {
  theme: string;
  locale: string;
  pinned_apps: string[];
}

export interface ShellApiApp {
  id: string;
  name: string;
  description: string;
  href: string;
  icon: string;
  tags: string[];
}

export const SHELL_API_AUDIENCE = 'shell-api';

export function shellApiToken(user: SagantaUser, secret: string): string {
  return issueBackendToken({ user, secret, audience: SHELL_API_AUDIENCE, ttlSeconds: 60 });
}

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt, Backend-Token kann nicht signiert werden.');
  return secret;
}

export async function shellApiFetch<T>(
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
    throw new Error(`shell-api ${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}
