/**
 * Tests gegen ein echtes DOM (happy-dom), nicht gegen einen Nachbau.
 *
 * Der Schwerpunkt liegt auf dem, was den Renderer überhaupt rechtfertigt: dass
 * aus fremdem Text niemals Markup wird. Die Formatierungstests sind das
 * Beiwerk, ein hübsch gerenderter Fettdruck wäre wertlos, wenn daneben ein
 * `<script>` durchkäme.
 */

// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { rendern } from './markdown';

const doc = document;

function html(quelle: string): string {
  const halter = doc.createElement('div');
  halter.appendChild(rendern(quelle, doc));
  return halter.innerHTML;
}

function knoten(quelle: string): HTMLDivElement {
  const halter = doc.createElement('div');
  halter.appendChild(rendern(quelle, doc));
  return halter;
}

describe('Markup aus fremdem Text', () => {
  it('führt eingebettetes HTML nicht aus, sondern zeigt es', () => {
    const aus = html('<script>alert(1)</script>');
    expect(aus).not.toContain('<script>');
    expect(aus).toContain('&lt;script&gt;');
  });

  it('lässt kein img mit onerror entstehen', () => {
    const aus = knoten('<img src=x onerror="alert(1)">');
    expect(aus.querySelector('img')).toBeNull();
    expect(aus.textContent).toContain('onerror');
  });

  it('macht aus javascript:-Adressen keinen Link', () => {
    const aus = knoten('[klick mich](javascript:alert(1))');
    expect(aus.querySelector('a')).toBeNull();
    expect(aus.textContent).toContain('klick mich');
  });

  it('lehnt data:-Adressen ab', () => {
    const aus = knoten('[x](data:text/html,<script>alert(1)</script>)');
    expect(aus.querySelector('a')).toBeNull();
  });

  it('lässt http, https und mailto durch', () => {
    for (const ziel of ['https://example.org/', 'http://example.org/', 'mailto:a@b.de']) {
      const a = knoten(`[Text](${ziel})`).querySelector('a');
      expect(a, ziel).not.toBeNull();
      expect(a?.getAttribute('href')).toContain(ziel.split(':')[0]);
    }
  });

  it('setzt rel und target an jedem Link', () => {
    const a = knoten('[x](https://example.org)').querySelector('a');
    expect(a?.getAttribute('rel')).toContain('noopener');
    expect(a?.getAttribute('target')).toBe('_blank');
  });

  it('bettet keine fremden Bilder ein, sondern verlinkt sie', () => {
    // Ein automatisch geladenes Bild würde dem fremden Server verraten, wer
    // wann eine geteilte Notiz öffnet.
    const aus = knoten('![Beschreibung](https://fremder-server.example/pixel.png)');
    expect(aus.querySelector('img')).toBeNull();
    expect(aus.querySelector('a')?.textContent).toBe('Beschreibung');
  });

  it('lässt Auszeichnung im Codeblock unangetastet', () => {
    const aus = knoten('```\n<b>fett?</b> **auch nicht**\n```');
    expect(aus.querySelector('b')).toBeNull();
    expect(aus.querySelector('strong')).toBeNull();
    expect(aus.querySelector('code')?.textContent).toContain('<b>fett?</b>');
  });

  it('behandelt auch Inline-Code als Text', () => {
    const aus = knoten('`<img src=x onerror=1>`');
    expect(aus.querySelector('img')).toBeNull();
    expect(aus.querySelector('code')?.textContent).toBe('<img src=x onerror=1>');
  });
});

describe('Formatierung', () => {
  it('erkennt Überschriften bis Stufe sechs', () => {
    expect(knoten('# Eins').querySelector('h1')?.textContent).toBe('Eins');
    expect(knoten('###### Sechs').querySelector('h6')?.textContent).toBe('Sechs');
    // Sieben Rauten sind keine Überschrift mehr.
    expect(knoten('####### Sieben').querySelector('h7')).toBeNull();
  });

  it('setzt fett, kursiv und durchgestrichen', () => {
    expect(knoten('**fett**').querySelector('strong')?.textContent).toBe('fett');
    expect(knoten('*kursiv*').querySelector('em')?.textContent).toBe('kursiv');
    expect(knoten('~~weg~~').querySelector('del')?.textContent).toBe('weg');
  });

  it('lässt Unterstriche innerhalb von Wörtern in Ruhe', () => {
    // sonst würde aus `mein_feld_name` mitten im Text eine Kursivschrift
    const aus = knoten('die Variable mein_feld_name steht dort');
    expect(aus.querySelector('em')).toBeNull();
  });

  it('baut Listen, auch verschachtelte', () => {
    const aus = knoten('- eins\n- zwei\n  - zwei a\n- drei');
    const oben = aus.querySelector('ul');
    expect(oben?.children.length).toBe(3);
    expect(oben?.querySelector('ul')).not.toBeNull();
  });

  it('unterscheidet nummerierte von Aufzählungslisten', () => {
    expect(knoten('1. eins\n2. zwei').querySelector('ol')).not.toBeNull();
    expect(knoten('- eins').querySelector('ol')).toBeNull();
  });

  it('zeigt Aufgabenlisten als nicht bedienbare Kästchen', () => {
    const aus = knoten('- [x] erledigt\n- [ ] offen');
    const kaesten = aus.querySelectorAll('input[type=checkbox]');
    expect(kaesten.length).toBe(2);
    expect((kaesten[0] as HTMLInputElement).checked).toBe(true);
    // Anklickbar wäre eine Lüge: gespeichert würde nichts.
    expect((kaesten[0] as HTMLInputElement).disabled).toBe(true);
  });

  it('rendert Zitate und Trennlinien', () => {
    expect(knoten('> zitiert').querySelector('blockquote')?.textContent).toContain('zitiert');
    expect(knoten('---').querySelector('hr')).not.toBeNull();
  });

  it('rendert Tabellen mit Kopfzeile', () => {
    const aus = knoten('| A | B |\n| --- | --- |\n| 1 | 2 |');
    expect(aus.querySelectorAll('th').length).toBe(2);
    expect(aus.querySelectorAll('td').length).toBe(2);
  });

  it('verlinkt nackte Adressen', () => {
    const a = knoten('siehe https://example.org/pfad hier').querySelector('a');
    expect(a?.getAttribute('href')).toBe('https://example.org/pfad');
  });

  it('trennt Absätze an Leerzeilen', () => {
    expect(knoten('eins\n\nzwei').querySelectorAll('p').length).toBe(2);
  });

  it('kommt mit leerem und mit reinem Zeilenumbruch-Text zurecht', () => {
    expect(html('')).toBe('');
    expect(html('\n\n\n')).toBe('');
  });

  it('behandelt Windows-Zeilenenden wie Unix-Zeilenenden', () => {
    expect(knoten('# Titel\r\n\r\nText').querySelector('h1')?.textContent).toBe('Titel');
  });
});
