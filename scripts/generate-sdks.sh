#!/usr/bin/env bash
# Generiert typisierte SDK-Clients aus den OpenAPI-Specs der Backends.
# Stub-Implementierung: Backends haben aktuell keine standardisierte
# OpenAPI-Spec exponiert. Sobald sie das tun:
#
#   pnpm dlx openapi-typescript $KALENDER_OPENAPI -o packages/sdk-kalender/src/schema.ts
#   pnpm dlx openapi-typescript $BRIEFKASTEN_OPENAPI -o packages/sdk-briefkasten/src/schema.ts
#   pnpm dlx openapi-typescript $LIFEOPS_OPENAPI -o packages/sdk-lifeops/src/schema.ts
#
# Aktuell sind die Clients von Hand getippt: siehe packages/sdk-*/src/index.ts.

set -euo pipefail
echo "Stub: noch keine OpenAPI-Specs verfügbar. Siehe Kommentar im Skript."
