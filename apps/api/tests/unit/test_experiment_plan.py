"""Pure release-gate checks for structured experiment plans."""

from __future__ import annotations

import uuid

from researchos.experiment_plans.models import ExperimentPlan
from researchos.experiment_plans.service import publish_issues


def _plan() -> ExperimentPlan:
    actor = uuid.uuid4()
    return ExperimentPlan(
        project_id=uuid.uuid4(),
        mission_id=uuid.uuid4(),
        title="Primary comparison",
        research_gap="A verified review gap.",
        hypothesis="The treatment improves the primary score.",
        variables_json=[
            {"name": "treatment", "role": "independent"},
            {"name": "score", "role": "dependent"},
            {"name": "budget", "role": "control"},
        ],
        baselines_json=[{"name": "B0", "evidence_status": "grounded"}],
        datasets_json=[{"name": "D", "split": "train/test"}],
        metrics_json=[{"name": "score", "direction": "max", "primary": True}],
        matrix_json=[{"name": "main", "repetitions": 3}],
        decision_rules_json=["Accept only after the predeclared comparison."],
        stop_conditions_json=["Stop after three seeds."],
        risks_json=[{"risk": "leakage", "mitigation": "held-out test"}],
        reproducibility_json=["Pin code and data revisions."],
        created_by=actor,
        updated_by=actor,
    )


def test_publish_gate_accepts_complete_plan() -> None:
    assert publish_issues(_plan()) == []


def test_publish_gate_reports_unresolved_evidence_and_missing_controls() -> None:
    plan = _plan()
    plan.baselines_json[0]["evidence_status"] = "needs_evidence"
    plan.variables_json = [item for item in plan.variables_json if item["role"] != "control"]

    issues = publish_issues(plan)

    assert "missing control variable" in issues
    assert "baseline evidence is unresolved" in issues
