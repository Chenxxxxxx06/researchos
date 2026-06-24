"""FastAPI application factory for the ResearchOS API.

Phase 0 wires up infrastructure only: configuration, structured logging,
CORS, request-context middleware, typed error handling, and health endpoints.
Business routers are added in later phases.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from researchos import __version__
from researchos.agents.router import router as agents_router
from researchos.coding_agent.router import router as coding_agent_router
from researchos.common.config import get_settings
from researchos.common.db import dispose_engine
from researchos.common.errors import register_exception_handlers
from researchos.common.logging import configure_logging, get_logger
from researchos.common.middleware import RequestContextMiddleware
from researchos.common.redis import close_redis
from researchos.documents.router import router as documents_router
from researchos.experiments.router import router as experiments_router
from researchos.git.router import router as git_router
from researchos.health.router import router as health_router
from researchos.identity.router import router as auth_router
from researchos.llm_config.router import router as llm_config_router
from researchos.organizations.router import router as organizations_router
from researchos.patches.router import router as patches_router
from researchos.projects.router import router as projects_router
from researchos.research.router import router as research_router
from researchos.skills.router import router as skills_router
from researchos.websocket.router import router as websocket_router
from researchos.workspace.router import router as workspace_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = get_logger(__name__)
    settings = get_settings()
    logger.info("api_startup", environment=settings.environment, version=__version__)
    # Idempotently seed the first-party skill catalog.
    try:
        from researchos.common.db import get_sessionmaker
        from researchos.skills.seed import seed_first_party

        async with get_sessionmaker()() as db:
            created = await seed_first_party(db)
        if created:
            logger.info("seeded_first_party_skills", count=created)
    except Exception as exc:  # noqa: BLE001 - never block startup on seeding
        logger.warning("skill_seed_failed", error=str(exc))
    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()
        logger.info("api_shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="ResearchOS API",
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(organizations_router)
    app.include_router(projects_router)
    app.include_router(research_router)
    app.include_router(agents_router)
    app.include_router(workspace_router)
    app.include_router(patches_router)
    app.include_router(coding_agent_router)
    app.include_router(git_router)
    app.include_router(experiments_router)
    app.include_router(documents_router)
    app.include_router(skills_router)
    app.include_router(llm_config_router)
    app.include_router(websocket_router)

    return app


app = create_app()
