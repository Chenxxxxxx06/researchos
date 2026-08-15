"""Pure acceptance policy for bounded autonomous research loops."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from researchos.common.errors import ValidationError

Direction = Literal["min", "max"]


@dataclass(frozen=True)
class CandidateDecision:
    status: Literal["kept", "discarded"]
    improvement: float
    reasons: tuple[str, ...]
    simplicity_win: bool


def evaluate_candidate(
    *,
    direction: Direction,
    incumbent: float,
    candidate: float,
    min_delta: float,
    complexity_delta: int,
    max_complexity_delta: int,
    critic_score: float,
    critic_threshold: float,
    rule_checks: Mapping[str, bool],
) -> CandidateDecision:
    improvement = candidate - incumbent if direction == "max" else incumbent - candidate
    failed_rules = sorted(name for name, passed in rule_checks.items() if not passed)
    reasons = [f"rule_failed:{name}" for name in failed_rules]
    if not rule_checks:
        reasons.append("rule_checks_missing")
    if critic_score < critic_threshold:
        reasons.append("critic_below_threshold")
    if complexity_delta > max_complexity_delta:
        reasons.append("complexity_budget_exceeded")
    simplicity_win = improvement >= 0 and complexity_delta < 0
    if improvement < min_delta and not simplicity_win:
        reasons.append("metric_not_improved")
    return CandidateDecision(
        status="discarded" if reasons else "kept",
        improvement=improvement,
        reasons=tuple(reasons),
        simplicity_win=simplicity_win,
    )


def stop_reason(
    *, iteration_count: int, no_improvement_count: int, max_iterations: int, patience: int
) -> str | None:
    if iteration_count >= max_iterations:
        return "max_iterations_reached"
    if no_improvement_count >= patience:
        return "no_improvement_patience_reached"
    return None


def validate_changed_paths(
    paths: Sequence[str], *, editable_scopes: Sequence[str], protected_scopes: Sequence[str]
) -> list[str]:
    if not paths:
        raise ValidationError("A research iteration must declare at least one changed path.")
    normalized = [_normalized_relative_path(value) for value in paths]
    editable = [_normalized_scope(value) for value in editable_scopes]
    protected = [_normalized_scope(value) for value in protected_scopes]
    for path in normalized:
        if any(_within(path, scope) for scope in protected):
            raise ValidationError(f"Changed path is protected: {path}")
        if not any(_within(path, scope) for scope in editable):
            raise ValidationError(f"Changed path is outside the editable scope: {path}")
    return normalized


def normalize_scopes(scopes: Sequence[str]) -> list[str]:
    if not scopes:
        raise ValidationError("At least one editable scope is required.")
    return list(dict.fromkeys(_normalized_scope(value) for value in scopes))


def _normalized_relative_path(value: str) -> str:
    clean = value.strip().replace("\\", "/")
    path = PurePosixPath(clean)
    if not clean or path.is_absolute() or ".." in path.parts:
        raise ValidationError("Changed paths must be normalized project-relative paths.")
    return path.as_posix()


def _normalized_scope(value: str) -> str:
    return _normalized_relative_path(value).rstrip("/")


def _within(path: str, scope: str) -> bool:
    return path == scope or path.startswith(f"{scope}/")
