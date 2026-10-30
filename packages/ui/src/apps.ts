/**
 * Kanonischer Saganta-App-Katalog: die EINE geteilte Quelle für App-Navigation
 * (AppSwitcher in der TopBar + ⌘K-CommandPalette in allen Apps). Statisch und
 * dependency-frei, damit jede Sub-App den Switcher ohne shell-api-Call rendern
 * kann (resilient). Die Shell überlagert diese Liste zur Laufzeit mit /api/apps
 * (Pinning/Badges); für den Switcher reicht die statische Liste.
 *
 * `id` ist stabil und dient als `currentAppId` zum Hervorheben der aktiven App.
 *
 * **Die Adressen stehen hier NICHT mehr als fertige `.de`-URLs.** Bis
 * 2026-09-13 taten sie das, und der App-Wechsler schickte damit jeden auf
 * `saganta.de` zurück, egal von wo er kam. Zwei Folgen, beide gemessen:
 *
 *  1. `projectdeck.saganta.de` **existiert überhaupt nicht** (kein DNS-Eintrag,
 *     kein cloudflared-Ingress, kein Vhost). Der Eintrag im Wechsler führte seit
 *     jeher ins Leere, ebenso der Link, den die Notizen auf ein verknüpftes
 *     Projekt setzen.
 *  2. Wer unter `*.home.arpa` arbeitete, wurde vom Wechsler aus dem Heimnetz
 *     heraus durch den Tunnel geschickt: anderer Cookie-Raum, also im Zweifel
 *     eine neue Anmeldung für einen Dienst, der eine Tür weiter stand.
 *
 * Stattdessen beschreibt jede App nur noch **ihre Subdomain**, und die Adresse
 * entsteht im Raum des aufrufenden Hosts (`appUrl`). Dieselbe Regel, nach der
 * `packages/auth` schon die Anmeldeadresse wählt: die Suite bleibt in dem Raum,
 * in dem man sie betreten hat. Ein neuer Raum (Demo-Instanz, Kundeninstanz)
 * braucht damit keine Code-Änderung mehr.
 */
export type SagantaRaum = string;

export interface SagantaApp {
  id: string;
  name: string;
  description: string;
  icon: string;
  /**
   * Subdomain im öffentlichen Raum. Leer = Wurzel der Domain (die Shell liegt
   * auf `saganta.de` selbst, nicht auf `shell.saganta.de`).
   */
  sub: string;
  /**
   * Abweichende Subdomain im Heim-Raum. Nur dort gesetzt, wo die Namen
   * auseinanderlaufen.
   *
   * ⚠️ Der Kalender ist der eine echte Fall: öffentlich `kalender.saganta.de`,
   * im Heimnetz `calendar.home.arpa`. Ein Vertipper trifft dort den
   * `default_server` des tardis und landet auf einer fremden Anmeldemaske,
   * was wie ein Rechteproblem aussieht. Der Unterschied ist deshalb hier
   * hinterlegt statt in jedem Aufrufer.
   */
  subHeim?: string;
  /**
   * App existiert nur im Heim-Raum (bewusst nicht im Tunnel). Im öffentlichen
   * Raum wird sie ausgeblendet, statt einen toten Eintrag zu zeigen.
   */
  nurHeim?: boolean;
  /**
   * Signaturlinie der App: das Muster des 2-px-Bandes unter der Kopfleiste.
   *
   * Warum ein Muster und keine Farbe. Die Suite soll sich als EINE Anwendung
   * anfuehlen und trotzdem erkennen lassen, wo man ist. Eine Hausfarbe je App
   * waere der naheliegende Weg und der falsche: im Saganta-Farbsystem traegt
   * Buntfarbe Bedeutung (Erfolg, Hinweis, Warnung, Fehler), und eine neunte,
   * zehnte Marke daneben nimmt genau dieser Bedeutung die Eindeutigkeit. Ein
   * Strichrhythmus konkurriert mit nichts, bleibt im Hochkontrast-Theme
   * erhalten und ist auch dann noch da, wenn jemand Farben nicht unterscheidet.
   *
   * Der Rhythmus kommt aus der Sache: der Kalender bekommt Taktstriche, die
   * Aufgaben eine Haekchenreihe, die Notizen die enge Linierung von Papier,
   * die Post eine Perforation wie ein Briefmarkenrand, das Tagebuch eine
   * unterbrochene Punktreihe. Gezeichnet wird in `currentColor`, gesetzt wird
   * `--color-border-stark`; das Band traegt damit in jedem Theme.
   */
  signatur: string;
  tags: ('core' | 'productivity' | 'admin')[];
}

