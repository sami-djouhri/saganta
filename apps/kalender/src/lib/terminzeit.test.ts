import { describe, expect, it } from 'vitest';
import type { KalenderEvent } from './kalender-bff';
import { dauerMinuten, endeNachDauer, endeWandertMit, rueckwegLoeschen, rueckwegZeit, verschoben } from './terminzeit';

const termin = (x: Partial<KalenderEvent> = {}): KalenderEvent => ({
  id: 't1',
  title: 'Zahnarzt',
  start: '2026-11-21T14:00:00',
  end: '2026-11-21T15:30:00',
  calendar_id: 'system-termine-0000-0000-000000000000',
  ...x,
});

describe('terminzeit', () => {
  it('Ende wandert mit und haelt die Dauer, auch ueber Mitternacht', () => {
    expect(endeWandertMit('2026-11-21T14:00', '2026-11-21T16:15', '2026-11-21T15:30')).toBe('2026-11-21T17:45');
    expect(endeWandertMit('2026-11-21T14:00', '2026-11-21T23:30', '2026-11-21T15:00')).toBe('2026-11-22T00:30');
    expect(endeWandertMit('2026-11-21T14:00', '2026-11-24T09:00', '2026-11-21T14:45')).toBe('2026-11-24T09:45');
  });
  it('Ende vor Start: eine Stunde ab dem neuen Start', () => {
    expect(endeWandertMit('2026-11-21T14:00', '2026-11-21T10:00', '2026-11-21T13:00')).toBe('2026-11-21T11:00');
  });
  it('unlesbarer Start laesst das Ende stehen', () => {
    expect(endeWandertMit('2026-11-21T14:00', '', '2026-11-21T15:00')).toBe('2026-11-21T15:00');
  });
  it('Dauer-Knopf setzt das Ende ab Start', () => {
    expect(endeNachDauer('2026-11-21T14:00', 90)).toBe('2026-11-21T15:30');
    expect(endeNachDauer('x', 30)).toBeNull();
  });
  it('verschoben und Dauer', () => {
    expect(verschoben('2026-11-21T14:00:00', 1, -15)).toBe('2026-11-22T13:45:00');
    expect(dauerMinuten('2026-11-21T14:00', '2026-11-21T15:30:00')).toBe(90);
  });
  it('Rueckweg Zeit: alte Zeiten, bei Reihen keiner', () => {
    expect(rueckwegZeit(termin(), 'verschoben')).toEqual({
      text: 'verschoben', action: 'eventVerschieben',
      felder: { id: 't1', start: '2026-11-21T14:00:00', end: '2026-11-21T15:30:00' },
    });
    expect(rueckwegZeit(termin({ id: 't1::2026-11-21' }), 'x')).toBeNull();
    expect(rueckwegZeit(termin({ recurrence_rule: 'FREQ=WEEKLY' }), 'x')).toBeNull();
  });
  it('Rueckweg Loeschen: legt mit allen Feldern neu an', () => {
    const r = rueckwegLoeschen(termin({ location: 'Praxis', reminder_minutes: 60, projekt: 'gesund' }))!;
    expect(r.action).toBe('eventWiederherstellen');
    const t = JSON.parse(r.felder.termin!);
    expect(t).toMatchObject({ title: 'Zahnarzt', location: 'Praxis', reminder_minutes: 60, projekt: 'gesund', all_day: false });
    expect(t.start).toBe('2026-11-21T14:00:00');
    expect(rueckwegLoeschen(termin({ is_recurring_instance: true }))).toBeNull();
  });
});
