import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/** Öffentlicher Stripe-Webhook-Proxy: das news-api-Backend liegt intern (cc-core),
 * Stripe erreicht nur das Frontend. Wir reichen den ROHEN Body + die Stripe-Signatur
 * unverändert durch, die Signaturprüfung (HMAC über den exakten Body) passiert im
 * Backend und darf den Payload nicht sehen, der neu serialisiert wurde. */
export const POST: RequestHandler = async ({ request, fetch }) => {
  const base = env.NEWS_API_BASE_URL;
  if (!base) throw error(503, 'NEWS_API_BASE_URL nicht gesetzt');
  const sig = request.headers.get('stripe-signature');
  const body = await request.arrayBuffer(); // roh, byte-genau
  const res = await fetch(`${base.replace(/\/$/, '')}/api/news/briefing/stripe/webhook`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(sig ? { 'Stripe-Signature': sig } : {}),
    },
    body,
  });
  const text = await res.text();
  return new Response(text, {
    status: res.status,
    headers: { 'Content-Type': res.headers.get('content-type') ?? 'application/json' },
  });
};
