<script lang="ts">
  import { onMount } from 'svelte';
  import { invalidateAll } from '$app/navigation';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  // Webhook kann ein paar Sekunden brauchen → bis zu ~15 s nachladen.
  let tries = $state(0);
  onMount(() => {
    if (data.isPro) return;
    const id = setInterval(async () => {
      tries += 1;
      await invalidateAll();
      if (data.isPro || tries >= 5) clearInterval(id);
    }, 3000);
    return () => clearInterval(id);
  });
</script>

<svelte:head><title>Willkommen bei Pro · Saganta Briefing</title></svelte:head>

<section class="mx-auto max-w-lg space-y-6 py-16 text-center">
  {#if data.isPro}
    <div class="text-5xl">✓</div>
    <h1 class="font-display text-3xl">Willkommen bei Pro!</h1>
    <p class="text-muted">
      Deine Premium-Stimme, längere Briefings, eigene Themen und Webhook-Zustellung sind ab sofort aktiv.
    </p>
  {:else}
    <div class="text-5xl">⏳</div>
    <h1 class="font-display text-3xl">Danke für dein Upgrade!</h1>
    <p class="text-muted">
      Wir aktivieren dein Pro-Abo gerade. Das dauert meist nur ein paar Sekunden…
    </p>
  {/if}
  <a
    href="/briefing"
    class="inline-block rounded-lg bg-accent-500 px-5 py-2.5 text-sm font-medium text-black hover:bg-accent-400"
  >
    Zu meinem Briefing
  </a>
</section>
