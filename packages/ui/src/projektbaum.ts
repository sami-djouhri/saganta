/**
 * Die Gliederung der Projekte (Ober- und Unterprojekte, seit 2026-11-15).
 *
 * Das ProjectDeck liefert je Projekt `eltern_ids` und `kinder_ids` (Zahlen).
 * Ein Projekt kann unter mehreren Oberprojekten stehen und ist trotzdem nur
 * einmal vorhanden; die Gliederung ist ein gerichteter Graph ohne Kreis, kein
 * Baum. Fuer eine Auswahl wird er hier zu einer eingerueckten Liste: ein
 * Projekt mit zwei Eltern steht unter beiden, der Wert bleibt derselbe Slug.
 *
 * Eine Quelle fuer Aufgaben, Notizen und Kalender. Drei eigene Fassungen
 * waeren drei Stellen, an denen ein Kreis oder ein fehlender Elternteil anders
 * behandelt wird.
 *
 * Reine Funktionen, ohne Netz: der Aufrufer holt die Liste und filtert vorher,
 * was er nicht zeigen will (z. B. archivierte Projekte).
 */

/** Ein Projekt, soweit die Gliederung es braucht. */
export interface BaumProjekt {
  slug: string;
  name: string;
  /** Die Zahl-Kennung im ProjectDeck; ohne sie steht das Projekt oben. */
  deck_id?: number | null;
  eltern_ids?: number[] | null;
  kinder_ids?: number[] | null;
  status?: string;
}

/** Eine Zeile der eingerueckten Liste. */
export interface BaumZeile {
  slug: string;
  name: string;
  status?: string;
  /** 0 = oberste Ebene. */
  tiefe: number;
  /** Eindeutig je Zeile (der Weg von oben), fuer `{#each … (schluessel)}`. */
  schluessel: string;
  /** Erstes Auftreten des Slugs: nur diese Zeile traegt eine Vorauswahl. */
  erstes: boolean;
}

/** Wie das ProjectDeck ein Projekt liefert (`GET /api/projects`). */
export interface DeckProjektRoh {
  id: number;
  slug: string;
  name: string;
  status?: string;
  eltern_ids?: number[] | null;
  kinder_ids?: number[] | null;
}

export function ausDeck(p: DeckProjektRoh): BaumProjekt {
  return {
    slug: p.slug,
    name: p.name,
    deck_id: p.id,
    eltern_ids: p.eltern_ids ?? [],
    kinder_ids: p.kinder_ids ?? [],
    status: p.status,
  };
}

function nachName(a: BaumProjekt, b: BaumProjekt): number {
  return a.name.localeCompare(b.name, 'de');
}

/**
 * Kinder je Projekt aus BEIDEN Richtungen: `kinder_ids` am Elternteil und
 * `eltern_ids` am Kind. Fehlt eine Seite (aelterer Stand, Teilliste), traegt
 * die andere. Nur Projekte, die in der Liste stehen.
 */
function kinderKarte(projekte: BaumProjekt[]): {
  nachId: Map<number, BaumProjekt>;
  kinder: Map<number, BaumProjekt[]>;
  hatEltern: Set<number>;
} {
  const nachId = new Map<number, BaumProjekt>();
  for (const p of projekte) if (p.deck_id != null) nachId.set(p.deck_id, p);
  const kinderIds = new Map<number, Set<number>>();
  const kante = (eltern: number, kind: number) => {
    if (eltern === kind || !nachId.has(eltern) || !nachId.has(kind)) return;
    if (!kinderIds.has(eltern)) kinderIds.set(eltern, new Set());
    kinderIds.get(eltern)!.add(kind);
  };
  for (const p of nachId.values()) {
    for (const k of p.kinder_ids ?? []) kante(p.deck_id!, k);
    for (const e of p.eltern_ids ?? []) kante(e, p.deck_id!);
  }
  const kinder = new Map<number, BaumProjekt[]>();
  const hatEltern = new Set<number>();
  for (const [e, ks] of kinderIds) {
    kinder.set(e, [...ks].map((k) => nachId.get(k)!).sort(nachName));
    for (const k of ks) hatEltern.add(k);
  }
  return { nachId, kinder, hatEltern };
}

