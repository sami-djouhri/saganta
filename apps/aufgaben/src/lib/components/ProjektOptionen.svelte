<script lang="ts">
  /**
   * Die Projekte als `<option>`-Liste, eingerueckt nach der Gliederung.
   *
   * Ein Projekt mit zwei Oberprojekten steht unter beiden (Entscheid
   * 15.11.), der Wert bleibt derselbe Slug. Vorausgewaehlt wird nur das erste
   * Auftreten: zwei `selected` im selben Feld nimmt der Browser beliebig.
   */
  import { eingerueckt, projektBaum } from '@saganta/ui';
  import type { Projekt } from '$lib/aufgaben-bff';
  import { alsBaum } from '$lib/projektfilter';

  interface Props {
    projekte: Projekt[];
    /** Vorbelegung als fertiger Wert (z. B. `projekt:<slug>`). */
    wert?: string;
    /** Wird vor den Slug gesetzt, z. B. `projekt:`. */
    praefix?: string;
    /** Slugs, die nicht angeboten werden (z. B. schon angeheftete). */
    ohne?: string[];
  }
  let { projekte, wert = '', praefix = '', ohne = [] }: Props = $props();

  const zeilen = $derived(projektBaum(alsBaum(projekte)).filter((z) => !ohne.includes(z.slug)));
</script>

{#each zeilen as z (z.schluessel)}
  <option value="{praefix}{z.slug}" selected={z.erstes && wert === `${praefix}${z.slug}`}>{eingerueckt(z)}</option>
{/each}
