/** `use:enhance` ohne SvelteKit: tut nichts, die Probe schickt nichts ab. */
export function enhance() {
  return { destroy() {} };
}

/** `$app/stores` fuer den Termin-Editor: nur die Adresse wird gelesen. */
import { readable } from 'svelte/store';
export const page = readable({ url: new URL('https://calendar.home.arpa/') });
