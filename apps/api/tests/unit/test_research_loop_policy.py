"""Acceptance and safety invariants for autonomous research loops."""

import pytest

from researchos.common.errors import ValidationError
from researchos.orchestration.loop_policy import (
    evaluate_candidate,
    normalize_scopes,
    stop_reason,
    validate_changed_paths,
)


def test_candidate_is_kept_only_when_metric_and_gates_pass() -> None:
    decision = evaluate_candidate(
        direction="min",
        incumbent=1.0,
        candidate=0.92,
        min_delta=0.01,
        complexity_delta=12,
        max_complexity_delta=100,
        critic_score=0.84,
        critic_threshold=0.7,
        rule_checks={"reproducible": True, "integrity": True},
    )
    assert decision.status == "kept"
    assert decision.improvement == pytest.approx(0.08)
    assert decision.reasons == ()


def test_candidate_is_discarded_when_any_independent_gate_fails() -> None:
    decision = evaluate_candidate(
        direction="max",
        incumbent=0.8,
        candidate=0.85,
        min_delta=0.01,
        complexity_delta=220,
        max_complexity_delta=100,
        critic_score=0.4,
        critic_threshold=0.7,
        rule_checks={"reproducible": False, "integrity": True},
    )
    assert decision.status == "discarded"
    assert set(decision.reasons) == {
        "rule_failed:reproducible",
        "critic_below_threshold",
        "complexity_budget_exceeded",
    }


def test_simplification_can_be_kept_without_metric_regression() -> None:
    decision = evaluate_candidate(
        direction="max",
        incumbent=0.8,
        candidate=0.8,
        min_delta=0.01,
        complexity_delta=-30,
        max_complexity_delta=100,
        critic_score=0.9,
        critic_threshold=0.7,
        rule_checks={"reproducible": True},
    )
    assert decision.status == "kept"
    assert decision.simplicity_win is True


@pytest.mark.parametrize(
    ("iteration_count", "no_improvement_count", "expected"),
    [
        (12, 0, "max_iterations_reached"),
        (3, 4, "no_improvement_patience_reached"),
        (3, 1, None),
    ],
)
def test_loop_stop_conditions(
    iteration_count: int, no_improvement_count: int, expected: str | None
) -> None:
    assert (
        stop_reason(
            iteration_count=iteration_count,
            no_improvement_count=no_improvement_count,
            max_iterations=12,
            patience=4,
        )
        == expected
    )


def test_changed_paths_must_stay_inside_editable_scope() -> None:
    assert validate_changed_paths(
        ["src/model.py", "src/layers/attention.py"],
        editable_scopes=["src"],
        protected_scopes=["src/eval.py"],
    ) == ["src/model.py", "src/layers/attention.py"]


@pytest.mark.parametrize(
    "path",
    ["../secrets.env", "/etc/passwd", "prepare.py", "src/eval.py"],
)
def test_changed_paths_reject_escape_and_protected_files(path: str) -> None:
    with pytest.raises(ValidationError):
        validate_changed_paths(
            [path], editable_scopes=["src"], protected_scopes=["src/eval.py"]
        )


def test_scope_normalization_is_stable_and_deduplicated() -> None:
    assert normalize_scopes(["src/", "src", "configs\\train"]) == [
        "src",
        "configs/train",
    ]
