<script lang="ts">
  import { page } from '$app/stores';
</script>

<div class="mx-auto max-w-md px-6 py-24 text-center">
  <h1 class="font-display text-3xl">{$page.status}</h1>
  <p class="mt-2 text-muted">{$page.error?.message ?? 'Da ist etwas schiefgegangen.'}</p>
  <a
    href="/"
    class="mt-6 inline-block rounded-md border border-border px-4 py-2 text-sm hover:text-text"
    >Zurück</a
  >
</div>
