/**
 * Fotografiert die Ansichtsprobe und misst dabei, was ein Bild allein nicht zeigt.
 *
 * Zwei Breiten, weil genau zwei real vorkommen: 1500 für den Laptop, 390 für das
 * Handy. Der Kalender soll ausdrücklich auch am Handy korrigierbar sein, und
 * dort entscheidet sich, ob Ziehen und Fallenlassen überhaupt möglich ist.
 *
 * Gemessen wird zusätzlich zum Bild:
 * - die Höhen der Blöcke gegen ihre Dauer (folgt die Höhe der Zeit?)
 * - ob die Entfernen-Zone während des Ziehens im sichtbaren Bereich liegt
 *   (sie erscheint unterhalb der Liste, und eine volle Tagesdecke ist lang)
 */
import puppeteer from 'puppeteer';
import { mkdirSync } from 'node:fs';

const BASIS = process.env.PROBE_URL ?? 'http://127.0.0.1:8202';
const AUSGABE = process.env.PROBE_OUT ?? '/tmp/decke-probe';
const FAELLE = ['arbeitstag_fest', 'arbeitstag_offen', 'freier_tag_verworfen'];
const BREITEN = [
  { name: 'laptop', breite: 1500, hoehe: 1400 },
  { name: 'handy', breite: 390, hoehe: 844 },
];

mkdirSync(AUSGABE, { recursive: true });

const browser = await puppeteer.launch({
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});

for (const { name, breite, hoehe } of BREITEN) {
  for (const fall of FAELLE) {
    const seite = await browser.newPage();
    await seite.setViewport({ width: breite, height: hoehe, isMobile: name === 'handy' });
    await seite.goto(`${BASIS}/?fall=${fall}`, { waitUntil: 'networkidle0' });
    await seite.waitForSelector('ul li', { timeout: 10000 });

    const datei = `${AUSGABE}/${name}-${fall}.png`;
    await seite.screenshot({ path: datei, fullPage: true });

    // Blockhöhe gegen Dauer: zeigt, ab wann die Höhe nichts mehr aussagt.
    const bloecke = await seite.evaluate(() =>
      [...document.querySelectorAll('ul li')].map((li) => ({
        text: li.innerText.replace(/\s+/g, ' ').slice(0, 60),
        hoehe: Math.round(li.getBoundingClientRect().height),
      })),
    );

    // Passt der ganze Tag auf den Schirm, ohne zu scrollen?
    const masse = await seite.evaluate(() => ({
      seitenhoehe: document.documentElement.scrollHeight,
      sichtbar: window.innerHeight,
      listeUnten: Math.round(
        document.querySelector('ul')?.getBoundingClientRect().bottom ?? 0,
      ),
    }));

    console.log(`\n== ${name} / ${fall} (${breite}x${hoehe}) -> ${datei}`);
    console.log(
      `   Seite ${masse.seitenhoehe}px hoch, sichtbar ${masse.sichtbar}px, ` +
        `Listenende bei ${masse.listeUnten}px`,
    );
    const hoehen = [...new Set(bloecke.map((b) => b.hoehe))].sort((a, b) => a - b);
    console.log(`   ${bloecke.length} Bloecke, Hoehen: ${hoehen.join(', ')}px`);

    await seite.close();
  }
}

// Der eigentliche Test am Handy: lässt sich ein Block bis zur Entfernen-Zone
// ziehen, ohne dass sie ausserhalb des Bildschirms liegt?
for (const { name, breite, hoehe } of BREITEN) {
  const seite = await browser.newPage();
  await seite.setViewport({ width: breite, height: hoehe, isMobile: name === 'handy' });
  await seite.goto(`${BASIS}/?fall=arbeitstag_fest`, { waitUntil: 'networkidle0' });
  await seite.waitForSelector('button[aria-label$="verschieben"]');

  const griffe = await seite.$$('button[aria-label$="verschieben"]');
  const griff = griffe[0];
  const kasten = await griff.boundingBox();

  // Ziehen anstossen: Pointer-Events, wie die Komponente sie erwartet.
  await seite.mouse.move(kasten.x + kasten.width / 2, kasten.y + kasten.height / 2);
  await seite.mouse.down();
  await seite.mouse.move(kasten.x + kasten.width / 2, kasten.y + 60, { steps: 5 });

  const lage = await seite.evaluate(() => {
    const zone = [...document.querySelectorAll('div')].find((d) =>
      d.textContent?.includes('Hierher ziehen, was du nicht gemacht hast'),
    );
    const liste = document.querySelector('ul');
    return {
      zoneDa: Boolean(zone),
      zoneOben: zone ? Math.round(zone.getBoundingClientRect().top) : null,
      listeUnten: liste ? Math.round(liste.getBoundingClientRect().bottom) : null,
      sichtbar: window.innerHeight,
      scrollY: Math.round(window.scrollY),
      seitenhoehe: document.documentElement.scrollHeight,
    };
  });

  await seite.screenshot({ path: `${AUSGABE}/${name}-ziehen.png`, fullPage: false });
  await seite.mouse.up();

  console.log(`\n== ${name} / Ziehen angestossen`);
  console.log(`   Entfernen-Zone vorhanden: ${lage.zoneDa}`);
  console.log(
    `   Zone beginnt bei ${lage.zoneOben}px, Listenende ${lage.listeUnten}px, ` +
      `Schirm ${lage.sichtbar}px hoch (Seite ${lage.seitenhoehe}px)`,
  );
  if (lage.zoneOben !== null && lage.zoneOben > lage.sichtbar) {
    console.log(
      `   BEFUND: die Zone liegt ${lage.zoneOben - lage.sichtbar}px unterhalb des ` +
        `sichtbaren Bereichs. Sie ist beim Ziehen nicht erreichbar.`,
    );
  }
  await seite.close();
}

await browser.close();
