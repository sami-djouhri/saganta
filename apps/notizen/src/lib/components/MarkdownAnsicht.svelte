<script lang="ts">
  import { rendern } from '$lib/markdown';

  let { quelle = '', klasse = '' }: { quelle?: string; klasse?: string } = $props();

  let ziel = $state<HTMLDivElement | null>(null);

  // Gerendert wird ins DOM, nicht als HTML-Zeichenkette gesetzt. Deshalb hier
  // ein Effekt statt {@html …}: `rendern` liefert fertige Knoten, und genau das
  // ist der Grund, warum aus fremdem Text kein Markup werden kann.
  $effect(() => {
    const inhalt = quelle;
    if (!ziel) return;
    ziel.replaceChildren(rendern(inhalt));
  });
</script>

<div bind:this={ziel} class="markdown {klasse}"></div>
