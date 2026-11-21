import { describe, expect, it } from 'vitest';
import type { KalenderEvent } from './kalender-bff';
import { artText, erinnerungText, kartenDatum, schnellgriffe, terminRechte, WEGE_KALENDER, wiederholungText } from './terminkarte';

const termin = (x: Partial<KalenderEvent> = {}): KalenderEvent => ({
  id: 't1',
  title: 'Zahnarzt',
  start: '2026-11-21T14:00:00',
  end: '2026-11-21T15:30:00',
  calendar_id: 'system-termine-0000-0000-000000000000',
  ...x,
});

describe('terminkarte', () => {
  it('normaler Termin bietet alle Schnellgriffe', () => {
    expect(schnellgriffe(termin()).map((g) => g.schluessel)).toEqual(['plus15', 'morgen', 'woche', 'kopie']);
  });
  it('Erzeugtes ist nur zum Ansehen', () => {
    for (const cid of [WEGE_KALENDER, 'daytype-arbeit-0000', 'system-geburtstage-0000']) {
      expect(terminRechte(termin({ calendar_id: cid }))).toEqual({ bearbeiten: false, verschieben: false, duplizieren: false });
    }
  });
  it('Serie selbst nur duplizieren, ihr Vorkommen auch verschieben', () => {
    expect(schnellgriffe(termin({ recurrence_rule: 'FREQ=WEEKLY' })).map((g) => g.schluessel)).toEqual(['kopie']);
    expect(schnellgriffe(termin({ id: 't1::2026-11-21', recurrence_rule: 'FREQ=WEEKLY' })).length).toBe(4);
  });
  it('ganztaegig ohne +15 min', () => {
    expect(schnellgriffe(termin({ all_day: true })).map((g) => g.schluessel)).not.toContain('plus15');
  });
  it('Datumszeile', () => {
    expect(kartenDatum(termin(), '2026-11-21')).toBe('Sa., 21. November (heute)');
    expect(kartenDatum(termin({ start: '2026-11-22T09:00:00' }), '2026-11-21')).toBe('So., 22. November (morgen)');
    expect(kartenDatum(termin({ start: '2027-01-01T09:00:00' }), '2026-11-21')).toBe('Fr., 1. Januar 2027');
  });
  it('Erinnerung und Art im Klartext', () => {
    expect(erinnerungText(null)).toBeNull();
    expect(erinnerungText(15)).toBe('15 min vorher');
    expect(erinnerungText(120)).toBe('2 h vorher');
    expect(erinnerungText(1440)).toBe('1 Tag vorher');
    expect(artText('lernen')).toBe('Lernen');
    expect(artText(null)).toBeNull();
  });
  it('Wiederholung im Klartext', () => {
    expect(wiederholungText(null)).toBeNull();
    expect(wiederholungText('FREQ=WEEKLY;BYDAY=MO,TH')).toBe('Wöchentlich am Mo, Do');
    expect(wiederholungText('FREQ=WEEKLY;INTERVAL=2;UNTIL=20261113T145959Z')).toBe('Alle 2 Wochen bis 13.11.2026');
    expect(wiederholungText('FREQ=DAILY')).toBe('Täglich');
  });
});
