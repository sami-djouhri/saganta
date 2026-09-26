import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import { backendSecret, newsApiToken } from '$lib/news-api';
import type { RequestHandler } from './$types';

/** Authed In-App-Player: streamt das eigene heutige Briefing-Audio (news-api cc-core). */
export const GET: RequestHandler = async ({ locals, fetch, url }) => {
  if (!locals.user) throw error(401, 'not authenticated');
  const base = env.NEWS_API_BASE_URL;
  if (!base) throw error(503, 'NEWS_API_BASE_URL nicht gesetzt');

  const date = url.searchParams.get('date');
  const token = newsApiToken(locals.user, backendSecret());
  const target = `${base.replace(/\/$/, '')}/api/news/briefing/audio/today${date ? `?date=${encodeURIComponent(date)}` : ''}`;
  const res = await fetch(target, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw error(res.status === 404 ? 404 : 502, 'Kein Audio');

  return new Response(res.body, {
    headers: {
      'Content-Type': res.headers.get('content-type') ?? 'audio/mpeg',
      'Cache-Control': 'private, max-age=300',
    },
  });
};
