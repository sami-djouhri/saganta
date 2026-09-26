/**
 * Verschlüsselung: geprüft gegen die WebCrypto-Umsetzung von Node, also
 * dieselbe Norm, die der Browser verwendet.
 *
 * Der wichtigste Test ist der vorletzte: dass ein falscher Schlüssel *scheitert*
 * und nicht etwa Unsinn liefert. Ein Verfahren, das bei falschem Schlüssel
 * klaglos Datenmüll zurückgibt, würde den Leser mit einer kaputten Notiz
 * alleinlassen, statt ihm zu sagen, dass der Link unvollständig ist.
 */

import { describe, expect, it } from 'vitest';
import {
  entschluesseln,
  neuerSchluessel,
  neuesSalz,
  paketOeffnen,
  paketSchnueren,
  schluesselAusPasswort,
  schluesselExportieren,
  schluesselImportieren,
  verschluesseln,
} from './krypto';

describe('Schlüssel aus dem Adress-Fragment', () => {
  it('übersteht Export und Import', async () => {
    const key = await neuerSchluessel();
    const kodiert = await schluesselExportieren(key);
    const zurueck = await schluesselImportieren(kodiert);

    const { chiffrat, iv } = await verschluesseln('Geheimnis', key);
    expect(await entschluesseln(chiffrat, iv, zurueck)).toBe('Geheimnis');
  });

  it('ergibt eine Kodierung, die ohne Umschreiben in eine Adresse passt', async () => {
    // base64url: keine +, /, =, sonst zerlegt der Browser das Fragment.
    const kodiert = await schluesselExportieren(await neuerSchluessel());
    expect(kodiert).toMatch(/^[A-Za-z0-9_-]+$/);
  });
});

describe('Schlüssel aus einem Passwort', () => {
  it('ergibt bei gleichem Passwort und Salz denselben Schlüssel', async () => {
    const salz = neuesSalz();
    const a = await schluesselAusPasswort('Sonnenblume42', salz, 50_000);
    const b = await schluesselAusPasswort('Sonnenblume42', salz, 50_000);
    const { chiffrat, iv } = await verschluesseln('Text', a);
    expect(await entschluesseln(chiffrat, iv, b)).toBe('Text');
  });

  it('ergibt bei anderem Salz einen anderen Schlüssel', async () => {
    const a = await schluesselAusPasswort('gleich', neuesSalz(), 50_000);
    const b = await schluesselAusPasswort('gleich', neuesSalz(), 50_000);
    const { chiffrat, iv } = await verschluesseln('Text', a);
    await expect(entschluesseln(chiffrat, iv, b)).rejects.toThrow();
  });
});

describe('Verschlüsseln', () => {
  it('nimmt für jeden Vorgang einen neuen Zufallswert', async () => {
    // Bei AES-GCM wäre ein zweites Mal derselbe iv kein Schönheitsfehler,
    // sondern der Verlust der Vertraulichkeit.
    const key = await neuerSchluessel();
    const eins = await verschluesseln('gleicher Text', key);
    const zwei = await verschluesseln('gleicher Text', key);
    expect(eins.iv).not.toBe(zwei.iv);
    expect(eins.chiffrat).not.toBe(zwei.chiffrat);
  });

  it('scheitert bei falschem Schlüssel, statt Unsinn zu liefern', async () => {
    const { chiffrat, iv } = await verschluesseln('Geheim', await neuerSchluessel());
    await expect(entschluesseln(chiffrat, iv, await neuerSchluessel())).rejects.toThrow();
  });

  it('merkt eine Veränderung am Chiffrat', async () => {
    const key = await neuerSchluessel();
    const { chiffrat, iv } = await verschluesseln('Ursprung', key);
    const verdreht = chiffrat.slice(0, -4) + (chiffrat.slice(-4) === 'AAAA' ? 'BBBB' : 'AAAA');
    await expect(entschluesseln(verdreht, iv, key)).rejects.toThrow();
  });

  it('trägt auch lange Texte und Sonderzeichen', async () => {
    const key = await neuerSchluessel();
    const lang = 'Äöü ß: 😀 '.repeat(20_000);
    const { chiffrat, iv } = await verschluesseln(lang, key);
    expect(await entschluesseln(chiffrat, iv, key)).toBe(lang);
  });
});

describe('Paket aus Titel und Text', () => {
  it('bringt beides unverändert zurück', () => {
    const paket = paketSchnueren('Der Titel', '# Inhalt\n\nText');
    expect(paketOeffnen(paket)).toEqual({ titel: 'Der Titel', inhalt: '# Inhalt\n\nText' });
  });

  it('behandelt reinen Text als Inhalt ohne Titel', () => {
    expect(paketOeffnen('nur text')).toEqual({ titel: '', inhalt: 'nur text' });
  });
});
