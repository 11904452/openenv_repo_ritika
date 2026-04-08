"""Hackathon inference script for the banking chargeback operations environment.

Reads API_BASE_URL, MODEL_NAME, and HF_TOKEN from environment variables and
emits [START]/[STEP]/[END] lines to stdout as required by the submission format.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import BadRequestError, OpenAI

try:
    from .client import ChargebackEnv
    from .constants import ACTION_TYPES
    from .models import ChargebackAction, ChargebackObservation
    from .tasks import TASK_IDS
except ImportError:
    from client import ChargebackEnv
    from constants import ACTION_TYPES
    from models import ChargebackAction, ChargebackObservation
    from tasks import TASK_IDS

ENV_NAME = "bankops-chargeback"


# ---------------------------------------------------------------------------
# Environment variables (per hackathon guidelines)
# ---------------------------------------------------------------------------
def _env_candidates() -> List[Path]:
    return [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]


def load_env_file_if_needed(
    fallback_trigger_key: str = "HF_TOKEN",
    candidates: Optional[List[Path]] = None,
) -> bool:
    """Load .env only when the required runtime env var is missing."""

    if os.getenv(fallback_trigger_key):
        return False

    env_path = next((path for path in (candidates or _env_candidates()) if path.exists()), None)
    if env_path is None:
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ and value:
            os.environ[key] = value

    return True


def get_runtime_config() -> Dict[str, Any]:
    """Resolve runtime config with OS env first and .env as fallback.

    HF_TOKEN is the hackathon-required key name.  OPENAI_API_KEY is accepted
    as an alternative so the script also works when pointed directly at the
    OpenAI API (or any other OpenAI-compatible provider that does not use HF).
    """

    load_env_file_if_needed()

    api_base_url = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4.1-mini")
    hf_token = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
    openenv_base_url = os.getenv("OPENENV_BASE_URL", "http://localhost:8000")
    max_tokens = 512
    temperature = 0.5

    if hf_token is None:
        raise ValueError(
            "HF_TOKEN environment variable is required. "
            "Set it in your .env file or export it before running. "
            "OPENAI_API_KEY is also accepted as a fallback."
        )

    return {
        "api_base_url": api_base_url,
        "model_name": model_name,
        "hf_token": hf_token,
        "openenv_base_url": openenv_base_url,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

SYSTEM_PROMPT = (
    "You are an operations analyst inside a retail bank chargeback desk.\n"
    "Choose exactly one action per turn. Review evidence before closing the case.\n"
    "Prefer concise, policy-aligned decisions and use only the allowed values "
    "shown in the observation."
)


# ---------------------------------------------------------------------------
# Prompt / action helpers (same logic as baseline.py)
# ---------------------------------------------------------------------------
def build_prompt(observation: ChargebackObservation) -> str:
    payload = {
        "task_id": observation.task_id,
        "difficulty": observation.difficulty,
        "title": observation.title,
        "objective": observation.objective,
        "case_summary": observation.case_summary,
        "visible_sections": observation.visible_sections,
        "workspace": observation.workspace.model_dump(),
        "allowed_values": observation.allowed_values,
        "remaining_steps": observation.remaining_steps,
        "last_message": observation.message,
        "action_history": observation.action_history,
    }
    return json.dumps(payload, indent=2)


def choose_action(
    client: OpenAI,
    model_name: str,
    observation: ChargebackObservation,
    seed: int,
    max_tokens: int = 512,
    temperature: float = 0.5,
    history: Optional[List[Dict[str, Any]]] = None,
) -> ChargebackAction:
    """Call the LLM to pick the next action.

    ``history`` is a list of prior-turn message dicts (alternating
    assistant / user) that are inserted between the initial user prompt
    and the current observation, giving the model memory of what it did
    in previous steps.
    """
    tool_schema = {
        "type": "function",
        "function": {
            "name": "submit_chargeback_action",
            "description": "Submit the next action to the banking operations environment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": list(ACTION_TYPES),
                    },
                    "value": {
                        "type": ["string", "null"],
                        "description": "Optional value for set_* actions.",
                    },
                    "rationale": {
                        "type": ["string", "null"],
                        "description": "Short explanation for auditability.",
                    },
                },
                "required": ["action_type"],
                "additionalProperties": False,
            },
        },
    }

    # Build the message list: system + history turns + current observation
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Inject prior-step history (assistant tool calls + user feedback pairs)
    if history:
        messages.extend(history)

    # Current observation as the latest user turn
    messages.append(
        {
            "role": "user",
            "content": (
                "Choose the next banking operations action using the tool.\n"
                f"Observation:\n{build_prompt(observation)}"
            ),
        }
    )

    request_kwargs: Dict[str, Any] = {
        "model": model_name,
        "temperature": temperature,
        "seed": seed,
        "max_tokens": max_tokens,
        "tools": [tool_schema],
        "tool_choice": {
            "type": "function",
            "function": {"name": "submit_chargeback_action"},
        },
        "messages": messages,
    }

    try:
        response = client.chat.completions.create(**request_kwargs)
    except BadRequestError as exc:
        if "seed" not in str(exc):
            raise
        request_kwargs.pop("seed", None)
        response = client.chat.completions.create(**request_kwargs)

    message = response.choices[0].message
    if not message.tool_calls:
        raise RuntimeError("Model did not return a tool call.")

    arguments = json.loads(message.tool_calls[0].function.arguments)
    return ChargebackAction(
        action_type=arguments["action_type"],
        value=arguments.get("value"),
        rationale=arguments.get("rationale"),
    )


# ---------------------------------------------------------------------------
# Formatting helpers for [START]/[STEP]/[END]
# ---------------------------------------------------------------------------
def _fmt_reward(r: float) -> str:
    return f"{r:.2f}"


def _fmt_bool(b: bool) -> str:
    return "true" if b else "false"


def _fmt_action(action: ChargebackAction) -> str:
    if action.value:
        return f"{action.action_type}:{action.value}"
    return action.action_type


def _fmt_error(last_action_error: Optional[str]) -> str:
    if not last_action_error:
        return "null"
    return last_action_error


# ---------------------------------------------------------------------------
# Run a single task
# ---------------------------------------------------------------------------
def run_task(task_id: str, seed: int = 7) -> Dict[str, Any]:
    config = get_runtime_config()
    client = OpenAI(base_url=config["api_base_url"], api_key=config["hf_token"])
    env = ChargebackEnv(base_url=config["openenv_base_url"]).sync()

    print(f"[START] task={task_id} env={ENV_NAME} model={config['model_name']}")
    sys.stdout.flush()

    rewards: List[float] = []
    step_count = 0
    success = False
    score = 0.0

    # Conversation history: list of message dicts (assistant + user pairs)
    # that are passed back to the LLM on every subsequent step so it retains
    # memory of what actions it already took and the feedback it received.
    history: List[Dict[str, Any]] = []

    try:
        with env:
            result = env.reset(task_id=task_id, seed=seed)

            while not result.done:
                action = choose_action(
                    client,
                    config["model_name"],
                    result.observation,
                    seed=seed,
                    max_tokens=config["max_tokens"],
                    history=history,
                )
                result = env.step(action)
                step_count += 1

                reward = result.reward if result.reward is not None else 0.0
                error_msg = result.observation.last_action_error
                rewards.append(reward)

                print(
                    f"[STEP] step={step_count} "
                    f"action={_fmt_action(action)} "
                    f"reward={_fmt_reward(reward)} "
                    f"done={_fmt_bool(result.done)} "
                    f"error={_fmt_error(error_msg)}"
                )
                sys.stdout.flush()

                # ----------------------------------------------------------
                # Update conversation history so the model remembers this step
                # on the next iteration. We append:
                #   1. An "assistant" turn summarising the action it chose.
                #   2. A "user" turn with the environment's feedback (reward /
                #      error), mirroring the pattern from the reference script.
                # ----------------------------------------------------------
                action_summary = (
                    f"action_type={action.action_type}"
                    + (f" value={action.value!r}" if action.value else "")
                    + (f" rationale={action.rationale!r}" if action.rationale else "")
                )
                history.append(
                    {"role": "assistant", "content": f"Step {step_count}: {action_summary}"}
                )
                feedback_parts = [f"reward={reward:.2f}"]
                if error_msg:
                    feedback_parts.append(f"error={error_msg}")
                history.append(
                    {
                        "role": "user",
                        "content": (
                            f"Step {step_count} result: "
                            + ", ".join(feedback_parts)
                            + "."
                        ),
                    }
                )

            if result.observation.grader:
                success = result.observation.grader.success
                score = result.observation.grader.score

    except Exception as exc:
        # Ensure [END] is always emitted even on exception
        rewards_str = ",".join(_fmt_reward(r) for r in rewards)
        print(
            f"[END] success=false steps={step_count} score={score:.4f} "
            f"rewards={rewards_str}"
        )
        sys.stdout.flush()
        raise exc

    rewards_str = ",".join(_fmt_reward(r) for r in rewards)
    print(
        f"[END] success={_fmt_bool(success)} steps={step_count} score={score:.4f} "
        f"rewards={rewards_str}"
    )
    sys.stdout.flush()

    return {
        "task_id": task_id,
        "success": success,
        "steps": step_count,
        "rewards": rewards,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run inference against the chargeback environment."
    )
    parser.add_argument(
        "--task-id",
        choices=TASK_IDS,
        help="Run a single task. When omitted, all benchmark tasks are evaluated.",
    )
    parser.add_argument("--seed", type=int, default=7, help="Deterministic seed")
    args = parser.parse_args()

    task_ids = [args.task_id] if args.task_id else list(TASK_IDS)
    for task_id in task_ids:
        run_task(task_id, seed=args.seed)


if __name__ == "__main__":
    main()