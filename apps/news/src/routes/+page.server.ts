import { env } from '$env/dynamic/private';
import { fail } from '@sveltejs/kit';
import {
  backendSecret,
  newsApiFetch,
  newsApiToken,
  type FeedItem,
  type FeedPage,
  type Source,
} from '$lib/news-api';
import type { Actions, PageServerLoad } from './$types';

const EMPTY_PAGE: FeedPage = { items: [], offset: 0, limit: 0, total: 0, next_offset: null };

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const failures: { api?: string } = {};
  let feed: FeedPage = EMPTY_PAGE;
  let sources: Source[] = [];
  let briefingIds: number[] = [];

  const source = url.searchParams.get('source') ?? '';
  const bookmarked = url.searchParams.get('bookmarked') === '1';

  if (locals.user && env.NEWS_API_BASE_URL) {
    const token = newsApiToken(locals.user, backendSecret());
    const params = new URLSearchParams();
    if (source) params.set('source', source);
    if (bookmarked) params.set('bookmarked', 'true');
    const qs = params.toString();
    try {
      [feed, sources] = await Promise.all([
        newsApiFetch<FeedPage>(
          env.NEWS_API_BASE_URL,
          `/api/news/feed${qs ? `?${qs}` : ''}`,
          token,
          fetch,
        ),
        newsApiFetch<Source[]>(env.NEWS_API_BASE_URL, '/api/news/sources', token, fetch),
      ]);
    } catch (err) {
      failures.api = String(err);
    }
    // Welche Artikel stehen im heutigen Briefing? Eigener Endpunkt, weil er nur
    // nachschlägt: `/today` würde beim blossen Öffnen der Feed-Liste ein Briefing
    // erzeugen. Scheitert er, fehlt nur die Markierung (Soft-Fail).
    briefingIds = await newsApiFetch<{ item_ids: number[] }>(
      env.NEWS_API_BASE_URL,
      '/api/news/briefing/today/item-ids',
      token,
      fetch,
    )
      .then((r) => r.item_ids ?? [])
      .catch(() => []);
  }

  return { feed, sources, failures, source, bookmarked, briefingIds };
};

/** Toggle read/bookmark für genau diesen User (sub-gescoped im Backend). */
async function toggle(
  locals: App.Locals,
  fetcher: typeof fetch,
  formData: FormData,
  field: 'read' | 'bookmarked',
) {
  if (!locals.user || !env.NEWS_API_BASE_URL) return fail(401, { error: 'not authenticated' });
  const itemId = Number(formData.get('item_id'));
  const value = formData.get('value') === 'true';
  if (!Number.isInteger(itemId)) return fail(400, { error: 'bad item_id' });

  const token = newsApiToken(locals.user, backendSecret());
  try {
    const item = await newsApiFetch<FeedItem>(
      env.NEWS_API_BASE_URL,
      `/api/news/items/${itemId}/state`,
      token,
      fetcher,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      },
    );
    return { item };
  } catch (err) {
    return fail(502, { error: String(err) });
  }
}

export const actions: Actions = {
  read: async ({ locals, fetch, request }) =>
    toggle(locals, fetch, await request.formData(), 'read'),
  bookmark: async ({ locals, fetch, request }) =>
    toggle(locals, fetch, await request.formData(), 'bookmarked'),
};
