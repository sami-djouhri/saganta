<script lang="ts">
  import '../app.css';
  import { TopBar, UpdateBanner, PageContainer } from '@saganta/ui';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();
</script>

<svelte:head>
  <!-- Fallback-Titel; Seiten (z. B. Landing) überschreiben ihn via eigenem svelte:head. -->
  <title>Saganta News</title>
</svelte:head>

{#if data.user}
  <UpdateBanner />
{/if}

<div class="min-h-dvh bg-surface text-text" data-theme="dark">
  <TopBar app="News" user={data.user} currentAppId="news" host={data.host}>
    {#snippet actions()}
      {#if data.user}
        <a
          href="/"
          class="rounded-md border border-border px-2 py-1 text-sm text-muted hover:text-text"
          title="Nachrichten-Feed"
        >
          Feed
        </a>
        <a
          href="/briefing"
          class="rounded-md border border-border px-2 py-1 text-sm text-muted hover:text-text"
          title="Mein Briefing"
        >
          Mein Briefing
        </a>
      {:else}
        <a
          href="https://saganta.de/login"
          class="rounded-md border border-border px-3 py-1 text-sm text-muted hover:text-text"
        >
          Anmelden
        </a>
        <a
          href="https://saganta.de/login?mode=register"
          class="rounded-md bg-accent-500 px-3 py-1 text-sm font-medium text-black hover:bg-accent-400"
        >
          Kostenlos starten
        </a>
      {/if}
    {/snippet}
  </TopBar>
  {#if data.user}
    <PageContainer breite="lesen">
      {@render children()}
    </PageContainer>
  {:else}
    <!-- Landing: randlos ueber die ganze Breite, aber mit Sprungziel. -->
    <main id="main" tabindex="-1" class="outline-none">
      {@render children()}
    </main>
  {/if}
</div>
