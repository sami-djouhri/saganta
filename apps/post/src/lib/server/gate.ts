import { env } from '$env/dynamic/private';

// Briefkasten (Briefe, Verträge, Dateianhänge) ist SINGLE-TENANT, die interne API
// liest mit einem statischen Token über ALLE Nutzer, es gibt kein per-sub-Schema.
// mail-api (E-Mail) ist dagegen pro sub isoliert.
//
// Deshalb KEIN blanket-403-Gate mehr auf die ganze App: jeder eingeloggte Nutzer
// darf Post für seine EIGENEN Mailkonten nutzen. Die Brief-/Vertragsdaten bleiben
// aber strikt auf die ALLOWED_SUBS-Allowlist begrenzt: fail-safe: für Nicht-Owner
// werden Briefe serverseitig gar nicht erst geholt, und JEDER Brief-Pfad (Feed,
// Detail, Archiv, Datei-Proxy) prüft canAccessLetters().
// ALLOWED_SUBS = kommaseparierte sub-Allowlist; leer = offen (Dev/Rückwärtskompat).
// Das blanket-Gate entfällt endgültig, wenn briefkasten echt user-isoliert ist.
function allowedSubs(): string[] {
  return (env.ALLOWED_SUBS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Darf dieser Nutzer die single-tenant Briefkasten-Daten (Briefe/Verträge/Dateien)
 * sehen? Leere Allowlist = offen. MUSS auf jedem Brief-Datenpfad geprüft werden.
 */
export function canAccessLetters(user: { sub: string } | null | undefined): boolean {
  if (!user) return false;
  const allow = allowedSubs();
  return allow.length === 0 || allow.includes(user.sub);
}
