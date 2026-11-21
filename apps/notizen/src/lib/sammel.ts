/**
 * Sammelaktionen über mehrere Notizen (Web wie App, seit 2026-11-14).
 *
 * Reine Übersetzung „Aktion + Auswahl → Aufrufe am Dienst", damit sie ohne
 * Server testbar ist. Der Dienst hat bewusst keine Sammelroute: jede Notiz
 * geht über denselben PATCH/DELETE wie einzeln, also auch über den Papierkorb
 * beim Löschen. Eine eigene Sammelroute wäre ein zweiter Weg, der beim
 * nächsten Feld vergessen wird.
 */
export const SAMMEL_AKTIONEN = [
  'anheften',
  'loesen',
  'archivieren',
  'zurueckholen',
  'verschieben',
  'loeschen',
] as const;
export type SammelAktion = (typeof SAMMEL_AKTIONEN)[number];

export interface Aufruf {
  methode: 'PATCH' | 'DELETE';
  pfad: string;
  rumpf?: Record<string, unknown>;
}

/** Höchstens so viele auf einmal: die Liste zeigt 100, mehr ist ein Fehler im Formular. */
export const SAMMEL_HOECHSTENS = 100;

export function ausgewaehlteIds(roh: FormDataEntryValue[]): number[] {
  const ids = roh.map((w) => Number(w)).filter((n) => Number.isInteger(n) && n > 0);
  return [...new Set(ids)];
}

/** `buch`: Kennung des Ziel-Notizbuchs, leer = aus dem Notizbuch lösen. */
export function sammelAufrufe(aktion: SammelAktion, ids: number[], buch = ''): Aufruf[] {
  const rumpf: Record<string, unknown> | null =
    aktion === 'anheften'
      ? { angeheftet: true }
      : aktion === 'loesen'
        ? { angeheftet: false }
        : aktion === 'archivieren'
          ? { archiviert: true }
          : aktion === 'zurueckholen'
            ? { archiviert: false }
            : aktion === 'verschieben'
              ? buch
                ? { notizbuch_id: Number(buch) }
                : { notizbuch_loesen: true }
              : null;
  return ids.map((id) =>
    rumpf
      ? { methode: 'PATCH', pfad: `/api/notizen/${id}`, rumpf }
      : { methode: 'DELETE', pfad: `/api/notizen/${id}` },
  );
}

const VERB: Record<SammelAktion, string> = {
  anheften: 'angeheftet',
  loesen: 'gelöst',
  archivieren: 'archiviert',
  zurueckholen: 'aus dem Archiv geholt',
  verschieben: 'verschoben',
  loeschen: 'in den Papierkorb gelegt',
};

export function sammelMeldung(aktion: SammelAktion, gelungen: number, fehler: number): string {
  const wort = (n: number) => (n === 1 ? '1 Notiz' : `${n} Notizen`);
  const teil = `${wort(gelungen)} ${VERB[aktion]}`;
  return fehler ? `${teil}, ${wort(fehler)} nicht (neu laden und nachsehen).` : `${teil}.`;
}

/** So viele Notizen lassen sich auf einmal verbinden (jede mit jeder, also bis 190 Paare). */
export const VERBINDEN_HOECHSTENS = 20;

export function verbindenMeldung(anzahl: number, neu: number): string {
  const paare = neu === 1 ? '1 neue Verbindung' : `${neu} neue Verbindungen`;
  return neu
    ? `${anzahl} Notizen miteinander verbunden, ${paare}.`
    : `Die ${anzahl} Notizen waren schon miteinander verbunden.`;
}
