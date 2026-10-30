/**
 * Suchbegriffe in einem Text markieren, ohne je HTML zu bauen.
 *
 * Die Funktion zerlegt den Text in Stücke und sagt zu jedem nur, ob es ein
 * Treffer ist; gerendert wird in der Komponente über Textknoten. Damit gilt
 * hier dieselbe Linie wie im Markdown-Renderer: aus Nutzereingaben (und die
 * Suchbegriffe sind eine) entsteht strukturell kein Markup.
 */

export interface Stueck {
  text: string;
  treffer: boolean;
}

/** Zeichen entschärfen, die in einem regulären Ausdruck etwas bedeuten. */
function entschaerfen(wert: string): string {
  return wert.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * `text` an den `begriffe`n zerteilen, Groß-/Kleinschreibung egal.
 *
 * Begriffe unter zwei Zeichen bleiben außen vor: ein einzelner Buchstabe
 * trifft fast jedes Wort und macht die Liste zum Flickenteppich. Längere
 * Begriffe zuerst, denn die Alternation nimmt die erste passende: stünde
 * „haus" vor „hausrat", bekäme „hausrat" nie einen ganzen Treffer.
 */
export function zerlegen(text: string, begriffe: string[]): Stueck[] {
  const woerter = [...new Set(begriffe.map((b) => b.trim()).filter((b) => b.length >= 2))].sort(
    (a, b) => b.length - a.length,
  );
  if (!text || woerter.length === 0) return text ? [{ text, treffer: false }] : [];

  const muster = new RegExp(`(${woerter.map(entschaerfen).join('|')})`, 'giu');
  const stuecke: Stueck[] = [];
  let letztesEnde = 0;
  for (const t of text.matchAll(muster)) {
    if (t.index > letztesEnde) {
      stuecke.push({ text: text.slice(letztesEnde, t.index), treffer: false });
    }
    stuecke.push({ text: t[0], treffer: true });
    letztesEnde = t.index + t[0].length;
  }
  if (letztesEnde < text.length) {
    stuecke.push({ text: text.slice(letztesEnde), treffer: false });
  }
  return stuecke;
}
