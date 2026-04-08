# Baseline Report

Generated: 2026-04-08

## Scan Summary

- Project type: Python OpenEnv/FastAPI environment for banking chargeback operations.
- Package: `openenv-bankops-chargeback` in `pyproject.toml`.
- Benchmark tasks found: 6.
- Main runtime entrypoint: `server.app:app`.
- Baseline entrypoint: `python -m bankops_chargeback.baseline`.
- Tests found: `tests/test_chargeback_env.py`.
- Notes: this checkout is not inside a Git repository. `.env` exists but was not printed because it may contain secrets. `.codex` is an empty file.

## Validation Baseline

| Check | Command | Result |
| --- | --- | --- |
| Compile | `.venv/bin/python -m compileall bankops_chargeback` | PASS |
| Unit tests | `.venv/bin/python -m unittest bankops_chargeback.tests.test_chargeback_env` | PASS, 9 tests |
| Static OpenEnv validation | `.venv/bin/openenv validate bankops_chargeback` | PASS |
| Live OpenEnv validation | `.venv/bin/openenv validate --url http://127.0.0.1:8000` | PASS, 6/6 criteria |
| Server smoke test | Python `ChargebackEnv` reset and step against `http://127.0.0.1:8000` | PASS |

## Deterministic Oracle Baseline

| Task | Difficulty | Score | Success | Steps |
| --- | --- | --- | --- | --- |
| `easy_unauthorized_card_not_present` | easy | 1.00 | true | 7 |
| `medium_subscription_confusion` | medium | 1.00 | true | 8 |
| `hard_wallet_account_takeover` | hard | 1.00 | true | 9 |
| `medium_duplicate_processing_error` | medium | 1.00 | true | 8 |
| `hard_friendly_fraud_denial` | hard | 1.00 | true | 9 |
| `expert_mixed_signals_tight_budget` | expert | 1.00 | true | 8 |

Aggregate deterministic baseline:

- Average score: 1.0000
- Success rate: 1.0000

## Live Model Baseline

- Command attempted: `.venv/bin/python -m bankops_chargeback.baseline --base-url http://127.0.0.1:8000`
- Configured model: `gemini-2.0-flash-lite`
- Status: blocked before the first model step by provider quota.
- Error class: `openai.RateLimitError`
- Error summary: `429 RESOURCE_EXHAUSTED`, free-tier request/input-token quota limit was `0` for `gemini-2.0-flash-lite`.

Implementation note: the first live baseline attempt also showed that this provider rejects the OpenAI `seed` request field. `baseline.py` and `inference.py` now retry once without `seed` when the provider returns a seed-related bad request.
