import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ out: 'build' }),
    // Kein CSRF-Override noetig: proxyHandle beantwortet alle Nicht-/healthz-
    // Pfade selbst (ohne resolve()), daher greift SvelteKits CSRF dort nicht.
    // Die Origin-Pruefung fuer unsafe-Methoden macht createBetterAuthHandle.
    alias: {
      $lib: 'src/lib',
    },
  },
};

export default config;
