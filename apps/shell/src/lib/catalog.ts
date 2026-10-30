// Öffentlicher Katalog für Nicht-Mitglieder: Plattform-Verfügbarkeit der Apps
// (Downloads). Bewusst statisch und ohne Backend, weil diese Seite public ist
// (siehe hooks.server.ts publicPaths) und auch ohne erreichbare shell-api/Auth
// rendern muss.
//
// Hier standen bis zum 2026-10-25 auch die Tarife: `plans` (Frei/Unlimited/
// Business), `appPlans` (jede App einzeln buchbar) und `compareRows`
// (Vergleichsmatrix). Sie sind mit der Seite `/preise` entfallen, weil Saganta
// seit dem Privat-Entscheid vom 21.10. kein Produkt mehr ist, das man bucht,
// sondern die private Suite des Owners und seiner Familie. Der Rückweg steht in
// der git-Historie, falls das Schaufenster auf netcup sie einmal braucht.

import { appUrl, appsFuer, type SagantaApp } from '@saganta/ui';

// ── Adressen der Installation ───────────────────────────────────────────────
//
// Hier stand bis zum 2026-10-25 `appAdresse()`, das die Adresse aus
// PUBLIC_SAGANTA_DOMAIN baute. Gemessen ergab das auf `/apps` sieben
// Browser-Knoepfe auf `*.saganta.de` -- also auf die Namen, die seit dem
// Privat-Entscheid vom 21.10. mit 404 antworten. Wer im Heimnetz auf „Browser"
// klickte, landete im Nichts, und die Seite sah dabei vollstaendig aus.
//
// Die Adresse entsteht jetzt im **Raum des Aufrufers** (`appUrl` aus
// `@saganta/ui`), genau wie im App-Wechsler und bei der Anmeldeadresse. Eine
// feste Domaene in einer Umgebungsvariablen ist eine zweite Wahrheit neben dem
// Host, unter dem die Seite gerade beantwortet wird, und sie veraltet still.

// ── Downloads (Proton-Stil) ──────────────────────────────────────────────────

export type Platform = 'web' | 'android' | 'windows' | 'linux';

export interface PlatformInfo {
  id: Platform;
  label: string;
  icon: string;
}

export const platforms: PlatformInfo[] = [
  { id: 'web', label: 'Browser', icon: 'globe' },
  { id: 'android', label: 'Android', icon: 'smartphone' },
  { id: 'linux', label: 'Linux', icon: 'monitor' },
  { id: 'windows', label: 'Windows', icon: 'monitor' },
];

/**
 * Plattformen, deren Knopf aus einem ausgelieferten Artefakt entsteht.
 *
 * Was hier steht, entscheidet NICHT diese Datei, sondern das
 * Downloads-Volume: liegt dort ein Manifest, ist der Knopf da. Alles andere
 * bleibt „bald". Windows fehlt bewusst: die Gradle-Module koennen `.msi`, aber
 * das baut nur auf Windows (Entscheid 2026-10-25: erst mal nicht).
 */
export const artefaktPlattformen: Platform[] = ['android', 'linux'];

export type DownloadStatus = 'available' | 'soon';

export interface AppDownload {
  /** Kennung im App-Katalog (`packages/ui/src/apps.ts`). */
  id: string;
  /** Name des Release-Artefakts im Downloads-Volume. */
  release: string;
  name: string;
  description: string;
  icon: string;
  /** Adresse der Browser-Fassung im Raum des Aufrufers. */
  web: string;
}

// Diese Liste war bis zum 2026-10-25 von Hand gefuehrt und damit eine
// zweite Wahrheit neben `packages/ui/src/apps.ts`. Sie war in beide Richtungen
// falsch: `aufgaben`, `tagebuch` und `assets` hatten ueberhaupt keine Karte,
// obwohl sie seit Wochen laufen, und `kontakte` hatte eine, obwohl es keine
// eigene App ist (Kontakte sind ein Teil des Kalenders). Genau dasselbe Muster
// wie die Kalender-APK, die ab dem 19.07.2026 ausgeliefert im Volume lag und
// hier monatelang auf 'soon' stand, also unsichtbar war.
//
// Jetzt kommt die Liste aus dem Katalog (`appsFuer` filtert die heim-only-Apps
// im oeffentlichen Raum heraus) und die Plattform-Knoepfe aus dem
// Downloads-Volume. Beides entscheidet nicht mehr diese Datei. Eine neue App
// erscheint ohne Zutun, ein neues Artefakt ebenso.
//
// Release-Schritte:
//   Android  saganta-android/release.sh <app> <apk> <code> <name>
//   Linux    saganta-apps/packaging/arch/ausliefern.sh <app>
// Gegenprobe, dass kein Artefakt unsichtbar bleibt:
//   saganta/scripts/downloads-abgleich.py

