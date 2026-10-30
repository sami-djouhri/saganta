import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals, url }) => {
  // `host` traegt den Raum, in dem diese Anfrage ankam (`home.arpa` gegen
  // `saganta.de`). App-Wechsler und Cross-App-Links bilden ihre Ziele daraus,
  // statt fest auf die oeffentliche Domaene zu zeigen; Begruendung in
  // `packages/ui/src/apps.ts`. Serverseitig gelesen, weil der Wert damit schon
  // im ersten Rendern stimmt und kein Hydration-Unterschied entstehen kann.
  return { user: locals.user, host: url.host };
};
