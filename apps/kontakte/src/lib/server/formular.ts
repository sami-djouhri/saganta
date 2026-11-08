/** Formularfelder zu dem Rumpf, den `kontakte-api` erwartet. */
import type { Jahrestag } from '$lib/typen';

function feld(fd: FormData, name: string): string | null {
  const wert = String(fd.get(name) ?? '').trim();
  return wert || null;
}

/**
 * Jahrestage kommen als parallele Felder `jt_bezeichnung` / `jt_datum`.
 * Zeilen mit nur einer Haelfte fallen weg statt den ganzen Kontakt abzulehnen;
 * eine leere neue Zeile ist der Normalfall.
 */
export function jahrestageAus(fd: FormData): Jahrestag[] {
  const namen = fd.getAll('jt_bezeichnung').map((v) => String(v).trim());
  const daten = fd.getAll('jt_datum').map((v) => String(v).trim());
  const ergebnis: Jahrestag[] = [];
  namen.forEach((bezeichnung, i) => {
    const datum = daten[i] ?? '';
    if (bezeichnung && /^\d{4}-\d{2}-\d{2}$/.test(datum)) ergebnis.push({ bezeichnung, datum });
  });
  return ergebnis;
}

export function kontaktAus(fd: FormData) {
  return {
    name: feld(fd, 'name') ?? '',
    telefon: feld(fd, 'telefon'),
    email: feld(fd, 'email'),
    adresse: feld(fd, 'adresse'),
    geburtstag: feld(fd, 'geburtstag'),
    gruppe: feld(fd, 'gruppe'),
    notiz: feld(fd, 'notiz'),
    jahrestage: jahrestageAus(fd),
  };
}
