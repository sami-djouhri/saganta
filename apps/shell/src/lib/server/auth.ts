import { env } from '$env/dynamic/private';
import { loadBetterAuthConfig, type BetterAuthConfig } from '@saganta/auth';

// Auth-Authority ist der zentrale saganta-auth-Service (better-auth).
// Lazy + memoized: Pflicht-Env erst zur Request-Zeit lesen (nicht beim Build).
let cached: BetterAuthConfig | undefined;
export function getAuthConfig(): BetterAuthConfig {
  return (cached ??= loadBetterAuthConfig(env));
}
