/**
 * Was an den Kalender geht, und ausschliesslich das.
 *
 * ★★ Diese Datei ist die einzige Stelle, an der Daten dieses Tagebuchs das
 * Tagebuch verlassen. Sie ist bewusst als **Allowlist** gebaut und nicht als
 * Durchreicher: es werden genau drei Felder gelesen und genau drei gesendet.
 *
 * Der Anlass ist konkret. Das Ziel-Schema `CheckInIn` im kalender-bff kennt ein
 * Feld `note` (bis 1000 Zeichen Freitext), und der Kalender legt es
 * unverschluesselt in seiner Datenbank ab. Ein `JSON.stringify(eingabe)` an
 * dieser Stelle wuerde also, sobald irgendwann ein `note` im Eintragspaket
 * auftaucht, den Tagebuchtext im Klartext in einen anderen Dienst schreiben.
 * Nichts wuerde dabei rot; es fiele erst auf, wenn jemand in die Kalender-DB
 * sieht. Deshalb steht `note` hier nirgends, und `checkin.test.ts` haelt fest,
 * dass es so bleibt.
 *
 * Eigene Datei statt einer Funktion im `+server.ts`, weil SvelteKit dort nur
 * seine eigenen Exporte erlaubt. Der Bau bricht sonst ab, was beim ersten
 * Versuch auch geschehen ist.
 */

const STIMMUNG = ['gut', 'neutral', 'mies'];
const ENERGIE = ['hoch', 'mittel', 'niedrig'];
const SCHLAF = ['gut', 'mittel', 'schlecht'];

function nurAus(wert: unknown, erlaubt: string[]): string | undefined {
  return typeof wert === 'string' && erlaubt.includes(wert) ? wert : undefined;
}

export function checkinNutzlast(datum: string, roh: Record<string, unknown>): Record<string, string> {
  const nutzlast: Record<string, string> = { date: datum };
  const mood = nurAus(roh.stimmung, STIMMUNG);
  const energy = nurAus(roh.energie, ENERGIE);
  const sleep = nurAus(roh.schlaf, SCHLAF);
  if (mood) nutzlast.mood = mood;
  if (energy) nutzlast.energy = energy;
  if (sleep) nutzlast.sleep_quality = sleep;
  return nutzlast;
}
