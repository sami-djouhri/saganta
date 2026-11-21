/**
 * Notizen nach Projekt, mit Unterprojekten (seit 2026-11-15, Entscheid U7).
 *
 * Die notizen-api kennt nur Verknuepfungen (`typ = projekt`, `ref = Slug`).
 * Ein Oberprojekt trifft alle Notizen, die an ihm ODER an einem seiner
 * Nachfahren haengen; geholt wird das in EINEM Aufruf ueber
 * `/api/notizen/verknuepft?typ=projekt&refs=a,b,c`. Notizbuch, Tag und Suche
 * wirken danach hier, weil jene Route sie nicht kennt.
 */
import type { NotizKurz } from './types';

/** Darf als Projekt-Slug in die Abfrage. */
export function istSlug(wert: string): boolean {
  return /^[a-z0-9][a-z0-9-]{0,119}$/.test(wert);
}

export interface Einschraenkung {
  notizbuch?: string | null;
  tag?: string | null;
  /** Treffer der Volltextsuche in deren Reihenfolge; `null` = keine Suche. */
  treffer?: number[] | null;
}

/**
 * Aus der Antwort je Slug eine Liste: jede Notiz einmal, Notizbuch und Tag
 * angewandt, sortiert wie die normale Liste (angeheftet zuerst, dann zuletzt
 * geaendert) oder bei einer Suche in deren Rangfolge.
 */
export function notizenDesProjekts(nach: Record<string, NotizKurz[]>, e: Einschraenkung = {}): NotizKurz[] {
  const eins = new Map<number, NotizKurz>();
  for (const liste of Object.values(nach)) for (const n of liste) eins.set(n.id, n);
  let alle = [...eins.values()];
  if (e.notizbuch) alle = alle.filter((n) => String(n.notizbuch_id ?? '') === e.notizbuch);
  if (e.tag) {
    const t = e.tag.trim().toLowerCase();
    alle = alle.filter((n) => n.tags.some((x) => x.toLowerCase() === t));
  }
  if (e.treffer) {
    const rang = new Map(e.treffer.map((id, i) => [id, i]));
    return alle.filter((n) => rang.has(n.id)).sort((a, b) => rang.get(a.id)! - rang.get(b.id)!);
  }
  return alle.sort(
    (a, b) => Number(b.angeheftet) - Number(a.angeheftet) || b.geaendert_am.localeCompare(a.geaendert_am),
  );
}
