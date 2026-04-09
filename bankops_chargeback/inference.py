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

from openai import OpenAI

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

_FALLBACK_ACTION_TYPE = "view_customer_profile"


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
    """Resolve runtime config with OS env first and .env as fallback."""
    load_env_file_if_needed()

    api_base_url = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("MODEL_NAME", "gpt-4.1-mini")
    hf_token = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
    openenv_base_url = os.getenv("OPENENV_BASE_URL", "http://localhost:8000")

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
        "max_tokens": 512,
        "temperature": 0.5,
    }


SYSTEM_PROMPT = (
    "You are an operations analyst inside a retail bank chargeback desk.\n"
    "Choose exactly one action per turn. Review evidence before closing the case.\n"
    "Prefer concise, policy-aligned decisions and use only the allowed values "
    "shown in the observation."
)


# ---------------------------------------------------------------------------
# Logging helpers — mirrors reference script pattern
# ---------------------------------------------------------------------------
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: ChargebackAction, reward: float, done: bool, error: Optional[str]) -> None:
    action_str = f"{action.action_type}:{action.value}" if action.value else str(action.action_type)
    error_val = error if error else "null"
    print(
        f"[STEP] step={step} action={action_str} reward={reward:.2f} "
        f"done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.4f} "
        f"rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Prompt / action helpers
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
    """Call the LLM and return the chosen action.

    On any failure, logs a [DEBUG] line and returns a safe fallback action —
    matching the reference script's pattern of never raising from the model call.
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

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
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
        "tool_choice": {"type": "function", "function": {"name": "submit_chargeback_action"}},
        "messages": messages,
    }

    try:
        response = client.chat.completions.create(**request_kwargs)
    except Exception as exc:
        exc_str = str(exc)
        # Fatal billing/auth errors — re-raise so the task aborts immediately
        if any(code in exc_str for code in ["402", "401", "403"]):
            print(f"[DEBUG] Fatal API error (will abort task): {exc}", flush=True)
            raise
        # If the error is due to unsupported `seed` param, retry without it
        if "seed" in exc_str:
            try:
                request_kwargs.pop("seed", None)
                response = client.chat.completions.create(**request_kwargs)
            except Exception as retry_exc:
                print(f"[DEBUG] Model request failed: {retry_exc}", flush=True)
                return ChargebackAction(action_type=_FALLBACK_ACTION_TYPE)
        else:
            print(f"[DEBUG] Model request failed: {exc}", flush=True)
            return ChargebackAction(action_type=_FALLBACK_ACTION_TYPE)

    try:
        message = response.choices[0].message
        if not message.tool_calls:
            print(f"[DEBUG] Model returned no tool call. Content: {message.content!r}", flush=True)
            return ChargebackAction(action_type=_FALLBACK_ACTION_TYPE)

        arguments = json.loads(message.tool_calls[0].function.arguments)
        return ChargebackAction(
            action_type=arguments["action_type"],
            value=arguments.get("value"),
            rationale=arguments.get("rationale"),
        )
    except Exception as exc:
        print(f"[DEBUG] Failed to parse model response: {exc}", flush=True)
        return ChargebackAction(action_type=_FALLBACK_ACTION_TYPE)


# ---------------------------------------------------------------------------
# Run a single task
# ---------------------------------------------------------------------------
def run_task(task_id: str, seed: int = 7) -> Dict[str, Any]:
    config = get_runtime_config()
    client = OpenAI(base_url=config["api_base_url"], api_key=config["hf_token"])
    env = ChargebackEnv(base_url=config["openenv_base_url"]).sync()

    rewards: List[float] = []
    step_count = 0
    success = False
    score = 0.0
    history: List[Dict[str, Any]] = []

    log_start(task=task_id, env=ENV_NAME, model=config["model_name"])

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
                    temperature=config["temperature"],
                    history=history,
                )

                result = env.step(action)
                step_count += 1

                reward = result.reward if result.reward is not None else 0.0
                error_msg = result.observation.last_action_error
                rewards.append(reward)

                log_step(step=step_count, action=action, reward=reward, done=result.done, error=error_msg)

                # Update conversation history (assistant action + env feedback)
                action_summary = (
                    f"action_type={action.action_type}"
                    + (f" value={action.value!r}" if action.value else "")
                    + (f" rationale={action.rationale!r}" if action.rationale else "")
                )
                history.append({"role": "assistant", "content": f"Step {step_count}: {action_summary}"})
                feedback_parts = [f"reward={reward:.2f}"]
                if error_msg:
                    feedback_parts.append(f"error={error_msg}")
                history.append(
                    {"role": "user", "content": f"Step {step_count} result: {', '.join(feedback_parts)}."}
                )

            if result.observation.grader:
                success = result.observation.grader.success
                score = result.observation.grader.score

    finally:
        try:
            env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)
        log_end(success=success, steps=step_count, score=score, rewards=rewards)

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
        try:
            run_task(task_id, seed=args.seed)
        except Exception as exc:
            # Fatal errors (e.g. 402 out-of-credits) are already logged inside
            # run_task and [END] is already emitted by the finally block.
            # Just stop processing remaining tasks — no traceback needed.
            print(f"[DEBUG] Task {task_id} aborted: {exc}", flush=True)
            break


if __name__ == "__main__":
    main()