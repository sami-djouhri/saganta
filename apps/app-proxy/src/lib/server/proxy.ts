import { createHmac } from 'node:crypto';
import { env } from '$env/dynamic/private';
import { error, type Handle } from '@sveltejs/kit';

// Transparenter Reverse-Proxy. Laeuft NACH createBetterAuthHandle (sequence),
// d.h. locals.user ist gesetzt und unauthentifizierte Requests wurden schon
// zum Login umgeleitet. Alle Pfade ausser /healthz werden 1:1 an das native
// Backend (BACKEND_URL) weitergereicht, inkl. Methode, Query, Body und Header.
// Der angemeldete Nutzer wird als X-Saganta-* und (Kompatibilitaet zur alten
// AutheliaHeaderMiddleware) als remote-user/remote-groups eingestempelt.

// Hop-by-hop-Header, die nicht weitergereicht werden duerfen (RFC 7230).
const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
]);

function backendBaseUrl(): string {
  const base = env.BACKEND_URL;
  if (!base) throw error(500, 'BACKEND_URL not configured');
  return base.replace(/\/$/, '');
}

// Owner-Gate wie in den direkten BFFs (verify_jwt): Das native Backend teilt
// EINEN Datensatz ueber alle Nutzer (kein per-User-Schema). Ohne diese Pruefung
// saehe jeder eingeloggte better-auth-Account dieselben privaten Haushaltsdaten.
// ALLOWED_SUBS = kommaseparierte sub-Allowlist; leer = offen (Dev/Rueckwaertskompat).
// Entfaellt erst, wenn das jeweilige Backend echt user-isoliert ist (Multiuser-Phase).
function allowedSubs(): string[] {
  return (env.ALLOWED_SUBS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export const proxyHandle: Handle = async ({ event, resolve }) => {
  const { url, request, locals } = event;

  // /healthz von SvelteKit selbst beantworten (Docker-Healthcheck, public).
  if (url.pathname === '/healthz') return resolve(event);

  // Owner-Gate: nur erlaubte subs duerfen ans geteilte Backend (siehe allowedSubs()).
  const allow = allowedSubs();
  if (allow.length > 0 && !allow.includes(locals.user?.sub ?? '')) {
    throw error(403, 'Kein Zugriff auf diese App.');
  }

  const target = `${backendBaseUrl()}${url.pathname}${url.search}`;

  const headers = new Headers();
  for (const [k, v] of request.headers) {
    if (!HOP_BY_HOP.has(k.toLowerCase())) headers.set(k, v);
  }

  // Nutzerkontext einstempeln (aus better-auth-Session).
  const user = locals.user;
  headers.set('X-Saganta-Sub', user?.sub ?? '');
  // ★ Echtheitsnachweis fuer den Sub (seit 2026-09-05). Die nativen Backends
  // nahmen den Header bisher ungeprueft entgegen (Audit-Befund FCS-01): wer
  // sie direkt erreichte, konnte sich als beliebiger Mandant ausgeben. Sie
  // pruefen ihn jetzt gegen dasselbe Geheimnis (app/tenant_auth.py dort).
  //
  // Zuerst LOESCHEN, dann setzen. Die Schleife oben uebernimmt die eingehenden
  // Header pauschal, eine vom Client mitgeschickte Signatur wuerde sonst
  // weitergereicht. Sie passt zwar nicht zu dem Sub, den wir gleich setzen,
  // aber ein Header, den der Aufrufer bestimmt und der Nachweis heisst, hat
  // hier nichts verloren.
  headers.delete('X-Saganta-Sub-Sig');
  const tenantSecret = env.TENANT_SECRET ?? '';
  if (tenantSecret && user?.sub) {
    headers.set(
      'X-Saganta-Sub-Sig',
      createHmac('sha256', tenantSecret).update(user.sub).digest('hex'),
    );
  }
  headers.set('X-Saganta-Email', user?.email ?? '');
  const groups = user?.groups ?? [];
  headers.set('X-Saganta-Groups', groups.join(','));
  // Kompatibilitaet: das native Backend liest heute noch remote-user/-groups.
  headers.set('remote-user', user?.email ?? user?.sub ?? '');
  headers.set('remote-groups', groups.join(','));

  const method = request.method;
  const hasBody = method !== 'GET' && method !== 'HEAD';
  const body = hasBody ? await request.arrayBuffer() : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body,
      redirect: 'manual',
    });
  } catch (e) {
    throw error(502, `upstream error: ${e instanceof Error ? e.message : String(e)}`);
  }

  const respHeaders = new Headers();
  for (const [k, v] of upstream.headers) {
    if (!HOP_BY_HOP.has(k.toLowerCase())) respHeaders.set(k, v);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
};
