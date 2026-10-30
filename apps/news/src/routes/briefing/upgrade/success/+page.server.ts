import { env } from '$env/dynamic/private';
import { redirect } from '@sveltejs/kit';
import { briefingFetch, type PlanInfo } from '$lib/briefing-api';
import type { PageServerLoad } from './$types';

/** Stripe-Rückkehr nach erfolgreichem Checkout. Der Webhook setzt plan=pro
 * asynchron; hier zeigen wir den aktuellen Stand und lassen die Seite kurz pollen. */
export const load: PageServerLoad = async ({ locals, fetch }) => {
  if (!locals.user) redirect(303, '/login');
  const base = env.NEWS_API_BASE_URL;
  if (!base) return { isPro: false as const };
  const plan = await briefingFetch<PlanInfo>(base, '/plan', locals.user, fetch).catch(() => null);
  return { isPro: plan?.is_pro ?? false };
};
