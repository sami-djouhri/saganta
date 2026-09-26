import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types';

const DOWNLOADS_DIR = env.DOWNLOADS_DIR || '/app/downloads';

/** Was `saganta-android/release.sh` je App als `<app>.json` ablegt. */
export interface ReleaseManifest {
  app: string;
  versionCode: number;
  versionName: string;
  apkUrl: string;
  sha256: string;
  size: number;
  changelog?: string;
  publishedAt?: string;
}

/**
 * Liest die Release-Manifeste aus dem Downloads-Volume.
 *
 * Warum ueberhaupt: bis 2026-08 stand in `catalog.ts` hart, welche Plattform
 * verfuegbar ist. Die Kalender-APK lag seit dem 19. Juli ausgeliefert im Volume,
 * war im Portal aber als „bald" markiert, sie war gehostet und trotzdem
 * unsichtbar, weil niemand den Katalog nachgezogen hatte. Jetzt entscheidet das
 * vorhandene Artefakt, nicht eine zweite Liste.
 *
 * Fehlt das Verzeichnis (lokale Entwicklung), bleibt die Karte einfach leer:
 * die Seite muss auch ohne Downloads rendern.
 */
export const load: PageServerLoad = async () => {
  const releases: Record<string, ReleaseManifest> = {};
  try {
    const files = await readdir(DOWNLOADS_DIR);
    for (const file of files) {
      if (!file.endsWith('.json')) continue;
      try {
        const raw = await readFile(join(DOWNLOADS_DIR, file), 'utf-8');
        const manifest = JSON.parse(raw) as ReleaseManifest;
        if (manifest?.app && manifest?.versionName) releases[manifest.app] = manifest;
      } catch {
        // Ein kaputtes Manifest darf die ganze Seite nicht mitnehmen.
      }
    }
  } catch {
    // Kein Downloads-Volume gemountet.
  }
  return { releases };
};
