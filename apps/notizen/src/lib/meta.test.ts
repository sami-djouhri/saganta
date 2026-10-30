import { beforeEach, describe, expect, it, vi } from 'vitest';

// `$env/dynamic/public` gibt es ausserhalb eines laufenden SvelteKit-Servers
// nicht. Der Mock haelt eine veraenderliche Umgebung, weil `freigabeBasis` den
// Wert bei jedem Aufruf liest und nicht beim Laden des Moduls.
const { umgebung } = vi.hoisted(() => ({ umgebung: {} as Record<string, string> }));
vi.mock('$env/dynamic/public', () => ({ env: umgebung }));

const { freigabeBasis, kurzBasisPruefen } = await import('./meta');

describe('freigabeBasis', () => {
  beforeEach(() => {
    for (const k of Object.keys(umgebung)) delete umgebung[k];
  });

  it('bleibt ohne Konfiguration auf dem eigenen Ursprung', () => {
    expect(freigabeBasis('https://notizen.example.org')).toBe(
      'https://notizen.example.org/n',
    );
  });

  // Der eigentliche Fehler, gegen den dieser Test steht: bis zum 2026-09-12
  // gab die Funktion fuer jeden Ursprung, der auf `.saganta.de` endete,
  // `https://n.saganta.de` zurueck. Das ist die Instanz des Projekts und nicht
  // die des Betreibers: eine Installation, deren Domaene so endet, haette
  // Freigabe-Links auf einen fremden Server ausgegeben.
  it('erfindet auch bei der Domaene des Projekts keinen fremden Namen', () => {
    expect(freigabeBasis('https://notizen.saganta.de')).toBe(
      'https://notizen.saganta.de/n',
    );
  });

  it('nimmt die konfigurierte Kurz-Adresse, ohne abschliessenden Schraegstrich', () => {
    umgebung.PUBLIC_NOTIZEN_KURZ_BASIS = 'https://n.example.org/';
    expect(freigabeBasis('https://notizen.example.org')).toBe('https://n.example.org');
  });

  it('behandelt einen leeren Eintrag wie keinen', () => {
    umgebung.PUBLIC_NOTIZEN_KURZ_BASIS = '   ';
    expect(freigabeBasis('https://notizen.example.org/')).toBe(
      'https://notizen.example.org/n',
    );
  });

  // Bis zum 2026-10-24 genuegte hier ein nichtleerer Wert. Geprueft wurde
  // also das Vorhandensein und nicht die Brauchbarkeit, und die vier Tests
  // darueber pruefen genau diese Vorhandenseinspruefung: alle gruen, waehrend
  // jeder ausgegebene Freigabe-Link ins Leere zeigte.
  it('faellt bei einem Wert ohne Schema auf den eigenen Ursprung zurueck', () => {
    umgebung.PUBLIC_NOTIZEN_KURZ_BASIS = 'n.example.org';
    expect(freigabeBasis('https://notizen.example.org')).toBe(
      'https://notizen.example.org/n',
    );
  });

  it('verwirft eine Basis mit Fragmentteil', () => {
    // Besonders heikel: an die Basis haengt die App bei verschluesselten
    // Freigaben den Schluessel als Fragment. Zwei Fragmente in einer Adresse
    // ergeben einen Link, der den Schluessel verliert.
    umgebung.PUBLIC_NOTIZEN_KURZ_BASIS = 'https://n.example.org/#x';
    expect(freigabeBasis('https://notizen.example.org')).toBe(
      'https://notizen.example.org/n',
    );
  });

  it('verwirft ein Protokoll, das keine Webadresse ist', () => {
    umgebung.PUBLIC_NOTIZEN_KURZ_BASIS = 'javascript:alert(1)';
    expect(freigabeBasis('https://notizen.example.org')).toBe(
      'https://notizen.example.org/n',
    );
  });
});

describe('kurzBasisPruefen', () => {
  it('meldet nichts Konfiguriertes als null, nicht als Fehler', () => {
    expect(kurzBasisPruefen(undefined)).toBeNull();
    expect(kurzBasisPruefen('')).toBeNull();
    expect(kurzBasisPruefen('  ')).toBeNull();
  });

  it('nennt bei einem unbrauchbaren Wert den Grund und den Rohwert', () => {
    const befund = kurzBasisPruefen('n.example.org');
    expect(befund).toMatchObject({ brauchbar: false, roh: 'n.example.org' });
    expect(befund && !befund.brauchbar && befund.grund).toMatch(/Schema/);
  });

  // Die Formpruefung kann NICHT beantworten, ob ein Name aufloest, und darf
  // es nicht vorgeben: `https://n.saganta.de` ist wohlgeformt und war genau der
  // tote Name. Dafuer gibt es die Probe im Browser (`erreichbar.ts`) und die
  // fuenfte Quelle der Tunnel-Sonde. Dieser Test haelt die Grenze fest, damit
  // niemand die Formpruefung spaeter fuer eine Erreichbarkeitspruefung haelt.
  it('laesst einen wohlgeformten Namen durch, auch wenn er nirgends aufloest', () => {
    expect(kurzBasisPruefen('https://n.saganta.de')).toEqual({
      brauchbar: true,
      basis: 'https://n.saganta.de',
    });
  });
});
