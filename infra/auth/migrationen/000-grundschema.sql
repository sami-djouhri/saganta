-- Das Grundschema des Anmeldedienstes (better-auth, Postgres).
--
-- WOZU: Bis zum 2026-09-12 entstand dieses Schema ausschliesslich ueber
-- `pnpm --filter @saganta/auth-service db:migrate`, also ueber die
-- better-auth-CLI aus dem Monorepo. Wer die Suite aus fertigen Abbildern
-- startet, hat weder pnpm noch den Quelltext noch einen Netzzugang zu npm.
-- Beim ersten Start aus einem frischen Klon war die Datenbank deshalb leer:
-- die Registrierung antwortete mit „Registrierung fehlgeschlagen", und die
-- eigentliche Ursache stand nur im Protokoll des Anmeldedienstes, als
-- Postgres-Fehler `parserOpenTable` auf eine Tabelle, die es nicht gibt.
--
-- Diese Datei wird beim ERSTEN Start der Datenbank ausgefuehrt (das
-- Postgres-Abbild arbeitet `/docker-entrypoint-initdb.d/` in
-- alphabetischer Reihenfolge ab, und nur solange sein Datenverzeichnis leer
-- ist). Deshalb die 000 im Namen: die Aenderungen daneben setzen sie voraus.
--
-- Herkunft: `pg_dump --schema-only` der laufenden Instanz, nicht von Hand
-- geschrieben. Es ist damit genau das Schema, das better-auth selbst angelegt
-- hat, einschliesslich der Aenderung 001 (Tarif am Konto).
--
-- Idempotent: `IF NOT EXISTS` ueberall, damit die Datei auch ueber eine
-- bestehende Datenbank laufen kann, ohne etwas zu zerstoeren.
--
-- ⚠️ Wer das Datenmodell im Quelltext aendert (`apps/auth-service/src/auth.ts`,
-- `additionalFields`), muss hier nachziehen. `pnpm --filter
-- @saganta/auth-service db:generate` zeigt, was better-auth erwartet.

CREATE TABLE IF NOT EXISTS "user" (
    id text NOT NULL,
    name text NOT NULL,
    email text NOT NULL,
    "emailVerified" boolean NOT NULL,
    image text,
    "createdAt" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    plan text DEFAULT 'free'::text NOT NULL,
    "planStatus" text,
    CONSTRAINT user_pkey PRIMARY KEY (id),
    CONSTRAINT user_email_key UNIQUE (email),
    CONSTRAINT user_plan_bekannt CHECK ((plan = ANY (ARRAY['free'::text, 'pro'::text])))
);

CREATE TABLE IF NOT EXISTS account (
    id text NOT NULL,
    "accountId" text NOT NULL,
    "providerId" text NOT NULL,
    "userId" text NOT NULL,
    "accessToken" text,
    "refreshToken" text,
    "idToken" text,
    "accessTokenExpiresAt" timestamp with time zone,
    "refreshTokenExpiresAt" timestamp with time zone,
    scope text,
    password text,
    "createdAt" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp with time zone NOT NULL,
    CONSTRAINT account_pkey PRIMARY KEY (id),
    CONSTRAINT "account_userId_fkey" FOREIGN KEY ("userId")
        REFERENCES "user"(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session (
    id text NOT NULL,
    "expiresAt" timestamp with time zone NOT NULL,
    token text NOT NULL,
    "createdAt" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp with time zone NOT NULL,
    "ipAddress" text,
    "userAgent" text,
    "userId" text NOT NULL,
    CONSTRAINT session_pkey PRIMARY KEY (id),
    CONSTRAINT session_token_key UNIQUE (token),
    CONSTRAINT "session_userId_fkey" FOREIGN KEY ("userId")
        REFERENCES "user"(id) ON DELETE CASCADE
);

-- Kurzlebige Token: Mail-Bestaetigung und Passwort-Ruecksetzung.
CREATE TABLE IF NOT EXISTS verification (
    id text NOT NULL,
    identifier text NOT NULL,
    value text NOT NULL,
    "expiresAt" timestamp with time zone NOT NULL,
    "createdAt" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT verification_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS "account_userId_idx" ON account USING btree ("userId");
CREATE INDEX IF NOT EXISTS "session_userId_idx" ON session USING btree ("userId");
CREATE INDEX IF NOT EXISTS verification_identifier_idx ON verification USING btree (identifier);