/**
 * Laengerer Text je App fuer die Download-Seite.
 *
 * Bewusst ein Zusatz und keine zweite Liste: fehlt ein Eintrag, gilt die
 * Beschreibung aus dem App-Katalog. Eine neue App ist damit sofort sichtbar,
 * nur knapper beschrieben -- und nicht erst dann, wenn jemand hier nachtraegt.
 */
const ZUSATZTEXT: Record<string, string> = {
  calendar:
    'Termine, Aufgaben, Tagesziele und Schichtplanung. Geburtstage als Overlay aus den Kontakten.',
  aufgaben: 'Aufgaben, Tagesziele und der geplante Tag, verknüpft mit Projekten und Notizen.',
  notizen:
    'Notizbücher mit Markdown, verknüpft mit Terminen, Aufgaben und Projekten. Freigaben für einzelne Notizen.',
  post: 'Physische Briefe (Scan, OCR, Ablage) und alle E-Mail-Konten, gebündelt in einer Inbox.',
  news: 'Feeds, Trends und Lesezeichen pro Profil, ohne Algorithmus-Rauschen.',
  projectdeck: 'Projekte, Entscheidungen und Fristen. Die ruhige Kommandozentrale.',
  tagebuch:
    'Tageseinträge, im Browser verschlüsselt. Der Server verwahrt nur das Chiffrat, es gibt keine Suche darin.',
  assets: 'Geräte, Garantien und Marktwerte. Wertsachen und Elektronik mit Zeitwert.',
  fitness: 'Training, Fortschritt und Ziele. Koppelt Makros und Energiebedarf mit Mealprep.',
  mealprep: 'Rezepte, Wochenplan und Makros. Erzeugt die Einkaufsliste aus Plan und Lagerbestand.',
  lager: 'Haushaltsinventar mit FIFO, Mindestbestand und Barcode.',
};

/**
 * Kennung im App-Katalog -> Name des Release-Artefakts.
 *
 * ⚠️ Es gibt genau eine Abweichung, und sie ist eine Falle: die App heisst im
 * Katalog `calendar` (weil der Heim-Vhost so heisst), das Gradle-Modul und
 * damit `kalender.json` im Volume heissen `kalender`. Ohne diese Zuordnung
 * bliebe die ausgelieferte Kalender-APK unsichtbar, und zwar wortlos -- der
 * genaue Fehler, den die Seite 2026-08 schon einmal hatte.
 *
 * Dass die Zuordnung vollstaendig ist, prueft `scripts/downloads-abgleich.py`
 * gegen das Volume: ein Manifest ohne Karte ist dort ein Befund.
 */
const RELEASE_NAME: Record<string, string> = { calendar: 'kalender' };

/** Name, unter dem die Artefakte dieser App im Downloads-Volume liegen. */
export function releaseNameFuer(id: string): string {
  return RELEASE_NAME[id] ?? id;
}

/**
 * Die Apps der Download-Seite im Raum des aufrufenden Hosts.
 *
 * `shell` faellt heraus: die Uebersicht ist die Seite selbst, kein Download.
 */
export function downloadsFuer(host: string | null | undefined): AppDownload[] {
  return appsFuer(host)
    .filter((app: SagantaApp) => app.id !== 'shell')
    .map((app: SagantaApp) => ({
      id: app.id,
      release: releaseNameFuer(app.id),
      name: app.name,
      description: ZUSATZTEXT[app.id] ?? app.description,
      icon: app.icon,
      web: appUrl(app, host),
    }));
}
