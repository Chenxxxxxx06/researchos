#!/usr/bin/env bash
# Stop the ResearchOS local development stack.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f infra/docker/docker-compose.yml down
