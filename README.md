---
title: BankOps Chargeback Operations Desk
emoji: 🏦
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - banking
  - operations
---

# BankOps Chargeback Operations Desk

A real-world OpenEnv environment for retail banking operations. Agents act as dispute analysts on a chargeback desk: they inspect case evidence, classify disputes, assign the right queue, choose a policy-compliant resolution, and close the case.

This environment replaces the original echo demo with a deterministic banking workflow that is practical to grade and benchmark.

## Why This Fits The Hackathon

- **Real-world task simulation**: chargeback and fraud triage is a real banking operations workflow.
- **OpenEnv-compatible**: typed `Action`, `Observation`, `State`, and typed reward breakdown models.
- **Six benchmark tasks**: spanning easy, medium, hard, and expert difficulty levels.
- **Deterministic graders**: every task has a programmatic scorer returning a value from `0.0` to `1.0`.
- **Trajectory reward**: rewards partial progress and penalizes looping, invalid actions, and premature closure.
- **Baseline included**: a script that uses the OpenAI API client against a running environment server.

## Tasks

### 1. Easy: Unauthorized Cross-Border Ecommerce Charge
The customer still has their card, reports quickly, and the transaction is a clear unauthorized card-not-present purchase. The correct workflow is to classify it as fraud, prioritize it correctly, route it to Card Disputes, and issue provisional credit.

### 2. Medium: Recurring Subscription Misrecognition
The customer disputes a recurring digital subscription they no longer recognize. The evidence shows a long recurring history and recent legitimate usage, so the agent must avoid a fraud classification and route it as a billing dispute.

### 3. Medium: Duplicate Merchant Charge Investigation
The customer sees two identical charges from the same electronics store on the same day. Both carry the same authorization code, pointing to a merchant processing error — not fraud. The agent must read the evidence carefully to avoid a false fraud classification.

### 4. Hard: Digital Wallet Account Takeover Escalation
The dispute shows a new wallet token, a password reset from a new device, and rapid high-value spend. The agent must identify the account takeover pattern and escalate it urgently to Fraud Ops.

### 5. Hard: Friendly Fraud — Customer-Initiated Purchase Denial
The customer claims an unauthorized online purchase, but device fingerprints, browsing history, and delivery records all show the customer made the purchase themselves. The agent must resist the fraud framing and deny the chargeback claim — a counterintuitive but policy-correct decision.

### 6. Expert: Mixed-Signal Dispute Under Time Pressure
A premier customer traveling in Paris disputes a luxury purchase. Legitimate physical-card purchases coexist with a suspicious wallet token provisioned from an unknown device. The case has a strict 8-step budget — exactly enough for a perfect run with zero wasted actions. The agent must identify the hidden account takeover pattern despite the travel notice and legitimate activity.

## Action Space

Agents send a `ChargebackAction` with:

- `action_type`: one of
  - `view_customer_profile`
  - `view_transaction`
  - `view_recent_activity`
  - `view_policy`
  - `set_dispute_type`
  - `set_priority`
  - `assign_team`
  - `set_resolution`
  - `close_case`
- `value`: optional string used by the `set_*` actions (see allowed values below)
- `rationale`: optional analyst note (logged for auditability)

### Allowed Values for `set_*` Actions

| Action | `value` must be one of |
|---|---|
| `set_dispute_type` | `card_not_present_fraud`, `merchant_billing_dispute`, `merchant_processing_error`, `account_takeover` |
| `set_priority` | `low`, `medium`, `high`, `urgent` |
| `assign_team` | `card_disputes`, `billing_disputes`, `fraud_ops`, `digital_wallet_ops` |
| `set_resolution` | `approve_provisional_credit`, `deny_claim`, `request_merchant_contact`, `escalate_fraud_investigation` |

The full map is also returned live in every `ChargebackObservation.allowed_values` field.

## Observation Schema

`ChargebackObservation` includes:

- task identity and difficulty
- the visible case summary
- hidden sections revealed through review actions
- current workspace selections
- action history
- remaining step budget
- deterministic `grader` output
- typed `reward_breakdown`

The OpenEnv base observation fields are still present:

- `reward`
- `done`
- `metadata`

## Reward Design

The reward is shaped over the full trajectory:

- positive delta when the grader score improves
- small per-step penalty to encourage efficient handling
- penalty for invalid values or unsupported actions
- penalty for repeating unhelpful actions
- strong penalty for closing a case before it is solved
- success bonus when a case is closed correctly

This gives agents signal before the final step instead of only at episode termination.

## Deterministic Graders

The deterministic grader is implemented in [graders.py](./graders.py). It scores the current workspace using the task-specific target values.

Weighted components:

- required evidence reviewed
- correct dispute type
- correct priority
- correct owning team
- correct resolution
- correct final closure
- small cumulative penalty for avoidable mistakes

A perfect run scores `1.0`.

## Project Structure

