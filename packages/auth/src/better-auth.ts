import type { Cookies, Handle } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';
import type { SagantaUser } from './types.js';
import type { SagantaLocals } from './hooks.js';

// ── Suite-weites Theme (subdomain-übergreifend) ──────────────────────────────
// Damit die ganze Suite „wie aus einem Guss" aussieht, teilen sich alle Apps das
// gewählte Theme über EIN Cookie auf der Registrar-Domain (.saganta.de/.home.arpa).
// Geschrieben wird es nur in der shell (Theme-Control-Center), gelesen von jeder App.

export const THEME_COOKIE_NAME = 'saganta_theme';
const VALID_THEMES = new Set(['dark', 'light', 'hc']);
const ONE_YEAR = 60 * 60 * 24 * 365;

/**
 * Parent-Registrar-Domain für ein subdomain-übergreifendes Cookie:
 * `shell.saganta.de` → `.saganta.de`, `home.arpa` → `.home.arpa`.
 * IP/localhost → undefined (host-only Cookie, Dev).
 */
export function parentCookieDomain(hostname: string): string | undefined {
  const host = (hostname.split(':')[0] ?? hostname).trim();
  if (!host || /^[0-9.]+$/.test(host)) return undefined; // IP → host-only
  const parts = host.split('.');
  if (parts.length < 2) return undefined; // localhost
  return '.' + parts.slice(-2).join('.');
}

/** Setzt das suite-weite Theme-Cookie (shell schreibt, alle Apps lesen). */
export function setThemeCookie(
  cookies: Cookies,
  hostname: string,
  secure: boolean,
  theme: string,
): void {
  if (!VALID_THEMES.has(theme)) return;
  const domain = parentCookieDomain(hostname);
  cookies.set(THEME_COOKIE_NAME, theme, {
    path: '/',
    domain,
    httpOnly: false, // nur Optik, kein Geheimnis; Client darf lesen
    sameSite: 'lax',
    secure,
    maxAge: ONE_YEAR,
  });
}

/**
 * better-auth-Integration für die SvelteKit-BFFs.
 *
 * Modellwechsel ggü. der alten OIDC-Schicht (oidc.ts/hooks.ts):
 * Die Session-Authority ist der zentrale `saganta-auth`-Service (better-auth).
 * Die BFFs halten KEINE eigene Session mehr, sie fragen den Auth-Service
 * server-side („wer ist dieses Cookie?") und übersetzen das Ergebnis weiter
 * in das HS256-Backend-JWT (backend-token.ts). Backends bleiben unverändert.
 */

export interface BetterAuthConfig {
  /** Interne URL des Auth-Service (server-to-server), z. B. http://saganta-auth:3000 */
  authServiceUrl: string;
  /** Öffentliche Login-Seite, z. B. /login (im shell) oder https://saganta.de/login */
  loginUrl: string;
  /**
   * Weitere Login-Seiten je Domain-Raum, für Installationen, die unter mehr als
   * einem Namen erreichbar sind. Schlüssel ist die Registrar-Domain ohne Punkt,
   * Wert die vollständige Adresse.
   *
   * ★ Ohne das schickt eine App unter `tagebuch.home.arpa` zum Login auf
   * `https://saganta.de/login`, und das dort gesetzte Cookie erreicht den
   * `.home`-Raum nie. Die Anmeldung liefe endlos im Kreis.
   */
  loginUrls?: Record<string, string>;
  /** better-auth Session-Cookie-Name. Default: saganta.session_token */
  cookieName?: string;
}

/**
 * Zerlegt `AUTH_LOGIN_URLS` in eine Zuordnung.
 *
 * Form: `home.arpa=https://shell.home.arpa/login`, mehrere durch Komma
 * getrennt. Unbrauchbare Einträge werden übergangen statt den Start zu
 * verhindern: eine kaputte Zusatzangabe darf die Anmeldung im Hauptraum nicht
 * mitreissen.
 */
export function leseLoginUrls(roh: string | undefined): Record<string, string> {
  const zuordnung: Record<string, string> = {};
  for (const teil of (roh ?? '').split(',')) {
    const stelle = teil.indexOf('=');
    if (stelle < 1) continue;
    const domain = teil.slice(0, stelle).trim().replace(/^\./, '').toLowerCase();
    const adresse = teil.slice(stelle + 1).trim();
    if (domain && adresse) zuordnung[domain] = adresse;
  }
  return zuordnung;
}

