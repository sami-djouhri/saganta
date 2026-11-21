/** `$app/forms` und `$app/stores` fuer die Probe: nichts wird abgeschickt. */
import { readable } from 'svelte/store';

export function enhance() {
  return { destroy() {} };
}

export const page = readable({ url: new URL(`https://projectdeck.home.arpa/projekte/probe${location.hash}`) });
