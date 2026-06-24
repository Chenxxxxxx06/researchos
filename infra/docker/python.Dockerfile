# Shared image for the FastAPI API and the Celery worker.
# Both apps are installed so the worker can reuse researchos.common.* from the
# API package. The compose file selects which process to run via `command`.
#
# Build context: repository root.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# uv for fast, reproducible installs.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy both Python apps (worker declares a path dependency on the API package).
COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker

# Install both packages (editable) into the system environment.
RUN uv pip install --system -e /app/apps/api -e /app/apps/worker

# Default command runs the API; the worker service overrides it in compose.
WORKDIR /app/apps/api
EXPOSE 8000
CMD ["uvicorn", "researchos.main:app", "--host", "0.0.0.0", "--port", "8000"]
