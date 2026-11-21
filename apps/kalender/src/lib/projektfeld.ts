/** Das Feld „Projekt" am Termin (seit 2026-11-15), ohne Server-Zugriffe und damit testbar. */

const SLUG = /^[a-z0-9][a-z0-9-]{0,119}$/;

/**
 * Das Feld „Projekt" aus dem Formular.
 *
 * Neu angelegt: nur ein gesetzter Slug geht mit. Beim Bearbeiten nur bei einer
 * Aenderung gegenueber `projekt_alt`; leerer Text loest den Bezug (so nimmt
 * ihn der kalender-bff). `fehler` bei einem Wert, der kein Slug ist.
 */
export function projektFeld(
  neu: string,
  alt: string | null,
  bearbeiten: boolean,
): { projekt?: string } | { fehler: string } {
  const wert = neu.trim();
  if (wert && !SLUG.test(wert)) return { fehler: 'Unbekanntes Projekt.' };
  if (!bearbeiten) return wert ? { projekt: wert } : {};
  if (alt === null || wert === alt.trim()) return {};
  return { projekt: wert };
}
