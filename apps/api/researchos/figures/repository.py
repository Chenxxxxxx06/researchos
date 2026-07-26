"""Figures data access: anchors, figures, rendered assets."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Figure, FigureAsset, ResultAnchor


class AnchorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, anchor: ResultAnchor) -> ResultAnchor:
        self.db.add(anchor)
        await self.db.flush()
        return anchor

    async def get(self, project_id: uuid.UUID, anchor_id: uuid.UUID) -> ResultAnchor | None:
        anchor = await self.db.get(ResultAnchor, anchor_id)
        return anchor if anchor and anchor.project_id == project_id else None

    async def get_by_name(self, project_id: uuid.UUID, name: str) -> ResultAnchor | None:
        return await self.db.scalar(
            select(ResultAnchor).where(
                ResultAnchor.project_id == project_id, ResultAnchor.name == name
            )
        )

    async def list_by_project(self, project_id: uuid.UUID) -> list[ResultAnchor]:
        result = await self.db.execute(
            select(ResultAnchor)
            .where(ResultAnchor.project_id == project_id)
            .order_by(ResultAnchor.name)
        )
        return list(result.scalars().all())

    async def list_for_experiment(self, experiment_id: uuid.UUID) -> list[ResultAnchor]:
        result = await self.db.execute(
            select(ResultAnchor)
            .where(ResultAnchor.experiment_id == experiment_id)
            .order_by(ResultAnchor.name)
        )
        return list(result.scalars().all())

    async def delete(self, anchor: ResultAnchor) -> None:
        await self.db.delete(anchor)


class FigureRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, figure: Figure) -> Figure:
        self.db.add(figure)
        await self.db.flush()
        return figure

    async def get(self, project_id: uuid.UUID, figure_id: uuid.UUID) -> Figure | None:
        figure = await self.db.get(Figure, figure_id)
        return figure if figure and figure.project_id == project_id else None

    async def get_by_id(self, figure_id: uuid.UUID) -> Figure | None:
        """Unscoped load for the internal render job (no request context)."""

        return await self.db.get(Figure, figure_id)

    async def get_by_name(self, project_id: uuid.UUID, name: str) -> Figure | None:
        return await self.db.scalar(
            select(Figure).where(Figure.project_id == project_id, Figure.name == name)
        )

    async def list_by_project(self, project_id: uuid.UUID) -> list[Figure]:
        result = await self.db.execute(
            select(Figure).where(Figure.project_id == project_id).order_by(Figure.name)
        )
        return list(result.scalars().all())

    async def delete(self, figure: Figure) -> None:
        await self.db.delete(figure)


class FigureAssetRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, figure_id: uuid.UUID, fmt: str) -> FigureAsset | None:
        return await self.db.scalar(
            select(FigureAsset).where(
                FigureAsset.figure_id == figure_id, FigureAsset.format == fmt
            )
        )

    async def upsert(
        self,
        figure_id: uuid.UUID,
        fmt: str,
        *,
        content: bytes,
        sha256: str,
        size_bytes: int,
        rendered_at: datetime,
    ) -> FigureAsset:
        """Keep only the latest render per (figure, format)."""

        asset = await self.get(figure_id, fmt)
        if asset is None:
            asset = FigureAsset(
                figure_id=figure_id,
                format=fmt,
                content=content,
                sha256=sha256,
                size_bytes=size_bytes,
                rendered_at=rendered_at,
            )
            self.db.add(asset)
        else:
            asset.content = content
            asset.sha256 = sha256
            asset.size_bytes = size_bytes
            asset.rendered_at = rendered_at
        await self.db.flush()
        return asset