/**
 * Prüft ein Weiterleitungsziel nach der Anmeldung.
 *
 * Erlaubt sind app-interne Pfade und absolute Adressen **im selben
 * Domain-Raum**. Alles andere wird zu `/`, damit die Anmeldeseite nicht als
 * offene Weiterleitung missbraucht werden kann.
 *
 * ★ Der Vergleich läuft über die Registrar-Domain, nicht über eine Namensliste.
 * `https://tagebuch.home.arpa.fremd.de/` sieht auf den ersten Blick
 * passend aus und gehört trotzdem `fremd.de`; eine Prüfung mit `includes` oder
 * `startsWith` fiele darauf herein.
 */
export function sicheresZiel(roh: string | null | undefined, eigenerHost?: string): string {
  if (!roh) return '/';
  if (roh.startsWith('/') && !roh.startsWith('//')) return roh;
  if (!eigenerHost) return '/';
  let ziel: URL;
  try {
    ziel = new URL(roh);
  } catch {
    return '/';
  }
  if (ziel.protocol !== 'https:' && ziel.protocol !== 'http:') return '/';
  const eigen = parentCookieDomain(eigenerHost);
  const fremd = parentCookieDomain(ziel.host);
  if (!eigen || eigen !== fremd) return '/';
  return ziel.toString();
}

/** Die Login-Seite, die zum Host der Anfrage gehört. */
export function anmeldeadresseFuer(cfg: BetterAuthConfig, anfrageHost: string | undefined): string {
  if (!anfrageHost || !cfg.loginUrls) return cfg.loginUrl;
  const host = (anfrageHost.split(':')[0] ?? anfrageHost).trim().toLowerCase();
  for (const [domain, adresse] of Object.entries(cfg.loginUrls)) {
    if (host === domain || host.endsWith('.' + domain)) return adresse;
  }
  return cfg.loginUrl;
}

export function loadBetterAuthConfig(env: Record<string, string | undefined>): BetterAuthConfig {
  const required = (key: string): string => {
    const value = env[key];
    if (!value) throw new Error(`Missing env var: ${key}`);
    return value;
  };
  return {
    authServiceUrl: required('AUTH_SERVICE_URL'),
    loginUrl: env.AUTH_LOGIN_URL ?? '/login',
    loginUrls: leseLoginUrls(env.AUTH_LOGIN_URLS),
    cookieName: env.AUTH_COOKIE_NAME ?? 'saganta.session_token',
  };
}

interface BetterAuthUser {
  id: string;
  email: string;
  name?: string | null;
  emailVerified?: boolean;
  image?: string | null;
  /** Zusatzfeld aus der auth-DB (user.additionalFields in auth-service/auth.ts). */
  plan?: string | null;
}

/** Übersetzt einen better-auth-User in das interne SagantaUser-Modell. */
export function mapBetterAuthUser(u: BetterAuthUser): SagantaUser {
  const user: SagantaUser = { sub: u.id, email: u.email, groups: [] };
  if (u.name) user.name = u.name;
  // Fail-closed: alles, was nicht ausdrücklich 'pro' ist, gilt als 'free'.
  // Ein leeres, fehlendes oder unbekanntes Feld darf niemals Merkmale öffnen.
  user.plan = u.plan === 'pro' ? 'pro' : 'free';
  return user;
}

function isPublic(pathname: string, publicPaths: (string | RegExp)[]): boolean {
  return publicPaths.some((p) => (typeof p === 'string' ? p === pathname : p.test(pathname)));
}

interface HandleOptions {
  /**
   * Config oder ein Thunk, der sie liefert. Thunk = lazy (Request-Zeit), damit
   * Pflicht-Env nicht beim Modul-Import/Build geladen werden muss.
   */
  cfg: BetterAuthConfig | (() => BetterAuthConfig);
  /** Pfade ohne Login. Default: /healthz, /robots.txt, /favicon.ico + Login-Pfad. */
  publicPaths?: (string | RegExp)[];
}

/**
 * SvelteKit-Handle: validiert die better-auth-Session über den Auth-Service,
 * befüllt `event.locals.user`, und leitet unauthentifizierte Requests auf die
 * Login-Seite um.
 */
