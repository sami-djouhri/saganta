import { describe, expect, it } from 'vitest';
import { kontextAusEreignissen } from './kontext';

describe('Tageskontext', () => {
  it('trennt den Tagestyp von den Terminen', () => {
    const kontext = kontextAusEreignissen([
      { calendar_id: 'daytype-arbeit-0000-0000', title: 'Arbeit', start: '2026-09-07T07:00:00' },
      { calendar_id: 'system-termine-0000', title: 'Zahnarzt', start: '2026-09-07T15:00:00', end: '2026-09-07T15:30:00' },
    ]);
    expect(kontext.tagestyp).toBe('Arbeit');
    expect(kontext.termine).toEqual([
      { titel: 'Zahnarzt', von: '15:00', bis: '15:30', ganztags: false },
    ]);
  });

  it('erkennt den Tagestyp an der Kennung, nicht am Titel', () => {
    /** ★ Ein Termin, der "Urlaub" heisst, ist kein Tagestyp. Sonst kippte ein
     * beliebiger Kalendereintrag die Anzeige des Tages. */
    const kontext = kontextAusEreignissen([
      { calendar_id: 'system-termine-0000', title: 'Urlaub planen', start: '2026-09-07T10:00:00' },
    ]);
    expect(kontext.tagestyp).toBeNull();
    expect(kontext.termine).toHaveLength(1);
  });

  it('faellt auf die Kennung zurueck, wenn der Titel fehlt', () => {
    const kontext = kontextAusEreignissen([{ calendar_id: 'daytype-urlaub-0000-0000', title: '' }]);
    expect(kontext.tagestyp).toBe('urlaub');
  });

  it('nimmt den ersten Tagestyp und rechnet keine Prioritaet nach', () => {
    // Die Aufloesung nach Prioritaet gehoert dem Kalender allein. Eine zweite
    // Daytype-Logik ist laut Root-Policy verboten.
    const kontext = kontextAusEreignissen([
      { calendar_id: 'daytype-feiertag-0000', title: 'Feiertag' },
      { calendar_id: 'daytype-arbeit-0000', title: 'Arbeit' },
    ]);
    expect(kontext.tagestyp).toBe('Feiertag');
  });

  it('behandelt Geburtstage als ganztaegig', () => {
    const kontext = kontextAusEreignissen([
      { calendar_id: 'system-geburtstage-0000', title: 'Oma hat Geburtstag' },
    ]);
    expect(kontext.termine[0]?.ganztags).toBe(true);
  });

  it('kommt mit einer leeren oder unbrauchbaren Antwort zurecht', () => {
    // Fail-soft: der Kontext ist eine Gedaechtnisstuetze. Faellt er aus, soll
    // man trotzdem schreiben koennen.
    expect(kontextAusEreignissen(null)).toEqual({ tagestyp: null, termine: [] });
    expect(kontextAusEreignissen('kaputt')).toEqual({ tagestyp: null, termine: [] });
    expect(kontextAusEreignissen([])).toEqual({ tagestyp: null, termine: [] });
  });

  it('nimmt einen Termin ohne Uhrzeit als ganztaegig', () => {
    const kontext = kontextAusEreignissen([{ calendar_id: 'system-termine', title: 'Umzug' }]);
    expect(kontext.termine[0]).toEqual({
      titel: 'Umzug',
      von: null,
      bis: null,
      ganztags: true,
    });
  });
});
