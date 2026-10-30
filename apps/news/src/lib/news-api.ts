import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export interface FeedItem {
  id: number;
  source_id: number;
  source_slug: string;
  source_name: string;
  title: string;
  link: string;
  summary: string | null;
  author: string | null;
  published_at: string | null;
  fetched_at: string;
  read: boolean;
  bookmarked: boolean;
}

export interface FeedPage {
  items: FeedItem[];
  offset: number;
  limit: number;
  total: number;
  next_offset: number | null;
}

export interface Source {
  id: number;
  slug: string;
  name: string;
  enabled: boolean;
  last_polled_at: string | null;
  last_error: string | null;
}

export const NEWS_API_AUDIENCE = 'news-api';

export function newsApiToken(user: SagantaUser, secret: string): string {
  return issueBackendToken({
    user,
    secret,
    audience: NEWS_API_AUDIENCE,
    ttlSeconds: 60,
  });
}

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt: Backend-Token kann nicht signiert werden.');
  return secret;
}

export async function newsApiFetch<T>(
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
    throw new Error(`news-api ${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}
