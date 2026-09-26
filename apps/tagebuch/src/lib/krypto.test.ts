/**
 * Verschlüsselung, geprüft gegen die WebCrypto-Umsetzung von Node, also
 * dieselbe Norm, die der Browser verwendet.
 *
 * Die wichtigsten Tests sind die, in denen etwas *scheitert*: eine falsche
 * Passphrase muss abgewiesen werden und darf nicht klaglos Datenmüll liefern.
 * Ein Verfahren, das bei falschem Schlüssel irgendetwas zurückgibt, lässt den
 * Leser mit einem scheinbar zerstörten Tagebuch allein, statt ihm zu sagen,
 * dass er sich vertippt hat.
 *
 * PBKDF2 läuft hier mit der echten Rundenzahl. Das macht die Suite spürbar
 * langsamer, ist aber Absicht: eine Testsuite, die mit 1000 Runden rechnet,
 * prüft ein anderes Verfahren als das ausgelieferte.
 */

import { describe, expect, it } from 'vitest';
import {
  KryptoFehler,
  eintragEntschluesseln,
  eintragVerschluesseln,
  passphraseNeuVerpacken,
  schluesselNormalisieren,
  sichererKontext,
  tresorAnlegen,
  tresorOeffnen,
  tresorOeffnenMitWiederherstellung,
  wiederherstellungsschluesselErzeugen,
} from './krypto';

const PASS = 'ein hinreichend langes Kennwort';

describe('sicherer Kontext', () => {
  it('ist unter Node vorhanden', () => {
    expect(sichererKontext()).toBe(true);
  });
});

describe('Wiederherstellungsschlüssel', () => {
  it('ist in Vierergruppen lesbar', () => {
    expect(wiederherstellungsschluesselErzeugen()).toMatch(/^([0-9A-Z]{4}-){7}[0-9A-Z]{4}$/);
  });

  it('enthält keine verwechselbaren Zeichen', () => {
    for (let i = 0; i < 20; i++) {
      expect(wiederherstellungsschluesselErzeugen()).not.toMatch(/[ILOU]/);
    }
  });

  it('ist jedes Mal ein anderer', () => {
    const menge = new Set(Array.from({ length: 50 }, () => wiederherstellungsschluesselErzeugen()));
    expect(menge.size).toBe(50);
  });

  it('verzeiht Abschreibfehler bei 0/O und 1/I/L', () => {
    expect(schluesselNormalisieren('o1il-OI1L')).toBe(schluesselNormalisieren('0111-0111'));
  });

  it('verzeiht Kleinschreibung und fehlende Trennstriche', () => {
    expect(schluesselNormalisieren('ab12-cd34')).toBe(schluesselNormalisieren('ab12cd34'));
  });
});

describe('Tresor', () => {
  it('lässt sich mit der Passphrase öffnen', async () => {
    const { pakete, dek } = await tresorAnlegen(PASS);
    const wieder = await tresorOeffnen(pakete, PASS);

    // Gleicher Schlüssel heisst: was der eine schliesst, öffnet der andere.
    const paket = await eintragVerschluesseln({ text: 'Heute war ein guter Tag' }, dek);
    expect((await eintragEntschluesseln(paket, wieder)).text).toBe('Heute war ein guter Tag');
  });

  it('lässt sich mit dem Wiederherstellungsschlüssel öffnen', async () => {
    const { pakete, dek, wiederherstellungsschluessel } = await tresorAnlegen(PASS);
    const wieder = await tresorOeffnenMitWiederherstellung(pakete, wiederherstellungsschluessel);

    const paket = await eintragVerschluesseln({ text: 'Notfallweg' }, dek);
    expect((await eintragEntschluesseln(paket, wieder)).text).toBe('Notfallweg');
  });

  it('akzeptiert den Wiederherstellungsschlüssel auch abgetippt', async () => {
    const { pakete, wiederherstellungsschluessel } = await tresorAnlegen(PASS);
    const abgetippt = wiederherstellungsschluessel.toLowerCase().replace(/-/g, ' ');

    await expect(tresorOeffnenMitWiederherstellung(pakete, abgetippt)).resolves.toBeDefined();
  });

  it('weist eine falsche Passphrase ab, statt Unsinn zu liefern', async () => {
    const { pakete } = await tresorAnlegen(PASS);
    await expect(tresorOeffnen(pakete, 'falsch')).rejects.toThrow(KryptoFehler);
  });

  it('weist einen falschen Wiederherstellungsschlüssel ab', async () => {
    const { pakete } = await tresorAnlegen(PASS);
    const fremd = wiederherstellungsschluesselErzeugen();
    await expect(tresorOeffnenMitWiederherstellung(pakete, fremd)).rejects.toThrow(KryptoFehler);
  });

  it('verpackt denselben Schlüssel zweimal verschieden', async () => {
    const { pakete } = await tresorAnlegen(PASS);
    // Gleicher DEK, aber eigenes Salz und eigener Einmalwert je Zweig. Wären
    // die Pakete gleich, verriete das eine Paket etwas über das andere.
    expect(pakete.wrap_passphrase).not.toBe(pakete.wrap_wiederherstellung);
    expect(pakete.salz_passphrase).not.toBe(pakete.salz_wiederherstellung);
    expect(pakete.wrap_passphrase_iv).not.toBe(pakete.wrap_wiederherstellung_iv);
  });

  it('meldet die Rundenzahl, mit der wirklich gerechnet wurde', async () => {
    const { pakete } = await tresorAnlegen(PASS);
    expect(pakete.kdf_iterationen).toBe(310_000);
    expect(pakete.kdf).toBe('PBKDF2-SHA256');
  });
});

