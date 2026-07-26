"""Async figure render job body (worker entry point).

The Celery task in ``apps/worker/researchos_worker/tasks/figures.py`` is a
thin shell around :func:`run_figure_render`. Idempotent under acks-late
redelivery: a re-render simply overwrites the per-format assets.
"""

from __future__ import annotations

import uuid

import structlog

from researchos.common.db import get_sessionmaker

from .enums import FigureRenderStatus
from .events import publish_figure_event
from .repository import FigureRepository

logger = structlog.get_logger(__name__)


async def run_figure_render(figure_id: str) -> None:
    from .figure_service import FigureService

    async with get_sessionmaker()() as db:
        figures = FigureRepository(db)
        figure = await figures.get_by_id(uuid.UUID(figure_id))
        if figure is None:
            logger.warning("figure_render_missing", figure_id=figure_id)
            return

        # Plain-value copies stay usable after a rollback expires ORM attributes.
        fid = figure.id
        project_id = figure.project_id
        name = figure.name

        figure.status = FigureRenderStatus.RENDERING
        await db.commit()
        await publish_figure_event(
            event_type="figure.render.started",
            project_id=project_id,
            figure_id=fid,
            payload={"figure_id": str(fid), "name": name},
        )

        service = FigureService(db)
        try:
            prepared = await service._prepare_render(figure)
            await service._execute_render(figure, prepared, timeout=None)
        except Exception as exc:
            # _execute_render already stamped FAILED for render/persist errors;
            # cover preparation errors (e.g. deleted source run) here.
            if figure.status != FigureRenderStatus.FAILED:
                await db.rollback()
                figure.status = FigureRenderStatus.FAILED
                figure.last_error = str(exc)[:2000]
                await db.commit()
                await publish_figure_event(
                    event_type="figure.render.failed",
                    project_id=project_id,
                    figure_id=fid,
                    payload={"figure_id": str(fid), "name": name, "error": str(exc)[:500]},
                )
            logger.error("figure_render_failed", figure_id=figure_id, error=str(exc))
            return

        await service._publish_completed(figure, prepared)
        logger.info("figure_render_completed", figure_id=figure_id)
