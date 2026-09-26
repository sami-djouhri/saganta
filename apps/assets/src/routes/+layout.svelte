<script lang="ts">
  import '../app.css';
  import {
    TopBar,
    UpdateBanner,
    CommandPalette,
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
  <TopBar app="Besitz" user={data.user} currentAppId="assets" host={data.host} />
  {#if data.user}<CommandPalette commands={buildAppCommands('assets', data.host)} />{/if}
  <PageContainer breite="standard">
    {@render children()}
  </PageContainer>
</div>
