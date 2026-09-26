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
  <TopBar app="Post" user={data.user} currentAppId="post" host={data.host} />
  {#if data.user}<CommandPalette commands={buildAppCommands('post', data.host)} />{/if}
  <PageContainer breite="lesen">
    {@render children()}
  </PageContainer>
</div>
