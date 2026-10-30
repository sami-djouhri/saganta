<script lang="ts">
  // Gemeinsamer Rahmen für die Auth-Seiten (Login/Register, Forgot, Reset).
  // Spiegelt die Atmosphäre der Landing (Gradient-Mesh + Korn), zentriert eine
  // schmale Spalte und rendert den Seiteninhalt darin.
  interface Props {
    children: import('svelte').Snippet;
  }
  let { children }: Props = $props();
</script>

<div class="auth relative flex min-h-dvh flex-col overflow-hidden bg-surface px-6 py-8 text-text">
  <div class="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
    <div class="mesh mesh-a"></div>
    <div class="mesh mesh-b"></div>
    <div class="grain"></div>
  </div>
  <!-- Inhalt füllt den freien Raum und bleibt zentriert; der Footer liegt im Fluss
       darunter → überlappt auch hohe Formulare (Register) auf kurzen Viewports nicht. -->
  <div class="grid flex-1 place-items-center py-6">
    <div class="reveal w-full max-w-sm">
      {@render children()}
    </div>
  </div>
  <footer class="flex flex-wrap justify-center gap-x-5 gap-y-1 text-xs text-muted">
    <a href="/" class="transition-colors duration-fast ease-saganta hover:text-text">Startseite</a>
    <a href="/impressum" class="transition-colors duration-fast ease-saganta hover:text-text">Impressum</a>
    <a href="/datenschutz" class="transition-colors duration-fast ease-saganta hover:text-text">Datenschutz</a>
  </footer>
</div>

<style>
  .mesh {
    position: absolute;
    border-radius: 9999px;
    filter: blur(90px);
  }
  .mesh-a {
    top: -10rem;
    left: 50%;
    width: 34rem;
    height: 34rem;
    transform: translateX(-60%);
    background: radial-gradient(circle, var(--color-accent-500), transparent 65%);
    opacity: 0.4;
    animation: drift-a 28s ease-in-out infinite alternate;
  }
  .mesh-b {
    bottom: -12rem;
    right: -6rem;
    width: 28rem;
    height: 28rem;
    background: radial-gradient(circle, #c8884a, transparent 65%);
    opacity: 0.18;
    animation: drift-b 34s ease-in-out infinite alternate;
  }
  .grain {
    position: absolute;
    inset: 0;
    opacity: 0.035;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }
  .reveal {
    opacity: 0;
    transform: translateY(12px);
    animation: reveal 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  @keyframes drift-a {
    to {
      transform: translateX(-60%) translate(3rem, 2.5rem) scale(1.1);
    }
  }
  @keyframes drift-b {
    to {
      transform: translate(-2rem, -2rem) scale(1.08);
    }
  }
  @keyframes reveal {
    to {
      opacity: 1;
      transform: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .mesh-a,
    .mesh-b,
    .reveal {
      animation: none;
    }
    .reveal {
      opacity: 1;
      transform: none;
    }
  }
</style>
