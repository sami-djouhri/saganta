<script lang="ts">
  import { zerlegen } from '$lib/hervorheben';

  let { text, begriffe }: { text: string; begriffe: string[] } = $props();

  let stuecke = $derived(zerlegen(text, begriffe));
</script>

<!-- Alles in einer Zeile: zwischen den Blöcken dürfen keine Leerzeichen
     entstehen, sonst zerreißt es Wörter mitten im Treffer. Die Farben stehen
     ausdrücklich dran, weil Browser <mark> sonst gelb mit schwarzer Schrift
     vorgeben, was im dunklen Design wie ein Fremdkörper wirkt. -->
{#each stuecke as stueck, i (i)}{#if stueck.treffer}<mark
      class="rounded-sm bg-accent-500/20 px-0.5 text-accent-300">{stueck.text}</mark
    >{:else}{stueck.text}{/if}{/each}
