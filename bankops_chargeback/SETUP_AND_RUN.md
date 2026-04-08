# Setup And Run Guide

This guide is the quickest way to get the `bankops_chargeback` environment running locally, validate it, and run tests or the baseline.

## What This Environment Is

`bankops_chargeback` is an OpenEnv banking operations environment for chargeback and fraud case handling.

It includes:

- a FastAPI/OpenEnv server
- deterministic tasks across easy, medium, hard, and expert difficulty levels
- automated tests
- a baseline runner and hackathon-compliant inference script

## Prerequisites

Make sure you have:

- Python 3.10+
- the repo checked out locally
- the project virtualenv available at `.venv`
- an HF_TOKEN (or OpenAI API key used as HF_TOKEN) if you want to run the baseline

## Directory Layout

Repo root:

```text
./ai-hackathon
```

Environment directory:

```text
./ai-hackathon/bankops_chargeback
```

## 1. Activate The Virtualenv

From the repo root:

```bash
cd ./ai-hackathon
source .venv/bin/activate
```

Sanity check:

```bash
python -c "import sys; print(sys.executable)"
```

It should point to:

```text
./ai-hackathon/.venv/bin/python
```

## 2. Configure Local Environment Variables

Edit:

[`bankops_chargeback/.env`](./ai-hackathon/bankops_chargeback/.env)

Example:

```dotenv
HF_TOKEN=your_huggingface_token_here
API_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4.1-mini
OPENENV_BASE_URL=http://localhost:8000
```

Notes:

- `HF_TOKEN` is mandatory for both `baseline.py` and `inference.py`
- `API_BASE_URL` defaults to `https://api.openai.com/v1`
- `MODEL_NAME` defaults to `gpt-4.1-mini`
- `OPENENV_BASE_URL` should match the server port you actually use

## 3. Start The Server

Open one terminal and run:

```bash
cd ./ai-hackathon
source .venv/bin/activate
cd bankops_chargeback
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Expected output includes something like:

```text
Uvicorn running on http://0.0.0.0:8000
```

## 4. Validate The Environment

In a second terminal:

```bash
cd ./ai-hackathon
source .venv/bin/activate
cd bankops_chargeback
openenv validate .
```

To validate the running server:

```bash
openenv validate --url http://127.0.0.1:8000
```

You should see the runtime validation pass.

## 5. Run Automated Tests

From the repo root:

```bash
cd ./ai-hackathon
source .venv/bin/activate
python -m unittest discover -s bankops_chargeback/tests -p 'test_*.py' -v
```

Expected result:

```text
Ran 19 tests ... OK
```

## 6. Run A Quick Manual Smoke Test

```bash
cd ./ai-hackathon
source .venv/bin/activate
python - <<'PY'
from bankops_chargeback import ChargebackAction, ChargebackEnv

env = ChargebackEnv(base_url="http://127.0.0.1:8000").sync()
with env:
    result = env.reset(task_id="easy_unauthorized_card_not_present")
    print("RESET:", result.observation.message)

    result = env.step(ChargebackAction(action_type="view_transaction"))
    print("STEP:", result.observation.message)
    print("VISIBLE:", sorted(result.observation.visible_sections.keys()))
    print("REWARD:", result.reward)
    print("DONE:", result.done)
PY
```

Expected behavior:

- reset loads the easy task
- `view_transaction` reveals the transaction section
- `done` remains `False`

## 7. Run The Baseline

If your `.env` file contains a valid `HF_TOKEN`:

```bash
cd ./ai-hackathon
source .venv/bin/activate
cd bankops_chargeback
python -m baseline
```

To run a single task:

```bash
python -m baseline --task-id hard_wallet_account_takeover
```

To override the URL manually:

```bash
python -m baseline --base-url http://localhost:8000
```

## 8. Run The Inference Script (Hackathon Format)

The `inference.py` script uses the hackathon-required output format (`[START]/[STEP]/[END]`):

```bash
cd ./ai-hackathon/bankops_chargeback
HF_TOKEN=your_token python inference.py
```

To run a single task:

```bash
HF_TOKEN=your_token python inference.py --task-id easy_unauthorized_card_not_present
```

## 9. Known Good Commands

Server:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Local validation:

```bash
cd bankops_chargeback
openenv validate .
```

Runtime validation:

```bash
openenv validate --url http://127.0.0.1:8000
```

Tests:

```bash
python -m unittest discover -s bankops_chargeback/tests -p 'test_*.py' -v
```

Baseline:

```bash
cd bankops_chargeback
python -m baseline
```

Inference (hackathon format):

```bash
cd bankops_chargeback
HF_TOKEN=your_token python inference.py
```

Submission validator:

```bash
cd ./ai-hackathon/bankops_chargeback
chmod +x validate-submission.sh
./validate-submission.sh https://your-space.hf.space .
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'openai'`

You are probably using the wrong Python interpreter.

Fix:

```bash
cd ./ai-hackathon
source .venv/bin/activate
```

### `ConnectionRefusedError` or `Failed to connect`

The server is not running on that port, or your baseline URL does not match the server port.

Fix:

- start the server first
- confirm the port (default is 8000)
- keep `OPENENV_BASE_URL` aligned with the running server

### `429 insufficient_quota`

Your API key is valid, but the account currently lacks quota or billing coverage.

Fix:

- use another API key / HF_TOKEN
- add quota/billing on the account

### `python -m baseline` cannot find the `.env` file

Run it from the environment directory:

```bash
cd ./ai-hackathon/bankops_chargeback
python -m baseline
```

## Related Docs

- [README.md](./ai-hackathon/bankops_chargeback/README.md)
- [TEST_CASES.md](./ai-hackathon/bankops_chargeback/TEST_CASES.md)