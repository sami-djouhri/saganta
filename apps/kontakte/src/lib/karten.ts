/**
 * CORS fuer die Ebene „Kontakte“ in karten.home.arpa. Nur genau diese
 * Herkunft bekommt die Antwort, mit Credentials; jede andere Seite liest sie
 * nicht, auch wenn ihr Browser das Saganta-Cookie mitschickt.
 */
export const KARTEN_HERKUNFT = 'https://karten.home.arpa';

export function kartenKoepfe(origin: string | null): Record<string, string> {
  const k: Record<string, string> = { 'Cache-Control': 'no-store', Vary: 'Origin' };
  if (origin === KARTEN_HERKUNFT) {
    k['Access-Control-Allow-Origin'] = origin;
    k['Access-Control-Allow-Credentials'] = 'true';
  }
  return k;
}
