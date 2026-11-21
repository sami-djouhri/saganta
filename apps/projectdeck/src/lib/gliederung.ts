/**
 * Ober- und Unterprojekte (Entscheide U1 bis U8, 15.11.).
 *
 * Ein Projekt kann mehrere Eltern haben und erscheint dann unter jedem; es
 * bleibt dasselbe Projekt. Die Baeume hier sind nur Anzeige, die Wahrheit
 * sind `eltern_ids`/`kinder_ids` aus der projectdeck-api.
 */
import type { Project } from './types';

export interface Knoten {
  projekt: Project;
  kinder: Knoten[];
  /** Summen ueber diesen Knoten und alles darunter (jedes Projekt einmal). */
  summe: { offen: number; hoch: number; ueberfaellig: number; projekte: number };
}

/** Wurzeln: Projekte ohne Eltern (oder deren Eltern nicht in der Liste stehen). */
export function wurzeln(projekte: Project[]): Project[] {
  const da = new Set(projekte.map((p) => p.id));
  return projekte.filter((p) => !(p.eltern_ids ?? []).some((e) => da.has(e)));
}

/** Alle Nachfahren-Kennungen, jede einmal, ohne den Start. Kreisfest. */
export function nachfahren(nachId: Map<number, Project>, start: number): number[] {
  const gesehen = new Set<number>([start]);
  const reihe: number[] = [];
  const offen = [...(nachId.get(start)?.kinder_ids ?? [])];
  while (offen.length) {
    const id = offen.shift()!;
    if (gesehen.has(id) || !nachId.has(id)) continue;
    gesehen.add(id);
    reihe.push(id);
    offen.push(...(nachId.get(id)?.kinder_ids ?? []));
  }
  return reihe;
}

/** Baum ab den Wurzeln; `sortieren` ordnet Geschwister. */
export function baum(projekte: Project[], sortieren: (a: Project, b: Project) => number): Knoten[] {
  const nachId = new Map(projekte.map((p) => [p.id, p]));
  const bau = (p: Project, pfad: Set<number>): Knoten => {
    const kinder = (p.kinder_ids ?? [])
      .map((id) => nachId.get(id))
      .filter((k): k is Project => !!k && !pfad.has(k.id))
      .sort(sortieren)
      .map((k) => bau(k, new Set([...pfad, k.id])));
    const teil = [p.id, ...nachfahren(nachId, p.id)].map((id) => nachId.get(id)!);
    return {
      projekt: p,
      kinder,
      summe: {
        offen: teil.reduce((s, q) => s + (q.open_tasks ?? 0), 0),
        hoch: teil.reduce((s, q) => s + (q.open_high ?? 0), 0),
        ueberfaellig: teil.reduce((s, q) => s + (q.overdue_tasks ?? 0), 0),
        projekte: teil.length - 1,
      },
    };
  };
  return wurzeln(projekte).sort(sortieren).map((p) => bau(p, new Set([p.id])));
}

/** Flache Liste fuer eine Auswahl, eingerueckt nach Tiefe (Mehrfacheltern mehrfach). */
export function eingerueckt(projekte: Project[]): { projekt: Project; tiefe: number }[] {
  const nachName = (a: Project, b: Project) => a.name.localeCompare(b.name, 'de');
  const aus: { projekt: Project; tiefe: number }[] = [];
  const laufe = (k: Knoten, tiefe: number) => {
    aus.push({ projekt: k.projekt, tiefe });
    for (const kind of k.kinder) laufe(kind, tiefe + 1);
  };
  for (const w of baum(projekte, nachName)) laufe(w, 0);
  return aus;
}

/** Kennungen, die als Oberprojekt von `id` nicht in Frage kommen (sich selbst und alle darunter). */
export function verboteneEltern(projekte: Project[], id: number): Set<number> {
  const nachId = new Map(projekte.map((p) => [p.id, p]));
  return new Set([id, ...nachfahren(nachId, id)]);
}
