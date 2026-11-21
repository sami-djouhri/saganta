// Sichtprobe mit erfundenen Daten: Desktop und Handy, Auswahl, Suche, [[-Liste.
// Aufruf ueber lauf.sh (setzt PLAYWRIGHT_CORE, CHROME, PROBE_URL, PROBE_BILDER).
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_CORE);
const ADRESSE = process.env.PROBE_URL;
const BILDER = process.env.PROBE_BILDER;
const browser = await chromium.launch({ executablePath: process.env.CHROME });
const ergebnis = {};
const fehler = [];
for (const [name, vp] of [
  ['desktop', { width: 1280, height: 900 }],
  ['handy', { width: 390, height: 844 }],
]) {
  const seite = await browser.newPage({ viewport: vp, deviceScaleFactor: 1, hasTouch: name === 'handy' });
  seite.on('pageerror', (e) => fehler.push(`${name}: ${e.message}`));
  seite.on('console', (m) => m.type() === 'error' && fehler.push(`${name}: ${m.text()}`));
  await seite.goto(ADRESSE);
  await seite.waitForTimeout(400);
  await seite.screenshot({ path: `${BILDER}/${name}-netz.png` });
  // Einen Knoten waehlen
  const box = await seite.locator('g.netz-knoten').first().boundingBox();
  if (name === 'handy') await seite.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  else await seite.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await seite.waitForTimeout(200);
  ergebnis[`${name}_auswahl`] = await seite.locator('[data-probe=auswahl]').innerText();
  await seite.screenshot({ path: `${BILDER}/${name}-auswahl.png` });
  // [[-Vorschlaege: Cursor ans Ende, ein Zeichen tippen
  await seite.locator('textarea').click();
  await seite.keyboard.press('Control+End');
  await seite.keyboard.type('t');
  await seite.waitForTimeout(400);
  ergebnis[`${name}_vorschlaege`] = await seite.locator('[role=option]').allInnerTexts();
  await seite.locator('[data-probe=editor]').screenshot({ path: `${BILDER}/${name}-vorschlag.png` });
  await seite.keyboard.press('ArrowDown');
  await seite.keyboard.press('Enter');
  await seite.waitForTimeout(100);
  ergebnis[`${name}_text`] = await seite.locator('[data-probe=text]').innerText();
  await seite.close();
}
// Fokus und Suche
const seite = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await seite.goto(`${ADRESSE}?fokus=6&suche=lichtorgel`);
await seite.waitForTimeout(400);
ergebnis.fokus_auswahl = await seite.locator('[data-probe=auswahl]').innerText();
await seite.screenshot({ path: `${BILDER}/desktop-fokus-suche.png` });
await browser.close();
console.log(JSON.stringify({ ergebnis, fehler }, null, 2));
