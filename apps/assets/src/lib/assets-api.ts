import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export interface Asset {
  id: number;
  source: string;
  source_id: string | null;
  name: string;
  category: string | null;
  location: string | null;
  usage_status: string;
  purchase_date: string | null;
  purchase_price_eur: number | null;
  market_value_eur: number | null;
  market_value_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  resale_recommended: boolean;
  resale_reason: string | null;
}

export const ASSETS_API_AUDIENCE = 'assets-api';

export function assetsApiToken(user: SagantaUser, secret: string): string {
  return issueBackendToken({
    user,
    secret,
    audience: ASSETS_API_AUDIENCE,
    ttlSeconds: 60,
  });
}

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt: Backend-Token kann nicht signiert werden.');
  return secret;
}

export async function assetsApiFetch<T>(
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
    throw new Error(`assets-api ${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}
