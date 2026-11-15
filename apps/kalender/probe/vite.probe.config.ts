/**
 * Eigene Vite-Wurzel für die Ansichtsprobe, bewusst ohne SvelteKit.
 *
 * Der Grund ist nicht Bequemlichkeit: über die echte Route käme man nur mit
 * angemeldetem Konto und geladenen Serverdaten an die Komponente, und für eine
 * Frage nach Blockhöhen und Erreichbarkeit ist das der lange Weg durch eine
 * fremde Fehlerquelle. Hier wird genau eine Komponente mit festen Daten
 * gerendert, und was im Bild falsch ist, liegt an ihr.
 */
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  root: 'probe',
  plugins: [tailwindcss(), svelte()],
  resolve: {
    alias: {
      // Siehe ui-schlank.ts: der Sammel-Export braucht SvelteKit-Aliasse, die
      // es hier nicht gibt. Das Icon bleibt dabei das echte.
      '@saganta/ui': fileURLToPath(new URL('./ui-schlank.ts', import.meta.url)),
      // Monat und Gewohnheiten (seit 2026-11-13): `$lib` wie in SvelteKit,
      // `$app/forms` als Attrappe, die Formulare werden hier nicht abgeschickt.
      $lib: fileURLToPath(new URL('../src/lib', import.meta.url)),
      '$app/forms': fileURLToPath(new URL('./app-forms-attrappe.ts', import.meta.url)),
    },
  },
  server: {
    port: 8202,
    strictPort: true,
    host: '127.0.0.1',
  },
});
