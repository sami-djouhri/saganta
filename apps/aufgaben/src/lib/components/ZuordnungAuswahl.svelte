<script lang="ts">
  /**
   * Ein Feld fuer „wohin gehoert die Aufgabe": Bereich (Liste) oder Projekt.
   *
   * Ein Feld statt zwei, weil der Dienst beides zugleich ablehnt. Der Wert
   * ist `liste:<id>` oder `projekt:<slug>`, uebersetzt in `zuordnung.ts`.
   * Bereiche stehen zuerst: sie sind fuer das Eigene, Projekte haben ihre
   * eigene Flaeche im ProjectDeck.
   */
  import type { Liste, Projekt } from '$lib/aufgaben-bff';
  import ProjektOptionen from './ProjektOptionen.svelte';

  interface Props {
    listen: Liste[];
    projekte: Projekt[];
    /** Vorbelegung, z. B. aus `zuordnungVon(aufgabe)`. */
    wert?: string;
    leer?: string;
    klasse?: string;
  }
  let { listen, projekte, wert = '', leer = 'nicht zugeordnet', klasse = '' }: Props = $props();
</script>

<select name="zuordnung" class={klasse}>
  <option value="">{leer}</option>
  {#if listen.length > 0}
    <optgroup label="Bereiche">
      {#each listen as l (l.id)}
        <option value="liste:{l.id}" selected={wert === `liste:${l.id}`}>{l.name}</option>
      {/each}
    </optgroup>
  {/if}
  {#if projekte.length > 0}
    <optgroup label="Projekte">
      <ProjektOptionen {projekte} {wert} praefix="projekt:" />
    </optgroup>
  {/if}
</select>
