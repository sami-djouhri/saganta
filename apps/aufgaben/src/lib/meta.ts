export const APP_NAME = 'Aufgaben';
export const APP_ID = 'aufgaben';

/** Die Navigation der App. `icon` sind Namen aus der Registry in `@saganta/ui`. */
export const NAV = [
  { href: '/', label: 'Heute', icon: 'sun' },
  { href: '/alle', label: 'Alle Aufgaben', icon: 'list-todo' },
  { href: '/projekte', label: 'Nach Projekt', icon: 'folder' },
  { href: '/archiv', label: 'Erledigt', icon: 'circle-check' },
] as const;
