import { env } from '$env/dynamic/private';
import {
  assetsApiFetch,
  assetsApiToken,
  backendSecret,
  type Asset,
} from '$lib/assets-api';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, fetch, url }) => {
  const failures: { api?: string } = {};
  let assets: Asset[] = [];
  let recommendations: Asset[] = [];

  const filter = url.searchParams.get('source') ?? '';

  if (locals.user && env.ASSETS_API_BASE_URL) {
    const token = assetsApiToken(locals.user, backendSecret());
    const path = filter ? `/api/assets?source=${encodeURIComponent(filter)}` : '/api/assets';
    try {
      [assets, recommendations] = await Promise.all([
        assetsApiFetch<Asset[]>(env.ASSETS_API_BASE_URL, path, token, fetch),
        assetsApiFetch<Asset[]>(
          env.ASSETS_API_BASE_URL,
          '/api/assets/recommendations',
          token,
          fetch,
        ),
      ]);
    } catch (err) {
      failures.api = String(err);
    }
  }

  return { assets, recommendations, failures, filter };
};
