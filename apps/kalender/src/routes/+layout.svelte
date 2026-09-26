<script lang="ts">
  import '../app.css';
  import {
    TopBar,
    UpdateBanner,
    CommandPalette,
    AppHinweis,
    buildAppCommands,
    PageContainer,
  } from '@saganta/ui';
  import type { LayoutData } from './$types';

  interface Props {
    children: import('svelte').Snippet;
    data: LayoutData;
  }
  let { children, data }: Props = $props();
</script>

<UpdateBanner />

<div class="min-h-dvh bg-surface text-text" data-theme="dark">
  <TopBar app="Kalender" user={data.user} currentAppId="calendar" host={data.host} />
  <!-- `kalender` ist die Manifest-Id unter /downloads, nicht die currentAppId `calendar`. -->
  <AppHinweis app="kalender" name="Kalender" zeigen={!!data.user} />
  {#if data.user}<CommandPalette commands={buildAppCommands('calendar', data.host)} />{/if}
  <PageContainer breite="breit">
    {@render children()}
  </PageContainer>
</div>
