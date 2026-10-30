import { env } from '$env/dynamic/private';
import { fail, redirect } from '@sveltejs/kit';
import {
  briefingFetch,
  type BriefingProfile,
  type BriefingSummary,
  type BriefingToday,
  type DeliveryConfig,
  type InterestOption,
  type PlanInfo,
} from '$lib/briefing-api';
import { backendSecret, newsApiFetch, newsApiToken } from '$lib/news-api';
import type { Actions, PageServerLoad } from './$types';

/** Formularwert als Zahl, aber leer/ungültig => null (Feld unverändert lassen). */
function numOrNull(value: FormDataEntryValue | null): number | null {
  const raw = String(value ?? '').trim().replace(',', '.');
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  if (!locals.user) redirect(303, '/login');
  const base = env.NEWS_API_BASE_URL;
  if (!base) return { configured: false as const };

  const user = locals.user;
  // ?tag=YYYY-MM-DD blättert im Archiv. Ohne Parameter: heute.
  const wantedDate = url.searchParams.get('tag') ?? '';
  const isArchive = /^\d{4}-\d{2}-\d{2}$/.test(wantedDate);

  const [interests, profile, delivery, plan, history] = await Promise.all([
    briefingFetch<InterestOption[]>(base, '/interests', user, fetch).catch(() => []),
    briefingFetch<BriefingProfile>(base, '/profile', user, fetch).catch(() => null),
    briefingFetch<DeliveryConfig>(base, '/delivery', user, fetch).catch(() => null),
    briefingFetch<PlanInfo>(base, '/plan', user, fetch).catch(() => null),
    briefingFetch<BriefingSummary[]>(base, '/history', user, fetch).catch(() => []),
  ]);
  // Heute: lazy erzeugen (Text). Archiv: nur nachschlagen, nie erzeugen. 404 = nichts da.
  let today: BriefingToday | null = null;
  if (profile?.enabled || isArchive) {
    const path = isArchive ? `/today?date=${wantedDate}` : '/today';
    today = await briefingFetch<BriefingToday>(base, path, user, fetch).catch(() => null);
  }

  return {
    configured: true as const,
    interests,
    profile,
    delivery,
    plan,
    today,
    history,
    viewedDate: isArchive ? wantedDate : '',
  };
};

function requireBase() {
  const base = env.NEWS_API_BASE_URL;
  if (!base) throw new Error('NEWS_API_BASE_URL nicht gesetzt');
  return base;
}

export const actions: Actions = {
  saveProfile: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    const tags = fd.getAll('interest').map(String);
    const interests = tags.map((tag) => ({
      tag,
      weight: Number(fd.get(`weight_${tag}`) ?? 1) || 1,
    }));
    const free_topics = String(fd.get('free_topics') ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const body = {
      enabled: fd.get('enabled') === 'on',
      interests,
      free_topics,
      length: String(fd.get('length') ?? 'mittel'),
      audio_enabled: fd.get('audio_enabled') === 'on',
      delivery_time: String(fd.get('delivery_time') ?? '05:00'),
      // Wetter-Ort: leere Felder heissen "nicht setzen" (null), nicht "auf 0 setzen":
      // 0/0 waere der Golf von Guinea.
      weather_lat: numOrNull(fd.get('weather_lat')),
      weather_lon: numOrNull(fd.get('weather_lon')),
      weather_place: String(fd.get('weather_place') ?? '').trim() || null,
    };
    try {
      await briefingFetch(requireBase(), '/profile', locals.user, fetch, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      return { saved: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  /** Merken/Gelesen aus dem Briefing heraus: schreibt in denselben Zustand, den
   *  der News-Feed führt (`UserItemState`). Deshalb der News-Endpunkt und nicht
   *  ein zweiter unter /briefing: ein Artikel, ein Zustand, zwei Ansichten. */
  itemState: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    const itemId = Number(fd.get('item_id'));
    const field = String(fd.get('field') ?? '');
    if (!Number.isInteger(itemId)) return fail(400, { error: 'bad item_id' });
    if (field !== 'read' && field !== 'bookmarked') return fail(400, { error: 'bad field' });
    try {
      await newsApiFetch(
        requireBase(),
        `/api/news/items/${itemId}/state`,
        newsApiToken(locals.user, backendSecret()),
        fetch,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [field]: fd.get('value') === 'true' }),
        },
      );
      return { itemStateSaved: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  feedback: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    try {
      await briefingFetch(requireBase(), '/feedback', locals.user, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ link: String(fd.get('link')), signal: Number(fd.get('signal')) }),
      });
      return { feedback: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  generateAudio: async ({ locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    try {
      await briefingFetch(requireBase(), '/generate', locals.user, fetch, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ with_audio: true }),
      });
      return { audioRequested: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  setWebhook: async ({ locals, fetch, request }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    const fd = await request.formData();
    try {
      await briefingFetch(requireBase(), '/delivery', locals.user, fetch, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          webhook_url: String(fd.get('webhook_url') ?? ''),
          webhook_secret: String(fd.get('webhook_secret') ?? ''),
        }),
      });
      return { webhookSaved: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },

  checkout: async ({ locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    let url: string;
    try {
      const res = await briefingFetch<{ url: string }>(requireBase(), '/checkout', locals.user, fetch, {
        method: 'POST',
      });
      url = res.url;
    } catch (err) {
      // 503 = Stripe (noch) nicht konfiguriert → UI zeigt weiter den mailto-Fallback.
      return fail(503, { error: 'Zahlung ist noch nicht aktiviert', checkoutUnavailable: true });
    }
    redirect(303, url);
  },

  rotateFeed: async ({ locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'not authenticated' });
    try {
      const dc = await briefingFetch<DeliveryConfig>(requireBase(), '/delivery/rotate', locals.user, fetch, {
        method: 'POST',
      });
      return { rotated: true, feed_url: dc.feed_url };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },
};