/**
 * Die eingerueckte Liste: oben alle Projekte ohne (sichtbaren) Elternteil,
 * darunter ihre Kinder, je Ebene nach Namen.
 *
 * Ein Projekt, dessen Elternteil nicht in der Liste steht (archiviert,
 * weggefiltert), rueckt nach oben. Ein Kreis (darf es nicht geben) bricht an
 * der Stelle ab, an der er sich schliesst; was nur ueber einen Kreis
 * erreichbar waere, steht ebenfalls oben, damit nichts verschwindet.
 */
export function projektBaum(projekte: BaumProjekt[]): BaumZeile[] {
  const { kinder, hatEltern } = kinderKarte(projekte);
  const zeilen: BaumZeile[] = [];
  const gesehen = new Set<string>();
  const besucht = new Set<string>();

  const gehe = (p: BaumProjekt, tiefe: number, weg: string[], aufDemWeg: Set<number>) => {
    const schluessel = [...weg, p.slug].join('/');
    zeilen.push({
      slug: p.slug,
      name: p.name,
      status: p.status,
      tiefe,
      schluessel,
      erstes: !gesehen.has(p.slug),
    });
    gesehen.add(p.slug);
    besucht.add(p.slug);
    if (p.deck_id == null) return;
    const naechste = new Set(aufDemWeg).add(p.deck_id);
    for (const k of kinder.get(p.deck_id) ?? []) {
      if (naechste.has(k.deck_id!)) continue;
      gehe(k, tiefe + 1, [...weg, p.slug], naechste);
    }
  };

  const oben = projekte.filter((p) => p.deck_id == null || !hatEltern.has(p.deck_id)).sort(nachName);
  for (const p of oben) gehe(p, 0, [], new Set());
  // Nur ueber einen Kreis erreichbar: oben anhaengen statt verlieren.
  for (const p of [...projekte].sort(nachName)) {
    if (!besucht.has(p.slug)) gehe(p, 0, [], new Set());
  }
  return zeilen;
}

/**
 * Slug und alle Nachfahren-Slugs, jeder einmal, in Breitensuche.
 *
 * Dieselbe Rechnung wie `GET /api/projects/by-slug/{slug}/teilbaum` im
 * ProjectDeck (`gliederung.nachfahren`), nur ohne eigenen Aufruf je Filter:
 * die Liste mit `kinder_ids` liegt der Seite ohnehin vor. Ein unbekannter
 * Slug ergibt nur sich selbst.
 */
export function teilbaumSlugs(slug: string, projekte: BaumProjekt[]): string[] {
  const { kinder } = kinderKarte(projekte);
  const start = projekte.find((p) => p.slug === slug);
  if (!start || start.deck_id == null) return [slug];
  const gesehen = new Set<number>([start.deck_id]);
  const reihe: string[] = [slug];
  const offen = [...(kinder.get(start.deck_id) ?? [])];
  while (offen.length) {
    const p = offen.shift()!;
    if (gesehen.has(p.deck_id!)) continue;
    gesehen.add(p.deck_id!);
    reihe.push(p.slug);
    offen.push(...(kinder.get(p.deck_id!) ?? []));
  }
  return reihe;
}

/** Teilbaum je Projekt mit Unterprojekten (Projekte ohne Kinder fehlen). */
export function teilbaeume(projekte: BaumProjekt[]): Record<string, string[]> {
  const aus: Record<string, string[]> = {};
  for (const p of projekte) {
    const t = teilbaumSlugs(p.slug, projekte);
    if (t.length > 1) aus[p.slug] = t;
  }
  return aus;
}

/**
 * Beschriftung einer Zeile in einem `<option>`. Dort wirkt kein CSS-Abstand,
 * deshalb geschuetzte Leerzeichen und ein leiser Punkt vor jedem Unterprojekt.
 */
export function eingerueckt(zeile: Pick<BaumZeile, 'name' | 'tiefe'>): string {
  if (zeile.tiefe <= 0) return zeile.name;
  return `${'\u00a0\u00a0\u00a0'.repeat(zeile.tiefe)}·\u00a0${zeile.name}`;
}
