import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { env } from '$env/dynamic/private';
import { downloadsFuer, type Platform } from '$lib/catalog';
import type { PageServerLoad } from './$types';

const DOWNLOADS_DIR = env.DOWNLOADS_DIR || '/app/downloads';

/** Was ein Release-Skript je App und Plattform als `<name>.json` ablegt. */
export interface ReleaseManifest {
  app: string;
  /**
   * Zielplattform des Artefakts.
   *
   * Fehlt das Feld, gilt `android`. Die vier Android-Manifeste im Volume
   * sind aelter als dieses Feld und tragen es nicht; eine Vorgabe `linux` oder
   * ein Abbruch haette sie stillschweigend von der Seite genommen.
   */
  platform?: Platform;
  versionCode?: number;
  versionName: string;
  /** Dateiname des Artefakts, relativ zu `/downloads/`. */
  apkUrl?: string;
  datei?: string;
  sha256: string;
  size: number;
  changelog?: string;
  publishedAt?: string;
}

/** Artefakte je Plattform, Schluessel ist der Release-Name der App. */
export type ReleaseIndex = Partial<Record<Platform, Record<string, ReleaseManifest>>>;

/**
 * Liest die Release-Manifeste aus dem Downloads-Volume.
 *
 * Warum ueberhaupt: bis 2026-08 stand in `catalog.ts` hart, welche Plattform
 * verfuegbar ist. Die Kalender-APK lag seit dem 19. Juli ausgeliefert im Volume,
 * war im Portal aber als „bald" markiert, sie war gehostet und trotzdem
 * unsichtbar, weil niemand den Katalog nachgezogen hatte. Jetzt entscheidet das
 * vorhandene Artefakt, nicht eine zweite Liste.
 *
 * Seit 2026-10-25 wird nach Plattform getrennt. Vorher war der Index
 * `releases[manifest.app]`, und ein zweites Manifest derselben App (Linux neben
 * Android) haette das erste ueberschrieben -- welches gewinnt, haette die
 * Reihenfolge von `readdir` entschieden, also der Zufall.
 *
 * Fehlt das Verzeichnis (lokale Entwicklung), bleibt die Karte einfach leer:
 * die Seite muss auch ohne Downloads rendern.
 */
async function manifesteLesen(): Promise<ReleaseIndex> {
  const releases: ReleaseIndex = {};
  let files: string[];
  try {
    files = await readdir(DOWNLOADS_DIR);
  } catch {
    return releases; // Kein Downloads-Volume gemountet.
  }
  for (const file of files) {
    if (!file.endsWith('.json')) continue;
    try {
      const raw = await readFile(join(DOWNLOADS_DIR, file), 'utf-8');
      const manifest = JSON.parse(raw) as ReleaseManifest;
      if (!manifest?.app || !manifest?.versionName) continue;
      const plattform: Platform = manifest.platform ?? 'android';
      (releases[plattform] ??= {})[manifest.app] = manifest;
    } catch {
      // Ein kaputtes Manifest darf die ganze Seite nicht mitnehmen.
    }
  }
  return releases;
}

export const load: PageServerLoad = async ({ url }) => {
  // Der Host der laufenden Anfrage bestimmt den Raum: wer ueber
  // shell.home.arpa kommt, bekommt die `.home`-Adressen der Apps. Bis zum
  // 2026-10-25 kam hier eine feste Domaene aus der Umgebung, und das waren
  // sieben Knoepfe auf Namen, die seit dem 21.10. mit 404 antworten.
  return { releases: await manifesteLesen(), apps: downloadsFuer(url.host) };
};
