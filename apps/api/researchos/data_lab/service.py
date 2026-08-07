"""Dataset registration, read-only SQL sandbox, and result history."""

from __future__ import annotations

import re
import sqlite3
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.common.errors import NotFoundError, ValidationError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.missions.models import ResearchMission
from researchos.projects.service import ProjectService

from .models import DatasetSource, SqlQueryResult
from .schemas import CreateDatasetSourceRequest

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|reindex|"
    r"replace|begin|commit|rollback|savepoint|release)\b",
    re.IGNORECASE,
)
_COMMENT = re.compile(r"(--|/\*)")


class DataLabService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_source(
        self, actor: User, project_id: uuid.UUID, payload: CreateDatasetSourceRequest
    ) -> DatasetSource:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        source = DatasetSource(
            project_id=project_id,
            name=payload.name.strip(),
            description=payload.description.strip(),
            columns_json=payload.model_dump(mode="json")["columns"],
            rows_json=payload.rows,
            created_by=actor.id,
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def list_sources(self, actor: User, project_id: uuid.UUID) -> list[DatasetSource]:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.VIEWER)
        return list(
            (
                await self.db.execute(
                    select(DatasetSource)
                    .where(DatasetSource.project_id == project_id)
                    .order_by(DatasetSource.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def validate_question(
        self,
        actor: User,
        project_id: uuid.UUID,
        mission_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> DatasetSource:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        mission = await self.db.get(ResearchMission, mission_id)
        source = await self.db.get(DatasetSource, source_id)
        if mission is None or mission.project_id != project_id:
            raise NotFoundError("Research mission not found.")
        if source is None or source.project_id != project_id:
            raise NotFoundError("Dataset source not found.")
        return source

    async def list_results(
        self, actor: User, project_id: uuid.UUID, mission_id: uuid.UUID
    ) -> list[SqlQueryResult]:
        await ProjectService(self.db).ensure_access(actor, project_id, ProjectRole.VIEWER)
        return list(
            (
                await self.db.execute(
                    select(SqlQueryResult)
                    .where(
                        SqlQueryResult.project_id == project_id,
                        SqlQueryResult.mission_id == mission_id,
                    )
                    .order_by(SqlQueryResult.created_at.desc())
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )


def validate_read_only_sql(sql: str) -> str:
    value = sql.strip()
    if value.endswith(";"):
        value = value[:-1].strip()
    if not value or not re.match(r"^(select|with)\b", value, re.IGNORECASE):
        raise ValidationError("SQL Agent may execute SELECT or WITH queries only.")
    if ";" in value or _COMMENT.search(value) or _FORBIDDEN.search(value):
        raise ValidationError("SQL contains a forbidden statement, comment, or multiple commands.")
    if re.search(r"\bsqlite_\w+\b", value, re.IGNORECASE):
        raise ValidationError("SQL may access the registered dataset snapshot only.")
    return value


def execute_snapshot_query(
    columns: list[dict], rows: list[dict], sql: str, *, limit: int = 200
) -> tuple[list[str], list[list[Any]], int]:
    statement = validate_read_only_sql(sql)
    type_map = {"text": "TEXT", "integer": "INTEGER", "real": "REAL", "boolean": "INTEGER"}
    names = [str(column["name"]) for column in columns]
    definitions = ", ".join(
        f'"{name}" {type_map.get(str(column.get("type")), "TEXT")}'
        for name, column in zip(names, columns, strict=True)
    )
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(f'CREATE TABLE "dataset" ({definitions})')
        placeholders = ", ".join("?" for _ in names)
        connection.executemany(
            f'INSERT INTO "dataset" VALUES ({placeholders})',
            [[_cell(row.get(name)) for name in names] for row in rows],
        )
        operations = 0

        def guard() -> int:
            nonlocal operations
            operations += 1
            return 1 if operations > 20_000 else 0

        connection.set_progress_handler(guard, 1000)
        cursor = connection.execute(f"SELECT * FROM ({statement}) AS result LIMIT ?", (limit + 1,))
        output_columns = [item[0] for item in cursor.description or []]
        values = cursor.fetchall()
        total = len(values)
        return output_columns, [list(item) for item in values[:limit]], total
    except sqlite3.Error as exc:
        raise ValidationError(f"Read-only SQL failed: {exc}") from exc
    finally:
        connection.close()


def _cell(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if value is None or isinstance(value, (str, int, float)):
        return value
    return str(value)
