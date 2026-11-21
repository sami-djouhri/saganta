/**
 * Projektbezug einer Aufgabe mit Unterprojekten (seit 2026-11-15).
 *
 * Eine Aufgabe hat ein Zuhause (`project_id`) und darf zusaetzlich an bis zu
 * zehn weiteren Projekten stehen (`weitere_projekte`). Ein Oberprojekt zeigt
 * alles, was an ihm und an seinen Nachfahren haengt (Entscheid U7), mit
 * dem Schalter „nur dieses Projekt" fuer den engen Blick.
 *
 * Reine Funktionen: die Gliederung kommt als Teilbaum-Karte vom Server
 * (`Bestand.teilbaum`, gerechnet wie `GET /api/projects/by-slug/{slug}/teilbaum`).
 */
import { projektBaum, teilbaumSlugs, type BaumZeile } from '@saganta/ui';
import type { Aufgabe, Projekt } from './aufgaben-bff';
import { istOffen, nachDringlichkeit } from './ordnen';

/** Alle Projekte einer Aufgabe: Zuhause zuerst, dann die weiteren. */
export function projekteDerAufgabe(a: Pick<Aufgabe, 'project_id' | 'weitere_projekte'>): string[] {
  const alle = [a.project_id, ...(a.weitere_projekte ?? [])].filter((s): s is string => !!s);
  return [...new Set(alle)];
}

/** Die Slugs, die ein Projektfilter trifft. */
export function filterSlugs(slug: string, nurDieses: boolean, teilbaum: Record<string, string[]>): Set<string> {
  return new Set(nurDieses ? [slug] : (teilbaum[slug] ?? [slug]));
}

/** Trifft die Aufgabe einen der Slugs, ueber ihr Zuhause oder ein weiteres Projekt? */
export function passtZuProjekten(a: Pick<Aufgabe, 'project_id' | 'weitere_projekte'>, slugs: Set<string>): boolean {
  return projekteDerAufgabe(a).some((s) => slugs.has(s));
}

/** Die Projekte als Baumeingang (Slug als Kennung, Zahl aus dem ProjectDeck). */
export function alsBaum(projekte: Projekt[]) {
  return projekte.map((p) => ({
    slug: p.slug ?? p.id,
    name: p.name,
    deck_id: p.deck_id ?? null,
    eltern_ids: p.eltern_ids ?? [],
    kinder_ids: p.kinder_ids ?? [],
    status: p.status,
  }));
}

/** Eine Zeile der Seite „Bereiche und Projekte". */
export interface ProjektAbschnitt {
  zeile: BaumZeile;
  /** Offene Aufgaben mit diesem Projekt als Zuhause. */
  eigene: Aufgabe[];
  /** Offene Aufgaben, die hier nur angeheftet sind. */
  angeheftet: Aufgabe[];
  /** Offene Aufgaben im ganzen Teilbaum, jede einmal. */
  imTeilbaum: number;
  /**
   * Zweites Auftreten eines Projekts mit mehreren Eltern: nur die Kopfzeile,
   * die Aufgaben stehen beim ersten Auftreten (sonst zaehlte man sie doppelt).
   */
  verweis: boolean;
}

/**
 * Die Projektgruppen als Baum. Ein Zweig ohne offene Aufgabe faellt weg; ein
 * Oberprojekt ohne eigene Aufgabe bleibt als Ueberschrift stehen, wenn darunter
 * etwas offen ist.
 */
export function projektAbschnitte(aufgaben: Aufgabe[], projekte: Projekt[]): ProjektAbschnitt[] {
  const offen = aufgaben.filter(istOffen);
  const baum = alsBaum(projekte);
  const abschnitte: ProjektAbschnitt[] = [];
  for (const zeile of projektBaum(baum)) {
    const slugs = new Set(teilbaumSlugs(zeile.slug, baum));
    const imTeilbaum = offen.filter((a) => passtZuProjekten(a, slugs)).length;
    if (imTeilbaum === 0) continue;
    const verweis = !zeile.erstes;
    abschnitte.push({
      zeile,
      eigene: verweis ? [] : offen.filter((a) => a.project_id === zeile.slug).sort(nachDringlichkeit),
      angeheftet: verweis
        ? []
        : offen
            .filter((a) => a.project_id !== zeile.slug && (a.weitere_projekte ?? []).includes(zeile.slug))
            .sort(nachDringlichkeit),
      imTeilbaum,
      verweis,
    });
  }
  return abschnitte;
}
