export const APP_NAME = 'Kontakte';
export const APP_ID = 'kontakte';

/** Die Navigation der App. `icon` sind Namen aus der Registry in `@saganta/ui`. */
export const NAV = [
  { href: '/', label: 'Kontakte', icon: 'users' },
  { href: '/neu', label: 'Neu', icon: 'plus' },
  { href: '/papierkorb', label: 'Papierkorb', icon: 'archive' },
] as const;
