// Öffentlicher Marketing-Katalog für Nicht-Mitglieder: Tarife (Pricing) und
// Plattform-Verfügbarkeit (Downloads). Bewusst statisch und ohne Backend, weil
// diese Seiten public sind (siehe hooks.server.ts publicPaths) und auch ohne
// erreichbare shell-api/Auth rendern müssen. Preise/Plattformen hier pflegen.
//
// Produktlogik (Proton-Stil):
//  - Jede verkaufbare App ist eine eigene SKU (einzeln buchbar, siehe appPlans).
//  - "Saganta Unlimited" bündelt alle Apps vergünstigt (der naheliegende Upsell,
//    weil die Apps sich gegenseitig verstärken).
//  - "Business" ist die Mehrnutzer-/ERP-Variante (Lager als kleines ERP).
//  - Einkaufsliste und Geburtstags-Overlay sind kostenlose Kleber-Features
//    (keine eigene SKU), in jedem Plan enthalten.

import { env } from '$env/dynamic/public';

// ── Adressen der Installation ───────────────────────────────────────────────
//
// ★ Die Domaene stand bis zum 2026-09-06 an 17 Stellen fest im Quelltext
// ("saganta.de"). Fuer eine selbst betriebene Installation waren das lauter
// tote Links auf eine fremde Instanz. Sie kommt jetzt aus
// PUBLIC_SAGANTA_DOMAIN.
//
// Ohne konfigurierte Domaene bleibt der Link LEER statt auf die fremde Instanz
// zu zeigen. Die Oberflaeche prueft ohnehin `status === 'available' && t.href`
// und laesst den Eintrag dann unverlinkt, was genau richtig ist: nicht
// konfiguriert heisst nicht erreichbar.
const DOMAENE = env.PUBLIC_SAGANTA_DOMAIN ?? '';

/** `https://<unterdomaene>.<domaene>`, oder leer ohne konfigurierte Domaene. */
export function appAdresse(unterdomaene: string): string {
  return DOMAENE ? `https://${unterdomaene}.${DOMAENE}` : '';
}

/** Kontaktadresse der Installation; leer, wenn keine konfiguriert ist. */
export const kontaktAdresse = env.PUBLIC_SAGANTA_KONTAKT ?? '';

export type Audience = 'personal' | 'business';

// ── Haupt-Tarife ────────────────────────────────────────────────────────────

export interface Plan {
  id: string;
  audience: Audience;
  name: string;
  tagline: string;
  /** Preis pro Monat in EUR; null = kostenlos, undefined = „auf Anfrage". */
  priceMonthly: number | null | undefined;
  /** Optionaler Jahrespreis pro Monat (bei jährlicher Zahlung). */
  priceYearly?: number;
  priceNote?: string;
  cta: { label: string; href: string };
  highlight?: boolean;
  features: string[];
}

export const plans: Plan[] = [
  {
    id: 'free',
    audience: 'personal',
    name: 'Frei',
    tagline: 'Der Einstieg in die Suite, dauerhaft kostenlos.',
    priceMonthly: null,
    priceNote: 'Dauerhaft kostenlos',
    cta: { label: 'Kostenlos starten', href: '/login?mode=register' },
    features: [
      'Kalender, Kontakte und News',
      'Einkaufsliste und Geburtstage inklusive',
      '1 GB verschlüsselter Speicher',
      'Browser- und Android-Apps',
      'Ende-zu-Ende privat, kein Tracking',
      'Keine Werbung, kein Datenverkauf',
    ],
  },
  {
    id: 'unlimited',
    audience: 'personal',
    name: 'Unlimited',
    tagline: 'Alle Apps in einem Tarif, deutlich günstiger als einzeln.',
    priceMonthly: 9,
    priceYearly: 7,
    priceNote: 'pro Monat · jährlich 84 €',
    cta: { label: 'Unlimited holen', href: '/login?mode=register&plan=unlimited' },
    highlight: true,
    features: [
      'Alle Apps, alle Funktionen',
      'Post: Briefe und alle Mailkonten',
      'Mealprep und Lager voll verzahnt',
      '500 GB verschlüsselter Speicher',
      'OCR und KI-Ablage ohne Limit',
      'Priorisierter Support',
    ],
  },
  {
    id: 'business',
    audience: 'business',
    name: 'Business',
    tagline: 'Mehrnutzer und kleines ERP für Familien und Firmen.',
    priceMonthly: undefined,
    priceNote: 'Individuell',
    cta: { label: 'Kontakt aufnehmen', href: kontaktAdresse ? `mailto:${kontaktAdresse}?subject=Saganta%20Business` : '' },
    features: [
      'Alle Apps für mehrere Nutzer',
      'Lager als ERP: Lieferanten, Bestellungen, Rollen',
      'Geteilte Kalender und Kontakte',
      'Zentrale Nutzerverwaltung',
      'Self-Hosting und eigene Domain',
      'SLA und dedizierter Support',
    ],
  },
];

