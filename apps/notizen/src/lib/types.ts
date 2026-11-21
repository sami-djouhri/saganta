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
  /**
   * Bei `fragment` steht der Schlüssel allein hinter dem `#` der Adresse, die
   * beim Anlegen einmal zu sehen war. Jede Liste kennt deshalb nur den vorderen
   * Teil und muss das sagen, statt eine halbe Adresse wie eine ganze zu zeigen.
   */
  schluessel_quelle: 'fragment' | 'passwort' | null;
}

/** Ein frueherer Stand einer Notiz, hoechstens fuenf je Notiz (seit 2026-11-14). */
export interface StandKurz {
  id: number;
  titel: string;
  /** Wann dieser Stand gespeichert worden war (naives UTC vom Dienst). */
  stand_vom: string;
  zeichen: number;
}

export interface Stand {
  id: number;
  titel: string;
  inhalt: string;
  tags: string[];
  stand_vom: string;
}

/** Eine geloeschte Notiz, 30 Tage zurueckholbar (Papierkorb seit 2026-11-07). */
export interface PapierkorbEintrag {
  id: number;
  titel: string;
  geloescht_am: string;
  /** So viele Anhaenge hatte sie; sie kommen nicht mit zurueck. */
  anhaenge: number;
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

/** Eine andere Notiz im Netz der angesehenen (Verweise seit 2026-11-20). */
export interface NotizVerweis {
  id: number;
  titel: string;
  ausschnitt: string;
  notizbuch_id: number | null;
  archiviert: boolean;
}

/** Verbunden von Hand, erwähnt per [[Titel]] in anderen, und die [[ ]] im eigenen Text. */
export interface Netz {
  verbunden: NotizVerweis[];
  erwaehnt_in: NotizVerweis[];
  verweist_auf: { text: string; id: number | null }[];
}

/** Alle Notizen und ihre Verweise, für die Netzansicht. */
export interface GesamtNetz {
  knoten: {
    id: number;
    titel: string;
    notizbuch_id: number | null;
    archiviert: boolean;
    angeheftet: boolean;
    grad: number;
    offene_verweise: number;
  }[];
  /** Bei `art` "text" verweist `a` per [[ ]] auf `b`. */
  kanten: { a: number; b: number; art: 'verbunden' | 'text' }[];
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
