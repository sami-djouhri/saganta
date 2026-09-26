/**
 * Der geöffnete Datenschlüssel, für die Dauer der Sitzung.
 *
 * ★★ Er liegt **nur im Arbeitsspeicher**. Nicht in `localStorage`, nicht in
 * `sessionStorage`, nicht in einem Cookie. Das ist die bewusste Entscheidung
 * dieser Datei, und sie kostet spürbaren Komfort: nach jedem Neuladen der Seite
 * (F5, neuer Tab, Browser-Neustart) ist die Passphrase erneut nötig.
 *
 * Warum trotzdem so: ein Schlüssel in `sessionStorage` ist für jedes Skript auf
 * dieser Seite lesbar und überlebt Reloads, ohne dass jemand ihn noch einmal
 * bewusst freigibt. Auf einem geteilten oder unbeaufsichtigten Rechner bliebe
 * das Tagebuch dann offen, obwohl es zugeklappt aussieht. Beim Blättern
 * zwischen Tagen entsteht kein Nachteil, denn SvelteKit navigiert im Client,
 * ohne die Seite neu zu laden.
 */
import type { TresorPakete } from './krypto';

interface Zustand {
  dek: CryptoKey | null;
  pakete: TresorPakete | null;
}

export const tresor = $state<Zustand>({ dek: null, pakete: null });

export function oeffnen(dek: CryptoKey, pakete: TresorPakete): void {
  tresor.dek = dek;
  tresor.pakete = pakete;
}

/** Zuklappen. Danach ist nichts mehr lesbar, ohne die Passphrase erneut einzugeben. */
export function schliessen(): void {
  tresor.dek = null;
  tresor.pakete = null;
}
