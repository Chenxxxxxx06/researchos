"""Pure DAG validation tests."""

import pytest

from researchos.common.errors import ValidationError
from researchos.orchestration.service import (
    _DEPENDENCIES,
    _GATES,
    _TASK_TEMPLATE,
    validate_acyclic,
)


def test_validate_acyclic_accepts_parallel_dag() -> None:
    validate_acyclic(
        {"scope", "read", "code", "experiment"},
        [("read", "scope"), ("code", "scope"), ("experiment", "read"), ("experiment", "code")],
    )


def test_standard_graph_template_has_unique_valid_references() -> None:
    task_keys = [str(item["key"]) for item in _TASK_TEMPLATE]
    gate_keys = [(task_key, gate_kind) for task_key, gate_kind, _, _ in _GATES]

    assert len(task_keys) == 17
    assert len(task_keys) == len(set(task_keys))
    assert len(_DEPENDENCIES) == len(set(_DEPENDENCIES))
    assert len(gate_keys) == len(set(gate_keys))
    assert all(task_key in task_keys for task_key, _, _, _ in _GATES)
    validate_acyclic(set(task_keys), list(_DEPENDENCIES))


@pytest.mark.parametrize(
    "edges",
    [
        [("scope", "scope")],
        [("scope", "missing")],
        [("scope", "read"), ("read", "scope")],
    ],
)
def test_validate_acyclic_rejects_invalid_graph(edges: list[tuple[str, str]]) -> None:
    with pytest.raises(ValidationError):
        validate_acyclic({"scope", "read"}, edges)