```text
bankops_chargeback/
├── .dockerignore
├── BASELINE_REPORT.md
├── README.md
├── TEST_CASES.md
├── __init__.py
├── baseline.py
├── baseline_results.json
├── client.py
├── constants.py
├── Dockerfile
├── graders.py
├── inference.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── tasks.py
├── tests/
│   ├── test_chargeback_env.py
│   ├── test_inference_env.py
│   └── test_web_ui_helpers.py
└── server/
    ├── __init__.py
    ├── app.py
    ├── chargeback_environment.py
    ├── requirements.txt
    └── web_ui.py
```

## Running Locally

### 1. Install dependencies

```bash
cd bankops_chargeback
uv sync
```

### 2. Add local environment variables

Create or edit `bankops_chargeback/.env`:

```dotenv
HF_TOKEN=your_huggingface_token_here
API_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4.1-mini
OPENENV_BASE_URL=http://localhost:8000
MAX_TOKENS=512
```

Both runners prefer exported environment variables and fall back to this file when required values are missing.

### 3. Start the environment server

Run from **inside** the `bankops_chargeback` directory:

```bash
cd bankops_chargeback
uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

### 4. Run a local validation pass

```bash
openenv validate .
```

## Python Client Example

The OpenEnv client is async by default, so the easiest local workflow is to use the sync wrapper:

```python
from bankops_chargeback import ChargebackAction, ChargebackEnv

env = ChargebackEnv(base_url="http://localhost:8000").sync()
with env:
    result = env.reset(task_id="easy_unauthorized_card_not_present")
    result = env.step(ChargebackAction(action_type="view_transaction"))
    result = env.step(ChargebackAction(action_type="view_policy"))
    result = env.step(
        ChargebackAction(
            action_type="set_dispute_type",
            value="card_not_present_fraud",
        )
    )
```

## Baseline Inference Script

The baseline script connects to a running server and uses the OpenAI API client to solve all benchmark tasks.

Requirements:

- `HF_TOKEN` — mandatory, set in `bankops_chargeback/.env` or exported
- `API_BASE_URL` — defaults to `https://api.openai.com/v1`
- `MODEL_NAME` — defaults to `gpt-4.1-mini`
- `OPENENV_BASE_URL` — defaults to `http://localhost:8000`
- `MAX_TOKENS` — defaults to `512`; limits the maximum tokens in each model response

Run all tasks:

```bash
cd bankops_chargeback
python -m baseline
```

Run a single task:

```bash
cd bankops_chargeback
python -m baseline --task-id hard_wallet_account_takeover
```

Override the environment URL:

```bash
cd bankops_chargeback
python -m baseline --base-url http://localhost:8001
```

## Baseline Performance Scores

Deterministic oracle baseline generated on `2026-04-08`:

| Task | Difficulty | Score | Success |
|------|-----------|-------|---------|
| `easy_unauthorized_card_not_present` | Easy | 1.00 | ✅ |
| `medium_subscription_confusion` | Medium | 1.00 | ✅ |
| `medium_duplicate_processing_error` | Medium | 1.00 | ✅ |
| `hard_wallet_account_takeover` | Hard | 1.00 | ✅ |
| `hard_friendly_fraud_denial` | Hard | 1.00 | ✅ |
| `expert_mixed_signals_tight_budget` | Expert | 1.00 | ✅ |

Aggregate deterministic baseline:

- Average score: `1.0000`
- Success rate: `1.0000`

Live-model baseline status:

- The model is configurable via `MODEL_NAME` and `API_BASE_URL` in `.env`
- An initial attempt against `gemini-2.0-flash-lite` was blocked by provider quota: `429 RESOURCE_EXHAUSTED`
- The baseline also gracefully retries without `seed` when a provider rejects that parameter
- See [baseline_results.json](./baseline_results.json) and [BASELINE_REPORT.md](./BASELINE_REPORT.md) for the current submission-time record

## Tests

Run a single test module from inside the environment directory:

```bash
cd bankops_chargeback
uv run python -m unittest tests.test_chargeback_env
```

To run the full local suite:

```bash
cd bankops_chargeback
uv run python -m unittest \
  tests.test_chargeback_env \
  tests.test_inference_env \
  tests.test_web_ui_helpers
```

Manual case walkthroughs for the easy, medium, and hard tasks are in [TEST_CASES.md](./TEST_CASES.md).

For a step-by-step local setup and execution guide, see [SETUP_AND_RUN.md](./SETUP_AND_RUN.md).

## Submission Validation

Run the included validator script to confirm the HF Space is live, Docker builds, and `openenv validate` passes:

```bash
cd bankops_chargeback
bash validation-submission.sh https://your-space.hf.space
```

The script runs three checks in order:

1. **HF Space health** — POSTs to `<ping_url>/reset` and expects HTTP 200
2. **Docker build** — builds the image from the `Dockerfile` in the repo
3. **OpenEnv validate** — runs `openenv validate .` against the local checkout

All three must pass before submitting.

## Deployment

### Build and test the Docker image locally

```bash
cd bankops_chargeback
docker build -t bankops-chargeback:latest .
docker run -p 8000:8000 -e HF_TOKEN=your_token bankops-chargeback:latest
```

The container starts `uvicorn bankops_chargeback.server.app:app` on port 8000 and exposes a `/health` endpoint.

### Deploy to Hugging Face Spaces

```bash
cd bankops_chargeback
openenv push
```
