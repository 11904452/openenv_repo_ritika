"""Deterministic graders for the banking chargeback operations tasks."""

from __future__ import annotations

from typing import Callable, Dict

try:
    from .models import GradeReport, WorkspaceSnapshot
    from .tasks import ChargebackTask, TASKS
except ImportError:
    from models import GradeReport, WorkspaceSnapshot
    from tasks import ChargebackTask, TASKS

REVIEW_WEIGHT = 0.25
DISPUTE_WEIGHT = 0.20
PRIORITY_WEIGHT = 0.10
TEAM_WEIGHT = 0.15
RESOLUTION_WEIGHT = 0.20
CLOSE_WEIGHT = 0.10
MISTAKE_PENALTY_PER_EVENT = 0.02
MAX_MISTAKE_PENALTY = 0.10


def grade_task(task: ChargebackTask, workspace: WorkspaceSnapshot, mistakes: int = 0) -> GradeReport:
    """Score the current workspace against the deterministic target for a task."""

    reviewed = set(workspace.reviewed_sections)
    required_reviews = set(task.required_reviews)
    review_fraction = len(reviewed & required_reviews) / len(required_reviews)

    dispute_type_correct = workspace.dispute_type == task.expected_dispute_type
    priority_correct = workspace.priority == task.expected_priority
    team_correct = workspace.assigned_team == task.expected_team
    resolution_correct = workspace.resolution == task.expected_resolution
    all_reviews_complete = required_reviews.issubset(reviewed)
    success = all(
        [
            dispute_type_correct,
            priority_correct,
            team_correct,
            resolution_correct,
            all_reviews_complete,
            workspace.closed,
        ]
    )

    raw_score = (
        review_fraction * REVIEW_WEIGHT
        + (DISPUTE_WEIGHT if dispute_type_correct else 0.0)
        + (PRIORITY_WEIGHT if priority_correct else 0.0)
        + (TEAM_WEIGHT if team_correct else 0.0)
        + (RESOLUTION_WEIGHT if resolution_correct else 0.0)
        + (CLOSE_WEIGHT if success else 0.0)
    )

    mistakes_penalty = min(mistakes * MISTAKE_PENALTY_PER_EVENT, MAX_MISTAKE_PENALTY)
    score = max(0.0, min(1.0, raw_score - mistakes_penalty))

    return GradeReport(
        task_id=task.task_id,
        score=round(score, 4),
        success=success,
        review_score=round(review_fraction, 4),
        dispute_type_correct=dispute_type_correct,
        priority_correct=priority_correct,
        team_correct=team_correct,
        resolution_correct=resolution_correct,
        missing_reviews=sorted(required_reviews - reviewed),
        mistakes_penalty=round(mistakes_penalty, 4),
    )


def _task_grader(task_id: str) -> Callable[[WorkspaceSnapshot, int], GradeReport]:
    task = TASKS[task_id]

    def _grade(workspace: WorkspaceSnapshot, mistakes: int = 0) -> GradeReport:
        return grade_task(task, workspace, mistakes=mistakes)

    return _grade


grade_easy_case = _task_grader("easy_unauthorized_card_not_present")
grade_medium_case = _task_grader("medium_subscription_confusion")
grade_hard_case = _task_grader("hard_wallet_account_takeover")
grade_medium_duplicate = _task_grader("medium_duplicate_processing_error")
grade_hard_friendly_fraud = _task_grader("hard_friendly_fraud_denial")
grade_expert_mixed_signals = _task_grader("expert_mixed_signals_tight_budget")

TASK_GRADERS: Dict[str, Callable[[WorkspaceSnapshot, int], GradeReport]] = {
    "easy_unauthorized_card_not_present": grade_easy_case,
    "medium_subscription_confusion": grade_medium_case,
    "hard_wallet_account_takeover": grade_hard_case,
    "medium_duplicate_processing_error": grade_medium_duplicate,
    "hard_friendly_fraud_denial": grade_hard_friendly_fraud,
    "expert_mixed_signals_tight_budget": grade_expert_mixed_signals,
}


__all__ = [
    "TASK_GRADERS",
    "grade_easy_case",
    "grade_expert_mixed_signals",
    "grade_hard_case",
    "grade_hard_friendly_fraud",
    "grade_medium_case",
    "grade_medium_duplicate",
    "grade_task",
]
