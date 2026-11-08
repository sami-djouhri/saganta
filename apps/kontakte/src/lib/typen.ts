/** So liefert `kontakte-api` einen Kontakt. Browser und Server lesen diese Datei. */
export interface Jahrestag {
  bezeichnung: string;
  datum: string;
}

export interface TerminVerweis {
  ref: string;
  label: string;
  start: string | null;
}

export interface Kontakt {
  id: string;
  name: string;
  telefon: string | null;
  email: string | null;
  adresse: string | null;
  geburtstag: string | null;
  jahrestage: Jahrestag[];
  gruppe: string | null;
  termine: TerminVerweis[];
  notiz: string | null;
  herkunft: string | null;
  geloescht_am: string | null;
  erstellt_am: string;
  geaendert_am: string;
}

export interface Anstehend {
  kontakt_id: string;
  name: string;
  art: 'geburtstag' | 'jahrestag';
  bezeichnung: string;
  datum: string;
  in_tagen: number;
  zahl: number;
}

export interface Fundtermin {
  ref: string;
  label: string;
  start: string | null;
}
