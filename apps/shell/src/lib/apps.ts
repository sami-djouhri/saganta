/**
 * Der resiliente Fallback des Launchpads: die App-Liste, wenn `shell-api` beim
 * Rendern nicht erreichbar war. Ohne ihn strandet ein Nutzer auf einem leeren
 * Dashboard, obwohl jede App fuer sich laeuft.
 *
 * ★★ **Das ist keine eigene Liste mehr.** Bis 2026-09-13 stand hier eine dritte
 * handgepflegte Kopie desselben Katalogs, neben `packages/ui/src/apps.ts` und
 * `services/shell-api/app/registry.py`. Drei Kopien, drei Staende: der Fallback
 * kannte `assets` nicht, das UI-Paket kannte `notizen` und `tagebuch` nicht,
 * und alle drei trugen `projectdeck.saganta.de` als Adresse, die es nicht gibt.
 *
 * Jetzt leitet der Fallback aus dem geteilten Katalog ab. Die Registry im
 * Backend bleibt die autoritative Quelle (sie traegt zusaetzlich Pinning), aber
 * beide beschreiben dieselben Apps, und eine neue App faellt nicht mehr aus
 * einer der Listen heraus.
 */
import { appUrl, appsFuer } from '@saganta/ui';

export interface SagantaApp {
  id: string;
  name: string;
  description: string;
  icon: string;
  href: string;
  /** Tags steuern Sortierung und Filter im Launchpad. */
  tags: ('core' | 'productivity' | 'admin')[];
}

/**
 * Die Apps des Raums, in dem diese Anfrage ankam.
 *
 * Ohne `host` gilt der oeffentliche Raum. Die Shell selbst ist ausgenommen: von
 * ihr aus zeigt man nicht auf sie selbst.
 */
export function appsFallback(host?: string | null): SagantaApp[] {
  return appsFuer(host)
    .filter((a) => a.id !== 'shell')
    .map((a) => ({
      id: a.id,
      name: a.name,
      description: a.description,
      icon: a.icon,
      href: appUrl(a, host),
      tags: a.tags,
    }));
}

/** Rueckfall ohne Host-Kenntnis (oeffentlicher Raum). */
export const apps: SagantaApp[] = appsFallback(null);
