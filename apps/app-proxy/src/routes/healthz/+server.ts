import { json } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

export const GET = () => json({ ok: true, app: env.APP_NAME ?? 'saganta-app-proxy' });
