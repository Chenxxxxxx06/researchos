"""Pure security and execution checks for the read-only SQL snapshot sandbox."""

from __future__ import annotations

import pytest

from researchos.common.errors import ValidationError
from researchos.data_lab.service import execute_snapshot_query, validate_read_only_sql


def test_snapshot_query_executes_declared_table_only_in_memory() -> None:
    columns = [
        {"name": "method", "type": "text"},
        {"name": "score", "type": "real"},
    ]
    rows = [
        {"method": "baseline", "score": 0.71},
        {"method": "proposed", "score": 0.79},
    ]

    names, values, count = execute_snapshot_query(
        columns,
        rows,
        "SELECT method, score FROM dataset ORDER BY score DESC",
    )

    assert names == ["method", "score"]
    assert values == [["proposed", 0.79], ["baseline", 0.71]]
    assert count == 2


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM dataset",
        "SELECT * FROM dataset; DROP TABLE dataset",
        "SELECT * FROM dataset -- hide a second statement",
        "PRAGMA table_info(dataset)",
        "ATTACH DATABASE 'x' AS x",
        "SELECT name FROM sqlite_master",
    ],
)
def test_sql_guard_rejects_mutation_comments_and_multiple_statements(sql: str) -> None:
    with pytest.raises(ValidationError):
        validate_read_only_sql(sql)
