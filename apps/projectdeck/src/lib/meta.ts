// Anzeige-Labels und Auswahllisten (Werte == Backend-Enums).

// icon == Name aus @saganta/ui Icon-Registry (siehe packages/ui Icon.svelte).
export const NAV = [
  { href: '/', label: 'Dashboard', icon: 'layout-dashboard' },
  { href: '/projekte', label: 'Projekte', icon: 'layout-grid' },
  { href: '/deadlines', label: 'Fristen', icon: 'clock' },
  { href: '/fokus', label: 'Wochenfokus', icon: 'star' },
  { href: '/public-pipeline', label: 'Veröffentlichung', icon: 'eye' },
  { href: '/kunden', label: 'Kundenprojekte', icon: 'users' },
  { href: '/reviews', label: 'Durchsichten', icon: 'check' },
  { href: '/shutdown', label: 'Abschalten', icon: 'power' },
  { href: '/archiv', label: 'Archiv', icon: 'archive' },
  { href: '/einstellungen', label: 'Einstellungen', icon: 'settings' },
] as const;

// Anzeigetexte sind deutsch wie der Rest der Oberflaeche. Bis 2026-09-18
// standen hier englische Bezeichnungen, waehrend READINESS_LABELS und
// SHUTDOWN_LABELS in derselben Datei schon deutsch waren: auf der Kachel stand
// dann "Public Project / Active" neben "Neues Projekt" und "Naechste Aktion".
// Die Schluessel bleiben die Backend-Enums, nur die Anzeige wechselt.
export const PROJECT_TYPES: Record<string, string> = {
  public: 'Öffentlich',
  private: 'Privat',
  client: 'Kunde',
  internal: 'Intern',
  experiment: 'Versuch',
  product_candidate: 'Produkt-Kandidat',
  frozen: 'Eingefroren',
  archived: 'Archiviert',
};

export const PROJECT_STATUS: Record<string, string> = {
  idea: 'Idee',
  planned: 'Geplant',
  active: 'Aktiv',
  maintenance: 'Pflege',
  frozen: 'Eingefroren',
  review: 'Durchsicht',
  shutdown_candidate: 'Abschalt-Kandidat',
  shutdown: 'Eingestellt',
  archived: 'Archiviert',
};

export const VISIBILITY: Record<string, string> = {
  private: 'Privat',
  internal_preview: 'Interne Vorschau',
  public_preview: 'Öffentliche Vorschau',
  public: 'Öffentlich',
  client_only: 'Nur für den Kunden',
};

export const SCHEDULING_MODE: Record<string, string> = {
  none: 'Keine Planung',
  low_maintenance: 'Geringe Pflege',
  weekly_focus: 'Wochenfokus',
  deadline: 'Auf Frist',
  sprint: 'Sprint',
  emergency: 'Notfall',
};

export const DEADLINE_TYPE: Record<string, string> = {
  hard: 'Harte Frist',
  soft: 'Weiche Frist',
  target: 'Zieltermin',
  review: 'Durchsicht-Termin',
  sunset: 'Abschalt-Termin',
};

export const RISK_COLORS: Record<string, string> = {
  relaxed: 'text-emerald-400 border-emerald-500/40',
  watch: 'text-sky-400 border-sky-500/40',
  tight: 'text-amber-400 border-amber-500/40',
  critical: 'text-orange-400 border-orange-500/40',
  impossible: 'text-red-400 border-red-500/40',
  overdue: 'text-red-500 border-red-600/60',
};

export const READINESS_LABELS: Record<string, string> = {
  description: 'Beschreibung vorhanden',
  demo_deployment: 'Demo/Deployment vorhanden',
  privacy_imprint: 'Datenschutz/Impressum geprüft',
  no_sensitive_data: 'Keine sensiblen Daten sichtbar',
  stable_auth: 'Stabile Auth (falls nötig)',
  error_handling: 'Fehlerhandling vorhanden',
  monitoring: 'Monitoring vorhanden',
  screenshot_preview: 'Screenshot/Preview vorhanden',
  changelog: 'Changelog vorhanden',
  domain_url: 'Domain/URL gesetzt',
};

export const SHUTDOWN_LABELS: Record<string, string> = {
  domain_decision: 'Domain behalten oder kündigen?',
  stop_deployment: 'Deployment stoppen?',
  archive_repo: 'Repo archivieren?',
  secure_backups: 'Backups sichern?',
  check_dns: 'DNS prüfen?',
  remove_secrets: 'Secrets entfernen?',
  save_documentation: 'Dokumentation speichern?',
  replace_public_page: 'Public-Seite ersetzen?',
  end_costs: 'Kosten beenden?',
  remove_calendar_todo_links: 'Kalender-/Todo-Verknüpfungen entfernen?',
};

export const TILE_LABELS: Record<string, string> = {
  active_this_week: 'Aktiv diese Woche',
  client_projects: 'Kundenprojekte',
  public_projects: 'Öffentliche Projekte',
  private_projects: 'Private Projekte',
  public_candidates: 'Kandidaten für öffentlich',
  deadline_risks: 'Fristen in Gefahr',
  blocked: 'Blockierte Projekte',
  maintenance_needed: 'Wartung nötig',
  frozen: 'Auf Eis gelegt',
  shutdown_check: 'Abschalten prüfen',
  without_next_action: 'Ohne nächste Aktion',
  without_review: 'Ohne Durchsicht',
};

export function fmtMinutes(m: number | null | undefined): string {
  if (!m) return '–';
  const h = Math.floor(m / 60);
  const min = m % 60;
  return h ? `${h}h${min ? ` ${min}m` : ''}` : `${min}m`;
}
