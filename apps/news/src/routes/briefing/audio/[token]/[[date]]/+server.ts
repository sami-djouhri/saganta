import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * Öffentliche Audio-Enclosure (Podcast/Alexa/Lautsprecher): geschützt nur per feed_token.
 *
 * `Range` wird durchgereicht, damit Abspieler springen können, ohne das lud jeder
 * Sprung die ganze Datei neu (oder scheiterte). `date` darf `latest` sein.
 */
export const GET: RequestHandler = async ({ params, fetch, request }) => {
  const base = env.NEWS_API_BASE_URL;
  if (!base) throw error(503, 'NEWS_API_BASE_URL nicht gesetzt');
  const datum = params.date ?? 'latest';
  const target =
    `${base.replace(/\/$/, '')}/api/news/briefing/public/audio/` +
    `${encodeURIComponent(params.token)}/${encodeURIComponent(datum)}`;

  const range = request.headers.get('range');
  const res = await fetch(target, range ? { headers: { range } } : undefined);
  if (!res.ok && res.status !== 206) throw error(res.status === 404 ? 404 : 502, 'Kein Audio');

  const headers = new Headers({
    'Content-Type': res.headers.get('content-type') ?? 'audio/mpeg',
    'X-Robots-Tag': 'noindex, nofollow',
    'Cache-Control': 'public, max-age=3600',
    'Accept-Ranges': res.headers.get('accept-ranges') ?? 'bytes',
  });
  for (const name of ['content-range', 'content-length']) {
    const value = res.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(res.body, { status: res.status, headers });
};
