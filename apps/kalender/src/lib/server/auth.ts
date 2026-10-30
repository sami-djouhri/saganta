import { env } from '$env/dynamic/private';
import { loadBetterAuthConfig, type BetterAuthConfig } from '@saganta/auth';

// Auth-Authority ist der zentrale saganta-auth-Service (better-auth).
// Diese App hostet keine Login-UI: unauthentifiziert → Redirect auf shell /login
// (AUTH_LOGIN_URL=https://saganta.de/login). Lazy + memoized (Env erst zur Request-Zeit).
let cached: BetterAuthConfig | undefined;
export function getAuthConfig(): BetterAuthConfig {
  return (cached ??= loadBetterAuthConfig(env));
}
