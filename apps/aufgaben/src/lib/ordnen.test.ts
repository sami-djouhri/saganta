import { describe, expect, it } from 'vitest';
import type { Aufgabe } from './aufgaben-bff';
import {
  dauer,
  datumsEtikett,
  demnaechst,
  gehoertZuHeute,
  istFaellig,
  istHeuteGeplant,
  istOffen,
  istUeberfaellig,
  nachDringlichkeit,
  nachProjekt,
  nachTagesablauf,
  pool,
  tagePlus,
  tagesGruppen,
} from './ordnen';

const HEUTE = '2026-09-13';

function a(teil: Partial<Aufgabe> & { id: string }): Aufgabe {
  return {
    title: teil.id,
    priority: 'mittel',
    completed: false,
    ...teil,
  } as Aufgabe;
}

describe('istOffen', () => {
  it('hoert auf beide Quellen', () => {
    expect(istOffen(a({ id: '1' }))).toBe(true);
    expect(istOffen(a({ id: '2', completed: true }))).toBe(false);
    expect(istOffen(a({ id: '3', status: 'done' }))).toBe(false);
    // Abgebrochen ist nicht offen. Ohne diesen Zweig taucht jede stillgelegte
    // Aufgabe wieder in der Tagesliste auf.
    expect(istOffen(a({ id: '4', status: 'cancelled' }))).toBe(false);
  });
});

describe('Faelligkeit', () => {
  it('ohne Datum ist nichts faellig', () => {
    // Der Pool ist kein Mahnstapel.
    expect(istFaellig(a({ id: '1' }), HEUTE)).toBe(false);
    expect(istUeberfaellig(a({ id: '1' }), HEUTE)).toBe(false);
  });

  it('trennt heute von ueberfaellig', () => {
    expect(istFaellig(a({ id: '1', due_date: HEUTE }), HEUTE)).toBe(true);
    expect(istUeberfaellig(a({ id: '1', due_date: HEUTE }), HEUTE)).toBe(false);
    expect(istUeberfaellig(a({ id: '2', due_date: '2026-09-12' }), HEUTE)).toBe(true);
  });
});

describe('istHeuteGeplant', () => {
  it('erkennt Plantag und Zeitfenster', () => {
    expect(istHeuteGeplant(a({ id: '1', planned_date: HEUTE }), HEUTE)).toBe(true);
    expect(
      istHeuteGeplant(a({ id: '2', scheduled_start: `${HEUTE}T09:00:00` }), HEUTE),
    ).toBe(true);
    expect(
      istHeuteGeplant(a({ id: '3', scheduled_start: '2026-09-14T09:00:00' }), HEUTE),
    ).toBe(false);
  });
});

describe('gehoertZuHeute', () => {
  it('nimmt faellig, geplant und Tagesziel, sonst nichts', () => {
    expect(gehoertZuHeute(a({ id: '1', due_date: HEUTE }), HEUTE)).toBe(true);
    expect(gehoertZuHeute(a({ id: '2', planned_date: HEUTE }), HEUTE)).toBe(true);
    expect(gehoertZuHeute(a({ id: '3', goal_id: 'z1' }), HEUTE)).toBe(true);
    expect(gehoertZuHeute(a({ id: '4' }), HEUTE)).toBe(false);
    // Erledigtes gehoert nie zu heute, auch wenn es heute faellig war.
    expect(gehoertZuHeute(a({ id: '5', due_date: HEUTE, completed: true }), HEUTE)).toBe(false);
  });
});

describe('nachTagesablauf', () => {
  it('stellt Zeitgebundenes nach Uhrzeit voran', () => {
    const liste = [
      a({ id: 'ohne', priority: 'dringend' }),
      a({ id: 'spaet', scheduled_start: `${HEUTE}T16:00:00` }),
      a({ id: 'frueh', scheduled_start: `${HEUTE}T08:00:00` }),
    ];
    expect(liste.sort(nachTagesablauf(HEUTE)).map((x) => x.id)).toEqual([
      'frueh',
      'spaet',
      'ohne',
    ]);
  });

  it('liest auch due_time als Uhrzeit', () => {
    const liste = [
      a({ id: 'b', due_date: HEUTE, due_time: '14:00' }),
      a({ id: 'a', due_date: HEUTE, due_time: '09:30' }),
    ];
    expect(liste.sort(nachTagesablauf(HEUTE)).map((x) => x.id)).toEqual(['a', 'b']);
  });

  it('ignoriert ein Zeitfenster eines anderen Tages', () => {
    // Sonst zoege die Aufgabe von uebermorgen die heutige Liste an sich.
    const liste = [
      a({ id: 'morgen', scheduled_start: '2026-09-14T06:00:00' }),
      a({ id: 'heute', scheduled_start: `${HEUTE}T20:00:00` }),
    ];
    expect(liste.sort(nachTagesablauf(HEUTE))[0]!.id).toBe('heute');
  });
});

describe('nachDringlichkeit', () => {
  it('Prioritaet vor Datum vor Titel', () => {
    const liste = [
      a({ id: 'c', priority: 'mittel', title: 'Beta' }),
      a({ id: 'b', priority: 'mittel', title: 'Alpha' }),
      a({ id: 'a', priority: 'dringend' }),
    ];
    expect(liste.sort(nachDringlichkeit).map((x) => x.id)).toEqual(['a', 'b', 'c']);
  });

  it('stellt Undatiertes hinter Datiertes', () => {
    const liste = [a({ id: 'ohne' }), a({ id: 'mit', due_date: '2027-01-01' })];
    expect(liste.sort(nachDringlichkeit).map((x) => x.id)).toEqual(['mit', 'ohne']);
  });
});

