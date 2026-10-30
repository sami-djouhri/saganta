import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ out: 'build' }),
    csrf: { trustedOrigins: [] },
    alias: {
      $lib: 'src/lib',
    },
    // In-App-Updater: Der Deploy stempelt den Git-SHA als APP_VERSION. SvelteKit
    // pollt alle 60 s die _app/version.json und setzt den `updated`-Store → das
    // <UpdateBanner> im Root-Layout erscheint. Fallback 'dev' bei lokalem Build.
    version: {
      name: process.env.APP_VERSION ?? 'dev',
      pollInterval: 60_000,
    },
  },
};

export default config;
