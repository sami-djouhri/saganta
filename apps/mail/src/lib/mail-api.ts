import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export interface Account {
  id: number;
  email: string;
  provider: string;
  display_name: string | null;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
  enabled: boolean;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface Message {
  id: number;
  account_id: number;
  account_email: string;
  folder: string;
  uid: string;
  subject: string;
  from_addr: string;
  from_name: string | null;
  to_addr: string | null;
  snippet: string | null;
  date: string | null;
  is_read: boolean;
  is_starred: boolean;
}

export interface MessagePage {
  items: Message[];
  offset: number;
  limit: number;
  total: number;
  next_offset: number | null;
}

export interface MessageBody {
  id: number;
  subject: string;
  from_addr: string;
  to_addr: string | null;
  date: string | null;
  text: string | null;
  html: string | null;
}

export interface ProviderPreset {
  key: string;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
  note: string | null;
}

export const MAIL_API_AUDIENCE = 'mail-api';

export function mailApiToken(user: SagantaUser, secret: string): string {
  return issueBackendToken({
    user,
    secret,
    audience: MAIL_API_AUDIENCE,
    ttlSeconds: 60,
  });
}

export function backendSecret(): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET ist nicht gesetzt: Backend-Token kann nicht signiert werden.');
  return secret;
}

export async function mailApiFetch<T>(
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
    throw new Error(`mail-api ${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
