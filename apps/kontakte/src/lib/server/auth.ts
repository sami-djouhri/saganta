import { env } from '$env/dynamic/private';
import { loadBetterAuthConfig, type BetterAuthConfig } from '@saganta/auth';

// Auth-Authority ist der zentrale saganta-auth-Service (better-auth).
// Diese App hostet keine Login-UI: unauthentifiziert → Redirect auf shell
// /login (AUTH_LOGIN_URL=https://saganta.de/login). Lazy + memoized, damit
// Pflicht-Env erst zur Request-Zeit gelesen wird.
let zwischengespeichert: BetterAuthConfig | undefined;
export function getAuthConfig(): BetterAuthConfig {
  return (zwischengespeichert ??= loadBetterAuthConfig(env));
}