/** Durchgehende Linie: die Vorgabe, wenn eine App keine eigene Signatur hat. */
export const SIGNATUR_DURCHGEHEND = 'linear-gradient(currentColor, currentColor)';

/** Signaturmuster einer App-Kennung, mit Rueckfall auf die durchgehende Linie. */
export function signaturFuer(id: string | undefined): string {
  if (!id) return SIGNATUR_DURCHGEHEND;
  return SAGANTA_APPS.find((a) => a.id === id)?.signatur ?? SIGNATUR_DURCHGEHEND;
}

/** Der öffentliche Raum. Rückfall, solange kein Host bekannt ist. */
export const STANDARD_RAUM = 'saganta.de';

/** Die Shell im öffentlichen Raum. Rückfall für Aufrufer ohne Host-Kenntnis. */
export const SHELL_URL = `https://${STANDARD_RAUM}`;

export const SAGANTA_APPS: SagantaApp[] = [
  {
    id: 'shell',
    name: 'Übersicht',
    description: 'Launchpad: alle Apps auf einen Blick.',
    sub: '',
    subHeim: 'shell',
    icon: 'layout-grid',
    // Durchgehend: die Uebersicht ist der Grund, auf dem alles liegt.
    signatur: SIGNATUR_DURCHGEHEND,
    tags: ['core'],
  },
  {
    id: 'calendar',
    name: 'Kalender',
    description: 'Termine, Tagestypen, Gewohnheiten.',
    sub: 'kalender',
    subHeim: 'calendar',
    icon: 'calendar',
    // Duennes Taktzeichen im weiten Abstand, das Raster einer Woche.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 2px, transparent 2px 13px)',
    tags: ['core', 'productivity'],
  },
  {
    id: 'aufgaben',
    name: 'Aufgaben',
    description: 'Aufgaben, Tagesziele und der geplante Tag. Verknüpft mit Projekten und Notizen.',
    sub: 'aufgaben',
    // Heim-only, Entscheid 2026-10-16: `aufgaben.saganta.de` hat kein
    // DNS, keine Tunnel-Regel und keinen Vhost (gemessen NXDOMAIN).
    nurHeim: true,
    icon: 'list-todo',
    // Gleich lange Striche mit gleich langer Luecke, eine Liste Punkt fuer Punkt.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 7px, transparent 7px 12px)',
    tags: ['core', 'productivity'],
  },
  {
    id: 'notizen',
    name: 'Notizen',
    description: 'Notizbücher, Anhänge, geteilte Notizen.',
    sub: 'notizen',
    // Heim-only, Entscheid 2026-10-16. Der nginx-Vhost fuer
    // `notizen.saganta.de` ist fertig gebaut, es fehlen nur DNS und
    // Tunnel-Regel -- ein halb fertiger Weg, der bei einem spaeteren CNAME
    // unbemerkt scharf wuerde.
    nurHeim: true,
    icon: 'file-text',
    // Fast durchgehend, nur leicht unterbrochen: die Linierung von Papier.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 15px, transparent 15px 18px)',
    tags: ['core', 'productivity'],
  },
  {
    id: 'post',
    name: 'Post',
    description: 'E-Mails und Briefe in einer Inbox. Konten, Briefkasten, Verträge und Fristen.',
    sub: 'post',
    icon: 'inbox',
    // Dichteste Lochung, der Rand einer Briefmarke.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 2px, transparent 2px 5px)',
    tags: ['core', 'productivity'],
  },
  {
    id: 'news',
    name: 'News',
    description: 'Nachrichtenquellen und das persönliche Briefing.',
    sub: 'news',
    icon: 'newspaper',
    // Lange Balken mit weiter Luecke, die Spaltenlinie einer Zeitung.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 30px, transparent 30px 40px)',
    tags: ['core'],
  },
  {
    id: 'projectdeck',
    name: 'ProjectDeck',
    description: 'Projekte, Entscheidungen, Portfolio.',
    sub: 'projectdeck',
    // Heim-only, Entscheid 2026-10-16. Diese Kachel war der Anlass
    // fuer den Umbau vom 13.09.; behoben wurde damals nur die Heim-Seite.
    nurHeim: true,
    icon: 'layout-dashboard',
    // Lang, dann kurz: eine Zeitachse mit Zwischenmarken.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 20px, transparent 20px 26px, currentColor 26px 29px, transparent 29px 35px)',
    tags: ['core', 'productivity'],
  },
  {
    id: 'tagebuch',
    name: 'Tagebuch',
    // Bewusst ohne Tunnel (`exposure: local_only`): ein Tagebuch soll nicht ohne
    // Not öffentlich stehen. Im öffentlichen Raum deshalb gar nicht erst zeigen.
    description: 'Tageseinträge, im Browser verschlüsselt. Nur im Heimnetz.',
    sub: 'tagebuch',
    nurHeim: true,
    icon: 'book',
    // Kaum etwas, weit auseinander: da steht etwas, aber nicht zu lesen.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 1px, transparent 1px 15px)',
    tags: ['core'],
  },
  {
    id: 'assets',
    name: 'Besitz',
    description: 'Geräte, Garantien, Marktwerte.',
    sub: 'assets',
    icon: 'box',
    // Kurze Marken in gleichem Abstand, eine Reihe Inventaretiketten.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 3px, transparent 3px 11px)',
    tags: ['productivity'],
  },
  {
    id: 'fitness',
    name: 'Fitness',
    description: 'Trainingspläne und erfasste Sätze.',
    sub: 'fitness',
    icon: 'dumbbell',
    // Ein langer Satz, eine kurze Wiederholung, dann Pause.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 16px, transparent 16px 20px, currentColor 20px 24px, transparent 24px 34px)',
    tags: ['productivity'],
  },
  {
    id: 'mealprep',
    name: 'MealPrep',
    description: 'Rezepte und Wochenplanung.',
    sub: 'mealprep',
    icon: 'utensils',
    // Zwei gleiche Portionen, dann Abstand bis zum naechsten Tag.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 5px, transparent 5px 8px, currentColor 8px 13px, transparent 13px 24px)',
    tags: ['productivity'],
  },
  {
    id: 'lager',
    name: 'Lager',
    description: 'Vorräte und Bestände.',
    sub: 'lager',
    icon: 'archive',
    // Gleich breite Faecher, gleich breite Zwischenraeume.
    signatur: 'repeating-linear-gradient(90deg, currentColor 0 11px, transparent 11px 22px)',
    tags: ['productivity'],
  },
];

