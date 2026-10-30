import { json } from '@sveltejs/kit';
import { createChallenge, captchaEnabled } from '$lib/server/captcha';
import type { RequestHandler } from './$types';

/** Same-origin PoW-Challenge für das <captcha-guard>-Widget. Lokal signiert
 * (CAPTCHA_HMAC_KEY), kein externer Dienst: überlebt den geplanten netcup-Umzug.
 * Ohne Key (captchaEnabled=false) liefert die Route 204 → Widget bleibt unsichtbar,
 * Verify lässt in captchaOk() alles durch (Captcha global aus). */
export const GET: RequestHandler = async () => {
  if (!captchaEnabled()) return new Response(null, { status: 204 });
  return json(createChallenge(), {
    headers: { 'Cache-Control': 'no-store' },
  });
};
