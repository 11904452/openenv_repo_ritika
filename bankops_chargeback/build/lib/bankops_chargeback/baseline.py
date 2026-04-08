"""Baseline runner for the banking chargeback operations environment.

Uses the hackathon-required environment variables (HF_TOKEN, API_BASE_URL,
MODEL_NAME) and emits [START]/[STEP]/[END] output, plus a JSON summary
at the end.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

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

SYSTEM_PROMPT = """You are an operations analyst inside a retail bank chargeback desk.
Choose exactly one action per turn. Review evidence before closing the case.
Prefer concise, policy-aligned decisions and use only the allowed values shown in the observation."""


def load_env_file() -> None:
    """Load simple KEY=VALUE pairs from a local .env file without extra dependencies."""

    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    env_path = next((path for path in candidates if path.exists()), None)
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ and value:
            os.environ[key] = value


load_env_file()

# ---------------------------------------------------------------------------
# Environment variables (hackathon-required)
# ---------------------------------------------------------------------------
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4.1-mini")
HF_TOKEN = os.environ.get("HF_TOKEN")

if HF_TOKEN is None:
    raise EnvironmentError(
        "HF_TOKEN environment variable is required. "
        "Set it in your .env file or export it before running."
    )

ENV_NAME = "bankops-chargeback"
OPENENV_BASE_URL = os.environ.get("OPENENV_BASE_URL", "http://localhost:8000")


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
    model: str,
    observation: ChargebackObservation,
    seed: int,
) -> ChargebackAction:
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

    request_kwargs: Dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "seed": seed,
        "tools": [tool_schema],
        "tool_choice": {"type": "function", "function": {"name": "submit_chargeback_action"}},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Choose the next banking operations action using the tool.\n"
                    f"Observation:\n{build_prompt(observation)}"
                ),
            },
        ],
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


def _fmt_error(last_action_error: str | None) -> str:
    if not last_action_error:
        return "null"
    return last_action_error


# ---------------------------------------------------------------------------
# Run a single task
# ---------------------------------------------------------------------------
def run_task(base_url: str, model: str, task_id: str, seed: int) -> Dict[str, Any]:
    llm_client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    env = ChargebackEnv(base_url=base_url).sync()

    print(f"[START] task={task_id} env={ENV_NAME} model={model}")
    sys.stdout.flush()

    rewards: List[float] = []
    step_count = 0
    success = False

    try:
        with env:
            result = env.reset(task_id=task_id, seed=seed)
            trajectory: List[Dict[str, Any]] = []

            while not result.done:
                action = choose_action(llm_client, model, result.observation, seed=seed)
                result = env.step(action)
                step_count += 1

                trajectory.append({
                    "action_type": action.action_type,
                    "value": action.value,
                    "rationale": action.rationale,
                })

                reward = result.reward if result.reward is not None else 0.0
                rewards.append(reward)

                print(
                    f"[STEP] step={step_count} "
                    f"action={_fmt_action(action)} "
                    f"reward={_fmt_reward(reward)} "
                    f"done={_fmt_bool(result.done)} "
                    f"error={_fmt_error(result.observation.last_action_error)}"
                )
                sys.stdout.flush()

            success = result.observation.grader.success

    except Exception as exc:
        rewards_str = ",".join(_fmt_reward(r) for r in rewards)
        print(f"[END] success=false steps={step_count} rewards={rewards_str}")
        sys.stdout.flush()
        raise exc

    rewards_str = ",".join(_fmt_reward(r) for r in rewards)
    print(f"[END] success={_fmt_bool(success)} steps={step_count} rewards={rewards_str}")
    sys.stdout.flush()

    grader = result.observation.grader.model_dump()
    return {
        "task_id": task_id,
        "difficulty": result.observation.difficulty,
        "score": grader["score"],
        "success": grader["success"],
        "steps": len(trajectory),
        "final_message": result.observation.message,
        "trajectory": trajectory,
    }


def summarize(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    results = list(results)
    average_score = round(sum(item["score"] for item in results) / len(results), 4)
    success_count = sum(1 for item in results if item["success"])
    return {
        "average_score": average_score,
        "success_rate": round(success_count / len(results), 4),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baseline against the chargeback environment.")
    parser.add_argument("--base-url", default=OPENENV_BASE_URL, help="Running OpenEnv server URL")
    parser.add_argument("--model", default=MODEL_NAME, help="Model name")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic model seed")
    parser.add_argument(
        "--task-id",
        choices=TASK_IDS,
        help="Optional single task id. When omitted, all benchmark tasks are evaluated.",
    )
    args = parser.parse_args()

    task_ids = [args.task_id] if args.task_id else list(TASK_IDS)
    results = [run_task(args.base_url, args.model, task_id, seed=args.seed) for task_id in task_ids]

    # Also emit a JSON summary for convenience
    print("\n--- JSON Summary ---")
    print(json.dumps(summarize(results), indent=2))


if __name__ == "__main__":
    main()
