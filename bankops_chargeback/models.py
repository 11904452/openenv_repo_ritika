"""Pydantic models for the banking chargeback operations environment."""

from __future__ import annotations

from typing import Dict, List, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import BaseModel, ConfigDict, Field

try:
    from .constants import ALLOWED_VALUES, ACTION_TYPES, ActionType
except ImportError:
    from constants import ALLOWED_VALUES, ACTION_TYPES, ActionType


class RewardBreakdown(BaseModel):
    """Typed reward detail stored on each observation."""

    progress_delta: float = Field(default=0.0, description="Change in normalized grader score")
    step_penalty: float = Field(default=0.0, description="Small per-step efficiency penalty")
    repeat_penalty: float = Field(default=0.0, description="Penalty for repeating unhelpful actions")
    invalid_action_penalty: float = Field(default=0.0, description="Penalty for invalid actions or values")
    premature_close_penalty: float = Field(default=0.0, description="Penalty for closing before the case is solved")
    success_bonus: float = Field(default=0.0, description="Bonus for completing a case correctly")
    trajectory_score: float = Field(default=0.0, description="Current normalized grader score after the step")


class WorkspaceSnapshot(BaseModel):
    """Current analyst workspace for the chargeback case."""

    dispute_type: Optional[str] = Field(default=None, description="Selected dispute classification")
    priority: Optional[str] = Field(default=None, description="Selected priority")
    assigned_team: Optional[str] = Field(default=None, description="Selected operations team")
    resolution: Optional[str] = Field(default=None, description="Selected case resolution")
    reviewed_sections: List[str] = Field(default_factory=list, description="Sections already inspected")
    closed: bool = Field(default=False, description="Whether the case has been closed")


class GradeReport(BaseModel):
    """Deterministic grader output for a task state."""

    task_id: str
    score: float
    success: bool
    review_score: float
    dispute_type_correct: bool
    priority_correct: bool
    team_correct: bool
    resolution_correct: bool
    missing_reviews: List[str] = Field(default_factory=list)
    mistakes_penalty: float = 0.0


class ChargebackAction(Action):
    """Action emitted by the agent while working a banking dispute case."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "action_type": ActionType.VIEW_TRANSACTION.value,
                    "rationale": "Review the disputed transaction evidence.",
                },
                {
                    "action_type": ActionType.SET_DISPUTE_TYPE.value,
                    "value": "card_not_present_fraud",
                    "rationale": "Classify the case after reviewing evidence and policy.",
                },
            ]
        }
    )

    action_type: ActionType = Field(..., description=f"One of: {', '.join(ACTION_TYPES)}")
    value: Optional[str] = Field(
        default=None,
        description=(
            "Optional value used by set_* actions. Leave empty for view_* actions and close_case."
        ),
    )
    rationale: Optional[str] = Field(default=None, description="Optional analyst note")


class ChargebackObservation(Observation):
    """Observation returned after reset and every step."""

    task_id: str = Field(..., description="Current task identifier")
    difficulty: str = Field(..., description="Task difficulty")
    title: str = Field(..., description="Short case title")
    objective: str = Field(..., description="What the agent must accomplish")
    case_summary: str = Field(..., description="Always-visible dispute summary")
    visible_sections: Dict[str, str] = Field(default_factory=dict, description="Sections the agent has inspected")
    workspace: WorkspaceSnapshot = Field(default_factory=WorkspaceSnapshot, description="Current analyst workspace")
    allowed_values: Dict[str, List[str]] = Field(default_factory=lambda: dict(ALLOWED_VALUES), description="Available action and label choices")
    action_history: List[str] = Field(default_factory=list, description="Ordered action history")
    message: str = Field(default="", description="Status message from the environment")
    last_action_error: Optional[str] = Field(
        default=None,
        description="Structured error for the most recent action, or null when the action succeeded cleanly.",
    )
    remaining_steps: int = Field(default=0, description="How many steps remain before timeout")
    reward_breakdown: RewardBreakdown = Field(default_factory=RewardBreakdown, description="Typed reward detail")
    grader: GradeReport = Field(..., description="Deterministic grader output for the current workspace")


class ChargebackState(State):
    """Internal state exposed through the OpenEnv state endpoint."""

    task_id: Optional[str] = Field(default=None, description="Current task identifier")
    difficulty: Optional[str] = Field(default=None, description="Current task difficulty")
    workspace: WorkspaceSnapshot = Field(default_factory=WorkspaceSnapshot)
    action_history: List[str] = Field(default_factory=list)
    current_score: float = Field(default=0.0, description="Current grader score")
    max_steps: int = Field(default=0, description="Per-task step budget")


__all__ = [
    "ChargebackAction",
    "ChargebackObservation",
    "ChargebackState",
    "GradeReport",
    "RewardBreakdown",
    "WorkspaceSnapshot",
]
