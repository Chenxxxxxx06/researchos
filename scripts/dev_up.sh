#!/usr/bin/env bash
# Start the ResearchOS local development stack.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f infra/docker/docker-compose.yml up -d --build
echo "Stack starting. Web: http://localhost:3000  API: http://localhost:8000/docs"