// ── Einzeln buchbare Apps (Proton-Stil: pick what you need) ──────────────────

export interface AppPlan {
  id: string;
  name: string;
  icon: string;
  description: string;
  /** Preis pro Monat in EUR bei Einzelbuchung. */
  priceMonthly: number;
}

export const appPlans: AppPlan[] = [
  { id: 'kalender', name: 'Kalender', icon: 'calendar', description: 'Termine, Tagesziele, Geburtstags-Overlay.', priceMonthly: 2 },
  { id: 'post', name: 'Post', icon: 'mail', description: 'Briefe mit OCR und alle Mailkonten gebündelt.', priceMonthly: 3 },
  { id: 'mealprep', name: 'Mealprep', icon: 'utensils', description: 'Rezepte, Wochenplan und Makro-Tracking.', priceMonthly: 3 },
  { id: 'lager', name: 'Lager', icon: 'box', description: 'Haushaltsinventar inklusive Wertsachen und Elektronik.', priceMonthly: 3 },
  { id: 'kontakte', name: 'Kontakte', icon: 'users', description: 'Privates Adressbuch, Quelle für Geburtstage und Absender.', priceMonthly: 2 },
  { id: 'news', name: 'News', icon: 'newspaper', description: 'Feeds, Trends und Bookmarks ohne Algorithmus-Rauschen.', priceMonthly: 2 },
  { id: 'projectdeck', name: 'ProjectDeck', icon: 'layout-dashboard', description: 'Projekte, Entscheidungen und Deadlines.', priceMonthly: 2 },
  { id: 'fitness', name: 'Fitness', icon: 'dumbbell', description: 'Training, Fortschritt und Ziele, gekoppelt an Mealprep.', priceMonthly: 2 },
];

// ── Vergleichsmatrix (Free / Unlimited / Business) ───────────────────────────

export interface CompareRow {
  label: string;
  values: Record<string, string | boolean>;
}

export const compareRows: CompareRow[] = [
  { label: 'Enthaltene Apps', values: { free: '3 Basis-Apps', unlimited: 'Alle Apps', business: 'Alle + ERP' } },
  { label: 'Browser-Apps', values: { free: true, unlimited: true, business: true } },
  { label: 'Android-Apps', values: { free: true, unlimited: true, business: true } },
  { label: 'Desktop (Windows/Linux)', values: { free: true, unlimited: true, business: true } },
  { label: 'Einkaufsliste und Geburtstage', values: { free: true, unlimited: true, business: true } },
  { label: 'Speicher', values: { free: '1 GB', unlimited: '500 GB', business: 'Individuell' } },
  { label: 'Post: OCR und KI-Ablage', values: { free: false, unlimited: true, business: true } },
  { label: 'Mealprep und Lager verzahnt', values: { free: false, unlimited: true, business: true } },
  { label: 'Mehrere Nutzer', values: { free: false, unlimited: false, business: true } },
  { label: 'Lager als ERP (Lieferanten/Bestellungen)', values: { free: false, unlimited: false, business: true } },
  { label: 'Self-Hosting und eigene Domain', values: { free: false, unlimited: false, business: true } },
];

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
  { id: 'windows', label: 'Windows', icon: 'monitor' },
  { id: 'linux', label: 'Linux', icon: 'monitor' },
];

export type DownloadStatus = 'available' | 'soon' | 'web-only';

