import { describe, expect, it } from 'vitest';
import { ausgewaehlteIds, sammelAufrufe, sammelMeldung, verbindenMeldung } from './sammel';

describe('sammelAufrufe', () => {
  it('verschiebt in ein Notizbuch oder löst daraus', () => {
    expect(sammelAufrufe('verschieben', [3], '7')).toEqual([
      { methode: 'PATCH', pfad: '/api/notizen/3', rumpf: { notizbuch_id: 7 } },
    ]);
    expect(sammelAufrufe('verschieben', [3], '')[0]?.rumpf).toEqual({ notizbuch_loesen: true });
  });

  it('löscht einzeln über DELETE, also über den Papierkorb', () => {
    expect(sammelAufrufe('loeschen', [1, 2])).toEqual([
      { methode: 'DELETE', pfad: '/api/notizen/1' },
      { methode: 'DELETE', pfad: '/api/notizen/2' },
    ]);
  });

  it('archiviert und holt zurück', () => {
    expect(sammelAufrufe('archivieren', [1])[0]?.rumpf).toEqual({ archiviert: true });
    expect(sammelAufrufe('zurueckholen', [1])[0]?.rumpf).toEqual({ archiviert: false });
    expect(sammelAufrufe('loesen', [1])[0]?.rumpf).toEqual({ angeheftet: false });
  });
});

describe('ausgewaehlteIds', () => {
  it('nimmt nur positive ganze Zahlen, jede einmal', () => {
    expect(ausgewaehlteIds(['4', '4', 'x', '-1', '0', '2.5', '9'])).toEqual([4, 9]);
  });
});

describe('sammelMeldung', () => {
  it('sagt Einzahl und Mehrzahl richtig', () => {
    expect(sammelMeldung('loeschen', 1, 0)).toBe('1 Notiz in den Papierkorb gelegt.');
    expect(sammelMeldung('archivieren', 3, 1)).toBe(
      '3 Notizen archiviert, 1 Notiz nicht (neu laden und nachsehen).',
    );
  });
});

describe('verbindenMeldung', () => {
  it('nennt neue Verbindungen und sagt, wenn es keine gab', () => {
    expect(verbindenMeldung(3, 3)).toBe('3 Notizen miteinander verbunden, 3 neue Verbindungen.');
    expect(verbindenMeldung(2, 1)).toBe('2 Notizen miteinander verbunden, 1 neue Verbindung.');
    expect(verbindenMeldung(2, 0)).toBe('Die 2 Notizen waren schon miteinander verbunden.');
  });
});
