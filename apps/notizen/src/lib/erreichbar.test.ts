import { describe, expect, it, vi } from 'vitest';

import { basisErreichbar } from './erreichbar';

const EIGEN = 'https://notizen.example.org';

describe('basisErreichbar', () => {
  it('fragt den eigenen Ursprung nicht, sondern vertraut ihm', async () => {
    // Waere er nicht erreichbar, haette der Nutzer die Seite nicht vor sich.
    // Der Test prueft nicht nur das Ergebnis, sondern dass gar nicht gefragt
    // wird: ohne eigene Kurz-Domaene ist das der Normalfall, und eine Probe
    // darin waere bei jedem Teilen eine Verzoegerung ohne Erkenntnis.
    const holen = vi.fn();
    await expect(basisErreichbar(`${EIGEN}/n`, EIGEN, holen as never)).resolves.toBe(true);
    expect(holen).not.toHaveBeenCalled();
  });

  it('nimmt jede Antwort als Beweis, auch eine mit Fehlerstatus', async () => {
    // Bei `no-cors` ist der Status unlesbar, und mehr braucht es nicht: ein 404
    // beweist, dass der Name traegt. Unterschieden wird Antwort von Nichts.
    const holen = vi.fn().mockResolvedValue(new Response(null, { status: 404 }));
    await expect(
      basisErreichbar('https://n.example.org', EIGEN, holen as never),
    ).resolves.toBe(true);
    expect(holen).toHaveBeenCalledOnce();
  });

  it('meldet einen Namen, der nicht aufloest, als nicht erreichbar', async () => {
    const holen = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(
      basisErreichbar('https://n.saganta.de', EIGEN, holen as never),
    ).resolves.toBe(false);
  });

  it('meldet eine abgelaufene Frist als nicht erreichbar', async () => {
    const holen = vi.fn().mockRejectedValue(new DOMException('timeout', 'TimeoutError'));
    await expect(
      basisErreichbar('https://n.example.org', EIGEN, holen as never),
    ).resolves.toBe(false);
  });

  it('meldet eine unlesbare Basis als nicht erreichbar, ohne zu fragen', async () => {
    const holen = vi.fn();
    await expect(basisErreichbar('n.example.org', EIGEN, holen as never)).resolves.toBe(false);
    expect(holen).not.toHaveBeenCalled();
  });
});
