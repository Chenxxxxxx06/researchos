# ResearchOS Worker

Celery worker for ResearchOS. Phase 0 provides a single worker process with
queue routing for the six planned workloads (`agents`, `ingestion`, `runtime`,
`latex`, `experiments`, `skills`) and health tasks only. In production these
queues are split across dedicated worker deployments.

The worker reuses configuration, logging, and connectivity probes from the
`researchos-api` package.

## Local (without Docker)

```bash
# from apps/worker, inside the dedicated environment
uv pip install -e ".[dev]"
celery -A researchos_worker.app worker --loglevel=info --queues=agents,ingestion,runtime,latex,experiments,skills
```
