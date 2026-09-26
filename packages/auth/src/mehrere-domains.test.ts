/**
 * Die Anmeldung unter mehr als einem Namen.
 *
 * Hintergrund: die Suite ist unter `saganta.de` (Demo, oeffentlich) und unter
 * `home.arpa` (produktiv, Heimnetz) erreichbar. Der Auth-Service setzt sein
 * Cookie fest auf `Domain=saganta.de`. Ein Browser verwirft ein Set-Cookie,
 * dessen Domain nicht zum antwortenden Host passt, und zwar **stillschweigend**:
 * die Anmeldung sieht erfolgreich aus, das naechste Laden ist wieder
 * abgemeldet, und nirgends steht ein Fehler. Bis 2026-09-06 war der
 * `.home`-Raum deshalb fuer angemeldete Apps unbenutzbar.
 *
 * Diese Tests halten beide Richtungen fest: der `.de`-Weg bleibt exakt wie
 * vorher, und der `.home`-Weg funktioniert jetzt.
 */

import { describe, expect, it } from 'vitest';
import {
  anmeldeadresseFuer,
  leseLoginUrls,
  parentCookieDomain,
  passendeCookieDomain,
  sicheresZiel,
  type BetterAuthConfig,
} from './better-auth.js';

describe('Cookie-Domain', () => {
  it('bleibt unveraendert, wenn kein Host bekannt ist', () => {
    // Rueckwaertskompatibilitaet: alte Aufrufer ohne dritten Parameter.
    expect(passendeCookieDomain('saganta.de', undefined)).toBe('saganta.de');
  });

  it('bleibt unveraendert im passenden Domain-Raum', () => {
    for (const host of ['saganta.de', 'shell.saganta.de', 'tagebuch.saganta.de']) {
      expect(passendeCookieDomain('saganta.de', host)).toBe('saganta.de');
    }
  });

  it('wandert in den Raum, aus dem die Anfrage kam', () => {
    expect(passendeCookieDomain('saganta.de', 'tagebuch.home.arpa')).toBe('.home.arpa');
    expect(passendeCookieDomain('saganta.de', 'shell.home.arpa')).toBe('.home.arpa');
  });

  it('nimmt den Port aus dem Host heraus', () => {
    expect(passendeCookieDomain('saganta.de', 'shell.home.arpa:8443')).toBe('.home.arpa');
  });

  it('ist gegen Gross- und Kleinschreibung unempfindlich', () => {
    expect(passendeCookieDomain('saganta.de', 'Shell.Saganta.DE')).toBe('saganta.de');
  });

  it('faellt auf host-only zurueck, wo es keine Registrar-Domain gibt', () => {
    // Lieber eine App angemeldet als gar keine: ohne Domain gilt das Cookie
    // nur fuer diesen einen Host, statt verworfen zu werden.
    expect(passendeCookieDomain('saganta.de', '192.0.2.10')).toBeUndefined();
    expect(passendeCookieDomain('saganta.de', 'localhost')).toBeUndefined();
  });

  it('laesst sich nicht von einem aehnlich klingenden Namen taeuschen', () => {
    // ★ `nichtsaganta.de` endet zwar auf `saganta.de`, ist aber eine fremde
    // Domain. Der Punkt vor dem Suffix ist der ganze Unterschied.
    expect(passendeCookieDomain('saganta.de', 'nichtsaganta.de')).toBe('.nichtsaganta.de');
  });

  it('benutzt dieselbe Ableitung wie das Theme-Cookie', () => {
    expect(passendeCookieDomain('saganta.de', 'tagebuch.home.arpa')).toBe(
      parentCookieDomain('tagebuch.home.arpa'),
    );
  });
});

describe('Login-Adressen je Domain-Raum', () => {
  it('liest eine einzelne Zuordnung', () => {
    expect(leseLoginUrls('home.arpa=https://shell.home.arpa/login')).toEqual({
      'home.arpa': 'https://shell.home.arpa/login',
    });
  });

  it('liest mehrere und verzeiht Leerzeichen', () => {
    expect(leseLoginUrls(' a.test=https://a/login , b.test=https://b/login ')).toEqual({
      'a.test': 'https://a/login',
      'b.test': 'https://b/login',
    });
  });

  it('uebergeht Unbrauchbares, statt den Start zu verhindern', () => {
    // Eine kaputte Zusatzangabe darf die Anmeldung im Hauptraum nicht mitreissen.
    expect(leseLoginUrls('kaputt,=https://x,y=')).toEqual({});
    expect(leseLoginUrls(undefined)).toEqual({});
    expect(leseLoginUrls('')).toEqual({});
  });
});

