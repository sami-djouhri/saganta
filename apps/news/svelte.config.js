import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    // In-App-Updater: Git-SHA als APP_VERSION (Build-Zeit!) → _app/version.json,
    // pollInterval → `updated`-Store → <UpdateBanner> im Layout.
    version: {
      name: process.env.APP_VERSION ?? 'dev',
      pollInterval: 60_000,
    },
    adapter: adapter({ out: 'build' }),
    csrf: { trustedOrigins: [] },
    alias: {
      $lib: 'src/lib',
    },
  },
};

export default config;