describe('Passphrasenwechsel', () => {
  it('öffnet den Bestand mit dem neuen Kennwort', async () => {
    const { pakete, dek } = await tresorAnlegen(PASS);
    const alt = await eintragVerschluesseln({ text: 'vor dem Wechsel' }, dek);

    const neu = await passphraseNeuVerpacken(dek, 'ein ganz neues Kennwort');
    const nachher = { ...pakete, ...neu };

    const geoeffnet = await tresorOeffnen(nachher, 'ein ganz neues Kennwort');
    expect((await eintragEntschluesseln(alt, geoeffnet)).text).toBe('vor dem Wechsel');
  });

  it('entwertet das alte Kennwort', async () => {
    const { pakete, dek } = await tresorAnlegen(PASS);
    const nachher = { ...pakete, ...(await passphraseNeuVerpacken(dek, 'neues Kennwort')) };

    await expect(tresorOeffnen(nachher, PASS)).rejects.toThrow(KryptoFehler);
  });

  it('lässt den Notfallzettel gültig', async () => {
    /** ★ Der Test zu der Entwurfsentscheidung, die man sonst nicht sieht:
     * ein Passwortwechsel darf einen ausgedruckten Wiederherstellungsschlüssel
     * nicht stillschweigend unbrauchbar machen. */
    const { pakete, dek, wiederherstellungsschluessel } = await tresorAnlegen(PASS);
    const nachher = { ...pakete, ...(await passphraseNeuVerpacken(dek, 'neues Kennwort')) };

    await expect(
      tresorOeffnenMitWiederherstellung(nachher, wiederherstellungsschluessel),
    ).resolves.toBeDefined();
  });
});

describe('Einträge', () => {
  it('übersteht Verschlüsseln und Entschlüsseln vollständig', async () => {
    const { dek } = await tresorAnlegen(PASS);
    const inhalt = {
      text: 'Ein Text mit Umlauten: Grüße, Straße, Öl. Und Zeilen.\n\nZweiter Absatz.',
      stimmung: 'gut' as const,
      energie: 'mittel' as const,
      schlaf: 'schlecht' as const,
    };

    const zurueck = await eintragEntschluesseln(await eintragVerschluesseln(inhalt, dek), dek);
    expect(zurueck).toEqual(inhalt);
  });

  it('verschlüsselt die Skalen mit, nicht nur den Text', async () => {
    const { dek } = await tresorAnlegen(PASS);
    const { chiffrat } = await eintragVerschluesseln(
      { text: 'x', stimmung: 'mies' },
      dek,
    );
    // Nichts vom Inhalt ist im Chiffrat zu erkennen, auch nicht die Stimmung.
    // Sie geht getrennt und bewusst an den Kalender, aber sie steht nicht
    // nebenbei offen in der Tagebuch-Datenbank.
    expect(atob(chiffrat)).not.toContain('mies');
  });

  it('erzeugt für denselben Text zweimal verschiedene Chiffrate', async () => {
    const { dek } = await tresorAnlegen(PASS);
    const eins = await eintragVerschluesseln({ text: 'derselbe Tag' }, dek);
    const zwei = await eintragVerschluesseln({ text: 'derselbe Tag' }, dek);

    expect(eins.chiffrat).not.toBe(zwei.chiffrat);
    expect(eins.iv).not.toBe(zwei.iv);
  });

  it('weist einen Eintrag ab, der zu einem fremden Schlüssel gehört', async () => {
    const einer = await tresorAnlegen(PASS);
    const anderer = await tresorAnlegen('anderes Kennwort');
    const paket = await eintragVerschluesseln({ text: 'geheim' }, einer.dek);

    await expect(eintragEntschluesseln(paket, anderer.dek)).rejects.toThrow(KryptoFehler);
  });

  it('merkt ein verändertes Chiffrat', async () => {
    /** AES-GCM siegelt. Ein veränderter Eintrag muss auffallen, statt
     * halb entschlüsselt zu werden. */
    const { dek } = await tresorAnlegen(PASS);
    const paket = await eintragVerschluesseln({ text: 'unverfälscht' }, dek);
    const bytes = atob(paket.chiffrat).split('');
    bytes[0] = bytes[0] === 'A' ? 'B' : 'A';
    const verfaelscht = { ...paket, chiffrat: btoa(bytes.join('')) };

    await expect(eintragEntschluesseln(verfaelscht, dek)).rejects.toThrow(KryptoFehler);
  });

  it('gibt einen leeren Text zurück statt zu scheitern, wenn Felder fehlen', async () => {
    const { dek } = await tresorAnlegen(PASS);
    const zurueck = await eintragEntschluesseln(await eintragVerschluesseln({ text: '' }, dek), dek);
    expect(zurueck.text).toBe('');
    expect(zurueck.stimmung).toBeNull();
  });
});
