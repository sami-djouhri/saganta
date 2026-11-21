import { describe, expect, it } from 'vitest';
import type { Aufgabe, Projekt } from './aufgaben-bff';
import { filterSlugs, passtZuProjekten, projektAbschnitte, projekteDerAufgabe } from './projektfilter';

function a(teil: Partial<Aufgabe> & { id: string }): Aufgabe {
  return { title: teil.id, priority: 'mittel', completed: false, ...teil };
}

// Erfunden: Gartiko-Bot unter Discord-Bots UND Gartiko.
const projekte: Projekt[] = [
  { id: 'discord-bots', slug: 'discord-bots', name: 'Discord-Bots', deck_id: 1, kinder_ids: [3] },
  { id: 'gartiko', slug: 'gartiko', name: 'Gartiko', deck_id: 2, kinder_ids: [3] },
  { id: 'gartiko-bot', slug: 'gartiko-bot', name: 'Gartiko-Bot', deck_id: 3, eltern_ids: [1, 2] },
  { id: 'karten', slug: 'karten', name: 'Karten', deck_id: 4 },
];
const teilbaum = { 'discord-bots': ['discord-bots', 'gartiko-bot'], gartiko: ['gartiko', 'gartiko-bot'] };

describe('Projektfilter', () => {
  it('nimmt Zuhause und weitere Projekte, jedes einmal', () => {
    expect(projekteDerAufgabe({ project_id: 'a', weitere_projekte: ['b', 'a'] })).toEqual(['a', 'b']);
    expect(projekteDerAufgabe({ project_id: null, weitere_projekte: null })).toEqual([]);
  });

  it('schliesst Unterprojekte ein, ausser mit „nur dieses"', () => {
    expect([...filterSlugs('gartiko', false, teilbaum)]).toEqual(['gartiko', 'gartiko-bot']);
    expect([...filterSlugs('gartiko', true, teilbaum)]).toEqual(['gartiko']);
    expect([...filterSlugs('karten', false, teilbaum)]).toEqual(['karten']);
  });

  it('trifft eine Aufgabe auch ueber ein angeheftetes Projekt', () => {
    const slugs = filterSlugs('gartiko', false, teilbaum);
    expect(passtZuProjekten({ project_id: 'gartiko-bot' }, slugs)).toBe(true);
    expect(passtZuProjekten({ project_id: 'karten', weitere_projekte: ['gartiko'] }, slugs)).toBe(true);
    expect(passtZuProjekten({ project_id: 'karten' }, slugs)).toBe(false);
  });
});

describe('projektAbschnitte', () => {
  it('zeigt den Baum, Aufgaben nur beim ersten Auftreten und Oberprojekte als Ueberschrift', () => {
    const aufgaben = [
      a({ id: 'bot-1', project_id: 'gartiko-bot' }),
      a({ id: 'karten-1', project_id: 'karten', weitere_projekte: ['gartiko'] }),
      a({ id: 'fertig', project_id: 'karten', completed: true }),
    ];
    const ab = projektAbschnitte(aufgaben, projekte);
    expect(ab.map((x) => `${x.zeile.tiefe}:${x.zeile.slug}:${x.imTeilbaum}${x.verweis ? ':verweis' : ''}`)).toEqual([
      '0:discord-bots:1',
      '1:gartiko-bot:1',
      '0:gartiko:2',
      '1:gartiko-bot:1:verweis',
      '0:karten:1',
    ]);
    const gartiko = ab.find((x) => x.zeile.slug === 'gartiko')!;
    expect(gartiko.eigene).toEqual([]);
    expect(gartiko.angeheftet.map((x) => x.id)).toEqual(['karten-1']);
    expect(ab[1]!.eigene.map((x) => x.id)).toEqual(['bot-1']);
    expect(ab[3]!.eigene).toEqual([]);
  });

  it('laesst Zweige ohne offene Aufgabe weg', () => {
    expect(projektAbschnitte([], projekte)).toEqual([]);
  });
});
