import { betterAuth } from 'better-auth';
import { bearer } from 'better-auth/plugins';
import { Pool } from 'pg';
import { sendResetMail, sendVerificationMail } from './email.js';

function required(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(`[saganta-auth] Pflicht-Env fehlt: ${key}`);
  }
  return value;
}

const baseURL = process.env.BETTER_AUTH_URL ?? 'http://localhost:3000';

// Cross-Subdomain-SSO: eine Session ueber alle Unterdomaenen der Installation.
//
// ★ Ohne AUTH_COOKIE_DOMAIN wird das Cookie nur fuer den aufrufenden Host
// gesetzt (seit 2026-09-06). Vorher stand hier die Domaene der
// Ursprungs-Instanz als Vorbelegung: eine fremde Installation haette ihr
// Sitzungs-Cookie fuer eine Domaene ausgestellt, die ihr nicht gehoert, und
// waere damit ueberhaupt nicht anmeldbar gewesen. Host-only ist der richtige
// Rueckfall: es funktioniert immer, nur eben ohne SSO ueber Unterdomaenen.
const cookieDomain = process.env.AUTH_COOKIE_DOMAIN ?? '';

// ★ Ohne Cookie-Domaene gaebe die Vorlage `https://` ergeben, also Unsinn.
// Dann bleibt die Liste leer, und better-auth vertraut nur der eigenen baseURL.
const trustedOrigins = (
  process.env.AUTH_TRUSTED_ORIGINS ?? (cookieDomain ? `https://${cookieDomain}` : '')
)
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

// Nur für lokale http-Entwicklung auf 'true' setzen, sonst immer Secure-Cookies.
const useSecureCookies = process.env.AUTH_INSECURE_COOKIES !== 'true';

// pg-Falle: ohne 'error'-Listener crasht ein idle-client-Fehler (z. B. DB-Neustart,
// Verbindungsabbruch) den gesamten Prozess. Abfangen + loggen, Pool heilt selbst.
// Exportiert, weil server.ts den Tarif am Konto setzt (POST /api/intern/tarif).
// Denselben Pool nutzen statt einen zweiten aufzumachen: eine Verbindungsquelle,
// ein Fehler-Listener, ein Ort zum Nachsehen.
export const pool = new Pool({ connectionString: required('DATABASE_URL') });
pool.on('error', (err) => {
  console.error('[saganta-auth] Postgres-Pool-Fehler (idle client):', err.message);
});

/**
 * Zentrale better-auth-Instanz der Saganta-Suite.
 *
 * Phase 1: Email/Passwort + Session. Folgt: 2FA/TOTP, Passkeys (WebAuthn),
 * Self-Service-Signup/Reset (+ SMTP), Organizations/Multi-Tenant.
 *
 * Die FastAPI-Backends bleiben unangetastet, die BFFs übersetzen die
 * better-auth-Session weiterhin in das HS256-Backend-JWT
 * (packages/auth/src/backend-token.ts).
 */
