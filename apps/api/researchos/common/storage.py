"""Object-storage connectivity probe.

Phase 0 does not perform real uploads/downloads; it only verifies that the
S3-compatible endpoint (MinIO in local development) is reachable. We probe the
MinIO health endpoint over HTTP to avoid pulling in a full S3 SDK this early.
The actual storage abstraction is introduced when a phase needs to persist
artifacts.
"""

from __future__ import annotations

import httpx

from .config import get_settings


async def check_object_storage() -> None:
    """Raise if the object-storage endpoint is unreachable.

    MinIO exposes ``/minio/health/live``. For a generic S3 endpoint we fall back
    to a plain reachability check of the base URL.
    """

    settings = get_settings()
    base = settings.s3_endpoint_url.rstrip("/")
    health_url = f"{base}/minio/health/live"

    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            resp = await client.get(health_url)
            if resp.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        # Fallback: any response from the base endpoint proves reachability.
        resp = await client.get(base)
        resp.raise_for_status()
