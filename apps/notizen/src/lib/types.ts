export type VerknuepfungsTyp =
  | 'termin'
  | 'aufgabe'
  | 'ziel'
  | 'projekt'
  | 'kontakt'
  | 'brief';

export interface Notizbuch {
  id: number;
  name: string;
  farbe: string | null;
  sortierung: number;
  erstellt_am: string;
  anzahl_notizen: number;
}

export interface Anhang {
  id: number;
  dateiname: string;
  mime: string;
  groesse: number;
  erstellt_am: string;
}

export interface Verknuepfung {
  id: number;
  typ: VerknuepfungsTyp;
  ref: string;
  label: string;
  erstellt_am: string;
}

export interface Freigabe {
  id: number;
  merkmal: string;
  modus: 'offen' | 'chiffriert';
  zustand: 'aktiv' | 'widerrufen' | 'abgelaufen' | 'verbraucht' | 'gesperrt' | 'quelle_weg';
  ablauf_am: string | null;
  max_abrufe: number | null;
  abrufe: number;
  passwortgeschuetzt: boolean;
  mit_anhaengen: boolean;
  notiz_id: number | null;
  notiz_titel: string;
  erstellt_am: string;
  letzter_abruf_am: string | null;
}

export interface NotizKurz {
  id: number;
  titel: string;
  ausschnitt: string;
  tags: string[];
  notizbuch_id: number | null;
  angeheftet: boolean;
  archiviert: boolean;
  anzahl_anhaenge: number;
  anzahl_verknuepfungen: number;
  anzahl_freigaben: number;
  erstellt_am: string;
  geaendert_am: string;
}

export interface Notiz {
  id: number;
  titel: string;
  inhalt: string;
  tags: string[];
  notizbuch_id: number | null;
  angeheftet: boolean;
  archiviert: boolean;
  erstellt_am: string;
  geaendert_am: string;
  anhaenge: Anhang[];
  verknuepfungen: Verknuepfung[];
  freigaben: Freigabe[];
}

/** Ein verknüpfbares Gegenstück, wie es die Suche im BFF zurückgibt. */
export interface Fundstueck {
  typ: VerknuepfungsTyp;
  ref: string;
  label: string;
  zusatz?: string;
}

export interface OeffentlicherZustand {
  modus: 'offen' | 'chiffriert';
  zustand: Freigabe['zustand'];
  braucht_passwort: boolean;
  einmalig: boolean;
  verbleibende_abrufe: number | null;
  ablauf_am: string | null;
  schluessel_quelle: 'fragment' | 'passwort' | null;
  algo: string | null;
  kdf_salz: string | null;
  kdf_iterationen: number | null;
}

export interface OeffentlicherInhalt {
  modus: 'offen' | 'chiffriert';
  titel: string;
  inhalt: string | null;
  chiffrat: string | null;
  iv: string | null;
  anhaenge: { id: number; dateiname: string; mime: string; groesse: number }[];
  verbleibende_abrufe: number | null;
  einmalig: boolean;
  anhang_schein: string | null;
}
