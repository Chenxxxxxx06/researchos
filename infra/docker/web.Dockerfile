# Next.js web app (development image).
# Build context: repository root (needs the workspace manifest and the shared
# package alongside apps/web).
FROM node:20-slim

ENV NODE_ENV=development
WORKDIR /app

RUN corepack enable

# Workspace manifests first for better layer caching.
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared-schemas/package.json packages/shared-schemas/package.json

RUN pnpm install

# Application sources.
COPY apps/web apps/web
COPY packages/shared-schemas packages/shared-schemas

WORKDIR /app/apps/web
EXPOSE 3000
CMD ["pnpm", "dev"]
