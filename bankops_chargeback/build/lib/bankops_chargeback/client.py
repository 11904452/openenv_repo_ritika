"""Client for the banking chargeback operations environment."""

from __future__ import annotations

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

try:
    from .models import (
        ChargebackAction,
        ChargebackObservation,
        ChargebackState,
        GradeReport,
        RewardBreakdown,
        WorkspaceSnapshot,
    )
except ImportError:
    from models import (
        ChargebackAction,
        ChargebackObservation,
        ChargebackState,
        GradeReport,
        RewardBreakdown,
        WorkspaceSnapshot,
    )


class ChargebackEnv(EnvClient[ChargebackAction, ChargebackObservation, ChargebackState]):
    """Persistent OpenEnv client for the banking chargeback operations desk."""

    def _step_payload(self, action: ChargebackAction) -> Dict:
        return {
            "action_type": action.action_type,
            "value": action.value,
            "rationale": action.rationale,
        }

    def _parse_result(self, payload: Dict) -> StepResult[ChargebackObservation]:
        obs_data = payload.get("observation", {})
        observation = ChargebackObservation(
            task_id=obs_data.get("task_id", ""),
            difficulty=obs_data.get("difficulty", ""),
            title=obs_data.get("title", ""),
            objective=obs_data.get("objective", ""),
            case_summary=obs_data.get("case_summary", ""),
            visible_sections=obs_data.get("visible_sections", {}),
            workspace=WorkspaceSnapshot.model_validate(obs_data.get("workspace", {})),
            allowed_values=obs_data.get("allowed_values", {}),
            action_history=obs_data.get("action_history", []),
            message=obs_data.get("message", ""),
            last_action_error=obs_data.get("last_action_error"),
            remaining_steps=obs_data.get("remaining_steps", 0),
            reward_breakdown=RewardBreakdown.model_validate(obs_data.get("reward_breakdown", {})),
            grader=GradeReport.model_validate(obs_data.get("grader", {})),
            done=payload.get("done", obs_data.get("done", False)),
            reward=payload.get("reward", obs_data.get("reward")),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward", obs_data.get("reward")),
            done=payload.get("done", obs_data.get("done", False)),
        )

    def _parse_state(self, payload: Dict) -> ChargebackState:
        return ChargebackState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id"),
            difficulty=payload.get("difficulty"),
            workspace=WorkspaceSnapshot.model_validate(payload.get("workspace", {})),
            action_history=payload.get("action_history", []),
            current_score=payload.get("current_score", 0.0),
            max_steps=payload.get("max_steps", 0),
        )
