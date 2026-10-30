import { createBetterAuthHandle } from '@saganta/auth';
import { sequence } from '@sveltejs/kit/hooks';
import type { Handle } from '@sveltejs/kit';
import { getAuthConfig } from '$lib/server/auth';
import { proxyHandle } from '$lib/server/proxy';

// 1) better-auth gated (Redirect auf Login wenn unauth, ausser /healthz).
// 2) proxyHandle reicht alles Uebrige an das native Backend weiter.
export const handle: Handle = sequence(
  createBetterAuthHandle({ cfg: getAuthConfig }),
  proxyHandle,
);
