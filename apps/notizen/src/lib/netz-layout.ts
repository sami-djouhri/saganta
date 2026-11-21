/**
 * Anordnung der Netzansicht (seit 2026-11-20): ein kleines Kräftemodell ohne
 * Abhängigkeit. Verbundene Notizen ziehen sich an, alle stoßen sich ab, eine
 * schwache Schwerkraft hält das Ganze in der Mitte.
 *
 * Deterministisch: die Startpunkte liegen auf einer Spirale in der
 * Reihenfolge der Knoten, nicht zufällig. Dieselben Daten ergeben dieselbe
 * Karte, beim Neuladen springt nichts, und der Test kann Abstände vergleichen.
 */

export interface Punkt {
  x: number;
  y: number;
}

export interface LayoutOptionen {
  /** Wunschlänge einer Kante. */
  laenge?: number;
  durchlaeufe?: number;
}

interface Knoten {
  x: number;
  y: number;
  dx: number;
  dy: number;
  grad: number;
}

const GOLDENER_WINKEL = Math.PI * (3 - Math.sqrt(5));

export function netzLayout(
  ids: number[],
  kanten: { a: number; b: number }[],
  optionen: LayoutOptionen = {},
): Map<number, Punkt> {
  const laenge = optionen.laenge ?? 70;
  const durchlaeufe = optionen.durchlaeufe ?? 300;
  const n = ids.length;
  const index = new Map(ids.map((id, i) => [id, i]));
  // Ein Objekt je Knoten statt paralleler Felder: so bleibt jeder Zugriff
  // typsicher (noUncheckedIndexedAccess), ohne Ausrufezeichen an jeder Stelle.
  const pkte = ids.map((_, i) => {
    const r = laenge * 0.6 * Math.sqrt(i + 0.5);
    return { x: r * Math.cos(i * GOLDENER_WINKEL), y: r * Math.sin(i * GOLDENER_WINKEL), dx: 0, dy: 0, grad: 0 };
  });
  const paare: [Knoten, Knoten][] = [];
  for (const k of kanten) {
    const a = pkte[index.get(k.a) ?? -1];
    const b = pkte[index.get(k.b) ?? -1];
    if (a && b && a !== b) {
      paare.push([a, b]);
      a.grad++;
      b.grad++;
    }
  }

  const abstossung = laenge * laenge;
  // Ab einigen hundert Knoten wird der Vergleich jeder mit jedem teuer; weit
  // entfernte Paare tragen dann ohnehin kaum etwas bei.
  const reichweite2 = n > 400 ? (laenge * 6) ** 2 : Infinity;

  for (let lauf = 0; lauf < durchlaeufe; lauf++) {
    const temperatur = laenge * (1 - lauf / durchlaeufe) + 0.5;
    for (const p of pkte) {
      p.dx = 0;
      p.dy = 0;
    }
    pkte.forEach((p, i) => {
      for (let j = i + 1; j < n; j++) {
        const q = pkte[j]!;
        let ex = p.x - q.x;
        let ey = p.y - q.y;
        let d2 = ex * ex + ey * ey;
        if (d2 > reichweite2) continue;
        if (d2 < 0.01) {
          // Zwei Punkte aufeinander: in eine feste Richtung auseinander.
          ex = 0.1 * (i - j);
          ey = 0.1;
          d2 = ex * ex + ey * ey;
        }
        const kraft = abstossung / d2;
        p.dx += ex * kraft;
        p.dy += ey * kraft;
        q.dx -= ex * kraft;
        q.dy -= ey * kraft;
      }
    });
    for (const [a, b] of paare) {
      const ex = a.x - b.x;
      const ey = a.y - b.y;
      const d = Math.sqrt(ex * ex + ey * ey) || 0.01;
      const kraft = (d - laenge) / d;
      a.dx -= ex * kraft;
      a.dy -= ey * kraft;
      b.dx += ex * kraft;
      b.dy += ey * kraft;
    }
    for (const p of pkte) {
      // Notizen ohne Verbindung zieht es schwächer zur Mitte: sie legen sich
      // als Ring um das Netz, statt sich zwischen die Gruppen zu schieben.
      const schwere = (p.grad > 0 ? 0.05 : 0.035) * laenge * 0.1;
      p.dx -= p.x * schwere;
      p.dy -= p.y * schwere;
      const d = Math.sqrt(p.dx * p.dx + p.dy * p.dy);
      if (d > 0) {
        const schritt = Math.min(d, temperatur);
        p.x += (p.dx / d) * schritt;
        p.y += (p.dy / d) * schritt;
      }
    }
  }

  const aus = new Map<number, Punkt>();
  ids.forEach((id, i) => aus.set(id, { x: pkte[i]!.x, y: pkte[i]!.y }));
  return aus;
}

