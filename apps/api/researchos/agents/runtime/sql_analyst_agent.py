"""Read-only SQL analyst over a registered dataset snapshot."""

from __future__ import annotations

import json
import uuid

from researchos.agents.enums import AgentType
from researchos.agents.llm import LLMMessage
from researchos.common.errors import NotFoundError, ValidationError
from researchos.data_lab.models import DatasetSource, SqlQueryResult
from researchos.data_lab.service import execute_snapshot_query
from researchos.missions.models import MissionEvent, ResearchMission

from .base import Agent, AgentContext

_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["sql", "explanation"],
}

_SYSTEM = """You are a read-only SQL analyst. The only table is named dataset.
Use only declared columns. Return exactly one SELECT (or WITH ... SELECT) query. Never use
comments, multiple statements, mutation, DDL, PRAGMA, ATTACH, or unsupported columns.
Return only the requested JSON object."""


class SqlAnalystAgent(Agent):
    agent_type = AgentType.SQL_ANALYST
    allowed_tools: list[str] = []
    response_schema = _SCHEMA

    async def _context(self, actx: AgentContext) -> tuple[ResearchMission, DatasetSource, str]:
        try:
            mission_id = uuid.UUID(str(actx.context["mission_id"]))
            source_id = uuid.UUID(str(actx.context["dataset_source_id"]))
        except (KeyError, ValueError) as exc:
            raise ValidationError(
                "SQL analyst runs require mission_id and dataset_source_id."
            ) from exc
        mission = await actx.db.get(ResearchMission, mission_id)
        source = await actx.db.get(DatasetSource, source_id)
        if mission is None or mission.project_id != actx.project_id:
            raise NotFoundError("Research mission not found for SQL analysis.")
        if source is None or source.project_id != actx.project_id:
            raise NotFoundError("Dataset source not found for SQL analysis.")
        question = str(actx.context.get("question") or actx.message).strip()
        if not question:
            raise ValidationError("SQL analysis question is empty.")
        return mission, source, question

    async def build_messages(self, actx: AgentContext) -> list[LLMMessage]:
        _mission, source, question = await self._context(actx)
        return [
            LLMMessage(role="system", content=_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"Dataset: {source.name}\nDescription: {source.description}\n"
                    f"Table: dataset\nColumns: {json.dumps(source.columns_json)}\n"
                    f"Sample rows: {json.dumps(source.rows_json[:8], ensure_ascii=False)}\n"
                    f"Question: {question}"
                ),
            ),
        ]

    async def finalize(
        self,
        actx: AgentContext,
        *,
        output_text: str,
        whitelist: set[str],
        citation_sources: dict[str, dict],
        usage: dict,
    ) -> tuple[dict, list[dict]]:
        del whitelist, citation_sources, usage
        parsed = json.loads(output_text)
        mission, source, question = await self._context(actx)
        sql = str(parsed.get("sql") or "")
        columns, rows, row_count = execute_snapshot_query(
            source.columns_json, source.rows_json, sql
        )
        result = SqlQueryResult(
            project_id=actx.project_id,
            mission_id=mission.id,
            dataset_source_id=source.id,
            agent_run_id=actx.run.id,
            question=question,
            sql=sql.strip(),
            explanation=str(parsed.get("explanation") or "").strip(),
            columns_json=columns,
            rows_json=rows,
            row_count=row_count,
            created_by=actx.actor.id,
        )
        actx.db.add(result)
        await actx.db.flush()
        actx.db.add(
            MissionEvent(
                project_id=actx.project_id,
                mission_id=mission.id,
                event_type="sql_query.completed",
                summary=f"SQL Agent 完成数据问题：{question[:80]}",
                step_kind=mission.current_step,
                payload_json={
                    "result_id": str(result.id),
                    "dataset_source_id": str(source.id),
                    "agent_run_id": str(actx.run.id),
                    "row_count": row_count,
                },
                actor_id=actx.actor.id,
            )
        )
        return (
            {
                "message": f"Read-only SQL completed with {row_count} result row(s).",
                "sql_query_result_id": str(result.id),
                "sql": result.sql,
                "columns": columns,
                "rows": rows,
                "row_count": row_count,
            },
            [],
        )
