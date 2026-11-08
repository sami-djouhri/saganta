<script lang="ts">
  import '../app.css';
  import { TopBar, UpdateBanner, PageContainer, AppRahmen } from '@saganta/ui';
  import { page } from '$app/stores';
  import type { LayoutData } from './$types';

  const NAV = [
    { href: '/', label: 'Feed', icon: 'newspaper' },
    { href: '/briefing', label: 'Mein Briefing', kurz: 'Briefing', icon: 'sunrise' },
  ] as const;

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();
</script>

<svelte:head>
  <!-- Fallback-Titel; Seiten überschreiben ihn via eigenem svelte:head. -->
  <title>Saganta News</title>
</svelte:head>

{#if data.user}
  <UpdateBanner />
{/if}

<div class="min-h-dvh bg-surface text-text">
  <TopBar app="News" user={data.user} currentAppId="news" host={data.host} />
  {#if data.user}
    <!-- Feed und Briefing standen bis 2026-11-08 als zwei umrandete Knoepfe im
         Kopf; jetzt wie in den anderen Apps Seitenleiste und Fussleiste. -->
    <AppRahmen nav={NAV} pfad={$page.url.pathname}>
      {@render children()}
    </AppRahmen>
  {:else}
    <PageContainer breite="lesen">
      {@render children()}
    </PageContainer>
  {/if}
</div>
