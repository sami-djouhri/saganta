import { beforeEach, describe, expect, it, vi } from 'vitest';

// `$env/dynamic/public` gibt es ausserhalb eines laufenden SvelteKit-Servers
// nicht. Der Mock haelt eine veraenderliche Umgebung, weil `freigabeBasis` den
// Wert bei jedem Aufruf liest und nicht beim Laden des Moduls.
const { umgebung } = vi.hoisted(() => ({ umgebung: {} as Record<string, string> }));
vi.mock('$env/dynamic/public', () => ({ env: umgebung }));

const { freigabeBasis } = await import('./meta');

describe('freigabeBasis', () => {
  beforeEach(() => {
    for (const k of Object.keys(umgebung)) delete umgebung[k];
  });

  it('bleibt ohne Konfiguration auf dem eigenen Ursprung', () => {
    expect(freigabeBasis('https://notizen.example.org')).toBe(
      'https://notizen.example.org/n',
    );
  });

  // ★★ Der eigentliche Fehler, gegen den dieser Test steht: bis zum 2026-09-12
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
});