export function createBetterAuthHandle(opts: HandleOptions): Handle {
  // Lazy: Config + abgeleitete Werte erst beim ersten Request bauen (memoized),
  // damit Pflicht-Env nicht zur Build-/Import-Zeit gelesen wird.
  let resolved: {
    cfg: BetterAuthConfig;
    cookieName: string;
    publicPaths: (string | RegExp)[];
  } | null = null;

  function ensure() {
    if (resolved) return resolved;
    const cfg = typeof opts.cfg === 'function' ? opts.cfg() : opts.cfg;
    const cookieName = cfg.cookieName ?? 'saganta.session_token';
    // loginUrl kann absolut (https://saganta.de/login) oder relativ (/login) sein.
    const loginPath = cfg.loginUrl.startsWith('http')
      ? new URL(cfg.loginUrl).pathname
      : cfg.loginUrl.split('?')[0]!;
    const publicPaths = opts.publicPaths ?? [
      '/healthz',
      '/robots.txt',
      '/favicon.ico',
      loginPath,
    ];
    resolved = { cfg, cookieName, publicPaths };
    return resolved;
  }

  return async ({ event, resolve }) => {
    const { cfg, cookieName, publicPaths } = ensure();
    const { url, request } = event;
    const cookieHeader = request.headers.get('cookie') ?? '';

    if (cookieHeader.includes(`${cookieName}=`)) {
      try {
        const res = await fetch(`${cfg.authServiceUrl}/api/auth/get-session`, {
          headers: { cookie: cookieHeader, accept: 'application/json' },
        });
        if (res.ok) {
          const data = (await res.json()) as
            | { user?: BetterAuthUser; session?: { token?: string } }
            | null;
          if (data?.user) {
            const locals = event.locals as SagantaLocals;
            locals.user = mapBetterAuthUser(data.user);
            if (data.session?.token) locals.sessionId = data.session.token;
          }
        }
      } catch (err) {
        // Auth-Service nicht erreichbar → als unauthentifiziert behandeln.
        // Mit Kontext loggen, damit Auth-Ausfälle (falsche URL/Timeout) auffindbar sind.
        console.error(
          '[saganta-auth] get-session fehlgeschlagen',
          JSON.stringify({
            authServiceUrl: cfg.authServiceUrl,
            path: url.pathname,
            error: err instanceof Error ? err.message : String(err),
          }),
        );
      }
    }

    const authed = Boolean((event.locals as SagantaLocals).user);
    if (!authed && !isPublic(url.pathname, publicPaths)) {
      // Die Login-Seite muss im selben Domain-Raum liegen wie die App, sonst
      // erreicht das dort gesetzte Cookie sie nie.
      const anmeldeadresse = anmeldeadresseFuer(cfg, url.host);
      // ★ Liegt die Anmeldung auf einem anderen Host, muss `next` absolut sein.
      // Ein blosser Pfad wuerde dort auf die Anmelde-App selbst zeigen: man
      // meldet sich an und landet in der Shell statt in der App, aus der man
      // kam. Die Shell laesst absolute Ziele nur im eigenen Domain-Raum zu.
      const anmeldeHost = anmeldeadresse.startsWith('http')
        ? new URL(anmeldeadresse).host
        : url.host;
      const next =
        anmeldeHost === url.host
          ? url.pathname + url.search
          : `${url.protocol}//${url.host}${url.pathname}${url.search}`;
      const sep = anmeldeadresse.includes('?') ? '&' : '?';
      redirect(303, `${anmeldeadresse}${sep}next=${encodeURIComponent(next)}`);
    }

    // Origin-Check für unsafe-Methoden (zusätzlich zu SvelteKits CSRF-Schutz).
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      const origin = request.headers.get('origin');
      if (origin && new URL(origin).host !== url.host) {
        return new Response('Origin mismatch', { status: 403 });
      }
    }

    // Suite-weites Theme: liegt es (per shell-Cookie) auf light/hc, in das
    // gerenderte HTML injizieren. `dark` ist der SSR-Default → kein Rewrite nötig
    // (spart den Transform im Normalfall). Nur validierte Werte werden gesetzt.
    const theme = event.cookies.get(THEME_COOKIE_NAME);
    if (theme && theme !== 'dark' && VALID_THEMES.has(theme)) {
      return resolve(event, {
        transformPageChunk: ({ html }) =>
          html.replaceAll('data-theme="dark"', `data-theme="${theme}"`),
      });
    }

    return resolve(event);
  };
}

// --- Login-/Logout-Helfer für die Login-Seite (server-side Form-Actions) ---

export interface AuthActionResult {
  ok: boolean;
  error?: string;
  /** better-auth-Fehlercode, z. B. EMAIL_NOT_VERIFIED (für gezielte UI-Reaktion). */
  code?: string;
  /** Vom Auth-Service gesetzte Cookies (an den Browser weiterzureichen). */
  setCookies: string[];
}

