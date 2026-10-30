export interface SagantaUser {
  sub: string;
  email: string;
  name?: string;
  groups: string[];
  /**
   * Tarif des Kontos ('free' | 'pro'), aus der auth-DB. Reist als `plan`-Claim
   * im Backend-JWT mit; was er bedeutet, steht in `saganta_dienst/tarife.py`.
   * Fehlt er, gilt 'free' (fail-closed, an jeder auswertenden Stelle).
   */
  plan?: string;
}

export interface SessionRecord {
  user: SagantaUser;
  accessToken: string;
  refreshToken?: string;
  idToken: string;
  expiresAt: number; // unix seconds
  createdAt: number;
}

export interface SessionStore {
  get(sid: string): Promise<SessionRecord | null>;
  set(sid: string, record: SessionRecord, ttlSeconds: number): Promise<void>;
  destroy(sid: string): Promise<void>;
}

export interface PendingAuth {
  state: string;
  nonce: string;
  codeVerifier: string;
  redirectAfter: string;
  createdAt: number;
}

export interface PendingStore {
  get(state: string): Promise<PendingAuth | null>;
  set(state: string, pending: PendingAuth, ttlSeconds: number): Promise<void>;
  destroy(state: string): Promise<void>;
}