describe('Auswahl der Login-Seite', () => {
  const cfg: BetterAuthConfig = {
    authServiceUrl: 'http://saganta-auth:3000',
    loginUrl: 'https://saganta.de/login',
    loginUrls: { 'home.arpa': 'https://shell.home.arpa/login' },
  };

  it('bleibt im Hauptraum bei der Hauptadresse', () => {
    expect(anmeldeadresseFuer(cfg, 'tagebuch.saganta.de')).toBe('https://saganta.de/login');
  });

  it('schickt den .home-Raum an die .home-Anmeldung', () => {
    expect(anmeldeadresseFuer(cfg, 'tagebuch.home.arpa')).toBe(
      'https://shell.home.arpa/login',
    );
    expect(anmeldeadresseFuer(cfg, 'home.arpa')).toBe('https://shell.home.arpa/login');
  });

  it('faellt ohne Host und ohne Zuordnung auf die Hauptadresse zurueck', () => {
    expect(anmeldeadresseFuer(cfg, undefined)).toBe('https://saganta.de/login');
    expect(anmeldeadresseFuer({ ...cfg, loginUrls: undefined }, 'x.home.arpa')).toBe(
      'https://saganta.de/login',
    );
  });

  it('waehlt nicht anhand eines aehnlich klingenden Namens', () => {
    expect(anmeldeadresseFuer(cfg, 'nichthome.arpa')).toBe('https://saganta.de/login');
  });
});

describe('Weiterleitung nach der Anmeldung', () => {
  const shell = 'shell.home.arpa';

  it('laesst app-interne Pfade durch', () => {
    expect(sicheresZiel('/notizen?x=1', shell)).toBe('/notizen?x=1');
  });

  it('laesst absolute Ziele im eigenen Domain-Raum durch', () => {
    // Der eigentliche Zweck: aus der Anmeldung zurueck in die App, aus der man kam.
    expect(sicheresZiel('https://tagebuch.home.arpa/', shell)).toBe(
      'https://tagebuch.home.arpa/',
    );
  });

  it('weist fremde Domains ab', () => {
    for (const boese of [
      'https://fremd.example/',
      '//fremd.example/',
      'https://tagebuch.home.arpa.fremd.de/',
      'http://home.arpa@fremd.de/',
    ]) {
      expect(sicheresZiel(boese, shell)).toBe('/');
    }
  });

  it('weist andere Protokolle ab', () => {
    expect(sicheresZiel('javascript:alert(1)', shell)).toBe('/');
    expect(sicheresZiel('data:text/html,<script>', shell)).toBe('/');
  });

  it('weist absolute Ziele ab, wenn der eigene Host unbekannt ist', () => {
    // Ohne Bezugspunkt laesst sich "eigener Raum" nicht beurteilen: dann lieber
    // auf die Startseite als raten.
    expect(sicheresZiel('https://tagebuch.home.arpa/', undefined)).toBe('/');
  });

  it('faellt bei fehlender oder unlesbarer Angabe auf die Startseite', () => {
    expect(sicheresZiel(null, shell)).toBe('/');
    expect(sicheresZiel('', shell)).toBe('/');
    expect(sicheresZiel('h ttp://kaputt', shell)).toBe('/');
  });

  it('trennt die beiden Raeume voneinander', () => {
    // ★ saganta.de und home.arpa sind verschiedene Raeume. Ein Ziel im einen
    // darf aus dem anderen heraus nicht angesteuert werden, sonst waere der
    // Schutz gegen offene Weiterleitungen an der Stelle wieder offen.
    expect(sicheresZiel('https://tagebuch.home.arpa/', 'shell.saganta.de')).toBe('/');
    expect(sicheresZiel('https://notizen.saganta.de/', shell)).toBe('/');
  });
});

describe('Cookie und Anmeldeseite passen zusammen', () => {
  /** ★ Der eigentliche Punkt: wer auf Seite X angemeldet wird, muss ein Cookie
   * bekommen, das App Y im selben Raum auch sendet. Die beiden Funktionen
   * einzeln zu pruefen wuerde diesen Zusammenhang nicht abdecken. */
  const cfg: BetterAuthConfig = {
    authServiceUrl: 'http://saganta-auth:3000',
    loginUrl: 'https://saganta.de/login',
    loginUrls: { 'home.arpa': 'https://shell.home.arpa/login' },
  };

  for (const [app, erwarteteAnmeldung] of [
    ['tagebuch.home.arpa', 'https://shell.home.arpa/login'],
    ['tagebuch.saganta.de', 'https://saganta.de/login'],
  ] as const) {
    it(`${app} wird dorthin geschickt, wo das Cookie fuer ihn gilt`, () => {
      const anmeldung = anmeldeadresseFuer(cfg, app);
      expect(anmeldung).toBe(erwarteteAnmeldung);

      // Das Cookie entsteht auf der Anmeldeseite, also mit deren Host.
      const anmeldeHost = new URL(anmeldung).host;
      const domain = passendeCookieDomain('saganta.de', anmeldeHost);

      // Und es muss von der App gesendet werden, also zu ihrem Host passen.
      const ohnePunkt = (domain ?? '').replace(/^\./, '');
      expect(app === ohnePunkt || app.endsWith('.' + ohnePunkt)).toBe(true);
    });
  }
});