async function postJson(
  cfg: BetterAuthConfig,
  path: string,
  body: unknown,
  cookieHeader?: string,
): Promise<{ res: Response; json: Record<string, unknown> | null }> {
  const headers: Record<string, string> = {
    'content-type': 'application/json',
    accept: 'application/json',
    // better-auth verlangt für state-changing Requests einen Origin in trustedOrigins.
    // Server-to-server vom BFF: mit dem Origin des Auth-Service ausweisen (trusted).
    origin: new URL(cfg.authServiceUrl).origin,
  };
  if (cookieHeader) headers.cookie = cookieHeader;
  const res = await fetch(`${cfg.authServiceUrl}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  let json: Record<string, unknown> | null = null;
  try {
    json = (await res.json()) as Record<string, unknown>;
  } catch {
    json = null;
  }
  return { res, json };
}

function setCookiesOf(res: Response): string[] {
  // Node 22 / undici: Headers.getSetCookie() liefert alle Set-Cookie-Header.
  return res.headers.getSetCookie?.() ?? [];
}

export async function signInEmail(
  cfg: BetterAuthConfig,
  email: string,
  password: string,
): Promise<AuthActionResult> {
  const { res, json } = await postJson(cfg, '/api/auth/sign-in/email', { email, password });
  if (!res.ok) {
    const error = (json?.message as string) ?? 'Anmeldung fehlgeschlagen';
    const code = (json?.code as string) ?? undefined;
    return { ok: false, error, code, setCookies: [] };
  }
  return { ok: true, setCookies: setCookiesOf(res) };
}

export async function signUpEmail(
  cfg: BetterAuthConfig,
  email: string,
  password: string,
  name: string,
): Promise<AuthActionResult> {
  const { res, json } = await postJson(cfg, '/api/auth/sign-up/email', { email, password, name });
  if (!res.ok) {
    const error = (json?.message as string) ?? 'Registrierung fehlgeschlagen';
    return { ok: false, error, setCookies: [] };
  }
  return { ok: true, setCookies: setCookiesOf(res) };
}

/**
 * Stößt den Passwort-Reset an: better-auth verschickt (über sendResetPassword)
 * eine Mail mit Token-Link. Antwortet bewusst immer `ok`, sofern der Service
 * erreichbar war, keine Account-Enumeration (existiert die Mail nicht, passiert
 * still nichts).
 */
export async function requestPasswordReset(
  cfg: BetterAuthConfig,
  email: string,
  redirectTo: string,
): Promise<AuthActionResult> {
  const { res } = await postJson(cfg, '/api/auth/request-password-reset', { email, redirectTo });
  if (!res.ok && res.status >= 500) {
    return { ok: false, error: 'Dienst nicht erreichbar.', setCookies: [] };
  }
  return { ok: true, setCookies: [] };
}

/** Setzt das Passwort mit dem Token aus der Reset-Mail neu. */
export async function resetPassword(
  cfg: BetterAuthConfig,
  token: string,
  newPassword: string,
): Promise<AuthActionResult> {
  const { res, json } = await postJson(cfg, '/api/auth/reset-password', { token, newPassword });
  if (!res.ok) {
    const error = (json?.message as string) ?? 'Zurücksetzen fehlgeschlagen.';
    return { ok: false, error, setCookies: [] };
  }
  return { ok: true, setCookies: [] };
}

/** Sendet die Verifizierungs-Mail erneut (z. B. Login mit unverifizierter Mail). */
export async function resendVerificationEmail(
  cfg: BetterAuthConfig,
  email: string,
  callbackURL: string,
): Promise<AuthActionResult> {
  const { res } = await postJson(cfg, '/api/auth/send-verification-email', { email, callbackURL });
  if (!res.ok && res.status >= 500) {
    return { ok: false, error: 'Dienst nicht erreichbar.', setCookies: [] };
  }
  return { ok: true, setCookies: [] };
}

/**
 * Ändert das Passwort eines eingeloggten Users über better-auth
 * (`POST /api/auth/change-password`). Verlangt das aktuelle Passwort; bei
 * `revokeOtherSessions` werden andere Sessions invalidiert und der Service
 * setzt ein frisches Session-Cookie (an den Browser weiterzureichen).
 */
export async function changePassword(
  cfg: BetterAuthConfig,
  cookieHeader: string,
  currentPassword: string,
  newPassword: string,
  revokeOtherSessions = false,
): Promise<AuthActionResult> {
  const { res, json } = await postJson(
    cfg,
    '/api/auth/change-password',
    { currentPassword, newPassword, revokeOtherSessions },
    cookieHeader,
  );
  if (!res.ok) {
    const error = (json?.message as string) ?? 'Passwort ändern fehlgeschlagen.';
    const code = (json?.code as string) ?? undefined;
    return { ok: false, error, code, setCookies: [] };
  }
  return { ok: true, setCookies: setCookiesOf(res) };
}

export async function signOut(cfg: BetterAuthConfig, cookieHeader: string): Promise<string[]> {
  const res = await fetch(`${cfg.authServiceUrl}/api/auth/sign-out`, {
    method: 'POST',
    headers: {
      cookie: cookieHeader,
      'content-type': 'application/json',
      origin: new URL(cfg.authServiceUrl).origin,
    },
  });
  return setCookiesOf(res);
}

/**
 * Passt die Cookie-Domain an den Host an, über den die Anfrage kam.
 *
 * ★ Der Grund: ein Browser verwirft ein Set-Cookie, dessen `Domain` nicht zum
 * antwortenden Host passt. Der Auth-Service schreibt fest `Domain=saganta.de`
 * (`AUTH_COOKIE_DOMAIN`). Wer die Suite über `shell.home.arpa` aufruft,
 * bekommt das Cookie also gesetzt, der Browser wirft es weg, und die Anmeldung
 * endet in einer Schleife, ohne dass irgendwo ein Fehler steht. Genau das war
 * bis 2026-09-06 der Zustand: der `.home`-Raum war für die Anmeldung nie
 * benutzbar, was niemandem auffiel, weil alle Apps über `.de` liefen.
 *
 * Passt die Domain zum Host, bleibt sie unverändert (der `.de`-Weg ist damit
 * byte-gleich wie vorher). Passt sie nicht, wird die Registrar-Domain des
 * Hosts genommen, also dieselbe Ableitung wie beim Theme-Cookie. Ist auch das
 * nicht möglich (IP, localhost), entfällt die Domain und das Cookie gilt
 * host-only: lieber eine App angemeldet als keine.
 */
export function passendeCookieDomain(
  gesetzt: string,
  anfrageHost: string | undefined,
): string | undefined {
  if (!anfrageHost) return gesetzt; // ohne Host: Verhalten wie bisher
  const host = (anfrageHost.split(':')[0] ?? anfrageHost).trim().toLowerCase();
  const soll = gesetzt.replace(/^\./, '').toLowerCase();
  if (host === soll || host.endsWith('.' + soll)) return gesetzt;
  return parentCookieDomain(host);
}

/**
 * Reicht die vom Auth-Service gesetzten Set-Cookie-Header an den Browser weiter.
 *
 * `anfrageHost` ist optional, damit bestehende Aufrufer unverändert
 * weiterlaufen. Wird er mitgegeben, wandert das Cookie in den Domain-Raum, aus
 * dem die Anfrage kam (siehe `passendeCookieDomain`).
 */
export function applySetCookies(
  cookies: Cookies,
  setCookies: string[],
  anfrageHost?: string,
): void {
  for (const raw of setCookies) {
    const segments = raw.split(';').map((s) => s.trim());
    const pair = segments[0] ?? '';
    const eq = pair.indexOf('=');
    if (eq < 0) continue;
    const name = pair.slice(0, eq);
    const value = pair.slice(eq + 1);

    // encode = Identity: der Wert vom Auth-Service ist bereits in finaler Wire-Form
    // (z. B. %3D-kodiert). Ohne das würde SvelteKit ihn doppelt kodieren (%253D)
    // und die better-auth-Signatur unbrauchbar machen.
    const opts: Parameters<Cookies['set']>[2] = { path: '/', encode: (v) => v };
    for (const seg of segments.slice(1)) {
      const idx = seg.indexOf('=');
      const key = (idx < 0 ? seg : seg.slice(0, idx)).toLowerCase();
      const val = idx < 0 ? '' : seg.slice(idx + 1);
      if (key === 'domain' && val) opts.domain = passendeCookieDomain(val, anfrageHost);
      else if (key === 'path' && val) opts.path = val;
      else if (key === 'max-age' && val) opts.maxAge = Number(val);
      else if (key === 'expires' && val) opts.expires = new Date(val);
      else if (key === 'httponly') opts.httpOnly = true;
      else if (key === 'secure') opts.secure = true;
      else if (key === 'samesite' && val) {
        const sv = val.toLowerCase();
        if (sv === 'lax' || sv === 'strict' || sv === 'none') opts.sameSite = sv;
      }
    }
    cookies.set(name, value, opts);
  }
}
