import type { Action } from 'svelte/action';

/**
 * Scroll-Reveal-Action: blendet ein Element sanft ein, sobald es in den Viewport
 * scrollt. Reine Client-Logik (Action läuft nur im Browser → SSR rendert das
 * Element regulär, kein Hydration-Mismatch). Respektiert prefers-reduced-motion:
 * dann sofort sichtbar, keine Animation.
 *
 * Nutzung: <div use:inview> ... </div>  (optional use:inview={{ delay: 120 }})
 * Das Element bekommt initial die Klasse `reveal-init`; bei Sichtbarkeit `reveal-in`.
 */
interface InviewOptions {
  /** Verzögerung in ms, gestaffelt z. B. nach Index. */
  delay?: number;
  /** Sichtbarkeits-Schwelle (0..1). Default 0.15. */
  threshold?: number;
}

export const inview: Action<HTMLElement, InviewOptions | undefined> = (node, options) => {
  const reduce =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  if (reduce) {
    node.classList.add('reveal-in');
    return {};
  }

  const delay = options?.delay ?? 0;
  const threshold = options?.threshold ?? 0.15;
  node.classList.add('reveal-init');
  if (delay) node.style.transitionDelay = `${delay}ms`;

  const obs = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          node.classList.add('reveal-in');
          obs.unobserve(node);
        }
      }
    },
    { threshold },
  );
  obs.observe(node);

  return {
    destroy() {
      obs.disconnect();
    },
  };
};
