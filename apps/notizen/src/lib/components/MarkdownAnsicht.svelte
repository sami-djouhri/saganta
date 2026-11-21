<script lang="ts">
  import { rendern, type VerweisAufloeser } from '$lib/markdown';

  let {
    quelle = '',
    klasse = '',
    verweise,
    anlegen,
  }: {
    quelle?: string;
    klasse?: string;
    /** Löst `[[Titel]]` auf; ohne ihn bleiben Verweise Text (öffentliche Leseseite). */
    verweise?: VerweisAufloeser;
    /** Gerufen, wenn ein Verweis auf eine Notiz angetippt wird, die es noch nicht gibt. */
    anlegen?: (titel: string) => void;
  } = $props();

  let ziel = $state<HTMLDivElement | null>(null);

  // Gerendert wird ins DOM, nicht als HTML-Zeichenkette gesetzt. Deshalb hier
  // ein Effekt statt {@html …}: `rendern` liefert fertige Knoten, und genau das
  // ist der Grund, warum aus fremdem Text kein Markup werden kann.
  $effect(() => {
    const inhalt = quelle;
    const aufloeser = verweise;
    if (!ziel) return;
    ziel.replaceChildren(rendern(inhalt, document, aufloeser));
  });

  function klick(e: MouseEvent) {
    const a = (e.target as Element | null)?.closest?.('a.verweis[data-fehlt]');
    if (!(a instanceof HTMLAnchorElement)) return;
    e.preventDefault();
    if (anlegen && a.dataset.titel) anlegen(a.dataset.titel);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<!-- Der Klick gehört den Links darin; Enter auf einem Link löst ihn ebenso aus. -->
<div bind:this={ziel} class="markdown {klasse}" onclick={klick}></div>
