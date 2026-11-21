import { describe, expect, it } from 'vitest';
import { mitNotizbuechern, nachbarn, netzLayout, rahmen } from './netz-layout';

const abstand = (p: { x: number; y: number }, q: { x: number; y: number }) =>
  Math.hypot(p.x - q.x, p.y - q.y);

describe('netzLayout', () => {
  it('ist deterministisch und ohne NaN', () => {
    const ids = [1, 2, 3, 4, 5, 6];
    const kanten = [{ a: 1, b: 2 }, { a: 2, b: 3 }, { a: 4, b: 5 }];
    const eins = netzLayout(ids, kanten);
    const zwei = netzLayout(ids, kanten);
    expect([...eins.entries()]).toEqual([...zwei.entries()]);
    for (const p of eins.values()) expect(Number.isFinite(p.x) && Number.isFinite(p.y)).toBe(true);
  });

  it('legt Verbundenes näher zusammen als Unverbundenes', () => {
    const ids = Array.from({ length: 12 }, (_, i) => i + 1);
    const kanten = [{ a: 1, b: 2 }, { a: 2, b: 3 }, { a: 3, b: 1 }, { a: 7, b: 8 }];
    const p = netzLayout(ids, kanten);
    const verbunden = abstand(p.get(1)!, p.get(2)!);
    const fremd = abstand(p.get(1)!, p.get(7)!);
    expect(verbunden).toBeLessThan(fremd);
    expect(verbunden).toBeLessThan(140);
  });

  it('übersteht Kanten auf unbekannte Knoten und Schleifen', () => {
    const p = netzLayout([1], [{ a: 1, b: 1 }, { a: 1, b: 99 }]);
    expect(p.size).toBe(1);
    expect(Number.isFinite(p.get(1)!.x)).toBe(true);
  });
});

describe('nachbarn und rahmen', () => {
  it('sammelt ungerichtet', () => {
    const n = nachbarn([{ a: 1, b: 2 }, { a: 3, b: 1 }]);
    expect([...n.get(1)!].sort()).toEqual([2, 3]);
    expect([...n.get(3)!]).toEqual([1]);
  });

  it('gibt einen Rahmen mit Rand, auch ohne Punkte', () => {
    expect(rahmen([{ x: 0, y: 0 }, { x: 10, y: 20 }], 5)).toEqual({ x: -5, y: -5, b: 20, h: 30 });
    expect(rahmen([]).b).toBeGreaterThan(0);
  });
});

describe('mitNotizbuechern', () => {
  const n = (id: number, buch: number | null) => ({
    id, titel: `N${id}`, notizbuch_id: buch, archiviert: false, angeheftet: false, grad: 0, offene_verweise: 0,
  });

  it('legt je Buch mit Notizen einen Knoten und eine Kante je Notiz an', () => {
    const { knoten, kanten } = mitNotizbuechern(
      [n(1, 7), n(2, 7), n(3, null)],
      [{ a: 1, b: 3, art: 'verbunden' }],
      [{ id: 7, name: 'Arbeit' }, { id: 8, name: 'Leer' }],
    );
    const buecher = knoten.filter((k) => k.buch);
    expect(buecher.map((b) => [b.id, b.titel, b.grad])).toEqual([[-7, 'Arbeit', 2]]);
    expect(kanten.filter((k) => k.art === 'buch')).toEqual([
      { a: -7, b: 1, art: 'buch' },
      { a: -7, b: 2, art: 'buch' },
    ]);
    // Die Verbindungen zwischen Notizen bleiben unberührt.
    expect(kanten).toContainEqual({ a: 1, b: 3, art: 'verbunden' });
  });

  it('zieht die Notizen eines Buchs im Layout zusammen', () => {
    const notizen = [n(1, 1), n(2, 1), n(3, 2), n(4, 2)];
    const { knoten, kanten } = mitNotizbuechern(notizen, [], [{ id: 1, name: 'A' }, { id: 2, name: 'B' }]);
    const lage = netzLayout(knoten.map((k) => k.id), kanten);
    const d = (a: number, b: number) => Math.hypot(lage.get(a)!.x - lage.get(b)!.x, lage.get(a)!.y - lage.get(b)!.y);
    expect(d(1, 2)).toBeLessThan(d(1, 3));
    expect(d(3, 4)).toBeLessThan(d(2, 4));
  });
});
