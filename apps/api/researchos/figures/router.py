"""Anchors, figures, and style-preset endpoints (project-scoped)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi.responses import PlainTextResponse

from researchos.common.deps import CurrentUser, DbSession, require_csrf

from .anchor_service import AnchorService
from .figure_service import FigureService
from .presets import PRESETS
from .schemas import (
    AnchorResponse,
    AnchorStalenessResponse,
    CreateAnchorRequest,
    CreateFigureRequest,
    FigureResponse,
    RefreshAnchorsResponse,
    RenderFigureRequest,
    RenderFigureResponse,
    StylePresetResponse,
    UpdateAnchorRequest,
    UpdateFigureRequest,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["figures"])

_ASSET_MEDIA_TYPES = {"svg": "image/svg+xml", "png": "image/png"}


# --- result anchors ----------------------------------------------------------
# Static segments (staleness / macros.tex / refresh) are registered before the
# parameterized /anchors/{anchor_id} routes so they never parse as UUIDs.


@router.get("/anchors", response_model=list[AnchorResponse])
async def list_anchors(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[AnchorResponse]:
    anchors = await AnchorService(db).list_anchors(user, project_id)
    return [AnchorResponse.from_model(a) for a in anchors]


@router.post(
    "/anchors",
    response_model=AnchorResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_anchor(
    project_id: uuid.UUID, payload: CreateAnchorRequest, user: CurrentUser, db: DbSession
) -> AnchorResponse:
    anchor = await AnchorService(db).create_anchor(user, project_id, payload)
    return AnchorResponse.from_model(anchor)


@router.post(
    "/anchors/refresh",
    response_model=RefreshAnchorsResponse,
    dependencies=[Depends(require_csrf)],
)
async def refresh_anchors(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> RefreshAnchorsResponse:
    return await AnchorService(db).refresh_all(user, project_id)


@router.get("/anchors/staleness", response_model=AnchorStalenessResponse)
async def anchors_staleness(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> AnchorStalenessResponse:
    return await AnchorService(db).staleness_report(user, project_id)


@router.get("/anchors/macros.tex")
async def anchors_macros_tex(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession, refresh: bool = True
) -> PlainTextResponse:
    content = await AnchorService(db).macros_tex(user, project_id, refresh=refresh)
    return PlainTextResponse(content, media_type="application/x-tex; charset=utf-8")


@router.get("/anchors/{anchor_id}", response_model=AnchorResponse)
async def get_anchor(
    project_id: uuid.UUID, anchor_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> AnchorResponse:
    anchor = await AnchorService(db).get_anchor(user, project_id, anchor_id)
    return AnchorResponse.from_model(anchor)


@router.patch(
    "/anchors/{anchor_id}", response_model=AnchorResponse, dependencies=[Depends(require_csrf)]
)
async def update_anchor(
    project_id: uuid.UUID,
    anchor_id: uuid.UUID,
    payload: UpdateAnchorRequest,
    user: CurrentUser,
    db: DbSession,
) -> AnchorResponse:
    anchor = await AnchorService(db).update_anchor(user, project_id, anchor_id, payload)
    return AnchorResponse.from_model(anchor)


@router.delete(
    "/anchors/{anchor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_anchor(
    project_id: uuid.UUID, anchor_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    await AnchorService(db).delete_anchor(user, project_id, anchor_id)


# --- figures -----------------------------------------------------------------


@router.get("/figures/style-presets", response_model=list[StylePresetResponse])
async def list_style_presets(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[StylePresetResponse]:
    # Membership check only; the registry itself is global code.
    await FigureService(db).projects.ensure_access(user, project_id)
    return [StylePresetResponse.from_preset(p) for p in PRESETS.values()]


@router.get("/figures", response_model=list[FigureResponse])
async def list_figures(
    project_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[FigureResponse]:
    service = FigureService(db)
    figures = await service.list_figures(user, project_id)
    return [FigureResponse.from_model(f, style_outdated=service.style_outdated(f)) for f in figures]


@router.post(
    "/figures",
    response_model=FigureResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_figure(
    project_id: uuid.UUID, payload: CreateFigureRequest, user: CurrentUser, db: DbSession
) -> FigureResponse:
    service = FigureService(db)
    figure = await service.create_figure(user, project_id, payload)
    return FigureResponse.from_model(figure, style_outdated=False)


@router.get("/figures/{figure_id}", response_model=FigureResponse)
async def get_figure(
    project_id: uuid.UUID, figure_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> FigureResponse:
    service = FigureService(db)
    figure = await service.get_figure(user, project_id, figure_id)
    return FigureResponse.from_model(figure, style_outdated=service.style_outdated(figure))


@router.patch(
    "/figures/{figure_id}", response_model=FigureResponse, dependencies=[Depends(require_csrf)]
)
async def update_figure(
    project_id: uuid.UUID,
    figure_id: uuid.UUID,
    payload: UpdateFigureRequest,
    user: CurrentUser,
    db: DbSession,
) -> FigureResponse:
    service = FigureService(db)
    figure = await service.update_figure(user, project_id, figure_id, payload)
    return FigureResponse.from_model(figure, style_outdated=service.style_outdated(figure))


@router.delete(
    "/figures/{figure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_figure(
    project_id: uuid.UUID, figure_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    await FigureService(db).delete_figure(user, project_id, figure_id)


@router.post(
    "/figures/{figure_id}/render",
    response_model=RenderFigureResponse,
    dependencies=[Depends(require_csrf)],
)
async def render_figure(
    project_id: uuid.UUID,
    figure_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    payload: RenderFigureRequest | None = None,
) -> RenderFigureResponse:
    mode = payload.mode if payload is not None else "async"
    result = await FigureService(db).render(user, project_id, figure_id, mode=mode)
    response.status_code = (
        status.HTTP_200_OK if result.assets else status.HTTP_202_ACCEPTED
    )
    return result


@router.get("/figures/{figure_id}/assets/{fmt}")
async def get_figure_asset(
    project_id: uuid.UUID,
    figure_id: uuid.UUID,
    fmt: Literal["svg", "png"],
    user: CurrentUser,
    db: DbSession,
    if_none_match: str | None = Header(default=None),
) -> Response:
    asset = await FigureService(db).get_asset(user, project_id, figure_id, fmt)
    etag = f'"{asset.sha256}"'
    if if_none_match is not None and if_none_match.strip() in (etag, asset.sha256, f"W/{etag}"):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    return Response(
        content=asset.content,
        media_type=_ASSET_MEDIA_TYPES[fmt],
        headers={"ETag": etag},
    )
