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
  class="group relative flex h-full flex-col gap-2 rounded-lg border border-border bg-surface-2 p-4 sm:p-5 transition-all duration-base ease-saganta hover:-translate-y-0.5 hover:border-accent-400 hover:shadow-lg"
>
  <div class="flex items-center justify-between">
    <span class="text-akzent transition-transform duration-base ease-saganta group-hover:scale-110" aria-hidden="true">
      <Icon name={icon} size={28} />
    </span>
    {#if badge !== undefined && badge !== ''}
      <span class="rounded-full bg-accent-600 px-2 py-0.5 text-xs font-medium text-white">{badge}</span>
    {/if}
  </div>
  <!-- Am Handy zwei Kacheln nebeneinander, nur Sinnbild und Name: die
       Beschreibungen machten elf Apps zu ueber 1000 px Laufweg. -->
  <div class="mt-1 sm:mt-2">
    <h3 class="pr-8 font-display text-lg text-text sm:pr-0 sm:text-xl">{name}</h3>
    <p class="mt-1 hidden text-sm text-muted sm:block">{description}</p>
  </div>
</a>
