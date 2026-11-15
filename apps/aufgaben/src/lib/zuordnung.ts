/**
 * Wohin eine Aufgabe gehoert: zu einem Projekt, zu einer Liste oder zu nichts.
 *
 * Der Dienst kennt die Listen seit der sechsten Fragerunde (04.11., sieben
 * Startlisten wie „Wohnung & Haushalt" und „Gesundheit & Körper"). Die Web-App
 * hat sie bis zum 13.11. nie abgerufen; fuer kein Konto waren sie angelegt.
 *
 * Projekt und Liste schliessen sich aus (der Dienst antwortet sonst 422).
 * Deshalb gibt es in der Oberflaeche EIN Feld „Zuordnung" mit einem Wert wie
 * `liste:<id>` oder `projekt:<slug>`, statt zwei Feldern, die man beide
 * setzen koennte.
 */
import type { Aufgabe, Liste } from './aufgaben-bff';
import { istOffen, nachDringlichkeit, type Gruppe } from './ordnen';

/** Der Wert der Auswahl fuer eine Aufgabe; leer heisst „nicht zugeordnet". */
export function zuordnungVon(a: Pick<Aufgabe, 'project_id' | 'liste_id'>): string {
  if (a.project_id) return `projekt:${a.project_id}`;
  if (a.liste_id) return `liste:${a.liste_id}`;
  return '';
}

/**
 * Der Wert der Auswahl als Felder fuer den Dienst.
 *
 * Beide Felder kommen immer mit: ein PUT, der nur `liste_id` setzt, liesse ein
 * altes Projekt stehen, und der Dienst lehnte die Aenderung ab. Ein
 * unbekannter Wert gibt `null`, damit die Aktion ihn ablehnt statt still zu
 * leeren.
 */
export function zuordnungAus(wert: string | null | undefined): { projekt: string | null; liste_id: string | null } | null {
  const w = (wert ?? '').trim();
  if (!w) return { projekt: null, liste_id: null };
  const [art, ...rest] = w.split(':');
  const kennung = rest.join(':');
  if (!kennung) return null;
  if (art === 'projekt') return { projekt: kennung, liste_id: null };
  if (art === 'liste') return { projekt: null, liste_id: kennung };
  return null;
}

/**
 * Die Listen fuer Gruppen und Auswahl, in der Reihenfolge des Dienstes.
 *
 * Dazu jede Liste, an der eine Aufgabe haengt, auch wenn der Abruf der Listen
 * gescheitert ist. Ohne diesen Platzhalter zeigte die Auswahl „nicht
 * zugeordnet", und das Speichern loeste die Aufgabe aus ihrer Liste
 * (dieselbe Falle wie bei den Projekten in `aktionen.ts`).
 */
export function listenAus(aufgaben: Aufgabe[], listen: Liste[]): Liste[] {
  const nach = new Map(listen.map((l) => [l.id, l]));
  let ende = listen.reduce((m, l) => Math.max(m, l.position), 0);
  for (const a of aufgaben) {
    if (!a.liste_id || nach.has(a.liste_id)) continue;
    nach.set(a.liste_id, { id: a.liste_id, name: 'Liste (nicht geladen)', position: ++ende });
  }
  return [...nach.values()].sort((x, y) => x.position - y.position);
}

/**
 * Gruppierung nach Liste, in der Reihenfolge der Listen.
 *
 * Leere Listen bleiben stehen: sie sind die Bereiche, in die man etwas legt,
 * und ohne sie saehe man nicht, dass es den Bereich gibt.
 */
export function nachListe(alle: Aufgabe[], listen: Liste[]): Gruppe[] {
  const offen = alle.filter(istOffen);
  return listen.map((l) => ({
    schluessel: `liste:${l.id}`,
    titel: l.name,
    symbol: 'list-todo',
    vertraulich: l.vertraulich ?? false,
    aufgaben: offen.filter((a) => a.liste_id === l.id).sort(nachDringlichkeit),
  }));
}
