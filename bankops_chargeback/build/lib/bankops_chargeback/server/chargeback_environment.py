"""Banking chargeback operations environment implementation."""

from __future__ import annotations

from typing import Dict, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import EnvironmentMetadata

try:
    from ..constants import ACTION_TYPES, ALLOWED_VALUES, SECTION_TITLES, SECTION_TO_ACTION
    from ..graders import grade_task
    from ..models import (
        ChargebackAction,
        ChargebackObservation,
        ChargebackState,
        RewardBreakdown,
        WorkspaceSnapshot,
    )
    from ..tasks import ChargebackTask, choose_task
except ImportError:
    from constants import ACTION_TYPES, ALLOWED_VALUES, SECTION_TITLES, SECTION_TO_ACTION
    from graders import grade_task
    from models import (
        ChargebackAction,
        ChargebackObservation,
        ChargebackState,
        RewardBreakdown,
        WorkspaceSnapshot,
    )
    from tasks import ChargebackTask, choose_task


class ChargebackOpsEnvironment(Environment):
    """Real-world banking operations environment for chargeback and fraud triage."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        super().__init__()
        self._task_cursor = 0
        self._mistakes = 0
        self._current_task: Optional[ChargebackTask] = None
        self._state = ChargebackState(episode_id=str(uuid4()), step_count=0)

    def get_metadata(self) -> EnvironmentMetadata:
        return EnvironmentMetadata(
            name="BankOps Chargeback Operations Desk",
            description=(
                "A deterministic banking operations environment where agents triage payment "
                "disputes, review case evidence, and route chargeback cases correctly."
            ),
            version="1.0.0",
            author="Roopesh and Ritika",
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: Optional[str] = None,
        **_: object,
    ) -> ChargebackObservation:
        self._current_task = choose_task(task_id=task_id, seed=seed, cursor=self._task_cursor)
        self._task_cursor += 1
        self._mistakes = 0
        self._state = ChargebackState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=self._current_task.task_id,
            difficulty=self._current_task.difficulty,
            workspace=WorkspaceSnapshot(),
            action_history=[],
            current_score=0.0,
            max_steps=self._current_task.max_steps,
        )
        return self._build_observation(
            message=(
                f"Loaded task '{self._current_task.task_id}'. Review the case and close it with the "
                "correct banking operations decision."
            ),
            last_action_error=None,
            reward=0.0,
            done=False,
            breakdown=RewardBreakdown(),
        )

    def step(
        self,
        action: ChargebackAction,
        timeout_s: Optional[float] = None,
        **_: object,
    ) -> ChargebackObservation:
        del timeout_s
        if self._current_task is None:
            raise RuntimeError("Call reset() before step().")

        if self._state.workspace.closed:
            self._mistakes += 1
            breakdown = RewardBreakdown(
                invalid_action_penalty=-0.08,
                trajectory_score=self._state.current_score,
            )
            return self._build_observation(
                message="The case is already closed. Reset the environment to start a new dispute.",
                last_action_error="The case is already closed. Reset the environment to start a new dispute.",
                reward=-0.08,
                done=True,
                breakdown=breakdown,
            )

        previous_grade = grade_task(self._current_task, self._state.workspace, mistakes=self._mistakes)
        self._state.step_count += 1
        step_penalty = -0.01
        repeat_penalty = 0.0
        invalid_action_penalty = 0.0
        premature_close_penalty = 0.0
        success_bonus = 0.0
        message = "Action recorded."
        last_action_error: Optional[str] = None

        action_record = self._format_action(action)
        self._state.action_history.append(action_record)

        if action.action_type not in ACTION_TYPES:
            self._mistakes += 1
            invalid_action_penalty -= 0.08
            message = f"Unknown action_type '{action.action_type}'."
            last_action_error = message
        elif action.action_type.startswith("view_"):
            message, repeat_penalty = self._handle_view_action(action.action_type)
            if repeat_penalty < 0:
                last_action_error = message
        elif action.action_type == "set_dispute_type":
            message, repeat_penalty, invalid_action_penalty = self._set_value(
                field_name="dispute_type",
                value=action.value,
                allowed_key="dispute_type",
                success_label="dispute type",
            )
            if repeat_penalty < 0 or invalid_action_penalty < 0:
                last_action_error = message
        elif action.action_type == "set_priority":
            message, repeat_penalty, invalid_action_penalty = self._set_value(
                field_name="priority",
                value=action.value,
                allowed_key="priority",
                success_label="priority",
            )
            if repeat_penalty < 0 or invalid_action_penalty < 0:
                last_action_error = message
        elif action.action_type == "assign_team":
            message, repeat_penalty, invalid_action_penalty = self._set_value(
                field_name="assigned_team",
                value=action.value,
                allowed_key="team",
                success_label="assigned team",
            )
            if repeat_penalty < 0 or invalid_action_penalty < 0:
                last_action_error = message
        elif action.action_type == "set_resolution":
            message, repeat_penalty, invalid_action_penalty = self._set_value(
                field_name="resolution",
                value=action.value,
                allowed_key="resolution",
                success_label="resolution",
            )
            if repeat_penalty < 0 or invalid_action_penalty < 0:
                last_action_error = message
        elif action.action_type == "close_case":
            self._state.workspace.closed = True
            message = "Case closure submitted for grading."
        else:
            self._mistakes += 1
            invalid_action_penalty -= 0.08
            message = f"Action '{action.action_type}' is not implemented."
            last_action_error = message

        current_grade = grade_task(self._current_task, self._state.workspace, mistakes=self._mistakes)
        done = False

        if action.action_type == "close_case":
            done = True
            if current_grade.success:
                success_bonus = 0.15
                message = "Case closed correctly. The dispute was routed and resolved according to policy."
            else:
                self._mistakes += 1
                current_grade = grade_task(self._current_task, self._state.workspace, mistakes=self._mistakes)
                premature_close_penalty -= 0.15
                missing = ", ".join(current_grade.missing_reviews) or "some required decisions"
                message = f"Case closed too early or with the wrong outcome. Missing or incorrect items: {missing}."
                last_action_error = message
        elif self._state.step_count >= self._current_task.max_steps:
            done = True
            self._state.workspace.closed = True
            current_grade = grade_task(self._current_task, self._state.workspace, mistakes=self._mistakes)
            if current_grade.success:
                success_bonus = 0.15
                message = "Case auto-closed correctly at the step budget."
            else:
                self._mistakes += 1
                current_grade = grade_task(self._current_task, self._state.workspace, mistakes=self._mistakes)
                premature_close_penalty -= 0.10
                message = "Step budget exhausted before the case was completed."
                last_action_error = message

        progress_delta = round(current_grade.score - previous_grade.score, 4)
        reward = round(
            progress_delta
            + step_penalty
            + repeat_penalty
            + invalid_action_penalty
            + premature_close_penalty
            + success_bonus,
            4,
        )

        self._state.current_score = current_grade.score
        breakdown = RewardBreakdown(
            progress_delta=progress_delta,
            step_penalty=step_penalty,
            repeat_penalty=repeat_penalty,
            invalid_action_penalty=invalid_action_penalty,
            premature_close_penalty=premature_close_penalty,
            success_bonus=success_bonus,
            trajectory_score=current_grade.score,
        )
        return self._build_observation(
            message=message,
            last_action_error=last_action_error,
            reward=reward,
            done=done,
            breakdown=breakdown,
        )

    @property
    def state(self) -> ChargebackState:
        return self._state

    def _handle_view_action(self, action_type: str) -> tuple[str, float]:
        assert self._current_task is not None
        section_name = next(
            section for section, section_action in SECTION_TO_ACTION.items() if section_action == action_type
        )
        if section_name in self._state.workspace.reviewed_sections:
            self._mistakes += 1
            return f"{SECTION_TITLES[section_name]} was already reviewed.", -0.03

        self._state.workspace.reviewed_sections.append(section_name)
        return f"Opened {SECTION_TITLES[section_name]}.", 0.0

    def _set_value(
        self,
        field_name: str,
        value: Optional[str],
        allowed_key: str,
        success_label: str,
    ) -> tuple[str, float, float]:
        if not value:
            self._mistakes += 1
            return f"Action requires a value for {success_label}.", 0.0, -0.08

        allowed_values = ALLOWED_VALUES[allowed_key]
        if value not in allowed_values:
            self._mistakes += 1
            return (
                f"'{value}' is not a valid {success_label}. Allowed values: {', '.join(allowed_values)}.",
                0.0,
                -0.08,
            )

        current_value = getattr(self._state.workspace, field_name)
        if current_value == value:
            self._mistakes += 1
            return f"{success_label.title()} is already set to '{value}'.", -0.03, 0.0

        setattr(self._state.workspace, field_name, value)
        return f"Set {success_label} to '{value}'.", 0.0, 0.0

    def _build_observation(
        self,
        message: str,
        last_action_error: Optional[str],
        reward: float,
        done: bool,
        breakdown: RewardBreakdown,
    ) -> ChargebackObservation:
        assert self._current_task is not None
        grader = grade_task(self._current_task, self._state.workspace, mistakes=self._mistakes)
        remaining_steps = max(self._current_task.max_steps - self._state.step_count, 0)
        visible_sections: Dict[str, str] = {}
        for section_name in self._state.workspace.reviewed_sections:
            if section_name == "customer_profile":
                visible_sections[section_name] = self._current_task.customer_profile
            elif section_name == "transaction":
                visible_sections[section_name] = self._current_task.transaction_details
            elif section_name == "recent_activity":
                visible_sections[section_name] = self._current_task.recent_activity
            elif section_name == "policy":
                visible_sections[section_name] = self._current_task.policy_excerpt

        observation = ChargebackObservation(
            task_id=self._current_task.task_id,
            difficulty=self._current_task.difficulty,
            title=self._current_task.title,
            objective=self._current_task.objective,
            case_summary=self._current_task.case_summary,
            visible_sections=visible_sections,
            workspace=self._state.workspace.model_copy(deep=True),
            action_history=list(self._state.action_history),
            message=message,
            last_action_error=last_action_error,
            remaining_steps=remaining_steps,
            reward_breakdown=breakdown,
            grader=grader,
            done=done,
            reward=reward,
            metadata={
                "task_id": self._current_task.task_id,
                "difficulty": self._current_task.difficulty,
                "required_reviews": list(self._current_task.required_reviews),
                "allowed_values": ALLOWED_VALUES,
                "grader": grader.model_dump(),
                "step_count": self._state.step_count,
                "mistakes": self._mistakes,
            },
        )
        return self._apply_transform(observation)

    def _format_action(self, action: ChargebackAction) -> str:
        if action.value:
            return f"{action.action_type}:{action.value}"
        return action.action_type


__all__ = ["ChargebackOpsEnvironment"]
