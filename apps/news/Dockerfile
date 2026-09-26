FROM node:22-slim AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@10.33.2 --activate

FROM base AS deps
WORKDIR /repo
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml* ./
COPY apps/news/package.json apps/news/package.json
COPY packages packages
RUN pnpm install --frozen-lockfile || pnpm install

FROM deps AS build
WORKDIR /repo
COPY apps/news apps/news
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
RUN pnpm --filter @saganta/news build

FROM node:22-slim AS runner
# Sicherheitsstand des Basis-Image nachziehen. Ein Upstream-Image friert die Paketstaende
# vom Tag seines Baus ein, Debian-security ist regelmaessig weiter, und ein `--pull` holt
# nur ein neueres Bild derselben Verspaetung: gemessen am 2026-09-13 trug das aktuelle
# python:3.13-slim aus der Registry dieselben drei perl-CVEs wie das monatealte lokale.
# `upgrade`, nicht `dist-upgrade`: letzteres darf Pakete entfernen, um Konflikte zu loesen.
RUN apt-get update \
 && apt-get -y upgrade \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -u 10001 -m -d /home/appuser appuser
WORKDIR /app
COPY --from=build /repo/apps/news/build /app/build
COPY --from=build /repo/apps/news/package.json /app/package.json
# node_modules bewusst NICHT ins Runtime-Image: adapter-node bundelt den Server
# self-contained nach build/ → node_modules ist zur Laufzeit tot und schleppte nur
# die verwundbare esbuild-Dev-Binary mit (CVE-2025-68121). Beleg ZIELBILD P1#4.
# npm/npx aus dem Laufzeit-Image werfen: gestartet wird mit `node build`, ein
# Paketmanager wird zur Laufzeit nie gebraucht. Das mitgelieferte npm schleppt
# CVE-2026-59873 (node-tar) mit, und KEIN node-Basisimage liefert die Fix-Version
# 7.5.19 (gemessen 2026-08-22: 22-slim 7.5.11, 24-slim 7.5.16) -- ein Basis-Bump
# behebt das also nicht, Entfernen schon. Gleiche Linie wie node_modules oben.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
USER appuser
EXPOSE 3000
CMD ["node", "build"]