export interface AppDownload {
  id: string;
  name: string;
  description: string;
  icon: string;
  targets: Partial<Record<Platform, { href?: string; status: DownloadStatus }>>;
}

// Finale App-Linie. Assets ist in Lager gefaltet (war nur eine lager.electronics-Sicht).
// Einkaufsliste und Geburtstage sind Kleber-Features, keine eigenständigen Downloads.
// APK-Hosting: native Saganta-Apps (Memory project_saganta_native_android).
//
// Release-Schritt ist NUR `saganta-android/release.sh <app> <apk> <code> <name>`.
// Das legt APK + `<app>.json` ins Downloads-Volume (`../downloads`, read-only in die
// Shell gemountet, NICHT `static/downloads/`, das war der alte Weg). Die Seite
// /apps liest die Manifeste serverseitig und schaltet Android selbst frei.
//
// Das `android`-Target unten ist damit nur noch der Fallback, wenn (noch) kein
// Artefakt existiert. Vorher musste man es von Hand nachziehen, und genau das
// wurde vergessen: die Kalender-APK lag ab dem 19.07.2026 ausgeliefert im Volume
// und stand hier trotzdem monatelang auf 'soon', also unsichtbar.
export const downloads: AppDownload[] = [
  {
    id: 'kalender',
    name: 'Kalender',
    description: 'Termine, Tasks, Tagesziele und Schichtplanung. Geburtstage als Overlay aus Kontakten.',
    icon: 'calendar',
    targets: {
      web: { href: appAdresse('kalender'), status: 'available' },
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'post',
    name: 'Post',
    description: 'Physische Briefe (Scan, OCR, KI-Ablage) und alle E-Mail-Konten, gebündelt in einer Inbox.',
    icon: 'mail',
    targets: {
      web: { href: appAdresse('post'), status: 'available' },
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'mealprep',
    name: 'Mealprep',
    description: 'Rezepte, Wochenplan und Makro-Tracking. Erzeugt die Einkaufsliste aus Plan und Lagerbestand.',
    icon: 'utensils',
    targets: {
      web: { href: appAdresse('mealprep'), status: 'available' },
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'lager',
    name: 'Lager',
    description: 'Haushaltsinventar mit FIFO, Mindestbestand und Barcode. Wertsachen und Elektronik mit Marktwert.',
    icon: 'box',
    targets: {
      web: { href: appAdresse('lager'), status: 'available' },
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'kontakte',
    name: 'Kontakte',
    description: 'Privates Adressbuch ohne fremde Cloud. Speist Geburtstage in den Kalender und Absender in die Post.',
    icon: 'users',
    targets: {
      web: { href: appAdresse('kontakte'), status: 'soon' },
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'news',
    name: 'News',
    description: 'Feeds, Trending und Bookmarks pro Profil, ohne Algorithmus-Rauschen.',
    icon: 'newspaper',
    targets: {
      web: { href: appAdresse('news'), status: 'available' },
      // Android folgt (gleicher Weg wie projectdeck: build-remote.sh → release.sh);
      // bis dahin 'soon' statt totem Link auf eine nicht mehr gehostete Alt-APK.
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'projectdeck',
    name: 'ProjectDeck',
    description: 'Projekte, Entscheidungen und Deadlines. Die ruhige Kommandozentrale.',
    icon: 'layout-dashboard',
    targets: {
      web: { href: appAdresse('projectdeck'), status: 'soon' },
      android: { href: '/downloads/saganta-projectdeck.apk', status: 'available' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'fitness',
    name: 'Fitness',
    description: 'Training, Fortschritt und Ziele. Koppelt Makros und Energiebedarf mit Mealprep.',
    icon: 'dumbbell',
    targets: {
      web: { href: appAdresse('fitness'), status: 'available' },
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
  {
    id: 'notizen',
    name: 'Notizen',
    description:
      'Notizbücher mit Markdown, verknüpft mit Terminen, Aufgaben und Projekten. Freigaben für einzelne Notizen.',
    icon: 'file-text',
    targets: {
      web: { href: appAdresse('notizen'), status: 'available' },
      android: { status: 'soon' },
      windows: { status: 'soon' },
      linux: { status: 'soon' },
    },
  },
];
