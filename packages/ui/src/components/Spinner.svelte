<script lang="ts">
  interface Props {
    size?: number;
    label?: string;
  }
  let { size = 16, label = 'Lädt…' }: Props = $props();
</script>

<span class="inline-flex items-center gap-2" role="status" aria-live="polite">
  <span
    class="animate-spin rounded-full border-2 border-current border-t-transparent"
    style="width:{size}px;height:{size}px;"
    aria-hidden="true"
  ></span>
  <span class="sr-only">{label}</span>
</span>
