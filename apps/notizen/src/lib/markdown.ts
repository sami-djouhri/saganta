/**
 * Markdown → DOM.
 *
 * Der Renderer baut **Elemente, keine HTML-Zeichenketten**. Es gibt in dieser
 * Datei kein `innerHTML`, und alles, was aus dem Text stammt, wird über
 * `createTextNode` gesetzt. Damit ist das Einschleusen von Markup strukturell
 * ausgeschlossen statt nachträglich weggefiltert, der Unterschied zählt hier,
 * weil dieselbe Funktion auch Fremdinhalte auf der öffentlichen Leseseite
 * darstellt, und eine Filterliste ist immer nur so gut wie ihre letzte
 * Aktualisierung.
 *
 * Deshalb auch keine Markdown-Bibliothek: die üblichen liefern HTML-Strings und
 * bräuchten eine zweite Abhängigkeit zum Saubermachen. Zwei Pakete mehr im
 * Auslieferungsstand, deren Lücken man verfolgen muss, für einen Funktionsumfang,
 * den eine Notiz nicht braucht.
 *
 * Bewusst nicht unterstützt:
 * - **Eingebettete Bilder aus fremden Adressen.** `![…](https://fremd/…)` wird zu
 *   einem Link. Ein automatisch geladenes Bild verrät dem fremden Server, wer
 *   wann eine geteilte Notiz öffnet, auf einer Seite, deren ganzer Zweck
 *   Vertraulichkeit ist, wäre das ein Selbstwiderspruch. Eigene Anhänge zeigt
 *   die Oberfläche separat an.
 * - **Rohes HTML.** Wird als Text dargestellt, nicht ausgeführt.
 */

const ERLAUBTE_SCHEMATA = new Set(['http:', 'https:', 'mailto:']);