/**
 * Der Raum eines Hosts: die letzten beiden Labels, also `home.arpa` aus
 * `notizen.home.arpa`.
 *
 * Bewusst rein syntaktisch und ohne Liste erlaubter Domänen. Der Wert wird nur
 * benutzt, um **eigene** Geschwister-Adressen zu bilden; er entscheidet nichts
 * über Vertrauen. Was Vertrauen betrifft (Cookie-Domain, erlaubtes `next`),
 * liegt in `packages/auth` und prüft dort gegen eine eigene Liste.
 *
 * Ein Host ohne Punkt (`localhost`) und ein leerer Wert ergeben `null`, der
 * Aufrufer fällt dann auf den öffentlichen Raum zurück.
 */
export function raumVon(host: string | null | undefined): SagantaRaum | null {
  if (!host) return null;
  // Port abschneiden, IPv6-Klammern entfernen.
  const name = host.replace(/^\[|\]$/g, '').replace(/:\d+$/, '').toLowerCase();
  // Eine nackte IP-Adresse hat keinen Raum: aus ihr lassen sich keine
  // Geschwister-Namen bilden, und ein zusammengesetzter Name wäre geraten.
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(name) || name.includes(':')) return null;
  const teile = name.split('.').filter(Boolean);
  if (teile.length < 2) return null;
  return teile.slice(-2).join('.');
}

