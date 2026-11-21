import { describe, expect, it } from 'vitest';
import { baum, eingerueckt, verboteneEltern, wurzeln } from './gliederung';
import type { Project } from './types';

const p = (id: number, name: string, eltern: number[], kinder: number[], offen = 0): Project =>
  ({ id, name, slug: name.toLowerCase(), eltern_ids: eltern, kinder_ids: kinder, open_tasks: offen }) as unknown as Project;

// Gartiko-Bot (3) haengt unter Discord-Bots (1) UND Gartiko (2).
const liste = [p(1, 'Discord-Bots', [], [3, 4], 1), p(2, 'Gartiko', [], [3], 2), p(3, 'Gartiko-Bot', [1, 2], [], 5), p(4, 'Herb', [1], [], 1)];
const nachName = (a: Project, b: Project) => a.name.localeCompare(b.name, 'de');

describe('gliederung', () => {
  it('findet die Wurzeln', () => {
    expect(wurzeln(liste).map((x) => x.id)).toEqual([1, 2]);
  });
  it('zeigt ein Projekt mit zwei Eltern unter beiden und zaehlt je Teilbaum einmal', () => {
    const b = baum(liste, nachName);
    expect(b.map((k) => k.projekt.name)).toEqual(['Discord-Bots', 'Gartiko']);
    expect(b[0]!.kinder.map((k) => k.projekt.name)).toEqual(['Gartiko-Bot', 'Herb']);
    expect(b[1]!.kinder.map((k) => k.projekt.name)).toEqual(['Gartiko-Bot']);
    expect(b[0]!.summe.offen).toBe(7);
    expect(b[1]!.summe.offen).toBe(7);
  });
  it('rueckt fuer Auswahlen ein', () => {
    expect(eingerueckt(liste).map((x) => `${x.tiefe}${x.projekt.name}`)).toEqual([
      '0Discord-Bots', '1Gartiko-Bot', '1Herb', '0Gartiko', '1Gartiko-Bot',
    ]);
  });
  it('verbietet sich selbst und Nachfahren als Oberprojekt', () => {
    expect([...verboteneEltern(liste, 1)].sort()).toEqual([1, 3, 4]);
  });
  it('haelt einen Kreis aus', () => {
    const kreis = [p(1, 'A', [2], [2]), p(2, 'B', [1], [1])];
    expect(() => baum(kreis, nachName)).not.toThrow();
  });
});