/** Nachbarn je Knoten, ungerichtet. */
export function nachbarn(kanten: { a: number; b: number }[]): Map<number, Set<number>> {
  const aus = new Map<number, Set<number>>();
  for (const { a, b } of kanten) {
    if (!aus.has(a)) aus.set(a, new Set());
    if (!aus.has(b)) aus.set(b, new Set());
    aus.get(a)!.add(b);
    aus.get(b)!.add(a);
  }
  return aus;
}

/** Rahmen um alle Punkte, mit Rand; für das Einpassen in die Ansicht. */
export function rahmen(punkte: Iterable<Punkt>, rand = 40): { x: number; y: number; b: number; h: number } {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of punkte) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  if (minX === Infinity) return { x: -100, y: -100, b: 200, h: 200 };
  return { x: minX - rand, y: minY - rand, b: maxX - minX + 2 * rand, h: maxY - minY + 2 * rand };
}

/**
 * Notizbücher als eigene Knoten (seit 2026-11-21). Vorher stand ein Notizbuch
 * nur als Farbe des Punkts im Netz, und ohne gesetzte Farbe gar nicht.
 *
 * Ein Notizbuch bekommt die Kennung `-id` (Notizen haben positive), dazu eine
 * Kante `buch` zu jeder seiner gezeigten Notizen. Die Kanten ziehen im Layout
 * mit, so liegen die Notizen eines Buchs beieinander. Der `grad` der Notizen
 * bleibt der aus dem Dienst: er zählt Verbindungen zwischen Notizen, nicht
 * die Zugehörigkeit.
 */
export interface NetzKnotenEingang {
  id: number;
  titel: string;
  notizbuch_id: number | null;
  archiviert: boolean;
  angeheftet: boolean;
  grad: number;
  offene_verweise: number;
}

export interface NetzKnotenMitBuch extends NetzKnotenEingang {
  /** Gesetzt, wenn der Knoten ein Notizbuch ist; dann ist `grad` die Zahl seiner Notizen. */
  buch?: true;
}

export interface NetzKanteMitBuch {
  a: number;
  b: number;
  art: string;
}

export const buchKennung = (buchId: number): number => -buchId;

export function mitNotizbuechern(
  knoten: NetzKnotenEingang[],
  kanten: NetzKanteMitBuch[],
  buecher: { id: number; name: string }[],
): { knoten: NetzKnotenMitBuch[]; kanten: NetzKanteMitBuch[] } {
  const zaehler = new Map<number, number>();
  const neueKanten: NetzKanteMitBuch[] = [];
  for (const n of knoten) {
    if (n.notizbuch_id === null) continue;
    zaehler.set(n.notizbuch_id, (zaehler.get(n.notizbuch_id) ?? 0) + 1);
    neueKanten.push({ a: buchKennung(n.notizbuch_id), b: n.id, art: 'buch' });
  }
  // Nur Bücher mit gezeigten Notizen: ein leeres Buch wäre ein Punkt ohne
  // Bezug, und bei aktivem Filter stünden alle anderen Bücher leer herum.
  const buchKnoten: NetzKnotenMitBuch[] = buecher
    .filter((b) => zaehler.has(b.id))
    .map((b) => ({
      id: buchKennung(b.id),
      titel: b.name,
      notizbuch_id: b.id,
      archiviert: false,
      angeheftet: false,
      grad: zaehler.get(b.id) ?? 0,
      offene_verweise: 0,
      buch: true,
    }));
  return { knoten: [...buchKnoten, ...knoten], kanten: [...kanten, ...neueKanten] };
}