/** Ist das der Heim-Raum? Dort gelten `subHeim` und `nurHeim`. */
export function istHeimRaum(raum: SagantaRaum | null | undefined): boolean {
  return !!raum && raum.endsWith('.home');
}

/**
 * Adresse einer App im Raum des aufrufenden Hosts.
 *
 * `host` ist der Host der laufenden Anfrage (`page.url.host`), nicht der Ziel-
 * Host. Fehlt er, gilt der öffentliche Raum: das ist das Verhalten von vor
 * 2026-09-13 und damit ein Rückfall, der nichts schlimmer macht.
 */
export function appUrl(app: SagantaApp, host?: string | null): string {
  const raum = raumVon(host) ?? STANDARD_RAUM;
  const sub = istHeimRaum(raum) ? (app.subHeim ?? app.sub) : app.sub;
  return sub ? `https://${sub}.${raum}` : `https://${raum}`;
}

/** Adresse einer App über ihre `id`. Unbekannte `id` ergibt die Shell. */
export function appUrlById(id: string, host?: string | null): string {
  const app = SAGANTA_APPS.find((a) => a.id === id);
  if (!app) {
    const raum = raumVon(host) ?? STANDARD_RAUM;
    return istHeimRaum(raum) ? `https://shell.${raum}` : `https://${raum}`;
  }
  return appUrl(app, host);
}

/**
 * Die Apps, die es im Raum dieses Hosts wirklich gibt.
 *
 * Ein Eintrag, hinter dem nichts steht, ist schlimmer als ein fehlender: er
 * sieht aus wie ein kaputter Dienst, und man sucht den Fehler an der falschen
 * Stelle.
 */
export function appsFuer(host?: string | null): SagantaApp[] {
  const heim = istHeimRaum(raumVon(host) ?? STANDARD_RAUM);
  return SAGANTA_APPS.filter((a) => heim || !a.nurHeim);
}

/** Command-Palette-Einträge für App-Navigation, aus dem geteilten Katalog.
 * Die aktive App wird ausgelassen (man springt nicht zu sich selbst). */
export interface AppCommand {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

export function buildAppCommands(currentAppId?: string, host?: string | null): AppCommand[] {
  return [
    ...appsFuer(host)
      .filter((a) => a.id !== currentAppId)
      .map((a) => ({
        id: `app-${a.id}`,
        label: `Öffnen: ${a.name}`,
        hint: a.id === 'shell' ? 'Übersicht' : undefined,
        run: () => {
          window.location.href = appUrl(a, host);
        },
      })),
    // Die Downloads waren aus einer angemeldeten Sitzung nur ueber einen einzigen,
    // versteckten Weg erreichbar (Konto-Menue der Shell). Die Palette liegt in jeder
    // App auf demselben Kuerzel und kostet nichts.
    {
      id: 'nav-downloads',
      label: 'Apps & Downloads',
      hint: 'Android',
      run: () => {
        window.location.href = `${appUrlById('shell', host)}/apps`;
      },
    },
  ];
}
