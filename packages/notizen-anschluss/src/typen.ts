/**
 * Die Begriffe, die beide Seiten brauchen: Server-Client und Oberfläche.
 *
 * ⚠️ **Diese Datei darf nichts importieren, was nur auf dem Server läuft.**
 * `anschluss.ts` zieht über `@saganta/auth` das `node:crypto` herein; eine
 * Svelte-Komponente, die von dort auch nur einen Wert holt, nimmt das in ihr
 * Browser-Bundle mit. Deshalb liegen Typen und Maße hier und werden von beiden
 * Seiten gelesen, statt in der Oberfläche als Abschrift nochmal zu stehen,
 * wo sie beim nächsten neuen Typ still veralten würden.
 */

/** Die Gegenstücke, an denen eine Notiz hängen kann. Spiegelt `VERKNUEPFUNGS_TYPEN`. */
export const VERKNUEPFUNGS_TYPEN = [
  'termin',
  'aufgabe',
  'ziel',
  'projekt',
  'kontakt',
  'brief',
] as const;

export type VerknuepfungsTyp = (typeof VERKNUEPFUNGS_TYPEN)[number];

export function istVerknuepfungsTyp(wert: unknown): wert is VerknuepfungsTyp {
  return typeof wert === 'string' && (VERKNUEPFUNGS_TYPEN as readonly string[]).includes(wert);
}

/** Wie das Gegenstück im Dialog heißt, in der Sprache des Nutzers. */
export const TYP_NAME: Record<VerknuepfungsTyp, string> = {
  termin: 'Termin',
  aufgabe: 'Aufgabe',
  ziel: 'Ziel',
  projekt: 'Projekt',
  kontakt: 'Kontakt',
  brief: 'Brief',
};

/** Eine Notiz, soweit eine fremde App sie anzeigt. */
export interface NotizKurz {
  id: number;
  titel: string;
  ausschnitt?: string;
  tags?: string[];
  geaendert_am?: string;
}

/** Das Ziel, an dem die Notiz hängen soll. */
export interface Ziel {
  typ: VerknuepfungsTyp;
  /** Kennung des Gegenstücks. Zahl, UUID oder Slug, je nach Quelle. */
  ref: string;
  /**
   * Beschriftung des Gegenstücks. Wird in der notizen-api als **Kopie**
   * gespeichert: benennt jemand den Termin um, zeigt die Notiz weiter, worauf
   * sie sich bezog, und die Liste bleibt lesbar, auch wenn die Quelle gerade
   * nicht antwortet.
   */
  label: string;
}

/** Längstes Label, das die notizen-api annimmt (`VerknuepfungAn.label`). */
export const LABEL_MAX = 300;
/** Längster Titel, den die notizen-api annimmt (`NotizAn.titel`). */
export const TITEL_MAX = 300;