/** Adresse prüfen; unklares wird zu `null` und damit zu reinem Text. */
function sichereAdresse(roh: string): string | null {
  const wert = roh.trim();
  if (!wert) return null;
  try {
    // Basis nur zum Auflösen relativer Angaben, das Ergebnis muss trotzdem
    // ein erlaubtes Schema haben.
    const url = new URL(wert, 'https://saganta.de');
    return ERLAUBTE_SCHEMATA.has(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

interface InlineMuster {
  regex: RegExp;
  bauen: (treffer: RegExpExecArray, doc: Document) => Node;
}

const INLINE: InlineMuster[] = [
  // Code zuerst: innerhalb von `…` gilt keine weitere Auszeichnung.
  {
    regex: /`([^`]+)`/,
    bauen: (t, doc) => {
      const el = doc.createElement('code');
      el.textContent = t[1] ?? '';
      return el;
    },
  },
  {
    regex: /!\[([^\]]*)\]\(([^)\s]+)\)/,
    bauen: (t, doc) => bildAlsLink(t[1] ?? '', t[2] ?? '', doc),
  },
  {
    regex: /\[([^\]]+)\]\(([^)\s]+)\)/,
    bauen: (t, doc) => link(t[1] ?? '', t[2] ?? '', doc),
  },
  // Nackte Adressen verlinken, in Notizen steht oft nur die URL.
  {
    regex: /(https?:\/\/[^\s<>"')]+)/,
    bauen: (t, doc) => link(t[1] ?? '', t[1] ?? '', doc),
  },
  {
    regex: /\*\*([^*]+)\*\*/,
    bauen: (t, doc) => umhuellen('strong', t[1] ?? '', doc),
  },
  {
    regex: /__([^_]+)__/,
    bauen: (t, doc) => umhuellen('strong', t[1] ?? '', doc),
  },
  {
    regex: /~~([^~]+)~~/,
    bauen: (t, doc) => umhuellen('del', t[1] ?? '', doc),
  },
  {
    regex: /\*([^*]+)\*/,
    bauen: (t, doc) => umhuellen('em', t[1] ?? '', doc),
  },
  {
    regex: /(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])/,
    bauen: (t, doc) => umhuellen('em', t[1] ?? '', doc),
  },
];

function umhuellen(tag: string, inhalt: string, doc: Document): Node {
  const el = doc.createElement(tag);
  el.appendChild(inline(inhalt, doc));
  return el;
}

function link(text: string, ziel: string, doc: Document): Node {
  const adresse = sichereAdresse(ziel);
  if (!adresse) return doc.createTextNode(text);
  const a = doc.createElement('a');
  a.href = adresse;
  a.textContent = text || adresse;
  a.rel = 'noopener noreferrer nofollow';
  a.target = '_blank';
  return a;
}

function bildAlsLink(beschriftung: string, ziel: string, doc: Document): Node {
  const adresse = sichereAdresse(ziel);
  if (!adresse) return doc.createTextNode(beschriftung);
  const a = link(beschriftung || adresse, adresse, doc);
  if (a instanceof HTMLAnchorElement) a.dataset.bild = 'true';
  return a;
}

/** Eine Zeile Text in Knoten übersetzen (rekursiv für verschachtelte Auszeichnung). */
function inline(text: string, doc: Document): DocumentFragment {
  const teil = doc.createDocumentFragment();
  let rest = text;

  while (rest) {
    let frühester: { index: number; treffer: RegExpExecArray; muster: InlineMuster } | null = null;
    for (const muster of INLINE) {
      const treffer = muster.regex.exec(rest);
      if (treffer && (frühester === null || treffer.index < frühester.index)) {
        frühester = { index: treffer.index, treffer, muster };
      }
    }
    if (!frühester) break;

    if (frühester.index > 0) {
      teil.appendChild(doc.createTextNode(rest.slice(0, frühester.index)));
    }
    teil.appendChild(frühester.muster.bauen(frühester.treffer, doc));
    rest = rest.slice(frühester.index + frühester.treffer[0].length);
  }

  if (rest) teil.appendChild(doc.createTextNode(rest));
  return teil;
}

function istTrennlinie(zeile: string): boolean {
  return /^ {0,3}([-*_])\s*(\1\s*){2,}$/.test(zeile);
}

function tabellenTrenner(zeile: string): boolean {
  return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(zeile);
}

function zellen(zeile: string): string[] {
  return zeile
    .replace(/^\s*\|/, '')
    .replace(/\|\s*$/, '')
    .split('|')
    .map((z) => z.trim());
}

/**
 * Markdown in einen Dokumentausschnitt übersetzen.
 *
 * `doc` ist überschreibbar, damit derselbe Code in Tests gegen ein
 * Fremd-Dokument laufen kann.
 */
export function rendern(quelle: string, doc: Document = document): DocumentFragment {
  const aus = doc.createDocumentFragment();
  const zeilen = (quelle ?? '').replace(/\r\n?/g, '\n').split('\n');
  let i = 0;

  const absatzPuffer: string[] = [];
  function absatzAbschliessen() {
    if (!absatzPuffer.length) return;
    const p = doc.createElement('p');
    p.appendChild(inline(absatzPuffer.join('\n'), doc));
    aus.appendChild(p);
    absatzPuffer.length = 0;
  }

  while (i < zeilen.length) {
    const zeile = zeilen[i] ?? '';

    // Codeblock: alles darin bleibt Text, auch Markdown-Zeichen.
    const zaun = /^\s*```(.*)$/.exec(zeile);
    if (zaun) {
      absatzAbschliessen();
      const inhalt: string[] = [];
      i++;
      while (i < zeilen.length && !/^\s*```/.test(zeilen[i] ?? '')) {
        inhalt.push(zeilen[i] ?? '');
        i++;
      }
      i++; // schließender Zaun
      const pre = doc.createElement('pre');
      const code = doc.createElement('code');
      const sprache = (zaun[1] ?? '').trim();
      if (sprache) code.dataset.sprache = sprache;
      code.textContent = inhalt.join('\n');
      pre.appendChild(code);
      aus.appendChild(pre);
      continue;
    }

    if (!zeile.trim()) {
      absatzAbschliessen();
      i++;
      continue;
    }

    if (istTrennlinie(zeile)) {
      absatzAbschliessen();
      aus.appendChild(doc.createElement('hr'));
      i++;
      continue;
    }

    const überschrift = /^ {0,3}(#{1,6})\s+(.*)$/.exec(zeile);
    if (überschrift) {
      absatzAbschliessen();
      const stufe = (überschrift[1] ?? '#').length;
      const h = doc.createElement(`h${Math.min(stufe, 6)}`);
      h.appendChild(inline(überschrift[2] ?? '', doc));
      aus.appendChild(h);
      i++;
      continue;
    }

    if (/^ {0,3}>/.test(zeile)) {
      absatzAbschliessen();
      const inhalt: string[] = [];
      while (i < zeilen.length && /^ {0,3}>/.test(zeilen[i] ?? '')) {
        inhalt.push((zeilen[i] ?? '').replace(/^ {0,3}>\s?/, ''));
        i++;
      }
      const zitat = doc.createElement('blockquote');
      zitat.appendChild(rendern(inhalt.join('\n'), doc));
      aus.appendChild(zitat);
      continue;
    }

    // Tabelle: Kopfzeile + Trennzeile + Körper.
    if (zeile.includes('|') && tabellenTrenner(zeilen[i + 1] ?? '')) {
      absatzAbschliessen();
      const tabelle = doc.createElement('table');
      const kopf = doc.createElement('thead');
      const kopfZeile = doc.createElement('tr');
      for (const z of zellen(zeile)) {
        const th = doc.createElement('th');
        th.appendChild(inline(z, doc));
        kopfZeile.appendChild(th);
      }
      kopf.appendChild(kopfZeile);
      tabelle.appendChild(kopf);
      i += 2;
      const körper = doc.createElement('tbody');
      while (i < zeilen.length && (zeilen[i] ?? '').includes('|')) {
        const tr = doc.createElement('tr');
        for (const z of zellen(zeilen[i] ?? '')) {
          const td = doc.createElement('td');
          td.appendChild(inline(z, doc));
          tr.appendChild(td);
        }
        körper.appendChild(tr);
        i++;
      }
      tabelle.appendChild(körper);
      aus.appendChild(tabelle);
      continue;
    }

    const listenAnfang = /^(\s*)([-*+]|\d+[.)])\s+/.exec(zeile);
    if (listenAnfang) {
      absatzAbschliessen();
      i = liste(zeilen, i, aus, doc, (listenAnfang[1] ?? '').length);
      continue;
    }

    absatzPuffer.push(zeile.trim());
    i++;
  }

  absatzAbschliessen();
  return aus;
}

/**
 * Listenblock ab Zeile `start` verarbeiten; gibt die nächste unverbrauchte
 * Zeile zurück. Verschachtelung entsteht über die Einrückung.
 */
function liste(
  zeilen: string[],
  start: number,
  ziel: Node,
  doc: Document,
  einzug: number,
): number {
  const erste = /^(\s*)([-*+]|\d+[.)])\s+/.exec(zeilen[start] ?? '');
  const geordnet = /\d/.test(erste?.[2] ?? '');
  const element = doc.createElement(geordnet ? 'ol' : 'ul');
  let i = start;

  while (i < zeilen.length) {
    const treffer = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(zeilen[i] ?? '');
    if (!treffer) break;
    const eigenerEinzug = (treffer[1] ?? '').length;
    if (eigenerEinzug < einzug) break;
    if (eigenerEinzug > einzug) {
      // Tiefere Ebene gehört unter den zuletzt begonnenen Punkt.
      i = liste(zeilen, i, element.lastElementChild ?? element, doc, eigenerEinzug);
      continue;
    }

    const li = doc.createElement('li');
    let text = treffer[3] ?? '';
    const kasten = /^\[([ xX])\]\s+(.*)$/.exec(text);
    if (kasten) {
      const box = doc.createElement('input');
      box.type = 'checkbox';
      box.checked = (kasten[1] ?? ' ').toLowerCase() === 'x';
      // Aufgabenlisten sind hier Darstellung, kein Bedienelement: angeklickt
      // würde nichts gespeichert, und ein Haken, der beim Neuladen verschwindet,
      // ist schlimmer als gar keiner. Geändert wird im Text.
      box.disabled = true;
      li.appendChild(box);
      text = kasten[2] ?? '';
    }
    li.appendChild(inline(text, doc));
    element.appendChild(li);
    i++;
  }

  ziel.appendChild(element);
  return i;
}
