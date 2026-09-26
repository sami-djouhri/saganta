<script lang="ts">
  import '../app.css';
  import { TopBar, Button, Icon, UpdateBanner, CommandPalette, buildAppCommands } from '@saganta/ui';
  import { APP_NAME, APP_ID } from '$lib/meta';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();
</script>

<UpdateBanner />
<div class="min-h-dvh bg-surface text-text">
  {#if data.user}
    <TopBar app={APP_NAME} user={data.user} currentAppId={APP_ID} host={data.host}>
      {#snippet actions()}
        <form method="POST" action="/logout">
          <Button type="submit" variant="ghost" size="sm" aria-label="Abmelden" title="Abmelden">
            <Icon name="log-out" size={16} />
          </Button>
        </form>
      {/snippet}
    </TopBar>
    <CommandPalette commands={buildAppCommands(APP_ID, data.host)} />
    <!-- Keine Seitenleiste: es gibt eine Seite. Die Navigation ist die Zeit,
         und die liegt als Datumsleiste bei dem Text, zu dem sie gehört. -->
    <div class="mx-auto max-w-3xl px-4 py-6 md:px-6">
      <main id="main" tabindex="-1" class="min-w-0 outline-none">
        {@render children()}
      </main>
    </div>
  {:else}
    <main id="main" tabindex="-1" class="mx-auto max-w-md px-6 py-24 text-center outline-none">
      <h1 class="font-display text-2xl">Saganta Tagebuch</h1>
      <p class="mt-2 text-muted">Bitte anmelden, um fortzufahren.</p>
      <a
        href="/"
        class="mt-6 inline-block rounded-md border border-border px-4 py-2 text-sm hover:text-text"
        >Zur Anmeldung</a
      >
    </main>
  {/if}
</div>
