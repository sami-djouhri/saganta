<script lang="ts">
  import { onMount } from 'svelte';

  // enabled = ob CAPTCHA_HMAC_KEY serverseitig gesetzt ist (aus load-Data). Ist es aus,
  // rendern wir nichts: captchaOk() lässt dann ohnehin alles durch.
  let { enabled = true }: { enabled?: boolean } = $props();

  let ready = $state(false);
  onMount(() => {
    if (!enabled) return;
    // Widget-Script einmal laden (idempotent: define() ist gegen Doppelregistrierung geschützt).
    const src = '/captcha-guard/captcha-guard.js';
    if (!document.querySelector(`script[src="${src}"]`)) {
      const s = document.createElement('script');
      s.src = src;
      s.defer = true;
      s.onload = () => (ready = true);
      document.head.appendChild(s);
    } else {
      ready = true;
    }
  });
</script>

{#if enabled}
  <div class="cg-field">
    <!-- Web-Component: holt Challenge same-origin, löst PoW, legt Token in Hidden-Input "altcha". -->
    <captcha-guard challenge-url="/captcha/challenge" field-name="altcha"></captcha-guard>
    {#if !ready}<span class="cg-hint">Sicherheitsprüfung wird geladen …</span>{/if}
  </div>
{/if}

<style>
  .cg-field :global(.cg-box) {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
    color: var(--color-muted, #9aa4b2);
  }
  .cg-field :global(.cg-spinner) {
    width: 0.85rem;
    height: 0.85rem;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: cg-spin 0.8s linear infinite;
    opacity: 0.6;
  }
  .cg-field :global(captcha-guard[data-state='solved'] .cg-spinner) {
    display: none;
  }
  .cg-field :global(captcha-guard[data-state='error'] .cg-status) {
    color: var(--color-warm-400, #f59e0b);
  }
  .cg-hint {
    font-size: 0.75rem;
    color: var(--color-muted, #9aa4b2);
  }
  @keyframes cg-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
