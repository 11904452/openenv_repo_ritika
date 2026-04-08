"""Custom Gradio UI helpers for the chargeback environment."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    from ..constants import ACTION_TYPES, DISPUTE_TYPES, PRIORITIES, RESOLUTIONS, TEAMS
    from ..tasks import TASKS
except ImportError:
    from constants import ACTION_TYPES, DISPUTE_TYPES, PRIORITIES, RESOLUTIONS, TEAMS
    from tasks import TASKS


DIFFICULTY_GROUPS: Dict[str, tuple[str, ...]] = {
    "easy": ("easy",),
    "medium": ("medium",),
    "difficult": ("hard", "expert"),
}

DIFFICULTY_GROUP_CHOICES = [
    ("Easy", "easy"),
    ("Medium", "medium"),
    ("Difficult (Hard + Expert)", "difficult"),
]

VALUE_CHOICES_BY_ACTION: Dict[str, List[str]] = {
    "set_dispute_type": list(DISPUTE_TYPES),
    "set_priority": list(PRIORITIES),
    "assign_team": list(TEAMS),
    "set_resolution": list(RESOLUTIONS),
}

VALUE_REQUIRED_ACTIONS = frozenset(VALUE_CHOICES_BY_ACTION)


def get_task_choices(difficulty_group: str) -> List[str]:
    """Return task ids visible for a difficulty group."""

    allowed_difficulties = DIFFICULTY_GROUPS.get(
        difficulty_group,
        tuple(task.difficulty for task in TASKS.values()),
    )
    return [
        task_id
        for task_id, task in TASKS.items()
        if task.difficulty in allowed_difficulties
    ]


def get_default_task_id(difficulty_group: str) -> Optional[str]:
    """Return the first task id for a difficulty group."""

    choices = get_task_choices(difficulty_group)
    return choices[0] if choices else None


def action_requires_value(action_type: Optional[str]) -> bool:
    """Return True when the action needs a value."""

    return bool(action_type in VALUE_REQUIRED_ACTIONS)


def value_options_for_action(action_type: Optional[str]) -> List[str]:
    """Return valid values for an action."""

    return VALUE_CHOICES_BY_ACTION.get(action_type or "", [])


def get_task_details_markdown(task_id: Optional[str]) -> str:
    """Format task metadata for the custom UI."""

    if not task_id:
        return "### Task Details\n\nSelect a task and click **Reset** to start."

    task = TASKS[task_id]
    required_reviews = ", ".join(task.required_reviews)
    return (
        f"### {task.title}\n\n"
        f"- `task_id`: `{task.task_id}`\n"
        f"- difficulty: `{task.difficulty}`\n"
        f"- required reviews: `{required_reviews}`\n"
        f"- max steps: `{task.max_steps}`\n\n"
        f"**Objective:** {task.objective}"
    )


def _format_observation_markdown(data: Dict[str, Any]) -> str:
    """Render a compact observation summary for the custom UI."""

    observation = data.get("observation", {})
    workspace = observation.get("workspace", {})
    reviewed_sections = workspace.get("reviewed_sections") or []
    reviewed_lines = [f"- `{section}`" for section in reviewed_sections] or ["- none"]
    current_assignments = [
        f"- dispute type: `{workspace.get('dispute_type') or 'unset'}`",
        f"- priority: `{workspace.get('priority') or 'unset'}`",
        f"- assigned team: `{workspace.get('assigned_team') or 'unset'}`",
        f"- resolution: `{workspace.get('resolution') or 'unset'}`",
        f"- closed: `{workspace.get('closed', False)}`",
    ]

    lines = [
        f"## {observation.get('title', 'Observation')}",
        "",
        f"- task id: `{observation.get('task_id', '')}`",
        f"- difficulty: `{observation.get('difficulty', '')}`",
        f"- remaining steps: `{observation.get('remaining_steps', 0)}`",
        f"- reward: `{data.get('reward')}`",
        f"- done: `{data.get('done')}`",
        "",
        f"**Message:** {observation.get('message', '')}",
        "",
        "**Reviewed sections**",
    ]
    lines.extend(reviewed_lines)
    lines.extend(["", "**Workspace**"])
    lines.extend(current_assignments)
    return "\n".join(lines)


def build_chargeback_gradio_app(
    web_manager: Any,
    action_fields: List[Dict[str, Any]],
    metadata: Any,
    is_chat_env: bool,
    title: str,
    quick_start_md: Optional[str],
):
    """Return a custom Gradio tab with task selection and action guidance."""

    del action_fields, is_chat_env, title, quick_start_md

    import gradio as gr

    initial_group = "easy"
    initial_task_id = get_default_task_id(initial_group)

    async def reset_with_selected_task(difficulty_group: str, task_id: Optional[str]):
        selected_task_id = task_id or get_default_task_id(difficulty_group)
        if not selected_task_id:
            return (
                "",
                "",
                "No task is available for the selected difficulty group.",
            )

        data = await web_manager.reset_environment({"task_id": selected_task_id})
        return (
            _format_observation_markdown(data),
            json.dumps(data, indent=2),
            f"Environment reset with task '{selected_task_id}'.",
        )

    async def step_with_action(
        action_type: Optional[str],
        value: Optional[str],
        rationale: Optional[str],
    ):
        if not action_type:
            return ("", "", "Choose an action before stepping.")

        action_data: Dict[str, Any] = {"action_type": action_type}

        if action_requires_value(action_type):
            if not value:
                return (
                    "",
                    "",
                    f"Value is required for '{action_type}'. Choose one from the dropdown first.",
                )
            action_data["value"] = value

        if rationale and str(rationale).strip():
            action_data["rationale"] = str(rationale).strip()

        data = await web_manager.step_environment(action_data)
        return (
            _format_observation_markdown(data),
            json.dumps(data, indent=2),
            "Step complete.",
        )

    def update_tasks_for_group(difficulty_group: str):
        task_choices = get_task_choices(difficulty_group)
        selected_task_id = task_choices[0] if task_choices else None
        return (
            gr.update(choices=task_choices, value=selected_task_id),
            get_task_details_markdown(selected_task_id),
        )

    def update_task_details(task_id: Optional[str]):
        return get_task_details_markdown(task_id)

    def update_value_control(action_type: Optional[str]):
        if action_requires_value(action_type):
            choices = value_options_for_action(action_type)
            return (
                gr.update(choices=choices, value=None, interactive=True),
                f"Value is required for `{action_type}`.",
            )

        return (
            gr.update(choices=[], value=None, interactive=False),
            "Value is not used for this action.",
        )

    def get_state_sync():
        try:
            return json.dumps(web_manager.get_state(), indent=2)
        except Exception as exc:
            return f"Error: {exc}"

    readme_preview = metadata.readme_content if metadata and metadata.readme_content else ""
    intro_lines = [
        "### Guided Chargeback UI",
        "",
        "Use **Reset** to choose a specific task.",
        "Use **Step** to send one action at a time.",
        "The selected task applies on the next reset.",
        "",
        "**Value is mandatory for:** `set_dispute_type`, `set_priority`, `assign_team`, `set_resolution`.",
    ]
    if readme_preview:
        intro_lines.extend(["", "**README is available in the main Playground tab as well.**"])

    with gr.Blocks(title="Chargeback Custom UI") as demo:
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("\n".join(intro_lines))
                difficulty_group = gr.Dropdown(
                    choices=DIFFICULTY_GROUP_CHOICES,
                    value=initial_group,
                    label="Difficulty Group",
                    allow_custom_value=False,
                )
                task_selector = gr.Dropdown(
                    choices=get_task_choices(initial_group),
                    value=initial_task_id,
                    label="Task",
                    allow_custom_value=False,
                )
                task_details = gr.Markdown(get_task_details_markdown(initial_task_id))
                reset_btn = gr.Button("Reset With Selected Task", variant="secondary")

            with gr.Column(scale=2):
                response_md = gr.Markdown(
                    value="## Ready\n\nChoose a task, then click **Reset With Selected Task**."
                )
                with gr.Group():
                    action_type = gr.Dropdown(
                        choices=list(ACTION_TYPES),
                        value="view_transaction",
                        label="Action Type",
                        allow_custom_value=False,
                    )
                    value = gr.Dropdown(
                        choices=[],
                        value=None,
                        label="Value",
                        allow_custom_value=False,
                        interactive=False,
                    )
                    value_help = gr.Markdown("Value is not used for this action.")
                    rationale = gr.Textbox(
                        label="Rationale",
                        placeholder="Optional analyst note",
                    )
                with gr.Row():
                    step_btn = gr.Button("Step", variant="primary")
                    state_btn = gr.Button("Get state", variant="secondary")
                status = gr.Textbox(label="Status", interactive=False)
                raw_json = gr.Code(
                    label="Raw JSON response",
                    language="json",
                    interactive=False,
                )

        difficulty_group.change(
            fn=update_tasks_for_group,
            inputs=[difficulty_group],
            outputs=[task_selector, task_details],
        )
        task_selector.change(
            fn=update_task_details,
            inputs=[task_selector],
            outputs=[task_details],
        )
        action_type.change(
            fn=update_value_control,
            inputs=[action_type],
            outputs=[value, value_help],
        )
        reset_btn.click(
            fn=reset_with_selected_task,
            inputs=[difficulty_group, task_selector],
            outputs=[response_md, raw_json, status],
        )
        step_btn.click(
            fn=step_with_action,
            inputs=[action_type, value, rationale],
            outputs=[response_md, raw_json, status],
        )
        state_btn.click(
            fn=get_state_sync,
            outputs=[raw_json],
        )

    return demo
