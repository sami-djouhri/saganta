<script lang="ts">
  import type { HTMLButtonAttributes } from 'svelte/elements';

  type Variant = 'primary' | 'ghost' | 'danger';
  type Size = 'sm' | 'md' | 'lg';

  interface Props extends HTMLButtonAttributes {
    variant?: Variant;
    size?: Size;
    loading?: boolean;
    children?: import('svelte').Snippet;
  }

  let {
    variant = 'primary',
    size = 'md',
    loading = false,
    children,
    class: klass = '',
    disabled,
    ...rest
  }: Props = $props();

  const variants: Record<Variant, string> = {
    primary: 'bg-accent-500 text-accent-ink font-semibold hover:bg-accent-400 active:bg-accent-600',
    ghost: 'bg-transparent text-text hover:bg-surface-2 border border-border',
    danger: 'bg-red-600 text-white hover:bg-red-500 active:bg-red-700',
  };
  const sizes: Record<Size, string> = {
    sm: 'h-8 px-3 text-sm rounded-sm',
    md: 'h-10 px-4 text-sm rounded-md',
    lg: 'h-12 px-5 text-base rounded-lg',
  };
</script>

<button
  class="inline-flex items-center justify-center gap-2 font-medium transition-colors duration-fast ease-saganta disabled:opacity-50 disabled:cursor-not-allowed {variants[
    variant
  ]} {sizes[size]} {klass}"
  disabled={disabled || loading}
  {...rest}
>
  {#if loading}<span class="size-3 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true"></span>{/if}
  {@render children?.()}
</button>
