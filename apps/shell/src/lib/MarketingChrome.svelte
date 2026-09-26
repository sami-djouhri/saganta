<script lang="ts">
  // Gemeinsame Marketing-Hülle (Nav + Footer + Atmosphäre) für die öffentlichen
  // Seiten (Landing, Preise, Apps). Hält Look und Navigation konsistent.
  interface Props {
    children: import('svelte').Snippet;
    /** Aktiver Navigationspunkt für die Hervorhebung. */
    active?: 'home' | 'preise' | 'apps';
    /** Eingeloggter Nutzer (aus dem Layout) → passende CTAs statt Anmelden/Registrieren. */
    user?: { email: string; name?: string } | null;
  }
  let { children, active, user = null }: Props = $props();

  const nav = [
    { href: '/apps', label: 'Apps', key: 'apps' },
    { href: '/preise', label: 'Preise', key: 'preise' },
  ];
</script>

<div class="landing min-h-dvh overflow-x-clip bg-surface text-text">
  <div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
    <div class="mesh mesh-a"></div>
    <div class="mesh mesh-b"></div>
    <div class="grain"></div>
  </div>

  <header class="sticky top-0 z-30 border-b border-border/50 bg-surface/70 backdrop-blur-xl">
    <nav class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
      <a href="/" class="flex items-center gap-2.5 font-display text-2xl tracking-tight"><svg viewBox="0 0 100 100" class="h-7 w-7" aria-hidden="true"><path d="M 69 27 A 19 19 0 1 0 50 46 A 19 19 0 1 1 31 73" fill="none" stroke="#dd9c3f" stroke-width="12.5" stroke-linecap="round"/><circle cx="69" cy="27" r="6" fill="currentColor"/><circle cx="31" cy="73" r="6" fill="currentColor"/></svg><span>Saganta</span></a>
      <div class="flex items-center gap-4 text-sm sm:gap-6">
        {#each nav as item (item.key)}
          <a
            href={item.href}
            aria-current={active === item.key ? 'page' : undefined}
            class="text-sm font-medium transition-colors duration-fast ease-saganta hover:text-text"
            class:text-text={active === item.key}
            class:text-muted={active !== item.key}
          >
            {item.label}
          </a>
        {/each}
      </div>
      <div class="flex items-center gap-1.5">
        {#if user}
          <a
            href="/"
            class="rounded-lg bg-accent-500 px-4 py-2 text-sm font-semibold text-accent-ink shadow-sm transition-colors duration-fast ease-saganta hover:bg-accent-400"
          >
            Zur Übersicht
          </a>
        {:else}
          <a
            href="/login"
            class="rounded-lg px-4 py-2 text-sm font-medium text-muted transition-colors duration-fast ease-saganta hover:text-text"
          >
            Anmelden
          </a>
          <a
            href="/login?mode=register"
            class="rounded-lg bg-accent-500 px-4 py-2 text-sm font-semibold text-accent-ink shadow-sm transition-colors duration-fast ease-saganta hover:bg-accent-400"
          >
            Konto erstellen
          </a>
        {/if}
      </div>
    </nav>
  </header>

  {@render children()}

  <footer class="border-t border-border">
    <div class="mx-auto grid max-w-6xl gap-8 px-6 py-14 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
      <div>
        <span class="flex items-center gap-2 font-display text-xl text-text"><svg viewBox="0 0 100 100" class="h-5 w-5" aria-hidden="true"><path d="M 69 27 A 19 19 0 1 0 50 46 A 19 19 0 1 1 31 73" fill="none" stroke="#dd9c3f" stroke-width="12.5" stroke-linecap="round"/></svg><span>Saganta</span></span>
        <p class="mt-2 max-w-xs text-sm text-muted">
          Deine private Suite. Selbst gehostet, werbefrei, unter deiner Kontrolle.
        </p>
      </div>
      <div>
        <p class="mb-3 text-xs font-medium uppercase tracking-wider text-muted">Produkt</p>
        <ul class="space-y-2 text-sm">
          <li><a href="/apps" class="text-muted transition-colors hover:text-text">Apps</a></li>
          <li><a href="/preise" class="text-muted transition-colors hover:text-text">Preise</a></li>
          <li><a href="/login?mode=register" class="text-muted transition-colors hover:text-text">Konto erstellen</a></li>
        </ul>
      </div>
      <div>
        <p class="mb-3 text-xs font-medium uppercase tracking-wider text-muted">Konto</p>
        <ul class="space-y-2 text-sm">
          <li><a href="/login" class="text-muted transition-colors hover:text-text">Anmelden</a></li>
          <li><a href="mailto:hallo@saganta.de" class="text-muted transition-colors hover:text-text">Kontakt</a></li>
        </ul>
      </div>
      <div>
        <p class="mb-3 text-xs font-medium uppercase tracking-wider text-muted">Rechtliches</p>
        <ul class="space-y-2 text-sm">
          <li><a href="/impressum" class="text-muted transition-colors hover:text-text">Impressum</a></li>
          <li><a href="/datenschutz" class="text-muted transition-colors hover:text-text">Datenschutz</a></li>
          <li><a href="/agb" class="text-muted transition-colors hover:text-text">AGB & Widerruf</a></li>
        </ul>
      </div>
    </div>
    <div class="border-t border-border/60">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-5 text-xs text-muted">
        <span>© Saganta</span>
        <span>Selbst gehostet · privat · werbefrei</span>
      </div>
    </div>
  </footer>
</div>

<style>
  .mesh {
    position: absolute;
    border-radius: 9999px;
    filter: blur(90px);
    opacity: 0.5;
  }
  .mesh-a {
    top: -12rem;
    left: -8rem;
    width: 38rem;
    height: 38rem;
    background: radial-gradient(circle, var(--color-accent-500), transparent 65%);
    animation: drift-a 26s ease-in-out infinite alternate;
  }
  .mesh-b {
    top: 18rem;
    right: -10rem;
    width: 32rem;
    height: 32rem;
    background: radial-gradient(circle, #c8884a, transparent 65%);
    opacity: 0.22;
    animation: drift-b 32s ease-in-out infinite alternate;
  }
  .grain {
    position: absolute;
    inset: 0;
    opacity: 0.035;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }
  @keyframes drift-a {
    to {
      transform: translate(4rem, 3rem) scale(1.12);
    }
  }
  @keyframes drift-b {
    to {
      transform: translate(-3rem, -2rem) scale(1.08);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .mesh-a,
    .mesh-b {
      animation: none;
    }
  }
</style>
