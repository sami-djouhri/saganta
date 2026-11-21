// Offline-Probe der Netzansicht und der [[-Vorschlaege mit erfundenen Daten.
// Baut ausserhalb von SvelteKit: $app/* sind Attrappen, $lib zeigt auf den
// echten Quelltext. Aufruf ueber lauf.sh.
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const hier = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  root: hier('.'),
  plugins: [tailwindcss(), svelte()],
  resolve: {
    alias: {
      $lib: hier('../../src/lib'),
      '$app/navigation': hier('./attrappe-navigation.ts'),
      '$app/stores': hier('./attrappe-app.ts'),
      '$app/environment': hier('./attrappe-app.ts'),
      '$app/forms': hier('./attrappe-app.ts'),
      '$env/dynamic/public': hier('./attrappe-env.ts'),
    },
  },
});
