import { describe, expect, it } from 'vitest';
import { ersterWochentag, langformat, tageImMonat, verschieben, wochentag } from './datum';

describe('Datumsrechnung', () => {
  it('geht einen Tag vor und zurueck', () => {
    expect(verschieben('2026-09-06', 1)).toBe('2026-09-07');
    expect(verschieben('2026-09-06', -1)).toBe('2026-09-05');
  });

  it('rechnet ueber Monats- und Jahresgrenzen', () => {
    expect(verschieben('2026-09-30', 1)).toBe('2026-10-01');
    expect(verschieben('2026-12-31', 1)).toBe('2027-01-01');
    expect(verschieben('2026-01-01', -1)).toBe('2025-12-31');
  });

  it('ueberspringt die Zeitumstellung nicht und verdoppelt sie nicht', () => {
    /** ★ Der Grund, warum diese Datei auf Zeichenketten rechnet. Am 29.03.2026
     * beginnt die Sommerzeit, am 25.10.2026 endet sie. Mit lokaler
     * Date-Arithmetik landet man hier je nach Richtung einen Tag daneben. */
    expect(verschieben('2026-03-28', 1)).toBe('2026-03-29');
    expect(verschieben('2026-03-29', 1)).toBe('2026-03-30');
    expect(verschieben('2026-10-24', 1)).toBe('2026-10-25');
    expect(verschieben('2026-10-25', 1)).toBe('2026-10-26');
  });

  it('kennt den Schalttag', () => {
    expect(verschieben('2028-02-28', 1)).toBe('2028-02-29');
    expect(tageImMonat(2028, 2)).toBe(29);
    expect(tageImMonat(2026, 2)).toBe(28);
  });

  it('benennt den Wochentag', () => {
    expect(wochentag('2026-09-06')).toBe('Sonntag');
    expect(langformat('2026-09-06')).toBe('Sonntag, 6. September 2026');
  });

  it('setzt den Monatsersten auf den richtigen Wochentag', () => {
    // 1. September 2026 ist ein Dienstag, also Spalte 1 bei Montag als 0.
    expect(ersterWochentag(2026, 9)).toBe(1);
  });
});
