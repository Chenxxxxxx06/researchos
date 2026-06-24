# ResearchOS API

FastAPI backend for ResearchOS. Phase 0 contains only engineering
infrastructure: configuration, structured logging, health/readiness checks, and
database/redis/object-storage connectivity. No business modules.

See the repository root `README.md` for how to run the whole stack, and
`docs/PHASE0_DECISIONS.md` for the architecture decisions.

## Local (without Docker)

```bash
# from apps/api, inside the dedicated environment
uv pip install -e ".[dev]"
uvicorn researchos.main:app --reload --port 8000
```

Endpoints:

- `GET /healthz` — liveness (no external dependencies)
- `GET /readyz`  — readiness (probes PostgreSQL, Redis, object storage)
- `GET /docs`    — OpenAPI UI
