import type { Handle, RequestEvent } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';
import type { AuthConfig } from './config.js';
import { buildAuthRequest, completeAuth, endSessionUrl, randomSessionId, refreshSession } from './oidc.js';
import type { PendingStore, SagantaUser, SessionStore } from './types.js';

const LOGIN_PATH = '/auth/login';
const CALLBACK_PATH = '/auth/callback';
const LOGOUT_PATH = '/auth/logout';

export interface SagantaLocals {
  user?: SagantaUser;
  accessToken?: string;
  sessionId?: string;
}

interface HookOptions {
  cfg: AuthConfig;
  sessions: SessionStore;
  pending: PendingStore;
  /** Pfade, die ohne Login zugänglich sind. Default: /healthz, /robots.txt, /favicon.ico */
  publicPaths?: (string | RegExp)[];
}

function isPublic(pathname: string, publicPaths: (string | RegExp)[]): boolean {
  return publicPaths.some((p) => (typeof p === 'string' ? p === pathname : p.test(pathname)));
}

function cookieAttrs(cfg: AuthConfig): string {
  const parts = ['Path=/', 'HttpOnly', 'Secure', 'SameSite=Lax'];
  if (cfg.cookieDomain) parts.push(`Domain=${cfg.cookieDomain}`);
  return parts.join('; ');
}

function buildCookie(cfg: AuthConfig, value: string, maxAgeSeconds: number): string {
  return `${cfg.cookieName ?? '__Host-saganta_session'}=${value}; Max-Age=${maxAgeSeconds}; ${cookieAttrs(cfg)}`;
}

function clearCookie(cfg: AuthConfig): string {
  return `${cfg.cookieName ?? '__Host-saganta_session'}=; Max-Age=0; ${cookieAttrs(cfg)}`;
}

export function createAuthHandle(opts: HookOptions): Handle {
  const { cfg, sessions, pending } = opts;
  const publicPaths = opts.publicPaths ?? [
    '/healthz',
    '/robots.txt',
    '/favicon.ico',
    LOGIN_PATH,
    CALLBACK_PATH,
    LOGOUT_PATH,
  ];

  return async ({ event, resolve }) => {
    const { url, request } = event;

    if (url.pathname === LOGIN_PATH) return handleLogin(event, cfg, pending);
    if (url.pathname === CALLBACK_PATH) return handleCallback(event, cfg, sessions, pending);
    if (url.pathname === LOGOUT_PATH) return handleLogout(event, cfg, sessions);

    const sid = event.cookies.get(cfg.cookieName ?? '__Host-saganta_session');
    if (sid) {
      let record = await sessions.get(sid);
      if (record) {
        const now = Math.floor(Date.now() / 1000);
        if (record.expiresAt - now < 60 && record.refreshToken) {
          try {
            record = await refreshSession(cfg, record.refreshToken);
            await sessions.set(sid, record, cfg.sessionTtl ?? 8 * 3600);
          } catch {
            await sessions.destroy(sid);
            record = null;
          }
        }
      }
      if (record) {
        const locals = event.locals as SagantaLocals;
        locals.user = record.user;
        locals.accessToken = record.accessToken;
        locals.sessionId = sid;
      } else {
        event.cookies.delete(cfg.cookieName ?? '__Host-saganta_session', { path: '/' });
      }
    }

    if (!(event.locals as SagantaLocals).user && !isPublic(url.pathname, publicPaths)) {
      const next = url.pathname + url.search;
      redirect(303, `${LOGIN_PATH}?next=${encodeURIComponent(next)}`);
    }

    // Origin-Check für unsafe-Methoden (zusätzlich zu SvelteKits CSRF-Protection).
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      const origin = request.headers.get('origin');
      if (origin && new URL(origin).host !== url.host) {
        return new Response('Origin mismatch', { status: 403 });
      }
    }

    return resolve(event);
  };
}

async function handleLogin(
  event: RequestEvent,
  cfg: AuthConfig,
  pending: PendingStore,
): Promise<Response> {
  const next = event.url.searchParams.get('next') ?? '/';
  const req = await buildAuthRequest(cfg);
  await pending.set(
    req.state,
    {
      state: req.state,
      nonce: req.nonce,
      codeVerifier: req.codeVerifier,
      redirectAfter: next,
      createdAt: Date.now(),
    },
    cfg.pendingTtl ?? 600,
  );
  return new Response(null, {
    status: 303,
    headers: { Location: req.url.toString() },
  });
}

async function handleCallback(
  event: RequestEvent,
  cfg: AuthConfig,
  sessions: SessionStore,
  pending: PendingStore,
): Promise<Response> {
  const state = event.url.searchParams.get('state');
  if (!state) return new Response('Missing state', { status: 400 });
  const pendingAuth = await pending.get(state);
  if (!pendingAuth) return new Response('Unknown or expired state', { status: 400 });
  await pending.destroy(state);

  let record;
  try {
    record = await completeAuth(cfg, event.url, pendingAuth.state, pendingAuth.nonce, pendingAuth.codeVerifier);
  } catch (err) {
    console.error('OIDC callback failed', err);
    return new Response('OIDC callback failed', { status: 400 });
  }

  const sid = randomSessionId();
  const ttl = cfg.sessionTtl ?? 8 * 3600;
  await sessions.set(sid, record, ttl);

  return new Response(null, {
    status: 303,
    headers: {
      Location: pendingAuth.redirectAfter,
      'Set-Cookie': buildCookie(cfg, sid, ttl),
    },
  });
}

async function handleLogout(
  event: RequestEvent,
  cfg: AuthConfig,
  sessions: SessionStore,
): Promise<Response> {
  const sid = event.cookies.get(cfg.cookieName ?? '__Host-saganta_session');
  let endUrl: URL | null = null;
  if (sid) {
    const rec = await sessions.get(sid);
    await sessions.destroy(sid);
    if (rec) endUrl = await endSessionUrl(cfg, rec.idToken);
  }
  return new Response(null, {
    status: 303,
    headers: {
      Location: endUrl?.toString() ?? cfg.postLogoutRedirectUri ?? '/',
      'Set-Cookie': clearCookie(cfg),
    },
  });
}
