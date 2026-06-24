#!/usr/bin/env bash
# Generate frontend TypeScript types from the API's OpenAPI schema.
#
# Phase 0 placeholder: the API currently exposes only health endpoints. Once
# business endpoints exist, this script will export the OpenAPI document and run
# a generator (e.g. openapi-typescript) into packages/shared-schemas.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Phase 0: no business endpoints to generate types from yet."
echo "The OpenAPI document is available at http://localhost:8000/openapi.json"
