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
  lat: number | null;
  lon: number | null;
  /** `null` = noch nicht gesucht, `gefunden`, `nicht_gefunden`, `hand`. */
  ort_stand: string | null;
  /** `adresse` (Hausnummer), `strasse`, `ort` oder `hand`. */
  ort_genauigkeit: string | null;
  geloescht_am: string | null;
  erstellt_am: string;
  geaendert_am: string;
}

/** Ein Kontakt als Punkt auf der Karte (`GET /api/orte`). */
export interface Ort {
  id: string;
  name: string;
  adresse: string | null;
  gruppe: string | null;
  lat: number;
  lon: number;
  ort_genauigkeit: string | null;
}

export interface Orte {
  orte: Ort[];
  nicht_gefunden: number;
  offen: number;
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
