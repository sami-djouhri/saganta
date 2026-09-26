<script lang="ts">
  import Icon from './Icon.svelte';

  interface Props {
    href: string;
    name: string;
    description: string;
    icon?: string;
    badge?: string | number;
  }
  let { href, name, description, icon = 'box', badge }: Props = $props();
</script>

<a
  {href}
  class="group relative flex flex-col gap-2 rounded-lg border border-border bg-surface-2 p-5 transition-all duration-base ease-saganta hover:-translate-y-0.5 hover:border-accent-400 hover:shadow-lg"
>
  <div class="flex items-center justify-between">
    <span class="text-accent-500 transition-transform duration-base ease-saganta group-hover:scale-110" aria-hidden="true">
      <Icon name={icon} size={28} />
    </span>
    {#if badge !== undefined && badge !== ''}
      <span class="rounded-full bg-accent-600 px-2 py-0.5 text-xs font-medium text-white">{badge}</span>
    {/if}
  </div>
  <div class="mt-2">
    <h3 class="font-display text-xl text-text">{name}</h3>
    <p class="mt-1 text-sm text-muted">{description}</p>
  </div>
</a>
