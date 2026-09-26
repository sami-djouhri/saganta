import { describe, expect, it } from 'vitest';
import {
  SAGANTA_APPS,
  appUrl,
  appUrlById,
  appsFuer,
  buildAppCommands,
  istHeimRaum,
  raumVon,
} from './apps';

/**
 * Diese Tests halten genau den Fehler fest, der die Suite am 2026-09-13
 * auseinanderlaufen liess: fertige `.de`-URLs im Katalog. Jeder von ihnen faellt
 * gegen die alte Fassung.
 */

describe('raumVon', () => {
  it('nimmt die letzten beiden Labels', () => {
    expect(raumVon('notizen.home.arpa')).toBe('home.arpa');
    expect(raumVon('kalender.saganta.de')).toBe('saganta.de');
    expect(raumVon('saganta.de')).toBe('saganta.de');
  });

  it('ignoriert Port und Grossschreibung', () => {
    expect(raumVon('Notizen.home.arpa:8443')).toBe('home.arpa');
  });

  it('gibt fuer alles ohne Raum null (Aufrufer faellt dann auf oeffentlich)', () => {
    expect(raumVon('localhost')).toBeNull();
    expect(raumVon('localhost:3000')).toBeNull();
    expect(raumVon('')).toBeNull();
    expect(raumVon(undefined)).toBeNull();
    // Aus einer nackten IP laesst sich kein Geschwister-Name bilden. Ohne diese
    // Pruefung entstuende aus 192.0.2.10 der Raum "0.11" und daraus Adressen
    // wie https://notizen.0.11, also ein Link, der nirgends aufloest.
    expect(raumVon('192.0.2.10')).toBeNull();
    expect(raumVon('192.0.2.10:8080')).toBeNull();
  });
});

describe('istHeimRaum', () => {
  it('trennt Heim von oeffentlich', () => {
    expect(istHeimRaum('home.arpa')).toBe(true);
    expect(istHeimRaum('saganta.de')).toBe(false);
    expect(istHeimRaum(null)).toBe(false);
  });
});

describe('appUrl', () => {
  const app = (id: string) => SAGANTA_APPS.find((a) => a.id === id)!;

  it('bleibt im Raum des Aufrufers', () => {
    expect(appUrl(app('notizen'), 'shell.home.arpa')).toBe('https://notizen.home.arpa');
    expect(appUrl(app('notizen'), 'saganta.de')).toBe('https://notizen.saganta.de');
  });

  it('kennt den Kalender-Sonderfall calendar gegen kalender', () => {
    // ⚠️ Die Falle: im Heimnetz heisst er `calendar`, oeffentlich
    // `kalender`. Ein Vertipper trifft den default_server des dev-portal.
    expect(appUrl(app('calendar'), 'shell.home.arpa')).toBe('https://calendar.home.arpa');
    expect(appUrl(app('calendar'), 'saganta.de')).toBe('https://kalender.saganta.de');
  });

  it('legt die Shell im Heim auf shell, oeffentlich auf die Wurzel', () => {
    expect(appUrl(app('shell'), 'notizen.home.arpa')).toBe('https://shell.home.arpa');
    expect(appUrl(app('shell'), 'news.saganta.de')).toBe('https://saganta.de');
  });

  it('faellt ohne Host auf den oeffentlichen Raum zurueck', () => {
    expect(appUrl(app('post'))).toBe('https://post.saganta.de');
    expect(appUrl(app('post'), null)).toBe('https://post.saganta.de');
  });
});

describe('appUrlById', () => {
  it('loest ueber die id auf', () => {
    expect(appUrlById('aufgaben', 'kalender.home.arpa')).toBe('https://aufgaben.home.arpa');
  });

  it('gibt bei unbekannter id die Shell des Raums', () => {
    expect(appUrlById('gibtesnicht', 'notizen.home.arpa')).toBe('https://shell.home.arpa');
    expect(appUrlById('gibtesnicht', 'news.saganta.de')).toBe('https://saganta.de');
  });
});

describe('appsFuer', () => {
  it('zeigt das Tagebuch nur im Heim', () => {
    // Es liegt bewusst nicht im Tunnel. Ein Eintrag im oeffentlichen Raum waere
    // eine Tuer, hinter der nichts ist.
    expect(appsFuer('shell.home.arpa').map((a) => a.id)).toContain('tagebuch');
    expect(appsFuer('saganta.de').map((a) => a.id)).not.toContain('tagebuch');
  });

  it('enthaelt die Apps, die im alten Katalog fehlten', () => {
    const ids = appsFuer('shell.home.arpa').map((a) => a.id);
    for (const id of ['aufgaben', 'notizen', 'assets', 'fitness', 'lager', 'mealprep']) {
      expect(ids).toContain(id);
    }
  });

  it('nennt keine App zweimal', () => {
    const ids = SAGANTA_APPS.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('buildAppCommands', () => {
  it('laesst die eigene App aus', () => {
    const ids = buildAppCommands('notizen', 'notizen.home.arpa').map((c) => c.id);
    expect(ids).not.toContain('app-notizen');
    expect(ids).toContain('app-aufgaben');
  });

  it('haengt den Downloads-Eintrag an', () => {
    const ids = buildAppCommands('post', 'post.home.arpa').map((c) => c.id);
    expect(ids).toContain('nav-downloads');
  });
});