describe('tagesGruppen', () => {
  const alle = [
    a({ id: 'alt', due_date: '2026-09-01' }),
    a({ id: 'heute', due_date: HEUTE }),
    a({ id: 'geplant', planned_date: HEUTE }),
    a({ id: 'ziel', goal_id: 'z1' }),
    a({ id: 'pool' }),
    a({ id: 'fertig', due_date: HEUTE, completed: true }),
  ];

  it('ordnet in die vier Gruppen', () => {
    const g = tagesGruppen(alle, HEUTE);
    expect(g.map((x) => x.schluessel)).toEqual(['ueberfaellig', 'heute', 'geplant', 'ziel']);
    expect(g[0]!.aufgaben.map((x) => x.id)).toEqual(['alt']);
    expect(g[1]!.aufgaben.map((x) => x.id)).toEqual(['heute']);
  });

  it('nennt keine Aufgabe zweimal', () => {
    // Eine Aufgabe, die heute faellig UND heute geplant ist UND an einem Ziel
    // haengt, stand in der ersten Fassung dreimal da.
    const doppelt = [a({ id: 'x', due_date: HEUTE, planned_date: HEUTE, goal_id: 'z1' })];
    const ids = tagesGruppen(doppelt, HEUTE).flatMap((g) => g.aufgaben.map((x) => x.id));
    expect(ids).toEqual(['x']);
  });

  it('laesst leere Gruppen weg', () => {
    expect(tagesGruppen([a({ id: 'pool' })], HEUTE)).toEqual([]);
  });

  it('zeigt Erledigtes nicht', () => {
    const ids = tagesGruppen(alle, HEUTE).flatMap((g) => g.aufgaben.map((x) => x.id));
    expect(ids).not.toContain('fertig');
  });
});

describe('pool', () => {
  it('ist das Undatierte und Ungeplante', () => {
    const alle = [
      a({ id: 'pool' }),
      a({ id: 'datiert', due_date: '2026-10-01' }),
      a({ id: 'geplant', planned_date: HEUTE }),
      a({ id: 'fertig', completed: true }),
    ];
    expect(pool(alle, HEUTE).map((x) => x.id)).toEqual(['pool']);
  });
});

describe('demnaechst', () => {
  it('nimmt das Fenster nach heute bis zur Grenze', () => {
    const alle = [
      a({ id: 'heute', due_date: HEUTE }),
      a({ id: 'morgen', due_date: '2026-09-14' }),
      a({ id: 'in7', due_date: '2026-09-20' }),
      a({ id: 'in8', due_date: '2026-09-21' }),
    ];
    expect(demnaechst(alle, HEUTE).map((x) => x.id)).toEqual(['morgen', 'in7']);
  });
});

describe('tagePlus', () => {
  it('rechnet ueber Monats- und Jahresgrenzen', () => {
    expect(tagePlus('2026-09-30', 1)).toBe('2026-10-01');
    expect(tagePlus('2026-12-31', 1)).toBe('2027-01-01');
    expect(tagePlus('2026-01-01', -1)).toBe('2025-12-31');
  });

  it('ueberspringt die Zeitumstellung nicht', () => {
    // ★ Der Grund fuer die Zeichenketten-Rechnung. Mit lokaler Zeitzone landet
    // ein naiver Tagessprung ueber die Umstellung auf demselben oder dem
    // uebernaechsten Tag. 2026: Sommerzeit ab 29.03., Winterzeit ab 25.10.
    expect(tagePlus('2026-03-28', 1)).toBe('2026-03-29');
    expect(tagePlus('2026-03-29', 1)).toBe('2026-03-30');
    expect(tagePlus('2026-10-24', 1)).toBe('2026-10-25');
    expect(tagePlus('2026-10-25', 1)).toBe('2026-10-26');
  });

  it('kennt den Schaltjahrestag', () => {
    expect(tagePlus('2028-02-28', 1)).toBe('2028-02-29');
    expect(tagePlus('2026-02-28', 1)).toBe('2026-03-01');
  });
});

describe('nachProjekt', () => {
  it('gruppiert und stellt Projektloses ans Ende', () => {
    const alle = [
      a({ id: 'ohne' }),
      a({ id: 'p1', project_id: 'b' }),
      a({ id: 'p2', project_id: 'a' }),
    ];
    const g = nachProjekt(alle, [
      { id: 'a', name: 'Anbau' },
      { id: 'b', name: 'Balkon' },
    ]);
    expect(g.map((x) => x.titel)).toEqual(['Anbau', 'Balkon', 'Ohne Projekt']);
  });

  it('benennt ein unbekanntes Projekt, statt es zu verschlucken', () => {
    const g = nachProjekt([a({ id: 'x', project_id: 'weg' })], []);
    expect(g[0]!.titel).toBe('Unbekanntes Projekt');
  });
});

describe('dauer', () => {
  it('schreibt Minuten und Stunden mit Komma', () => {
    expect(dauer(45)).toBe('45 min');
    expect(dauer(90)).toBe('1,5 h');
    expect(dauer(120)).toBe('2 h');
    expect(dauer(null)).toBe('');
    expect(dauer(0)).toBe('');
  });
});

describe('datumsEtikett', () => {
  it('benennt die drei nahen Tage', () => {
    expect(datumsEtikett(HEUTE, HEUTE)).toBe('Heute');
    expect(datumsEtikett('2026-09-14', HEUTE)).toBe('Morgen');
    expect(datumsEtikett('2026-09-12', HEUTE)).toBe('Gestern');
  });

  it('schreibt sonst Wochentag und Datum', () => {
    // 2026-09-20 ist ein Sonntag.
    expect(datumsEtikett('2026-09-20', HEUTE)).toBe('So, 20.09.');
  });
});
