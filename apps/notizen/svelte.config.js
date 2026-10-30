import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    version: {
      name: process.env.APP_VERSION ?? 'dev',
      pollInterval: 60_000,
    },
    adapter: adapter({ out: 'build' }),
    // Kein zusaetzlich vertrauter Ursprung: die oeffentliche Leseseite laeuft
    // zwar unter n.saganta.de statt notizen.saganta.de, aber beide sprechen
    // jeweils mit sich selbst. Damit der Abgleich stimmt, muss die .env
    // PROTOCOL_HEADER/HOST_HEADER setzen (wie in den anderen Apps), sonst
    // haelt adapter-node den Ursprung fuer http:// und lehnt jedes POST ab.
    csrf: { trustedOrigins: [] },
    alias: {
      $lib: 'src/lib',
    },
  },
};

export default config;
