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
  <TopBar app="Mail" user={data.user} currentAppId="mail" host={data.host} />
  {#if data.user}<CommandPalette commands={buildAppCommands('mail', data.host)} />{/if}
  <PageContainer breite="standard">
    {@render children()}
  </PageContainer>
</div>
