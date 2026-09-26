-- Der Tarif zieht von der App-Tabelle ans Konto (02.09.2026).
--
-- Vorher lag er in `briefing_profiles.plan` der news-api. Das war die Tabelle
-- des Briefing-Produkts, nicht die des Nutzers: kein anderer Dienst konnte ihn
-- lesen, und beim Oeffnen der Registrierung haette ein zahlender Kunde in sechs
-- von sieben Backends dasselbe gesehen wie ein Gratis-Konto.
--
-- Ab hier ist `user.plan` die Wahrheit. Von dort reist der Wert als
-- `plan`-Claim im Backend-JWT (packages/auth/src/backend-token.ts und der
-- Inline-Spiegel in apps/auth-service/src/server.ts) zu allen Backends und
-- wird in saganta_dienst/tarife.py ausgewertet.
--
-- Idempotent: mehrfach ausfuehrbar. Die Spaltennamen folgen better-auths
-- camelCase-Konvention (wie `emailVerified`), sonst findet die Bibliothek das
-- additionalField nicht.

ALTER TABLE "user" ADD COLUMN IF NOT EXISTS "plan" text NOT NULL DEFAULT 'free';
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS "planStatus" text;

-- Fail-closed absichern: kein Konto darf durch einen Tippfehler oder einen
-- NULL-Wert in einen bezahlten Tarif rutschen. Die Pruefung steht in der
-- Datenbank und nicht nur im Anwendungscode, weil der Stripe-Webhook und die
-- Admin-Route beide hierher schreiben.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'user_plan_bekannt'
  ) THEN
    ALTER TABLE "user"
      ADD CONSTRAINT user_plan_bekannt CHECK ("plan" IN ('free', 'pro'));
  END IF;
END $$;

-- Bestandsuebernahme: wer heute Pro hat, behaelt es. Bewusst ausgeschrieben
-- statt aus der news-api gelesen, weil die beiden Datenbanken getrennt sind
-- (Postgres hier, SQLite dort) und ein Migrationsschritt keinen laufenden
-- Dienst befragen soll. Stand 02.09.2026 hatte genau ein Konto Pro, gemessen
-- in briefing_profiles.
--
-- ★ Die Kennung ist ein Aufrufparameter und steht nicht mehr im Quelltext
--   (2026-09-05). Sie gehoert einem konkreten Menschen, und diese Datei soll
--   veroeffentlicht werden koennen. Ohne -v konto=... macht dieser Teil nichts,
--   das Schema oben wird trotzdem angelegt.
--
--   psql -v konto='<better-auth user.id>' -f 001-tarif-am-konto.sql
\if :{?konto}
UPDATE "user" SET "plan" = 'pro'
WHERE id = :'konto' AND "plan" <> 'pro';
\else
\echo 'Hinweis: kein -v konto=... angegeben, kein Konto auf pro gesetzt.'
\endif