export const auth = betterAuth({
  baseURL,
  secret: required('BETTER_AUTH_SECRET'),
  database: pool,
  emailAndPassword: {
    enabled: true,
    // ★ Registrierung ist seit 2026-09-05 zu (Owner-Entscheid: Saganta geht den
    // Weg Open Source + Demo, es wird kein fremdes Konto auf dieser Instanz
    // gefuehrt). Der Riegel sitzt hier und nicht in `ALLOWED_SUBS`, weil der nur
    // fuenf von sieben Backends bremst: `news-api` und `shell-api` stehen jedem
    // angemeldeten Konto offen. Wieder aufmachen ist eine Env-Aenderung am
    // Compose-Dienst, kein Rebuild: AUTH_ALLOW_SIGNUP=true.
    // Anmeldung, Passwort-Reset und Mail-Bestaetigung bleiben unberuehrt.
    disableSignUp: process.env.AUTH_ALLOW_SIGNUP !== 'true',
    // Login erfordert verifizierte E-Mail (Schutz der nicht-isolierten
    // kalender/assets-Apps). Seit 2026-06-30 mit echtem SMTP-Versand: neue
    // Accounts erhalten beim Signup eine Bestätigungs-Mail und können sich nach
    // Klick einloggen. Der Haupt-Account ist in der DB bereits emailVerified=true.
    requireEmailVerification: true,
    // Passwort-Reset per Mail. better-auth liefert Token; Link zeigt auf die
    // Shell-Seite /reset (siehe email.ts).
    sendResetPassword: async ({ user, token }) => {
      await sendResetMail(user.email, user.name ?? undefined, token);
    },
    resetPasswordTokenExpiresIn: 60 * 60, // 1h
  },
  emailVerification: {
    // Bestätigungs-Mail automatisch beim Signup versenden.
    sendOnSignUp: true,
    // Nach erfolgreicher Verifizierung direkt eingeloggt weiterleiten.
    autoSignInAfterVerification: true,
    expiresIn: 60 * 60, // 1h
    sendVerificationEmail: async ({ user, token }) => {
      await sendVerificationMail(user.email, user.name ?? undefined, token);
    },
  },
  user: {
    additionalFields: {
      // Der Tarif gehoert zum Konto, nicht zu einer App. Bis zum 02.09.2026 lag
      // er in `briefing_profiles.plan` der news-api, also in einer Tabelle, die
      // kein anderer Dienst sieht. Von hier aus reist er als `plan`-Claim im
      // Backend-JWT zu allen sieben Backends (packages/auth/backend-token.ts).
      //
      // ★★ `input: false` ist der Riegel, nicht die Kosmetik: ohne ihn nimmt
      // better-auth das Feld aus dem Signup-Rumpf entgegen, und wer sich
      // registriert, koennte sich `plan: "pro"` selbst mitgeben. Gesetzt wird
      // der Wert ausschliesslich serverseitig (Stripe-Webhook, Admin-Route).
      plan: { type: 'string', defaultValue: 'free', required: false, input: false },
      // Zustand des Abos aus Stripe-Sicht (active/past_due/canceled). Rein
      // informativ fuer die Oberflaeche; ueber Merkmale entscheidet `plan`.
      planStatus: { type: 'string', required: false, input: false },
    },
  },
  session: {
    // Lange, gleitende Session: native Apps halten den Session-Token in
    // EncryptedSharedPreferences und tauschen ihn gegen kurzlebige Backend-JWTs.
    // Bei häufigen App-Updates (In-Place, Daten bleiben) soll man NICHT jedes Mal
    // neu anmelden müssen → 90 Tage Laufzeit, alle 24h gleitend verlängert.
    // Sessions bleiben serverseitig widerrufbar (revokeOtherSessions bei PW-Wechsel).
    expiresIn: 60 * 60 * 24 * 90, // 90 Tage
    updateAge: 60 * 60 * 24, // täglich gleitend verlängern
  },
  advanced: {
    cookiePrefix: 'saganta',
    crossSubDomainCookies: {
      // ★ Nur einschalten, wenn es auch eine Domaene gibt. Mit leerem `domain`
      // stellt better-auth ein Cookie fuer "" aus, das kein Browser annimmt:
      // die Anmeldung schiene dann zu gelingen und waere beim naechsten
      // Aufruf weg. Aus heisst schlicht host-only, und das funktioniert.
      enabled: Boolean(cookieDomain),
      domain: cookieDomain,
    },
    useSecureCookies,
    // SG-02: Ohne aufgelöste Client-IP fällt better-auths Rate-Limiter auf EINEN
    // globalen per-Path-Bucket ("no-trusted-ip") zurück → ein Client kann Login/
    // Signup/Reset für ALLE sperren (DoS/Lockout). auth.saganta.de läuft hinter
    // Cloudflare; CF setzt die echte Client-IP single-value in `cf-connecting-ip`
    // (kein mehrgliedriges x-forwarded-for-Problem, kein trustedProxies-Count nötig).
    // Header per Env übersteuerbar, falls die Proxy-Kette einen anderen durchreicht.
    ipAddress: {
      ipAddressHeaders: (process.env.AUTH_IP_HEADERS ?? 'cf-connecting-ip')
        .split(',')
        .map((h) => h.trim())
        .filter(Boolean),
    },
  },
  trustedOrigins,
  // Native Apps haben keinen Browser-Cookie-Jar: das bearer-Plugin gibt bei
  // sign-in einen `set-auth-token`-Header aus und akzeptiert nachfolgend
  // `Authorization: Bearer <session-token>` für getSession. Cookie-Flow der
  // Web-BFFs bleibt unberührt (additiv).
  plugins: [bearer()],
});

export type Auth = typeof auth;
