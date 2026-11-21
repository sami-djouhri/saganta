/**
 * Ansichtsprobe des ProjectDecks, ohne SvelteKit und ohne Anmeldung (Muster
 * apps/kalender/probe). Gerendert werden Gliederung und Projektakte mit
 * erfundenen Daten aus probe.ts; `pnpm probe:bauen` schreibt probe/dist,
 * das `probe/fotografieren.sh` in zwei Breiten ablichtet.
 */
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const hier = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  root: 'probe',
  base: './',
  plugins: [tailwindcss(), svelte()],
  resolve: {
    alias: {
      '@saganta/ui': hier('./ui-schlank.ts'),
      $lib: hier('../src/lib'),
      '$app/forms': hier('./app-attrappe.ts'),
      '$app/stores': hier('./app-attrappe.ts'),
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
});
