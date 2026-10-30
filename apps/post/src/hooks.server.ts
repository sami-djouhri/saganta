import { createBetterAuthHandle } from '@saganta/auth';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';

// better-auth: locals.user setzen, unauth auf Login umleiten (ausser publicPaths).
// KEIN blanket-Owner-Gate mehr: Post ist für jeden eingeloggten Nutzer offen
// (E-Mail ist pro sub isoliert). Die single-tenant Briefkasten-Daten sind stattdessen
// pro Datenpfad via canAccessLetters() (lib/server/gate.ts) fail-safe abgesichert.
export const handle: Handle = createBetterAuthHandle({ cfg: getAuthConfig });
