<script lang="ts">
  /**
   * Die kleine Projektmarke am Termin (seit 2026-11-15).
   *
   * Mit `href` ein Link ins ProjectDeck; ohne (z. B. innerhalb eines Knopfes,
   * wo ein Link ungueltiges HTML waere) nur die Marke.
   */
  import { Icon } from '@saganta/ui';

  interface Props {
    slug: string;
    name?: string | null;
    href?: string | null;
  }
  let { slug, name = null, href = null }: Props = $props();
  const text = $derived(name || slug);
</script>

{#if href}
  <a
    {href}
    class="inline-flex max-w-full items-center gap-1 rounded-full border border-border-stark px-2 py-0.5 text-xs text-muted hover:border-accent-500 hover:text-akzent"
    title="Projekt „{text}“ im ProjectDeck öffnen"
  >
    <Icon name="folder" size={11} /><span class="truncate">{text}</span>
  </a>
{:else}
  <span
    class="inline-flex max-w-full items-center gap-1 rounded-full border border-border-stark px-2 py-0.5 text-xs text-muted"
    title="Projekt „{text}“"
  >
    <Icon name="folder" size={11} /><span class="truncate">{text}</span>
  </span>
{/if}
