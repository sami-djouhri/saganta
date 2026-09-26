import { env } from '$env/dynamic/private';
import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * Das eigene Briefing als JSON, ohne Login, nur mit dem Feed-Token.
 *
 * Gegenstück zur Audio-Enclosure: bisher gab es token-basiert nur RSS-XML und MP3.
 * Damit lässt sich das Briefing aus einem Skript oder einer Heim-Automation
 * abholen, ohne den kurzlebigen, BFF-internen Token nachzubauen.
 *
 * `date` ist optional; ohne Angabe (oder mit `latest`) kommt das neueste Briefing:
 * ein Client muss dann nicht wissen, welches Datum erzeugt wurde.
 */
export const GET: RequestHandler = async ({ params, fetch }) => {
  const base = env.NEWS_API_BASE_URL;
  if (!base) throw error(503, 'NEWS_API_BASE_URL nicht gesetzt');
  const datum = params.date ?? 'latest';
  const target =
    `${base.replace(/\/$/, '')}/api/news/briefing/public/briefing/` +
    `${encodeURIComponent(params.token)}/${encodeURIComponent(datum)}`;
  const res = await fetch(target);
  if (!res.ok) throw error(res.status === 404 ? 404 : 502, 'Kein Briefing');
  return json(await res.json(), {
    headers: {
      'X-Robots-Tag': 'noindex, nofollow',
      'Cache-Control': 'private, max-age=300',
    },
  });
};
