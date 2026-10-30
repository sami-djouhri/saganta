import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/** Öffentlicher Podcast-RSS-Feed, geschützt nur per unguessable feed_token. */
export const GET: RequestHandler = async ({ params, fetch }) => {
  const base = env.NEWS_API_BASE_URL;
  if (!base) throw error(503, 'NEWS_API_BASE_URL nicht gesetzt');
  const target = `${base.replace(/\/$/, '')}/api/news/briefing/public/feed/${encodeURIComponent(params.token)}`;
  const res = await fetch(target);
  if (!res.ok) throw error(res.status === 404 ? 404 : 502, 'Feed nicht gefunden');
  const xml = await res.text();
  return new Response(xml, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'X-Robots-Tag': 'noindex, nofollow',
      'Cache-Control': 'public, max-age=1800',
    },
  });
};
